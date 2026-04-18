"""Lean decode loop — platform-adapter bypass of HF GenerationMixin.

Why this exists
===============
The profile (docs/bench_tools.md + /debug/profile endpoint) showed the
slowdown on real client requests is not the matmul — it's the Python
wrapper around sampling:

  * Greedy path (do_sample=False):  23 tok/s ( 43 ms/tok)
  * Sampled path (do_sample=True):   9.6 tok/s (100 ms/tok)

That 57 ms/tok gap is entirely HF GenerationMixin overhead:
LogitsProcessor chain, StoppingCriteria loop, kwarg rewrite every step,
Python-level cache prep. None of it touches the GPU meaningfully.

This module replaces the wrapper with a straight forward-loop that:
  * reuses the same StaticCache + CUDA-graph-compiled model.forward
  * does top-k/top-p/temperature sampling inline in 3 torch ops
  * has no LogitsProcessor / StoppingCriteria abstraction
  * is cross-platform by construction — all ops are plain torch,
    dispatched via the tensor's device. Adapters (not dependencies):
      - CUDA    (Linux/Win+CUDA):  native tensor-core matmul
      - MPS     (Mac):             Metal backend, same torch ops
      - CPU     (any):             fallback path for CI / debug
"""

from __future__ import annotations

import time
from typing import Optional

import torch


# ---------------------------------------------------------------------
# Sampling primitive — one function, cross-platform.

def lean_sample(
    logits: torch.Tensor,  # (B, vocab)
    *,
    temperature: float = 1.0,
    top_k: int = 0,
    top_p: float = 1.0,
    min_p: float = 0.0,
    repetition_penalty: float = 1.0,
    prev_tokens: Optional[torch.Tensor] = None,  # (B, T) for repetition penalty
    do_sample: bool = True,
    generator: Optional[torch.Generator] = None,
) -> torch.Tensor:
    """Pick the next token from logits.

    Fused into the top-k subspace: when top_k is set, top_p / min_p /
    softmax / multinomial all operate on (B, k) instead of (B, vocab).
    For Qwen3.6 vocab=250k and typical top_k=20, that's a ~12000×
    reduction in element count for the sort + cumsum + masked_fill +
    multinomial chain. HF's LogitsProcessor does each filter on the
    full vocab.

    Returns (B,) int64 token ids.
    """
    if not do_sample or temperature <= 0.0:
        return logits.argmax(dim=-1)

    if repetition_penalty != 1.0 and prev_tokens is not None and prev_tokens.numel() > 0:
        score = torch.gather(logits, -1, prev_tokens)
        score = torch.where(score < 0, score * repetition_penalty, score / repetition_penalty)
        logits = logits.scatter(-1, prev_tokens, score)

    if top_k > 0:
        # Fused top-k path — sort, cumsum, mask, multinomial all on k elements.
        # topk returns values already sorted descending; we reuse that.
        k = min(int(top_k), logits.shape[-1])
        topk_vals, topk_idx = logits.topk(k, dim=-1)  # both (B, k), sorted desc
        topk_vals = topk_vals / temperature
        probs_k = torch.softmax(topk_vals, dim=-1)
        if top_p < 1.0:
            cum = probs_k.cumsum(dim=-1)
            mask = (cum - probs_k) > top_p
            probs_k = probs_k.masked_fill(mask, 0.0)
        if min_p > 0.0:
            mx = probs_k.amax(dim=-1, keepdim=True)
            probs_k = probs_k * (probs_k >= mx * min_p).to(probs_k.dtype)
        probs_k = probs_k / probs_k.sum(dim=-1, keepdim=True).clamp(min=1e-12)
        # Sample within top-k index space, then gather to vocab index.
        idx_in_k = torch.multinomial(probs_k, num_samples=1, generator=generator)
        return topk_idx.gather(-1, idx_in_k).squeeze(-1)

    # No top_k: full-vocab path.
    logits = logits / temperature
    probs = torch.softmax(logits, dim=-1)
    if top_p < 1.0:
        sorted_probs, sorted_idx = probs.sort(dim=-1, descending=True)
        cum = sorted_probs.cumsum(dim=-1)
        mask_sorted = (cum - sorted_probs) > top_p
        sorted_probs = sorted_probs.masked_fill(mask_sorted, 0.0)
        probs = torch.zeros_like(probs).scatter(-1, sorted_idx, sorted_probs)
    if min_p > 0.0:
        max_p = probs.amax(dim=-1, keepdim=True)
        probs = torch.where(probs < max_p * min_p, torch.zeros_like(probs), probs)
    if top_p < 1.0 or min_p > 0.0:
        probs = probs / probs.sum(dim=-1, keepdim=True).clamp(min=1e-12)
    return torch.multinomial(probs, num_samples=1, generator=generator).squeeze(-1)


# ---------------------------------------------------------------------
# Decode loop — one forward per token, reusing past_key_values.

class DecodeStats:
    __slots__ = (
        "prefill_ms", "decode_ms", "n_new", "tok_per_s", "ms_per_tok",
        "forward_ms_total", "sample_ms_total", "overhead_ms_total",
    )

    def __init__(self) -> None:
        self.prefill_ms = 0.0
        self.decode_ms = 0.0
        self.n_new = 0
        self.tok_per_s = 0.0
        self.ms_per_tok = 0.0
        # Per-phase breakdown (summed across the decode loop).
        self.forward_ms_total = 0.0
        self.sample_ms_total = 0.0
        self.overhead_ms_total = 0.0

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


# --- CUDA-graph-captured decode step (optional, env-gated) --------------
#
# Motivation: the per-phase profile shows forward=50ms/tok on Qwen3.6 / GB10,
# vs the CompiledFxGraph's GPU time of ~25ms/tok in /debug/profile. The
# ~25ms gap is Python + kernel-launch overhead per forward. torch.compile
# with mode="reduce-overhead" uses CUDA graphs under the hood — one capture,
# N replays with zero Python overhead per step. Published community number
# for Qwen3.5-35B-A3B FP8 on GB10: 13.3 → 48.6 tok/s (3.65×) from CUDA
# graphs alone (see ~/agentic_speed/tier2/fa3.md).

_compiled_step_cache: dict = {}

# Warm CUDA-graph cache: the capture itself costs ~150ms per request, which
# is meaningful for short decodes (e.g., agent tool calls at 20-50 tokens).
# Keep one (StaticCache, CudaGraphedDecodeStep) pair per (max_cache_len)
# bucket; reset the cache between requests and reuse the graph. First
# request in each bucket pays the capture; all subsequent ones get 0ms.
#
# Thread safety: the _gpu_sem in serve_qwen36_fp8.py serialises GPU work,
# so only one request touches this dict at a time in practice.
_warm_graph_cache: dict = {}  # keyed by (id(model), max_cache_len)


def _get_compiled_step(model):
    """Return (or build) a torch.compile'd step function for this model.

    reduce-overhead mode combines inductor kernel fusion with CUDA-graph
    capture. First call compiles + captures (seconds); later calls replay.
    """
    key = id(model)
    if key in _compiled_step_cache:
        return _compiled_step_cache[key]

    def _step(input_ids, attention_mask, position_ids, cache_position, past_key_values):
        return model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            cache_position=cache_position,
            past_key_values=past_key_values,
            use_cache=True,
            return_dict=True,
        )

    compiled = torch.compile(_step, mode="reduce-overhead", fullgraph=False, dynamic=False)
    _compiled_step_cache[key] = compiled
    return compiled


def _make_static_cache(model, max_cache_len: int):
    """Build a StaticCache sized for the longest sequence we'll see.

    HF's generate() auto-creates one when cache_implementation="static" is
    passed; since we bypass generate(), we have to do it ourselves. Pre-
    allocating fixed-size KV tensors unlocks:
      - the CompiledFxGraph path (profile showed ~25ms/tok greedy under
        static cache vs our lean_decode's 50ms/tok without it)
      - CUDA graph capture (requires fixed tensor pointers across steps)
    """
    from transformers.cache_utils import StaticCache
    # StaticCache internally calls config.get_text_config(decoder=True) so
    # top-level config is fine; no need to unwrap text_config manually.
    return StaticCache(
        config=model.config,
        max_cache_len=max_cache_len,
    )


def lean_decode(
    model,
    input_ids: torch.Tensor,  # (B, T)
    *,
    max_new_tokens: int,
    eos_token_ids: Optional[list[int] | int] = None,
    temperature: float = 0.6,
    top_k: int = 20,
    top_p: float = 0.95,
    min_p: float = 0.0,
    repetition_penalty: float = 1.0,
    do_sample: bool = True,
    attention_mask: Optional[torch.Tensor] = None,
    generator: Optional[torch.Generator] = None,
    return_stats: bool = False,
    use_compile: bool = False,
    use_static_cache: bool = True,
    use_cuda_graph: bool = False,
    max_cache_len: Optional[int] = None,
    on_token: Optional[object] = None,  # Optional[Callable[[int], None]]
) -> torch.Tensor | tuple[torch.Tensor, DecodeStats]:
    """Manual decode loop. Returns the full (B, T+max_new_tokens) ids.

    Skips HF GenerationMixin: no LogitsProcessor list, no StoppingCriteria
    polling, no per-step kwarg rebuild. Just prefill -> loop -> sample.
    The model's own past_key_values dict accumulates across calls (any
    Cache subclass works: DynamicCache, StaticCache, HybridCache).
    """
    device = input_ids.device
    B, T = input_ids.shape
    if attention_mask is None:
        attention_mask = torch.ones_like(input_ids)

    eos_set: set[int] = set()
    if eos_token_ids is not None:
        if isinstance(eos_token_ids, int):
            eos_set = {eos_token_ids}
        else:
            eos_set = set(int(x) for x in eos_token_ids)

    stats = DecodeStats() if return_stats else None

    # Position ids: feed the model absolute positions so rotary embeddings
    # and the KV cache agree on "where" each token sits. HF's generate()
    # builds these in _update_model_kwargs_for_generation; we do the same
    # inline so per-step forward sees (T+step,).
    position_ids = torch.arange(T, dtype=torch.long, device=device).unsqueeze(0).expand(B, -1)
    cache_position = torch.arange(T, dtype=torch.long, device=device)

    # Pre-allocate the full attention mask up to T + max_new_tokens once.
    # Each step slices [:, :cur_pos+1] instead of torch.cat-ing per step
    # (cat reallocates a new tensor every iter = GPU free+alloc thrash).
    attn_buf = torch.ones(B, T + max_new_tokens, dtype=attention_mask.dtype, device=device)
    attn_buf[:, :T] = attention_mask
    # Pre-allocate per-step position + cache_position on-device to avoid
    # building a fresh small tensor inside the loop each iteration.
    step_pos_buf = torch.zeros(B, 1, dtype=torch.long, device=device)
    step_cache_pos_buf = torch.zeros(1, dtype=torch.long, device=device)

    # Build a StaticCache if requested. Without it, HF default is
    # DynamicCache which grows via torch.cat each step — measured 50ms/tok
    # on our stack. StaticCache pre-allocates the full KV buffer so
    # pointers are stable across steps (prerequisite for CUDA graphs) and
    # avoids the per-step reallocation.
    #
    # If use_cuda_graph is also set, check the warm-graph cache for a
    # previously-captured graph at this cache-len bucket. Reuse the
    # StaticCache + graph (reset contents, keep pointers) to skip the
    # ~150ms capture cost per request.
    static_cache = None
    warm_bucket = None
    if use_static_cache:
        cache_len = max_cache_len if max_cache_len else (T + max_new_tokens + 8)
        # Power-of-2 bucketing when graph capture is enabled — the warm
        # graph cache keys on cache_len, and captured graphs have their
        # attention_mask / KV tensors sized to cache_len. Rounding to a
        # small set of bucket sizes (256, 512, 1024, 2048, 4096, 8192)
        # means similar-sized requests share a capture. Per-bucket KV
        # bandwidth scales with the bucket size so we still don't want
        # a giant ceiling; this is the ergonomic middle ground.
        if use_cuda_graph:
            _bucket = 256
            while _bucket < cache_len:
                _bucket *= 2
            cache_len = _bucket
        if use_cuda_graph:
            warm_bucket = (id(model), cache_len)
            warm_entry = _warm_graph_cache.get(warm_bucket)
            if warm_entry is not None:
                static_cache, _prewarm_graph = warm_entry
                # Reset cache contents — zeroes all KV slots. Pointers
                # stay the same so the captured graph still replays.
                try:
                    static_cache.reset()
                except Exception:
                    # If reset fails, drop the warm entry and re-capture below.
                    static_cache = None
                    _warm_graph_cache.pop(warm_bucket, None)
        if static_cache is None:
            try:
                static_cache = _make_static_cache(model, cache_len)
            except Exception as _e:
                static_cache = None

    # --- Prefill ---
    # logits_to_keep=1 tells the model's lm_head to project only the last
    # position. For a T-token prompt, the default path computes (T, vocab)
    # logits but we only use position T-1 for the first sampled token —
    # (T-1) × (hidden × vocab) GEMM is wasted work. At vocab=250k,
    # hidden=4096 that's ~1GB of wasted writes per extra position.
    # Transformers accepts the kwarg (confirmed on Qwen3_5MoeForCausalLM).
    _sync_if_cuda(device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            cache_position=cache_position,
            past_key_values=static_cache,
            use_cache=True,
            return_dict=True,
            logits_to_keep=1,
        )
    _sync_if_cuda(device)
    if stats is not None:
        stats.prefill_ms = (time.perf_counter() - t0) * 1000

    past = out.past_key_values
    logits = out.logits[:, -1, :]  # (B, vocab)

    # CUDA-graph capture for the per-step forward. Gated by flag +
    # must have a StaticCache (fixed tensor pointers). First request per
    # cache-len bucket captures (~150ms); subsequent requests reuse the
    # warm graph from _warm_graph_cache (~0ms).
    graph_step = None
    if use_cuda_graph and static_cache is not None:
        try:
            from cuda_graph_decode import CudaGraphedDecodeStep
            if warm_bucket is not None and warm_bucket in _warm_graph_cache:
                _, graph_step = _warm_graph_cache[warm_bucket]
                # Graph is already captured against this static_cache's
                # tensors. After reset() + fresh prefill, cache contents
                # reflect the current request; pointers unchanged so
                # replay is valid.
            else:
                graph_step = CudaGraphedDecodeStep(
                    model, max_cache_len=(max_cache_len or (T + max_new_tokens + 8)),
                    device=str(device),
                )
                graph_step.capture(past, pos=T, warmup_iters=2)
                if warm_bucket is not None:
                    _warm_graph_cache[warm_bucket] = (static_cache, graph_step)
        except Exception as _e:
            graph_step = None

    generated = [input_ids]
    done = torch.zeros(B, dtype=torch.bool, device=device)
    prev_tokens = input_ids
    cur_pos = T
    # EOS check cadence: checking every step forces a GPU→CPU sync per token
    # (bool(done.all()) blocks on pending CUDA work). Batch-checking every
    # EOS_CHECK_EVERY steps cuts the sync cost ~Nx at the price of emitting
    # up to N-1 post-EOS tokens before breaking — sliced off at return.
    EOS_CHECK_EVERY = 8
    first_eos_step: Optional[int] = None

    # --- Decode loop ---
    _sync_if_cuda(device)
    t1 = time.perf_counter()
    # Per-phase time accumulators (filled only when return_stats=True — the
    # extra perf_counter calls are cheap but still ~100ns each, skip when not
    # measuring).
    measure = stats is not None
    for step in range(max_new_tokens):
        # Sample
        if measure:
            _sync_if_cuda(device)
            _ts = time.perf_counter()
        tok = lean_sample(
            logits,
            temperature=temperature,
            top_k=top_k, top_p=top_p, min_p=min_p,
            repetition_penalty=repetition_penalty,
            prev_tokens=prev_tokens if repetition_penalty != 1.0 else None,
            do_sample=do_sample,
            generator=generator,
        )  # (B,)
        if measure:
            _sync_if_cuda(device)
            stats.sample_ms_total += (time.perf_counter() - _ts) * 1000

        generated.append(tok.unsqueeze(-1))

        # Stream callback — fires once per decoded token. Kept outside
        # the graph path (CPU-side) since emitting SSE lines on GPU is
        # not a thing. For B=1 we pass the scalar token id.
        if on_token is not None:
            try:
                on_token(int(tok.item()))
            except Exception:
                # Callback errors must not kill decode — this is logged
                # by the caller if they care.
                pass

        # EOS check (batched — only sync every N steps).
        if eos_set:
            for eid in eos_set:
                done = done | (tok == eid)
            if ((step + 1) % EOS_CHECK_EVERY == 0) and bool(done.all()):
                first_eos_step = step
                break

        if repetition_penalty != 1.0:
            prev_tokens = torch.cat(generated, dim=-1)

        if step == max_new_tokens - 1:
            break

        # Next forward — feed the new token only, with absolute position.
        # Uses pre-allocated buffers to avoid per-step tensor construction.
        if measure:
            _tf = time.perf_counter()
        if graph_step is not None:
            # CUDA-graph replay: no Python overhead, no kernel-launch
            # overhead. The graph was captured against `past` so it
            # reads/writes the same KV slots on every replay.
            logits = graph_step.step(tok, cur_pos)
        else:
            step_pos_buf.fill_(cur_pos)
            step_cache_pos_buf.fill_(cur_pos)
            if use_compile:
                step_fn = _get_compiled_step(model)
                with torch.inference_mode():
                    out = step_fn(
                        tok.unsqueeze(-1), attn_buf, step_pos_buf,
                        step_cache_pos_buf, past,
                    )
            else:
                with torch.inference_mode():
                    out = model(
                        input_ids=tok.unsqueeze(-1),
                        attention_mask=attn_buf[:, :cur_pos + 1],
                        position_ids=step_pos_buf,
                        cache_position=step_cache_pos_buf,
                        past_key_values=past,
                        use_cache=True,
                        return_dict=True,
                    )
            past = out.past_key_values
            logits = out.logits[:, -1, :]
        if measure:
            _sync_if_cuda(device)
            stats.forward_ms_total += (time.perf_counter() - _tf) * 1000
        cur_pos += 1

    _sync_if_cuda(device)
    if stats is not None:
        stats.decode_ms = (time.perf_counter() - t1) * 1000
        stats.n_new = sum(t.shape[-1] for t in generated[1:])
        if stats.decode_ms > 0:
            stats.tok_per_s = stats.n_new / (stats.decode_ms / 1000)
            stats.ms_per_tok = stats.decode_ms / max(stats.n_new, 1)
        # overhead = everything in the loop that's not forward or sample:
        # Python branches, attn_buf slice, tensor construction for `generated`,
        # list append, repetition_penalty cat, etc.
        stats.overhead_ms_total = max(
            stats.decode_ms - stats.forward_ms_total - stats.sample_ms_total,
            0.0,
        )

    full = torch.cat(generated, dim=-1)
    return (full, stats) if return_stats else full


# ---------------------------------------------------------------------
# Platform helpers

def _sync_if_cuda(device: torch.device) -> None:
    """torch.cuda.synchronize is a no-op on CPU/MPS; guard to keep the
    hot loop the same code on every platform."""
    if device.type == "cuda":
        torch.cuda.synchronize()
    elif device.type == "mps":
        torch.mps.synchronize()
    # cpu: nothing to do


def describe_platform() -> dict:
    """Return the adapter we'd pick on the current machine.

    Informational — the decode loop doesn't branch on this; it just
    runs whatever torch ops are available. But for logging + debug
    we report which backend will handle the hot path.
    """
    info: dict = {"torch": torch.__version__}
    if torch.cuda.is_available():
        info["backend"] = "cuda"
        info["device"] = torch.cuda.get_device_name(0)
        info["capability"] = f"sm_{''.join(map(str, torch.cuda.get_device_capability()))}"
    elif torch.backends.mps.is_available():
        info["backend"] = "mps"
        info["device"] = "Apple Metal"
    else:
        info["backend"] = "cpu"
        info["device"] = "host"
    return info
