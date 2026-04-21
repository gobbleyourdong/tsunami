# item_icons — ERNIE prompt template

Unified STATIC icon workflow covering three item categories — **weapons**,
**consumables**, **equipment (armor)** — with one shared template and
per-category defaults. The unified workflow exists because all three
share the same geometry (compact centered subject, shoulders-up scale,
magenta chromakey, small canvas) and differ only in subject vocabulary
and canvas default.

Covers Shoal plan categories:
- **cat. 39** — weapon icons (8 baseline: sword, axe, bow, staff, dagger, spear, gun, shield)
- **cat. 40** — consumable icons (8 baseline: potion-r/b/g, food, coin, gem, key, scroll)
- **cat. 41** — equipment icons (7 baseline: helmet, chest-plate, gloves, boots, cloak, amulet, ring)

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA).
  `keep_largest_only=True` — items are compact single-subject silhouettes.
- **Canvas:** 512×512 for gen; downscale to 128×128 or 256×256 per-category
  (see `anim_set.json::categories.*.out_px`).
  Generating at 512 and downscaling gives sharper icons than generating at
  target size — ERNIE has more room to detail the subject.
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** one seed per (category, subject) pair, pinned in
  `anim_set.json::subjects`. Stable catalog across regenerations.

## The template

```
single <item_kind> icon, <subject_description>, <style_variant>,
centered in frame filling roughly 75 percent of the canvas, isolated
against a solid magenta #FF00FF background, no background objects, no
props, no characters, no ground, no shadow, 3/4 front-facing product-shot
angle, bold readable silhouette, clean cel-shaded colors with one-light
rim highlight from upper-left, crisp edges, saturated colors, no
antialiasing bleed into the magenta, no text, no border, no watermark,
<style_modifiers>
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<item_kind>` | category anchor word | `fantasy sword weapon`, `healing potion consumable`, `plate armor helmet piece of equipment` |
| `<subject_description>` | specific design | `longsword with a crossguard and leather-wrapped grip, polished steel blade with a blood groove`, `round glass flask with a cork stopper filled with swirling red liquid, small label tied with string`, `knight helmet with a full-face visor and a plume crest on top, burnished silver with gold trim` |
| `<style_variant>` | overall visual register | `Diablo-II-style dark fantasy inventory art`, `Stardew-Valley-style warm cartoon with pixel-art feel`, `Hollow Knight-style inky monochrome`, `Zelda-LttP-style 16-bit SNES pixel art` |
| `<style_modifiers>` | per-scaffold flavor | `gritty weathered textures`, `bright saturated primary colors`, `cool blue palette with silver highlights`, `warm orange palette with bronze accents` |

### ERNIE rules baked in

- **3/4 front-facing product shot** is the default because pure-profile
  icons lose detail at icon scale. Named because the model understands
  "product shot" as clean studio lighting + centered subject.
- **No shadow** — icons are UI elements; engine overlays its own shadow
  if it wants one. Same anti-shadow discipline as every other workflow.
- No literal quotes in the prompt.
- `use_pe=false`.

## Scale targets

| Category | gen_px | out_px | rationale |
|---|---|---|---|
| weapon | 512 | 256 | visible craft detail (engraving, hilt wrap, arrow fletching) |
| consumable | 512 | 128 | small UI slots; simple shapes don't need much resolution |
| equipment (armor) | 512 | 256 | same as weapons — craft detail matters |

## Call-count budget

- **Full baseline library** (8 weapons + 8 consumables + 7 equipment = 23
  icons): 23 calls × ~8 s = **~3 min single-pipe, ~2 min with 3× pool**.
- Canaries here cover 3 icons (one per category) to prove the workflow;
  the full 23-icon batch ships on a later round as a dedicated library
  build.
