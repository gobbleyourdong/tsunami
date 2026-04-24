# projectile_sprites — ERNIE base + Qwen chain workflow

Small projectile sprites (blaster shots, wave-beams, missiles, thrown
daggers, grenades). Covers the `projectile` kind (49 anims across 14
essences per `SPRITE_KIND_WORKFLOW_MATRIX.md §2`).

> **Architecture update 2026-04-22 (post-Shoal)**: this workflow no
> longer has its own run_canary.py. ERNIE produces one canonical base
> per projectile; Qwen-Image-Edit produces frame transitions. Both are
> driven by the shared `_common/base_plus_chain.py` orchestrator from
> nudge payloads at `scaffolds/.claude/nudges/<essence>/<anim>.json`.
> See the per-kind animation-flag table in `_common/nudge_library.py`.

## Animation flag per sub_kind

```
gun_proj              → needs_animation = false  (single-frame)
special_attack_proj   → needs_animation = true   (4-frame chain)
missile               → needs_animation = true   (4-frame chain)
melee_thrown          → needs_animation = true   (4-frame rotation)
explosive             → needs_animation = true   (4-frame fuse flicker)
```

Canonical cell sizes per sub_kind live in `anim_set.json`. Postprocess
helpers (`assemble_strip`, `alpha_bbox`, `center_pad_to_cell`) are in
`postprocess.py` — consumed by `_common/strip_assembler.py` after base
+ chain produces per-frame PNGs.

## Run

```bash
cd scaffolds/engine/asset_workflows/_common

# Gold-quality projectiles only
python3 batch_run.py --apply --kind projectile --min-nudges 3

# All projectile payloads including static gun_proj + unparsed chains
python3 batch_run.py --apply --kind projectile

# After batch_run finishes, assemble per-animation strips:
python3 strip_assembler.py ./out/bpc/ --recurse
```

Outputs land under `_common/out/bpc/<essence>/<animation>/`:
- `frame_000.png` (ERNIE base) ... `frame_00N.png` (Qwen chain)
- `strip.png` (post-assembly horizontal N×1)
- `strip.manifest.json` + `manifest.json`

## Postprocess contract

`postprocess.py` exposes (unchanged from 2026-04-22 landing):

- `assemble_single(src_path, out_path, cell_px)` — single-frame case (gun_proj)
- `assemble_strip(src_path, out_path, cell_px, frame_count)` — legacy helper; `strip_assembler.py` is the new canonical path
- `alpha_bbox(img)`, `split_4frame_strip(img, frames)`, `center_pad_to_cell(img, cell_px)`, `align_frames(frames)` — shared helpers

## Status

- **Coverage gap**: closed 2026-04-22 — 13th asset_workflow.
- **Old canary set**: deleted (`run_canary.py` + `canary_prompts.jsonl`) — replaced by corpus-driven nudge payloads.
- **Live outputs**: pending ERNIE + Qwen servers coming back online.
