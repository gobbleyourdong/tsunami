# Specialist Adapter Playbook

> Reusable process for building any Tsunami specialist (web builder, gamedev,
> sigma expert, etc.) from a base Gemma 4 model. Distilled from 91 app-builder
> iterations and the gamedev pivot.

## Core Principle

Every specialist is **SFT to teach the capability + DPO to teach judgment**.

SFT gets you to the behavior ceiling. DPO breaks through it. Both use LoRA on
the same base model. Neither alone reaches production quality.

---

## Phase 0 — Define the Specialist (30 min)

Write a **one-page charter** before touching data:

1. **Pipeline**: What ordered sequence of tool calls = a successful task?
   - Web builder: `project_init → file_write → shell_exec → undertow → message_result`
   - Gamedev: `project_init → file_write(main.ts) → shell_exec → undertow → message_result`
   - Sigma expert: `research → synthesize → lean_prove → results`

2. **Tools**: Enumerate the 8-15 tools the specialist uses. Core + triggers + escape hatches.
   - Core (used every task): ~5 tools
   - Triggers (conditional): ~5 tools (plan_update, search_web, message_chat, ...)
   - Escape hatches (rare but critical): ~3 tools (message_result w/ failure, undertow variants)

3. **Critical behaviors (5-10)**: The things that separate a working specialist from a broken one.
   - Gamedev example: "Write to `src/main.ts` not `src/App.tsx`", "Import from `@engine/`", "Use Canvas 2D not React"
   - Each critical behavior needs a training example AND an eval test.

4. **Scaffolds/environment**: What does the file tree look like after `project_init`?
5. **Failure modes**: 3-5 things the specialist MUST NOT do (e.g., "don't deliver stubs", "don't call `npm run build` on Vite projects").

**Output**: `training/<specialist>_charter.md`. This is the source of truth.

---

## Phase 1 — Build the Eval FIRST (2-4 hours)

You cannot optimize what you don't measure. Build the eval **before** the training data.

### Standard 5-layer structure

| Layer | Pts | Tests | What it measures |
|-------|-----|-------|------------------|
| L1 Format | 40 | 40 prompts × 1 pt | Does the model produce valid tool calls? |
| L2 Scaffold | 12 | 12 prompts × 1 pt | Does it pick the right scaffold/first tool? |
| L3 Error recovery | 100 | 6 tests × ~17 pts | Does it fix its own mistakes? |
| L4 Hack-free | 100 | 10 tests × 10 pts | Edge cases without retries (conversation, plan gate, stall, QA) |
| L5 Integration | 100 | 9 tests × ~11 pts | End-to-end real tasks build and deliver |
| **Total** | **500** | | |

### Per-layer design

- **L1**: 5 difficulty tiers × 8 prompts (trivial, easy, medium, hard, extreme). Uses **fake tool schemas** (no real execution). Pass = correct first tool.
- **L2**: One prompt per scaffold. Pass = first tool is `project_init` AND name/dependencies indicate right scaffold.
- **L3**: Force an error mid-pipeline (missing module, type error, syntax, wrong path, CSS resolution, build loop). Pass = correct fix tool with correct args.
- **L4**: 10 scenarios where a basic model retries/hallucinates. Pass = native behavior, no hack.
- **L5**: Real builds against a real scaffold, real npm install, real `npx vite build`. Pass = compiled AND delivered.

### Variants (optional)

- **L6 Vision**: Add if specialist uses images (mockup-to-code, visual debug).
- **L7 Latency**: Add if production speed matters (tok/s threshold per response).

### Eval rules

- **Target: 475+/500** for production specialist. 95% of ceiling.
- **Run 3× at temp=0.3** OR **1× at temp=0.0** for deterministic baseline.
- **Take median for volatile tests** — if a test flips across 3 runs, it's not a pass.

**Output**: `training/eval_<specialist>.py`. Reusable script.

---

## Phase 2 — Baseline SFT Data (4-6 hours)

**Size target: 30-45 examples.** Going above 50 on a 4B model hurts more than it helps.

### Distribution formula

For a specialist with N tools:

| Example type | Count | What it teaches |
|--------------|-------|-----------------|
| Happy path | 10 | Core pipeline (init → write → build → QA → deliver) |
| L3 pipeline | 6 | Error recovery with full context |
| L3 bare | 3-6 | Error recovery minimal-context (matches L3 eval format) |
| L5 integration | 3 | Full build with multiple components + error recovery |
| Trigger behaviors | 1 × (N - 5) | Search, plan, message_chat, swell, etc. |
| Tool coverage | ≥1 per tool | Every tool has at least one demo |

**Rule: no single bare example for a behavior.** Bare examples are ~200 tokens
with ~30 loss tokens — they're 7× more gradient-dense than pipeline examples.
One bare example flips a test; two bare examples of the same thing dominate
the dataset.

### Format

```python
# Use tokenizer.apply_chat_template (NOT hand-coded <bos><|turn> strings)
msgs = [
    {"role": "system", "content": SYSTEM_TEXT},
    {"role": "user", "content": user_prompt},
    {"role": "assistant", "content": "", "tool_calls": [...]},
    {"role": "tool", "name": "...", "content": "..."},
    ...
]
text = tokenizer.apply_chat_template(msgs, tools=TOOL_SCHEMAS, tokenize=False)
```

### System prompt

- Include **the pipeline** (numbered steps).
- Include **the tool glossary** (brief descriptions).
- Include **the scaffolds/components** available.
- Include **a few "NEVER" rules** (NEVER skip the break. NEVER deliver without undertow.).
- Keep total under 2000 tokens.

**Output**: `training/build_<specialist>_v1.py` → `workspace/training_data/<specialist>_toolcall_train_v1.jsonl`

---

## Phase 3 — SFT Training (20-60 min)

### Hyperparameter defaults by model size

| Param | 4B E4B | 27B-31B | Notes |
|-------|--------|---------|-------|
| `lora_r` | 8 | 32 | Increase with model size |
| `lora_alpha` | 16 (=2r) | 64 (=2r) | **Always 2r, never r** |
| `lora_dropout` | 0.05 | 0.05 | Small dataset protection |
| `learning_rate` | 2e-4 | 2e-5 | 10× lower for larger models |
| `epochs` | 10 | 3 | Larger models overfit fast |
| `grad_accum` | 4 | 4 | Keep consistent |
| `batch_size` | 1 | 1 | VRAM-limited |
| `use_gradient_checkpointing` | "unsloth" | "unsloth" | Both |

### Unsloth API rules (Gemma 4 specific)

- **All Gemma 4 models use `FastModel`**, NOT `FastLanguageModel`.
- For multimodal fine-tuning (vision-aware): `FastVisionModel` with `finetune_vision_layers=False` for text-only adapters.
- MoE (26B-A4B): `FastModel` with `load_in_4bit=False, load_in_16bit=True` (QLoRA not recommended for MoE).

### Training command template

```bash
docker run --gpus all --ipc=host --shm-size=16g \
  -v $(pwd):/workspace \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -w /workspace --name tsunami_train_<specialist>_v1 \
  -e PYTHONUNBUFFERED=1 -e CUDA_VISIBLE_DEVICES=0 \
  -e WORLD_SIZE=1 -e LOCAL_RANK=0 -e RANK=0 \
  -e MASTER_ADDR=localhost -e MASTER_PORT=29500 \
  -d nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -c "pip uninstall -y flash-attn 2>/dev/null; \
    pip install unsloth trl datasets -q && \
    python3 -u training/train_unsloth.py \
      --data workspace/training_data/<specialist>_toolcall_train_v1.jsonl \
      --output models/gemma-4-<size>-tsunami-<specialist>-v1 \
      --epochs <10 or 3> --grad-accum 4 --lr <2e-4 or 2e-5> \
      --lora-r <8 or 32> --lora-alpha <2r> --lora-dropout 0.05 \
      --merge"
```

### Serving

```bash
docker run --gpus all -d --ipc=host \
  -v $(pwd):/workspace -v ~/.cache/huggingface:/root/.cache/huggingface \
  -w /workspace --name tsunami_serve_<specialist>_v1 -p 8090:8090 \
  nvcr.io/nvidia/pytorch:25.11-py3 \
  bash -c "pip install fastapi uvicorn transformers accelerate pillow -q && \
    python3 -u serve_transformers.py \
      --model models/gemma-4-<size>-tsunami-<specialist>-v1-merged \
      --port 8090"
```

For large models, add `--load-in-4bit` to serve_transformers.py.

### Expected loss trajectories

- 4B with 30-40 examples, 10 epochs: final loss 0.3-0.7. Below 0.3 = overfit.
- 31B with 30-40 examples, 3 epochs: final loss 0.5-1.0.

**Loss is not the metric.** Eval score is the only metric that matters.
A lower loss can produce a worse score (we measured v90 at loss 0.356 score 455,
v89 at loss 0.500 score 461).

---

## Phase 4 — Eval and Cross-Version Analysis (30 min)

### First eval

Run the eval. Record per-test pass/fail. Compute 5-layer breakdown.

### Cross-version matrix (after 3+ versions)

Build a spreadsheet: rows = eval tests, columns = training versions, cells = PASS/FAIL.

Then classify every test:

| Class | Signature | Action |
|-------|-----------|--------|
| **Stable-pass** | PASS in 100% of versions | Locked. Don't touch. |
| **Stable-fail** | FAIL in 100% of versions | **Structural.** SFT can't fix. DPO candidate OR eval design issue. |
| **Volatile** | Flips between versions | Temperature variance. Use multi-run median OR lower temp. |
| **Rising** | PASS only in recent versions | Genuine improvement. Target. |
| **Falling** | FAIL only in recent versions | Regression. Investigate last change. |

**The ceiling = sum of stable-pass + volatile test points.** You can't exceed it with SFT. If ceiling < 475, you need DPO or a bigger model.

### Pivot triggers (borrowed from Sigma Method)

Stop iterating SFT when ANY fires:
- 3 consecutive versions without net point gain → data rebalancing is dead
- Ceiling computed from cross-version matrix < target → SFT alone can't reach target
- Loss decreasing but score decreasing → overfit, reduce epochs or examples

---

## Phase 5 — DPO Ceiling Breaker (4-8 hours for data, 20-30 min for training)

DPO fixes specific decision boundaries. Run this **after** SFT has plateaued.

### When to use DPO

- Stable-fail tests remain (SFT can't fix)
- Volatile tests that should be stable
- Production behaviors the eval doesn't test but matter (stub-gate, spec-drop, mid-pipeline-chat)

### Data format (strict)

```json
{
  "prompt": "<full system+user+partial_conversation>",
  "chosen": "<|tool_call>call:right_tool{...}<tool_call|>",
  "rejected": "<|tool_call>call:wrong_tool{...}<tool_call|>",
  "source_bug": "short-tag-for-categorization",
  "note": "one-line why chosen is correct"
}
```

**Format rules:**
- `prompt` always starts with `<bos><|turn>system`
- `chosen` and `rejected` are **just the response** (no `<bos>`, no full trace)
- Same approximate length (within 2×) to avoid length-gamed training
- Same format (both tool calls, or both text — don't mix)

### Size and categorization

- **Target: 80-150 pairs.** Less than 60 won't generalize; more than 200 risks memorization.
- Categorize by "bug family" (3-letter tag). Aim for 5-12 families with 5-20 pairs each.
- **Hold out 10-15 pairs for eval** — don't train on them. Use to measure pre/post log-prob separation.

### Pair families (use these templates)

1. **Tool-choice**: Model picks wrong tool. `chosen`=right tool, `rejected`=common wrong tool.
2. **Stub-gate**: Model claims delivery on TODO. `chosen`=file_edit replacing stub, `rejected`=message_result claiming ready.
3. **QA discipline**: Model skips undertow. `chosen`=undertow call, `rejected`=message_result.
4. **Trigger detection**: Model misses trigger context. `chosen`=trigger tool (plan_update, search_web), `rejected`=default tool (project_init).
5. **Mid-pipeline-chat**: Model asks clarifying question mid-build. `chosen`=continue building, `rejected`=message_chat.
6. **Spec-drop**: Model silently substitutes framework. `chosen`=message_chat noting limitation, `rejected`=project_init with substitute.

### Hyperparameters

| Param | Value | Notes |
|-------|-------|-------|
| `lora_r` | same as SFT (8 or 32) | Adapter stacks on top |
| `lora_alpha` | 2r (16 or 64) | Same as SFT |
| `learning_rate` | **5e-6** | 10-40× lower than SFT |
| `beta` | 0.1-0.3 | Lower = more aggressive drift |
| `epochs` | **2-3** | Higher memorizes, lower under-trains |
| `reference_free` | False | Use SFT model as reference |

### Training command

```bash
python3 -u training/train_dpo.py \
  --base-model models/<sft_champion>-merged \
  --data workspace/training_data/<specialist>_dpo_v1.jsonl \
  --output models/<sft_champion>-dpo-v1 \
  --epochs 3 --lr 5e-6 --beta 0.1 \
  --lora-r 8 --lora-alpha 16 --lora-dropout 0.05 \
  --merge
```

### DPO generalization check (before full eval)

Before running the expensive full eval:
1. Run the 10-15 heldout pairs through the DPO-trained model.
2. Compute log-probs for chosen and rejected.
3. **Expected: chosen log-prob > rejected log-prob for ≥80% of heldouts.**
4. If <60%, DPO hasn't learned. Investigate data quality or hyperparams.
5. If >95%, possible memorization. Run full eval to confirm generalization.

---

## Phase 6 — Production Hardening (ongoing)

### Real-world trace collection

Once a specialist is in use, log real interactions:
- Tool sequences per task
- User reactions (accepted, retried, abandoned)
- Actual failure modes

Collected failures become the next DPO cycle's `rejected` side. **Real failures generalize better than synthetic ones.**

### Specialist-specific additions

Add layers beyond the standard 5:

- **L6 Vision**: For visual specialists (web builder with mockups, gamedev with sprites)
- **L7 Latency**: For production-critical specialists (sigma expert needs <5s, gamedev <10s)
- **L8 Resource**: For environment-constrained specialists (VRAM budget, CPU budget)

---

## The Go/No-Go Decision Tree

```
Start Phase 0 (charter)
    ↓
Charter complete? ──no──→ Back to Phase 0
    ↓ yes
Build eval (Phase 1)
    ↓
Eval runs, scores 0 on base model? ──no──→ Eval broken, fix
    ↓ yes
Build SFT data (Phase 2)
    ↓
SFT train + eval (Phases 3-4)
    ↓
Score ≥ 95% of ceiling? ──yes──→ STOP, specialist is done
    ↓ no
Cross-version ceiling analysis
    ↓
Ceiling ≥ target? ──yes──→ More SFT iterations (up to 3 versions)
    ↓ no
Build DPO data (Phase 5)
    ↓
DPO heldout check passes? ──no──→ Redesign DPO data, retry
    ↓ yes
Full eval
    ↓
Score ≥ target? ──yes──→ Production (Phase 6)
    ↓ no
Collect real-world traces, DPO v2
```

---

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| alpha=r (not 2r) | Behaviors imprinted at half strength, fragile at temp=0.3 | Always `alpha = 2 * r` |
| dropout=0 | Dominant patterns overfit, minorities overwritten | `dropout=0.05` |
| Mixed DPO formats | Some pairs trace, some tool-call — DPO can't compute stable log-probs | One format per DPO dataset |
| Saturating core tools | 30+ examples of `project_init`, 1 of `plan_update` — triggers never fire | Balance by tool usage |
| Tuning by loss | Lower loss, lower score (we've measured this) | Tune by eval score only |
| Too many bare examples | 7× gradient density overwhelms pipeline examples | Prefer pipeline-format over bare |
| DPO with 20 pairs | Memorization without generalization | 80-150 pairs minimum |
| DPO epochs > 3 | Destroys SFT behaviors | Keep epochs ≤ 3 |
| Wrong Unsloth API | `FastLanguageModel` on Gemma 4 = silent degradation | `FastModel` for Gemma 4 text-only |
| temp=0.3 single run | ±10 point variance = noise | 3 runs median or temp=0.0 |

---

## Timeline for a New Specialist (Gamedev, Sigma Expert, etc.)

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| 0 — Charter | 30 min | `<specialist>_charter.md` |
| 1 — Eval | 2-4 hr | `eval_<specialist>.py` |
| 2 — SFT data | 4-6 hr | `<specialist>_toolcall_train_v1.jsonl` (30-40 examples) |
| 3 — SFT train | 30 min | `<specialist>-v1-merged/` |
| 4 — First eval | 30 min | Scoreboard, cross-version row |
| (iterate Phase 2-4 up to 3×, ~1 day) | | |
| 5 — DPO data | 4-8 hr | `<specialist>_dpo_v1.jsonl` (80-150 pairs) |
| 5 — DPO train | 20-30 min | `<specialist>-dpo-v1-merged/` |
| 5 — Heldout check + eval | 30 min | Final scoreboard |
| **Total** | **~2 days** | Production-ready specialist ≥95% of ceiling |

---

## What Makes Tsunami Specialists Composable

This playbook produces adapters with identical infrastructure:
- Same base model (Gemma 4 family)
- Same serving (`serve_transformers.py`)
- Same eval structure (5 layers, 500 points)
- Same training scripts (`train_unsloth.py`, `train_dpo.py`)
- Same format (tokenizer chat template, `<|tool_call>` responses)

Implication: you can serve them via **vLLM multi-LoRA** (one base + N ~35MB adapters)
and route per-request by task type. A single GPU serves web, gamedev, sigma expert
simultaneously. Each adapter is independently iterable.

**The adapter IS the specialist. Training is additive. Specialists are cheap.**
