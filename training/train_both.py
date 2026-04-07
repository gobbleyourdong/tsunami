#!/usr/bin/env python3
"""Train E2B then E4B sequentially. Fire and forget.

Usage:
  CUDA_VISIBLE_DEVICES=0 python -u training/train_both.py

Produces:
  models/gemma-4-e2b-tsunami-v3/  (full merged weights)
  models/gemma-4-e4b-tsunami-v3/  (full merged weights)
  models/gemma-4-e2b-toolcall-v3-lora/  (LoRA adapters)
  models/gemma-4-e4b-toolcall-v3-lora/  (LoRA adapters)
"""
import json, logging, torch, gc, os, time
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

from transformers import AutoModelForImageTextToText, AutoTokenizer, AutoProcessor, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model, PeftModel
from trl import SFTTrainer, SFTConfig
from datasets import Dataset

# ==========================================
# SHARED CONFIG
# ==========================================
DATA_PATH = "workspace/training_data/e4b_toolcall_train_v3.jsonl"
NUM_EPOCHS = 3
BATCH_SIZE = 1
GRAD_ACCUM = 4
LR = 5e-5
MAX_LENGTH = 8192
LORA_R = 64
LORA_ALPHA = 128
SAVE_STEPS = 30

INSTRUCTION_MARKER = "<|turn>user\n"
RESPONSE_MARKER = "<|turn>model\n"

MODELS = [
    {
        "name": "E2B",
        "base": "google/gemma-4-e2b-it",
        "lora_dir": "models/gemma4_e2b_tsunami_lora",
        "merged_dir": "models/gemma4_e2b_tsunami",
    },
    {
        "name": "E4B",
        "base": "google/gemma-4-e4b-it",
        "lora_dir": "models/gemma4_e4b_tsunami_lora",
        "merged_dir": "models/gemma4_e4b_tsunami",
    },
]

# ==========================================
# LOAD DATA
# ==========================================
data = []
with open(DATA_PATH) as f:
    for line in f:
        data.append(json.loads(line))
log.info(f"Loaded {len(data)} examples from {DATA_PATH}")
dataset = Dataset.from_list(data)

# ==========================================
# RESPONSE-ONLY COLLATOR
# ==========================================
IGNORE_INDEX = -100

def make_collator(tokenizer):
    _inst_ids = tokenizer.encode(INSTRUCTION_MARKER, add_special_tokens=False)
    _resp_ids = tokenizer.encode(RESPONSE_MARKER, add_special_tokens=False)

    class ResponseOnlyCollator(DataCollatorForLanguageModeling):
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

    return ResponseOnlyCollator(tokenizer=tokenizer, mlm=False)

# ==========================================
# TRAIN LOOP
# ==========================================
for model_cfg in MODELS:
    name = model_cfg["name"]
    start = time.time()
    log.info(f"{'='*60}")
    log.info(f"=== {name} TRAINING START ===")
    log.info(f"{'='*60}")

    # Load model with vision
    log.info(f"Loading {model_cfg['base']}...")
    model = AutoModelForImageTextToText.from_pretrained(
        model_cfg["base"], torch_dtype=torch.bfloat16,
        device_map={"":0}, trust_remote_code=True
    )
    tokenizer = AutoTokenizer.from_pretrained(model_cfg["base"], trust_remote_code=True)

    # Unwrap ClippableLinear
    unwrapped = 0
    for mod_name, module in list(model.named_modules()):
        if type(module).__name__ == "Gemma4ClippableLinear" and hasattr(module, "linear"):
            parts = mod_name.rsplit(".", 1)
            if len(parts) == 2:
                parent = dict(model.named_modules())[parts[0]]
                setattr(parent, parts[1], module.linear)
                unwrapped += 1
    log.info(f"Unwrapped {unwrapped} layers")

    # LoRA
    model.gradient_checkpointing_enable()
    lora_config = LoraConfig(
        r=LORA_R, lora_alpha=LORA_ALPHA,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                         "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    collator = make_collator(tokenizer)

    sft_config = SFTConfig(
        output_dir=model_cfg["lora_dir"],
        run_name=f"{name.lower()}_v3_thwomp",
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUM,
        learning_rate=LR, lr_scheduler_type="cosine", warmup_steps=20,
        bf16=True, logging_steps=10,
        save_strategy="steps", save_steps=SAVE_STEPS,
        report_to="none", max_grad_norm=0.3,
        optim="adamw_torch_fused", weight_decay=0.01,
        max_length=MAX_LENGTH, dataset_text_field="text",
    )

    trainer = SFTTrainer(
        model=model, args=sft_config, train_dataset=dataset,
        processing_class=tokenizer, data_collator=collator,
    )

    log.info(f"=== {name} THWOMP === r={LORA_R}, batch={BATCH_SIZE}x{GRAD_ACCUM}, max_len={MAX_LENGTH}")
    trainer_stats = trainer.train()

    # Save LoRA
    trainer.save_model(model_cfg["lora_dir"])
    tokenizer.save_pretrained(model_cfg["lora_dir"])
    log.info(f"{name} LoRA saved to {model_cfg['lora_dir']}")

    # Merge
    log.info(f"Merging {name} LoRA into base model...")
    merged = model.merge_and_unload()
    merged.save_pretrained(model_cfg["merged_dir"], max_shard_size="2GB")
    tokenizer.save_pretrained(model_cfg["merged_dir"])

    # Save processor config (needed for mmproj/vision GGUF conversion)
    processor = AutoProcessor.from_pretrained(model_cfg["base"], trust_remote_code=True)
    processor.save_pretrained(model_cfg["merged_dir"])
    log.info(f"{name} merged weights + processor saved to {model_cfg['merged_dir']}")

    elapsed = time.time() - start
    log.info(f"{name} DONE in {elapsed/60:.1f} min, loss: {trainer_stats.training_loss:.4f}")

    # Free GPU memory before next model
    del model, trainer, merged, collator
    gc.collect()
    torch.cuda.empty_cache()
    log.info(f"{name} memory freed, starting next model...")

log.info(f"{'='*60}")
log.info(f"=== TRAINING COMPLETE — CONVERTING TO GGUF ===")
log.info(f"{'='*60}")

import subprocess

for model_cfg in MODELS:
    name = model_cfg["name"]
    merged = model_cfg["merged_dir"]
    base_name = merged.split("/")[-1]

    # Convert to F16 GGUF
    f16_path = f"{merged}-f16.gguf"
    q4_path = f"{merged}-Q4_K_M.gguf"
    mmproj_path = f"{merged}-mmproj-f16.gguf"

    log.info(f"Converting {name} to GGUF...")
    subprocess.run([
        "python3", "llama.cpp/convert_hf_to_gguf.py", merged,
        "--outfile", f16_path, "--outtype", "f16"
    ], check=True)

    # Quantize to Q4_K_M
    log.info(f"Quantizing {name} to Q4_K_M...")
    subprocess.run([
        "llama.cpp/build/bin/llama-quantize", f16_path, q4_path, "Q4_K_M"
    ], check=True)

    # Generate mmproj for vision
    log.info(f"Generating {name} mmproj...")
    result = subprocess.run([
        "python3", "llama.cpp/convert_hf_to_gguf.py", merged,
        "--outfile", mmproj_path, "--mmproj"
    ], capture_output=True, text=True)
    if result.returncode == 0:
        log.info(f"{name} mmproj saved to {mmproj_path}")
    else:
        log.warning(f"{name} mmproj failed: {result.stderr[-200:]}")

    # Clean up F16 (large)
    os.remove(f16_path)
    log.info(f"{name}: {q4_path} ready")

log.info(f"{'='*60}")
log.info(f"=== ALL DONE ===")
log.info(f"E2B GGUF: {MODELS[0]['merged_dir']}-Q4_K_M.gguf")
log.info(f"E4B GGUF: {MODELS[1]['merged_dir']}-Q4_K_M.gguf")
log.info(f"{'='*60}")
