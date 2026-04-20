#!/usr/bin/env python3
"""NVFP4 W4A4 calibration + pack for Qwen3.6-35B-A3B-bf16 on GB10.

Run from the isolated quant venv (torch 2.10 + cu130 + llm-compressor):
    tsunami/serving/quant/venv_llmc/bin/python3 \
        tsunami/serving/quant/pack_nvfp4.py

Recipe follows ~/agentic_speed/tier1/nvfp4.md §1 (SPARK reference):
  * Scheme: NVFP4 W4A4
  * Ignore list: lm_head + MoE gates + embeddings + shared-expert gate
    + linear-attn layers (they have no GEMM surface worth quantizing)
  * MoE: all experts see calibration data
  * Dataset: ultrachat_200k, 256 samples × max_seq_len=2048 (middle of
    the 20-512 research range; more samples = marginally better scales
    at the cost of wall time)
  * Wall time estimate: ~90 min on GB10
  * Peak RAM: ~80-90GB (tight on 128.5GB UMA; bf16 weights resident +
    per-layer calibration activations)
  * Output: ~15GB packed safetensors at OUTPUT_DIR

Fallback knobs if OOM or wall too long:
  * NUM_SAMPLES=20 (min)     → ~10min, marginal quality drop
  * MAX_SEQ_LEN=1024         → half activation memory
  * DEVICE_MAP="auto"        → llm-compressor's per-layer streaming
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import torch
from datasets import load_dataset
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import QuantizationModifier
from transformers import AutoModelForCausalLM, AutoTokenizer

# transformers 5 removed PreTrainedModel._get_no_split_modules (used to
# exist as an accelerate-path helper). llm-compressor still calls it
# during sequential calibration pipeline. Patch it back as a thin wrapper
# over the _no_split_modules class attribute (which still exists).
from transformers.modeling_utils import PreTrainedModel as _PTM
if not hasattr(_PTM, "_get_no_split_modules"):
    def _get_no_split_modules(self, device_map):
        # Return the list of module class names that mustn't be split
        # across devices. For calibration on single-GPU this is purely
        # informational; pass through what the class declares.
        return list(getattr(self, "_no_split_modules", None) or [])
    _PTM._get_no_split_modules = _get_no_split_modules

# llm-compressor ships MoE calibration adapters keyed on the model's
# SparseMoeBlock class name: Qwen3MoeSparseMoeBlock, Qwen3NextSparseMoeBlock,
# Qwen3VLMoeTextSparseMoeBlock. Our model's block is Qwen3_5MoeSparseMoeBlock
# (not registered). Without the adapter, the fused experts.gate_up_proj +
# experts.down_proj tensors are invisible to the quantizer — we saw this
# the hard way on the first calibration run: only 1.6GB of 68GB got packed,
# the MoE expert weights (~61GB) stayed bf16.
#
# Structural check: both Qwen3_5MoeExperts and Qwen3NextExperts store
# experts as fused nn.Parameter tensors (gate_up_proj + down_proj) with
# identical shape semantics. We alias the registry entry so our block
# class name maps to the Qwen3Next calibration adapter. If the forward
# logic diverges at runtime we'll see a clean error and need a dedicated
# adapter; as of 2026-04-18 their forwards track each other closely.
from llmcompressor.modeling.moe_context import MoECalibrationModule
from llmcompressor.modeling.qwen3_next_moe import CalibrationQwen3NextSparseMoeBlock
# Registry normalizes names to lowercase-no-underscore. Qwen3_5MoeSparseMoeBlock
# → "qwen35moesparsemoeblock". Idempotent — skips if already registered.
try:
    if "qwen35moesparsemoeblock" not in MoECalibrationModule.registered_names():
        MoECalibrationModule.register_value(
            value=CalibrationQwen3NextSparseMoeBlock,
            name="Qwen3_5MoeSparseMoeBlock",
        )
except Exception as _e:
    print(f"[pack_nvfp4] MoE alias registration skipped: {_e}")


# --- Config ---
MODEL_ID = "Qwen/Qwen3.6-35B-A3B"  # bf16 master
OUTPUT_DIR = Path(__file__).parent / "Qwen3.6-35B-A3B-NVFP4"
NUM_SAMPLES = int(os.getenv("NUM_SAMPLES", "256"))
MAX_SEQ_LEN = int(os.getenv("MAX_SEQ_LEN", "2048"))
DATASET_NAME = "HuggingFaceH4/ultrachat_200k"
DEVICE_MAP = os.getenv("DEVICE_MAP", "cuda:0")  # "auto" broke under transformers 5
                                                #   (_get_no_split_modules removed); we have
                                                #   107GB free RAM, bf16 weights fit.

# --- Quantization recipe ---
# The ignore regex list below matches:
#   - lm_head                       (bf16 output projection; stays high-precision)
#   - model.embed_tokens            (input embedding lookup)
#   - .*mlp.gate$                   (MoE router gate — tiny + quantization hurts routing quality)
#   - .*shared_expert_gate$         (shared-expert gate)
#   - .*linear_attn.*               (Qwen3.6 linear-attention layers; different numerics)
# These are the standard ignore patterns from the llm-compressor NVFP4 examples.
IGNORE_PATTERNS = [
    "lm_head",
    "re:.*embed_tokens",
    "re:.*mlp\\.gate$",
    "re:.*shared_expert_gate",
    "re:.*linear_attn.*",
]

RECIPE = QuantizationModifier(
    targets="Linear",
    scheme="NVFP4",
    ignore=IGNORE_PATTERNS,
)


def main() -> int:
    t0 = time.time()
    print(f"[pack_nvfp4] torch {torch.__version__}, cuda {torch.cuda.is_available()}", flush=True)
    print(f"[pack_nvfp4] model: {MODEL_ID}", flush=True)
    print(f"[pack_nvfp4] output: {OUTPUT_DIR}", flush=True)
    print(f"[pack_nvfp4] calibration: {NUM_SAMPLES} samples × {MAX_SEQ_LEN} tokens", flush=True)

    # --- Load ---
    # device_map="auto" lets accelerate split large models across CPU+GPU for
    # calibration. On GB10 UMA that's less meaningful (unified memory) but
    # llm-compressor uses it as a trigger to stream layers instead of loading
    # everything at once.
    print(f"[pack_nvfp4] loading tokenizer + model …", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
        device_map=DEVICE_MAP,
        low_cpu_mem_usage=True,
    )
    print(f"[pack_nvfp4] model loaded in {time.time()-t0:.1f}s", flush=True)

    # Qwen3Next's calibration adapter reads `config.norm_topk_prob` but
    # Qwen3_5MoeTextConfig doesn't declare that attr. Verified via source
    # inspection: Qwen3_5MoeTopKRouter.forward always normalizes top-k
    # (router_top_value /= router_top_value.sum(...)), so True is the
    # correct default. Set on text_config (where the adapter looks).
    tc = getattr(model.config, "text_config", model.config)
    if not hasattr(tc, "norm_topk_prob"):
        tc.norm_topk_prob = True
        print("[pack_nvfp4] patched text_config.norm_topk_prob=True for MoE adapter", flush=True)

    # --- Dataset ---
    print(f"[pack_nvfp4] loading dataset {DATASET_NAME} [:{NUM_SAMPLES}] …", flush=True)
    ds = load_dataset(DATASET_NAME, split=f"train_sft[:{NUM_SAMPLES}]")

    def preprocess(example):
        msgs = example["messages"]
        text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
        return {"text": text}

    ds = ds.map(preprocess, remove_columns=[c for c in ds.column_names if c != "messages"])

    def tokenize(example):
        return tokenizer(example["text"], truncation=True, max_length=MAX_SEQ_LEN,
                         padding=False, return_tensors=None, add_special_tokens=False)

    ds = ds.map(tokenize, remove_columns=["text", "messages"])

    # --- Calibration ---
    print(f"[pack_nvfp4] starting oneshot calibration (this is the long step) …", flush=True)
    t1 = time.time()
    oneshot(
        model=model,
        dataset=ds,
        recipe=RECIPE,
        output_dir=str(OUTPUT_DIR),
        max_seq_length=MAX_SEQ_LEN,
        num_calibration_samples=NUM_SAMPLES,
        # llm-compressor tries to auto-init a processor from the model id
        # but fails on Qwen3.6's multimodal processor (Qwen2VLImageProcessor
        # lineage). Pass the tokenizer directly — it's what the Linear
        # calibration path actually uses.
        processor=tokenizer,
    )
    print(f"[pack_nvfp4] calibration done in {(time.time()-t1)/60:.1f} min", flush=True)

    print(f"[pack_nvfp4] total wall: {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"[pack_nvfp4] output: {OUTPUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
