#!/usr/bin/env python3
"""E2B LoRA fine-tune on curated tool-call dataset (v3).

Same config will be used for E4B — only the base model path changes.
"""
import json, logging, torch
import torch.nn as nn
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# ==========================================
# CONFIG — identical for E2B and E4B
# ==========================================
BASE_MODEL = "models/gemma-4-e2b-it"
DATA_PATH = "workspace/training_data/e4b_toolcall_train_v2.jsonl"
OUTPUT_DIR = "models/gemma-4-e2b-toolcall-v3"
RUN_NAME = "e2b_v3"

NUM_EPOCHS = 5
BATCH_SIZE = 1
GRAD_ACCUM = 8        # effective batch = 8
LR = 1e-4
MAX_LENGTH = 16384     # 99% of examples fit, stable on GB10
LORA_R = 32
LORA_ALPHA = 64
LORA_DROPOUT = 0.05
MAX_GRAD_NORM = 0.3
WARMUP_STEPS = 20
SAVE_STRATEGY = "epoch"

# ==========================================
# LOAD DATA
# ==========================================
data = []
with open(DATA_PATH) as f:
    for line in f:
        data.append(json.loads(line))
log.info(f"Loaded {len(data)} examples from {DATA_PATH}")

# ==========================================
# LOAD MODEL
# ==========================================
log.info(f"Loading {BASE_MODEL}...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL, dtype=torch.bfloat16, device_map="auto", trust_remote_code=True
)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Unwrap ClippableLinear if present (Gemma 4 quirk)
log.info("Unwrapping ClippableLinear...")
unwrapped = 0
for name, module in list(model.named_modules()):
    if type(module).__name__ == "Gemma4ClippableLinear" and hasattr(module, "linear"):
        parts = name.rsplit(".", 1)
        if len(parts) == 2:
            parent = dict(model.named_modules())[parts[0]]
            setattr(parent, parts[1], module.linear)
            unwrapped += 1
log.info(f"Unwrapped {unwrapped} layers")

# ==========================================
# GRADIENT CHECKPOINTING + LoRA
# ==========================================
model.gradient_checkpointing_enable()

lora_config = LoraConfig(
    r=LORA_R,
    lora_alpha=LORA_ALPHA,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_dropout=LORA_DROPOUT,
    bias="none",
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_config)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# ==========================================
# DATASET
# ==========================================
dataset = Dataset.from_list(data)

# ==========================================
# TRAINING CONFIG
# ==========================================
sft_config = SFTConfig(
    output_dir=OUTPUT_DIR,
    run_name=RUN_NAME,
    num_train_epochs=NUM_EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    lr_scheduler_type="cosine",
    warmup_steps=WARMUP_STEPS,
    bf16=True,
    logging_steps=10,
    save_strategy=SAVE_STRATEGY,
    report_to="none",
    max_grad_norm=MAX_GRAD_NORM,
    optim="adamw_torch",
    weight_decay=0.01,
    max_length=MAX_LENGTH,
    dataset_text_field="text",
)

# ==========================================
# TRAIN
# ==========================================
trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset,
    processing_class=tokenizer,
)

log.info(f"Training {NUM_EPOCHS} epochs, r={LORA_R}, {len(data)} examples, max_len={MAX_LENGTH}")
log.info(f"Effective batch: {BATCH_SIZE * GRAD_ACCUM}, LR: {LR}, output: {OUTPUT_DIR}")
trainer.train()

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
log.info(f"Done! Model saved to {OUTPUT_DIR}")
