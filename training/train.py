#!/usr/bin/env python3

"""Gemma 4 E4B training with Unsloth — faster, less VRAM.

Based on Unsloth's Gemma 4 recommendations:
- LoRA r=8 (not 64) — fewer params, faster
- LR 2e-4 (not 5e-5) — Unsloth recommended
- adamw_8bit optimizer — less VRAM
- gradient_checkpointing="unsloth" — their optimization

Usage:
  # Train + merge to HF weights (for serve_transformers.py):
  python -u training/train.py --merge --data workspace/training_data/e4b_toolcall_train_v80.jsonl --epochs 10 --grad-accum 4
"""
import argparse
import json
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

# ==========================================
# CONFIG
# ==========================================
parser = argparse.ArgumentParser()
parser.add_argument("--data", default="workspace/training_data/e4b_toolcall_train_v14.jsonl")
parser.add_argument("--output", default="models/gemma-4-e4b-tsunami-unsloth")
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--lr", type=float, default=2e-4)
parser.add_argument("--lora-r", type=int, default=8)
parser.add_argument("--lora-alpha", type=int, default=None, help="LoRA alpha (default: 2*r)")
parser.add_argument("--lora-dropout", type=float, default=0.0, help="LoRA dropout (try 0.05)")
parser.add_argument("--base-model", default="google/gemma-4-e4b-it", help="Base model path or HF name")
parser.add_argument("--max-len", type=int, default=16384)
parser.add_argument("--batch", type=int, default=1)
parser.add_argument("--grad-accum", type=int, default=16)
parser.add_argument("--gguf", default=None, help="(deprecated, ignored)")
parser.add_argument("--merge", action="store_true", help="Merge LoRA into base and save full HF weights")
parser.add_argument("--load-in-4bit", action="store_true", help="Load base model in 4-bit (for large models like 31B)")
parser.add_argument("--run-name", default="tsunami_unsloth")
args = parser.parse_args()

# ==========================================
# LOAD MODEL WITH UNSLOTH
# ==========================================
from unsloth import FastLanguageModel

lora_alpha = args.lora_alpha if args.lora_alpha else args.lora_r * 2
log.info(f"Loading {args.base_model} with Unsloth (LoRA r={args.lora_r}, alpha={lora_alpha}, dropout={args.lora_dropout})...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=args.base_model,
    max_seq_length=args.max_len,
    dtype=None,  # auto-detect
    load_in_4bit=args.load_in_4bit,
)

log.info("Applying LoRA...")
model = FastLanguageModel.get_peft_model(
    model,
    r=args.lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=args.lora_dropout,
    bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth",  # Unsloth's optimization
    random_state=3407,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# Unsloth returns a Processor for multimodal models — extract the tokenizer
if hasattr(tokenizer, 'tokenizer'):
    processor = tokenizer
    tokenizer = processor.tokenizer
    log.info("Extracted tokenizer from Gemma4Processor")

# ==========================================
# LOAD DATA
# ==========================================
data = []
with open(args.data) as f:
    for line in f:
        ex = json.loads(line)
        data.append({"text": ex["text"]})

log.info(f"Loaded {len(data)} examples from {args.data}")

from datasets import Dataset
dataset = Dataset.from_list(data)

# ==========================================
# RESPONSE-ONLY MASKING (custom collator, works with any TRL version)
# v69+: handles <|turn>user, <|turn>tool, <|turn>system as instruction
# markers (everything that's NOT <|turn>model). v14-v21 only handled
# <|turn>user — this fix is required for the native chat template format
# where tool responses use <|turn>tool\n role.
# ==========================================
RESPONSE_MARKER = "<|turn>model\n"
INSTRUCTION_MARKERS = [
    "<|turn>user\n",
    "<|turn>tool\n",
    "<|turn>system\n",
]

import torch
from transformers import DataCollatorForLanguageModeling

_resp_ids = tokenizer.encode(RESPONSE_MARKER, add_special_tokens=False)
_inst_ids_list = [tokenizer.encode(m, add_special_tokens=False) for m in INSTRUCTION_MARKERS]
IGNORE_INDEX = -100

class ResponseOnlyCollator(DataCollatorForLanguageModeling):
    def __call__(self, features, return_tensors=None):
        batch = super().__call__(features, return_tensors=return_tensors)
        for i in range(len(batch["labels"])):
            input_ids = batch["input_ids"][i]
            labels = batch["labels"][i]
            masked = torch.full_like(labels, IGNORE_INDEX)
            input_list = input_ids.tolist()
            in_response = False
            j = 0
            while j < len(input_list):
                # Start response on <|turn>model
                if input_list[j:j+len(_resp_ids)] == _resp_ids:
                    in_response = True
                    j += len(_resp_ids)
                    continue
                # End response on any non-model turn marker
                hit = False
                for inst_ids in _inst_ids_list:
                    if input_list[j:j+len(inst_ids)] == inst_ids:
                        in_response = False
                        j += len(inst_ids)
                        hit = True
                        break
                if hit:
                    continue
                if in_response and labels[j] != IGNORE_INDEX:
                    masked[j] = labels[j]
                j += 1
            batch["labels"][i] = masked
        return batch

collator = ResponseOnlyCollator(tokenizer=tokenizer, mlm=False)
log.info(f"Response-only masking on <|turn>model tokens (instruction markers: user, tool, system)")

# ==========================================
# TRAINING
# ==========================================
from trl import SFTTrainer, SFTConfig

sft_config = SFTConfig(
    output_dir=args.output,
    run_name=args.run_name,
    num_train_epochs=args.epochs,
    per_device_train_batch_size=args.batch,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr,
    lr_scheduler_type="cosine",
    warmup_steps=10,
    bf16=True,
    logging_steps=10,
    save_strategy="steps",
    save_steps=50,
    report_to="none",
    max_grad_norm=0.3,
    optim="adamw_torch_fused",
    weight_decay=0.001,
    max_seq_length=args.max_len,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset,
    processing_class=tokenizer,
    data_collator=collator,
)

log.info(f"=== UNSLOTH TRAINING ===")
log.info(f"Data: {args.data} ({len(data)} examples)")
log.info(f"Epochs: {args.epochs}, LR: {args.lr}, LoRA r={args.lora_r}, alpha={lora_alpha}, dropout={args.lora_dropout}")
log.info(f"Effective batch: {args.batch * args.grad_accum}")
log.info(f"Optimizer: adamw_8bit, max_len: {args.max_len}")
log.info(f"Output: {args.output}")

stats = trainer.train()
log.info(f"Train loss: {stats.training_loss:.4f}")

# ==========================================
# SAVE
# ==========================================
log.info(f"Saving LoRA adapter to {args.output}...")
trainer.save_model(args.output)
tokenizer.save_pretrained(args.output)

# Merge LoRA into base model and save full HF weights
if args.merge:
    merged_dir = args.output + "-merged"
    log.info(f"Merging LoRA into base model → {merged_dir}...")
    model.save_pretrained_merged(
        merged_dir,
        tokenizer,
        save_method="merged_16bit",
    )
    # Also save the processor (needed for vision inference with AutoProcessor)
    try:
        from transformers import AutoProcessor
        proc = AutoProcessor.from_pretrained("google/gemma-4-e4b-it", trust_remote_code=True)
        proc.save_pretrained(merged_dir)
        log.info(f"Saved processor to {merged_dir}")
    except Exception as e:
        log.warning(f"Could not save processor: {e} — copy from base model manually")
    log.info(f"Done! Merged HF weights at {merged_dir}/")

if not args.merge:
    log.info("Done! LoRA adapter saved. Use --merge for HF weights.")
