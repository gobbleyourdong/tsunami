# Asset pipeline — state graph → animated RGBA sprite sheet

One-command path from an entity state-graph YAML to a pixel-art sprite
sheet at an arbitrary target grid size. Owned by the tsunami main
instance (gen/bake/extract/pixelize); consumed by the engine runtime
(compositing + state-machine playback) and produced by the parallel
sprite-scraping instance (entity + primitive YAMLs mined from canonical
game sprite sheets).

## Scope split

```
  scraping instance         this instance             engine runtime
  ─────────────────         ─────────────             ──────────────
  scrape real sprites  →   schema / bake     →      compositing + playback
  AI-describe motion       (this doc)                attach points, z-order
  emit entity + prim       extract alpha              state machine
  YAMLs                    pixelize                   runtime lighting
```

The scraping instance's `progression_description` fields map 1:1 onto
our `AnimationPrimitive.guidance` + `PrimitiveNudge.delta` fields; their
outputs drop into `scaffolds/engine/asset_library/` as new primitive and
entity YAMLs.

## Schema

Two YAML shapes in `scaffolds/engine/asset_library/`:

**Animation primitive** (`animations/<slug>.yaml`) — a reusable chain
of nudge edits. Example `shattering.yaml`:

```yaml
primitive: shattering
category: vfx          # character | vfx | environment | prop
frame_count: 6
reversible: true       # if true, reverse playback is a valid inverse
base_hint: "solid crystalline object on plain background"
guidance: "Progression: intact → hairline cracks → fragments separating → dust cloud"
nudges:
  - delta: "hairline cracks appearing across the surface, faint internal stress"
    strength: 0.25
  - delta: "cracks deepen and branch, small chips starting to flake off"
    strength: 0.30
  ...
```

**Entity state graph** (`entities/<entity>.yaml`) — a character / prop
/ environment instance with its states, transitions, and loops.
Example `tree.yaml`:

```yaml
entity: tree
base: scaffolds/engine/asset_library/tree_static/baseline_oak_iso.png

states:
  healthy_still: {source: base}
  windy:
    derive_from: healthy_still
    prompt: "branches swaying in a steady breeze, leaves rustling"
  on_fire:
    derive_from: healthy_still
    prompt: "engulfed in active orange flames, bark charring"
  ...

transitions:
  - from: healthy_still
    to: on_fire
    "on": IGNITE       # YAML 1.1: `on` must be quoted (bool coercion)
    animation: igniting
  - from: on_fire
    to: extinguished
    "on": WATER
    animation: water_extinguish
  ...

loops:
  wind_sway_in_windy:
    state: windy
    animation: wind_sway_loop
```

Schema invariants enforced at load (`tsunami/animation/state_graph.py`):
- Exactly one root state (`source: base`)
- All `derive_from` / `from` / `to` references resolve to defined states
- No derivation cycles
- Every primitive reference has a matching YAML file on disk
- Every `reverse_of` points to a valid transition

## Pipeline (one command)

```bash
python scripts/asset/end_to_end.py \
    --entity scaffolds/engine/asset_library/entities/tree.yaml \
    --out-dir /tmp/tree_final \
    --target-size 128
```

Runs three steps in sequence; each can be invoked standalone.

### Step 1: bake → 1024² magenta-bg frames

`scripts/asset/bake_sprite_sheet.py` loads the entity + its primitives,
walks the graph topologically:

1. **Derive states.** Root copies the base PNG (upscaled to 1024² on
   magenta `(255, 0, 255)`). Each derived state runs one
   `/v1/images/edit` call against its parent-state's baked image.
2. **Animate transitions.** For each `animation: X` transition, call
   `/v1/images/animate` starting from the `from`-state's image, chain-
   editing through the primitive's nudges.
3. **Reverse transitions.** `reverse_of: <forward-id>` transitions are
   pure file copies of the forward frames in reverse order — no extra
   inference.
4. **Loops.** Animate each loop starting from its state's image.
5. **Compose.** Stitch rows × cols into one `sheet.png`; emit
   `metadata.json` with per-cell delta, Σstrength, from_state, to_state.

Output at `<out-dir>/`:
```
states/
  healthy_still.png     ← root (copied from upscaled base)
  windy.png             ← one /edit from healthy_still
  ...
transitions/
  healthy_still__on_fire/
    frame_000.png       ← one /animate chain step
    ...
  ...
loops/
  wind_sway_in_windy/
    frame_000.png
    ...
sheet.png               ← composed
metadata.json
```

**Generation settings (model-card-correct lightning mode):**
- 1024² output
- 8 inference steps
- `true_cfg_scale=1.0`, `guidance_scale=1.0`
- `negative_prompt=" "` (single space — empty disables CFG in Qwen-Image-Edit)
- lightning LoRA attached at server startup (`--lora lightning`)
- magenta-bg input — RGBA asset composited onto `(255, 0, 255)` before upscale

Per-call cost: ~45s (1024², 8 steps, CFG on). A 7-state entity with 3
forward transitions × 5 frames + 2 loops × 4 frames ≈ 29 inference
calls ≈ 22 min.

### Step 2: extract alpha

`scripts/asset/extract_alpha_unmix.py --bake <out-dir>` walks every
state PNG + every transition/loop frame, produces `<name>_rgba.png`
siblings. Uses closed-form un-premultiplication of magenta:

```
P = α·F + (1-α)·M       where M = (1, 0, 1)
α = 1 - clamp(min(Pr, Pb) - Pg, 0, 1)
F = (P - (1-α)·M) / α
```

Produces clean partial alpha on translucent edges (smoke, dust, glow)
without the pink bleed that hard chromakey leaves behind. On
crystal_v2's `shattered.png`: 733K partial-alpha pixels recovered
correctly vs. 775K force-transparent pixels from classical keyer.

### Step 3: pixelize

`scripts/asset/pixelize_sheet.py --bake <out-dir> --size 128 --filter lanczos`
takes the full-res `sheet.png` + `metadata.json` and writes
`sheet_<N>.png` + `metadata_<N>.json` at the target grid size. Whole-
sheet LANCZOS downsample (nearest also available for harsh retro look).

## Subject vs VFX routing (future work)

Subject primitives (`category: character | environment | prop`) use
magenta-bg + un-premix. VFX primitives (`category: vfx`) should use
black-bg + luminance-alpha for additive compositing — soft fire/smoke/
dust keys cleanly against black without the pink contamination that
translucent layers get on magenta. See
`project_sprite_vfx_composite_architecture.md` for the Mortal Kombat
pattern. Wiring is designed, not yet built — needs a category-routed
branch in the bake + extract steps.

## Related

- **Model/LoRA discipline:** `feedback_qwen_lightning_worse.md`
  (lightning probation + multi_angles selective attach rule)
- **Input preparation:** always upscale to 1024² on magenta before gen;
  never rotate or edit a pre-pixelized image
  (`feedback_fullres_then_pixelize.md`)
- **Quality priority:** `feedback_quality_consistency_coherence_first.md`
  (resolution sweep exists to find model-breakdown floor, not fastest path)
- **Flat-lit gen:** prompt for flat lighting so the runtime's
  depth/normal/reflection pipeline isn't fighting baked shadows
  (`project_flat_gen_depth_normal_pipeline.md`)
- **Tests:** `tsunami/tests/test_state_graph.py` (schema invariants),
  `test_seed_animation_primitives.py` (6 seed VFX),
  `test_seed_entity_graphs.py` (tree + crystal), `test_pixelize_sheet.py`
  (8 pure-math tests), `test_extract_alpha_unmix.py` (10 tests)
