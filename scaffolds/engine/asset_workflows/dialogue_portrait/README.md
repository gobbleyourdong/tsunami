# dialogue_portrait

**Flag:** STATIC + emotion variants (not anim)
**Projection:** head-and-shoulders (shoulders_up_portrait)
**Coral gap:** `asset_dialogue_portrait_001`
**Consumer scaffolds:** `scaffolds/gamedev/jrpg`,
`scaffolds/gamedev/action_adventure` (NPC dialogues), any scaffold with
cutscene dialogue UI.

Per-character 7-emotion portrait set (`neutral`, `happy`, `sad`,
`angry`, `surprised`, `determined`, `hurt`). The 7 portraits share a
pinned seed per character, so identity stays stable across emotion
variants — this is the single most important discipline in the workflow.

## Pick this over a full-body portrait when…

- You need dialogue-box portraits (head-and-shoulders framing) specifically.
- The scaffold supports emotion swaps during dialogue (most RPGs).
- You don't need action poses or full-body (those come from
  `top_down_character` / `side_scroller_character`).

## Pipeline

1. Pin the seed per character (`anim_set.json` doesn't enumerate
   characters — scaffolds allocate seeds; 10_000 + char_index is a sane
   baseline).
2. For each of the 7 canonical emotions:
   - fill `prompt_template.md`'s `<character_name>`, `<emotion_description>`,
     `<style_variant>`, `<style_modifiers>`.
   - hit ERNIE `/v1/workflows/icon` with the **same seed** and the
     emotion-specific prompt variation.
3. `postprocess.crop_portrait(src, out_dir, pad_px=20, out_side=256)` —
   tight alpha-crop, pad to square, resize to scaffold UI target.

## ERNIE call count budget

- Per character: **7 calls** (~1 min single-pipe).
- Per 10-character cast: 70 calls (~10 min single-pipe, ~3.3 min with
  3× parallel pipelines).

## Canary corpus

Three canaries (`canary_prompts.jsonl`) — **same character identity +
same seed, 3 different emotions**:

- `canary_001_ranger_neutral.png` — elven ranger, neutral
- `canary_002_ranger_happy.png` — same ranger, happy
- `canary_003_ranger_angry.png` — same ranger, angry

All three hold identity: pale blonde hair, green eyes, pointed elf
ears, subtle freckles, green-and-gold cloak with leaf pendant. This
canary round is the **proof that seed-pinning preserves character
identity across emotion variants** — the load-bearing claim of the
workflow.

## Library seed

`scaffolds/engine/asset_library/dialogue_portrait/baseline_ranger_neutral.png` —
the neutral ranger portrait, used as a reference for scaffolds that
want a generic fantasy-protagonist starting archetype to customize via
`edit_image`.

## Findings from this canary round

### Seed-pinning-for-identity works exceptionally well on portraits

Unlike side_scroller characters where pose fidelity was ~70-80%, the
dialogue_portrait round held **near-perfect identity across all 3
emotion variants**. Every distinguishing detail — the leaf pendant, the
braided hair, the freckles, the specific shade of green on the cloak
trim — survived seed-pinned regeneration with only the emotion prompt
changing.

This is the cleanest result of any Shoal workflow canary round. Portrait
generation is the workflow where identity-preservation works best, which
fits the model's training prior (portraits are over-represented vs.
action poses in training data).

### Alpha extraction is very clean for portraits

No residual magenta, no purple rings, no interior chromakey holes. The
character outline is well-separated from the magenta background because
skin + hair + fabric colors are all far from the magenta hue. One of
the few workflows where the chromakey caveats don't apply.

### Emotion fidelity is strong but not absolute

The neutral, happy, and angry emotions read instantly and correctly. The
subtle emotions (determined, hurt) would likely need more specific
prompt engineering — `hurt` specifically often gets rendered as
"wistful-sad" rather than "in-pain". Scaffolds that need pain-forward
hurt portraits should add `wincing, eyes partially squeezed shut, teeth
slightly visible` to the emotion_description rather than relying on the
default hint from `anim_set.json`.

### Copyright-prior warning (same as side_scroller)

Generic portraits can auto-reconstruct recognizable characters from
training data. The `character_name` placeholder should always include
a distinguishing detail (scar, accessory, non-default hair color,
tattoo) to avoid summoning copyrighted silhouettes. For the canary I
used "pale blonde hair tied back + green eyes + leaf pendant" — which
landed as a bespoke ranger character, not a recognizable IP.

### No baked background — scaffold UI owns the matte

The prompt says "isolated against a solid magenta background, no
background elements." Scaffolds that want a scenic backdrop behind the
portrait should composite the portrait onto their own UI matte at render
time, not prompt ERNIE for an environment — a prompted environment makes
the alpha extraction ambiguous and muddles the portrait subject.
