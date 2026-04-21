# top_down_jrpg_character — ERNIE prompt template

The small-sprite RPG-Maker convention. Final per-frame size is **48×48**
(classic RPG Maker 2003/XP/VX/VX-Ace/MZ) or 64×64 (MV/MZ high-res mode).
Characters are overworld NPCs + party sprites in classic JRPG games —
readable at very small scale, limited palette, sharp outlines.

Plan cat. 5. Anchors: Chrono Trigger, Final Fantasy VI, Dragon Quest III,
every RPG Maker game.

## Relationship to `top_down_character`

`top_down_character` (cat. 1) is the modern ARPG-scale workflow — 256×256
or 128×128 per frame, Zelda-ALttP / Hyper Light Drifter detail level.

`top_down_jrpg_character` (this workflow, cat. 5) is the **retro JRPG
convention** — 48×48 or 64×64 per frame, 3-frame walk × 4 directions =
12 frames minimal (no separate idle — the walk cycle's middle frame IS
the idle pose by convention).

Both use the same `_common/character_blockout.py` helpers and the same
cross-projection identity discipline, so the **same character can live
in both libraries** and scaffolds pick the scale that matches their
engine.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA)
- **Canvas:** 1024×1024 gen → downscale to 48×48 at postprocess
  (generating at 48 directly is useless — the model can't render a
  readable character at 48 px. Gen big, downscale with NEAREST to
  preserve pixel-art crispness.)
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pinned per character, shared across 4 direction frames for
  identity preservation (same lesson from `iso_character` +
  `dialogue_portrait`).

## The template

```
top-down overhead JRPG sprite of <character_name>, SNES-era 16-bit
pixel-art style with limited 32-color palette, <direction_phrase>,
<movement_pose_description>, orthographic camera directly above
looking straight down, character centered in frame filling roughly 20
percent of the canvas (small compact sprite intended to downscale to
48 pixels), viewed from directly overhead with top of head visible and
shoulders forming a small circular silhouette, isolated against a
solid magenta #FF00FF background, no ground plane, no shadow, clean
flat cel-shaded colors with hard 1-pixel edges, no antialiasing bleed
into the magenta, no text, no border, no watermark, <style_modifiers>
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<character_name>` | identity (KEEP CONSTANT across 4 directions) | `barbarian warrior with red hair, chainmail vest, and an axe` (keep it simpler than iso/top_down — small sprites need compressed identity) |
| `<direction_phrase>` | compass heading | `north-facing (back of character visible)`, `east-facing`, `south-facing (front of character visible)`, `west-facing` |
| `<movement_pose_description>` | mid-stride reference | `mid-stride walking pose with right leg forward and left leg back` |
| `<style_modifiers>` | palette / era flavor | `SNES Chrono-Trigger palette with warm reds and forest greens`, `NES 4-color constraint per sprite`, `GBC handheld-retro palette` |

### ERNIE rules baked in

- **"small compact sprite intended to downscale to 48 pixels"** is
  spelled out in the prompt — it nudges the model toward simpler
  silhouettes that survive aggressive downscaling. Without the hint the
  model over-detailifies and the 48-px downscale loses readability.
- No literal quotes. `use_pe=false`. `keep_largest_only=True`.
- **Downscale with `Image.NEAREST`** (NOT LANCZOS or bicubic) — pixel
  art needs hard pixels, not smoothed interpolation. This is the only
  character workflow where `NEAREST` downscaling is the right choice.

## Scale targets

- Gen canvas: 1024×1024
- Character occupies ~20% of the canvas (smaller than other character
  workflows — 48×48 output means the source character only needs to be
  ~200×200 at gen time)
- Final output: **48×48** (classic RPG Maker) or 64×64 (MV/MZ)

## Call-count budget

- **Blockout round (shipped here):** 4 calls (one per direction) — one
  mid-stride pose each.
- **Full 3-frame walk × 4 directions = 12 frames** (future work for the
  `character_animation` workflow): 12 calls — runs in ~1 min with
  3-ERNIE pool.

## Cross-projection identity

Same barbarian seed (`20_001`) and description as
`iso_character` and `top_down_character` — the cross-projection
library grows another projection. One character, four scales/projections:
- iso (2:1 dimetric, 8 directions, ~128px/frame)
- top_down (orthographic, 4 directions, ~256px/frame)
- side_scroller (side profile, 1 direction, ~256px/frame)
- **jrpg (overhead, 4 directions, 48px/frame)** ← this workflow
