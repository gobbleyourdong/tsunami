#!/usr/bin/env python3
"""Train 26B-A4B MoE — the production model (52 tok/s on Spark).

Per Unsloth docs: MoE uses bf16 LoRA (NOT QLoRA).
  - FastVisionModel (Gemma 4 is multimodal)
  - load_in_4bit=False, load_in_16bit=True
  - Start with small ranks, scale up after stable

Usage:
  python -u training/train_a4b.py \
    --data workspace/training_data/e4b_toolcall_train_v89.jsonl \
    --epochs 3 --lr 2e-5 --merge
"""
import argparse, json, logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_a4b")

parser = argparse.ArgumentParser()
parser.add_argument("--data", required=True, help="Training JSONL (text field)")
parser.add_argument("--output", default="models/gemma-4-a4b-tsunami")
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--lr", type=float, default=2e-5)
parser.add_argument("--lora-r", type=int, default=8)
parser.add_argument("--lora-alpha", type=int, default=None, help="Default: 2*r")
parser.add_argument("--max-len", type=int, default=8192)
parser.add_argument("--grad-accum", type=int, default=4)
parser.add_argument("--merge", action="store_true")
parser.add_argument("--run-name", default="tsunami_a4b")
args = parser.parse_args()

lora_alpha = args.lora_alpha if args.lora_alpha else args.lora_r * 2

from unsloth import FastVisionModel

log.info(f"Loading gemma-4-26B-A4B-it via FastVisionModel (bf16 LoRA, r={args.lora_r}, alpha={lora_alpha})...")

# Disable flash_attn before loading — A4B head dim > 256 which FlashAttention doesn't support
import os
os.environ["ATTN_IMPLEMENTATION"] = "sdpa"

model, tokenizer = FastVisionModel.from_pretrained(
    model_name="unsloth/gemma-4-26B-A4B-it",
    max_seq_length=args.max_len,
    load_in_4bit=False,      # MoE: QLoRA not recommended per Unsloth docs
    load_in_16bit=True,      # MoE: use bf16 LoRA instead
    full_finetuning=False,
)

# Force SDPA attention if flash_attn was auto-selected
if hasattr(model.config, '_attn_implementation'):
    model.config._attn_implementation = "sdpa"

log.info("Applying LoRA...")
model = FastVisionModel.get_peft_model(
    model,
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=args.lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=0.05,
    bias="none",
    random_state=3407,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

if hasattr(tokenizer, "tokenizer"):
    processor = tokenizer
    tokenizer = processor.tokenizer
    log.info("Extracted tokenizer from processor")

data = []
with open(args.data) as f:
    for line in f:
        text = json.loads(line)["text"]
        # Strip <bos> if present (31B/A4B data convention)
        if text.startswith("<bos>"):
            text = text[5:]
        data.append({"text": text})
log.info(f"Loaded {len(data)} examples from {args.data}")

from datasets import Dataset
dataset = Dataset.from_list(data)

from trl import SFTTrainer, SFTConfig
sft_config = SFTConfig(
    output_dir=args.output,
    run_name=args.run_name,
    num_train_epochs=args.epochs,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr,
    lr_scheduler_type="cosine",
    warmup_steps=5,
    bf16=True,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
    max_grad_norm=0.3,
    optim="adamw_8bit",
    weight_decay=0.001,
    max_seq_length=args.max_len,
    dataset_text_field="text",
    seed=3407,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    args=sft_config,
)

from unsloth.chat_templates import train_on_responses_only
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|turn>user\n",
    response_part="<|turn>model\n",
)
log.info("Using Unsloth train_on_responses_only masking")

log.info(f"=== 26B-A4B TRAINING ===")
log.info(f"Data: {args.data} ({len(data)} examples)")
log.info(f"Epochs: {args.epochs}, LR: {args.lr}, LoRA r={args.lora_r}, alpha={lora_alpha}")
log.info(f"MoE bf16 LoRA (NOT QLoRA)")

stats = trainer.train()
log.info(f"Train loss: {stats.training_loss:.4f}")

log.info(f"Saving adapter to {args.output}...")
trainer.save_model(args.output)
tokenizer.save_pretrained(args.output)

if args.merge:
    merged_dir = args.output + "-merged"
    log.info(f"Merging LoRA -> {merged_dir}...")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")
    try:
        from transformers import AutoProcessor
        proc = AutoProcessor.from_pretrained("google/gemma-4-26B-A4B-it", trust_remote_code=True)
        proc.save_pretrained(merged_dir)
        log.info(f"Saved processor to {merged_dir}")
    except Exception as e:
        log.warning(f"Could not save processor: {e}")
    log.info(f"Done! Merged at {merged_dir}/")
else:
    log.info("DONE (adapter only, use --merge for full weights)")
