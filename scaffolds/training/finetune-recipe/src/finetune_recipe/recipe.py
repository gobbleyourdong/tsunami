"""The actual training loop. ML deps are imported lazily so a canary
can import this module and inspect the callable without needing
torch/transformers installed.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .config import RecipeConfig


log = logging.getLogger("finetune_recipe.recipe")


_ML_MISSING = (
    "ML dependencies not installed. Install with:\n"
    "    pip install -e '.[ml]'\n"
    "Or individually: torch, transformers, peft, accelerate, datasets"
)


def _require_ml() -> None:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import datasets  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(_ML_MISSING) from exc


def train(cfg: RecipeConfig) -> None:
    """Run the recipe. Imports ML deps only when called, not at import time."""
    _require_ml()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    log.info(f"loading tokenizer + model: {cfg.model.name}")
    dtype = {
        "float16":  torch.float16,
        "bfloat16": torch.bfloat16,
        "float32":  torch.float32,
    }[cfg.model.dtype]

    tokenizer = AutoTokenizer.from_pretrained(
        cfg.model.name, trust_remote_code=cfg.model.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict = {
        "trust_remote_code": cfg.model.trust_remote_code,
        "torch_dtype": dtype,
    }
    if cfg.model.quantize_4bit:
        try:
            from transformers import BitsAndBytesConfig
            model_kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=dtype,
                bnb_4bit_quant_type="nf4",
            )
        except ImportError as exc:
            raise RuntimeError(
                "quantize_4bit=true but bitsandbytes is not installed",
            ) from exc

    model = AutoModelForCausalLM.from_pretrained(cfg.model.name, **model_kwargs)

    target_modules: object
    if cfg.lora.target == "all-linear":
        target_modules = "all-linear"
    else:
        target_modules = [s.strip() for s in cfg.lora.target.split(",") if s.strip()]

    lora_cfg = LoraConfig(
        r=cfg.lora.r,
        lora_alpha=cfg.lora.alpha,
        lora_dropout=cfg.lora.dropout,
        target_modules=target_modules,  # type: ignore[arg-type]
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)

    log.info(f"loading dataset: {cfg.data.path}")
    if Path(cfg.data.path).is_file():
        ds = load_dataset("json", data_files=cfg.data.path, split="train")
    else:
        ds = load_dataset(cfg.data.path, split="train")

    def tokenize(row: dict) -> dict:
        prompt = row[cfg.data.prompt_field]
        response = row[cfg.data.response_field]
        full = prompt + response
        out = tokenizer(full, truncation=True, max_length=cfg.data.max_seq_len)
        out["labels"] = out["input_ids"].copy()
        return out

    ds = ds.map(tokenize, remove_columns=ds.column_names)

    args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.train.epochs,
        max_steps=cfg.train.max_steps,
        per_device_train_batch_size=cfg.train.batch_size,
        gradient_accumulation_steps=cfg.train.grad_accum,
        learning_rate=cfg.train.lr,
        warmup_ratio=cfg.train.warmup_ratio,
        weight_decay=cfg.train.weight_decay,
        logging_steps=cfg.train.log_steps,
        save_steps=cfg.train.save_steps,
        seed=cfg.train.seed,
        bf16=dtype is torch.bfloat16,
        fp16=dtype is torch.float16,
        report_to="none",
    )

    trainer = Trainer(model=model, args=args, train_dataset=ds, tokenizer=tokenizer)
    trainer.train()
    trainer.save_model(cfg.output_dir)
    log.info(f"saved to {cfg.output_dir}")
