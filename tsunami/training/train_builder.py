"""Train the 2B builder model on Tsunami scaffold-filling data.

Designed to run inside Docker container nvcr.io/nvidia/pytorch:25.11-py3
which has the correct PyTorch + CUDA for DGX Spark (GB10 Blackwell).

Usage:
  docker run --gpus all -d --ipc=host \
    -v /home/jb/ComfyUI/CelebV-HQ/ark:/workspace \
    -w /workspace \
    nvcr.io/nvidia/pytorch:25.11-py3 \
    bash -c "pip install transformers peft trl datasets -q && \
             python -u tsunami/training/train_builder.py \
             --data workspace/training_data/builder_sharegpt_train.jsonl \
             --model Qwen/Qwen2.5-Coder-3B-Instruct \
             --output /workspace/models/tsunami-builder-v1"

Or on Vast.ai:
  python train_builder.py \
    --data builder_sharegpt_train.jsonl \
    --model Qwen/Qwen2.5-Coder-3B-Instruct \
    --output ./tsunami-builder-v1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger("train_builder")


def load_sharegpt_data(path: str) -> list[dict]:
    """Load ShareGPT format training data."""
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
    """Format a single example for SFT training.

    Uses Qwen's chat template for consistency with inference.
    """
    messages = [
        {"role": "system", "content": "You are a TypeScript/React expert building apps with the Tsunami framework. Write clean, compilable code using the design system CSS variables. Include all imports."},
        {"role": "user", "content": example["instruction"]},
        {"role": "assistant", "content": example["output"]},
    ]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}


def main():
    parser = argparse.ArgumentParser(description="Train Tsunami builder model")
    parser.add_argument("--data", type=str, required=True, help="Path to builder_sharegpt_train.jsonl")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-Coder-3B-Instruct", help="Base model")
    parser.add_argument("--output", type=str, default="./tsunami-builder-v1", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=4, help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--max-seq-len", type=int, default=4096, help="Max sequence length")
    parser.add_argument("--dry-run", action="store_true", help="Just validate data, don't train")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    # Validate data
    log.info(f"Loading data from {args.data}")
    raw_data = load_sharegpt_data(args.data)
    log.info(f"Loaded {len(raw_data)} examples")

    if args.dry_run:
        # Just print stats
        lengths = [len(d["instruction"]) + len(d["output"]) for d in raw_data]
        log.info(f"Avg chars: {sum(lengths)//len(lengths)}")
        log.info(f"Max chars: {max(lengths)}")
        log.info(f"Min chars: {min(lengths)}")
        log.info("Dry run complete — data looks good")
        return

    # Import training libraries (only available in Docker)
    try:
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
        from peft import LoraConfig, get_peft_model
        from trl import SFTTrainer
        from datasets import Dataset
    except ImportError as e:
        log.error(f"Missing dependency: {e}")
        log.error("Run inside Docker: nvcr.io/nvidia/pytorch:25.11-py3")
        log.error("pip install transformers peft trl datasets")
        sys.exit(1)

    # Check GPU
    if torch.cuda.is_available():
        log.info(f"GPU: {torch.cuda.get_device_name(0)}")
        log.info(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}GB")
    else:
        log.warning("No GPU detected — training will be slow")

    # Load tokenizer and model
    log.info(f"Loading model: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    # LoRA config
    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # Format data
    log.info("Formatting training data...")
    formatted = [format_for_training(d, tokenizer) for d in raw_data]
    dataset = Dataset.from_list(formatted)

    # Training arguments
    # Training config
    from trl import SFTConfig
    total_steps = (len(dataset) // (args.batch_size * args.grad_accum)) * args.epochs
    warmup_steps = max(1, int(total_steps * 0.05))
    sft_config = SFTConfig(
        output_dir=args.output,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        lr_scheduler_type="cosine",
        warmup_steps=warmup_steps,
        bf16=True,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
        max_grad_norm=0.3,
        optim="adamw_torch",
        weight_decay=0.01,
        max_length=args.max_seq_len,
        dataset_text_field="text",
    )
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=dataset,
        processing_class=tokenizer,
    )

    # Train
    log.info("Starting training...")
    trainer.train()

    # Save
    log.info(f"Saving to {args.output}")
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    log.info("Training complete!")


if __name__ == "__main__":
    main()
