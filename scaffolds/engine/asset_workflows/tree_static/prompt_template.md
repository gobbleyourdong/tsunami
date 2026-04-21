# tree_static — ERNIE prompt template

Static tree sprites for world decoration. Ships with 5 species
(`oak`, `pine`, `palm`, `dead`, `cherry_blossom`) × 2 projections
(`top_down` orthographic overhead, `iso_side` 3/4-view).

No animation by default — trees are backdrop/world-decor. A
`wind_sway_loop` 8-frame variant lives as an OPTIONAL-ANIM sub-workflow
(see `anim_set.json::optional_anims.wind_sway`); most scaffolds don't
need it and engines that do want swaying can apply a CSS/shader transform
at runtime cheaper than a per-frame gen.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA). Trees are
  compact-silhouette subjects — `keep_largest_only=True` is the right
  default (single connected blob).
- **Canvas:** 1024×1024, tree occupying ~70% of the frame.
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pinned per (species, projection) for reproducibility and
  catalog stability (see `anim_set.json::species[*].seeds`).

## The template

```
single <species> tree, <projection_phrase>, full tree from base of
trunk to top of canopy, centered in frame, isolated against a solid
magenta #FF00FF background, no ground plane, no shadow cast on
background, no other foliage, no rocks, no props, bold readable
silhouette, clean cel-shaded colors with natural variation, crisp
edges, natural <species_palette>, no text, no border, no watermark,
<style_modifiers>
```

### Placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<species>` | tree kind | `mature oak with broad rounded canopy`, `tall straight pine with layered conical canopy`, `tropical palm with curving trunk and fanned fronds at top`, `dead leafless skeletal tree with exposed branches`, `cherry blossom with dense pink-white flowered canopy` |
| `<projection_phrase>` | camera geometry | `orthographic top-down overhead view, seen directly from above, showing the round canopy silhouette with the trunk partially visible underneath` / `three-quarter isometric side view at 30° elevation, full profile visible with trunk and canopy clearly separated` |
| `<species_palette>` | species-appropriate colors | `deep forest green canopy with brown bark, slight color variation across leaves`, `blue-green needle clusters with brown-gray bark`, `yellow-green fronds with ringed brown trunk`, `gray branches with dark weathered bark, no leaves`, `pale pink and white blossoms with dark brown bark visible through gaps` |
| `<style_modifiers>` | per-scaffold flavor | `painterly hand-drawn with visible strokes`, `clean vector flat-colors`, `pixel-art with visible pixels and limited palette`, `photo-realistic but flat lit` |

### ERNIE rules baked in

- `no ground plane, no shadow cast on background` — same lesson as
  side_scroller (asking for shadow produces purple chromakey residual).
- No literal quotes in the prompt.
- `use_pe=false`.

## Scale targets

- Canvas: 1024×1024, tree ~70% of the frame (≈ 700×700 effective).
- Final per-sprite size after alpha-crop: 128×192 (platformer),
  192×288 (iso top-down RPG), or 256×384 (modern high-DPI).

## Species × projection catalog

Per `anim_set.json::species`: 5 species × 2 projections = **10 sprites**
baseline. Each is one ERNIE call. Full catalog = 10 calls / ~1.5 min
single-pipe.

Scaffolds that need other species (dogwood, birch, willow, redwood,
joshua_tree, coconut_palm, etc.) add entries with the same template,
a pinned seed, and species-appropriate palette — the template is
open-vocabulary on `<species>`.
