#!/usr/bin/env python3
"""MTP H2 probe — do streaming cache writes produce different K/V than a
fresh prefill at the same slot, for identical hidden + token inputs?

Iter-33 eager confirmed H1 is fully closed by cache-invariant attention
(|Δh|∞ = 0.000e+00 across all layers + positions). Yet MTP greedy accept
under eager is 13%, far below the 83% diagnostic ceiling. The remaining
gap must live in MTP itself — either its cache-write path diverges from its
prefill path, or its attention computation on accumulated cache entries
produces different logits than on a freshly-rebuilt cache.

Protocol (all under attn_implementation="eager" so main's hidden is
bit-identical across paths):
  1. Run main over a prompt of S tokens to get hidden + committed tokens.
  2. Extend by one MORE token T (the first decode position).
  3. Path A — rebuild: mtp_prefill over the full (S+1)-token sequence, take
     the resulting DynamicCache. Has S slots (0..S-1).
  4. Path B — streaming: mtp_prefill over the first S tokens → cache with
     S-1 slots. Then one mtp_head call with (hidden_{S-1}, token_S) at
     position_id S-1 → appends slot S-1. Final cache has S slots.
  5. Compare the two caches slot-by-slot: K/V tensor |Δ|∞ at each slot.
  6. Probe the NEXT MTP prediction: feed (hidden_S, hypothetical_token) to
     both caches, compare logits.

If cache contents match slot-for-slot and the next-step logits agree, H2
is negative — MTP's streaming path IS semantically equivalent to rebuild,
and the 13% → 83% gap is elsewhere (probably hidden-input convention [-2]
vs whatever MTP was trained on).

If cache contents differ at some slot, that's the smoking gun.
"""
import os, sys
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
from mtp_module import load_mtp_head, mtp_prefill
from serve_qwen36_fp8 import (
    _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict,
)

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)
ATTN_IMPL = os.environ.get("ATTN_IMPL", "eager").strip()  # default to eager
HIDDEN_LAYER = int(os.environ.get("HIDDEN_LAYER", "-2"))


def get_cache_slot(cache, slot_idx):
    """Return (K, V) tensors at a given slot index of a DynamicCache. Handles
    both `key_cache` list-of-tensors and `layers[i].keys` variants."""
    # DynamicCache in recent transformers: `cache.layers` is a list of
    # DynamicLayer, each holding keys/values. But MTP has only one layer, so
    # there's just layer index 0; "slot_idx" is the position within that
    # layer's sequence-length dimension.
    lyr = None
    layers = getattr(cache, "layers", None)
    if layers is not None and len(layers) > 0:
        lyr = layers[0]
        k = getattr(lyr, "keys", None) or getattr(lyr, "key_cache", None)
        v = getattr(lyr, "values", None) or getattr(lyr, "value_cache", None)
    else:
        key_list = getattr(cache, "key_cache", None)
        val_list = getattr(cache, "value_cache", None)
        k = key_list[0] if key_list else None
        v = val_list[0] if val_list else None
    if k is None or v is None:
        raise RuntimeError("could not extract K/V from DynamicCache")
    # Shape is typically (B, heads, seq_len, head_dim)
    return k[..., slot_idx, :], v[..., slot_idx, :]


@torch.no_grad()
def main_entrypoint():
    print(f"=== MTP H2 probe — cache-write semantics (attn_impl={ATTN_IMPL}) ===")
    cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
    cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
    cfg.text_config._attn_implementation = ATTN_IMPL
    cfg._attn_implementation = ATTN_IMPL
    cache_f = _fuse_cache_path(SNAP, Path.home() / ".cache" / "sigma_fuse")
    if cache_f.exists():
        sd = _load_fused_from_cache(cache_f, device="cuda:0")
    else:
        sd = _build_fused_state_dict(SNAP)
    main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
        None, config=cfg, state_dict=sd, dtype="auto",
        device_map="cuda:0", trust_remote_code=True,
        attn_implementation=ATTN_IMPL, low_cpu_mem_usage=True,
    )
    sd = None; torch.cuda.empty_cache()
    mtp = load_mtp_head(
        SNAP, cfg.text_config, main, cfg.quantization_config, device="cuda:0"
    )
    torch.cuda.empty_cache()
    tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)
    print(f"main + MTP loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

    prompt = "Count from 1 to 40, one number per line."
    ids = tok(prompt, return_tensors="pt").input_ids.to("cuda:0")
    S = ids.shape[1]
    print(f"prompt S={S}")

    # Sample ONE greedy continuation token to get a committed token T at pos S.
    with torch.no_grad():
        o = main(input_ids=ids, output_hidden_states=True, use_cache=False)
    logits_tail = o.logits[:, -1, :]
    token_at_S = logits_tail.argmax(dim=-1, keepdim=True)
    print(f"first decode token at pos S: {token_at_S.item()}  "
          f"= {tok.decode([int(token_at_S.item())])!r}")

    # Build the cumulative (S+1)-token sequence and its prefill hidden.
    full_ids = torch.cat([ids, token_at_S], dim=1)           # (1, S+1)
    o_full = main(input_ids=full_ids, output_hidden_states=True, use_cache=False)
    hidden_full = o_full.hidden_states[HIDDEN_LAYER]         # (1, S+1, H)
    # Ditto for just the prompt:
    o_prompt = main(input_ids=ids, output_hidden_states=True, use_cache=False)
    hidden_prompt = o_prompt.hidden_states[HIDDEN_LAYER]     # (1, S, H)

    # --- Path A: rebuild ---
    cache_rebuild = mtp_prefill(hidden_full, full_ids, mtp)
    slots_rebuild = cache_rebuild.get_seq_length()
    print(f"\nPath A (rebuild): MTP prefill over {S+1} tokens → slots={slots_rebuild}")

    # --- Path B: streaming ---
    cache_stream = mtp_prefill(hidden_prompt, ids, mtp)
    slots_stream_before = cache_stream.get_seq_length()
    print(f"Path B (streaming): MTP prefill over {S} tokens → slots={slots_stream_before}")
    # One streaming step: (hidden_{S-1}, token_S) at RoPE pos S-1 writes slot S-1.
    last_hidden = hidden_prompt[:, -1:, :]
    pos = torch.tensor([[cache_stream.get_seq_length()]], device="cuda:0")
    _ = mtp(
        hidden_from_main=last_hidden,
        next_token_ids=token_at_S,
        position_ids=pos,
        past_key_values=cache_stream,
    )
    slots_stream = cache_stream.get_seq_length()
    print(f"after one streaming step → slots={slots_stream}")

    if slots_stream != slots_rebuild:
        print(f"✗ slot counts differ ({slots_stream} vs {slots_rebuild})")
        return

    # --- Slot-by-slot K/V comparison ---
    print("\n=== slot-by-slot K/V diff ===")
    print(f"{'slot':>4}  {'|ΔK|∞':>12}  {'|ΔV|∞':>12}  {'|ΔK|mean':>12}  {'|ΔV|mean':>12}")
    any_drift = False
    for i in range(slots_rebuild):
        k_r, v_r = get_cache_slot(cache_rebuild, i)
        k_s, v_s = get_cache_slot(cache_stream, i)
        dk_max = float((k_r - k_s).abs().max().item())
        dv_max = float((v_r - v_s).abs().max().item())
        dk_mean = float((k_r - k_s).abs().mean().item())
        dv_mean = float((v_r - v_s).abs().mean().item())
        if dk_max > 1e-6 or dv_max > 1e-6:
            any_drift = True
        print(f"{i:>4}  {dk_max:>12.3e}  {dv_max:>12.3e}  "
              f"{dk_mean:>12.3e}  {dv_mean:>12.3e}")

    # --- Next-step MTP logits under both caches ---
    # Feed (hidden_S, hypothetical_next_token) to both caches, compare logits.
    # Use hidden at position S from the full prefill — bit-identical in both paths.
    last_hidden_next = hidden_full[:, -1:, :]
    # Need a "next token" to fuse with hidden_S; use whatever main predicts at S.
    next_tok = o_full.logits[:, -1, :].argmax(dim=-1, keepdim=True)

    pos_r = torch.tensor([[cache_rebuild.get_seq_length()]], device="cuda:0")
    pos_s = torch.tensor([[cache_stream.get_seq_length()]], device="cuda:0")
    # IMPORTANT: make independent shallow copies so both caches advance
    # symmetrically without poisoning each other.
    import copy
    cache_r2 = copy.deepcopy(cache_rebuild)
    cache_s2 = copy.deepcopy(cache_stream)
    logits_r = mtp(
        hidden_from_main=last_hidden_next, next_token_ids=next_tok,
        position_ids=pos_r, past_key_values=cache_r2,
    )
    logits_s = mtp(
        hidden_from_main=last_hidden_next, next_token_ids=next_tok,
        position_ids=pos_s, past_key_values=cache_s2,
    )
    dl = float((logits_r - logits_s).abs().max().item())
    top1_match = (logits_r.argmax() == logits_s.argmax()).item()
    print(f"\nnext-step MTP logits |Δ|∞ = {dl:.3e}  top1_match = {top1_match}")

    print("\nDIAGNOSIS:")
    if not any_drift and dl < 1e-4:
        print("  H2 NEGATIVE — streaming == rebuild at the cache + logits level.")
        print("  The 13% → 83% gap must lie elsewhere (hidden-layer choice,")
        print("  MTP prediction quality at these specific positions, or the")
        print("  per-step protocol diverging from what MTP was trained on).")
    elif any_drift:
        print("  H2 POSITIVE — MTP's streaming cache writes different K/V than")
        print("  its prefill path for identical inputs. The slot with the")
        print("  largest |ΔK|∞ / |ΔV|∞ above is the smoking gun.")
    else:
        print("  Caches match but logits diverge — possibly an attention-mask")
        print("  or position-id wiring issue in the decode forward path.")


if __name__ == "__main__":
    main_entrypoint()
