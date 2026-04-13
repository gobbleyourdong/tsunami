# Unsloth Gemma 4 Recipe — Manifest

> **Source**: `~/Downloads/copy_of_gemma4_(e4b)_vision.py` (Unsloth's official
> Gemma 4 E4B Vision notebook, Colab export 2026-04-13)
> **Purpose**: structured index of every variable from the source notebook.
> Port training code by consulting this manifest, not memory.

## Rule of engagement

Before porting any hyperparameter or API pattern from Unsloth's notebook:
1. Find the relevant section in the notebook.
2. Add its vars to the table below with `type`, `value`, `line`.
3. Only then write the corresponding line in `train.py`.

When Unsloth updates the notebook, re-extract. Diff this manifest vs the new
one — the delta is exactly what we need to change in `train.py`.

## Model load — `FastVisionModel.from_pretrained` (notebook line 76-80)

| var | type | value | notes |
|---|---|---|---|
| `model_name` | str | `"unsloth/gemma-4-E4B-it"` | we use `"google/gemma-4-e4b-it"` (works equivalently) |
| `load_in_4bit` | bool | `True` | memory saver; we keep True |
| `use_gradient_checkpointing` | str | `"unsloth"` | Unsloth's optimization |

## LoRA config — `FastVisionModel.get_peft_model` (notebook line 87-102)

| var | type | value | notes |
|---|---|---|---|
| `finetune_vision_layers` | bool | `True` | vision-only; skip for text SFT |
| `finetune_language_layers` | bool | `True` | vision-only; skip for text SFT |
| `finetune_attention_modules` | bool | `True` | vision-only; skip for text SFT |
| `finetune_mlp_modules` | bool | `True` | vision-only; skip for text SFT |
| `r` | int | `32` | LoRA rank |
| `lora_alpha` | int | `32` | == r (NOT 2r) |
| `lora_dropout` | int | `0` | ∈ {0, 0.05} |
| `bias` | str | `"none"` | |
| `random_state` | int | `3407` | reproducibility seed |
| `use_rslora` | bool | `False` | rank-stabilized LoRA off |
| `loftq_config` | None | `None` | LoftQ off |
| `target_modules` | **str** | `"all-linear"` | ⚠️ **STRING, not list**. When serialized by Unsloth, expands to a long regex: `(?:.*?(?:vision\|image\|visual\|patch\|language\|text).*?(?:self_attn\|...)...)`. Downstream code that iterates must check `isinstance(tm, (list, str))` first. |

## Data / chat template — notebook line 111-182

| var | type | value | notes |
|---|---|---|---|
| `dataset` | HF Dataset | `load_dataset("unsloth/LaTeX_OCR", split="train")` | vision-specific; we use our jsonl |
| `processor` | AutoProcessor | `get_chat_template(processor, "gemma-4")` | **unsloth.get_chat_template patches the tokenizer** |
| example shape | dict | `{"messages": [{"role":"user","content":[{"type":"text","text":...},{"type":"image",...}]}, {"role":"assistant","content":[{"type":"text","text":...}]}]}` | vision shape; our text-only `messages` drops `{"type":"image"}` blocks |

## SFTConfig — notebook line 221-249

| var | type | value | notes |
|---|---|---|---|
| `per_device_train_batch_size` | int | `1` | |
| `gradient_accumulation_steps` | int | `4` | |
| `max_grad_norm` | float | `0.3` | gradient clipping |
| `warmup_ratio` | float | `0.03` | cosine warmup |
| `max_steps` | int | `60` | quick iter; use `num_train_epochs` for full |
| `learning_rate` | float | `2e-4` | |
| `logging_steps` | int | `1` | tight feedback |
| `save_strategy` | str | `"steps"` | |
| `optim` | str | `"adamw_8bit"` | not `adamw_torch_fused` |
| `weight_decay` | float | `0.001` | |
| `lr_scheduler_type` | str | `"cosine"` | |
| `seed` | int | `3407` | |
| `output_dir` | str | `"outputs"` | we parameterize via `--output` |
| `report_to` | str | `"none"` | no W&B |
| `remove_unused_columns` | bool | `False` | **required for vision collator; keep for text too** |
| `dataset_text_field` | str | `""` | vision uses collator, empty; text uses `"text"` |
| `dataset_kwargs` | dict | `{"skip_prepare_dataset": True}` | **vision-specific; OMIT for text SFT** |
| `max_length` | int | `2048` | sequence cap |

## Inference (for sanity checks)

| var | type | value | notes |
|---|---|---|---|
| `temperature` | float | `1.0` | |
| `top_p` | float | `0.95` | |
| `top_k` | int | `64` | |
| `max_new_tokens` | int | `128` | per inference sample |

## Save (LoRA only, not merged)

Notebook line 313-316:
- `model.save_pretrained("gemma_4_lora")`
- `processor.save_pretrained("gemma_4_lora")`
- optional `push_to_hub` / `push_to_hub_merged`

## Traps landed tonight (for next time)

1. **`target_modules` is a STRING** for `all-linear`, **a LIST** for explicit modules. Our port script assumed list → iterated characters of the regex string → produced nonsense module names like `"a.linear", "l.linear", ..`. Fix applied: isinstance check before iterating.
2. **`dataset_text_field=""`** is vision-only (used with `UnslothVisionDataCollator`). For text SFT we need `"text"` or the trainer has nothing to read.
3. **`dataset_kwargs={"skip_prepare_dataset": True}`** is vision-only. For text SFT, omit it so SFTTrainer prepares the dataset normally.
4. **`max_length=2048`** is shorter than our legacy `max_seq_length=16384`. Large prompts (our 3KB system prompt + long tool-call traces) WILL be truncated. For tool-call SFT we might need 4096.
