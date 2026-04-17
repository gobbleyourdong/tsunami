#!/usr/bin/env python3
"""MTP benchmark with attn_implementation="eager" on main — tests whether
collapsing the cache/no-cache attention-kernel distinction (per iter-32 drift
finding) lifts accept rate. If greedy jumps materially above the 9% baseline,
the cached-vs-uncached hidden drift IS the root cause and a kernel fix is
warranted. If accept stays at 9%, the gap is elsewhere.

Requires free GPU. Slow (~5-10× main-forward cost under eager vs SDPA)."""
import sys, time
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

from transformers import AutoConfig, AutoProcessor, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head, generate_with_mtp
from serve_qwen36_fp8 import (
    _load_fused_from_cache, _fuse_cache_path, _build_fused_state_dict,
)

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)

print("loading main with attn_implementation='eager' …")
cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
# Force eager attention — should use the same code path for prefill and
# decode, eliminating the cached/uncached hidden drift flagged by iter-32.
cfg.text_config._attn_implementation = "eager"
cfg._attn_implementation = "eager"

cache = _fuse_cache_path(SNAP, Path.home() / ".cache" / "sigma_fuse")
if cache.exists():
    print(f"using fused cache {cache.name}")
    sd = _load_fused_from_cache(cache, device="cuda:0")
else:
    sd = _build_fused_state_dict(SNAP)
main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd, dtype="auto",
    device_map="cuda:0", trust_remote_code=True,
    attn_implementation="eager",
)
sd = None; torch.cuda.empty_cache()
print(f"main loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")
print(f"attn_impl resolved: {getattr(main.config, '_attn_implementation', '?')}")

print("loading MTP head…")
mtp = load_mtp_head(SNAP, cfg.text_config, main, cfg.quantization_config, device="cuda:0")
torch.cuda.empty_cache()
print(f"MTP loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

proc = AutoProcessor.from_pretrained(MID, trust_remote_code=True)
msgs = [{"role": "user", "content": [{"type": "text", "text": "Count 1 to 40, one per line."}]}]
inputs = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                   return_dict=True, return_tensors="pt").to("cuda:0")
inputs = {k: v for k, v in inputs.items() if k in ("input_ids", "attention_mask")}
eos = set(main.generation_config.eos_token_id or []) if isinstance(main.generation_config.eos_token_id, list) else {main.generation_config.eos_token_id}

print("--- plain generate (eager baseline) ---")
for i in ("warm", 1, 2):
    t = time.time()
    with torch.no_grad():
        out = main.generate(**inputs, max_new_tokens=128, do_sample=False, use_cache=True)
    dt = time.time() - t
    new = out.shape[1] - inputs["input_ids"].shape[1]
    print(f"  {i}: {new} tok / {dt:.2f}s = {new/dt:.1f} tok/s")

print("--- MTP generate (eager attention) ---")
for temp_label, temp in (("greedy", 0.0), ("sample", 0.7)):
    print(f"  [temperature={temp}]")
    for i in ("warm", 1, 2):
        t = time.time()
        gen, stats = generate_with_mtp(
            main, mtp,
            input_ids=inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            max_new_tokens=128,
            eos_token_ids=eos,
            temperature=temp, top_p=0.95, top_k=64,
        )
        dt = time.time() - t
        new = gen.shape[1]
        print(f"    {temp_label} {i}: {new} tok / {dt:.2f}s = {new/dt:.1f} tok/s  "
              f"(steps={stats['steps']} accepts={stats['accepts']} "
              f"rate={stats['accepts']/max(1,stats['steps']):.0%})")
