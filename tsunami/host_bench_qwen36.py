#!/usr/bin/env python3
"""Host-native benchmark: load Qwen3.6-35B-A3B-FP8 on GB10 without Docker.

Settles two questions at once:
  1. Does comfyui-env torch 2.10.0+cu130 (cc <= 12.0 claimed support) actually
     run this FP8 MoE correctly on GB10 (cc 12.1), or produce garbage?
  2. How fast is host-native decode vs the containered nv-torch 2.11?

Re-uses the same in-memory expert fuser as serve_qwen36_fp8.py.
"""
import os, sys, time
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

# Identical monkey-patch as the server — DeepGEMM community build crashes on
# Qwen3.5-Moe FP8 shapes; force Triton fallback.
import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")
# Mask sys.argv so the server module's early bind-probe short-circuits
# (it skips when `-h`/`--help` is present). We just want the helpers.
_saved_argv = sys.argv
sys.argv = [sys.argv[0], "--help"]
from serve_qwen36_fp8 import _resolve_snapshot_dir, _build_fused_state_dict  # noqa: E402
sys.argv = _saved_argv

import torch
from transformers import (
    AutoConfig, AutoProcessor, AutoTokenizer,
    Qwen3_5MoeForConditionalGeneration,
)

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
print(f"torch {torch.__version__}  cuda {torch.version.cuda}  "
      f"device {torch.cuda.get_device_name(0)}  cap {torch.cuda.get_device_capability(0)}")

cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
if not hasattr(cfg.text_config, "intermediate_size"):
    cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size

t0 = time.time()
snap = _resolve_snapshot_dir(MID)
sd = _build_fused_state_dict(snap)
print(f"fuse: {time.time() - t0:.1f}s  tensors={len(sd)}")

t1 = time.time()
m = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd,
    dtype="auto", device_map="cuda:0", trust_remote_code=True,
)
sd = None
torch.cuda.synchronize()
print(f"load: {time.time() - t1:.1f}s  vram={torch.cuda.memory_allocated() / 1e9:.2f} GB")

proc = AutoProcessor.from_pretrained(MID, trust_remote_code=True)
tok = AutoTokenizer.from_pretrained(MID, trust_remote_code=True)

prompt = "In one short sentence: what color is the sky on a clear day?"
msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
inp = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                               return_dict=True, return_tensors="pt").to(m.device)

# Warm-up pass (kernel autotune + mrope caches)
with torch.no_grad():
    _ = m.generate(**inp, max_new_tokens=8, do_sample=False, use_cache=True)

# Timed pass
n_new = 128
torch.cuda.synchronize()
t2 = time.time()
with torch.no_grad():
    out = m.generate(**inp, max_new_tokens=n_new, do_sample=False, use_cache=True)
torch.cuda.synchronize()
dt = time.time() - t2

new_ids = out[0][inp["input_ids"].shape[1]:]
decoded = tok.decode(new_ids, skip_special_tokens=False)
print(f"gen: {dt:.2f}s for {len(new_ids)} tok  =>  {len(new_ids) / dt:.1f} tok/s")
print("OUTPUT:")
print(decoded)
