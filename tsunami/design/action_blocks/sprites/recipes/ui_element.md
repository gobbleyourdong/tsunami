# ui_element — generation recipe

## Style prefix

```
pixel art UI element, single game interface asset, flat design, clean
geometric shapes, solid magenta #FF00FF background, centered, high
contrast edges, sharp pixels, 16-bit game menu aesthetic, minimal
shading, bold outlines,
```

Notes:
- "flat design" + "minimal shading" steers away from Z-Image's
  default "ornate 3D bevels" tendency
- "game menu aesthetic" is more specific than "UI"; narrows the model
  to retro-GUI style rather than web-app-button style
- Solid magenta bg essential for clean alpha extraction (UI must
  composite cleanly over variable game backgrounds)

## Negative prompt

```
realistic, photographic, 3d rendered, glossy, gradient, blurry, soft,
anti-aliased, lens flare, bokeh, text, label, icon with letters,
decorative serif, ornate filigree, baroque, cluttered, busy background,
perspective, isometric, skeuomorphic, multiple elements, set
```

"icon with letters" is important — the model LOVES to put "A" or
"OK" on buttons unprompted, which is useless (we want naked icons).

## Default generation settings

- `gen_size: (512, 512)` — generate square, crop/scale later
- `variations: 3`
- `target_size: (64, 32)` — default; varies per asset (see metadata)
- `palette_colors: 6` — UI is intentionally low-color for clarity
- `backend: z_image` — Z-Image's flat-design output is cleaner than
  ERNIE's on pixel-art UI elements

## Post-processing chain

1. `pixel_extract` (existing) — magenta bg removal, clean alpha
2. `isolate_largest_object` (existing) — UI is single element
3. **`flat_color_quantize`** (new op; architecture thread adds) —
   reduce to `palette_colors` count using median-cut or octree
   quantization. UI benefits from aggressive quantization (fewer
   colors = clearer).
4. `trim_transparent` (existing)
5. **`nine_slice_detect`** (new op; architecture thread adds;
   only for `metadata.is_nine_slice: true`) — analyze the element
   for a 3×3 logical grid. Write out `metadata.nine_slice: [top,
   right, bottom, left]` as px offsets from each edge where the
   stretchable middle starts. Used by the engine's UI system to
   stretch panels without distorting corners.
6. `pixel_snap` to `target_size` with aspect-preserve

## Scorer

New scorer: `ui_element_scorer`. Weighted criteria:
- **Flatness** (fraction of opaque pixels that fall into ≤ 6 colors
  after quantize without significant error) — 35%
- **High contrast** (color-distance between main element and its
  bg/outline ≥ threshold) — 25%
- **Clean edges** (jagged-pixel count / edge-pixel count is low —
  looks like sharp pixel art, not smoothed) — 20%
- **Centering** (for non-nine-slice elements) — 10%
- **Opacity** (40% < opaque < 95%; too full = box, too empty =
  bad gen) — 10%

Nine-slice elements score differently: centering is skipped, aspect-
match to `target_size` is weighted +20%.

## Example prompts (3+)

1. `pixel art HUD health bar, horizontal, red liquid fill, dark outline
   frame, empty right side`
2. `pixel art menu button, rectangular, pressed state, subtle shadow,
   solid color fill`
3. `pixel art dialog box panel, 9-slice ready, simple border, 1-pixel
   highlight on top-left edges`
4. `pixel art inventory slot, square, subtle rounded corners, darker
   center, bright highlight top`
5. `pixel art score icon, star shape, yellow, black outline, clean`
6. `pixel art map marker, circular pin, red with white outline ring,
   target-like`

## Metadata schema

```ts
{
  role: 'button' | 'panel' | 'icon' | 'bar' | 'frame' | 'cursor'
      | 'marker' | 'indicator',
  is_nine_slice: boolean,           // true for panels, frames, buttons
                                     // that stretch to content size
  state: 'default' | 'hover' | 'pressed' | 'disabled' | string,
                                     // for buttons; null for icons
  target_aspect: '1:1' | '2:1' | '4:1' | '1:3' | string,
                                     // hints at target_size ratio
}
```

For nine-slice elements, `target_size` represents the **base cell
size** — engine uses `nine_slice` metadata to compute stretch regions.

## Common failures + mitigations

1. **Gradient fills appear despite "flat"** (Z-Image defaults to
   subtle gradients on buttons) → `flat_color_quantize` to 6 colors
   forces discretization. Visual cost: slight banding, but aesthetic-
   appropriate for retro UI.
2. **Unprompted text on icons** (model adds "A" or "1" to buttons) →
   strong negative "icon with letters" + reject variations that
   score-flag has text-shaped high-frequency regions. Last resort:
   manual curation.
3. **Too detailed / baroque** (model generates ornate filigree on
   "simple frame") → "minimal shading, bold outlines" in prefix;
   negative "ornate filigree, baroque". Still ~20% failure rate; best-
   of-N.
4. **Nine-slice detection fails** (panel has asymmetric sides that
   can't cleanly decompose into 3×3) → defer nine-slice detection to
   asset-curation time; scorer penalizes but doesn't reject outright.
   Fix by re-prompting with more explicit "symmetric frame, all four
   sides identical."
5. **Aspect ratio wrong** (asks for horizontal bar, gets square
   element) — generate at 512² then force-crop to target aspect in
   post-proc rather than asking the model for non-square aspects.

## Handoff notes

- `flat_color_quantize` is a new op. Implementation: PIL's
  `quantize(colors=N)` followed by palette mapping.
- `nine_slice_detect` is a new op; stretch-goal for v1.1.
  Implementation: analyze the 4 corners + 4 edge-middles + center for
  color-stability; compute the boundary pixels. v1.0 can ship without
  nine-slice auto-detect; authors supply metadata manually.
- UI elements compose heavily with the engine's `HUD` + `DialogTree`
  mechanics from action-blocks v1.0.3 — palette_MAP should reference
  this.
