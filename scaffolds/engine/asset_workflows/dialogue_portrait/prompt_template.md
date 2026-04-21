# dialogue_portrait — ERNIE prompt template

Static head-and-shoulders portraits for dialogue/cutscene UI. One
character × 7 canonical emotions (`neutral`, `happy`, `sad`, `angry`,
`surprised`, `determined`, `hurt`). Identity is held across the 7 passes
by pinning the seed and varying only the `<emotion_description>`
placeholder.

Anchored on Fire Emblem portraits (dense shoulders-up framing), Persona
5 (bold graphic style), Undertale (limited-palette + expressive).

## How ERNIE is called

- **Model kind:** Turbo (8-step, bf16)
- **Mode:** `icon` (magenta chromakey) OR `photo` with an explicit
  full-background color — scaffolds with a matted portrait frame in
  the UI prefer `photo` + solid background; transparent-overlay
  dialogue systems want `icon`. See `anim_set.json::bg_mode` for
  per-scaffold default.
- **Canvas:** 512×512 or 768×768 (tighter framing than character
  full-body). Default 512×512 in `anim_set.json`.
- **steps=8, cfg=1.0, use_pe=false**
- **Seed:** pinned per-character. Critical for identity consistency
  across the 7 emotion variants — shared seed means the same face.

## The template

```
head and shoulders portrait of <character_name>, <style_variant>,
<emotion_description>, looking at the viewer, neutral dialogue-ready
framing from mid-chest up, character centered in frame, clean cel-shaded
colors, readable facial features, soft balanced lighting, isolated
against a solid magenta #FF00FF background, no background elements,
no props outside the shoulders-up framing, <style_modifiers>, no text,
no border, no watermark
```

### Required placeholders

| Placeholder | Meaning | Examples |
|---|---|---|
| `<character_name>` | subject identity | `young elven ranger with shoulder-length blonde hair and green eyes`, `grizzled veteran knight with a scar across the left eye and short gray beard`, `cheerful merchant woman with red hair in a braid and round glasses` |
| `<style_variant>` | overall visual register | `Fire-Emblem-style hand-painted portrait`, `Persona-5-style bold graphic art with strong outlines`, `Undertale-style pixel-art portrait`, `semi-realistic anime with soft shading` |
| `<emotion_description>` | facial expression + minor posture cue | `neutral expression, eyes level, mouth closed, shoulders relaxed`, `genuinely happy smile, eyes slightly narrowed in warmth, shoulders slightly raised`, `sad expression, eyebrows angled upward-inward, mouth downturned slightly, shoulders slumped`, `angry expression, brows furrowed deeply, mouth tight and downturned, jaw set, shoulders tensed forward`, `surprised expression, eyebrows raised high, mouth open in O-shape, eyes wide`, `determined expression, brows set firmly, mouth set with slight clench, eyes focused and forward`, `hurt expression, one eye partially closed in pain, mouth strained, shoulders flinched protectively` |
| `<style_modifiers>` | per-scaffold flavor | `warm painterly palette`, `high-contrast graphic with black outlines`, `muted somber tones for dark narrative`, `bright saturated colors for cheerful tone` |

### ERNIE rules baked in

- No literal quotes in the prompt — ERNIE renders them as glyphs.
- `use_pe=false`.
- Seed pinning is non-optional. Without it, each emotion regenerates a
  different-looking character and the 7-portrait set won't read as one
  person.

### Copyright-prior warning

Just like `side_scroller_character` round, generic character descriptions
can auto-reconstruct copyrighted characters (Persona 5 protagonists are
particularly over-represented in training data and will appear from bare
"red jacket + gray hair + glasses" prompts). Include at least one
pattern-breaking detail (unique accessory, non-default hair color, a
scar, a tattoo) to avoid copyright drift.

## Scale targets

- Canvas: 512×512 default; 768×768 for high-detail RPG; 1024×1024 if the
  scaffold wants the Fire Emblem-style dense portrait.
- Tight-crop to alpha bbox before shipping — portraits naturally come
  back with 15–25% empty magenta around the head, which the
  `postprocess.alpha_bbox_crop` trims.

## ERNIE call count budget

- One character: **7 calls** (one per emotion). ~1 min wall-clock.
- Ten characters: 70 calls. ~10 min single-pipe, ~3.3 min with
  3-pipeline parallelism.
