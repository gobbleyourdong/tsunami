# portrait — generation recipe

## Style prefix

```
pixel art character portrait, head and shoulders close-up, eyes
clearly visible, facing forward or three-quarter view, solid magenta
#FF00FF background, centered head, expressive face, clean silhouette,
sharp pixel edges, 16-bit JRPG dialog portrait style,
```

Notes:
- "head and shoulders close-up" is the anti-full-body prompt —
  critical to distinguish from `character` recipe
- "16-bit JRPG dialog portrait style" specifically references FF6 /
  Chrono Trigger style — Z-Image has strong prior for this, yields
  clean outputs
- "eyes clearly visible" — dialogue portraits communicate emotion via
  eyes; without this, model sometimes closes them or shadows them

## Negative prompt

```
full body, legs, feet, arms visible, weapon, inventory, background
scenery, multiple faces, group portrait, tiny face in large frame,
blurry, soft, anti-aliased, photographic, 3d render, realistic,
anime gradient shading, painted background, text, speech bubble,
name plate, caption, border decoration
```

"anime gradient shading" is specific — Z-Image on "anime portrait"
produces soft gradients which are wrong for retro-pixel. "16-bit"
forces palette-limited shading.

## Default generation settings

- `gen_size: (512, 512)` — square generation, square output
- `variations: 4`
- `target_size: (128, 128)` — larger than character sprite since
  portraits show more detail per-pixel (typical SNES JRPG sprite 64×64
  → portrait 48×48 to 64×64; we go bigger for modern displays)
- `palette_colors: 20` — faces benefit from more colors than items
  (skin gradient + hair shadows + eye color + outline + etc.)
- `backend: ernie` preferred for portraits — ERNIE tends to produce
  more expressive faces; fallback `z_image` if ERNIE unavailable. Note
  that ERNIE constants are steps=8, CFG=1.0, 1024², `use_pe=false`
  per memory.

## Post-processing chain

1. `pixel_extract` (existing) — magenta bg removal
2. `isolate_largest_object` (existing) — single subject
3. **`eye_center`** (new op; architecture thread adds) — detect eye
   positions via high-contrast dark-on-skin pixel cluster near upper
   third of sprite. Re-center output so eyes are at ~35% from top,
   centered horizontally. Reduces author jitter from frame to frame
   when portraits vary.
4. **`head_only_crop`** (new op; architecture thread adds) — if the
   generated sprite shows below-shoulders, detect the
   shoulder-to-neck transition (vertical color-saturation drop) and
   crop to just above it. Keeps portraits tight.
5. `trim_transparent` (existing)
6. `pixel_snap` to `target_size` with aspect-preserve

## Scorer

New scorer: `portrait_scorer`. Weighted criteria:
- **Eye detection** (2 distinct high-contrast spots in upper third of
  opaque region) — 30%
- **Head proportion** (detected-head-height / total-height ≥ 0.75 —
  not too much below-shoulders) — 20%
- **Centering** (horizontally centered face within 5%) — 15%
- **Color-palette coherence** (skin tone + hair tone + clothing tone
  visible as distinct color bands) — 15%
- **No text / decoration** (no letter-shaped pixel regions) — 10%
- **Clean silhouette** (outer edge is single connected path, not
  fragmented) — 10%

## Example prompts (3+)

1. `pixel art portrait of a wise old wizard, white beard, blue robes,
   kind eyes, warm expression`
2. `pixel art portrait of a young warrior woman, red hair, leather
   armor, determined expression, scar on cheek`
3. `pixel art portrait of a merchant, round face, green vest, smiling,
   warm brown eyes, rosy cheeks`
4. `pixel art portrait of a shadow assassin, hood covering hair, pale
   skin, piercing blue eyes, mask covering lower face`
5. `pixel art portrait of an elven mage, pointed ears, silver hair,
   purple eyes, star-embroidered blue hood`
6. `pixel art portrait of a dwarven smith, braided red beard, leather
   apron, safety goggles pushed up, soot-smudged cheek`

## Metadata schema

```ts
{
  character_id: string?,            // links to archetype that uses this portrait
  emotion: 'neutral' | 'happy' | 'sad' | 'angry' | 'surprised'
         | 'determined' | 'fearful' | 'sly' | string,
  facing: 'front' | 'three_quarter_left' | 'three_quarter_right'
        | 'profile_left' | 'profile_right',
  age: 'child' | 'young_adult' | 'adult' | 'elder' | string,
  species: 'human' | 'elf' | 'dwarf' | 'orc' | 'beast' | 'undead'
         | string,
}
```

`emotion` and `facing` are typically set by the author's DialogTree
script: same character may have multiple portraits with different
emotions (`character_hero_neutral`, `character_hero_happy`, etc.).
Author pre-generates the emotion variants they want.

## Common failures + mitigations

1. **Full body instead of portrait** (model ignores "close-up" ~15%) →
   `head_only_crop` op post-processes. Scorer penalizes if below-
   shoulders is prominent.
2. **Eyes closed or shadowed** (portraits lose emotional read) → "eyes
   clearly visible" in prefix + scorer rejects variants where eye
   detection fails. Best-of-N recovers.
3. **Anime-style gradient instead of pixel shading** (default to
   smooth rendering) → "16-bit JRPG dialog portrait" + "sharp pixel
   edges" in prefix; negative "anime gradient shading". Z-Image is
   prone; ERNIE less so.
4. **Off-center face** (subject drifts left or right during
   generation) → `eye_center` op re-aligns.
5. **Text on portrait** (model adds nameplate or speech bubble
   occasionally) → strong negative + scorer penalizes.
6. **Race/species mismatch** (asks for elf, gets human with pointed
   ear barely visible) — prompt engineering limitation. More explicit
   features ("long pointed ears extending to top of head") help but
   not guaranteed.

## Handoff notes

- 2 new ops: `eye_center`, `head_only_crop`. Both use simple
  image analysis (color clustering + saturation gradient). No ML
  required.
- Portrait category should check for ERNIE availability and fall
  back to Z-Image gracefully. If both unavailable → error with
  actionable message.
- Portraits compose with `DialogTree` mechanic from action-blocks
  v1.0.3 — palette_MAP entries for "narrative-adjacent" and
  "narrative-RPG" should recommend portrait assets.
