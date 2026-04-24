# _common/

Shared helpers for asset workflows. Two eras of modules live here:

**Legacy (pre-2026-04-22)** — per-workflow primitives Shoal built for
the hand-authored character / vfx / tile workflows:
- `sprite_sheet_asm.py` — canonical sheet assembler (horizontal/grid)
- `character_blockout.py` — 8-direction iso movement-loop blockout

**Pipeline (post-2026-04-22)** — corpus-driven ERNIE-base + Qwen-chain
orchestration shared across `projectile_sprites` / `effect_custom` /
`parallax_backdrop` (and any future workflow that consumes nudge
payloads):
- `nudge_library.py` — progression_description → NudgeSpec parser
- `base_plus_chain.py` — single-payload orchestrator (ERNIE base + Qwen chain)
- `batch_run.py` — corpus walker with priority/filter/resume
- `strip_assembler.py` — post-processor (frames → canonical strip)

## The pipeline (end-to-end)

```
sprite_sheets/<essence>/*.json              ← sister's extractions (2074 anims)
  ↓ tools/nudge_extractor.py
scaffolds/.claude/nudges/<essence>/*.json   ← 2074 nudge payloads
  ↓ tools/nudge_quality_report.py (optional)
_QUALITY_REPORT.md + 7 gold-clean payloads
  ↓ _common/batch_run.py --apply
  │   → _common/base_plus_chain.py (per payload)
  │       → ERNIE :8092 /v1/images/generate     (base frame)
  │       → Qwen-Image-Edit :8094 /v1/images/animate (chain frames; only if needs_animation)
  ↓
<out>/bpc/<essence>/<anim>/
  frame_000.png ... frame_00N.png + manifest.json
  ↓ _common/strip_assembler.py --recurse
<out>/bpc/<essence>/<anim>/strip.png + strip.manifest.json
  ↓ (engine's build_sprites.py ingests strips; runtime loads via loader.ts)
scaffolds/engine/src/sprites/kind_index.ts    ← typed lookup at runtime
```

## Modules

### `nudge_library.py`

Parses sister's `progression_description` prose into Qwen-Image-Edit-
ready NudgeSpec objects (delta + strength + confidence + strategy).

Four parse strategies:
1. `frame_enumerate` — explicit "frame 1 X, frame 2 Y" lists (confidence 0.9)
2. `arrow_split` — `X → Y → Z` chains (confidence 0.85)
3. `narrative` (comma-list) — fc-aligned comma-separated phrases (confidence 0.7)
4. `narrative` (cycle fallback) — "alternate to X" / "next phase of Y" shorthand (confidence 0.55)

Also exports `classify_kind_needs_animation(kind, sub_kind) → bool` —
default per-kind flag table. Scaffolds can override per-entry.

### `base_plus_chain.py`

Single-payload orchestrator. Call `run_payload(payload, out_dir)` with
a loaded nudge JSON. Handles:
- Idempotency (cached disposition skips already-produced outputs)
- Dry-run (prints the plan, no server calls)
- ERNIE base generation (50-step Base or 8-step Turbo configurable)
- Qwen chain (only when `needs_animation: true`)
- Manifest write with full provenance

Environment:
- `ERNIE_URL` (default `http://localhost:8092`)
- `QWEN_EDIT_URL` (default `http://localhost:8094`)

### `batch_run.py`

Corpus walker over `scaffolds/.claude/nudges/`. Priority ordering:
1. Animated gold (≥3 parsed nudges)
2. Animated partial (1-2 parsed nudges)
3. Static (ERNIE-only)
4. Animated unparsed (needs_animation=true but 0 nudges; skipped by default)

Filters: `--essence`, `--kind`, `--sub-kind`, `--min-nudges`,
`--max-nudges`, `--include-unparsed`, `--no-static`.

### `strip_assembler.py`

Post-processor. After `base_plus_chain` produces frame_*.png files,
this tool assembles them into a canonical N×1 strip PNG + manifest
via `sprite_sheet_asm.assemble_strip`. Uses the `nudges_used` field
from base_plus_chain's manifest as frame labels.

Works batch-style: `python3 strip_assembler.py ./out/bpc/ --recurse`.

### `sprite_sheet_asm.py` (legacy, still canonical)

The underlying sheet assembler. `assemble_strip(frames, labels,
gutter_px)` is the primitive `strip_assembler.py` calls. Also
`assemble_grid` / `assemble_labeled_grid` for dev-view thumbnails.

### `character_blockout.py` (legacy)

Used by the 4 character workflows (iso / top_down / top_down_jrpg /
side_scroller) for 8-direction movement-loop blockouts. Pre-dates the
nudge-driven pipeline; these workflows still work independently but
could be migrated to the base_plus_chain pattern if character-animation
coverage becomes a priority (~903 character anims in the corpus).

### `blockout_loader.py`

Bridges `scaffolds/.claude/blockouts/<essence>/<anim>.json` (emitted by
the harvester `tools/character_blockout_extractor.py`) into `BlockoutSpec`
objects + per-direction ERNIE prompts. Identity-anchor comes from
sister's actual progression_descriptions — not hand-authored templates.

```python
from blockout_loader import load_blockout, blockout_prompts, blockout_seed
raw = load_blockout("1986_dragon_quest", "hero_plainclothes_walk")
prompts = blockout_prompts(raw)   # {'N': ..., 'E': ..., 'S': ..., 'W': ...}
seed = blockout_seed(raw)         # pin across all N direction calls
# Character workflow fires ERNIE × 4 directions with pinned seed,
# then (optional) Qwen chain per-direction for anim_frame_targets frames.
```

Current inventory (30 specs):
- **1986_dragon_quest**: 16 (full character roster — 6 armor-tiers, princess, king, NPCs)
- **1986_legend_of_zelda**: 10 (moblin / lynel / darknut / link variants)
- **1980_pac_man**: 1 (ghost/pac-man 4-dir chomp)
- other essences: 3

Dragon Quest's 6-tier armor set (plainclothes → leather → chain →
half-plate → full-plate → magic) is the **canonical identity-preservation
test**: same character, same 4-dir × 2-frame structure, differs only by
equipment. Perfect for validating Qwen-Image-Edit + multi_angles LoRA
identity-lock behavior.

## Running the pipeline

```bash
# Pre-flight: run the quality report + triage flagged payloads
python3 scaffolds/.claude/tools/nudge_quality_report.py
# → scaffolds/.claude/nudges/_QUALITY_REPORT.md

# Dry-run the 22 highest-quality chains (no server calls)
cd scaffolds/engine/asset_workflows/_common
python3 batch_run.py --min-nudges 3 --no-static

# Live-fire one essence first (cheap validation)
python3 batch_run.py --apply --essence 1981_galaga --min-nudges 3

# After batch_run finishes, assemble strips
python3 strip_assembler.py ./out/bpc/ --recurse

# Verify outputs
ls ./out/bpc/1981_galaga/player_explosion/
# → frame_000.png frame_001.png frame_002.png frame_003.png
#   manifest.json strip.png strip.manifest.json
```

## Disposition reference

`base_plus_chain.RunResult.disposition` values:
- `cached` — all frames exist; no server calls fired
- `static` — ERNIE-only (single frame); no Qwen
- `animated` — ERNIE base + Qwen chain frames
- `dry-run` — no actual calls
- `error` — fatal at either server stage (check `result.error`)

`batch_run.py` aggregates these + reports at end. `strip_assembler.py`
emits its own dispositions: `assembled`, `cached`, `skipped`
(missing frames), `error:<msg>`.

## Future additions

- `character_animation.py` — refactor the 4 legacy character workflows
  to consume nudge payloads (character kind × 903 anims in corpus)
- `nudge_llm_refine.py` — use Qwen36 text model to refine the 563
  unparsed multi-frame anims into structured chains (blocked on 8095)
- `palette_ops.py` — consolidate `normalize_palette(max_colors=N)`
  discipline currently duplicated across per-workflow postprocess
