#!/usr/bin/env python3
"""torch.profiler over a warm decode step. Tells us where the 45ms/token
actually goes — matmul vs attention vs moe vs kernel launch idle."""
import sys, time
from pathlib import Path
import torch

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")

# Mirror server's monkey patches
import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())
from vendor.deepseek_fp8_kernel import fp8_gemm as _ds_fp8_gemm
def _shim(A, B, As, Bs, block_size=None, output_dtype=torch.bfloat16):
    A2 = A.reshape(-1, A.shape[-1]).contiguous()
    As2 = As.reshape(-1, As.shape[-1]).contiguous() if As.dim()>=2 else As.contiguous()
    prev=torch.get_default_dtype()
    if output_dtype is not None and output_dtype != prev: torch.set_default_dtype(output_dtype)
    try: out=_ds_fp8_gemm(A2, As2, B.contiguous(), Bs.contiguous())
    finally:
        if output_dtype is not None and output_dtype != prev: torch.set_default_dtype(prev)
    return out.view(*A.shape[:-1], B.shape[0])
_fgfp8.w8a8_fp8_matmul = _shim

from transformers import AutoConfig, AutoProcessor, Qwen3_5MoeForConditionalGeneration
from serve_qwen36_fp8 import _build_fused_state_dict

MID="Qwen/Qwen3.6-35B-A3B-FP8"
SNAP=Path("/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/snapshots/61a5771f218894aaacf97551e24a25b866750fc2")

cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
sd = _build_fused_state_dict(SNAP)
m = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd, dtype="auto", device_map="cuda:0", trust_remote_code=True)
sd=None; torch.cuda.empty_cache()
proc = AutoProcessor.from_pretrained(MID, trust_remote_code=True)
msgs=[{"role":"user","content":[{"type":"text","text":"hi"}]}]
inp = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
  return_dict=True, return_tensors="pt", enable_thinking=False).to("cuda:0")
inp = {k:v for k,v in inp.items() if k in ("input_ids","attention_mask")}

# Warm up: run a short generate first so kernels are autotuned + caches hot
with torch.no_grad():
    _ = m.generate(**inp, max_new_tokens=16, do_sample=False, use_cache=True)

# Profile a 32-token decode
from torch.profiler import profile, ProfilerActivity
torch.cuda.synchronize()
with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
             record_shapes=False) as prof:
    with torch.no_grad():
        out = m.generate(**inp, max_new_tokens=32, do_sample=False, use_cache=True)

print(prof.key_averages().table(sort_by="self_cuda_time_total", row_limit=25))
print("---")
print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=10))
