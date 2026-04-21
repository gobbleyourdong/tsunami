# side_scroller_character — ERNIE prompt template

Profile-view 2D platformer / action character. Full body, pure left-facing
baseline — right-facing is a horizontal flip at render time (halves the gen
count where the character is left/right symmetric; disable mirroring in
`anim_set.json` if the design has single-side details like a holstered
sidearm). Anchored on Super Mario Bros, Castlevania: SOTN, Celeste, Metal
Slug, Hollow Knight.

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey → transparent RGBA, client-side)
- **Canvas:** 1024×1024
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** one-seed-per-character (stable identity across anim states);
  vary only the `<anim_name>` / `<pose_description>` placeholders between
  passes.

## Production pattern — per-frame generation

The top_down_character canary round proved that grid-prompting produces
duplicate poses, not animation phases. Side-scroller work follows the
**per-frame** path from the start:

- One ERNIE call per frame.
- Each call's prompt includes an explicit `<pose_description>` (see
  `canary_prompts.jsonl` for the canonical per-frame descriptions).
- Outputs are 1024×1024 single-pose PNGs with magenta background;
  `postprocess.stack_horizontal` concatenates the frame sequence into an
  N-wide strip, one anim per strip.

Grid-prompting is still allowed as a quick identity/palette check against
a new character design (single call, 4–9 cells) before committing to the
70-frame gen budget.

## The template (per frame)

```
full-body side-view profile sprite of <character_name>, <style_variant>,
facing left, <pose_description>, <anim_name> animation, single pose
centered on a solid magenta #FF00FF background, no shadow under the
character, clean negative space between feet and background, flat clean
cel-shaded colors, readable silhouette, crisp edges, no antialiasing
bleed into the magenta, no text, no border, no watermark, <style_modifiers>
```

**Why no baked shadow**: both the top_down_character and side_scroller
canary rounds showed that asking ERNIE for a "soft ground shadow" produces
a dark purple/magenta-adjacent ellipse that survives `extract_bg` as a
residual purple blob. Engines consuming these sprites should render
shadows at runtime with a canvas/WebGL primitive, not bake them into the
ERNIE output. Scaffolds that specifically need a baked shadow can override
the template with `shadow_color: dark_slate_gray` to force a non-magenta
hue that the chromakey will keep.

### Copyright-prior warning

ERNIE's training data auto-reconstructs recognizable characters from
generic descriptions. Canary 001 (`red cap + blue overalls + white gloves`)
produced a cap with a literal "M" logo despite nothing in the prompt
requesting it. Production prompts should include at least one
distinguishing detail that breaks the pattern — a green scarf, different
boot colors, a staff-in-hand — to avoid summoning a copyrighted silhouette
wholesale.

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<character_name>` | subject identity + archetype | `nimble platformer hero with a red cap and blue overalls`, `dark-cloaked vampire hunter with a whip`, `mercenary commando with a compact rifle` |
| `<style_variant>` | overall visual register | `8-bit NES limited palette`, `16-bit Castlevania painterly gothic`, `Metal Slug hand-inked neo-retro`, `Hollow Knight inky monochrome` |
| `<pose_description>` | per-frame posture | `both feet planted flat, arms at sides, neutral stance`, `mid-stride with left knee high and right leg extended behind`, `crouched on haunches knees bent body compressed`, `mid-air apex of jump legs tucked` |
| `<anim_name>` | animation state (for metadata; shown to the model for context) | `idle`, `walk`, `run`, `jump_up`, `jump_peak`, `jump_down`, `land`, `attack_light`, `attack_heavy`, `hurt`, `death`, `wall_slide`, `dash`, `crouch`, `crouch_walk` |
| `<motion_direction>` | shadow-drift cue | `stationary`, `forward`, `upward`, `downward` |
| `<style_modifiers>` | per-scaffold flavor | `high-contrast palette, no outline glow`, `gothic purple-and-green, heavy chiaroscuro`, `warm pastels, soft 8-bit dither` |

### ERNIE rules baked in

- No literal ASCII quotes in the prompt — ERNIE renders them as glyphs.
- `use_pe=false` (caller passes this at the `/v1/images/generate`
  boundary; the template is the final prompt).
- No alpha composites — `mode=icon`'s RGBA is the only ground truth.

## Scale targets

- Character occupies ~30 % of the 1024×1024 frame → effective 300×300
  footprint with room for wind-up / follow-through on attack anims.
- Final per-frame size after downscale: 256×256 (classic platformer),
  128×128 (SNES / Castlevania), or 64×64 (NES).

## Facing convention

Facing-left is the generator baseline. Right-facing is produced by
horizontal-flipping the left-facing frame unless
`directions.left_mirror_to_right = false` in `anim_set.json`. Disable
the mirror for:

- Characters with handedness-specific weapons or accessories (a sword
  always held in the right hand, a holster on the left hip, a cape
  asymmetrically draped over one shoulder).
- Any time the flipped version reads as "wrong-handed" to a platformer
  player's eye — cheaper to pay the extra gen than to ship a sprite that
  looks off.

## Anchor references

- **Super Mario Bros** — 8-bit baseline; tiny sprites, exaggerated
  silhouettes, no anti-aliasing.
- **Castlevania: Symphony of the Night** — 16-bit painterly gothic;
  multi-frame idles with subtle breathing + cape animation; canonical
  walk-run-jump vocabulary.
- **Celeste** — modern pixel-art; crisp 1-px edges, expressive
  wind-up / follow-through on dashes and attacks.
- **Metal Slug** — hand-inked, richly-shaded; ~100+ frames per character;
  comedic hit/death animations.
- **Hollow Knight** — inky monochrome; emphasis on readable silhouette
  even with small sprite counts.
