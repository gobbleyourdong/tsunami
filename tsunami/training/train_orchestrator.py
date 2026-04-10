"""Train the 9B orchestrator model on Tsunami planning/execution data.

The orchestrator learns:
- When to decompose complex prompts into phases
- Which scaffold to pick for a given prompt
- What tool sequence produces a passing build
- When to dispatch eddies vs write directly

Designed for Docker container nvcr.io/nvidia/pytorch:25.11-py3.

Usage:
  python train_orchestrator.py \
    --data workspace/training_data/orchestrator_sharegpt_train.jsonl \
    --model Qwen/Qwen3.5-9B \
    --output ./tsunami-orchestrator-v1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("train_orchestrator")

ORCHESTRATOR_SYSTEM = (
    "You are the Tsunami orchestrator. You receive a user's app request and "
    "produce a plan + tool call sequence that builds a working app.\n\n"
    "Available scaffolds: react-app, dashboard, data-viz, form-app, landing, "
    "fullstack, game, realtime, chrome-extension, electron-app, api-only\n\n"
    "Rules:\n"
    "1. Call project_init FIRST with the right scaffold\n"
    "2. Write types.ts before components\n"
    "3. Write components before App.tsx\n"
    "4. Run shell_exec to verify compilation\n"
    "5. Call message_result to deliver\n"
    "6. For complex prompts (3+ features), decompose into phases\n"
    "7. Never spend more than 5 iterations on research"
)


def load_data(path: str) -> list[dict]:
    """Load ShareGPT format orchestrator data."""
    data = []
    with open(path) as f:
        for line in f:
            item = json.loads(line)
            convos = item["conversations"]
            data.append({
                "instruction": convos[0]["value"],
                "output": convos[1]["value"],
            })
    return data


def format_for_training(example: dict, tokenizer) -> dict:
    """Format for SFT with orchestrator system prompt."""
    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM},
        {"role": "user", "content": example["instruction"]},
        {"role": "assistant", "content": example["output"]},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}


def main():
    parser = argparse.ArgumentParser(description="Train Tsunami orchestrator model")
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument("--model", type=str, default="Qwen/Qwen3.5-9B")
    parser.add_argument("--output", type=str, default="./tsunami-orchestrator-v1")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--max-seq-len", type=int, default=8192)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    raw_data = load_data(args.data)
    log.info(f"Loaded {len(raw_data)} orchestrator examples")

    if args.dry_run:
        lengths = [len(d["instruction"]) + len(d["output"]) for d in raw_data]
        log.info(f"Avg chars: {sum(lengths)//len(lengths)}, Max: {max(lengths)}")
        # Check scaffold distribution
        scaffolds = {}
        for d in raw_data:
            for s in ["react-app", "dashboard", "fullstack", "game", "form-app"]:
                if s in d["output"]:
                    scaffolds[s] = scaffolds.get(s, 0) + 1
        log.info(f"Scaffold mentions: {scaffolds}")
        log.info("Dry run complete")
        return

    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
        from datasets import Dataset
    except ImportError as e:
        log.error(f"Missing: {e}. Run in Docker.")
        sys.exit(1)

    log.info(f"Loading model: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16,
        device_map="auto", trust_remote_code=True,
    )

    # Smaller LoRA for 9B (less overfitting risk with 150 examples)
    lora_config = LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.1, bias="none", task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    formatted = [format_for_training(d, tokenizer) for d in raw_data]
    dataset = Dataset.from_list(formatted)

    training_args = TrainingArguments(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        bf16=True,
        logging_steps=5,
        save_strategy="epoch",
        report_to="none",
        max_grad_norm=0.3,
        optim="adamw_8bit",
        weight_decay=0.01,
    )

    trainer = SFTTrainer(
        model=model, args=training_args,
        train_dataset=dataset, tokenizer=tokenizer,
        max_seq_length=args.max_seq_len,
        dataset_text_field="text",
    )

    log.info("Starting orchestrator training...")
    trainer.train()
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    log.info("Orchestrator training complete!")


if __name__ == "__main__":
    main()
