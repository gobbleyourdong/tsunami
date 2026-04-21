# tileable_terrain — ERNIE prompt template

Seamless tileable ground textures for top-down / isometric terrain layers.
One ERNIE call per base material. The output is a 1024×1024 "tile sheet"
that `postprocess.slice_to_tile(source_px, tile_px)` samples into 64×64
or 128×128 tile units for the engine's tile layer.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `photo` (NO chromakey — backgrounds are the whole image;
  textures are flat colorfields, there is nothing to remove)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** **one seed per base-tile and pin it.** Re-rolling the seed
  breaks tileability because ERNIE doesn't have a seamless-tile prior —
  seamlessness comes from *sampling a small square out of a larger
  generated region where the center has no obvious composition cues*, not
  from the model knowing about tileability. A pinned seed that produced a
  good tile center should be remembered per-material in `anim_set.json`
  (yes, even though there's no anim — the metadata table is the shared
  schema for all workflows).

## The template

```
seamless tileable repeating ground texture of <material>, top-down
orthographic overhead view, uniform even lighting with no directional
shadows or gradient, no cast shadows, no distinct large features or focal
points, uniform density of <material> across the entire frame, edge-to-edge
continuous pattern that would repeat without visible seams, natural
<material> color palette, high detail at pixel scale, photographic
realism but flat lit, <style_modifiers>
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<material>` | the terrain substance | `dense green grass blades`, `mossy gray flagstone pavement`, `fine golden sand`, `shallow rippling clear water`, `fresh untouched snow`, `molten orange lava with dark crust`, `packed brown dirt with small pebbles`, `loose multi-colored gravel`, `wooden plank flooring with visible grain`, `polished ceramic floor tiles`, `red-orange clay brick pavement`, `thick emerald moss ground cover` |
| `<style_modifiers>` | per-scaffold flavor | `saturated cartoon look`, `grimdark desaturated`, `photoreal with subtle AO`, `pixel-art friendly with clear color blocks` |

### ERNIE rules baked in

- `mode=photo` — there is no magenta chromakey; backgrounds are the
  content and there is nothing to extract.
- No literal quotes in the prompt.
- `use_pe=false`.
- No reference composites; the output IS the tile source.

## Seamlessness discipline

The model is NOT trained on tileable textures. "Seamless tileable" in the
prompt is a style hint, not a constraint. Seamlessness is enforced
**post-generation** by the pipeline:

1. Generate the 1024×1024 field.
2. `postprocess.sample_tile_center(field, tile_px, seam_pad_px=16)` —
   samples a `(tile_px + 2*seam_pad_px) × (tile_px + 2*seam_pad_px)`
   patch from the geometric center of the field (maximum distance from
   composition-biased edges).
3. `postprocess.feather_edges(patch, feather_px=16)` — applies a
   radial-cosine alpha feather on the outer `seam_pad_px` so the tile's
   own edges blend naturally against a wrapped-around neighbor.
4. `postprocess.verify_tileable(patch)` — pastes the patch 3×3 in a grid
   and saves to `canary_tile_wrap_<material>.png`. Eyeball for seams;
   if visible, regenerate with a different seed.

Manual verify is the ground truth here — no automated seam metric is
reliable enough to ship as a gate.

## Scale targets

- Source field: 1024×1024, full-frame texture.
- Tile output: 64×64 (classic 16-bit RPG) or 128×128 (modern top-down).
- Feather padding: 16 px on the 1024 source before sampling.

## Suggested base-material set (per Coral's gap and Shoal plan cat. 30)

`grass`, `stone`, `sand`, `water`, `snow`, `lava`, `dirt`, `gravel`,
`wood-plank`, `tile-floor`, `brick`, `moss`. 12 textures for the baseline
engine tileset library; more can be added per-scaffold (e.g., volcanic
rock, ice, cloud, crystal, marble, tentacle-flesh, tech-panel).
