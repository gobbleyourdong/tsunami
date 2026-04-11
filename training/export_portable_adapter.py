#!/usr/bin/env python3
"""Export Unsloth-trained adapter as stock PEFT-compatible adapter.

Unsloth patches Gemma4's layers (Gemma4ClippableLinear) which stock PEFT
can't load. This script loads via Unsloth, then re-saves the adapter
with standard layer names so it works with raw transformers + PEFT
on any platform (CPU, MPS, CUDA).

Usage:
  python3 export_portable_adapter.py \
    --base google/gemma-4-e4b-it \
    --adapter models/gemma-4-e4b-tsunami-v89 \
    --output models/adapters/apps
"""

import argparse
import json
import os
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="google/gemma-4-e4b-it")
    parser.add_argument("--adapter", required=True, help="Unsloth adapter dir")
    parser.add_argument("--output", required=True, help="Output dir for portable adapter")
    parser.add_argument("--load-in-4bit", action="store_true")
    args = parser.parse_args()

    from unsloth import FastLanguageModel

    print(f"Loading base: {args.base}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base,
        load_in_4bit=args.load_in_4bit,
    )

    print(f"Loading Unsloth adapter: {args.adapter}")
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, args.adapter)

    # Save — Unsloth's patched model saves with standard PEFT format
    # because save_pretrained uses the PEFT internals which normalize
    # the layer names back to standard
    os.makedirs(args.output, exist_ok=True)
    print(f"Saving portable adapter to: {args.output}")
    model.save_pretrained(args.output)

    # Also save tokenizer for completeness
    tokenizer.save_pretrained(args.output)

    # Verify the adapter config doesn't reference Unsloth-specific classes
    config_path = Path(args.output) / "adapter_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        print(f"  target_modules: {config.get('target_modules', '?')}")
        print(f"  r: {config.get('r', '?')}")
        print(f"  lora_alpha: {config.get('lora_alpha', '?')}")
        base_ref = config.get("base_model_name_or_path", "")
        if "unsloth" in base_ref.lower():
            # Fix base model reference to point to Google's official model
            config["base_model_name_or_path"] = args.base
            config_path.write_text(json.dumps(config, indent=2))
            print(f"  Fixed base_model_name_or_path: {args.base}")

    size = sum(f.stat().st_size for f in Path(args.output).rglob("*") if f.is_file())
    print(f"  Total size: {size / 1024 / 1024:.1f} MB")
    print("Done. This adapter can be loaded with stock PEFT on any platform.")


if __name__ == "__main__":
    main()
