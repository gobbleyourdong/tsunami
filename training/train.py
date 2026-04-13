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

# Unsloth import-time compat check hard-fails on the container's torchvision 0.25
# (newer torch wants >=0.26). We've verified the old torchvision works — skip the
# check so `train.py` just runs. Must be set BEFORE unsloth is imported below.
os.environ.setdefault("UNSLOTH_SKIP_TORCHVISION_CHECK", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("UNSLOTH_DISABLE_STATISTICS", "1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train")

# ==========================================
# CONFIG
# ==========================================
parser = argparse.ArgumentParser()
parser.add_argument("--data", default="workspace/training_data/champion.jsonl")
parser.add_argument("--output", default="models/tsunami-adapter-textv2")
# SCALED recipe (default): longer train, more capacity, lower LR.
# Notebook quick-iter values: --epochs 3 --lr 2e-4 --lora-r 8 --max-steps 60
parser.add_argument("--epochs", type=int, default=10)
parser.add_argument("--max-steps", type=int, default=None,
                    help="Cap total optimizer steps. Unsloth notebook uses 60 for quick iteration.")
parser.add_argument("--lr", type=float, default=2e-5,
                    help="Scaled default 2e-5 per Unsloth 'reduce to 2e-5 for long training runs'. Quick-iter: 2e-4.")
parser.add_argument("--lora-r", type=int, default=32,
                    help="LoRA rank. Scaled default 32. Notebook quick-iter: 8.")
parser.add_argument("--lora-alpha", type=int, default=None,
                    help="LoRA alpha (default: r, matching Unsloth notebook — alpha==r ratio preserved).")
parser.add_argument("--lora-dropout", type=float, default=0.0, help="LoRA dropout (try 0.05)")
parser.add_argument("--target-modules", default="all-linear",
                    help="LoRA target modules. Unsloth recommends 'all-linear' (default) or a comma list.")
parser.add_argument("--warmup-ratio", type=float, default=0.03,
                    help="Cosine warmup ratio. Unsloth notebook default 0.03.")
parser.add_argument("--base-model", default="google/gemma-4-e4b-it", help="Base model path or HF name")
parser.add_argument("--max-len", type=int, default=2048,
                    help="Max sequence length. Unsloth notebook: 2048.")
parser.add_argument("--batch", type=int, default=1)
parser.add_argument("--grad-accum", type=int, default=4,
                    help="Gradient accumulation. Unsloth notebook: 4.")
parser.add_argument("--gguf", default=None, help="(deprecated, ignored)")
parser.add_argument("--merge", action="store_true", help="Merge LoRA into base and save full HF weights")
parser.add_argument("--load-in-4bit", action="store_true", help="Load base model in 4-bit (for large models like 31B)")
parser.add_argument("--run-name", default="tsunami_unsloth")
args = parser.parse_args()

# ==========================================
# LOAD MODEL WITH UNSLOTH — TEXT notebook recipe
# Source: ~/Downloads/gemma4_(e4b)_text.py  (see UNSLOTH_RECIPE.md)
# ==========================================
from unsloth import FastModel

lora_alpha = args.lora_alpha if args.lora_alpha else args.lora_r  # NOTEBOOK: alpha == r
log.info(f"Loading {args.base_model} — Unsloth TEXT recipe (r={args.lora_r}, alpha={lora_alpha})")

model, tokenizer = FastModel.from_pretrained(
    model_name=args.base_model,
    dtype=None,                               # NOTEBOOK: None (auto-detect)
    max_seq_length=args.max_len,              # NOTEBOOK: 1024; we bump for our long prompts
    load_in_4bit=True,                        # NOTEBOOK: True
    full_finetuning=False,                    # NOTEBOOK: False (LoRA, not full FT)
)

# NOTEBOOK ORDER: get_peft_model FIRST (line 174), then get_chat_template (line 201).
log.info("Applying LoRA per Unsloth TEXT recipe...")
model = FastModel.get_peft_model(
    model,
    finetune_vision_layers=False,     # NOTEBOOK: False (text-only SFT; keep vision frozen)
    finetune_language_layers=True,    # NOTEBOOK: True
    finetune_attention_modules=True,  # NOTEBOOK: True
    finetune_mlp_modules=True,        # NOTEBOOK: True
    r=args.lora_r,                    # NOTEBOOK: 8
    lora_alpha=lora_alpha,            # NOTEBOOK: 8 (== r)
    lora_dropout=0,                   # NOTEBOOK: 0
    bias="none",                      # NOTEBOOK: "none"
    random_state=3407,                # NOTEBOOK: 3407
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# NOTEBOOK line 201: get_chat_template AFTER get_peft_model.
# IMPORTANT: returned object is a Gemma4Processor (multimodal). Notebook keeps the
# whole processor and passes it to SFTTrainer as `tokenizer=processor`. We do NOT
# extract the inner tokenizer — that breaks multimodal-aware tokenization in TRL.
from unsloth.chat_templates import get_chat_template
tokenizer = get_chat_template(tokenizer, chat_template="gemma-4")

# ==========================================
# LOAD DATA
# Supports two input formats:
#   1. Legacy: {"text": "<pre-rendered chat template>"}
#   2. Unsloth-style: {"messages": [{"role":"user","content":"..."}, ...]}
#      — we render via unsloth.get_chat_template at train time.
# ==========================================
data = []
has_messages = False
with open(args.data) as f:
    for line in f:
        ex = json.loads(line)
        if "messages" in ex:
            has_messages = True
            data.append({"messages": ex["messages"]})
        elif "text" in ex:
            # NOTEBOOK: .removeprefix('<bos>') — processor adds <bos> back at tokenize time;
            # leaving it in pre-rendered text causes double-bos.
            data.append({"text": ex["text"].removeprefix("<bos>")})

log.info(f"Loaded {len(data)} examples from {args.data} "
         f"(format: {'messages' if has_messages else 'text'})")

from datasets import Dataset
dataset = Dataset.from_list(data)

# If the dataset is structured (messages), render via the already-patched processor.
# Mirror notebook formatting_prompts_func (line 223-226): apply_chat_template + removeprefix('<bos>').
if has_messages:
    def _render(ex):
        text = tokenizer.apply_chat_template(
            ex["messages"], tools=None, tokenize=False, add_generation_prompt=False
        ).removeprefix("<bos>")
        return {"text": text}
    dataset = dataset.map(_render, remove_columns=["messages"])
    log.info(f"Rendered {len(dataset)} messages → text via gemma-4 template")

# ==========================================
# TRAINING
# ==========================================
from trl import SFTTrainer, SFTConfig

# SFTConfig — replicate the Unsloth notebook verbatim.
# Source: ~/Downloads/copy_of_gemma4_(e4b)_vision.py SFTConfig block.
# SFTConfig — TEXT notebook verbatim (UNSLOTH_RECIPE.md):
sft_config_kwargs = dict(
    dataset_text_field="text",                       # NOTEBOOK: "text" (locked)
    per_device_train_batch_size=args.batch,          # NOTEBOOK: 1 (locked — effective batch 4)
    gradient_accumulation_steps=args.grad_accum,     # NOTEBOOK: 4 (locked)
    learning_rate=args.lr,                           # NOTEBOOK: 2e-4 quick-iter / 2e-5 long run
    logging_steps=1,                                 # NOTEBOOK: 1
    optim="adamw_8bit",                              # NOTEBOOK: "adamw_8bit" (locked)
    weight_decay=0.001,                              # NOTEBOOK: 0.001 (locked)
    seed=3407,                                       # NOTEBOOK: 3407 (locked)
    report_to="none",                                # NOTEBOOK: "none"
    output_dir=args.output,
    run_name=args.run_name,
    save_strategy="no",  # only final save via trainer.save_model() — no mid-run checkpoints
)
# Quick-iter mode (max_steps): linear scheduler + fixed warmup_steps=5, matching notebook.
# Scaled mode (epochs): cosine scheduler + warmup_ratio, so warmup scales with total steps.
if args.max_steps:
    sft_config_kwargs["max_steps"] = args.max_steps
    sft_config_kwargs["warmup_steps"] = 5              # NOTEBOOK quick-iter
    sft_config_kwargs["lr_scheduler_type"] = "linear"  # NOTEBOOK quick-iter
else:
    sft_config_kwargs["num_train_epochs"] = args.epochs
    sft_config_kwargs["warmup_ratio"] = args.warmup_ratio  # scales with run length
    sft_config_kwargs["lr_scheduler_type"] = "cosine"      # smoother tail on long runs
sft_config = SFTConfig(**sft_config_kwargs)

trainer = SFTTrainer(
    model=model,
    args=sft_config,
    train_dataset=dataset,
    processing_class=tokenizer,
)

# NOTEBOOK: train_on_responses_only — masks user/system turns so loss flows only on
# assistant outputs. This is the critical missing piece per UNSLOTH_RECIPE.md.
from unsloth.chat_templates import train_on_responses_only
trainer = train_on_responses_only(
    trainer,
    instruction_part="<|turn>user\n",
    response_part="<|turn>model\n",
)
log.info("Wrapped trainer with unsloth train_on_responses_only (instruction=<|turn>user, response=<|turn>model)")

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
