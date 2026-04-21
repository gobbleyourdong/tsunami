# vfx_library — ERNIE prompt template

The VFX library is a **pre-rendered catalog** of 20 canonical effects that
scaffolds pull from directly rather than regenerating per-project. Each
VFX is a short animation sequence (1–12 frames) generated per-frame
following the pattern proved out in `side_scroller_character` —
grid-prompting does not produce animation phases.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA) for the great
  majority of VFX; a handful (scene-baked fire, photoreal-smoke) use
  `photo` and get explicit chromakey at postprocess time instead.
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** one seed per (vfx_name, frame_index) so the whole sequence is
  reproducible. Frames within the same VFX share the seed's low bits —
  each frame's prompt handles the visual progression, not the sampling
  randomness.

## Production pattern — per-frame generation

For a VFX with N frames:

1. Look up `anim_set.json::vfx[<vfx_name>].frames` for the per-frame
   `pose_description` array.
2. Fire N ERNIE calls (one per frame). Each call uses the shared
   `<vfx_name>` prompt fragment plus that frame's specific
   `<frame_description>`.
3. Postprocess crops each result to its alpha bounding box and stacks
   them into a horizontal spritesheet.

This is the same per-frame pattern `side_scroller_character` uses. The
difference: VFX have no consistent-character-identity constraint, so
parallel pipelines can be used aggressively — any frame is standalone.

## The template (per frame)

```
2D game VFX sprite of a <vfx_name>, <frame_description>, <anim_phase>
phase of the effect, centered on a solid magenta #FF00FF background, no
background objects, no ground plane, no depth cues other than the
effect itself, pure standalone effect sprite with alpha cutout intent,
bold readable shapes, saturated <color_palette>, <style_modifiers>, no
text, no border, no watermark, no cast shadow on background
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<vfx_name>` | the effect kind | `circular impact burst`, `ring shockwave`, `diagonal sword slash`, `lightning bolt arc`, `healing pulse aura`, `poisoning drip cloud`, `sparkle twinkle`, `flame flicker` |
| `<frame_description>` | per-frame appearance | `thin starting radial, 10% diameter, bright white core`, `peak radial at 80% diameter, full brightness`, `fading halo at 100% diameter with 40% opacity`, `final wisp at 120% diameter, 10% opacity` |
| `<anim_phase>` | narrative phase tag (for model context) | `startup`, `peak`, `decay`, `dissipation`, `loop` |
| `<color_palette>` | emissive color prescription | `white-hot core with yellow and orange falloff`, `deep crimson with dark red shadows`, `teal-to-cyan gradient`, `emerald green with soft gold highlights`, `violet with magenta bleed — avoid pure #FF00FF chroma in the effect itself` |
| `<style_modifiers>` | per-scaffold flavor | `cel-shaded with 3-level gradient`, `pixel-art, each pixel visible, no antialiasing`, `neon-glow with hard core and soft halo`, `gritty hand-painted with visible brush strokes` |

### ERNIE rules baked in

- **Avoid literal #FF00FF in the effect itself.** The chromakey drops
  anything matching the magenta background; an effect whose color is
  meant to be magenta will eat its own alpha. `<color_palette>` specs
  call out "avoid pure #FF00FF chroma" to bias the model away.
- No literal quotes in the prompt.
- `use_pe=false`.
- No alpha composites.

## Scale targets

- Canvas: 1024×1024, effect centered and filling 50–90 % of the frame
  depending on its size at peak.
- Final per-frame size after alpha-crop + downscale: 64×64 (pixel-art
  VFX layer), 128×128 (standard game), or 256×256 (high-DPI).

## Full library call budget

Per `anim_set.json::ernie_call_count.total`: **~170 calls** for the full
20-VFX library at the declared frame budgets (1 shipped spritesheet per
VFX). At 9 s / Turbo call on a single pipeline that's ~25 min wall-clock;
with 3 parallel pipelines it's ~8–9 min.

The first 3 canaries (see `canary_prompts.jsonl`) validate the pipeline.
The remaining 17 VFX are batch-rendered on demand — this workflow
directory ships the catalog and the canary seeds but NOT the 17 full
spritesheets, to keep the repo clean. Run `fire_vfx_library_full.py` (in
`~/shoal_scratch/notes/` when it exists) to build the full library on
demand.
