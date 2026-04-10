#!/usr/bin/env python3
"""E4B LoRA fine-tune — THWOMP CONFIG for 8x RTX PRO 6000 Blackwell (1.5TB VRAM).

Same dataset + hyperparams as E2B. FSDP across 8 GPUs.
With 1.5TB we can go full bf16 at 8192 seq length, no QLoRA needed.

Launch:
  accelerate launch --num_processes 8 training/train_e4b_v3.py

Or single GPU (fits in 188GB easily):
  python -u training/train_e4b_v3.py
"""
import json, logging, torch, os
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

from transformers import AutoModelForCausalLM, AutoTokenizer, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# ==========================================
# CONFIG — identical to E2B except model + seq length
# ==========================================
BASE_MODEL = "google/gemma-4-e4b-it"     # download from HF (or local path)
DATA_PATH = "workspace/training_data/e4b_toolcall_train_v21.jsonl"
OUTPUT_DIR = "models/gemma-4-e4b-toolcall-v21"
RUN_NAME = "e4b_v3_v21"

NUM_EPOCHS = 3
BATCH_SIZE = 1          # 1.5TB — go big
GRAD_ACCUM = 16          # effective batch = 16
LR = 5e-5
MAX_LENGTH = 16384      # covers 100% of examples, zero truncation
LORA_R = 64
LORA_ALPHA = 128
LORA_DROPOUT = 0.0
MAX_GRAD_NORM = 0.3
WARMUP_STEPS = 20
SAVE_STEPS = 30

# Gemma 4 native turn markers
INSTRUCTION_MARKER = "<|turn>user\n"
RESPONSE_MARKER = "<|turn>model\n"

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
log.info(f"Loading {BASE_MODEL} bf16...")
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# Unwrap ClippableLinear (Gemma 4 quirk)
log.info("Unwrapping ClippableLinear...")
unwrapped = 0
for name, module in list(model.named_modules()):
    if type(module).__name__ == "Gemma4ClippableLinear" and hasattr(module, "linear"):
        parts = name.rsplit(".", 1)
        if len(parts) == 2:
            parent = dict(model.named_modules())[parts[0]]
            setattr(parent, parts[1], module.linear)
            unwrapped += 1
log.info(f"Unwrapped {unwrapped} ClippableLinear layers")

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
# RESPONSE-ONLY DATA COLLATOR
# ==========================================
_inst_ids = tokenizer.encode(INSTRUCTION_MARKER, add_special_tokens=False)
_resp_ids = tokenizer.encode(RESPONSE_MARKER, add_special_tokens=False)
log.info(f"Instruction marker IDs ({len(_inst_ids)}): {_inst_ids}")
log.info(f"Response marker IDs ({len(_resp_ids)}): {_resp_ids}")

IGNORE_INDEX = -100

class ResponseOnlyCollator(DataCollatorForLanguageModeling):
    """Loss only on model response tokens. Everything else masked."""

    def __call__(self, features, return_tensors=None):
        batch = super().__call__(features, return_tensors=return_tensors)

        for i in range(len(batch["labels"])):
            input_ids = batch["input_ids"][i]
            labels = batch["labels"][i].clone()
            masked = torch.full_like(labels, IGNORE_INDEX)

            input_list = input_ids.tolist()
            in_response = False
            j = 0
            while j < len(input_list):
                if input_list[j:j+len(_resp_ids)] == _resp_ids:
                    in_response = True
                    j += len(_resp_ids)
                    continue
                if input_list[j:j+len(_inst_ids)] == _inst_ids:
                    in_response = False
                    j += len(_inst_ids)
                    continue
                if in_response and labels[j] != IGNORE_INDEX:
                    masked[j] = labels[j]
                j += 1

            batch["labels"][i] = masked

        return batch

collator = ResponseOnlyCollator(tokenizer=tokenizer, mlm=False)
log.info("Response-only masking: loss on <|turn>model tokens only")

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
    save_strategy="steps",
    save_steps=SAVE_STEPS,
    report_to="none",
    max_grad_norm=MAX_GRAD_NORM,
    optim="adamw_torch_fused",
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
    data_collator=collator,
)

log.info(f"=== E4B THWOMP ===")
log.info(f"Model: {BASE_MODEL}")
log.info(f"Epochs: {NUM_EPOCHS}, LR: {LR}, LoRA r={LORA_R}, max_len={MAX_LENGTH}")
log.info(f"Effective batch: {BATCH_SIZE * GRAD_ACCUM}, optimizer: adamw_torch_fused")
log.info(f"Response-only masking, bf16, gradient checkpointing")
log.info(f"Save every {SAVE_STEPS} steps → {OUTPUT_DIR}")

trainer_stats = trainer.train()

trainer.save_model(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)

log.info(f"Done! Train loss: {trainer_stats.training_loss:.4f}")
log.info(f"Model saved to {OUTPUT_DIR}")
log.info(f"Checkpoints at: {OUTPUT_DIR}/checkpoint-*/")
