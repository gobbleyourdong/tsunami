#!/usr/bin/env python3
"""DPO training for Tsunami E4B — teach contrastive tool-call boundaries.

DPO teaches "do A, NOT B" by training on (prompt, chosen, rejected) triples.
This targets behaviors that resist SFT: ER05, HF09, T01-T04.

Usage:
  python -u training/train_dpo.py \
    --base-model models/gemma-4-e4b-tsunami-v89-merged \
    --data workspace/training_data/dpo_pairs.jsonl \
    --output models/gemma-4-e4b-tsunami-v89-dpo \
    --epochs 3 --merge

Data format (JSONL, each line):
  {"prompt": "<full chat template text up to model turn>",
   "chosen": "<model turn with correct tool call>",
   "rejected": "<model turn with wrong tool call>"}
"""
import argparse
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("train_dpo")

parser = argparse.ArgumentParser()
parser.add_argument("--base-model", required=True, help="Path to SFT model (merged HF weights)")
parser.add_argument("--data", required=True, help="JSONL with prompt/chosen/rejected fields")
parser.add_argument("--output", default="models/gemma-4-e4b-tsunami-dpo")
parser.add_argument("--epochs", type=int, default=3)
parser.add_argument("--lr", type=float, default=5e-6, help="DPO uses much lower LR than SFT")
parser.add_argument("--lora-r", type=int, default=8)
parser.add_argument("--lora-alpha", type=int, default=None, help="Default: 2*r")
parser.add_argument("--beta", type=float, default=0.1, help="DPO beta (KL penalty strength)")
parser.add_argument("--max-len", type=int, default=4096, help="Shorter than SFT — DPO pairs are single-turn")
parser.add_argument("--batch", type=int, default=1)
parser.add_argument("--grad-accum", type=int, default=4)
parser.add_argument("--merge", action="store_true")
parser.add_argument("--run-name", default="tsunami_dpo")
args = parser.parse_args()

# ==========================================
# LOAD MODEL
# ==========================================
from unsloth import FastLanguageModel

lora_alpha = args.lora_alpha if args.lora_alpha else args.lora_r * 2

log.info(f"Loading {args.base_model} (LoRA r={args.lora_r}, alpha={lora_alpha})...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=args.base_model,
    max_seq_length=args.max_len,
    dtype=None,
    load_in_4bit=False,
)

log.info("Applying LoRA for DPO...")
model = FastLanguageModel.get_peft_model(
    model,
    r=args.lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=0.05,  # regularization for small DPO datasets
    bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth",
    random_state=3407,
)

trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
total = sum(p.numel() for p in model.parameters())
log.info(f"Trainable: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

# Extract tokenizer from processor if needed
if hasattr(tokenizer, 'tokenizer'):
    processor = tokenizer
    tokenizer = processor.tokenizer
    log.info("Extracted tokenizer from Gemma4Processor")

# ==========================================
# LOAD DPO DATA
# ==========================================
data = []
with open(args.data) as f:
    for line in f:
        ex = json.loads(line)
        assert "prompt" in ex and "chosen" in ex and "rejected" in ex, \
            f"DPO data must have prompt/chosen/rejected fields: {list(ex.keys())}"
        data.append(ex)

log.info(f"Loaded {len(data)} DPO pairs from {args.data}")

from datasets import Dataset
dataset = Dataset.from_list(data)

# ==========================================
# DPO TRAINING
# ==========================================
# Patch: TRL 0.24 imports mergekit/llm_blender/weave in callback chain.
# These optional deps conflict with our container. Use a meta-path finder
# that intercepts any import of these packages and returns stubs.
import types
import sys
import importlib.abc
import importlib.machinery

_STUB_PKGS = {'mergekit', 'llm_blender', 'weave'}

class _Stub(types.ModuleType):
    def __getattr__(self, name):
        return _Stub(f"{self.__name__}.{name}")
    def __call__(self, *a, **kw):
        return None
    def __bool__(self):
        return False
    def __iter__(self):
        return iter([])

class _StubFinder(importlib.abc.MetaPathFinder):
    def find_module(self, fullname, path=None):
        top = fullname.split('.')[0]
        if top in _STUB_PKGS:
            return self
        return None
    def load_module(self, fullname):
        if fullname in sys.modules:
            return sys.modules[fullname]
        m = _Stub(fullname)
        m.__path__ = [f"/tmp/stub/{fullname}"]
        m.__file__ = f"<stub:{fullname}>"
        m.__loader__ = self
        m.__package__ = fullname
        sys.modules[fullname] = m
        return m

sys.meta_path.insert(0, _StubFinder())

from trl import DPOTrainer, DPOConfig

dpo_config = DPOConfig(
    output_dir=args.output,
    run_name=args.run_name,
    num_train_epochs=args.epochs,
    per_device_train_batch_size=args.batch,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr,
    lr_scheduler_type="cosine",
    warmup_steps=5,
    bf16=True,
    logging_steps=5,
    save_strategy="no",  # DPO is short, save at end
    report_to="none",
    max_grad_norm=1.0,  # less aggressive than SFT
    optim="adamw_torch_fused",
    beta=args.beta,
    max_length=args.max_len,
    max_prompt_length=args.max_len - 512,
)

# Monkey-patch: TRL DPOTrainer expects warnings_issued on the model
if not hasattr(model, 'warnings_issued'):
    model.warnings_issued = {}

trainer = DPOTrainer(
    model=model,
    args=dpo_config,
    train_dataset=dataset,
    processing_class=tokenizer,
)

log.info(f"=== DPO TRAINING ===")
log.info(f"Base model: {args.base_model}")
log.info(f"Data: {args.data} ({len(data)} pairs)")
log.info(f"Epochs: {args.epochs}, LR: {args.lr}, beta: {args.beta}")
log.info(f"LoRA r={args.lora_r}, alpha={lora_alpha}")

stats = trainer.train()
log.info(f"DPO train loss: {stats.training_loss:.4f}")

# ==========================================
# SAVE
# ==========================================
log.info(f"Saving DPO adapter to {args.output}...")
trainer.save_model(args.output)
tokenizer.save_pretrained(args.output)

if args.merge:
    merged_dir = args.output + "-merged"
    log.info(f"Merging DPO LoRA into base model -> {merged_dir}...")
    model.save_pretrained_merged(
        merged_dir,
        tokenizer,
        save_method="merged_16bit",
    )
    try:
        from transformers import AutoProcessor
        proc = AutoProcessor.from_pretrained(args.base_model, trust_remote_code=True)
        proc.save_pretrained(merged_dir)
        log.info(f"Saved processor to {merged_dir}")
    except Exception as e:
        log.warning(f"Could not save processor: {e}")
    log.info(f"Done! Merged DPO weights at {merged_dir}/")

if not args.merge:
    log.info("Done! DPO adapter saved. Use --merge for full HF weights.")
