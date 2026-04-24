# effect_custom — ERNIE base + Qwen chain workflow

Per-game custom VFX generation. 5 sub_kinds matching sister's live
`effect_layer::sub_kind` taxonomy. Complements `vfx_library` (20
pre-rendered canonical effects) by letting scaffolds produce
title-specific variants matching the game's palette + era.

> **Architecture update 2026-04-22 (post-Shoal)**: this workflow no
> longer has its own run_canary.py. ERNIE produces one canonical base
> per effect; Qwen-Image-Edit `/v1/images/animate` produces per-frame
> transitions via the shared `_common/base_plus_chain.py` orchestrator
> from nudge payloads at `scaffolds/.claude/nudges/<essence>/<anim>.json`.

## Animation flag per sub_kind

```
explosion_vfx     → needs_animation = true   (4-frame chain)
spell_vfx         → needs_animation = true   (8-frame chain)
aura_vfx          → needs_animation = true   (8-frame LOOP — verify_loop_seam)
atmospheric_vfx   → needs_animation = true   (6-frame LOOP — tileable)
summon_vfx        → needs_animation = true   (10-frame chain)
```

All 5 effect sub_kinds require the Qwen chain — none are static-only.

## Canonical cell sizes + frame counts

Per `anim_set.json::sub_kinds`:

| sub_kind | Canonical cell | Frames | Loop | Notes |
|---|---|---:|:-:|---|
| `explosion_vfx` | 16×16 (small) or 128×128 (large) | 4 | no | Bimodal size — scaffolds pick per-use-case |
| `spell_vfx` | 32×32 | 8 | no | JRPG cast arc (gather/peak/dissipate) |
| `aura_vfx` | 32×32 | 8 | **yes** | Frame N must match frame 0; screen-blend |
| `atmospheric_vfx` | 64×64 | 6 | **yes** | Horizontally tileable |
| `summon_vfx` | 64×64 | 10 | no | FF-style portal-emergence arc |

## Run

```bash
cd scaffolds/engine/asset_workflows/_common

# Effect-layer only
python3 batch_run.py --apply --kind effect_layer

# Just explosions across the corpus
python3 batch_run.py --apply --kind effect_layer --sub-kind explosion_vfx

# After batch_run finishes, assemble strips + verify loop seams
python3 strip_assembler.py ./out/bpc/ --recurse
```

## Postprocess contract

`postprocess.py` exposes (unchanged from 2026-04-22 landing):

- `assemble_strip(src, out, cell_px, frame_count, do_align=True)` — legacy; `strip_assembler.py` is the new canonical path
- `verify_loop_seam(strip_path, frame_count, cell_px)` — pixel-diff RMS between first and last frame for loop sub_kinds (aura, atmospheric). Returns `{rms_diff, ok, note}`.
- `darken_to_transparent(src, out, darkness_threshold=20)` — aura screen-blend prep
- `split_strip`, `align_frames`, `center_pad_to_cell`, `alpha_bbox` — shared helpers

## Relationship to vfx_library

| | `vfx_library` | `effect_custom` (this) |
|---|---|---|
| Model | Pre-rendered catalog, one fixed palette per effect | Per-game custom generation via ERNIE + Qwen chain |
| Per-game customization | No | Yes — palette + era slot + corpus-harvested nudges |
| Coverage | 20 canonical effects | 99 corpus effect_layer anims (after nudge tuning) |

## Status

- **Coverage gap**: closed 2026-04-22 — 14th asset_workflow.
- **Old canary set**: deleted (`run_canary.py` + `canary_prompts.jsonl`) — replaced by corpus-driven nudge payloads.
- **Live outputs**: pending ERNIE + Qwen servers coming back online.
