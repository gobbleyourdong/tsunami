#!/usr/bin/env python3
"""End-to-end MTP draft-verify test: load main model + MTP head, generate a
short continuation, compare output + wall time vs plain model.generate().

Requires a free GPU — won't co-tenant with the server on :8095."""
import sys, time
from pathlib import Path
import torch

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")

import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())

from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm
def _ds_w8a8_fp8_matmul(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    orig_shape = A.shape
    A_2d = A.reshape(-1, orig_shape[-1]).contiguous()
    As_2d = As.reshape(-1, As.shape[-1]).contiguous() if As.dim() >= 2 else As.contiguous()
    prev = torch.get_default_dtype()
    if output_dtype is not None and output_dtype != prev:
        torch.set_default_dtype(output_dtype)
    try:
        out = _ds_fp8_gemm(A_2d, As_2d, B.contiguous(), Bs.contiguous())
    finally:
        if output_dtype is not None and output_dtype != prev:
            torch.set_default_dtype(prev)
    return out.view(*orig_shape[:-1], B.shape[0])
_fgfp8.w8a8_fp8_matmul = _ds_w8a8_fp8_matmul

from transformers import AutoConfig, AutoProcessor, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head, generate_with_mtp

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)

from serve_qwen35_fp8 import _build_fused_state_dict

print("loading main model…")
cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
sd = _build_fused_state_dict(SNAP)
main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd,
    dtype="auto", device_map="cuda:0", trust_remote_code=True,
)
sd = None
torch.cuda.empty_cache()
print(f"main loaded, VRAM {torch.cuda.memory_allocated()/1e9:.2f} GB")

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

print("--- plain generate (baseline) ---")
for i in ("warm", 1, 2):
    t = time.time()
    with torch.no_grad():
        out = main.generate(**inputs, max_new_tokens=128, do_sample=False, use_cache=True)
    dt = time.time() - t
    new = out.shape[1] - inputs["input_ids"].shape[1]
    print(f"  {i}: {new} tok / {dt:.2f}s = {new/dt:.1f} tok/s")

print("--- MTP generate ---")
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
