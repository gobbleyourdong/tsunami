"""finetune_recipe — LoRA fine-tuning scaffold.

Scope: small-to-medium causal-LM fine-tuning with LoRA adapters on
HuggingFace transformers + peft. The recipe is a thin shim — the
interesting work happens in ``config.yaml`` (model / LoRA rank /
learning rate / data paths). Swap in a different trainer class if
you need SFT / DPO / ORPO (trl_sft.py is a starting point).
"""

__version__ = "0.1.0"
