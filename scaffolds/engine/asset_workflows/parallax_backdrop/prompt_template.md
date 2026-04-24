# parallax_backdrop — ERNIE prompt template

Multi-layer parallax-scrolling backdrops. One ERNIE call per layer
(single-layer = 1 call; 3-layer = 3 calls with pinned seed; mode7 = 2
calls). Shoal-spec'd by sister at INT-18; implemented by main after
Shoal went offline.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `photo` (no chromakey — backdrops are full-image, nothing
  to remove)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed strategy:**
  - **`parallax_single` / `skybox_static`** — pin one seed per backdrop.
  - **`parallax_3layer`** — pin the SAME seed across all 3 layer calls
    of one backdrop. Same biome-identity across layers (scale + density
    vary; palette stays coherent because ERNIE sampled same seed).
  - **`mode7`** — pin seed per track-biome; horizon and floor share it.

Seed sharing is the identity trick — ERNIE has no parallax-layer prior,
so coherence between far/mid/near is produced by same-seed sampling
with different prompts that describe detail-scale.

## The template

The template has 5 slots. Fill them per-backdrop:

```
A 2D game-art parallax-backdrop {layer_role}, side-scrolling {era}-console era.
Biome: {biome}. Time of day: {time_of_day}. Palette mood: {palette_mood}.
{layer_role_details}
Wide horizontal composition, meant to tile horizontally. No characters,
no enemies, no players, no UI. Pure scenic backdrop. Flat 2D scenic
painting or pixel-art painted look (match the era). No 3D-rendered
look. Sharp horizon / ground line / midline should be visible and
suitable for image tiling. No text.
```

### Slot fill examples

**parallax_far** (slowest, simplest):
- `{layer_role}` = "far-distance background layer"
- `{layer_role_details}` = "Very low detail density. Large shapes only: distant mountains / sky / horizon / silhouetted treeline. No individual details. Should look blurry or simplified from distance."

**parallax_mid** (medium depth):
- `{layer_role}` = "mid-distance parallax layer"
- `{layer_role_details}` = "Medium detail density. Small individual elements visible: distant trees, buildings, rock formations. No foreground grass or individual leaves."

**parallax_near** (foreground, fastest scroll):
- `{layer_role}` = "near-foreground parallax layer"
- `{layer_role_details}` = "High detail density. Foreground vegetation, detailed rocks, close-ups of terrain features. This is what the player's eye focuses on when scrolling — highly detailed but still background (no gameplay elements)."

**parallax_single** (NES-era single-layer):
- `{layer_role}` = "single-layer background"
- `{layer_role_details}` = "Simple pixel-art backdrop, unified scene (not layered). Represents an 8-bit game's single scroll-register capability."

**mode7_horizon** (upper band, static):
- `{layer_role}` = "Mode-7 horizon strip"
- `{layer_role_details}` = "Horizon + sky + distant silhouettes. Will be placed as a static upper-band behind the rotating floor. NO ground."

**mode7_floor** (lower band, rotates at runtime):
- `{layer_role}` = "Mode-7 tileable floor texture"
- `{layer_role_details}` = "Overhead top-down track surface — asphalt / grass / sand / ice. Tileable seamlessly. Pattern is detailed enough to read perspective when warped at runtime."

**skybox_static** (non-scrolling):
- `{layer_role}` = "static battle backdrop"
- `{layer_role_details}` = "Single-screen fixed backdrop — boss arena, battle scene, or JRPG combat backdrop. Central focal point. 256×224 aspect."

## Canary prompts

Three canonical backdrops for validation — one per mode:

### Canary A: Sonic green-hill parallax 3-layer

Seed: `SONIC_GREEN_HILL_01` (pinned across 3 calls).

- **far**: biome=`green_hill`, tod=`day`, palette=`vibrant`, slot `{layer_role_details}` = far-distance template.
- **mid**: same biome/tod/palette; `{layer_role_details}` = mid-distance template, mention "rolling checkered hills in the distance" (SNES Sonic signature).
- **near**: same triple; `{layer_role_details}` = near-foreground template with "grass tufts, loops, palm trees".

### Canary B: Raiden vertical single-layer

Seed: `RAIDEN_URBAN_MILITARY_01`.

- `parallax_single`: biome=`urban_night`, tod=`night`, palette=`cool_cyan`, with slot mention "top-down vertical-scroll military base — runways, buildings, antiaircraft installations viewed from above".

### Canary C: Super Mario Kart Mode-7 track

Seeds: `SMK_TRACK_GRASS_01` (floor) + `SMK_TRACK_HORIZON_01` (horizon).

- **mode7_horizon**: biome=`meadow_pasture`, tod=`day`, palette=`vibrant`. Slot mention "mountains and sky stretching to horizon".
- **mode7_floor**: biome=`meadow_pasture`, tod=`day`, palette=`vibrant`. Slot mention "grass texture with subtle dirt-patches, overhead-view, tileable seamless".

## Honest limits

- **ERNIE seam-handling**: same as `tileable_terrain` — ERNIE doesn't produce seamless tiles natively. `postprocess.seam_blend_edges(img, feather_px=16)` handles it. For `mode7_floor`, the seamless requirement is strict (runtime rotates + repeats); for horizontal-scroll layers, feather-blend on the left/right edges is enough.
- **Biome × palette combinatorics**: 20 × 5 × 10 = 1000 discrete backdrops achievable. Canary set covers 3; production fills the catalog over time.
- **Layer semantic coherence**: depends on seed-sharing. If the 3 layers don't look like same-biome at different distances, seed might not have produced a globally-coherent landscape. Re-roll strategy: try 2-3 seeds per biome+tod+palette, pick the most coherent triple.
- **Style-era lock**: `{era}` slot controls whether output looks NES-pixel-art or SNES-painterly or arcade-refined. Match to the anchoring essence per backdrop.
