# effect_custom — ERNIE prompt template

Per-game custom VFX generation. Covers 5 sub_kinds: `explosion_vfx` /
`spell_vfx` / `aura_vfx` / `atmospheric_vfx` / `summon_vfx`. Complements
vfx_library (pre-rendered catalog of 20 canonical effects) by letting
scaffolds produce title-specific effects matching the game's palette +
pixel-art era.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pin-per-effect-id for reproducibility

Output is cropped to the target cell size during postprocess. Most
effects produce a multi-frame horizontal strip (4 for explosion, 8
for spell/aura, 10 for summon, 6 for atmospheric).

## The template

Two slot sets — single-frame cases are rare here (most effects are
animations). Primary template is multi-frame strip:

### Multi-frame strip template

```
A {frame_count}-frame horizontal strip of a pixel-art {sub_kind_role}
effect on solid magenta (#FF00FF) background. Animation: {animation_arc}.
Each cell is {cell_size_hint}, strip is {frame_count} cells wide.
Color palette: {palette_preset_description}. Style: pixel art with
chunky pixels, no anti-aliasing. {era} aesthetic. No text, no
characters, no UI elements — just the effect centered in each frame.
{blend_mode_hint}
```

### Slot values by sub_kind

#### `explosion_vfx` (4 frames, 16×16 small OR 128×128 large)

- `sub_kind_role` = "explosion burst"
- `animation_arc` = "frame 1 flash-start, frame 2 peak-expansion, frame 3 debris-scatter, frame 4 fade-smoke"
- `cell_size_hint` = "16×16 pixel tight spark" (small) OR "128×128 pixel wide explosion" (large)
- `blend_mode_hint` = "High-contrast bright core, alpha-over blending"

#### `spell_vfx` (8 frames, 32×32 canonical)

- `sub_kind_role` = "magic spell"
- `animation_arc` = "frames 1-2 gathering energy, 3-4 spell shape forms, 5-6 peak release, 7-8 dissipation"
- `cell_size_hint` = "32×32 pixel magic effect"
- `blend_mode_hint` = "Bright core with glow, alpha-over"

#### `aura_vfx` (8 frames, LOOP — 32×32 canonical)

- `sub_kind_role` = "persistent aura glow"
- `animation_arc` = "gentle pulse cycle — frame 1 through 8 subtle brightness/size oscillation; FRAME 8 MUST MATCH FRAME 1 so the animation loops seamlessly"
- `cell_size_hint` = "32×32 pixel aura shimmer"
- `blend_mode_hint` = "Screen-blend (light-additive), soft edges"

#### `atmospheric_vfx` (6 frames, LOOP — 64×64 or larger)

- `sub_kind_role` = "ambient atmospheric effect"
- `animation_arc` = "sustained drift loop — frame 1 through 6 particle motion; FRAME 6 MUST MATCH FRAME 1 for seamless looping"
- `cell_size_hint` = "64×64 pixel atmospheric tile (tileable)"
- `blend_mode_hint` = "Alpha-over, horizontally-tileable pattern"

#### `summon_vfx` (10 frames, 64×64 canonical)

- `sub_kind_role` = "summon portal / teleport"
- `animation_arc` = "frames 1-3 gathering darkness, 4-5 portal opens, 6-8 emergence light flares, 9-10 portal closes"
- `cell_size_hint` = "64×64 pixel summon portal"
- `blend_mode_hint` = "Alpha-over, multi-stage emergence"

### `palette_preset_description` (pick one of 13 from anim_set.json)

- `fire_orange` → "orange-red flames with yellow core"
- `ice_cyan` → "cyan-white crystalline shards"
- `electric_yellow` → "bright yellow zig-zag with white core"
- `holy_white` → "pure white with gold highlights"
- `dark_purple` → "deep purple with black core"
- `green_plasma` → "translucent green glow"
- `rainbow_glitter` → "multi-color sparkles"
- `blood_red` → "dark red with sharp edges"
- `smoke_grey` → "grey wispy puff"
- `water_blue` → "blue translucent ripple"
- `rain_streaks` → "diagonal grey streaks"
- `ember_float` → "small orange points drifting up"
- `spark_flash` → "white radial burst"

### `era`
- `"8-bit NES"` (chunky pixels, limited palette)
- `"16-bit SNES/Genesis"` (smoother but still pixel-art)
- `"arcade CPS"` (vibrant, high-detail)

## Canary prompts

Six effects — one per sub_kind (+ one bimodal explosion variant):

### Canary A: `small_hit_spark` (explosion_vfx, 16×16)
4-frame · fire_orange · 8-bit NES · Classic 8-bit impact-spark for bullet hits.

### Canary B: `mega_explosion` (explosion_vfx, 128×128)
4-frame · fire_orange · 16-bit SNES · Large-scale boss-death or stage-finale explosion.

### Canary C: `fire_spell_cast` (spell_vfx, 32×32)
8-frame · fire_orange · 16-bit SNES · JRPG fire-magic cast animation.

### Canary D: `power_up_aura` (aura_vfx, 32×32 loop)
8-frame loop · rainbow_glitter · 8-bit NES · Power-up-active indicator.

### Canary E: `rain_tile` (atmospheric_vfx, 64×64 tileable loop)
6-frame loop · rain_streaks · 16-bit SNES · Diagonal rain backdrop, horizontal-tileable.

### Canary F: `ff_summon_portal` (summon_vfx, 64×64)
10-frame · dark_purple · 16-bit SNES · FF-style summon portal.

## Honest limits

- **Loop seamlessness for aura + atmospheric**: ERNIE doesn't guarantee frame[last] matches frame[0] despite the prompt instruction. Postprocess includes `verify_loop_seam(frames)` — computes pixel-diff between last and first frame, flags frames that need manual touchup or re-roll.
- **Bimodal explosion sizes**: scaffolds pick 16 or 128 per call; no auto-selection. Defaults to 16.
- **Pixel-art consistency**: ERNIE Turbo sometimes produces smooth gradients despite "chunky pixels" prompt. `/v1/images/pixelize` post-pass available.
- **Aura screen-blend**: ERNIE doesn't know about blend modes; generated aura has white backdrop unsuited for screen-blending. Post-pass `darken_to_transparent` converts white backdrop to transparent for screen-blend compositing.
