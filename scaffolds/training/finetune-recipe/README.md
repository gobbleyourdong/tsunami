# training/finetune-recipe

**Pitch:** small-to-medium LoRA fine-tuning recipe on HuggingFace
transformers + peft. Config-driven (one YAML); the Python is a shim.
Baseline defaults follow Unsloth's current recipe (r=16, alpha=r,
all-linear targets) — proven against stale-prior defaults (see
`~/SIGMA_METHOD.md` v8 Priors Don't Beat Source case study).

## Quick start

```bash
# Light install — CLI surface only (no torch):
pip install -e .

# Parse the example config (no model/data download):
finetune-recipe validate config.example.yaml
# → ok — model=Qwen/Qwen2.5-0.5B-Instruct r=16 alpha=16 lr=2e-05 epochs=1

# Full install for actual training:
pip install -e '.[ml]'
finetune-recipe train config.example.yaml
```

## Config shape

| Section     | Keys                                                       |
|-------------|------------------------------------------------------------|
| `model`     | `name`, `dtype` (bfloat16/float16/float32), `quantize_4bit`, `trust_remote_code` |
| `lora`      | `r`, `alpha`, `dropout`, `target` ("all-linear" or comma list) |
| `train`     | `lr`, `epochs`, `batch_size`, `grad_accum`, `max_steps`, `warmup_ratio`, `seed`, `save_steps`, `log_steps` |
| `data`      | `path` (JSONL or HF dataset id), `prompt_field`, `response_field`, `max_seq_len` |
| `output_dir`| Where to save the adapter                                  |

## What this is NOT

- **Not** a distributed training harness. Single-GPU, single-node.
  For multi-GPU, wrap with `accelerate launch finetune-recipe train config.yaml`.
- **Not** an SFT / DPO / ORPO library — it's the common-case completion
  recipe. If you need DPO, start from `recipe.py::train` and swap the
  `Trainer` for `trl.DPOTrainer`.
- **Not** a model-merging tool. Adapter saves to `output_dir`; merge
  yourself with `peft.PeftModel.merge_and_unload()` if you need
  standalone weights.

## Customize

- **Swap the trainer** — edit `src/finetune_recipe/recipe.py::train`.
  The config → trainer wiring is ~60 LOC; most work happens in
  `trl.SFTTrainer` / `DPOTrainer` if you go that route.
- **Different data shape** — the default tokenizer is `prompt + response`
  as a single sequence with labels=input_ids (standard CLM). For
  chat-format, tokenize with `tokenizer.apply_chat_template` instead
  of the concat.
- **Mask prompt loss** — replace labels for prompt tokens with -100 if
  you only want response-token loss (the scaffold defaults to full
  sequence loss, which is simpler and often fine for small data).

## Don't

- Don't bump `r` to 64 on a 100-example dataset. The adapter will
  memorize the noise.
- Don't trust `trust_remote_code=true` from models you haven't
  audited — it executes code from the model repo at load time.
- Don't commit `output_dir/` — adapter checkpoints are tens to
  hundreds of MB. Add `runs/` to your `.gitignore`.

## Anchors

`huggingface/transformers`, `huggingface/peft`, `huggingface/accelerate`,
`huggingface/trl`, `unslothai/unsloth`, `Axolotl`, `LLaMA-Factory`.
