#!/usr/bin/env python3
"""MTP diagnostic harness — surgical tool to isolate the 0% accept bug.

Four in-session iterations tried (position_ids off-by-one, hidden-state slicing,
causal prefill mask, fc concat flip) — all 0% accept. The remaining hypotheses
need direct inspection rather than another full generate-loop:

  H-A  Weights broken:  MTP's logits look uniform (entropy ≈ log(V))
  H-B  Alignment bug:   MTP's logits are peaked but on wildly wrong tokens
  H-C  Shift-by-one:    MTP's top-k overlaps main's top-k but at position t±1
  H-D  Protocol issue:  MTP produces reasonable tokens but our accept rule is
                        comparing the wrong positions

This script loads main + MTP, runs main over a prompt, then for 20 consecutive
positions computes both main's and MTP's top-10 distributions side by side. The
output pattern tells you which hypothesis is correct.

Run:
  python3 test_mtp_diagnose.py

Requires free GPU (server should be stopped first).
"""
import sys, time
from pathlib import Path
import torch

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")

# Mirror server-side monkeypatches
import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())
from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm
def _ds_shim(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    orig = A.shape
    A2 = A.reshape(-1, orig[-1]).contiguous()
    As2 = As.reshape(-1, As.shape[-1]).contiguous() if As.dim() >= 2 else As.contiguous()
    prev = torch.get_default_dtype()
    if output_dtype is not None and output_dtype != prev: torch.set_default_dtype(output_dtype)
    try: out = _ds_fp8_gemm(A2, As2, B.contiguous(), Bs.contiguous())
    finally:
        if output_dtype is not None and output_dtype != prev: torch.set_default_dtype(prev)
    return out.view(*orig[:-1], B.shape[0])
_fgfp8.w8a8_fp8_matmul = _ds_shim

from transformers import AutoConfig, AutoTokenizer, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head, mtp_prefill
from serve_qwen35_fp8 import (
    _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict,
)

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)

print("=== MTP diagnostic ===")
cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size

cache_file = _fuse_cache_path(SNAP, Path.home() / ".cache" / "sigma_fuse")
if cache_file.exists():
    print(f"loading main from fused cache {cache_file.name} …")
    sd = _load_fused_from_cache(cache_file, device="cuda:0")
else:
    print("building fused sd from raw shards (slow) …")
    sd = _build_fused_state_dict(SNAP)

main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd, dtype="auto",
    device_map="cuda:0", trust_remote_code=True, low_cpu_mem_usage=True,
)
sd = None; torch.cuda.empty_cache()
print(f"main loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

print("loading MTP head …")
mtp = load_mtp_head(SNAP, cfg.text_config, main, cfg.quantization_config, device="cuda:0")
torch.cuda.empty_cache()
print(f"MTP loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

# Probe actual weight values. RMSNorm weights should cluster around 1.0 when
# properly loaded (they were trained to that regime). fc.weight is FP8 with
# a scale_inv; we check its stored bfloat16/fp32 min/max to see if it's all
# zero (load failure) or random (default init).
print("\n-- MTP weight sanity probe --")
for name, mod in mtp.named_modules():
    if hasattr(mod, "weight") and mod.weight is not None:
        w = mod.weight.data
        n = w.numel()
        if n == 0: continue
        # Sample absolute stats; FP8 tensors may need float cast.
        try:
            wf = w.float()
            vmin, vmax = float(wf.abs().min()), float(wf.abs().max())
            mean = float(wf.mean())
        except Exception as e:
            print(f"  {name:<50} shape={list(w.shape)} dtype={w.dtype} (skipped: {e})")
            continue
        # Only surface the interesting (non-huge) modules
        if n < 100_000 or "norm" in name or name in ("fc", "layer.self_attn.q_proj", "layer.self_attn.k_proj"):
            print(f"  {name:<50} shape={list(w.shape)} dtype={w.dtype}  |abs|=[{vmin:.3g},{vmax:.3g}]  mean={mean:.3g}")

tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)
prompt = "Count from 1 to 40, one number per line."
ids = tok(prompt, return_tensors="pt").input_ids.to("cuda:0")
S = ids.shape[1]
print(f"\nPrompt: {prompt!r}  -> {S} tokens")

# Run main once to get hidden states
with torch.no_grad():
    out = main(input_ids=ids, output_hidden_states=True, use_cache=False)
last_hidden = out.hidden_states[-1]  # trying POST-final-norm (was -2); convention varies by checkpoint
main_logits = out.logits  # (1, S, V)
V = main_logits.shape[-1]
print(f"main logits shape {tuple(main_logits.shape)}, vocab={V}")

# Also check post-final-norm variant for comparison
last_hidden_post = out.hidden_states[-1]
print(f"hidden_states[-2] mean/std: {last_hidden.mean().item():.4f} / {last_hidden.std().item():.4f}")
print(f"hidden_states[-1] mean/std: {last_hidden_post.mean().item():.4f} / {last_hidden_post.std().item():.4f}")

# Populate MTP's KV cache over the prompt
print("\n-- MTP self_attn runtime config --")
print(f"  mtp.layer.self_attn.layer_idx: {getattr(mtp.layer.self_attn, 'layer_idx', 'MISSING')}")
print(f"  mtp.layer.layer_idx: {getattr(mtp.layer, 'layer_idx', 'MISSING')}")
print(f"  self_attn attn class: {type(mtp.layer.self_attn).__name__}")

print("\nprefilling MTP cache …")
mtp_past = mtp_prefill(last_hidden, ids, mtp)
print(f"MTP cache seq_length: {mtp_past.get_seq_length()}")

# Dump cache internal structure to see which slots are populated
print("-- DynamicCache internals after prefill --")
# DynamicCache stores per-layer state; implementation detail varies across
# transformers versions. Probe common attributes.
for attr in ("key_cache", "value_cache", "_seen_tokens", "layers"):
    v = getattr(mtp_past, attr, None)
    if v is None:
        continue
    if isinstance(v, list):
        print(f"  {attr}: len={len(v)}", end="")
        if v and hasattr(v[0], "shape"):
            shapes = [tuple(t.shape) if hasattr(t, "shape") else type(t).__name__ for t in v[:5]]
            print(f"  first_shapes={shapes}")
        else:
            # Layer objects — peek into key_cache / value_cache on each
            print()
            for i, layer in enumerate(v[:5]):
                ks = getattr(layer, "keys", None)
                if ks is None:
                    ks = getattr(layer, "key_cache", None)
                vs = getattr(layer, "values", None)
                if vs is None:
                    vs = getattr(layer, "value_cache", None)
                ksh = tuple(ks.shape) if ks is not None and hasattr(ks, "shape") else None
                vsh = tuple(vs.shape) if vs is not None and hasattr(vs, "shape") else None
                print(f"    layer[{i}]: type={type(layer).__name__}  k.shape={ksh}  v.shape={vsh}")
    else:
        print(f"  {attr}: {v}")

# Direct logits comparison at each position
print("\n=== Per-position top-5 comparison (main vs MTP) ===")
print(f"{'pos':>3}  {'main-top5':<60}  {'mtp-top5':<60}")
# For first decode step we simulate: at position t, main would predict t+1
# from hidden[t]; MTP would predict t+2 from (hidden[t], token[t+1]).
# Walk t from S-20 to S-2 so we compare 18 consecutive positions.
def top5_readable(logits, tokenizer):
    probs = torch.softmax(logits.float(), dim=-1)
    vals, idx = torch.topk(probs, 5, dim=-1)
    return "  ".join(f"{tokenizer.decode([int(i)])!r}={float(v):.2f}" for v, i in zip(vals[0], idx[0]))

start = max(1, S - 20)
# Build per-position MTP logits by stepping the MTP head once per position,
# each time with hidden[t] and the ground-truth next token[t+1].
# We only reuse the prefilled cache; no cache rollbacks needed because this
# is purely diagnostic (we re-create the cache per call).
for t in range(start, S - 1):
    h_t = last_hidden[:, t:t+1, :]                 # hidden at position t
    tok_t_plus_1 = ids[:, t+1:t+2]                  # ground-truth token at t+1
    # Fresh cache per step to match what decode sees at position t.
    from transformers import DynamicCache
    fresh_cache = mtp_prefill(last_hidden[:, :t+1, :], ids[:, :t+1], mtp)
    pos = torch.tensor([[fresh_cache.get_seq_length()]], device="cuda:0")
    with torch.no_grad():
        mlogits = mtp(h_t, tok_t_plus_1, position_ids=pos, past_key_values=fresh_cache)
    # main predicts token at position t+1 from hidden[t]. MTP predicts t+2
    # from (hidden[t], token[t+1]). So compare main.logits[t+1] against
    # mtp.logits — they should both score "token at position t+2".
    # Wait: main.logits[t] predicts token[t+1]. To get "main predicts t+2",
    # we need main.logits[t+1] — which is the column for position t+1.
    main_top = top5_readable(main_logits[:, t+1, :], tok)
    mtp_top  = top5_readable(mlogits[:, 0, :],      tok)
    print(f"{t:>3}  {main_top:<60}  {mtp_top:<60}")

# Final summary: entropy check (uniform ~= log(V) ~= 12.3 for 150K vocab)
import math
uniform_entropy = math.log(V)
mtp_last = mlogits[:, 0, :]
ent_m = -(torch.softmax(main_logits[0, -1], -1) * torch.log_softmax(main_logits[0, -1], -1)).sum().item()
ent_p = -(torch.softmax(mtp_last[0], -1) * torch.log_softmax(mtp_last[0], -1)).sum().item()
print(f"\nEntropy (max = {uniform_entropy:.2f}):")
print(f"  main.logits[-1]: {ent_m:.3f}  (peaked={ent_m/uniform_entropy < 0.4})")
print(f"  mtp.logits[-1]:  {ent_p:.3f}  (peaked={ent_p/uniform_entropy < 0.4})")
print("\nDIAGNOSIS HINTS:")
print("  - If MTP entropy ~= log(V), weights are broken (H-A).")
print("  - If MTP entropy is low but tokens are wildly wrong, alignment bug (H-B).")
print("  - If MTP's top-1 equals main's top-1 from position t+1 (not t+2), protocol bug (H-D).")
print("  - If MTP is fine pre-prefill but falls apart post, cache-write is wrong.")
