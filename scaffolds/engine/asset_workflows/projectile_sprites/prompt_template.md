# projectile_sprites — ERNIE prompt template

Small, short-animation projectile sprites. Canonical sizes 8×8 or 16×16,
frame counts 1 or 4. Cheapest ERNIE workflow in the library — one call
per projectile, ~20s turnaround for Turbo model.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA). Projectiles
  are center-framed on chromakey; postprocess alpha-extracts.
- **Canvas:** 1024×1024 (waste most; crop to cell size during postprocess)
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pin-per-projectile-id for reproducibility. Identity across
  variants is NOT required (unlike character).

## The template

Two slot sets — one for single-frame (gun_proj / simple thrown), one
for 4-frame travel animations (special_attack_proj / missile / explosive).

### Single-frame template

```
Pixel-art {projectile_kind} projectile sprite on solid magenta
(#FF00FF) background. Single frame, facing east (right-moving). Size
approximately {size_hint}. Color palette: {palette_preset_description}.
Style: 8-bit or 16-bit pixel art, chunky pixels, no anti-aliasing.
Centered in frame with plenty of magenta around it. No text, no UI,
no character holding it.
```

### 4-frame travel animation template

One ERNIE call produces a 4-cell horizontal strip. Prompt instructs the
composition:

```
A 4-frame horizontal strip of a pixel-art {projectile_kind} projectile
in flight, facing east (right-moving). Each cell shows the same projectile
at a slightly different moment of its {travel_animation_description}.
Solid magenta (#FF00FF) background. Pixel-art style: {palette_preset_description}.
Each cell is {size_hint}, strip is 4 cells wide. All 4 frames have the
projectile centered vertically and aligned consistently so they animate
smoothly when played in sequence. No text, no background details.
```

## Slot values

### `projectile_kind`
- `gun_proj` → "blaster shot" or "bullet" or "laser pellet"
- `special_attack_proj` → "character special attack" — prefix with character name (e.g., "samus-style wave-beam")
- `missile` → "homing missile with exhaust trail"
- `melee_thrown` → "thrown dagger" or "thrown axe" or "thrown cross"
- `explosive` → "grenade with lit fuse" or "throwable bomb"

### `travel_animation_description` (4-frame only)
- `gun_proj` (usually 1-frame; if 4-frame: "energy pulse — glow brightens then dims")
- `special_attack_proj` → "energy pulsing: frame 1 gathering, frame 2 peak, frame 3 arcing, frame 4 pulsing"
- `missile` → "thrust pulse: exhaust trail brightens across frames"
- `melee_thrown` → "rotation: 0°, 90°, 180°, 270° about center"
- `explosive` → "fuse-light flicker: bright-dim-bright-dim"

### `size_hint`
- `[8, 8]` → "8×8 pixel, very small — roughly 1/8 the canvas height"
- `[16, 16]` → "16×16 pixel, small — roughly 1/6 the canvas height"
- `[16, 8]` → "16 wide × 8 tall pixel, horizontal beam shape"
- `[48, 8]` → "48 wide × 8 tall pixel, long thin laser beam"

### `palette_preset_description` (from anim_set.json palette_presets)
Pick one of:
- `yellow_pellet` → "bright yellow core with white inner-light — classic 8-bit blaster"
- `red_energy` → "red-orange energy ball, glowing hot"
- `blue_beam` → "blue-cyan energy beam, electric — samus wave-beam canonical"
- `green_plasma` → "green alien plasma, translucent glow"
- `white_missile` → "white metallic body with orange exhaust flame"
- `brown_dagger` → "brown-silver dagger with highlighted blade"
- `grey_bomb` → "dark grey metal bomb with glowing red fuse"
- `purple_magic` → "purple magical glow with white sparkles"
- `rainbow_powerup` → "multi-color rainbow shot, sparkling"

## Canary prompts

Six canonical projectiles — one per sub_kind (+ one extra 4-frame variant):

### Canary A: `mega_buster_shot` (gun_proj, single-frame)
- kind: gun_proj, single-frame, 8×8, yellow_pellet
- Prompt fills: "yellow blaster shot pixel sprite, 8×8 pixel tiny size, centered on magenta"

### Canary B: `samus_wave_beam` (special_attack_proj, 4-frame)
- kind: special_attack_proj, 4-frame strip, 16×16 per cell, blue_beam
- Prompt fills: "samus-style wave-beam, blue-cyan electric pulse, 4-frame strip, energy pulsing animation"

### Canary C: `homing_missile` (missile, 4-frame)
- kind: missile, 4-frame strip, 16×16 per cell, white_missile
- Prompt fills: "homing missile with exhaust trail, 4-frame strip, thrust pulse animation"

### Canary D: `thrown_dagger` (melee_thrown, 4-frame rotation)
- kind: melee_thrown, 4-frame strip, 16×16 per cell, brown_dagger
- Prompt fills: "thrown dagger, 4-frame rotation animation, 0°/90°/180°/270°"

### Canary E: `grenade_fuse` (explosive, 4-frame)
- kind: explosive, 4-frame strip, 16×16 per cell, grey_bomb
- Prompt fills: "grenade with lit fuse, 4-frame strip, fuse-flicker animation"

### Canary F: `contra_spread_shot` (gun_proj, single-frame, enemy-variant)
- kind: gun_proj, single-frame, 8×8, red_energy
- Prompt fills: "enemy red energy pellet, 8×8 pixel tiny, centered on magenta"

## Honest limits

- **Size mismatch**: ERNIE canvas is 1024² but output target is 8×8 or
  16×16. Most pixels wasted. Acceptable for a workflow-cost perspective
  (turbo Turbo ERNIE generates in ~20s; the waste is irrelevant).
- **Pixel-art consistency**: ERNIE sometimes produces painted/smooth
  output despite "pixel-art" prompts. Postprocess includes an optional
  `pixelize` pass using ERNIE's `/v1/images/pixelize` endpoint for
  cleanup.
- **Directional variants**: only E-facing sprites produced. Runtime
  flip + rotate for N/S/W/diagonal. Saves 4-8× sprite-gen budget.
- **Animation smoothness**: 4-frame travel animations can have
  frame-to-frame discontinuities. Postprocess includes an optional
  `align_frames` pass that re-centers all 4 cells around the projectile's
  detected center-of-mass to reduce judder.
