# ui_hud

**Flag:** STATIC
**Projection:** flat 2D UI
**Covers Shoal plan categories:** 46 (panel), 47 (button), 48 (health bar)
**Consumer scaffolds:** every scaffold with a HUD or menu

Unified STATIC workflow covering three UI categories with one shared
prompt template. Panels support 9-slice decomposition; buttons support
4 state variants with shared-base seeds for identity consistency; bars
support multiple resolutions.

## Pick this over per-scaffold custom UI when…

- The scaffold needs stretchable frames (9-slice panels) for variable-size
  dialogs, menus, or HUD regions.
- Button states are the standard 4-state set (idle/hover/active/disabled).
- Health/resource bars are horizontal gradients (standard RPG convention).
- You're fine with one of the named style_variants (fantasy / sci-fi /
  minimalist / pixel-art) or close relatives.

## Pipeline

### Panel (cat. 46 — 9-slice)

1. Fill `prompt_template.md` with `kind=panel`, leave `state_description` empty.
2. Gen at 512×512 via ERNIE `/v1/workflows/icon`.
3. `postprocess.slice_9slice(src, out_dir, corner_px=96)` → 9 PNGs
   (tl/t/tr/l/c/r/bl/b/br). Engine stretches at render time.
4. Alternative: ship the single source + 4 corner coords in a manifest;
   Phaser / Pixi / Godot 9-slice renderers consume that directly.

### Button (cat. 47 — 4-state)

1. Gen 4 times with the SAME `subject_description` and different
   `state_description` fragments (idle / hover / active / disabled).
2. Use `seed_base + state_seed_offset` (0/1/2/3) per state — states
   look like "the same button pressed differently", not 4 different
   designs.
3. `postprocess.crop_to_ui_element(src, out_dir, out_w, out_h)` per state.

### Health bar (cat. 48)

1. Gen at 512×192 (rectangular — aspect-matches the output).
2. `postprocess.crop_to_ui_element(src, out_dir, out_w=384, out_h=64)`.
3. For an animated fill (frames 0→100% at 10 % increments), gen 11 times
   varying the `subject_description`'s "N percent filled" clause.

## ERNIE call count budget

- **Minimal HUD for one scaffold** (1 panel + 1 button × 4 states + 1 bar):
  **6 calls** / ~4 s wall-clock with 3-ERNIE pool.
- **Animated bar** adds 10 calls for an 11-frame fill cycle.
- **Multiple button styles** × 4 states each scale linearly.

## Canary corpus (rendered in 4.0 s wall-clock via 3-ERNIE pool)

- `canary_001_panel_fantasy.png` — carved-wood-and-metal fantasy frame
  with gold filigree, iron rivets, parchment interior. 9-sliceable.
- `canary_002_button_idle.png` — cyberpunk rounded rect with cyan accent
  line across the top third, dark navy fill, soft rim glow.
- `canary_003_healthbar_minimalist.png` — horizontal bar at 75% fill,
  red-to-orange gradient left side, dark empty right side.

## Library seeds

`scaffolds/engine/asset_library/ui_hud/`:
- `baseline_panel_fantasy.png` (38 KB) — reference frame
- `baseline_button_scifi.png` (13 KB) — reference button
- `baseline_bar_minimalist.png` (8 KB) — reference bar
- `panel_fantasy_9slice/*.png` (9 tiles, 81 KB total) — the panel
  decomposed into 9-slice pieces, ready for any engine's 9-slice
  renderer at any target panel size

## Known caveats

### Text baking is forbidden, not a mistake to avoid

The template explicitly says `no text labels or words on the element`.
ERNIE's text rendering is unreliable (renders garbled glyphs, misspells,
sometimes just paints "IDLE" if it sees state_description wording).
**Scaffolds must render button labels / bar numeric values / panel
titles as runtime DOM / canvas overlays** on top of the UI sprite,
never inside it. This is standard UI discipline in every non-AI
engine too — ERNIE just makes the rule load-bearing.

### 9-slice corner size depends on the artwork

The shipped `slice_9slice(corner_px=96)` assumes the decorative border
occupies the outer ~96 px of a 512-px panel. Scaffolds with thinner or
thicker borders should override `corner_px` (32 for pixel-art UIs, 128
for densely-ornamented fantasy panels). The corner size is a style
decision, not a fixed value.

### Subject size inside the chromakey varies

Panels typically occupy ~80% of the 512 canvas (good). Buttons and
bars often come back smaller than expected — the model renders them
centered on the magenta field with significant padding around. This is
fine because `postprocess.crop_to_ui_element` tight-crops to the alpha
bbox before the final resize, so the visible UI element fills its
output frame regardless of how big it came back.

### Aspect-match at gen time matters for bars

Generating a wide horizontal bar at 512×512 (square canvas) produces
artwork that doesn't fill the frame — ERNIE centers a small horizontal
bar on the square. Generating at 512×192 (rectangular canvas) fills
the frame properly. The `anim_set.json::kinds.bar.gen_canvas` defaults
to the rectangular shape for this reason.

### Button-state consistency is strong with seed-pinning

Canary round observation: the same `subject_description` + different
`state_description` + seeds differing only in the state offset produces
4 buttons that visibly look like "the same button in 4 states" rather
than 4 different designs. Same lesson as `dialogue_portrait`'s
seed-pinning for identity — applies to any asset category where a
"same subject, variant state" relationship is needed.

### Style variant fidelity

Consistent with every other Shoal workflow:
- **Fantasy RPG style** renders with high fidelity (canary 1 perfect).
- **Sci-fi cyberpunk** renders well with clear style cues (canary 2 perfect).
- **Minimalist flat design** renders well (canary 3 perfect).
- **Pixel-art UI** (not tested in canary round) would need strict
  palette normalization post-gen per the `tree_static` and `item_icons`
  caveats — use `normalize_palette(max_colors=16)`.
