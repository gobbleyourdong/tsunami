"""Config schema + loader. No ML deps — safe to import in a canary.

The config is a single YAML file. Fields are deliberately flat: if
you find yourself reaching for nested structures, that's a signal
to split this scaffold into multiple recipes (SFT vs DPO vs ORPO)
rather than grow one config into a DSL.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelCfg:
    name: str
    trust_remote_code: bool = False
    dtype: str = "bfloat16"     # "float16" | "bfloat16" | "float32"
    quantize_4bit: bool = False


@dataclass
class LoRACfg:
    r: int = 16
    alpha: int = 16             # Unsloth-style; use alpha=r as the baseline
    dropout: float = 0.05
    target: str = "all-linear"  # "all-linear" or comma-separated names


@dataclass
class TrainCfg:
    lr: float = 2e-5
    epochs: int = 1
    batch_size: int = 1
    grad_accum: int = 8
    max_steps: int = -1         # -1 = compute from epochs
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    seed: int = 42
    save_steps: int = 100
    log_steps: int = 10


@dataclass
class DataCfg:
    path: str                   # JSONL / HF dataset id
    prompt_field: str = "prompt"
    response_field: str = "response"
    max_seq_len: int = 2048


@dataclass
class RecipeConfig:
    model: ModelCfg
    lora: LoRACfg = field(default_factory=LoRACfg)
    train: TrainCfg = field(default_factory=TrainCfg)
    data: DataCfg = field(default_factory=lambda: DataCfg(path=""))
    output_dir: str = "runs/default"


def load_config(path: str) -> RecipeConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    if "model" not in raw or not isinstance(raw["model"], dict):
        raise ValueError(f"{path}: missing required 'model' section")
    if "name" not in raw["model"]:
        raise ValueError(f"{path}: model.name required")

    model = ModelCfg(**raw["model"])
    lora = LoRACfg(**raw.get("lora", {}))
    train = TrainCfg(**raw.get("train", {}))
    data_raw = raw.get("data", {})
    if "path" not in data_raw:
        raise ValueError(f"{path}: data.path required (JSONL file or HF dataset id)")
    data = DataCfg(**data_raw)
    return RecipeConfig(
        model=model, lora=lora, train=train, data=data,
        output_dir=raw.get("output_dir", "runs/default"),
    )
