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


# --- Config ---
MODEL_ID = "Qwen/Qwen3.6-35B-A3B"  # bf16 master
OUTPUT_DIR = Path(__file__).parent / "Qwen3.6-35B-A3B-NVFP4"
NUM_SAMPLES = int(os.getenv("NUM_SAMPLES", "256"))
MAX_SEQ_LEN = int(os.getenv("MAX_SEQ_LEN", "2048"))
DATASET_NAME = "HuggingFaceH4/ultrachat_200k"
DEVICE_MAP = os.getenv("DEVICE_MAP", "auto")  # llm-compressor handles streaming

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
    )
    print(f"[pack_nvfp4] calibration done in {(time.time()-t1)/60:.1f} min", flush=True)

    print(f"[pack_nvfp4] total wall: {(time.time()-t0)/60:.1f} min", flush=True)
    print(f"[pack_nvfp4] output: {OUTPUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
