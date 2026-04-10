"""QAT + Distillation — train Gemma 4 31B to be ternary.

TWO-PHASE approach to avoid OOM on unified memory:

Phase A: Teacher generates logits (one model in memory)
  - Load fp16 teacher
  - Run calibration data through it
  - Save teacher logits to disk
  - Unload teacher, free memory

Phase B: Student trains against saved logits (one model in memory)
  - Load student with ternary STE wrappers
  - Train against saved teacher logits
  - Checkpoint to host volume every N steps
  - Never loads teacher again

Usage:
    python -u tsunami/ternary/train_qat.py \
        --model models/gemma-4-31B-it \
        --output models/gemma-4-31B-ternary-qat \
        --steps 5000
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import math
import os
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

log = logging.getLogger("train_qat")


# ========== Straight-Through Ternary ==========

class StraightThroughTernary(torch.autograd.Function):
    """Quantize to ternary in forward, pass gradients straight through."""

    @staticmethod
    def forward(ctx, weight, scale):
        w_norm = weight / scale.clamp(min=1e-8)
        ternary = torch.clamp(torch.round(w_norm), -1, 1)
        return ternary * scale

    @staticmethod
    def backward(ctx, grad_output):
        return grad_output, None


def ternary_forward(weight):
    """Apply ternary quantization with STE."""
    scale = weight.abs().mean()
    return StraightThroughTernary.apply(weight, scale)


class TernaryWrapper(nn.Module):
    """Wraps a Linear layer to use ternary weights in forward pass."""

    def __init__(self, linear: nn.Linear):
        super().__init__()
        self.weight = linear.weight
        self.bias = linear.bias

    def forward(self, x):
        w_ternary = ternary_forward(self.weight)
        return F.linear(x, w_ternary, self.bias)


# ========== Calibration Data ==========

CALIBRATION_TEXTS = [
    "Build a React counter component with increment and decrement buttons using useState.",
    "Write a TypeScript interface for a User with name, email, and optional avatar fields.",
    "Create a dashboard layout with a sidebar navigation and main content area.",
    "Implement a search function that filters an array of objects by a query string.",
    "Build a weather app that displays temperature, humidity, and a 5-day forecast chart.",
    "Write CSS for a dark theme with glassmorphism cards and a blue accent color.",
    "Create a REST API endpoint that handles CRUD operations for a todo list.",
    "Implement drag and drop functionality for a kanban board with multiple columns.",
    "Build a form with validation for email, password, and confirm password fields.",
    "Write a custom React hook called useLocalStorage that persists state.",
    "Create a responsive navigation bar that collapses into a hamburger menu on mobile.",
    "Build a data table with sorting, filtering, and pagination.",
    "Write a WebSocket client that reconnects automatically on disconnect.",
    "Create an audio player component with play, pause, volume, and progress bar.",
    "Build a markdown editor with live preview side by side.",
    "Write a function that converts CSV text into a sorted HTML table.",
    "Create a timer component with start, stop, reset, and lap functionality.",
    "Build a chart component using SVG that displays bar, line, and pie charts.",
    "Create a file upload component with drag and drop, progress bar, and preview.",
    "Build a quiz game with multiple choice questions, score tracking, and timer.",
    "Create a calendar component with month navigation, event markers, and date selection.",
    "Implement keyboard shortcuts for an application with a command palette.",
    "Build a multi-step wizard form with validation at each step.",
    "Create a photo gallery with masonry layout, lightbox, and category filters.",
    "What is the capital of France?",
    "Explain how a neural network learns through backpropagation.",
    "Write a Python function to find the longest common subsequence of two strings.",
    "How does garbage collection work in JavaScript?",
    "Describe the difference between TCP and UDP protocols.",
    "What are the SOLID principles in object-oriented programming?",
    "Explain the CAP theorem in distributed systems.",
    "How does Reacts virtual DOM diffing algorithm work?",
]


def make_batches(tokenizer, texts, batch_size=2, max_len=256):
    """Create training batches from calibration texts."""
    batches = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        messages_batch = [[{"role": "user", "content": t}] for t in batch_texts]
        formatted = [
            tokenizer.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
            for m in messages_batch
        ]
        encoded = tokenizer(
            formatted, return_tensors="pt", padding=True,
            truncation=True, max_length=max_len,
        )
        batches.append(encoded)
    return batches


# ========== Phase A: Generate teacher logits ==========

def phase_a_teacher_logits(model_path: str, output_dir: str, batch_size: int, max_len: int):
    """Load teacher, generate logits for all calibration data, save to disk, unload."""
    from transformers import AutoTokenizer, AutoModelForCausalLM

    log.info("=== Phase A: Generating teacher logits ===")

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    log.info("Loading teacher (bf16)...")
    teacher = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16,
        device_map="cpu", trust_remote_code=True,
    )
    teacher.eval()
    log.info(f"Teacher loaded: {sum(p.numel() for p in teacher.parameters())/1e9:.1f}B params")

    batches = make_batches(tokenizer, CALIBRATION_TEXTS, batch_size=batch_size, max_len=max_len)
    logits_dir = Path(output_dir) / "teacher_logits"
    logits_dir.mkdir(parents=True, exist_ok=True)

    log.info(f"Running {len(batches)} batches through teacher...")
    for i, batch in enumerate(batches):
        with torch.no_grad():
            out = teacher(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"])
            # Save logits as bf16 to save space
            torch.save({
                "logits": out.logits.to(torch.bfloat16),
                "input_ids": batch["input_ids"],
                "attention_mask": batch["attention_mask"],
            }, logits_dir / f"batch_{i:04d}.pt")
        log.info(f"  Batch {i+1}/{len(batches)} done")

    # Save tokenizer for student phase
    tokenizer.save_pretrained(Path(output_dir) / "tokenizer")

    # Unload teacher completely
    del teacher
    gc.collect()
    torch.cuda.empty_cache() if torch.cuda.is_available() else None
    log.info("Teacher unloaded. Memory freed.")
    log.info(f"Teacher logits saved to {logits_dir}")


# ========== Phase B: Train student ==========

def phase_b_train_student(model_path: str, output_dir: str, args):
    """Load student with ternary wrappers, train against saved teacher logits."""
    from transformers import AutoTokenizer, AutoModelForCausalLM

    log.info("=== Phase B: Training student with ternary STE ===")

    tokenizer = AutoTokenizer.from_pretrained(
        Path(output_dir) / "tokenizer", trust_remote_code=True
    )

    log.info("Loading student (bf16, GPU)...")
    student = AutoModelForCausalLM.from_pretrained(
        model_path, dtype=torch.bfloat16,
        device_map="auto", trust_remote_code=True,
    )
    # Gradient checkpointing — trades compute for memory (~40% less VRAM)
    if hasattr(student, 'gradient_checkpointing_enable'):
        student.gradient_checkpointing_enable()
        log.info("Gradient checkpointing enabled")

    # Wrap linear layers with ternary STE
    wrapped = 0
    skip_patterns = ["embed", "lm_head", "norm", "vision", "layernorm"]
    for name, module in list(student.named_modules()):
        if isinstance(module, nn.Linear):
            if any(skip in name.lower() for skip in skip_patterns):
                continue
            parts = name.rsplit(".", 1)
            if len(parts) == 2:
                parent = dict(student.named_modules())[parts[0]]
                wrapper = TernaryWrapper(module)
                setattr(parent, parts[1], wrapper)
                wrapped += 1

    log.info(f"Wrapped {wrapped} linear layers with ternary STE")

    # Load teacher logits from disk
    logits_dir = Path(output_dir) / "teacher_logits"
    logit_files = sorted(logits_dir.glob("batch_*.pt"))
    log.info(f"Loaded {len(logit_files)} teacher logit batches from disk")

    # Optimizer
    trainable_params = [p for p in student.parameters() if p.requires_grad]
    log.info(f"Trainable: {sum(p.numel() for p in trainable_params)/1e9:.2f}B params")
    optimizer = torch.optim.AdamW(trainable_params, lr=args.lr, weight_decay=0.01)

    # LR schedule
    def lr_lambda(step):
        if step < args.warmup_steps:
            return step / max(args.warmup_steps, 1)
        progress = (step - args.warmup_steps) / max(args.steps - args.warmup_steps, 1)
        return 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # Checkpoint dir
    ckpt_dir = Path(output_dir)
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    # Training loop
    log.info(f"Starting training: {args.steps} steps")
    student.train()
    total_loss = 0
    batch_idx = 0

    for step in range(1, args.steps + 1):
        # Load next teacher logit batch from disk
        logit_file = logit_files[batch_idx % len(logit_files)]
        batch_idx += 1
        saved = torch.load(logit_file, map_location="cpu", weights_only=False)
        device = next(student.parameters()).device
        teacher_logits = saved["logits"].to(device)
        input_ids = saved["input_ids"].to(device)
        attention_mask = saved["attention_mask"].to(device)

        # Student forward (mm_token_type_ids=0 for text-only, required by Gemma 4)
        mm_token_type_ids = torch.zeros_like(input_ids)
        student_out = student(
            input_ids=input_ids, attention_mask=attention_mask,
            mm_token_type_ids=mm_token_type_ids,
        )
        student_logits = student_out.logits

        # KL divergence loss
        T = args.temperature
        teacher_probs = F.softmax(teacher_logits.float() / T, dim=-1)
        student_log_probs = F.log_softmax(student_logits.float() / T, dim=-1)
        kl_loss = F.kl_div(student_log_probs, teacher_probs, reduction="batchmean") * (T * T)

        # CE loss
        labels = input_ids[:, 1:].contiguous()
        shift_logits = student_logits[:, :-1, :].contiguous()
        ce_loss = F.cross_entropy(
            shift_logits.reshape(-1, shift_logits.size(-1)),
            labels.reshape(-1),
            ignore_index=tokenizer.pad_token_id or -100,
        )

        loss = args.alpha_kl * kl_loss + args.alpha_ce * ce_loss

        loss.backward()
        torch.nn.utils.clip_grad_norm_(trainable_params, args.max_grad_norm)
        optimizer.step()
        scheduler.step()
        optimizer.zero_grad()

        total_loss += loss.item()

        # Logging
        if step % args.log_every == 0:
            avg = total_loss / args.log_every
            lr = scheduler.get_last_lr()[0]
            log.info(f"Step {step}/{args.steps} | loss={avg:.4f} kl={kl_loss.item():.4f} ce={ce_loss.item():.4f} lr={lr:.2e}")
            total_loss = 0

        # Checkpoint (saves to host volume — survives docker death)
        if step % args.checkpoint_every == 0:
            ckpt_path = ckpt_dir / f"checkpoint-{step}"
            ckpt_path.mkdir(exist_ok=True)
            torch.save({
                "step": step,
                "model_state_dict": student.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "loss": loss.item(),
            }, ckpt_path / "training_state.pt")
            log.info(f"Checkpoint: {ckpt_path}")

        # Memory cleanup
        del student_out, student_logits, teacher_logits, teacher_probs
        del student_log_probs, kl_loss, ce_loss, loss, saved
        if step % 100 == 0:
            gc.collect()

    # Final save
    log.info("Saving final model...")
    final_path = ckpt_dir / "final"
    final_path.mkdir(exist_ok=True)
    student.save_pretrained(final_path / "model")
    tokenizer.save_pretrained(final_path / "model")
    log.info(f"Done! Final model: {final_path / 'model'}")


# ========== Main ==========

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="models/gemma-4-31B-it")
    parser.add_argument("--output", type=str, default="models/gemma-4-31B-ternary-qat")
    parser.add_argument("--steps", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--lr", type=float, default=1e-5)
    parser.add_argument("--warmup-steps", type=int, default=200)
    parser.add_argument("--temperature", type=float, default=2.0)
    parser.add_argument("--alpha-kl", type=float, default=0.7)
    parser.add_argument("--alpha-ce", type=float, default=0.3)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--checkpoint-every", type=int, default=500)
    parser.add_argument("--phase", type=str, default="both", choices=["a", "b", "both"])
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    log.info("=== Ternary QAT + Distillation ===")
    log.info(f"Model: {args.model}")
    log.info(f"Steps: {args.steps}, LR: {args.lr}, Temp: {args.temperature}")
    log.info(f"Checkpoints every {args.checkpoint_every} steps to {args.output}")

    if args.phase in ("a", "both"):
        phase_a_teacher_logits(args.model, args.output, args.batch_size, args.max_len)

    if args.phase in ("b", "both"):
        phase_b_train_student(args.model, args.output, args)


if __name__ == "__main__":
    main()
