#!/usr/bin/env python3
"""Serve Qwen3.5-27B-FP8 via transformers — text + vision.

Qwen3.5 is a hybrid-attention (linear + full) MoE with native FP8 weights
(fine-grained block-128 quant). Runs on Blackwell GB10 through the
nvcr.io/nvidia/pytorch:26.03-py3 container (torch 2.11 / CUDA 13.2).

Usage:
  python3 serve_qwen35_fp8.py --model Qwen/Qwen3.5-27B-FP8 --port 8095

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
import time
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
import transformers.models.qwen3_5_moe.modeling_qwen3_5_moe as _q35moe_mod
_q35moe_mod.create_causal_mask = _unwrap_dict_mask

# Sibling to the dict-unwrap above: _update_linear_attn_mask receives the same
# {layer_pattern: mask} dict under static cache, and its `torch.all(mask == 1)`
# check blows up on a dict (`dict == 1` → Python bool, `torch.all(bool)` → TypeError).
# Pull the linear_attention entry out before delegating.
_orig_ulam = _q35moe_mod.Qwen3_5MoeTextModel._update_linear_attn_mask
def _ulam_dict_aware(self, attention_mask, past_key_values):
    if isinstance(attention_mask, dict):
        return attention_mask.get("linear_attention")
    return _orig_ulam(self, attention_mask, past_key_values)
_q35moe_mod.Qwen3_5MoeTextModel._update_linear_attn_mask = _ulam_dict_aware

# Also override the Triton fallback with DeepSeek's reference Triton FP8 GEMM.
# The kernels-community/finegrained-fp8 kernel is generic and slow; DeepSeek's
# was hand-tuned for exactly this quant recipe (block-128, e4m3) and tends to
# win 1.5-3x on MoE shapes where the community build's autotune space is tuned
# for larger tiles. Routed through the same `w8a8_fp8_matmul` entry point so
# transformers' per-module FP8Linear dispatch still works.
import sys as _vsys
_vsys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")
from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm

def _ds_w8a8_fp8_matmul(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    """Shim: DeepSeek's fp8_gemm(a, a_s, b, b_s) expects:
      a:  (M, K)  fp8_e4m3fn — row-major
      a_s:(M, K/BLK) fp32    — per-row per-K-block scales
      b:  (N, K)  fp8_e4m3fn — row-major (weight stored out-major)
      b_s:(N/BLK, K/BLK) fp32 — block-wise weight scales
    transformers' caller contract is identical; we just pass through.
    output comes back in torch.get_default_dtype(), so we temporarily flip it."""
    # 3D activations → 2D matmul → restore shape after.
    orig_shape = A.shape
    A_2d = A.reshape(-1, orig_shape[-1]).contiguous()
    As_2d = As.reshape(-1, As.shape[-1]).contiguous() if As.dim() >= 2 else As.contiguous()
    prev_dtype = torch.get_default_dtype()
    if output_dtype is not None and output_dtype != prev_dtype:
        torch.set_default_dtype(output_dtype)
    try:
        out = _ds_fp8_gemm(A_2d, As_2d, B.contiguous(), Bs.contiguous())
    finally:
        if output_dtype is not None and output_dtype != prev_dtype:
            torch.set_default_dtype(prev_dtype)
    return out.view(*orig_shape[:-1], B.shape[0])

# Swap the whole entry point — finegrained_fp8.FP8Linear.forward calls this
# by name, so a module-level reassignment catches every dispatch.
_fgfp8.w8a8_fp8_matmul = _ds_w8a8_fp8_matmul

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal, Union
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("qwen35_fp8")

app = FastAPI()
model = None
processor = None
tokenizer = None  # fallback when processor isn't available


# tool_choice payload shape — same shape as serve_transformers.py.
class _ToolChoiceFunction(BaseModel):
    name: str


class ForceToolChoice(BaseModel):
    type: Literal["function"] = "function"
    function: _ToolChoiceFunction


ToolChoice = Union[Literal["auto", "none", "required"], ForceToolChoice]


class ChatRequest(BaseModel):
    model: str = "qwen3.5-27b-fp8"
    messages: list
    tools: list = []
    tool_choice: ToolChoice = "auto"
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 64
    user: str = ""
    # Qwen3.5 generates <think>…</think> before answering. Default strip so the
    # OpenAI-shape content field only carries the user-facing answer. Set to
    # true to return the raw thinking trace alongside the answer.
    keep_thinking: bool = False
    # Qwen3.5 chat template accepts `enable_thinking`. When False the template
    # emits an empty `<think>\n\n</think>` preamble, steering the model to
    # skip the reasoning phase entirely — 2-3× fewer tokens for simple Qs.
    enable_thinking: bool = True


# Fairness layer — pulled from serve_transformers.py. One in-flight request
# per user via _user_sems; one GPU occupant at a time via _gpu_sem. Together
# this keeps /health responsive and prevents concurrent-forward-pass CUDA
# contention from starving throughput.
_user_sems: dict[str, asyncio.Semaphore] = {}
_gpu_sem = asyncio.Semaphore(1)


def _get_user_sem(user: str) -> asyncio.Semaphore:
    sem = _user_sems.get(user)
    if sem is None:
        sem = asyncio.Semaphore(1)
        _user_sems[user] = sem
    return sem


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
                        images.append(img)
                        parts.append({"type": "image", "image": img})
                else:
                    parts.append(part)
            messages.append({"role": role, "content": parts})
            continue
        messages.append(msg)
    return messages, images


def _apply_chat_template(messages, tools, enable_thinking: bool = True):
    """Processor path (multimodal) with tokenizer fallback (pure-text)."""
    if processor is not None and hasattr(processor, "apply_chat_template"):
        inputs = processor.apply_chat_template(
            messages,
            tools=tools if tools else None,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=enable_thinking,
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
            enable_thinking=enable_thinking,
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


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    _user_sem = _get_user_sem(req.user or "default")
    async with _user_sem:
        return await _chat_completions_impl(req)


async def _chat_completions_impl(req: ChatRequest):
    start = time.time()
    _utag = f"[user={req.user or 'default'}] "

    messages, _images = _normalize_messages(req.messages)
    inputs = _apply_chat_template(messages, req.tools, req.enable_thinking)
    prompt_len = inputs["input_ids"].shape[1]

    # The Qwen3VLProcessor emits `mm_token_type_ids`, `pixel_values`,
    # `image_grid_thw`, etc. alongside the text ids. With the ConditionalGen
    # wrapper those are routed into the vision tower and the mrope position-id
    # builder — keep everything. (An earlier CausalLM-fallback code path did
    # need to strip `mm_token_type_ids` because that class's forward rejected
    # it; we no longer take that path, so the strip is gone.)

    def _generate():
        with torch.no_grad():
            return model.generate(
                **inputs,
                max_new_tokens=req.max_tokens,
                use_cache=True,
                # Static cache + CUDA graphs path: needs the four hybrid-
                # attention patches above (LinearAttentionLayer.max_batch_size,
                # StaticLayer.max_batch_size, linear_attention mask entry, +
                # proper 2D-bool return from the mask fn). With those, this
                # unlocks torch.compile(reduce-overhead) style kernel fusion
                # and eliminates launch overhead at bs=1.
                cache_implementation="static",
                temperature=req.temperature if req.temperature > 0 else 1.0,
                top_p=req.top_p,
                top_k=req.top_k,
                do_sample=req.temperature > 0,
            )

    async with _gpu_sem:
        output = await asyncio.to_thread(_generate)

    new_tokens = output[0][prompt_len:]
    text = _decode(new_tokens)
    log.info(f"{_utag}RAW OUTPUT: {text[:200]!r}{'…' if len(text) > 200 else ''}")

    # Strip any trailing EOS / chat-turn markers commonly left by the model.
    for stop in ("<|im_end|>", "<|endoftext|>", "<|end|>"):
        if stop in text:
            text = text.split(stop, 1)[0]
    text = text.strip()

    thinking, answer = _split_thinking(text)
    content = answer if not req.keep_thinking else text

    elapsed = time.time() - start
    completion_tokens = len(new_tokens)
    log.info(f"{_utag}generated {completion_tokens} tok in {elapsed:.1f}s "
             f"({completion_tokens / max(elapsed, 1e-6):.1f} tok/s)")

    message = {"role": "assistant", "content": content}
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
            "finish_reason": "stop",
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


def _load_fused_from_cache(cache_file: _Path, device: str) -> dict:
    """Re-hydrate a fused state_dict straight to GPU from a safetensors cache
    file produced by a prior fuse pass. Near-instant vs re-running the full
    concat/stack over 256 experts × 40 layers."""
    from safetensors import safe_open
    t0 = time.time()
    sd: dict[str, "torch.Tensor"] = {}
    with safe_open(str(cache_file), framework="pt", device=device) as f:
        for name in f.keys():
            sd[name] = f.get_tensor(name)
    log.info(f"fuser: loaded cached fused state_dict from {cache_file.name} "
             f"in {time.time() - t0:.1f}s ({len(sd)} tensors)")
    return sd


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
                model = loader.from_pretrained(
                    None,
                    config=cfg,
                    state_dict=sd,
                    dtype="auto",
                    device_map="cuda:0",
                    trust_remote_code=True,
                )
                sd = None  # drop the CPU copy now the weights live on GPU
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

    # torch.compile(reduce-overhead) crashes the inductor on torch 2.13-nightly
    # with a `KeyError: 'op6'` during scheduler build — a known upstream regression
    # we hit around the hybrid linear-attention path. Leave the forward eager until
    # we pin a working torch or adopt a hand-rolled CUDA-graph capture.
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3.5-27B-FP8",
                        help="HF repo id or local path (Qwen3.5 native FP8).")
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
