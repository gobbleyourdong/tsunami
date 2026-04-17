#!/usr/bin/env python3
"""MTP drift isolation: why does streaming decode report 9% greedy accept when
test_mtp_diagnose measures ~83% per-position top-1 alignment via fresh-rebuild?

CONFIRMED FINDING (2026-04-17): main's hidden_states[-2] from a prefill with
use_cache=True diverges from the same prefill with use_cache=False at the SAME
position, for IDENTICAL token inputs, by |Δh|∞ ~ 0.44 in bf16 under the
default SDPA attention. That drift snowballs through subsequent decode steps
(|Δh|∞ 2-14 across 11 streaming positions, KL > 4 nats vs prefill-equivalent
MTP logits on 8 of 11 steps).

Iter-33 partial fix: forcing attn_implementation="eager" lifted MTP greedy
accept 9% → 13% — eager uses the SAME code path for prefill with/without
cache, so it should (in theory) drive the sanity diff to ~0. Re-run this
script with ATTN_IMPL=eager to verify empirically:
  ATTN_IMPL=eager python3 tsunami/serving/tests/test_mtp_streaming_drift.py

If eager sanity diff IS ~0 but MTP accept under eager is still only 13% (not
83%), the remaining 70pp gap lives in H2 — MTP's streaming cache-entry
semantics differ from fresh-prefill even with identical hidden inputs. If
eager sanity diff is NOT 0, the kernel drift has multiple sources and deeper
investigation of attention-dispatch paths is warranted.

Run:
  python3 tsunami/serving/tests/test_mtp_streaming_drift.py             # default (sdpa)
  ATTN_IMPL=eager python3 tsunami/serving/tests/test_mtp_streaming_drift.py
"""
import os, sys
from pathlib import Path
import torch

ATTN_IMPL = os.environ.get("ATTN_IMPL", "").strip() or None  # None = auto

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami/serving")

import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())

from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm
def _ds_shim(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    orig = A.shape
    A2 = A.reshape(-1, orig[-1]).contiguous()
    As2 = As.reshape(-1, As.shape[-1]).contiguous() if As.dim() >= 2 else As.contiguous()
    prev = torch.get_default_dtype()
    if output_dtype is not None and output_dtype != prev:
        torch.set_default_dtype(output_dtype)
    try:
        out = _ds_fp8_gemm(A2, As2, B.contiguous(), Bs.contiguous())
    finally:
        if output_dtype is not None and output_dtype != prev:
            torch.set_default_dtype(prev)
    return out.view(*orig[:-1], B.shape[0])
_fgfp8.w8a8_fp8_matmul = _ds_shim

from transformers import AutoConfig, AutoTokenizer, Qwen3_5MoeForConditionalGeneration
from serve_qwen36_fp8 import (
    _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict,
)

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)


def load():
    cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
    cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
    if ATTN_IMPL:
        cfg.text_config._attn_implementation = ATTN_IMPL
        cfg._attn_implementation = ATTN_IMPL
    cache = _fuse_cache_path(SNAP, Path.home() / ".cache" / "sigma_fuse")
    if cache.exists():
        print(f"loading main from fused cache {cache.name}")
        sd = _load_fused_from_cache(cache, device="cuda:0")
    else:
        print("building fused sd from raw shards (slow)")
        sd = _build_fused_state_dict(SNAP)
    kw = dict(
        config=cfg, state_dict=sd, dtype="auto",
        device_map="cuda:0", trust_remote_code=True, low_cpu_mem_usage=True,
    )
    if ATTN_IMPL:
        kw["attn_implementation"] = ATTN_IMPL
    main = Qwen3_5MoeForConditionalGeneration.from_pretrained(None, **kw)
    sd = None; torch.cuda.empty_cache()
    resolved = getattr(main.config, "_attn_implementation", "?")
    print(f"  attn_impl resolved: {resolved}")
    tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)
    return main, tok


@torch.no_grad()
def main_entrypoint():
    print("=== MTP streaming drift: cached vs uncached prefill hidden ===")
    main, tok = load()
    print(f"main loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

    prompt = "Count from 1 to 40, one number per line."
    ids = tok(prompt, return_tensors="pt").input_ids.to("cuda:0")
    S = ids.shape[1]
    print(f"Prompt: {prompt!r}  -> S={S} tokens")

    # Two prefills over IDENTICAL inputs, differing only in the use_cache flag.
    # If the attention kernel path is cache-agnostic in numerics, these should
    # be bit-identical. If dispatches differ (e.g. sdpa-prefill vs sdpa-decode),
    # we'll see BF16-scale precision drift. If they differ by > 1e-3, something
    # more substantial is going on and MTP's input distribution in streaming
    # decode does NOT match what a fresh rebuild gives it.
    for layer_idx in (-1, -2):
        print(f"\n-- hidden_states[{layer_idx}] --")
        o_uncached = main(input_ids=ids, output_hidden_states=True, use_cache=False)
        h_uncached = o_uncached.hidden_states[layer_idx]
        o_cached = main(input_ids=ids, output_hidden_states=True, use_cache=True)
        h_cached = o_cached.hidden_states[layer_idx]
        # Compare at the last position (tail of prompt) — this is what MTP's
        # first decode step feeds into the head.
        tail_u = h_uncached[:, -1, :]
        tail_c = h_cached[:, -1, :]
        dmax = float((tail_u - tail_c).abs().max().item())
        dmean = float((tail_u - tail_c).abs().mean().item())
        print(f"  pos S-1 cached vs uncached  |Δ|∞ = {dmax:.3e}  |Δ|_mean = {dmean:.3e}")
        # All-position summary
        dmax_all = float((h_uncached - h_cached).abs().max().item())
        print(f"  all positions  |Δ|∞ = {dmax_all:.3e}")

    # Also inspect the raw logits divergence at the tail position — this is
    # what main's next-token sampler sees. A large shift here would drift the
    # generated trajectory; a small shift means the LM head de-noises.
    o1 = main(input_ids=ids, use_cache=False)
    o2 = main(input_ids=ids, use_cache=True)
    l1 = o1.logits[:, -1, :]
    l2 = o2.logits[:, -1, :]
    print(f"\nlogits at pos S-1 cached vs uncached  |Δ|∞ = "
          f"{float((l1 - l2).abs().max().item()):.3e}  "
          f"top1 match = {(l1.argmax() == l2.argmax()).item()}")

    print(
        "\nIf |Δh|∞ > 1e-3 at either hidden layer, the cached attention path"
        " produces materially different hidden than the uncached path, and"
        " streaming MTP decode is fed a distribution the fresh-rebuild"
        " diagnostic does not see. The 9% vs 83% gap is explained by"
        " training-distribution mismatch rather than a cache-management bug."
    )


if __name__ == "__main__":
    main_entrypoint()
