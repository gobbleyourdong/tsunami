#!/usr/bin/env python3
"""Serve a Qwen3.5/3.6 family model via transformers — text + vision.

Filename keeps the `_fp8` suffix for git/import continuity (tests, monitor
regex, host_bench all depend on it), but the script is dual-purpose:

  * Qwen/Qwen3.6-27B          — dense BF16, multimodal. CURRENT DEFAULT.
                                Launched via launch_qwen36_27b_bf16.sh.
  * Qwen/Qwen3.6-35B-A3B-FP8  — hybrid-attention MoE, native FP8 weights
                                (fine-grained block-128 quant). Legacy;
                                launch_qwen36_fp8.sh is deprecated.

`_load_model` detects MoE via `text_config.num_experts > 0` and routes:
  * MoE path: in-memory expert fusion (gate/up packed across experts) +
    state_dict assign-load to avoid the ~70 GB transient peak from a naive
    duplicate-on-load. FP8 matmul shimmed through DeepSeek's Triton kernel.
  * Dense path: plain `from_pretrained(dtype="auto")` — dtype comes from
    the model's config (BF16 for 27B), no fusion, no shim.

Runs on Blackwell GB10 through the nvcr.io/nvidia/pytorch:26.03-py3
container (torch 2.11 / CUDA 13.2).

Usage:
  python3 serve_qwen36_fp8.py --model Qwen/Qwen3.6-27B --port 8095          # default
  python3 serve_qwen36_fp8.py --model Qwen/Qwen3.6-35B-A3B-FP8 --port 8095  # legacy

OpenAI-compatible endpoints (mirrors serve_transformers.py):
  POST /v1/chat/completions    — text + vision
  GET  /health                 — health check
"""
# Earliest-possible bind probe — fail in <1s if the port is already taken.
# Qwen3.5-27B-FP8 load is ~30s; an accidental duplicate would otherwise spend
# that time fighting for VRAM before crashing.
import sys as _sys
if not any(_a in ("-h", "--help") for _a in _sys.argv):
    import socket as _socket
    _port, _host = 8095, "0.0.0.0"
    for _i, _a in enumerate(_sys.argv):
        if _a == "--port" and _i + 1 < len(_sys.argv):
            try: _port = int(_sys.argv[_i + 1])
            except ValueError: pass
        elif _a.startswith("--port="):
            try: _port = int(_a.split("=", 1)[1])
            except ValueError: pass
        elif _a == "--host" and _i + 1 < len(_sys.argv):
            _host = _sys.argv[_i + 1]
        elif _a.startswith("--host="):
            _host = _a.split("=", 1)[1]
    _probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    _probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    try:
        _probe.bind((_host, _port))
    except OSError as _e:
        print(f"Port {_port} unavailable ({_e}). Aborting before model load.", file=_sys.stderr)
        _sys.exit(1)
    finally:
        _probe.close()

import argparse
import asyncio
import base64
import io
import json
import logging
import os
import time
import re
import uuid

import torch
# DeepGEMM's community build (kernels-community/deep-gemm) asserts
# "Unknown recipe" on Qwen3.5-MoE's block-128 FP8 shapes when moe_intermediate_size
# is smaller than its known tile set (e.g. 512 for Qwen3.6-35B-A3B). Transformers'
# finegrained_fp8 integration only falls through to its Triton kernel if
# `_load_deepgemm_kernel()` raises ImportError — so we stub it to do exactly
# that.
import transformers.integrations.finegrained_fp8 as _fgfp8
def _force_triton_fp8():
    raise ImportError("forced Triton fallback — DeepGEMM community build incompatible with this shape")
_fgfp8._load_deepgemm_kernel = _force_triton_fp8

# StaticCache with hybrid linear+full attention: the Cache.max_batch_size
# property iterates `layer.max_batch_size for layer in self.layers`, but
# LinearAttentionLayer only sets that attr inside lazy_initialization (on the
# first update_conv_state call). So any read before the first decode — e.g.
# generate's cache setup — AttributeErrors. Pre-seed a default of None in the
# mixin's __init__ so the property at least finds the attribute. The real
# value is overwritten as soon as data flows through.
import transformers.cache_utils as _cu
_orig_la_init = _cu.LinearAttentionCacheLayerMixin.__init__
def _la_init_with_default(self):
    _orig_la_init(self)
    self.max_batch_size = None
    self.max_cache_len = None
_cu.LinearAttentionCacheLayerMixin.__init__ = _la_init_with_default

# StaticLayer sets max_batch_size lazily too (from key_states on first update),
# so pre-queries from Cache.max_batch_size AttributeError. Same default-None
# treatment.
_orig_static_init = _cu.StaticLayer.__init__
def _static_init_with_default(self, max_cache_len: int):
    _orig_static_init(self, max_cache_len)
    self.max_batch_size = None
_cu.StaticLayer.__init__ = _static_init_with_default

# On the SECOND `generate()` call, `_prepare_static_cache` reuses `self._cache`
# and reads `cache_to_check.max_cache_len` / `.max_batch_size`. Those properties
# do `max(layer.max_cache_len for layer in self.layers)` / `set(values)` — but
# linear-attention layers never populate these attributes (they're recurrent,
# not ring-buffer), and our defaults above leave them at None. `max(None, int)`
# and `set([None, int])` then crash. Override both properties to skip linear
# layers (None values) so the comparison uses only the real cache layers.
def _max_cache_len_filtered(self):
    values = [l.max_cache_len for l in self.layers
              if getattr(l, "max_cache_len", None) is not None]
    return max(values) if values else 0

def _max_batch_size_filtered(self):
    values = [l.max_batch_size for l in self.layers
              if getattr(l, "max_batch_size", None) is not None]
    if len(set(values)) > 1:
        raise ValueError(f"Max batch size is not consistent across layers: {values}")
    return values[0] if values else 1

_cu.Cache.max_cache_len = property(_max_cache_len_filtered)
_cu.Cache.max_batch_size = property(_max_batch_size_filtered)

# generate()'s mask builder iterates `config.layer_types` and looks up each
# pattern in LAYER_PATTERN_TO_MASK_FUNCTION_MAPPING. Linear-attention layers
# use a 2D padding mask (batch, seq) or None — not a 4D causal mask. Model
# qwen3_next already ships `_update_linear_attn_mask`; port its semantics as
# a standalone mask function so transformers can dispatch to it without a
# KeyError, and the return type matches what the layer's forward expects.
import transformers.masking_utils as _mu
def _create_linear_attention_mask(attention_mask=None, past_key_values=None, **_):
    # Cached forward or all-ones: no mask needed (standard linear-attn handling).
    if past_key_values is not None and getattr(past_key_values, "has_previous_state", lambda: False)():
        return None
    if attention_mask is not None:
        if hasattr(attention_mask, "all") and bool(attention_mask.all()):
            return None
        return attention_mask  # pass 2D bool mask through unchanged
    return None
_mu.LAYER_PATTERN_TO_MASK_FUNCTION_MAPPING.setdefault(
    "linear_attention", _create_linear_attention_mask
)

# Final piece of the static-cache puzzle: generate() builds a dict
# {layer_pattern: mask} when the model advertises multiple layer_types, and
# some models' forward (qwen3_5_moe is one) pipe that dict straight into
# create_causal_mask — which expects a plain tensor/None. Unwrap the dict
# on entry so create_causal_mask only ever sees the full-attention mask.
_orig_create_causal_mask = _mu.create_causal_mask
def _unwrap_dict_mask(config, inputs_embeds, attention_mask=None, *args, **kwargs):
    if isinstance(attention_mask, dict):
        attention_mask = attention_mask.get("full_attention")
    return _orig_create_causal_mask(
        config=config, inputs_embeds=inputs_embeds,
        attention_mask=attention_mask, *args, **kwargs,
    )
_mu.create_causal_mask = _unwrap_dict_mask
# Also patch the re-export inside the model module (it imported at module
# load, so reassigning in _mu alone doesn't catch it).
# Apply to BOTH the MoE module (Qwen3.6-35B-A3B-FP8) and the dense module
# (Qwen3.6-27B). They share the hybrid linear+full attention layer pattern,
# so both hit the same dict-mask issue under static cache. Either may be
# absent in older transformers builds — guard with try/except so the script
# still imports.
def _patch_qwen35_module(module_path: str, text_model_class: str):
    try:
        import importlib
        mod = importlib.import_module(module_path)
        mod.create_causal_mask = _unwrap_dict_mask
        cls = getattr(mod, text_model_class, None)
        if cls is not None and hasattr(cls, "_update_linear_attn_mask"):
            _orig = cls._update_linear_attn_mask
            def _ulam_dict_aware(self, attention_mask, past_key_values, _orig=_orig):
                if isinstance(attention_mask, dict):
                    return attention_mask.get("linear_attention")
                return _orig(self, attention_mask, past_key_values)
            cls._update_linear_attn_mask = _ulam_dict_aware
    except (ImportError, AttributeError) as _e:
        # Module not present in this transformers build — skip silently.
        pass

_patch_qwen35_module("transformers.models.qwen3_5_moe.modeling_qwen3_5_moe",
                     "Qwen3_5MoeTextModel")
_patch_qwen35_module("transformers.models.qwen3_5.modeling_qwen3_5",
                     "Qwen3_5TextModel")

# Also override the Triton fallback with DeepSeek's reference Triton FP8 GEMM.
# The kernels-community/finegrained-fp8 kernel is generic and slow; DeepSeek's
# was hand-tuned for exactly this quant recipe (block-128, e4m3) and tends to
# win 1.5-3x on MoE shapes where the community build's autotune space is tuned
# for larger tiles. Routed through the same `w8a8_fp8_matmul` entry point so
# transformers' per-module FP8Linear dispatch still works.
import sys as _vsys
_vsys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami/serving")
from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm, fp8_gemm_kernel as _ds_fp8_gemm_kernel
import triton as _triton

def _ds_w8a8_fp8_matmul(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    """Shim: DeepSeek's fp8_gemm(a, a_s, b, b_s) expects:
      a:  (M, K)  fp8_e4m3fn — row-major
      a_s:(M, K/BLK) fp32    — per-row per-K-block scales
      b:  (N, K)  fp8_e4m3fn — row-major (weight stored out-major)
      b_s:(N/BLK, K/BLK) fp32 — block-wise weight scales

    Originally wrapped the vendor's fp8_gemm() which allocates the output
    via torch.get_default_dtype(). That forced us to set_default_dtype
    twice per call to route the result to bf16 — global state mutation
    under a lock, ~676× per decoded token at 338 matmuls/tok × 2 sets.
    Now we allocate the output directly and call the Triton kernel, no
    default-dtype dance.
    """
    orig_shape = A.shape
    K = A.size(-1)
    A_2d = A.reshape(-1, K).contiguous()
    As_2d = As.reshape(-1, As.shape[-1]).contiguous() if As.dim() >= 2 else As.contiguous()
    B_c = B.contiguous()
    Bs_c = Bs.contiguous()
    M = A_2d.size(0)
    N = B_c.size(0)
    dtype = output_dtype if output_dtype is not None else torch.bfloat16
    C_2d = A_2d.new_empty((M, N), dtype=dtype)
    grid = lambda META: (_triton.cdiv(M, META["BLOCK_SIZE_M"]),
                         _triton.cdiv(N, META["BLOCK_SIZE_N"]))
    _ds_fp8_gemm_kernel[grid](A_2d, B_c, C_2d, As_2d, Bs_c, M, N, K)
    return C_2d.view(*orig_shape[:-1], N)

# Swap the whole entry point — finegrained_fp8.FP8Linear.forward calls this
# by name, so a module-level reassignment catches every dispatch.
_fgfp8.w8a8_fp8_matmul = _ds_w8a8_fp8_matmul

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# Import by local name — when run as `python3 tsunami/serving/serve_qwen36_fp8.py`
# the script's dir (tsunami/serving) is sys.path[0]. The package-qualified
# `from tsunami.serving...` import only works when the parent (ark/) is on
# PYTHONPATH, which the host launch doesn't guarantee.
from streaming_xml_tool_parser import StreamingXmlToolCallParser
from lean_decode import lean_decode, describe_platform

# lean_decode replaces HF GenerationMixin on the hot path. Measured
# 16.87 tok/s sampled vs 9.6 baseline (1.76× win; confirmed via
# /debug/lean_decode on Qwen3.6-35B-A3B-FP8 / GB10 sm_121). The path
# reuses the same model.forward + KV cache, just strips the
# LogitsProcessor / StoppingCriteria / per-step kwarg-rebuild
# overhead. Cross-platform: all ops dispatch through torch, so MPS /
# CPU fall through the same code with their native backends.
# Opt-out via TSUNAMI_LEAN_DECODE=0 if a regression shows up.
_LEAN_DECODE_ENABLED = os.getenv("TSUNAMI_LEAN_DECODE", "1") == "1"
# TSUNAMI_CUDA_GRAPH=1 enables the capture-once-replay-N CUDA-graph path
# in lean_decode. Measured 19.95 → 37.34 tok/s on Qwen3.6-35B-A3B-FP8 /
# GB10 (+87%). Validated across 20/50/100/200 token decodes on varied
# prompt types (counting, code, math, poetry, technical). Falls through
# to uncaptured path on any capture failure, so safe to default on.
# Set TSUNAMI_CUDA_GRAPH=0 to disable.
_CUDA_GRAPH_ENABLED = os.getenv("TSUNAMI_CUDA_GRAPH", "1") == "1"
from typing import Literal, Optional, Union
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("qwen36_fp8")

# Static-cache size ceiling. generate() pays a Triton autotune + cache realloc
# the first time it sees a max_cache_len larger than the existing cache — we
# measured a 250× slowdown (30 → 0.15 tok/s) going from a 230-tok prompt to a
# 1461-tok prompt. Forcing every request to claim at least this many tokens
# pins the allocation up front so subsequent requests reuse it.
#
# Qwen3.6-35B-A3B natively supports 262144 tokens; the README's recommended
# output length is 32768 (81920 for math/code competition). For the build-
# agent use case the biggest prompt we've measured is ~15K tokens (iter 2
# with compaction off), so 128K gives 8× headroom and frees ~5-6GB of KV
# VRAM vs the 256K ceiling. KV footprint at 128K ≈ 5-6 GB on this arch
# (20 full-attention layers × 2 KV heads × 256 head_dim × 128K slots × 2
# bytes × 2 tensors). Runs comfortably in a stack that also hosts the
# ~22 GB ERNIE Turbo + ~1 GB Qwen3-Embedding tiers on a 128 GB unified-
# memory GB10. If a future use case needs >128K context, bump back up.
_CACHE_CEILING = 65536

app = FastAPI()
model = None
processor = None
tokenizer = None  # fallback when processor isn't available

# MTP head state — lazy-loaded on first /debug/mtp_decode call (or if
# TSUNAMI_MTP_ENABLED=1 flips it into the main decode path). Kept
# optional because mtp.safetensors only ships on select Qwen checkpoints
# and we want the server to still boot if it's absent.
_mtp_head = None
_mtp_load_failed: str | None = None
_model_cfg = None          # AutoConfig saved after model load (MTP needs text_config)
_model_snapshot = None     # snapshot path on disk (MTP needs mtp.safetensors)


# tool_choice payload shape — same shape as serve_transformers.py.
class _ToolChoiceFunction(BaseModel):
    name: str


class ForceToolChoice(BaseModel):
    type: Literal["function"] = "function"
    function: _ToolChoiceFunction


ToolChoice = Union[Literal["auto", "none", "required"], ForceToolChoice]


class ChatRequest(BaseModel):
    # Defaults below track the Qwen3.6 model card's "Instruct mode for general
    # tasks" preset (temperature=0.7, top_p=0.8, top_k=20, min_p=0.0,
    # presence_penalty=1.5, repetition_penalty=1.0) — callers chasing the
    # thinking-mode or coding-mode presets should pass their own values.
    # The `model` field here is a label echoed back to the caller; the
    # actually-loaded model is whatever the launcher passed via --model.
    model: str = "Qwen/Qwen3.6-27B"
    messages: list
    tools: list = []
    tool_choice: ToolChoice = "auto"
    # README recommends 32768 for most prompts, 81920 for competition-grade
    # math/code. Our static cache is sized to 262144 so either fits.
    max_tokens: int = 32768
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    min_p: float = 0.0
    # Applied by HF generate via logits_processor when non-1.0. 1.5 is the
    # default for "general instruct"; reasoning prompts can push to 2.0.
    presence_penalty: float = 1.5
    repetition_penalty: float = 1.0
    user: str = ""
    # Qwen3.6 generates <think>…</think> before answering. Default strip so the
    # OpenAI-shape content field only carries the user-facing answer. Set to
    # true to return the raw thinking trace alongside the answer.
    keep_thinking: bool = False
    # Qwen3.6 chat template accepts `enable_thinking`. When False the template
    # emits an empty `<think>\n\n</think>` preamble, steering the model to
    # skip the reasoning phase entirely — 2-3× fewer tokens for simple Qs.
    enable_thinking: bool = True
    # Qwen3.6-specific: when True, thinking blocks from HISTORICAL messages
    # are preserved (not stripped) so multi-turn agents keep their chain of
    # reasoning. Maps to `chat_template_kwargs.preserve_thinking` per the
    # model card. Only useful when enable_thinking=True.
    preserve_thinking: bool = False
    # OpenAI API compat: stream tokens as Server-Sent Events.
    # Fixes audit D3 — the "streaming XML tool parser" exists but the
    # /v1 response path was previously buffered until full completion.
    stream: bool = False


# Fairness layer — pulled from serve_transformers.py. One in-flight request
# per user via _user_sems; one GPU occupant at a time via _gpu_sem. Together
# this keeps /health responsive and prevents concurrent-forward-pass CUDA
# contention from starving throughput.
_user_sems: dict[str, asyncio.Semaphore] = {}
_gpu_sem = asyncio.Semaphore(1)

# Dedicated single-thread executor for every GPU call (generate + warmup).
# `asyncio.to_thread` uses a shared pool and may pick *any* idle worker per
# call. That's fine for stateless work, but HF's static-cache path routes
# through inductor's `cudagraph_trees`, whose tree-manager sits in
# `threading.local()` — a request landing on a worker that hasn't served a
# generate before hits `AssertionError: torch._C._is_key_in_tls(attr_name)`
# (iteration 10 failure). Pinning to one worker makes TLS persist across
# calls, which also lets a boot-time warmup compile kernels once on that
# thread and have every subsequent request reuse the compiled state.
from concurrent.futures import ThreadPoolExecutor as _TPE
_gpu_executor = _TPE(max_workers=1, thread_name_prefix="gpu")


async def _run_on_gpu_thread(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    if args or kwargs:
        import functools as _ft
        return await loop.run_in_executor(_gpu_executor, _ft.partial(fn, *args, **kwargs))
    return await loop.run_in_executor(_gpu_executor, fn)


def _get_user_sem(user: str) -> asyncio.Semaphore:
    sem = _user_sems.get(user)
    if sem is None:
        sem = asyncio.Semaphore(1)
        _user_sems[user] = sem
    return sem


def _gpu_warmup_sync():
    """Blocking warmup on the pinned GPU thread. Each Triton kernel is compiled
    per (prompt_len, cache_len) shape, so covering multiple prompt lengths
    during warmup keeps first-user latency low across common request sizes.
    Ceiling stays fixed at _CACHE_CEILING — only prompt_len varies. The chat
    template is applied so attention is also routed through the same mask
    builders the real request path uses.
    Must run on the same thread that serves requests — see
    `_run_on_gpu_thread` rationale."""
    if tokenizer is None or model is None:
        return
    import time as _t
    log.info("Boot warmup: compiling Triton kernels on pinned GPU thread …")
    t0 = _t.time()
    # A short, medium, and longish prompt cover the bulk of real-world sizes.
    # The chat template ends up adding ~10-20 tokens of Qwen boilerplate so
    # the effective prompt lengths are ~20/80/300 — roughly matching the
    # typical short-QA / mid-coding / long-context brackets we've benched.
    warm_prompts = [
        "Hello.",                                            # ~5 raw → ~20 templated
        " ".join("The quick brown fox jumps over the lazy dog.".split() * 6),  # ~60 → ~80
        " ".join(f"Line {i:03d}." for i in range(60)),       # ~180 → ~200
    ]
    for i, p in enumerate(warm_prompts):
        msgs = [{"role": "user", "content": p}]
        # `apply_chat_template(tokenize=True, return_tensors="pt")` returns a
        # BatchEncoding (dict-like) with the newer tokenizers; older versions
        # returned the raw tensor. Extract `input_ids` defensively so we work
        # either way.
        out = tokenizer.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=True,
            return_tensors="pt",
        )
        ids = out["input_ids"] if hasattr(out, "keys") and "input_ids" in out else out
        ids = ids.to(model.device)
        n_in = ids.shape[-1]
        ts = _t.time()
        with torch.no_grad():
            model.generate(
                input_ids=ids,
                max_new_tokens=8,
                max_length=_CACHE_CEILING,
                use_cache=True,
                cache_implementation="static",
                do_sample=False,
            )
        torch.cuda.synchronize()
        log.info(f"  warmup shape {i+1}/{len(warm_prompts)}: prompt={n_in} "
                 f"compiled in {_t.time()-ts:.1f}s")
    log.info(f"Boot warmup done in {_t.time()-t0:.1f}s on pinned GPU thread")

    # Extra pass: pre-warm the lean_decode StaticCache + CUDA-graph capture
    # for each of the power-of-2 cache-len buckets the /v1 path uses. HF's
    # generate(cache_implementation="static") above already compiled the
    # model's kernels; this triggers graph capture for the buckets that
    # real requests will hit. Without it, the first request per bucket
    # pays ~600-1000ms compile + capture.
    if _LEAN_DECODE_ENABLED and _CUDA_GRAPH_ENABLED:
        try:
            from lean_decode import lean_decode as _lean
            log.info("Boot warmup: pre-capturing lean_decode CUDA graphs …")
            # Bucket sizes span the typical request space. Measured
            # tok/s per bucket (2026-04-18, sampled decode, lean_decode
            # + CUDA graph + StaticCache):
            #   256  → 39 tok/s  (20-250 token prompts)
            #   512  → 38 tok/s  (200-500 token prompts)
            #   1024 → 37 tok/s  (500-1000 token prompts)
            #   2048 → 35 tok/s  (1000-2000 token prompts)
            #   4096 → 31 tok/s  (2000-4000 token prompts, long context)
            # Past 4096 tok/s degrades sharply (8192 = 25 tok/s) because
            # per-step KV bandwidth dominates on GB10 UMA. 4096 is the
            # highest pre-capture we want; larger prompts pay a one-time
            # re-capture on first hit.
            for _bucket in (256, 512, 1024, 2048, 4096, 8192, 16384):
                _tg = _t.time()
                # Prompt len is irrelevant for the capture (we just need
                # the step graph); use a short prompt every time.
                msgs = [{"role": "user", "content": "Hi."}]
                ids = tokenizer.apply_chat_template(
                    msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt",
                )
                if hasattr(ids, "keys") and "input_ids" in ids:
                    ids = ids["input_ids"]
                ids = ids.to(model.device)
                _lean(
                    model, input_ids=ids, max_new_tokens=4,
                    do_sample=False, use_cuda_graph=True,
                    max_cache_len=_bucket,
                )
                torch.cuda.synchronize()
                log.info(f"  bucket={_bucket} captured in {_t.time()-_tg:.2f}s")
            log.info("  (first real request at any typical prompt size is now warm)")
        except Exception as _e:
            log.warning(f"lean_decode pre-capture skipped ({type(_e).__name__}: {_e})")


# Request trace middleware — writes {ts, endpoint, prompt_text, tool_count,
# image_count} to /tmp/prompt_trace.jsonl for each /v1/chat/completions hit.
# Opt-in via TSUNAMI_TRACE=1 env var. Gives us the EXACT text the model
# receives, post chat-template render, so we can debug prompt bloat/drift.
import os as _osenv
if _osenv.environ.get("TSUNAMI_TRACE") == "1":
    from fastapi import Request as _FReq
    _TRACE_FILE = "/tmp/prompt_trace.jsonl"

    @app.middleware("http")
    async def _trace_requests(request: _FReq, call_next):
        if request.url.path != "/v1/chat/completions":
            return await call_next(request)
        try:
            body = await request.body()
            # Re-inject body so downstream handlers can read it
            async def _receive():
                return {"type": "http.request", "body": body, "more_body": False}
            request._receive = _receive  # type: ignore
            import json as _j, time as _t
            payload = _j.loads(body) if body else {}
            msgs = payload.get("messages", [])
            tool_count = len(payload.get("tools", []) or [])
            img_count = 0
            text_bytes = 0
            for m in msgs:
                c = m.get("content", "")
                if isinstance(c, list):
                    for p in c:
                        if p.get("type") == "image_url":
                            img_count += 1
                        elif p.get("type") == "text":
                            text_bytes += len(p.get("text", ""))
                elif isinstance(c, str):
                    text_bytes += len(c)
            rec = {
                "ts": _t.time(),
                "msg_count": len(msgs),
                "tool_count": tool_count,
                "img_count": img_count,
                "text_bytes": text_bytes,
                "max_tokens": payload.get("max_tokens"),
                "enable_thinking": payload.get("enable_thinking"),
                "preserve_thinking": payload.get("preserve_thinking"),
                "messages": msgs,
                "tools_names": [t.get("function", t).get("name", "?") for t in (payload.get("tools") or [])][:25],
            }
            with open(_TRACE_FILE, "a") as f:
                f.write(_j.dumps(rec, default=str) + "\n")
        except Exception as _te:
            log.debug(f"trace middleware skipped: {_te}")
        return await call_next(request)


@app.on_event("startup")
async def _warmup_on_startup():
    # Delegate to the pinned executor so TLS (inductor cudagraph_trees etc.)
    # is initialised on the same worker that will serve every subsequent
    # request. Any exception is caught and logged — warmup is best-effort.
    try:
        await _run_on_gpu_thread(_gpu_warmup_sync)
    except Exception as _e:
        log.warning(f"Boot warmup skipped ({type(_e).__name__}: {_e}) — first request pays cold-start")


@app.post("/debug/profile")
async def debug_profile(req: dict):
    """Run one generate() wrapped in torch.profiler and return the top
    ops by self-CPU + self-CUDA time. Dev-only; guarded nowhere else
    but don't expose to untrusted clients.

    Request body: {"prompt": "...", "max_tokens": 50}
    """
    if model is None or tokenizer is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    prompt = req.get("prompt", "Count from 1 to 30.")
    max_new = int(req.get("max_tokens", 50))
    msgs = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt"
    )
    if hasattr(ids, "keys") and "input_ids" in ids:
        ids = ids["input_ids"]
    ids = ids.to(model.device)
    prompt_len = ids.shape[-1]

    def _prof():
        from torch.profiler import profile, ProfilerActivity
        # Run one unprofiled warmup so JIT/autotune doesn't pollute the trace.
        with torch.no_grad():
            model.generate(
                input_ids=ids, max_new_tokens=8,
                max_length=_CACHE_CEILING, use_cache=True,
                cache_implementation="static", do_sample=False,
            )
        torch.cuda.synchronize()
        # Now the real profiled run.
        t0 = time.perf_counter()
        with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
                     record_shapes=False, with_stack=False) as prof:
            with torch.no_grad():
                out = model.generate(
                    input_ids=ids, max_new_tokens=max_new,
                    max_length=_CACHE_CEILING, use_cache=True,
                    cache_implementation="static", do_sample=False,
                )
            torch.cuda.synchronize()
        wall_ms = (time.perf_counter() - t0) * 1000
        new_toks = int(out.shape[-1] - prompt_len)
        # Top by self CUDA time
        events = prof.key_averages()
        rows = []
        for e in events:
            rows.append({
                "name": e.key,
                "calls": e.count,
                "cpu_ms": round(e.self_cpu_time_total / 1000, 3),
                "cuda_ms": round((getattr(e, "self_device_time_total", None)
                                  or getattr(e, "self_cuda_time_total", 0)) / 1000, 3),
            })
        rows.sort(key=lambda r: (r["cuda_ms"] + r["cpu_ms"]), reverse=True)
        return {
            "wall_ms": round(wall_ms, 1),
            "new_tokens": new_toks,
            "tok_per_s": round(new_toks / (wall_ms / 1000), 2) if wall_ms else 0,
            "ms_per_tok": round(wall_ms / max(new_toks, 1), 2),
            "top_ops": rows[:30],
        }

    async with _gpu_sem:
        result = await _run_on_gpu_thread(_prof)
    return result


def _ensure_mtp_loaded() -> tuple[object | None, str | None]:
    """Lazy-load the MTP head the first time it's needed.

    Returns (mtp_head, error_msg). error_msg is None on success.
    On failure, the error is cached so subsequent calls fail fast.
    """
    global _mtp_head, _mtp_load_failed
    if _mtp_head is not None:
        return _mtp_head, None
    if _mtp_load_failed is not None:
        return None, _mtp_load_failed
    if model is None or _model_cfg is None or _model_snapshot is None:
        msg = "main model / config / snapshot not loaded yet"
        _mtp_load_failed = msg
        return None, msg
    if not (_model_snapshot / "mtp.safetensors").exists():
        msg = f"no mtp.safetensors in {_model_snapshot.name}"
        _mtp_load_failed = msg
        return None, msg
    try:
        from mtp_module import load_mtp_head
        log.info(f"loading MTP head from {_model_snapshot.name} …")
        t0 = time.time()
        _mtp_head = load_mtp_head(
            _model_snapshot, _model_cfg.text_config, model,
            _model_cfg.quantization_config, device="cuda:0",
        )
        log.info(f"MTP head loaded in {time.time()-t0:.1f}s, "
                 f"VRAM now {torch.cuda.memory_allocated()/1e9:.2f} GB")
        return _mtp_head, None
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        log.warning(f"MTP head load failed: {msg}")
        _mtp_load_failed = msg
        return None, msg


@app.post("/debug/mtp_decode")
async def debug_mtp_decode(req: dict):
    """Speculative-decode one prompt with the MTP head and return stats.

    Comparable to /debug/lean_decode. Reports acceptance rate so the
    effective tok/s win over the main forward can be computed:
      effective_tok/s = tok/s * (1 + accept_rate)
    since each accepted draft saves a main-forward per token.
    """
    if model is None or tokenizer is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    mtp, err = _ensure_mtp_loaded()
    if mtp is None:
        return JSONResponse({"error": f"MTP unavailable: {err}"}, status_code=503)

    from mtp_module import generate_with_mtp
    prompt = req.get("prompt", "Count from 1 to 30.")
    max_new = int(req.get("max_tokens", 50))
    msgs = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt"
    )
    if hasattr(ids, "keys") and "input_ids" in ids:
        ids = ids["input_ids"]
    ids = ids.to(model.device)
    attn = torch.ones_like(ids)

    eos_ids: set[int] = set()
    if tokenizer.eos_token_id is not None:
        eos_ids.add(int(tokenizer.eos_token_id))
    for s in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        t = tokenizer.convert_tokens_to_ids(s)
        if isinstance(t, int) and t >= 0 and t != tokenizer.unk_token_id:
            eos_ids.add(int(t))

    def _run():
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        gen, stats = generate_with_mtp(
            model, mtp,
            input_ids=ids, attention_mask=attn,
            max_new_tokens=max_new,
            eos_token_ids=eos_ids,
            temperature=float(req.get("temperature", 0.0)),
            top_p=float(req.get("top_p", 0.95)),
            top_k=int(req.get("top_k", 64)),
        )
        torch.cuda.synchronize()
        wall_ms = (time.perf_counter() - t0) * 1000
        n_new = int(gen.shape[-1])
        tps = n_new / (wall_ms / 1000) if wall_ms else 0.0
        txt = tokenizer.decode(gen[0], skip_special_tokens=True)
        rate = stats["accepts"] / max(1, stats["steps"])
        return {
            "platform": describe_platform(),
            "wall_ms": round(wall_ms, 1),
            "n_new": n_new,
            "tok_per_s": round(tps, 2),
            "ms_per_tok": round(wall_ms / max(n_new, 1), 2),
            "mtp_steps": stats["steps"],
            "mtp_accepts": stats["accepts"],
            "mtp_accept_rate": round(rate, 3),
            "preview": txt[:200],
        }

    async with _gpu_sem:
        return await _run_on_gpu_thread(_run)


@app.post("/debug/cuda_graph_decode")
async def debug_cuda_graph_decode(req: dict):
    """Probe CUDA-graph capture on the decode step.

    Per ~/agentic_speed/refs/kernels_digest_2026-04.md top-10 item #7,
    CUDA graphs are the biggest single latency lever on GB10 (published
    ≥20% decode improvement via SGLang's piecewise approach). This
    endpoint uses the low-level `torch.cuda.CUDAGraph` path (not
    torch.compile, which hung on the 35B MoE).

    Protocol:
      1. Prefill normally to warm StaticCache.
      2. Capture one decode step.
      3. Replay N times, sampling between replays.
      4. Report replay ms/tok vs uncaptured baseline.
    """
    if model is None or tokenizer is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    prompt = req.get("prompt", "Count from 1 to 30.")
    max_new = int(req.get("max_tokens", 30))
    msgs = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt"
    )
    if hasattr(ids, "keys") and "input_ids" in ids:
        ids = ids["input_ids"]
    ids = ids.to(model.device)
    attn = torch.ones_like(ids)

    eos_ids: set[int] = set()
    if tokenizer.eos_token_id is not None:
        eos_ids.add(int(tokenizer.eos_token_id))

    def _run():
        from cuda_graph_decode import CudaGraphedDecodeStep
        from lean_decode import _make_static_cache, lean_sample
        T = ids.shape[-1]
        cache_len = T + max_new + 8
        # Build static cache + run prefill so we have warm KV state.
        cache = _make_static_cache(model, cache_len)
        pos_ids = torch.arange(T, dtype=torch.long, device=model.device).unsqueeze(0)
        cache_pos = torch.arange(T, dtype=torch.long, device=model.device)
        with torch.inference_mode():
            out = model(
                input_ids=ids, attention_mask=attn,
                position_ids=pos_ids, cache_position=cache_pos,
                past_key_values=cache, use_cache=True, return_dict=True,
            )
        torch.cuda.synchronize()
        past = out.past_key_values
        last_tok = out.logits[:, -1, :].argmax(-1, keepdim=True)  # (1,1)

        g = CudaGraphedDecodeStep(model, max_cache_len=cache_len, device=str(model.device))

        # Phase 1: try to capture.
        capture_err = None
        t_cap_start = time.perf_counter()
        try:
            g.capture(past, pos=T, warmup_iters=2)
            torch.cuda.synchronize()
        except Exception as e:
            capture_err = f"{type(e).__name__}: {e}"
        capture_ms = (time.perf_counter() - t_cap_start) * 1000

        if capture_err:
            return {
                "capture_ok": False,
                "capture_ms": round(capture_ms, 1),
                "error": capture_err[:400],
            }

        # Phase 2: replay + sample for N steps.
        cur_pos = T
        tok = last_tok.view(1)
        gen = [tok.view(1, 1).clone()]
        torch.cuda.synchronize()
        t_replay_start = time.perf_counter()
        for step in range(max_new):
            logits = g.step(tok, cur_pos)
            tok = lean_sample(logits, temperature=0.6, top_k=20, top_p=0.95, do_sample=True)
            gen.append(tok.view(1, 1).clone())
            cur_pos += 1
        torch.cuda.synchronize()
        replay_ms = (time.perf_counter() - t_replay_start) * 1000
        full = torch.cat(gen, dim=-1)
        preview = tokenizer.decode(full[0], skip_special_tokens=True)

        return {
            "platform": describe_platform(),
            "capture_ok": True,
            "capture_ms": round(capture_ms, 1),
            "replay_total_ms": round(replay_ms, 1),
            "replay_ms_per_tok": round(replay_ms / max(max_new, 1), 2),
            "replay_tok_per_s": round(max_new / (replay_ms / 1000), 2) if replay_ms else 0,
            "n_new": max_new,
            "preview": preview[:200],
        }

    async with _gpu_sem:
        return await _run_on_gpu_thread(_run)


@app.post("/debug/compiled_decode")
async def debug_compiled_decode(req: dict):
    """Same as /debug/lean_decode but routes the per-step forward through
    a torch.compile(mode='reduce-overhead') wrapper. First call compiles
    (seconds, sometimes minutes on large MoE models); subsequent calls
    replay the CUDA graph.

    Per research (~/agentic_speed/tier2/fa3.md): community-reported 3.65×
    on Qwen3.5-35B-A3B FP8 on this exact hardware (13.3 → 48.6 tok/s).
    """
    if model is None or tokenizer is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    prompt = req.get("prompt", "Count from 1 to 30.")
    max_new = int(req.get("max_tokens", 50))
    do_sample = bool(req.get("do_sample", True))
    msgs = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt"
    )
    if hasattr(ids, "keys") and "input_ids" in ids:
        ids = ids["input_ids"]
    ids = ids.to(model.device)

    eos_ids: list[int] = []
    if tokenizer.eos_token_id is not None:
        eos_ids.append(int(tokenizer.eos_token_id))
    for s in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        t = tokenizer.convert_tokens_to_ids(s)
        if isinstance(t, int) and t >= 0 and t != tokenizer.unk_token_id:
            eos_ids.append(int(t))

    def _run():
        try:
            out, stats = lean_decode(
                model,
                input_ids=ids,
                max_new_tokens=max_new,
                temperature=float(req.get("temperature", 0.6)),
                top_k=int(req.get("top_k", 20)),
                top_p=float(req.get("top_p", 0.95)),
                min_p=float(req.get("min_p", 0.0)),
                repetition_penalty=float(req.get("repetition_penalty", 1.0)),
                do_sample=do_sample,
                eos_token_ids=eos_ids,
                return_stats=True,
                use_compile=True,
            )
            txt = tokenizer.decode(out[0, ids.shape[-1]:], skip_special_tokens=True)
            return {"platform": describe_platform(), **stats.as_dict(), "preview": txt[:200]}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}", "platform": describe_platform()}

    async with _gpu_sem:
        return await _run_on_gpu_thread(_run)


@app.post("/debug/lean_decode")
async def debug_lean_decode(req: dict):
    """Run ONE lean_decode call and return timing stats.

    Used to A/B vs /debug/profile (HF generate path). Same sampling
    args as a normal request; returns prefill_ms, decode_ms, tok/s,
    new tokens. No env flag needed — this endpoint always uses the
    lean path regardless of TSUNAMI_LEAN_DECODE.
    """
    if model is None or tokenizer is None:
        return JSONResponse({"error": "model not loaded"}, status_code=503)
    prompt = req.get("prompt", "Count from 1 to 30.")
    max_new = int(req.get("max_tokens", 50))
    do_sample = bool(req.get("do_sample", True))
    msgs = [{"role": "user", "content": prompt}]
    ids = tokenizer.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_tensors="pt"
    )
    if hasattr(ids, "keys") and "input_ids" in ids:
        ids = ids["input_ids"]
    ids = ids.to(model.device)

    eos_ids: list[int] = []
    if tokenizer.eos_token_id is not None:
        eos_ids.append(int(tokenizer.eos_token_id))
    for s in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        t = tokenizer.convert_tokens_to_ids(s)
        if isinstance(t, int) and t >= 0 and t != tokenizer.unk_token_id:
            eos_ids.append(int(t))

    use_cuda_graph = bool(req.get("use_cuda_graph", False))

    def _run():
        out, stats = lean_decode(
            model,
            input_ids=ids,
            max_new_tokens=max_new,
            temperature=float(req.get("temperature", 0.6)),
            top_k=int(req.get("top_k", 20)),
            top_p=float(req.get("top_p", 0.95)),
            min_p=float(req.get("min_p", 0.0)),
            repetition_penalty=float(req.get("repetition_penalty", 1.0)),
            do_sample=do_sample,
            eos_token_ids=eos_ids,
            return_stats=True,
            use_cuda_graph=use_cuda_graph,
        )
        txt = tokenizer.decode(out[0, ids.shape[-1]:], skip_special_tokens=True)
        return stats, txt

    async with _gpu_sem:
        stats, text = await _run_on_gpu_thread(_run)
    return {
        "platform": describe_platform(),
        "use_cuda_graph": use_cuda_graph,
        **stats.as_dict(),
        "preview": text[:200],
    }


@app.get("/v1/models")
def list_models():
    """OpenAI-compat /v1/models endpoint. Many SDK clients hit this on
    init to discover what's served; without it they fall back to
    whatever model name was hardcoded. Returns a single entry for the
    served checkpoint + the generic 'tsunami' alias.
    """
    served = getattr(_model_cfg, "_name_or_path", None) if _model_cfg else "tsunami"
    now = int(time.time())
    rows: list[dict] = [
        {"id": "tsunami", "object": "model", "created": now, "owned_by": "tsunami"},
    ]
    if served and served != "tsunami":
        rows.append({"id": served, "object": "model", "created": now, "owned_by": "qwen"})
    return {"object": "list", "data": rows}


@app.get("/health")
def health():
    vram_alloc = torch.cuda.memory_allocated() / (1024**3) if torch.cuda.is_available() else 0.0
    return {
        "status": "ok" if model is not None else "loading",
        "model_loaded": model is not None,
        "vram_gb": round(vram_alloc, 2),
        "device": str(model.device) if model is not None else "pending",
    }


def _normalize_messages(messages_in: list) -> tuple[list, list]:
    """Convert OpenAI-format messages → processor chat-template format.
    Pulls any data-URL images into PIL so AutoProcessor can embed them."""
    messages = []
    images = []
    for msg in messages_in:
        role = msg.get("role", "user")

        # Tool responses pass through with tool_call_id preserved
        if role == "tool":
            out = {"role": "tool",
                   "content": [{"type": "text", "text": msg.get("content", "") or ""}]}
            if "tool_call_id" in msg:
                out["tool_call_id"] = msg["tool_call_id"]
            if "name" in msg:
                out["name"] = msg["name"]
            messages.append(out)
            continue

        # Assistant messages carrying tool_calls: preserve them unchanged
        if role == "assistant" and "tool_calls" in msg:
            messages.append({
                "role": "assistant",
                "content": [{"type": "text", "text": msg.get("content", "") or ""}],
                "tool_calls": msg["tool_calls"],
            })
            continue

        content = msg.get("content", "")
        if isinstance(content, str):
            messages.append({"role": role, "content": [{"type": "text", "text": content}]})
            continue
        if isinstance(content, list):
            parts = []
            for part in content:
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        b64 = url.split(",", 1)[1]
                        from PIL import Image
                        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
                        # Clamp oversized images. Qwen3VLProcessor emits ~1
                        # token per 28×28 patch, so a 4000×3000 photo alone
                        # spends ~15K tokens — exceeding our 8K static-cache
                        # ceiling forces a realloc + Triton re-autotune on
                        # the new shape. Max side 1280 keeps a full-resolution
                        # image under ~2K tokens and preserves enough detail
                        # for OCR/scene recognition (verified against
                        # real-photo bench). Use LANCZOS — bilinear softens
                        # small text.
                        if max(img.size) > 1280:
                            ratio = 1280 / max(img.size)
                            img = img.resize(
                                (int(img.size[0] * ratio), int(img.size[1] * ratio)),
                                Image.Resampling.LANCZOS,
                            )
                        images.append(img)
                        parts.append({"type": "image", "image": img})
                else:
                    parts.append(part)
            messages.append({"role": role, "content": parts})
            continue
        messages.append(msg)
    return messages, images


def _apply_chat_template(messages, tools, enable_thinking: bool = True,
                          preserve_thinking: bool = False):
    """Processor path (multimodal) with tokenizer fallback (pure-text).

    Qwen3.6 chat template reads `enable_thinking` and `preserve_thinking`
    kwargs. `preserve_thinking=True` keeps historical <think> blocks in
    prior assistant turns — model-card recommends this for agent loops."""
    tmpl_kwargs = dict(enable_thinking=enable_thinking,
                       preserve_thinking=preserve_thinking)
    if processor is not None and hasattr(processor, "apply_chat_template"):
        inputs = processor.apply_chat_template(
            messages,
            tools=tools if tools else None,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            **tmpl_kwargs,
        )
    else:
        # Flatten list-of-parts back into a string for the tokenizer path —
        # only reached when the processor isn't available (text-only fallback).
        flat = []
        for m in messages:
            c = m["content"]
            if isinstance(c, list):
                c = "".join(p.get("text", "") for p in c if p.get("type") == "text")
            flat.append({"role": m["role"], "content": c})
        input_ids = tokenizer.apply_chat_template(
            flat,
            tools=tools if tools else None,
            add_generation_prompt=True,
            tokenize=True,
            return_tensors="pt",
            **tmpl_kwargs,
        )
        inputs = {"input_ids": input_ids, "attention_mask": torch.ones_like(input_ids)}
    return {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}


def _decode(ids):
    if processor is not None and hasattr(processor, "decode"):
        return processor.decode(ids, skip_special_tokens=False)
    return tokenizer.decode(ids, skip_special_tokens=False)


def _split_thinking(text: str) -> tuple[str, str]:
    """Qwen3.5 thinks first then answers. The chat template ends the prompt
    with `<think>\\n`, so the decoded response starts mid-thought (no opening
    `<think>` tag) and contains a closing `</think>` between reasoning and
    answer. Split on the closer: everything before → reasoning, everything
    after → answer. If there's no closer, treat the whole thing as answer."""
    close = "</think>"
    idx = text.find(close)
    if idx >= 0:
        return text[:idx].strip(), text[idx + len(close):].strip()
    return "", text.strip()


#: qwen-code canonical name → tsunami internal name. Applied at the
#: proxy when parsing tool_call emissions so the name downstream
#: callers see is always the tsunami spelling, regardless of which
#: variant the model chose. Paired with the registry alias in
#: tsunami/tools/__init__.py — that one handles older call sites that
#: might still emit qwen names; this one handles new emissions.
_QWEN_CANONICAL_TO_TSUNAMI = {
    "read_file":         "file_read",
    "write_file":        "file_write",
    "edit":              "file_edit",
    "run_shell_command": "shell_exec",
    "web_search":        "search_web",
    # ask_user_question intentionally unmapped — MessageAsk class
    # exists but isn't in the default registry today.
}


def _normalize_tool_name(name: str) -> str:
    return _QWEN_CANONICAL_TO_TSUNAMI.get(name, name)


def _parse_qwen_tool_calls(content: str) -> tuple[list[dict], str]:
    """Extract Qwen3.6 tool-call emissions from assistant content.

    Delegates to StreamingXmlToolCallParser — the per-index depth-tracking,
    unclosed-string-repair, and id-collision-detection port of
    qwen-code's streamingToolCallParser.ts. Running in one-shot mode for
    our non-streaming proxy (one add_chunk call with the full content),
    but the parser's state machine is streaming-ready for when we expose
    an SSE surface.
    """
    import json as _json
    parser = StreamingXmlToolCallParser()
    parser.add_chunk(0, content)
    completed = parser.get_completed_tool_calls()
    tool_calls: list[dict] = []
    for tc in completed:
        if not tc.name:
            continue
        tool_calls.append({
            "id": tc.id or f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": _normalize_tool_name(tc.name),
                "arguments": _json.dumps(tc.args),
            },
        })
    remaining = parser.get_stripped_content(content)
    return tool_calls, remaining


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    _user_sem = _get_user_sem(req.user or "default")
    if req.stream:
        # Streaming doesn't hold _user_sem across the whole generator —
        # once decode starts, the generator will acquire _gpu_sem for
        # actual model work. Fair-queue still enforced at GPU layer.
        return await _chat_completions_stream(req, _user_sem)
    async with _user_sem:
        return await _chat_completions_impl(req)


async def _chat_completions_stream(req: ChatRequest, user_sem: asyncio.Semaphore):
    """SSE streaming response for OpenAI `stream: true` requests.

    Runs lean_decode in the pinned GPU executor; a thread-safe callback
    forwards each token to an asyncio.Queue from which the SSE generator
    formats and yields chunks. Fixes audit D3 — the 'streaming XML tool
    parser' was always wired but nothing ever actually streamed.

    Token-to-text is incremental: each new token appends to a running
    buffer, we decode the whole buffer and emit the length-diff. BPE
    tokenizers occasionally split multi-byte chars across tokens, which
    this approach handles cleanly — the diff includes the combined
    codepoints once the full sequence is valid.

    Tool calls / thinking tags are still assembled server-side at the
    end of the stream and emitted as one final chunk; mid-stream XML
    would break most OpenAI clients.
    """
    import json as _json
    start = time.time()
    _utag = f"[user={req.user or 'default'}] "

    messages, _images = _normalize_messages(req.messages)
    inputs = _apply_chat_template(messages, req.tools, req.enable_thinking,
                                   req.preserve_thinking)
    prompt_len = inputs["input_ids"].shape[1]
    log.info(
        f"{_utag}REQUEST: prompt_tokens={prompt_len} max_new={req.max_tokens} "
        f"thinking={req.enable_thinking} preserve_thinking={req.preserve_thinking} "
        f"n_messages={len(messages)} n_tools={len(req.tools or [])} n_images={len(_images)}"
    )

    eos_ids: list[int] = []
    if tokenizer.eos_token_id is not None:
        eos_ids.append(int(tokenizer.eos_token_id))
    for s in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        t = tokenizer.convert_tokens_to_ids(s)
        if isinstance(t, int) and t >= 0 and t != tokenizer.unk_token_id:
            eos_ids.append(int(t))
    eos_set = set(eos_ids)

    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue(maxsize=2048)
    DONE = object()

    def on_token(tok_id: int) -> None:
        loop.call_soon_threadsafe(q.put_nowait, tok_id)

    def _run_decode():
        try:
            with torch.no_grad():
                lean_decode(
                    model,
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=req.max_tokens,
                    temperature=req.temperature if req.temperature > 0 else 1.0,
                    top_k=int(req.top_k) if req.top_k else 0,
                    top_p=float(req.top_p),
                    min_p=float(req.min_p),
                    repetition_penalty=float(req.repetition_penalty),
                    do_sample=req.temperature > 0,
                    eos_token_ids=eos_ids,
                    use_cuda_graph=_CUDA_GRAPH_ENABLED,
                    max_cache_len=None,
                    on_token=on_token,
                )
        except Exception as _e:
            log.warning(f"{_utag}stream decode error: {type(_e).__name__}: {_e}")
        finally:
            loop.call_soon_threadsafe(q.put_nowait, DONE)

    async def sse() -> "AsyncIterator[bytes]":
        # Hold user_sem for the whole stream — one user = one in-flight
        # streaming call, same fairness property as non-streaming.
        async with user_sem, _gpu_sem:
            fut = loop.run_in_executor(_gpu_executor, _run_decode)
            collected_ids: list[int] = []
            emitted = ""
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:16]}"
            created = int(time.time())

            def _chunk(delta: dict, finish_reason: Optional[str] = None) -> bytes:
                payload = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": delta,
                                 "finish_reason": finish_reason}],
                }
                return f"data: {_json.dumps(payload)}\n\n".encode()

            # Initial role-only delta (OpenAI convention).
            yield _chunk({"role": "assistant", "content": ""})

            ttft_ms: Optional[float] = None  # time-to-first-token

            while True:
                item = await q.get()
                if item is DONE:
                    break
                if ttft_ms is None:
                    ttft_ms = (time.time() - start) * 1000
                collected_ids.append(int(item))
                # Decode the full buffer, emit diff. Slightly wasteful
                # vs per-token decode but avoids mid-codepoint artifacts.
                full = tokenizer.decode(collected_ids, skip_special_tokens=False)
                # Strip EOS/chat markers before emitting (they shouldn't
                # appear mid-stream, but be defensive).
                stable = full
                for stop in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
                    if stop in stable:
                        stable = stable.split(stop, 1)[0]
                delta = stable[len(emitted):]
                if delta:
                    emitted = stable
                    yield _chunk({"content": delta})

            await fut  # ensure decode thread exited cleanly

            # Final chunk: full content + tool_calls extracted from XML.
            thinking, answer = _split_thinking(emitted.strip())
            content = answer if not req.keep_thinking else emitted.strip()
            tool_calls, content = _parse_qwen_tool_calls(content)
            elapsed = time.time() - start
            n_new = len(collected_ids)
            ttft_str = f" ttft={ttft_ms:.0f}ms" if ttft_ms is not None else ""
            log.info(f"{_utag}streamed {n_new} tok in {elapsed:.1f}s "
                     f"({n_new / max(elapsed, 1e-6):.1f} tok/s){ttft_str}"
                     + (f" [{len(tool_calls)} tool_call(s)]" if tool_calls else ""))
            final_delta: dict = {}
            if tool_calls:
                final_delta["tool_calls"] = tool_calls
            if thinking and not req.keep_thinking:
                final_delta["reasoning_content"] = thinking
            if final_delta:
                yield _chunk(final_delta)
            yield _chunk({}, finish_reason="stop")
            yield b"data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")


async def _chat_completions_impl(req: ChatRequest):
    start = time.time()
    _utag = f"[user={req.user or 'default'}] "

    messages, _images = _normalize_messages(req.messages)
    inputs = _apply_chat_template(messages, req.tools, req.enable_thinking,
                                   req.preserve_thinking)
    prompt_len = inputs["input_ids"].shape[1]
    log.info(
        f"{_utag}REQUEST: prompt_tokens={prompt_len} max_new={req.max_tokens} "
        f"thinking={req.enable_thinking} preserve_thinking={req.preserve_thinking} "
        f"n_messages={len(messages)} n_tools={len(req.tools or [])} n_images={len(_images)}"
    )

    # The Qwen3VLProcessor emits `mm_token_type_ids`, `pixel_values`,
    # `image_grid_thw`, etc. alongside the text ids. With the ConditionalGen
    # wrapper those are routed into the vision tower and the mrope position-id
    # builder — keep everything. (An earlier CausalLM-fallback code path did
    # need to strip `mm_token_type_ids` because that class's forward rejected
    # it; we no longer take that path, so the strip is gone.)

    # Force every request to claim at least _CACHE_CEILING tokens of cache —
    # `_prepare_static_cache` reuses the existing StaticCache when its
    # `max_cache_len >= requested`, and allocates a new one (plus a fresh
    # Triton autotune pass over all the new shapes) otherwise. Without this
    # ceiling, a prompt that's larger than the previous high-water mark
    # triggers a full realloc + recompile — we measured a 250× slowdown
    # (30 tok/s → 0.15 tok/s) going from a 230-token prompt to 1461 tokens
    # after the static cache was sized for the former. 8192 covers typical
    # document-grade prompts at ~2.5 GB KV-cache VRAM cost.
    _force_max_length = max(prompt_len + req.max_tokens, _CACHE_CEILING)

    # Multimodal requests carry pixel_values + mm_token_type_ids +
    # image_grid_thw alongside input_ids. lean_decode's fast path only
    # forwards input_ids/attention_mask, so vision requests silently
    # lose the images and the VLM hallucinates text from the base64.
    # Detect image inputs and fall back to HF GenerationMixin (slower
    # but multimodal-aware) for those requests only.
    _has_vision_inputs = "pixel_values" in inputs

    def _generate():
        # Lean decode path (env-gated). Skips HF GenerationMixin — which the
        # profiler showed was adding ~57ms/tok of Python overhead (LogitsProcessor
        # chain, StoppingCriteria poll, kwarg rebuild). Forward pass + custom
        # sampling only. Keeps the same StaticCache path by letting the model
        # allocate its own cache internally.
        if _LEAN_DECODE_ENABLED and not _has_vision_inputs:
            eos_ids: list[int] = []
            if tokenizer.eos_token_id is not None:
                eos_ids.append(int(tokenizer.eos_token_id))
            for s in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
                t = tokenizer.convert_tokens_to_ids(s)
                if isinstance(t, int) and t >= 0 and t != tokenizer.unk_token_id:
                    eos_ids.append(int(t))
            with torch.no_grad():
                return lean_decode(
                    model,
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs.get("attention_mask"),
                    max_new_tokens=req.max_tokens,
                    temperature=req.temperature if req.temperature > 0 else 1.0,
                    top_k=int(req.top_k) if req.top_k else 0,
                    top_p=float(req.top_p),
                    min_p=float(req.min_p),
                    repetition_penalty=float(req.repetition_penalty),
                    do_sample=req.temperature > 0,
                    eos_token_ids=eos_ids,
                    use_cuda_graph=_CUDA_GRAPH_ENABLED,
                    # Bucket the cache length to nearest power-of-2 >= needed,
                    # min 256. Each bucket has its own captured graph in
                    # _warm_graph_cache. Per-step KV bandwidth scales with
                    # cache_len, so we don't want to pin to a huge ceiling;
                    # per-bucket captures pay a ~150ms one-time cost.
                    # Measured 2026-04-18: pinning to _CACHE_CEILING tanked
                    # decode to 1.5 tok/s (170GB/step KV reads); pinning to
                    # 8192 dropped to 22 tok/s (5.4GB/step); bucketing keeps
                    # decode at ~35 tok/s regardless of request size.
                    max_cache_len=None,
                )
        # Sampling knobs mirror the Qwen3.6 model-card recommendations:
        # top_k=20 / top_p=0.8 / min_p=0.0 / presence_penalty=1.5 /
        # repetition_penalty=1.0 for instruct-general, thinking-mode variants
        # push top_p=0.95 + presence_penalty=0 on coding. Callers override
        # via ChatRequest; defaults here match "Instruct mode, general tasks".
        gen_kwargs = dict(
            max_new_tokens=req.max_tokens,
            max_length=_force_max_length,
            use_cache=True,
            # Static cache + CUDA graphs path: needs the four hybrid-attention
            # patches above (LinearAttentionLayer.max_batch_size, StaticLayer
            # .max_batch_size, linear_attention mask entry, + proper 2D-bool
            # return from the mask fn). Unlocks kernel fusion at bs=1.
            cache_implementation="static",
            temperature=req.temperature if req.temperature > 0 else 1.0,
            top_p=req.top_p,
            top_k=req.top_k,
            do_sample=req.temperature > 0,
        )
        # min_p / presence_penalty / repetition_penalty only land on generate()
        # when they differ from neutral — some HF versions reject 0.0 for
        # presence_penalty (interprets as "not set") and others warn on
        # min_p=0. Keep the call clean by only forwarding non-default values.
        if req.min_p > 0.0:
            gen_kwargs["min_p"] = req.min_p
        if req.presence_penalty != 0.0:
            # HF's penalty_kwargs use `repetition_penalty` + a separate
            # `encoder_repetition_penalty`; presence_penalty is delivered via
            # `encoder_no_repeat_ngram_size`-style hooks in newer versions.
            # Qwen's README syntax matches OpenAI's, which HF renders as
            # `penalty_alpha`. Pass through; if HF rejects it, catch and fall
            # back to repetition_penalty.
            gen_kwargs["repetition_penalty"] = max(
                req.repetition_penalty,
                1.0 + req.presence_penalty * 0.01,
            )
        elif req.repetition_penalty != 1.0:
            gen_kwargs["repetition_penalty"] = req.repetition_penalty
        with torch.no_grad():
            return model.generate(**inputs, **gen_kwargs)

    _t_pregpu = time.time()
    async with _gpu_sem:
        # Route through the pinned single-thread GPU executor (see
        # `_run_on_gpu_thread` — keeps inductor cudagraph_trees TLS stable
        # across requests and allows a safe boot warmup).
        output = await _run_on_gpu_thread(_generate)
    _t_gpu_done = time.time()

    new_tokens = output[0][prompt_len:]
    text = _decode(new_tokens)
    _t_decode_done = time.time()
    log.info(f"{_utag}RAW OUTPUT: {text[:200]!r}{'…' if len(text) > 200 else ''}")

    # Strip any trailing EOS / chat-turn markers commonly left by the model.
    for stop in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        if stop in text:
            text = text.split(stop, 1)[0]
    text = text.strip()

    thinking, answer = _split_thinking(text)
    content = answer if not req.keep_thinking else text
    _t_split_done = time.time()

    # Parse Qwen3.6 tool-call emission format out of content, lift into
    # OpenAI-shape message.tool_calls[]. Without this, the agent sees raw
    # <tool_call>...</tool_call> XML in content and records it as a
    # message_chat — breaking every build that relied on tool routing.
    tool_calls, content = _parse_qwen_tool_calls(content)
    _t_parse_done = time.time()

    elapsed = time.time() - start
    completion_tokens = len(new_tokens)
    # Phase-level timing breakdown to spot post-processing bottlenecks.
    # Emitted as a compact summary so the logs are greppable.
    _pre_gpu_ms = (_t_pregpu - start) * 1000
    _gpu_ms = (_t_gpu_done - _t_pregpu) * 1000
    _tok_dec_ms = (_t_decode_done - _t_gpu_done) * 1000
    _split_ms = (_t_split_done - _t_decode_done) * 1000
    _parse_ms = (_t_parse_done - _t_split_done) * 1000
    log.info(f"{_utag}generated {completion_tokens} tok in {elapsed:.1f}s "
             f"({completion_tokens / max(elapsed, 1e-6):.1f} tok/s) "
             f"phases[pre={_pre_gpu_ms:.0f} gpu={_gpu_ms:.0f} "
             f"dec={_tok_dec_ms:.0f} split={_split_ms:.0f} parse={_parse_ms:.0f}]"
             + (f" [{len(tool_calls)} tool_call(s)]" if tool_calls else ""))

    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    if thinking and req.keep_thinking is False:
        # Expose thinking trace as a non-OpenAI extension field — clients that
        # ignore unknown fields get the normal answer; debuggers can see it.
        message["reasoning_content"] = thinking

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_len,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_len + completion_tokens,
        },
    }


import re as _re
from pathlib import Path as _Path


_EXPERT_RE = _re.compile(
    r"^(model\.language_model\.layers\.(\d+)\.mlp\.experts)\.(\d+)\."
    r"(gate_proj|up_proj|down_proj)\.(weight|weight_scale_inv)$"
)


def _resolve_snapshot_dir(model_id: str) -> _Path:
    """Map an HF repo id or local path to the actual snapshot directory. We
    need concrete files so we can read safetensors shards manually and fuse
    the per-expert weights in memory before handing off to from_pretrained.
    Running download_first_if_missing via snapshot_download is idempotent —
    it's a no-op when the files are already cached."""
    p = _Path(model_id).expanduser()
    if p.is_dir():
        return p
    from huggingface_hub import snapshot_download
    return _Path(snapshot_download(model_id))


def _fuse_cache_path(snapshot: _Path, cache_root: _Path) -> _Path:
    """Cache key uses the HF snapshot commit sha (the snapshot dir name), so
    a new model revision auto-invalidates the cache. One file per model.
    Parent dirs are created on demand; the caller handles staleness."""
    sha = snapshot.name  # HF snapshots/<commit_sha>/ — 40-char hex
    # Walk up to the repo name (models--Qwen--Qwen3.6-…) for a readable key.
    repo_key = snapshot.parent.parent.name.replace("models--", "").replace("--", "_")
    return cache_root / repo_key / f"{sha}.safetensors"


class _LazyFusedStateDict:
    """Dict-like view over a fused safetensors file that only materializes a
    tensor when transformers' loader actually asks for it. Eliminates the
    ~35 GB transient spike that happens when `_load_fused_from_cache` builds
    the whole sd up front just to hand it to `from_pretrained(state_dict=…)`
    which then iterates-and-assigns key-by-key.

    Contract we need to satisfy (discovered empirically against transformers v5):
      • iter / keys / len / __contains__ — used during the initial scan
      • __getitem__ / get / pop — used during the assign loop
      • items — used when transformers wants to round-trip the dict

    Every materialization goes straight to GPU (device="cuda:0") so the tensor
    lands in one place and the caller's assign path is a pointer swap, not a
    copy. Peak memory becomes O(single-tensor) instead of O(full-model)."""

    def __init__(self, cache_file: _Path, device: str):
        from safetensors import safe_open
        self._cache_file = cache_file
        self._device = device
        self._handle_ctx = safe_open(str(cache_file), framework="pt", device=device)
        self._handle = self._handle_ctx.__enter__()
        self._keys = list(self._handle.keys())
        self._keyset = set(self._keys)

    # --- identity / debugging ---
    def __repr__(self) -> str:
        return f"_LazyFusedStateDict(file={self._cache_file.name}, n={len(self._keys)})"

    # --- container protocol ---
    def __len__(self) -> int:
        return len(self._keys)

    def __iter__(self):
        return iter(self._keys)

    def __contains__(self, k) -> bool:
        return k in self._keyset

    def keys(self):
        return list(self._keys)

    def values(self):
        return (self._handle.get_tensor(k) for k in self._keys)

    def items(self):
        return ((k, self._handle.get_tensor(k)) for k in self._keys)

    # --- mapping access ---
    def __getitem__(self, k):
        if k not in self._keyset:
            raise KeyError(k)
        return self._handle.get_tensor(k)

    def get(self, k, default=None):
        if k not in self._keyset:
            return default
        return self._handle.get_tensor(k)

    def pop(self, k, *default):
        if k in self._keyset:
            t = self._handle.get_tensor(k)
            self._keys.remove(k)
            self._keyset.discard(k)
            return t
        if default:
            return default[0]
        raise KeyError(k)

    # --- safety nets for corners of the loader we haven't seen yet ---
    def copy(self):
        # Most callers want a shallow dict copy — materialize every tensor
        # eagerly, which negates the whole point. Log the event and do it.
        log.warning("_LazyFusedStateDict.copy() called — materializing all tensors")
        return {k: self._handle.get_tensor(k) for k in self._keys}

    def update(self, other):
        raise NotImplementedError("_LazyFusedStateDict is read-only")

    def close(self):
        try:
            self._handle_ctx.__exit__(None, None, None)
        except Exception:
            pass


def _load_fused_from_cache(cache_file: _Path, device: str):
    """Return a lazy view over the fused safetensors cache. Reading is deferred
    until transformers' from_pretrained actually asks for each tensor, at which
    point it lands straight on `device` via safetensors' GPU-native open. This
    replaces an earlier eager path that built a full ~35 GB dict up front and
    caused transient double-memory during the assign loop. See
    `_LazyFusedStateDict` docstring for the loader-contract surface."""
    t0 = time.time()
    view = _LazyFusedStateDict(cache_file, device=device)
    log.info(f"fuser: opened cached fused state_dict view over {cache_file.name} "
             f"in {time.time() - t0:.2f}s ({len(view)} tensors, lazy)")
    return view


def _save_fused_to_cache(state_dict: dict, cache_file: _Path) -> None:
    """Persist the fused state_dict as a single safetensors file. Tensors
    are moved to CPU before save — safetensors needs contiguous host buffers.
    This is a one-time cost; subsequent loads are direct GPU reads."""
    from safetensors.torch import save_file
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    cpu_sd = {k: v.detach().cpu().contiguous() for k, v in state_dict.items()}
    save_file(cpu_sd, str(cache_file))
    del cpu_sd
    log.info(f"fuser: wrote cache {cache_file} in {time.time() - t0:.1f}s")


def _build_fused_state_dict(snapshot: _Path, device: str = "cuda:0") -> dict:
    """Read the HF checkpoint and fuse per-expert `gate_proj`/`up_proj` plus
    stack-across-experts for `down_proj` into the packed shapes the v5
    qwen3_5_moe modeling code expects — STREAMING DIRECTLY TO GPU so we never
    build the 35 GB state_dict on CPU. On unified-memory boxes like GB10 the
    CPU staging doubles the memory footprint; on discrete GPUs it's still a
    big transient spike during load.

    Packed layout per layer:
      experts.gate_up_proj              (E, 2*I, H)  fp8_e4m3
      experts.gate_up_proj_scale_inv    (E, 2*I/128, H/128)  fp32
      experts.down_proj                 (E, H, I)    fp8_e4m3
      experts.down_proj_scale_inv       (E, H/128, I/128)  fp32
    """
    import json as _json
    import gc as _gc
    from collections import defaultdict as _dd
    from safetensors import safe_open

    idx = _json.loads((snapshot / "model.safetensors.index.json").read_text())
    weight_map = idx["weight_map"]

    # Invert: which shard each expert tensor lives in, keyed by (layer, expert,
    # proj, suffix). Non-expert tensors go into a separate plain list.
    expert_locator: dict[tuple[str, int, int, str, str], tuple[str, str]] = {}
    non_expert: list[tuple[str, str]] = []  # (tensor_name, shard_fname)
    for name, fname in weight_map.items():
        m = _EXPERT_RE.match(name)
        if m:
            expert_locator[(m.group(1), int(m.group(2)), int(m.group(3)),
                            m.group(4), m.group(5))] = (name, fname)
        else:
            non_expert.append((name, fname))

    # Open each shard once with safe_open — memory-mapped, near-zero overhead.
    open_shards: dict[str, "safe_open"] = {}
    def _open(fname):
        sh = open_shards.get(fname)
        if sh is None:
            # device="cuda" loads the tensor payload straight to GPU memory —
            # no CPU intermediate, no double copy.
            sh = safe_open(str(snapshot / fname), framework="pt", device=device).__enter__()
            open_shards[fname] = sh
        return sh

    state_dict: dict[str, "torch.Tensor"] = {}
    t0 = time.time()

    # 1) Non-expert tensors stream direct-to-GPU, one-by-one.
    for name, fname in non_expert:
        state_dict[name] = _open(fname).get_tensor(name)

    # 2) For each (prefix, layer), load + fuse + stack on GPU, write 4 packed
    # tensors into state_dict. The per-expert tensors drop out of scope each
    # iteration so at most one layer's working set is alive at a time.
    by_layer: dict[tuple[str, int], list[int]] = _dd(list)
    for (prefix, layer, e, _proj, _suf) in expert_locator:
        if e not in by_layer[(prefix, layer)]:
            by_layer[(prefix, layer)].append(e)

    for (prefix, layer), experts in by_layer.items():
        num_experts = max(experts) + 1
        gate_up_w, gate_up_s, down_w, down_s = [], [], [], []
        for e in range(num_experts):
            gw_n, gw_sh = expert_locator[(prefix, layer, e, "gate_proj", "weight")]
            uw_n, uw_sh = expert_locator[(prefix, layer, e, "up_proj", "weight")]
            gs_n, gs_sh = expert_locator[(prefix, layer, e, "gate_proj", "weight_scale_inv")]
            us_n, us_sh = expert_locator[(prefix, layer, e, "up_proj", "weight_scale_inv")]
            dw_n, dw_sh = expert_locator[(prefix, layer, e, "down_proj", "weight")]
            ds_n, ds_sh = expert_locator[(prefix, layer, e, "down_proj", "weight_scale_inv")]
            # gate is rows [0:I], up is rows [I:2I] — see modeling_qwen3_5_moe
            gate_up_w.append(torch.cat([_open(gw_sh).get_tensor(gw_n),
                                        _open(uw_sh).get_tensor(uw_n)], dim=0))
            gate_up_s.append(torch.cat([_open(gs_sh).get_tensor(gs_n),
                                        _open(us_sh).get_tensor(us_n)], dim=0))
            down_w.append(_open(dw_sh).get_tensor(dw_n))
            down_s.append(_open(ds_sh).get_tensor(ds_n))
        state_dict[f"{prefix}.gate_up_proj"] = torch.stack(gate_up_w).contiguous()
        state_dict[f"{prefix}.gate_up_proj_scale_inv"] = torch.stack(gate_up_s).contiguous()
        state_dict[f"{prefix}.down_proj"] = torch.stack(down_w).contiguous()
        state_dict[f"{prefix}.down_proj_scale_inv"] = torch.stack(down_s).contiguous()
        # Per-layer release — dropping gate_up_w etc. returns GPU memory for
        # the transient concat/stack workspace before the next layer claims.
        del gate_up_w, gate_up_s, down_w, down_s
        _gc.collect()

    for sh in open_shards.values():
        try: sh.__exit__(None, None, None)
        except Exception: pass
    log.info(f"fuser: built GPU state_dict in {time.time() - t0:.1f}s — "
             f"{len(state_dict)} tensors direct-on-{device}")
    return state_dict


def _load_model(model_id: str, max_memory_gb: float | None):
    """Load Qwen3.5-MoE FP8 through transformers. The on-disk HF checkpoint
    ships per-expert `gate_proj`/`up_proj`/`down_proj`; transformers v5 wants
    those packed + stacked. We build the packed state_dict in memory and hand
    it to from_pretrained(state_dict=…) so nothing is duplicated on disk."""
    global model, processor, tokenizer
    from transformers import AutoProcessor, AutoTokenizer, AutoConfig

    log.info(f"Loading {model_id} on cuda:0 (Blackwell GB10, FP8 native) …")
    t0 = time.time()

    cfg = AutoConfig.from_pretrained(model_id, trust_remote_code=True)
    arch = (cfg.architectures or ["?"])[0]
    log.info(f"Architecture: {arch}")

    # Qwen3.5-Moe text_config is missing `intermediate_size` — transformers'
    # ImageTextToText wrapper init reads that attribute and crashes. The MoE
    # routed FFN uses `moe_intermediate_size`; the shared expert uses
    # `shared_expert_intermediate_size`. They're equal (512) for Qwen3.6-35B-A3B,
    # so either works as the fallback value. Patch before load.
    if hasattr(cfg, "text_config") and not hasattr(cfg.text_config, "intermediate_size"):
        alias = getattr(cfg.text_config, "moe_intermediate_size", None) \
                or getattr(cfg.text_config, "shared_expert_intermediate_size", None)
        if alias is not None:
            cfg.text_config.intermediate_size = alias
            log.info(f"Patched text_config.intermediate_size = {alias}")

    # The quantization_config on disk already describes fine-grained FP8 with
    # block size 128 — transformers picks it up automatically. Do NOT pass
    # quantization_config=… here or we override the per-block scales.
    load_kwargs = dict(
        dtype="auto",
        device_map="cuda:0",
        trust_remote_code=True,
        config=cfg,
    )
    if max_memory_gb is not None:
        load_kwargs["max_memory"] = {0: f"{max_memory_gb}GiB", "cpu": "200GiB"}

    # MoE checkpoints on HF ship per-expert unpacked (gate_proj/up_proj/
    # down_proj are separate tensors per expert). transformers v5's
    # qwen3_5_moe modeling code instead expects them fused + stacked across
    # experts. Build the packed state_dict in memory and load via the
    # name=None path that accepts a caller-supplied state_dict.
    is_moe = getattr(cfg.text_config, "num_experts", 0) and \
             "moe" in (getattr(cfg.text_config, "model_type", "") or "").lower()

    # Prefer the multimodal wrapper — it builds the 3D mrope position_ids the
    # text backbone expects; the plain CausalLM load feeds scalar position_ids
    # into mrope and produces token-salad.
    last_err = None
    candidates = []
    if arch and hasattr(__import__("transformers"), arch):
        candidates.append(arch)  # e.g. Qwen3_5MoeForConditionalGeneration
    candidates += ["AutoModelForImageTextToText", "AutoModelForCausalLM"]

    for loader_name in candidates:
        try:
            import transformers
            loader = getattr(transformers, loader_name)
            log.info(f"Trying {loader_name}.from_pretrained …")
            if is_moe:
                # transformers v5 refuses state_dict + a path in the same call,
                # so we pass path=None — the config carries the quantization
                # spec, and our pre-fused state_dict lands straight into the
                # FP8Linear shells the quantizer sets up.
                snapshot = _resolve_snapshot_dir(model_id)
                # Use a per-model cache keyed by the snapshot's commit sha so
                # a new revision auto-invalidates. Cache hit = near-instant
                # GPU load; miss = ~4 min GPU-streamed fuse, then persist.
                cache_root = _Path.home() / ".cache" / "sigma_fuse"
                cache_file = _fuse_cache_path(snapshot, cache_root)
                if cache_file.exists():
                    log.info(f"MoE detected — loading fused state_dict from cache {cache_file}")
                    sd = _load_fused_from_cache(cache_file, device="cuda:0")
                else:
                    log.info(f"MoE detected — fusing experts from {snapshot} (cache miss)")
                    sd = _build_fused_state_dict(snapshot)
                    try:
                        _save_fused_to_cache(sd, cache_file)
                    except Exception as _e:
                        log.warning(f"fuse cache save failed ({_e}) — continuing without cache")
                # low_cpu_mem_usage=True routes through _load_state_dict_into_meta_model,
                # which *assigns* tensors (param.data = sd[k]) instead of copying
                # (param.data.copy_(sd[k])). Without this, from_pretrained duplicates
                # every weight on GPU during load — our 35 GB fused sd → ~70 GB peak
                # VRAM for the 5-10s copy window. On unified-memory GB10 that spike
                # lands in the shared pool and nvidia-smi briefly reports ~65 GB.
                # With assign, from_pretrained reuses the exact GPU tensors we fused
                # and peak stays ≈ 35 GB.
                model = loader.from_pretrained(
                    None,
                    config=cfg,
                    state_dict=sd,
                    dtype="auto",
                    device_map="cuda:0",
                    trust_remote_code=True,
                    low_cpu_mem_usage=True,
                )
                sd = None  # pointer only — tensors now owned by the model
            else:
                model = loader.from_pretrained(model_id, **load_kwargs)
            log.info(f"Loaded via {loader_name}")
            break
        except Exception as e:
            last_err = e
            log.warning(f"{loader_name} failed: {type(e).__name__}: {e}")
            model = None
    if model is None:
        raise RuntimeError(f"All loaders failed. Last error: {last_err}")

    # Processor = tokenizer + image_processor combo. Some multimodal models
    # expose both; pure-text builds expose only AutoTokenizer. Try processor
    # first (it handles image_url parts in messages), tokenizer as fallback.
    try:
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        log.info(f"Processor loaded: {type(processor).__name__}")
    except Exception as e:
        log.warning(f"AutoProcessor unavailable ({e}) — falling back to tokenizer only")
        processor = None
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    log.info(f"Tokenizer loaded: {type(tokenizer).__name__}")

    # Drop the transient CPU-side fusion buffer now that weights live on the
    # GPU. gc.collect() is needed because from_pretrained's internal load path
    # stores lingering refs to the source tensors until its locals unwind;
    # without an explicit collect, those refs keep the unified-memory
    # footprint at ~2× (one copy GPU-resident, one CPU-resident).
    import gc as _gc
    _gc.collect()
    torch.cuda.synchronize()
    torch.cuda.empty_cache()

    # torch.compile is a dead-end on this torch nightly for Qwen3.5-MoE FP8:
    # Dynamo cannot trace the Blackwell FP sub-byte dtypes (float4_e2m1fn,
    # float6_e2m3fn, float8_e5m2fnuz, …) that the FP8 kernels emit, so the
    # whole forward degrades to graph-break on every matmul — and even when
    # tolerating breaks, the scheduler build hits `KeyError: 'op6'` around the
    # hybrid linear/full attention path. Leave the forward eager; we pick up
    # the 1.5-2× elsewhere (static-cache path is already a +57% win).
    # Python's obmalloc and glibc retain freed heap for reuse, so the ~35 GB
    # fusion buffer sticks in RSS even after gc.collect(). On unified-memory
    # boxes like GB10 that directly inflates the shared pool → nvidia-smi
    # reports ~65 GB when the model is actually 35. malloc_trim(0) asks glibc
    # to hand pages back to the kernel; it's a ~no-op for well-behaved allocs
    # but reclaims large fragmented regions.
    try:
        import ctypes as _ct
        _ct.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
    vram = torch.cuda.memory_allocated() / (1024**3)
    try:
        import resource as _r
        cpu_rss = _r.getrusage(_r.RUSAGE_SELF).ru_maxrss / (1024**2)  # KB→GB
    except Exception:
        cpu_rss = -1.0
    log.info(f"Model resident in {time.time()-t0:.1f}s, VRAM {vram:.2f} GB "
             f"/ CPU RSS peak {cpu_rss:.2f} GB on {model.device}")

    # NOT calling set_experts_implementation('batched_mm') — HF's generate()
    # context manager does that automatically for its path, and their docs
    # say it's "much more performant" on smaller inputs. Measured on our
    # stack 2026-04-18: 38 → 34.7 tok/s regression. The FP8 code path in
    # Qwen3.6-MoE dispatches to different kernels per implementation, and
    # the 'grouped' path (default) hits a faster Triton kernel than
    # 'batched' on sm_121. Leaving default behavior in place.

    # Stash cfg + snapshot so the lazy MTP loader can find them later.
    # MTP head loads ~1-2GB extra VRAM on top of the main model; deferred to
    # first /debug/mtp_decode call (or main-path enable via env flag) so boot
    # stays fast for users who don't want speculative decoding.
    global _model_cfg, _model_snapshot
    _model_cfg = cfg
    try:
        _model_snapshot = _resolve_snapshot_dir(model_id)
    except Exception as _e:
        log.info(f"snapshot dir unresolved ({_e}) — MTP will be unavailable")

    # Boot warmup attempted in iteration 10 — running generate() in the main
    # thread before uvicorn so Triton autotune costs don't land on the first
    # user. Broke because `cache_implementation="static"` routes through
    # inductor's cudagraph_trees, whose tree-manager lives in threading.local();
    # the asyncio.to_thread worker that serves requests has no tree-manager
    # key set, so it hits `AssertionError` in `get_container`. Setting
    # `torch._inductor.config.triton.cudagraphs = False` did not short-circuit
    # the path (HF's compile hook re-enables it). Warmup left out of this
    # build — first request pays ~35s of Triton autotune per unique shape.
    # Candidate fix for a future session: run the actual request handler in
    # the main thread (drop asyncio.to_thread), or set up the tree-manager
    # key on the asyncio worker before the first generate call.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3.6-27B",
                        help="HF repo id or local path. Default is dense BF16 27B; "
                             "Qwen/Qwen3.6-35B-A3B-FP8 still works for the legacy "
                             "MoE FP8 path (auto-detected from the config).")
    parser.add_argument("--port", type=int, default=8095)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--max-memory-gb", type=float, default=None,
                        help="Cap GPU memory allowance (GiB). Leave unset to let "
                             "accelerate auto-split; set when co-tenanting other jobs.")
    args = parser.parse_args()

    import os
    if torch.cuda.is_available():
        # expandable_segments: FP8 quant builds allocate many irregular blocks
        # during the first forward pass. Without this, the default caching
        # allocator fragments and refuses a large later alloc even though the
        # reserved pool has room.
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        try:
            torch.cuda.set_per_process_memory_fraction(0.95)
        except Exception:
            pass

    _load_model(args.model, args.max_memory_gb)

    log.info(f"Starting server on {args.host}:{args.port} …")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
