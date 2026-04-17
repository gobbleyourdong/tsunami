#!/usr/bin/env python3
"""Iter-39: is fc M-dependent on the REAL streaming inputs, or only on
random inputs?

iter-37 measured fc drift of 7.8e-3 at M=1 vs M=14 on random bf16 input.
iter-37/38 fp32 fixes didn't move the H2 slot-13 drift (stayed exactly
1.953e-3 / 3.906e-3). Question: does the real `[norm_emb(embed(token)),
norm_h(hidden)]` input actually trigger fc's M-dependency?

If fc-on-real-inputs shows 0 drift → iter-37 was a red herring, true
source is elsewhere. If it shows ~7.8e-3 → fc IS the source, and the
fp32 fixes mysteriously didn't help (TF32 / cuBLAS subtlety).
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

from transformers import AutoConfig, AutoTokenizer, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head
from serve_qwen36_fp8 import _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)


@torch.no_grad()
def main_entrypoint():
    print("=== iter-39: fc M-dependency on REAL inputs ===")
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
    tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)
    torch.cuda.empty_cache()
    print(f"loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

    # Build real inputs: prompt → tokens, embed + hidden, form fc inputs the
    # same way mtp_prefill does: cat([norm_emb(embed(t[1:])), norm_h(hidden[:-1])])
    prompt = "Count from 1 to 40, one number per line."
    ids = tok(prompt, return_tensors="pt").input_ids.to("cuda:0")
    S = ids.shape[1]
    print(f"prompt S={S}")

    o = main(input_ids=ids, output_hidden_states=True, use_cache=False)
    hidden = o.hidden_states[-2]  # (1, S, H)
    H = hidden.shape[-1]

    h_shift = hidden[:, :-1, :]        # (1, S-1, H)
    t_shift = ids[:, 1:]                # (1, S-1)
    emb = mtp.embed_tokens(t_shift)     # (1, S-1, H)
    real_2h = torch.cat([
        mtp.pre_fc_norm_embedding(emb),
        mtp.pre_fc_norm_hidden(h_shift),
    ], dim=-1)                          # (1, S-1, 2H) — the actual fc input

    print(f"real fc input shape: {tuple(real_2h.shape)}, dtype: {real_2h.dtype}")
    print(f"  mean: {real_2h.float().mean().item():.4f}  std: {real_2h.float().std().item():.4f}")
    print(f"  |x|∞: {real_2h.float().abs().max().item():.4f}")

    N = S - 1  # number of rows in the fc input
    # Batched fc call (M=N)
    out_batched = mtp.fc(real_2h)                                   # (1, N, H)
    # Per-row single calls (M=1 × N)
    out_single = torch.cat([mtp.fc(real_2h[:, i:i+1, :]) for i in range(N)], dim=1)

    diffs_max = [float((out_batched[:, i, :] - out_single[:, i, :]).abs().max().item()) for i in range(N)]
    diffs_mean = [float((out_batched[:, i, :] - out_single[:, i, :]).abs().mean().item()) for i in range(N)]
    print(f"\nfc on REAL inputs, per-row |Δ|∞:")
    for i in range(N):
        print(f"  row {i:>2}: |Δ|∞ = {diffs_max[i]:>10.3e}  |Δ|_mean = {diffs_mean[i]:>10.3e}")
    overall = max(diffs_max)
    print(f"\noverall max |Δ|∞ = {overall:.3e}")

    # Compare to a random-input call with the same shape, for the iter-37 control
    torch.manual_seed(0)
    rand_2h = torch.randn_like(real_2h)
    r_batched = mtp.fc(rand_2h)
    r_single = torch.cat([mtp.fc(rand_2h[:, i:i+1, :]) for i in range(N)], dim=1)
    rand_diffs = [float((r_batched[:, i, :] - r_single[:, i, :]).abs().max().item()) for i in range(N)]
    print(f"fc on RANDOM inputs (control), overall max |Δ|∞ = {max(rand_diffs):.3e}")

    print("\nVERDICT:")
    if overall > 1e-4 and max(rand_diffs) > 1e-4:
        print("  fc is M-dependent on BOTH real and random inputs.")
        print("  → iter-37 was right about the source. The fp32/TF32-off fixes")
        print("    genuinely failed to eliminate the drift — cuBLAS fp32 on")
        print("    Blackwell is M-dependent at the same precision as bf16.")
    elif overall < 1e-4 and max(rand_diffs) > 1e-4:
        print("  fc is M-dependent on RANDOM inputs but NOT on real inputs.")
        print("  → iter-37 was a red herring. True streaming drift source is")
        print("    elsewhere — need to probe further.")
    elif overall < 1e-4 and max(rand_diffs) < 1e-4:
        print("  fc is M-invariant on both inputs. iter-37 result was spurious.")
    else:
        print("  fc is M-dependent on real inputs but not random. Unusual.")


if __name__ == "__main__":
    main_entrypoint()
