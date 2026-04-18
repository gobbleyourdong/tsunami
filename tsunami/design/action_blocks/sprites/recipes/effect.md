# effect — generation recipe

## Style prefix

```
pixel art game effect, single visual effect sprite, bright glowing
core, radial symmetry, centered, solid magenta #FF00FF background,
high contrast, energetic composition, sharp pixels, 16-bit style,
animation key-frame peak-intensity moment,
```

Notes:
- "bright glowing core" + "radial symmetry" tell the model this is a
  RADIATING effect, not a scene — critical for
  explosions/magic/impacts
- "animation key-frame peak-intensity moment" — single-frame recipe,
  but this prompt token steers toward "mid-effect" visual rather than
  "just starting" or "just ending" which often looks like other
  categories
- The solid magenta is extra-important here because effects have
  complex edges that require clean alpha for later runtime additive-
  blend compositing

## Negative prompt

```
full scene, landscape, character, enemy, monster, weapon, realistic,
photo, 3d render, text, watermark, border, frame, multiple effects,
smoke trail stretched to edges, static object, inert, unlit, dark
center, cold, muted, subtle
```

"dark center, cold, muted, subtle" specifically negates Z-Image's
tendency to generate LESS intense effects than prompted.

## Default generation settings

- `gen_size: (768, 768)` — large enough for radial detail at center +
  wispy edges
- `variations: 5` — effects have more aesthetic variance than other
  categories; higher N gives authors more curation room
- `target_size: (96, 96)` — typical effect sprite size; between item
  (32) and character (64) as effects occupy more screen area
- `palette_colors: 24` — effects benefit from more colors (bright
  yellow core → orange → red → dark red → transparent) than UI/item
- `backend: z_image`

## Post-processing chain

1. `pixel_extract` (existing) — magenta bg removal
2. **`radial_alpha_cleanup`** (new op; architecture thread adds) —
   effects often have wispy/scattered edges that pixel_extract leaves
   with semi-transparent noise. This op: identifies the radial center
   via center-of-mass-of-luminance; feathers alpha from center
   outward smoothly; removes scattered pixels >R from center where R
   = 0.6 × max-radius.
3. **`preserve_fragmentation`** (new op; architecture thread adds) —
   normally `isolate_largest_object` throws away satellite pieces,
   but effects LEGITIMATELY have shards/sparks/debris. This op:
   retain fragments above size threshold (5% of max-blob-area) within
   radius R; reject fragments outside. Inverse of isolate_largest.
4. `trim_transparent` (existing) — but with generous padding (4px)
   since effects often have important wisps near frame edge
5. **`additive_blend_tag`** (new op; architecture thread adds) —
   mark alpha channel as suitable for additive blending (bright
   pixels stay opaque, dark pixels become semi-transparent). Stored
   in `metadata.composite_mode: 'additive'` for engine renderer.
6. `pixel_snap` to `target_size`

## Scorer

New scorer: `effect_scorer`. Weighted criteria:
- **Radial coherence** (center-of-mass-of-brightness matches geometric
  center within 10%) — 30%
- **Brightness range** (max luminance / median luminance ratio ≥ 3 —
  indicates clear core + periphery) — 25%
- **Color warmth / energy** (for fire/explosion types: R > G > B
  dominant; for magic: varies by metadata hint) — 15%
- **Coverage** (30% < opaque pixels < 85%) — 15%
- **No unwanted subject** (no character-shaped blob — reject if frag
  analysis finds human-silhouette-ratio blob) — 15%

Inverts item_scorer's centering (effects SHOULD be centered radially
but not subject-centered).

## Example prompts (3+)

1. `pixel art fire explosion, orange yellow red, scattered spark debris,
   peak moment, octagonal burst pattern`
2. `pixel art magic spell effect, blue and white, swirling mist
   converging to bright core, peak-intensity casting moment`
3. `pixel art lightning strike, white-hot core, jagged electric
   branches, ionized air glow`
4. `pixel art sword slash, diagonal white streak, motion smear, brief
   spark along edge`
5. `pixel art healing aura, green white, ascending light particles,
   soft radiant`
6. `pixel art poison cloud, dark green, skull-hint at core (negative:
   no actual skull), scattered noxious particles`
7. `pixel art impact flash, yellow white center, radial crack-pattern
   lines in 8 directions`

## Metadata schema

```ts
{
  type: 'explosion' | 'magic' | 'impact' | 'projectile_trail'
      | 'buff' | 'debuff' | 'environmental' | string,
  element: 'fire' | 'ice' | 'lightning' | 'nature' | 'arcane'
         | 'holy' | 'shadow' | 'poison' | 'physical' | string,
  composite_mode: 'normal' | 'additive' | 'screen' | 'multiply',
                                     // additive for glowing effects,
                                     // screen for soft auras,
                                     // normal for opaque splats
  loop_frame_hint: 'peak' | 'sustain' | 'fade',
                                     // for future animated variants;
                                     // v1 all are 'peak'
}
```

## Common failures + mitigations

1. **Effect is too subtle** (Z-Image generates "soft glow" when
   asked for "explosion") → "energetic composition, peak intensity"
   + negative "subtle, muted". Score brightness-range to reject.
2. **Scene instead of effect** (model generates "explosion in a city
   street") → solid magenta bg requirement in prefix forces isolation
3. **Fragmentation rejection kills valid effects** (standard
   isolate_largest throws away sparks that are legit part of effect)
   → `preserve_fragmentation` op specifically retains them within
   radius
4. **Alpha edges too hard** (makes additive blending look blocky) →
   `radial_alpha_cleanup` feathers outer edge; output suits additive
   blend mode
5. **Wrong element look** (prompted "ice spell" gets fire-colored
   effect) → color-warmth scorer catches by metadata.element hint;
   best-of-N typically recovers

## Handoff notes

- 3 new ops: `radial_alpha_cleanup`, `preserve_fragmentation`,
  `additive_blend_tag`. All three are architecturally simple
  (alpha manipulation, pixel distance from center). Architecture
  thread adds to ops table.
- `composite_mode` in metadata is READ by engine's VFX subsystem —
  additive-blended bright effects compose correctly over any game
  scene.
- Single-frame only per BRIEF.md scope; animated effects are future
  work (frame-set synthesis subsystem).
