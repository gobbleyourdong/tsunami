#!/usr/bin/env python3
"""Debug: run MTP standalone after main's prefill. Skip verify — just sample
straight from MTP's logits. If MTP was trained correctly, tokens should be
coherent English. If garbage, weight-loading / contract is off."""
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

from transformers import AutoConfig, AutoProcessor, Qwen3_5MoeForConditionalGeneration, DynamicCache
from mtp_module import load_mtp_head, mtp_prefill
from serve_qwen36_fp8 import _build_fused_state_dict

MID = "Qwen/Qwen3.6-35B-A3B-FP8"
SNAP = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)

cfg = AutoConfig.from_pretrained(MID, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size
sd = _build_fused_state_dict(SNAP)
main = Qwen3_5MoeForConditionalGeneration.from_pretrained(
    None, config=cfg, state_dict=sd, dtype="auto", device_map="cuda:0", trust_remote_code=True)
sd = None; torch.cuda.empty_cache()
mtp = load_mtp_head(SNAP, cfg.text_config, main, cfg.quantization_config, device="cuda:0")
proc = AutoProcessor.from_pretrained(MID, trust_remote_code=True)

msgs = [{"role": "user", "content": [{"type": "text", "text": "Count 1 to 10, one per line."}]}]
inp = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                return_dict=True, return_tensors="pt").to("cuda:0")
inp = {k: v for k, v in inp.items() if k in ("input_ids", "attention_mask")}

with torch.no_grad():
    out = main(**inp, output_hidden_states=True, use_cache=True)

# Try both hidden-state selections: pre-norm ([-2]) and post-norm ([-1])
for label, idx in (("pre-norm [-2]", -2), ("post-norm [-1]", -1)):
    last_hidden = out.hidden_states[idx]
    # Prefill MTP
    mtp_cache = mtp_prefill(last_hidden, inp["input_ids"], mtp)
    # Sample next token from main for MTP's embed input
    next_tok = out.logits[:, -1, :].argmax(dim=-1, keepdim=True)
    # Greedy-sample 10 tokens straight from MTP
    gen_tokens = []
    cur_tok = next_tok
    cur_hidden = last_hidden
    for step in range(10):
        pos = torch.tensor([[mtp_cache.get_seq_length()]], device="cuda:0")
        logits = mtp(hidden_from_main=cur_hidden, next_token_ids=cur_tok,
                     position_ids=pos, past_key_values=mtp_cache)
        nxt = logits[:, -1, :].argmax(dim=-1, keepdim=True)
        gen_tokens.append(nxt.item())
        cur_tok = nxt
        # No fresh main hidden for next step — reuse the same last_hidden
        # (this won't be accurate but at least shows if MTP produces sane tokens)
    decoded = proc.tokenizer.decode(gen_tokens)
    print(f"{label}: {gen_tokens[:8]}")
    print(f"  decoded: {decoded!r}")
