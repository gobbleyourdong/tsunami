# background — generation recipe

## Style prefix

```
pixel art game background layer, wide horizontal composition, parallax-
ready, no centered subject, no characters, no foreground objects,
horizontally tileable left-to-right, top-down or side-view horizon
line, solid magenta #FF00FF sky or bottom-edge alpha, clean pixel
edges, 16-bit style,
```

Notes:
- "wide horizontal composition" plus `gen_size: (1024, 512)` enforces
  2:1 aspect at generation time (Z-Image honors aspect ratio reliably).
- "horizontally tileable" is the key — parallax backgrounds loop as
  the camera scrolls; left edge must match right edge.
- "no centered subject" avoids the model's default "put a castle in
  the middle of every background."

## Negative prompt

```
centered subject, character, enemy, player, hero, foreground object,
isolated building, prominent tree, obvious focal point, vertical
composition, portrait aspect, 3d, photo, realistic, blurry, soft,
anti-aliased, gradient background, text, watermark, border, frame,
cropped, signature, different left and right edges
```

"different left and right edges" is prompt-engineering-hail-mary —
doesn't always work, but marginally improves seamless-horizontal.

## Default generation settings

- `gen_size: (1024, 512)` — 2:1 wide aspect, Z-Image's strongest for
  landscape compositions
- `variations: 3` — backgrounds have less to fail than characters; 3 is enough
- `target_size: (512, 256)` — 2:1 aspect preserved; 512 wide is the
  typical parallax-layer resolution in WebGPU scenes
- `palette_colors: 16`
- `backend: z_image` — Z-Image strong at landscape; ERNIE tends to add
  figures even when prompted not to

## Post-processing chain

1. `pixel_extract` (existing) — handles top-edge sky or no-bg scenes;
   for backgrounds with sky, the magenta-sky prompt token yields
   clean alpha there
2. **`horizontal_tileable_fix`** (new op; architecture thread adds) —
   compare leftmost 8px column to rightmost 8px column. If RGB delta
   is high, blend them via linear crossfade over the outer 16px on
   each side. Not always clean but mitigates obvious seams.
3. `pixel_snap` to `target_size` (existing)
4. **`parallax_depth_tag`** (new op; stretch, architecture thread
   marks v2) — estimate depth-of-field or near/mid/far based on color
   saturation + spatial frequency. Writes `metadata.parallax_depth:
   'near'|'mid'|'far'`. Useful for auto-assembling 3-layer parallax
   without author effort. v1 scope: skip (let author assign).

No `isolate_largest_object` (the "subject" IS the whole background).
No `center_crop_object`.

## Scorer

New scorer: `background_scorer`. Weighted criteria:
- **Aspect fidelity** (output matches 2:1 or author-specified) — 10%
- **Seamless horizontal** (L/R edge RGB delta < threshold) — 35%
- **No dominant subject** (center 25% of frame should NOT be the
  color-peakest region) — 20%
- **Opacity** (at least 60% opaque — no giant alpha holes) — 20%
- **Color diversity** (≥ 10 unique colors) — 15%

Explicitly does not score "centering" (inverted from character/item).

## Example prompts (3+)

1. `pixel art forest background layer, morning light, distant
   mountains, silhouette trees, cloudy sky`
2. `pixel art city rooftop background, night, neon signs, windows lit,
   distant skyscraper silhouettes, starry sky`
3. `pixel art cave wall background, dark, stalactites, luminous
   crystals, dripping water highlights`
4. `pixel art desert dune background, sunset, orange sky, silhouette
   cactus, wind-ripple sand texture`
5. `pixel art underwater background, kelp forest silhouette, rays of
   sunlight from above, bubble streams, distant fish`

## Metadata schema

```ts
{
  layer: 'near' | 'mid' | 'far',    // parallax depth; author-assigned
  time: 'day' | 'dusk' | 'night' | 'dawn' | 'overcast',
  biome: 'forest' | 'city' | 'cave' | 'desert' | 'underwater' | 'space' | string,
  tileable_horizontal: boolean,      // author intent; enforced by post-proc
  tileable_vertical: boolean,        // rare but possible (endless-sky effect)
}
```

## Common failures + mitigations

1. **Model puts a character or focal object in center** (most common
   — 30%+ rate despite negative prompt) → `no_dominant_subject`
   scorer catches; best-of-N selects the non-subject variant. If all
   variations fail, escalate to operator (prompt may need domain-
   specific softening).
2. **Left/right edges don't match** (50%+ without mitigation) →
   `horizontal_tileable_fix` blends. Still-visible seam = acceptable
   on far-parallax layers (player doesn't notice); unacceptable on
   near-layers. Score + reject if near + seam visible.
3. **Sky reads as bg for alpha** but hills/ground don't → that's
   correct: parallax backgrounds typically want opaque terrain +
   transparent sky (for layering over solid color). The magenta-sky
   prompt token is load-bearing.
4. **Too painterly / not "pixel"** (Z-Image sometimes defaults to
   landscape-painting aesthetic on biome prompts) → double-down on
   "pixel art, sharp pixel edges, no anti-alias" in prefix; reject
   variations with low color-count-quantization.
5. **Resolution too low for detail** (512 wide is sparse at far-
   distance mountains) → recipe target 1024 gen → 512 final; post-
   quantize to 16 colors forces pixelation visibly.

## Handoff notes

- `horizontal_tileable_fix` is a new op. Implementation: 16-column
  linear crossfade between L and R edges.
- `parallax_depth_tag` is v2.
- Backgrounds are typically less-critical than characters for game-
  feel; if this category has low success rate, author-curation (pick
  best of N) works at build time.
