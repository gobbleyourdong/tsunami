# Unsloth Gemma 4 TEXT SFT Recipe — Manifest

> **Source**: `~/Downloads/gemma4_(e4b)_text.py` (Unsloth's official
> Gemma 4 E4B TEXT Conversational notebook)
> **Supersedes**: the vision notebook manifest (wrong for our use case;
> our dataset has no image columns).
> **Purpose**: structured index of every variable from the source notebook.
> Port training code by consulting this manifest, not memory.

## Rule of engagement (M5 from sigma operator_gap)

Before porting any hyperparameter or API pattern from Unsloth's notebook:
1. Find the relevant section in the notebook.
2. Add its vars to the table below with `type`, `value`, `line`.
3. Only then write the corresponding line in `train.py`.

When Unsloth updates the notebook, re-extract. Diff this manifest vs the new
one — the delta is exactly what we need to change in `train.py`.

## Model load — `FastModel.from_pretrained` (line 79-86)

| var | type | value | notes |
|---|---|---|---|
| wrapper class | class | `FastModel` | **NOT FastLanguageModel, NOT FastVisionModel**. FastModel handles text and vision in one wrapper. |
| `model_name` | str | `"unsloth/gemma-4-E4B-it"` | we use `"google/gemma-4-e4b-it"` (equivalent) |
| `dtype` | None | `None` | auto-detect |
| `max_seq_length` | int | `1024` | ⚠️ notebook uses 1024, SHORTER than vision's 2048. Our tool-call examples median 1591 tokens → need to bump. |
| `load_in_4bit` | bool | `True` | |
| `full_finetuning` | bool | `False` | Unsloth added full-FT option; we want LoRA only |

## Chat template — `unsloth.chat_templates.get_chat_template` (line 201-205)

| var | type | value | notes |
|---|---|---|---|
| import path | module | `unsloth.chat_templates.get_chat_template` | **NOT from unsloth directly.** |
| `chat_template` | str | `"gemma-4"` | supports: zephyr, chatml, mistral, llama, alpaca, vicuna, phi3/4, llama3, qwen2.5, gemma3, gemma-4 |
| when applied | — | BEFORE dataset map + BEFORE inference | apply twice in a session if you reload tokenizer |

## Data prep — `standardize_data_formats` + `formatting_prompts_func` (line 214-228)

| var | type | value | notes |
|---|---|---|---|
| `standardize_data_formats(dataset)` | module | `unsloth.chat_templates.standardize_data_formats` | converts ShareGPT / chatml / raw to standard `conversations` format |
| expected column | str | `"conversations"` | list of `[{"role": "user/assistant", "content": "..."}]` per row |
| formatting fn | fn | renders via `tokenizer.apply_chat_template(convo, tokenize=False, add_generation_prompt=False).removeprefix('<bos>')` | `<bos>` stripped because processor adds it back |
| final column | str | `"text"` | what SFTConfig's `dataset_text_field` points at |

## LoRA config — `FastModel.get_peft_model` (line 174-186)

| var | type | value | notes |
|---|---|---|---|
| `finetune_vision_layers` | bool | `False` | text-only, OFF |
| `finetune_language_layers` | bool | `True` | ON |
| `finetune_attention_modules` | bool | `True` | ON (good for GRPO per comment) |
| `finetune_mlp_modules` | bool | `True` | ON (always) |
| `r` | int | **`8`** | ⚠️ **8, NOT 32.** Vision notebook used 32; text uses 8. |
| `lora_alpha` | int | **`8`** | ⚠️ **equal to r (8, not 32).** |
| `lora_dropout` | int | `0` | |
| `bias` | str | `"none"` | |
| `random_state` | int | `3407` | |
| `target_modules` | — | NOT SPECIFIED | notebook omits; FastModel defaults to all linear language layers |

## SFTConfig — `SFTConfig` (line 245-259)

| var | type | value | notes |
|---|---|---|---|
| `dataset_text_field` | str | `"text"` | |
| `per_device_train_batch_size` | int | `1` | |
| `gradient_accumulation_steps` | int | `4` | |
| `warmup_steps` | int | **`5`** | ⚠️ fixed steps, NOT warmup_ratio. Vision used 0.03 ratio. |
| `max_steps` | int | `60` | quick iter; set `num_train_epochs=1` for full |
| `learning_rate` | float | `2e-4` | "Reduce to 2e-5 for long training runs" |
| `logging_steps` | int | `1` | tight feedback |
| `optim` | str | `"adamw_8bit"` | |
| `weight_decay` | float | `0.001` | |
| `lr_scheduler_type` | str | **`"linear"`** | ⚠️ **LINEAR, not cosine.** Vision used cosine. |
| `seed` | int | `3407` | |
| `report_to` | str | `"none"` | |

**Notable absences vs vision config:** no `max_grad_norm`, no `warmup_ratio`,
no `max_length`, no `remove_unused_columns`, no `dataset_kwargs`. Text uses
the SFTTrainer defaults for those.

## Response-only loss masking — `train_on_responses_only` (line 264-269)

| var | type | value | notes |
|---|---|---|---|
| import path | module | `unsloth.chat_templates.train_on_responses_only` | **THE CRITICAL MISSING PIECE.** Without this, gradient flows on user tokens too, diluting tool-call signal. |
| `instruction_part` | str | `"<\|turn>user\n"` | EXACT match, chat template specific |
| `response_part` | str | `"<\|turn>model\n"` | EXACT match |
| how it works | — | wraps the trainer to set `labels = -100` on user/system turns, so only assistant outputs contribute to loss |

## Inference settings

| var | type | value | notes |
|---|---|---|---|
| `temperature` | float | `1.0` | Gemma 4 recommended |
| `top_p` | float | `0.95` | |
| `top_k` | int | `64` | |
| `add_generation_prompt` | bool | `True` | required for generation |

## Save paths

| method | saves | files |
|---|---|---|
| `model.save_pretrained("gemma_4_lora")` | LoRA adapters only | adapter_config.json, adapter_model.safetensors |
| `model.save_pretrained_merged("gemma-4-finetune", tokenizer)` | 16-bit merged weights | model.safetensors + tokenizer |
| `model.save_pretrained_gguf(..., quantization_method="Q8_0")` | GGUF | single .gguf file |

## Critical deltas from vision notebook → text notebook

These are the things we got WRONG when we ported from the vision notebook:

1. **r/alpha 32→8**: text uses smaller LoRA. Matches the "r small → less overfit" intuition.
2. **cosine→linear** LR scheduler. Simpler, expected to be more stable on short runs.
3. **warmup_ratio=0.03 → warmup_steps=5**: fixed warmup in text.
4. **NO `train_on_responses_only`** in vision → text adds it as the critical instruction-masking wrapper.
5. **`get_chat_template` from `unsloth.chat_templates`** (text) vs from `unsloth` directly (vision).
6. **`max_seq_length=1024`** (text) vs `2048` (vision). Our examples exceed both — need to bump to 2048 or 4096 for safety.
7. **`FastModel`** class instead of `FastVisionModel` / `FastLanguageModel`.

## Traps avoided this extraction (M4 shape-before-operate applied)

- Verified `r`, `lora_alpha` are both `int` not float or str.
- Verified `lr_scheduler_type` is `str` — value `"linear"` (would have assumed cosine from vision notebook).
- Verified `train_on_responses_only` is NOT in SFTConfig — it's a *trainer wrapper*, applied after trainer construction.
- Verified `target_modules` is NOT specified in `get_peft_model` for FastModel+text — default is applied. (Vision specified `"all-linear"` explicitly.)
