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

    # Iter-37 probes: fc (bf16 Linear, 2H→H) and input_layernorm.
    # If fc is M-dependent, the drifted x propagates into all downstream
    # compute — that would be the source. If fc is clean, the drift must
    # be inside the decoder layer itself.
    print("\n--- iter-37: upstream probes ---")
    X2H = torch.randn(1, N, 2 * H, dtype=torch.bfloat16, device="cuda:0")
    fc_batched = mtp.fc(X2H)
    fc_single = torch.cat([mtp.fc(X2H[:, i:i+1, :]) for i in range(N)], dim=1)
    dfc = float((fc_batched - fc_single).abs().max().item())
    print(f"fc (bf16 Linear 2H→H): overall |Δ|∞ = {dfc:.3e}")

    # input_layernorm on the decoder layer
    iln = mtp.layer.input_layernorm
    iln_batched = iln(X)
    iln_single = torch.cat([iln(X[:, i:i+1, :]) for i in range(N)], dim=1)
    diln = float((iln_batched - iln_single).abs().max().item())
    print(f"input_layernorm (Qwen3_5MoeRMSNorm): overall |Δ|∞ = {diln:.3e}")

    # Post_attention_layernorm (also RMSNorm, in the residual branch).
    paln = mtp.layer.post_attention_layernorm
    paln_batched = paln(X)
    paln_single = torch.cat([paln(X[:, i:i+1, :]) for i in range(N)], dim=1)
    dpaln = float((paln_batched - paln_single).abs().max().item())
    print(f"post_attention_layernorm: overall |Δ|∞ = {dpaln:.3e}")

    # Full decoder-layer call — compare K/V written to cache at slot i
    # between batched and single-row calls.
    from transformers import DynamicCache
    # Build fresh caches; call the layer batched and single-row, extract
    # the resulting K/V at slot 13 from each.
    pos_batched = torch.arange(N, device="cuda:0")[None, :]
    # Need position_embeddings; construct via mtp.rotary_emb
    pos_emb_batched = mtp.rotary_emb(X, pos_batched)
    cache_b = DynamicCache()
    _ = mtp.layer(X, position_ids=pos_batched, position_embeddings=pos_emb_batched,
                  past_key_values=cache_b, use_cache=True)
    # Extract slot 13 K/V from cache_b
    lyr_b = cache_b.layers[0]
    k_b = getattr(lyr_b, "keys", None)
    if k_b is None:
        k_b = getattr(lyr_b, "key_cache", None)
    v_b = getattr(lyr_b, "values", None)
    if v_b is None:
        v_b = getattr(lyr_b, "value_cache", None)
    k_b_13 = k_b[..., 13, :]
    v_b_13 = v_b[..., 13, :]

    # Now per-row: build cache by streaming rows 0..13 one at a time
    cache_s = DynamicCache()
    for i in range(N):
        xi = X[:, i:i+1, :]
        pos_i = torch.tensor([[i]], device="cuda:0")
        pe_i = mtp.rotary_emb(xi, pos_i)
        _ = mtp.layer(xi, position_ids=pos_i, position_embeddings=pe_i,
                      past_key_values=cache_s, use_cache=True)
    lyr_s = cache_s.layers[0]
    k_s = getattr(lyr_s, "keys", None)
    if k_s is None:
        k_s = getattr(lyr_s, "key_cache", None)
    v_s = getattr(lyr_s, "values", None)
    if v_s is None:
        v_s = getattr(lyr_s, "value_cache", None)
    k_s_13 = k_s[..., 13, :]
    v_s_13 = v_s[..., 13, :]

    dk13 = float((k_b_13 - k_s_13).abs().max().item())
    dv13 = float((v_b_13 - v_s_13).abs().max().item())
    print(f"full decoder_layer slot 13 |ΔK|∞ = {dk13:.3e}, |ΔV|∞ = {dv13:.3e}")

    print("\nSUMMARY:")
    print(f"  fc bf16 GEMM:            {dfc:.3e}")
    print(f"  input_layernorm:         {diln:.3e}")
    print(f"  post_attention_layernorm:{dpaln:.3e}")
    print(f"  decoder_layer slot 13 K: {dk13:.3e}")
    print(f"  decoder_layer slot 13 V: {dv13:.3e}")
    print(f"  (target reproduces H2 slot-13 drift: ~1.953e-3 / ~3.906e-3)")


if __name__ == "__main__":
    main_entrypoint()
