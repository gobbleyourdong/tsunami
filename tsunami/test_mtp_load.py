#!/usr/bin/env python3
"""Smoke test: can we load the MTP head end-to-end without the main server
needing to be up? Only instantiates the sub-model (~1.2B params), verifies no
missing/unexpected keys, and runs a dummy forward."""
import sys
from pathlib import Path
import torch

sys.path.insert(0, "/home/jb/ComfyUI/CelebV-HQ/ark/tsunami")

# DeepGEMM stub (same force-Triton path as the server)
import transformers.integrations.finegrained_fp8 as _fgfp8
_fgfp8._load_deepgemm_kernel = lambda: (_ for _ in ()).throw(ImportError())

from transformers import AutoConfig, Qwen3_5MoeForConditionalGeneration
from mtp_module import load_mtp_head

mid = "Qwen/Qwen3.6-35B-A3B-FP8"
snap = Path(
    "/home/jb/.cache/huggingface/hub/models--Qwen--Qwen3.6-35B-A3B-FP8/"
    "snapshots/61a5771f218894aaacf97551e24a25b866750fc2"
)

cfg = AutoConfig.from_pretrained(mid, trust_remote_code=True)
cfg.text_config.intermediate_size = cfg.text_config.moe_intermediate_size

# Load just enough of the main model to get embed_tokens + lm_head on GPU.
# We don't need the full 35GB main to validate MTP structure.
# Build a meta-device shell, pull only embed+lm_head weights via safetensors.
print("Building model skeleton (meta) + loading embed+lm_head…")
from accelerate import init_empty_weights
with init_empty_weights():
    main = Qwen3_5MoeForConditionalGeneration(cfg)

# Move embed + lm_head to cuda and load their weights from `outside.safetensors`.
embed = main.get_input_embeddings()
lm = main.get_output_embeddings()

from safetensors import safe_open
with safe_open(str(snap / "outside.safetensors"), framework="pt", device="cuda:0") as f:
    for k in f.keys():
        if "embed_tokens" in k or k == "lm_head.weight":
            # Route by tail name.
            tail = k.rsplit(".", 1)[-1]  # weight
            if "embed_tokens" in k:
                embed.weight = torch.nn.Parameter(f.get_tensor(k), requires_grad=False)
            elif k == "lm_head.weight":
                lm.weight = torch.nn.Parameter(f.get_tensor(k), requires_grad=False)
print("embed shape:", embed.weight.shape, "lm_head shape:", lm.weight.shape)

# Build MTP head against this stub main
print("Loading MTP head…")
head = load_mtp_head(snap, cfg.text_config, main, cfg.quantization_config, device="cuda:0")
print("MTP head loaded.")

# Dummy forward
B, S, H = 1, 8, cfg.text_config.hidden_size
hidden = torch.zeros(B, S, H, device="cuda:0", dtype=torch.bfloat16)
next_tok = torch.tensor([[100]], device="cuda:0", dtype=torch.long)
pos = torch.arange(S + 1, device="cuda:0")[None].expand(B, S + 1)[:, -1:]
logits = head(hidden, next_tok, position_ids=pos)
print("forward OK — logits shape:", logits.shape)
