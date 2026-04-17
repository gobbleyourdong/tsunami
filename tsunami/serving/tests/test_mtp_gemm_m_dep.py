#!/usr/bin/env python3
"""Is the FP8 GEMM in MTP's q/k/v projections genuinely M-dependent?

Iter-34/35 narrowed the drift to MTP's linear projections in the decoder
layer's self_attn. Before committing to an FP32-upcast refactor, verify
directly: for the SAME MTP projection (k_proj) and the SAME input
activations, does a batched call (M=14) produce different outputs than
per-row single calls (M=1 repeated 14 times)?

If diff at row 13 = ~1.953e-3 → hypothesis confirmed at the GEMM level.
  Structural fix: skip FP8 wrapping for MTP's q/k/v/o_proj and run them as
  plain BF16 Linear layers (per-row-independent matmul).

If diff ≈ 0 → the GEMM is M-invariant and the drift lives upstream (input
  layernorm, RoPE, or how K/V are assembled from projection output).
"""
import sys
from pathlib import Path
import torch

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

from transformers import AutoConfig, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head
from serve_qwen36_fp8 import _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)


@torch.no_grad()
def main_entrypoint():
    print("=== FP8 GEMM M-dependency probe ===")
    cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
    cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
    cfg.text_config._attn_implementation = "eager"
    cfg._attn_implementation = "eager"
    cache_f = _fuse_cache_path(SNAP, Path.home() / ".cache" / "sigma_fuse")
    sd = _load_fused_from_cache(cache_f, device="cuda:0") if cache_f.exists() else _build_fused_state_dict(SNAP)
    main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
        None, config=cfg, state_dict=sd, dtype="auto",
        device_map="cuda:0", trust_remote_code=True,
        attn_implementation="eager", low_cpu_mem_usage=True,
    )
    sd = None; torch.cuda.empty_cache()
    mtp = load_mtp_head(SNAP, cfg.text_config, main, cfg.quantization_config, device="cuda:0")
    torch.cuda.empty_cache()
    print(f"loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

    k_proj = mtp.layer.self_attn.k_proj
    print(f"k_proj type: {type(k_proj).__name__}")
    print(f"k_proj.weight dtype: {k_proj.weight.dtype}, shape: {tuple(k_proj.weight.shape)}")
    if hasattr(k_proj, "weight_scale_inv"):
        print(f"k_proj.weight_scale_inv shape: {tuple(k_proj.weight_scale_inv.shape)}")

    H = mtp.hidden_size
    N = 14  # match H2 test's prompt length
    # Deterministic input: same values whether we call batched or per-row.
    torch.manual_seed(0)
    X = torch.randn(1, N, H, dtype=torch.bfloat16, device="cuda:0")

    # Path A: batched call (M=N)
    out_batched = k_proj(X)  # (1, N, kv_hidden)
    # Path B: per-row single calls (M=1 each)
    rows = [k_proj(X[:, i:i+1, :]) for i in range(N)]
    out_single = torch.cat(rows, dim=1)

    print(f"\nout_batched shape: {tuple(out_batched.shape)}")
    diffs_max = [float((out_batched[:, i, :] - out_single[:, i, :]).abs().max().item()) for i in range(N)]
    diffs_mean = [float((out_batched[:, i, :] - out_single[:, i, :]).abs().mean().item()) for i in range(N)]

    print(f"\n{'row':>4}  {'|Δ|∞':>12}  {'|Δ|_mean':>12}")
    for i in range(N):
        print(f"{i:>4}  {diffs_max[i]:>12.3e}  {diffs_mean[i]:>12.3e}")

    overall_max = max(diffs_max)
    print(f"\noverall |Δ|∞ = {overall_max:.3e}")

    print("\nINTERPRETATION:")
    if overall_max > 1e-4:
        print("  FP8 GEMM IS M-dependent. Drift lives in the kernel dispatch.")
        print("  Justifies FP32 upcast of MTP's q/k/v/o_proj (skip FP8 wrapping).")
    else:
        print("  FP8 GEMM is M-invariant at this tolerance. Drift lives upstream")
        print("  of the projection — likely in input_layernorm, RoPE application,")
        print("  or how K/V are assembled into multi-head layout.")

    # Also compare v_proj and q_proj
    for pname in ("v_proj", "q_proj"):
        p = getattr(mtp.layer.self_attn, pname)
        ob = p(X)
        os = torch.cat([p(X[:, i:i+1, :]) for i in range(N)], dim=1)
        dmax = float((ob - os).abs().max().item())
        print(f"{pname}: overall |Δ|∞ = {dmax:.3e}")


if __name__ == "__main__":
    main_entrypoint()
