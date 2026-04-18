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

    Combines the common filters (temperature, top_k, top_p, min_p,
    repetition penalty) into ~8 torch ops. HF's equivalent is a chain
    of ~6 LogitsProcessor classes each doing its own torch ops + a
    python wrapper. Same math, one-tenth the python.

    Returns (B,) int64 token ids.
    """
    if not do_sample or temperature <= 0.0:
        return logits.argmax(dim=-1)

    if repetition_penalty != 1.0 and prev_tokens is not None and prev_tokens.numel() > 0:
        # Lower logit of any token that appeared in prev_tokens. HF's version
        # is a Python loop over batch items; we vectorise with gather/scatter.
        score = torch.gather(logits, -1, prev_tokens)
        # For neg logits we multiply; for pos we divide. One branchless expr:
        score = torch.where(score < 0, score * repetition_penalty, score / repetition_penalty)
        logits = logits.scatter(-1, prev_tokens, score)

    logits = logits / temperature

    if top_k > 0:
        # Set everything except the top-k to -inf.
        k = min(int(top_k), logits.shape[-1])
        topk_vals = logits.topk(k, dim=-1).values
        kth = topk_vals[..., -1:]
        logits = torch.where(logits < kth, torch.full_like(logits, float("-inf")), logits)

    if top_p < 1.0 or min_p > 0.0:
        probs = torch.softmax(logits, dim=-1)
        if top_p < 1.0:
            # Sort descending, cumulative sum, mask the tail past top_p.
            sorted_probs, sorted_idx = probs.sort(dim=-1, descending=True)
            cum = sorted_probs.cumsum(dim=-1)
            # Shift by one: keep the first token that crosses the threshold.
            mask_sorted = cum - sorted_probs > top_p
            sorted_probs = sorted_probs.masked_fill(mask_sorted, 0.0)
            # Scatter back to original order.
            probs = torch.zeros_like(probs).scatter(-1, sorted_idx, sorted_probs)
        if min_p > 0.0:
            # min_p: drop any token whose prob < min_p * max_prob.
            max_p = probs.amax(dim=-1, keepdim=True)
            probs = torch.where(probs < max_p * min_p, torch.zeros_like(probs), probs)
        probs = probs / probs.sum(dim=-1, keepdim=True).clamp(min=1e-12)
    else:
        probs = torch.softmax(logits, dim=-1)

    # Multinomial — cross-platform. CUDA/MPS/CPU all provide this.
    tok = torch.multinomial(probs, num_samples=1, generator=generator).squeeze(-1)
    return tok


# ---------------------------------------------------------------------
# Decode loop — one forward per token, reusing past_key_values.

class DecodeStats:
    __slots__ = ("prefill_ms", "decode_ms", "n_new", "tok_per_s", "ms_per_tok")

    def __init__(self) -> None:
        self.prefill_ms = 0.0
        self.decode_ms = 0.0
        self.n_new = 0
        self.tok_per_s = 0.0
        self.ms_per_tok = 0.0

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}


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

    # --- Prefill ---
    _sync_if_cuda(device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            cache_position=cache_position,
            use_cache=True,
            return_dict=True,
        )
    _sync_if_cuda(device)
    if stats is not None:
        stats.prefill_ms = (time.perf_counter() - t0) * 1000

    past = out.past_key_values
    logits = out.logits[:, -1, :]  # (B, vocab)

    generated = [input_ids]
    done = torch.zeros(B, dtype=torch.bool, device=device)
    prev_tokens = input_ids
    cur_pos = T

    # --- Decode loop ---
    _sync_if_cuda(device)
    t1 = time.perf_counter()
    for step in range(max_new_tokens):
        # Sample
        tok = lean_sample(
            logits,
            temperature=temperature,
            top_k=top_k, top_p=top_p, min_p=min_p,
            repetition_penalty=repetition_penalty,
            prev_tokens=prev_tokens if repetition_penalty != 1.0 else None,
            do_sample=do_sample,
            generator=generator,
        )  # (B,)

        # EOS check
        if eos_set:
            for eid in eos_set:
                done = done | (tok == eid)
            if bool(done.all()):
                generated.append(tok.unsqueeze(-1))
                break

        generated.append(tok.unsqueeze(-1))
        prev_tokens = torch.cat(generated, dim=-1) if repetition_penalty != 1.0 else None

        if step == max_new_tokens - 1:
            break

        # Next forward — feed the new token only, with absolute position.
        attention_mask = torch.cat(
            [attention_mask, torch.ones((B, 1), dtype=attention_mask.dtype, device=device)],
            dim=-1,
        )
        next_pos = torch.tensor([[cur_pos]], dtype=torch.long, device=device).expand(B, -1)
        next_cache_pos = torch.tensor([cur_pos], dtype=torch.long, device=device)
        with torch.no_grad():
            out = model(
                input_ids=tok.unsqueeze(-1),
                attention_mask=attention_mask,
                position_ids=next_pos,
                cache_position=next_cache_pos,
                past_key_values=past,
                use_cache=True,
                return_dict=True,
            )
        past = out.past_key_values
        logits = out.logits[:, -1, :]
        cur_pos += 1

    _sync_if_cuda(device)
    if stats is not None:
        stats.decode_ms = (time.perf_counter() - t1) * 1000
        stats.n_new = sum(t.shape[-1] for t in generated[1:])
        if stats.decode_ms > 0:
            stats.tok_per_s = stats.n_new / (stats.decode_ms / 1000)
            stats.ms_per_tok = stats.decode_ms / max(stats.n_new, 1)

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
