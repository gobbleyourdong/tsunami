# top_down_character — ERNIE prompt template

Canonical top-down ARPG character sheet. Orthographic overhead, shadow directly
below the sprite's feet. Anchored on Zelda: A Link to the Past, Stardew Valley,
Hyper Light Drifter.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA via postprocess)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** one-seed-per-character-per-anim so re-runs land in the same identity
  lattice. Vary only the `<direction>` placeholder between passes.

## Output layout (what comes back from one ERNIE call)

One anim × one direction → one 1024×1024 sheet with an N-frame horizontal strip
packed into a 4×(N/4) or 2×(N/2) grid (postprocess slices). Multi-direction
anims fan out as N ERNIE calls, one per compass heading, then concatenated into
a vertically-stacked master sheet by `postprocess.py`.

## The template

```
top-down overhead sprite sheet of <character_name>, <style_variant>,
orthographic camera directly above, <direction>-facing,
<anim_name> animation cycle, <frame_count> evenly-spaced poses arranged in
a <grid_w>x<grid_h> grid on a solid magenta #FF00FF background,
each pose centered in its cell with consistent character identity,
soft circular ground shadow directly beneath the feet,
flat clean cel-shaded colors, readable silhouette, no text, no border,
no watermark, crisp edges, no antialiasing bleed into the magenta,
<style_modifiers>
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<character_name>` | subject identity + archetype | `young adventurer in green tunic`, `red-cloaked wizard with wooden staff`, `stoic knight in plate armor` |
| `<style_variant>` | overall visual register | `16-bit SNES pixel art`, `hand-drawn flat cartoon`, `hyper-light-drifter neon silhouette` |
| `<direction>` | compass heading | `north`, `east`, `south`, `west` |
| `<anim_name>` | animation state | `idle breathing`, `walk`, `run`, `light sword slash attack`, `heavy two-handed swing attack`, `hurt stagger`, `death collapse`, `interact reach` |
| `<frame_count>` | how many frames in this strip | `4`, `8`, `16` |
| `<grid_w>` × `<grid_h>` | frame layout | `4x4`, `2x4`, `8x1` |
| `<style_modifiers>` | per-scaffold flavor | `high-contrast palette, limited 16-color`, `soft pastel farmstead`, `grimdark desaturated` |

### ERNIE rules baked in

- No literal ASCII quotes inside the prompt — ERNIE renders them as glyphs.
- `use_pe=false` — `pe` (prompt enhancer) degrades text rendering and
  adds decorative junk (literal asterisks, decorative quotes, random glitch
  nudges). The caller passes `use_pe=false` at the `/v1/images/generate`
  boundary; the template itself is the final prompt.
- No alpha composites (no `_on_white.png` / `_on_magenta.png` reference outputs).
  `mode=icon` keys out the magenta and the resulting RGBA PNG's alpha channel
  is the only proof-of-correctness we keep.

## Scale targets

- Character occupies ~25 % of each cell (e.g. ~64×64 px inside a 256×256 cell
  on a 4×4 sheet).
- Final per-frame size after `postprocess.slice_grid` → 128×128 (classic ARPG)
  or 256×256 (modern high-DPI).

## Direction convention

North = facing up / away from camera (back of head visible).
East = facing right (character's left hand toward the camera in profile-ish).
South = facing down / toward camera (face visible, the baseline).
West = facing left (mirror of East; many pipelines just flip East horizontally
to save a generation call — we still generate natively for richer identity).

## Anchor references

- Zelda: A Link to the Past — canonical 4-direction 8-frame walks, 5-frame
  attacks, ~16×24 px native res.
- Stardew Valley — 3-frame walks × 4 directions, warm palette, readable
  shoulder-from-above silhouette.
- Hyper Light Drifter — neon on dark, 8-frame runs, precise 1-pixel edges,
  high visual density in a tiny sprite.
