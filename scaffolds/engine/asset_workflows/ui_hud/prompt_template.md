# ui_hud — ERNIE prompt template

Unified STATIC UI workflow covering three HUD categories:
- **cat. 46** — HUD frame / panel (9-sliceable for stretchable panels)
- **cat. 47** — Button / widget (state variants: idle / hover / active / disabled)
- **cat. 48** — Health bar / resource meter (static base + optional animated fill)

One shared prompt template; per-category canvas + state in `anim_set.json`.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA)
- **Canvas:** 512×512 by default; panels/bars sometimes use 512×192
  rectangular gens to match output aspect (see `anim_set.json`).
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** one seed per (kind, subject, state). State variants of the
  same subject share the character-level base seed with small offsets
  so hover/active/disabled versions look like the same button in
  different states, not three different buttons.

## The template

```
2D game UI element, <kind_description>, <subject_description>,
<state_description>, centered in frame, isolated against a solid
magenta #FF00FF background, no background scene, no 3D depth, flat
clean UI art, <style_variant>, <style_modifiers>, bold readable
silhouette, crisp 1-pixel edges, saturated colors, no antialiasing
bleed into the magenta, no text labels or words on the element, no
border, no watermark
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<kind_description>` | broad category anchor | `a decorative HUD panel frame suitable for 9-slice stretching`, `a circular menu button`, `a horizontal health bar with an empty container and a fill region` |
| `<subject_description>` | specific visual design | `fantasy stone-and-wood frame with metal rivets at the corners and a filigree border`, `rounded rectangular button with a soft gradient and a glossy highlight on top half`, `rectangular hp bar container shaped like a scroll with ornate end-caps` |
| `<state_description>` | state variant cue (buttons only; pass empty for panels/bars) | `at rest in the default idle state, subtle normal lighting`, `on hover state with a subtle brighter outer glow and slightly lifted shadow`, `active pressed state pushed down by 2 pixels with a slightly darker color`, `disabled state desaturated to gray with reduced opacity` |
| `<style_variant>` | overall visual register | `fantasy RPG UI with carved wood and metal textures`, `sci-fi cyberpunk UI with neon edges and dark panels`, `minimalist flat design with crisp geometric shapes`, `pixel-art UI with visible pixels and a limited 16-color palette` |
| `<style_modifiers>` | per-scaffold flavor | `warm brown-and-gold palette`, `cool cyan-and-black palette`, `muted neutral grays with one accent color`, `high-contrast with black inner borders` |

### ERNIE rules baked in

- **No text labels on the element.** Every prompt says "no text, no
  words." Scaffolds render button labels / bar values via DOM / canvas
  overlay at runtime — ERNIE's text rendering is unreliable and would
  make the button say `"IDLE"` if given a chance.
- **No shadow baked in** (same as item_icons and every other Shoal
  workflow). UI shadows are a CSS/engine concern.
- No literal quotes; `use_pe=false`.

### 9-slice discipline (cat. 46 specifically)

For HUD panels that need to stretch to variable sizes:

- Generate at 512×512 with `kind_description` saying "suitable for
  9-slice stretching".
- Crop to 4 corners + 4 edges + 1 center = 9 regions before shipping.
  `postprocess.slice_9slice(src, out_dir, corner_px=64)` produces 9
  separate PNGs (tl/t/tr/l/c/r/bl/b/br) that the engine assembles at
  any target size.
- Alternative: ship the single 512×512 source plus the 4 corner/edge
  coordinates in a manifest; the engine's 9-slice renderer consumes
  those directly (Phaser, Pixi, Godot all support this).

## Scale targets

| Category | gen_w × gen_h | out_w × out_h |
|---|---|---|
| panel | 512 × 512 | 256 × 256 (square) or 384 × 192 (wide banner) — 9-slice supports any |
| button | 512 × 512 | 192 × 192 (square) or 256 × 96 (pill) |
| health bar | 512 × 192 | 384 × 64 (standard) or 256 × 32 (compact) |

## Call-count budget

- 1 HUD panel: **1 call** (9-slice is pure postprocess; no ERNIE for slicing).
- 1 button × 4 states: **4 calls** (one per state, shared-base seed).
- 1 health bar: **1 call** (or 2 if you want an animated-fill variant).
- Full minimal HUD set for one scaffold (1 panel + 1 button × 4 states +
  1 bar): **6 calls** / ~4 s wall-clock with 3-ERNIE pool.
