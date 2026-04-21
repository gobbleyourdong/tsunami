# iso_character — ERNIE prompt template

Isometric 2:1 dimetric character workflow. Covers Shoal plan cat. 2.

This round ships a **movement-loop blockout**: one canonical mid-stride
pose per direction, 8 directions, one frame each = **8 frames total**.
Future animation + rotation workflows (not yet shipped) will interpolate
the blockout into full N-frame walk/run cycles and fill in sub-8-angle
rotations.

Anchors: Diablo II, Fallout Tactics, Hades, SNES Landstalker.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pinned per character. All 8 direction frames share the
  **same seed** (identity discipline from `dialogue_portrait` canary
  round — seed-pinning holds identity across varying-prompt regenerations).
- **Pool dispatch:** 8 frames × 3-ERNIE pool → ~3 waves parallel, wall-clock
  ~30–45 s for the full blockout (vs ~70 s single-pipe).

## The template

```
isometric dimetric 2:1 game sprite of <character_name>, <style_variant>,
<direction_description>, <movement_pose_description>, 26.57 degree
camera elevation angle, character centered in frame filling roughly 30
percent of the canvas, isolated against a solid magenta #FF00FF
background, no ground plane, no shadow, flat clean cel-shaded colors,
readable silhouette, crisp edges, no antialiasing bleed into the
magenta, no text, no border, no watermark, <style_modifiers>
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<character_name>` | subject identity (KEEP CONSTANT across all 8 directions) | `barbarian warrior with braided red beard, chainmail vest, a two-handed axe strapped to the back, leather boots` |
| `<style_variant>` | overall visual register | `Diablo-II-style dark fantasy painterly sprite`, `Fallout-Tactics-style grim sci-fi`, `Hades-style vibrant cel-shaded`, `blockout grey-box placeholder with silhouette-only detail` |
| `<direction_description>` | compass heading (varies per frame) | `facing away from camera toward the back of the scene`, `facing right in full profile`, `facing the camera toward the viewer`, `facing up-and-right toward the upper-right corner` |
| `<movement_pose_description>` | the canonical mid-stride pose (SAME across all 8 directions — only direction changes) | `mid-stride walking pose, one leg forward and bent at the knee, one leg back with heel slightly lifted, torso slightly leaning forward, arms swinging counter to the legs — canonical movement reference pose` |
| `<style_modifiers>` | per-scaffold flavor | `warm saturated palette with dramatic lighting`, `muted desaturated palette with harsh shadows`, `neon-trimmed with strong rim lighting` |

### ERNIE rules baked in

- **Same seed + same `<character_name>` + same `<movement_pose_description>`
  across all 8 frames** — only `<direction_description>` varies. This
  is the identity-preservation discipline proved out in
  `dialogue_portrait`.
- **26.57° elevation** is the 2:1 dimetric convention (atan(0.5)). The
  prompt spells it literally because diffusion models often interpret
  "isometric" as "close to orthographic" without a number.
- No baked shadow, no literal quotes, `use_pe=false`.

## Blockout style variant

For a grey-box / blockout render (silhouette-only, for prototyping
layout before full character art), use:

```
style_variant: "blockout grey-box placeholder with silhouette-only
detail, flat grey fill with 3-tone shading (light/mid/dark grey), no
face details, no equipment detail, simple geometric body proportions"
```

Scaffolds can render the blockout to lay out combat timing, collision
bounds, and z-sorting before committing to full character art gens.

## Full 8-direction blockout budget

- 8 frames (one per direction) × 1 ERNIE call per frame = **8 calls**
- 3-ERNIE pool wall-clock: **~30 s** (3 parallel waves at 1024 px —
  GPU compute-bound, so ~1.4× speedup vs single-pipe)
- Single-pipe wall-clock: ~70 s

## Future animation + rotation hooks

This workflow produces **1 blockout frame per direction** now.
Downstream workflows will consume the blockout output:

- `character_animation` (future) — reads `blockout.spec.json`'s
  `anim_frame_targets` and interpolates the mid-stride pose into N
  frames per anim per direction using `edit_image` on the blockout
  reference. Expected: 4-8 frames per walk/run cycle, 4-8 frames per
  attack. 8 dir × 8 frames × 3 anims = 192 frames per character.
- `character_rotation` (future) — reads `rotation_angles` (default 8)
  and can up-res to 16/32/64 direction rotation by interpolating
  between the 8 shipped cardinal/ordinal directions.

The blockout manifest's `.spec.json` companion carries these forward
so the downstream workflows don't need to re-derive anything.

## Scale targets

- Character occupies ~30 % of the 1024×1024 canvas (≈ 300×300 effective).
- Final per-frame size after alpha-crop: 256×256 for Diablo-scale iso,
  128×128 for retro iso (Landstalker / early RPG Maker iso).
