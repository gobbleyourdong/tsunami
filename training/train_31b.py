#!/usr/bin/env python3
"""Train gemma-4-31B-it (dense) with Unsloth LoRA."""
import argparse, json, logging, torch
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_31b")

parser = argparse.ArgumentParser()
parser.add_argument("--data", default="workspace/training_data/31b_toolcall_train_v1.jsonl")
parser.add_argument("--output", default="models/gemma-4-31b-tsunami-v1")
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--lr", type=float, default=2e-4)
parser.add_argument("--lora-r", type=int, default=8)
parser.add_argument("--max-len", type=int, default=8192)
parser.add_argument("--batch", type=int, default=1)
parser.add_argument("--grad-accum", type=int, default=4)
args = parser.parse_args()

from unsloth import FastLanguageModel

log.info(f"Loading gemma-4-31B-it (LoRA r={args.lora_r})...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-4-31B-it",
    max_seq_length=args.max_len,
    dtype=None,
    load_in_4bit=False,
)

log.info("Applying LoRA...")
model = FastLanguageModel.get_peft_model(
    model, r=args.lora_r, lora_alpha=args.lora_r, lora_dropout=0, bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth",
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
        data.append({"text": json.loads(line)["text"]})
log.info(f"Loaded {len(data)} examples")

from datasets import Dataset
dataset = Dataset.from_list(data)

# Response-only masking
RESPONSE_MARKER = "<|turn>model\n"
INSTRUCTION_MARKERS = ["<|turn>user\n", "<|turn>tool\n", "<|turn>system\n"]

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
                if input_list[j:j+len(_resp_ids)] == _resp_ids:
                    in_response = True; j += len(_resp_ids); continue
                hit = False
                for inst_ids in _inst_ids_list:
                    if input_list[j:j+len(inst_ids)] == inst_ids:
                        in_response = False; j += len(inst_ids); hit = True; break
                if hit: continue
                if in_response and labels[j] != IGNORE_INDEX:
                    masked[j] = labels[j]
                j += 1
            batch["labels"][i] = masked
        return batch

collator = ResponseOnlyCollator(tokenizer=tokenizer, mlm=False)

from trl import SFTTrainer, SFTConfig
sft_config = SFTConfig(
    output_dir=args.output, num_train_epochs=args.epochs,
    per_device_train_batch_size=args.batch,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr, lr_scheduler_type="cosine",
    warmup_steps=10, bf16=True, logging_steps=5,
    save_strategy="steps", save_steps=50, report_to="none",
    max_grad_norm=0.3, optim="adamw_torch_fused",
    weight_decay=0.001, max_seq_length=args.max_len,
    dataset_text_field="text",
)

trainer = SFTTrainer(
    model=model, args=sft_config, train_dataset=dataset,
    processing_class=tokenizer, data_collator=collator,
)

log.info(f"=== 31B TRAINING ===")
log.info(f"Data: {args.data} ({len(data)} examples)")
log.info(f"Epochs: {args.epochs}, LR: {args.lr}, LoRA r={args.lora_r}")

stats = trainer.train()
log.info(f"Train loss: {stats.training_loss:.4f}")

log.info(f"Saving adapter to {args.output}...")
trainer.save_model(args.output)
tokenizer.save_pretrained(args.output)
log.info("DONE")
