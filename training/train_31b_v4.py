#!/usr/bin/env python3
"""Train 31B v4 — BOS fix + Unsloth train_on_responses_only (matching Kaggle notebook)."""
import argparse, json, logging, torch
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_31b_v4")

parser = argparse.ArgumentParser()
parser.add_argument("--data", default="workspace/training_data/31b_toolcall_train_v4.jsonl")
parser.add_argument("--output", default="models/gemma-4-31b-tsunami-v4")
parser.add_argument("--epochs", type=int, default=10)
parser.add_argument("--lr", type=float, default=2e-5)  # 10x lower for 31B
parser.add_argument("--lora-r", type=int, default=8)
parser.add_argument("--max-len", type=int, default=8192)
parser.add_argument("--grad-accum", type=int, default=4)
parser.add_argument("--merge", action="store_true", help="Merge LoRA into base and save full weights")
parser.add_argument("--data-format", choices=["raw", "strip-bos"], default="raw")
args = parser.parse_args()

from unsloth import FastModel

log.info(f"Loading gemma-4-31B-it with FastModel (LoRA r={args.lora_r})...")
model, tokenizer = FastModel.from_pretrained(
    model_name="google/gemma-4-31B-it",
    max_seq_length=args.max_len,
    load_in_4bit=True,  # 31B BF16 OOMs on 128GB Spark
    full_finetuning=False,
)

log.info("Applying LoRA via FastModel...")
model = FastModel.get_peft_model(
    model,
    finetune_vision_layers=False,
    finetune_language_layers=True,
    finetune_attention_modules=True,
    finetune_mlp_modules=True,
    r=args.lora_r,
    lora_alpha=args.lora_r * 2,  # alpha=2r convention
    lora_dropout=0.05,  # regularization for small dataset
    bias="none",
    random_state=3407,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# Extract tokenizer from processor if needed
if hasattr(tokenizer, "tokenizer"):
    processor = tokenizer
    tokenizer = processor.tokenizer
    log.info("Extracted tokenizer from processor")

data = []
with open(args.data) as f:
    for line in f:
        data.append({"text": json.loads(line)["text"]})
log.info(f"Loaded {len(data)} examples")

from datasets import Dataset
dataset = Dataset.from_list(data)

from trl import SFTTrainer, SFTConfig
sft_config = SFTConfig(
    output_dir=args.output,
    num_train_epochs=args.epochs,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr,
    lr_scheduler_type="linear",
    warmup_steps=5,
    bf16=True,
    logging_steps=5,
    save_strategy="steps",
    save_steps=50,
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

# Use Unsloth's built-in response masking (matches Kaggle notebook)
from unsloth.chat_templates import train_on_responses_only
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|turn>user\n",
    response_part="<|turn>model\n",
)
log.info("Using Unsloth train_on_responses_only masking")

log.info(f"=== 31B v4 TRAINING ===")
log.info(f"Data: {args.data} ({len(data)} examples)")
log.info(f"Epochs: {args.epochs}, LR: {args.lr}, LoRA r={args.lora_r}")

stats = trainer.train()
log.info(f"Train loss: {stats.training_loss:.4f}")

log.info(f"Saving adapter to {args.output}...")
trainer.save_model(args.output)
tokenizer.save_pretrained(args.output)

if args.merge:
    merged_dir = args.output + "-merged"
    log.info(f"Merging LoRA into base model -> {merged_dir}...")
    model.save_pretrained_merged(merged_dir, tokenizer, save_method="merged_16bit")
    try:
        from transformers import AutoProcessor
        proc = AutoProcessor.from_pretrained("google/gemma-4-31B-it", trust_remote_code=True)
        proc.save_pretrained(merged_dir)
        log.info(f"Saved processor to {merged_dir}")
    except Exception as e:
        log.warning(f"Could not save processor: {e}")
    log.info(f"Done! Merged weights at {merged_dir}/")
else:
    log.info("DONE (adapter only, use --merge for full weights)")
