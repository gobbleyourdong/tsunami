# Asset State-Graph Plan — Chain-Edit Animation System

> Filed: 2026-04-21
> Author: consolidator
> Goal: build declarative per-entity state-graphs where every transition is a
> chain-edit animation primitive. One schema covers characters, VFX, environment,
> and props. Identity preservation via chain-edits with bounded per-step drift.

## Context

From the design discussion with the operator:

1. **Chain-edit beats star-edit** for identity preservation. Each frame is a
   small delta from the PREVIOUS frame, not from the base. Drift bounds are
   small and additive.
2. **Reverse-playback doubles the catalog** — every "destruction" chain played
   backwards is a "formation" chain. Free second animation per chain written.
3. **State-graph as the real primitive**: entities have STATES (healthy, on_fire,
   charred, windy, snowy), LOOPS within each state, and EVENT-DRIVEN TRANSITIONS
   between states. Game logic speaks in events (`tree.send("WATER")`) and the
   asset runtime plays the right chain.
4. **One schema unifies characters + VFX + environment + props.** `knight`,
   `tree`, `skull_fragment_dust`, `fountain_water` all look identical at the
   runtime layer.

## The topological invariant (sigma draft_023 anchor)

**Chain-edit identity drift is bounded by Σ(per-step strength × per-step
relevance) across the chain.** For low per-step strength (~0.3-0.5) and
semantic nudge descriptions (only what CHANGES, not the full pose), drift
stays below visual perceptibility across N chained edits.

This is the structural property the whole system rests on. Falsifiable via:
generate a 20-frame chain, compute perceptual-hash distance frame-to-frame,
check whether distance bounds or diverges.

## The 5-commit plan

### Commit 1 — `/v1/images/animate` endpoint in qwen_image_server

Add a new endpoint to `tsunami/serving/qwen_image_server.py`:

```python
class AnimateRequest(BaseModel):
    base_image: ImageInput  # seed frame
    nudges: list[NudgeStep]  # ordered chain of deltas
    save_dir: str            # where to write per-frame PNGs
    seed: Optional[int] = None

class NudgeStep(BaseModel):
    delta: str               # prompt describing what CHANGES from prev frame
    strength: float = 0.4    # per-step edit strength (low by default)
    guidance_scale: float = 4.0
    num_inference_steps: int = 30

class AnimateResponse(BaseModel):
    created: int
    frames: list[GenResponseImage]  # one per nudge step
    timing: dict
    total_strength: float     # Σ(step strengths) — proxy for drift upper bound
```

Loop body: take base_image, apply first nudge's edit → frame_0. Feed frame_0
as input to second nudge's edit → frame_1. Continue. Return full frame list.

Same locks as `/v1/images/edit` — serial within the pipeline.

### Commit 2 — State-graph schema + loader

New module `tsunami/animation/state_graph.py` with pydantic models:

```python
class StateDef(BaseModel):
    source: Optional[str] = None      # "base" for the root state
    derive_from: Optional[str] = None  # state name this derives from
    prompt: Optional[str] = None       # derivation prompt (required if derive_from)

class AnimationPrimitive(BaseModel):
    """Loaded from asset_library/animations/*.yaml."""
    primitive: str
    base_hint: Optional[str] = None
    reversible: bool = False
    frame_count: int
    category: str  # character | vfx | environment | prop
    nudges: list[NudgeStep]

class Transition(BaseModel):
    from_state: str = Field(alias="from")
    to_state: str = Field(alias="to")
    on: str                            # event name
    animation: Optional[str] = None    # yaml reference
    reverse_of: Optional[str] = None   # reference another transition
    overlay: Optional[str] = None      # VFX overlay primitive

class EntityGraph(BaseModel):
    entity: str
    base: str                          # image path or registry key
    states: dict[str, StateDef]
    transitions: list[Transition]
    loops: dict[str, str] = {}         # loop_name → animation yaml
```

Loader reads YAML, validates graph integrity (every transition's from/to
exists in states, no dangling animation references, reverse_of targets
exist, etc.), returns a typed EntityGraph.

### Commit 3 — Seed 6 animation primitives

New directory `scaffolds/engine/asset_library/animations/` with 6 YAML files:

- `wind_sway_loop.yaml` — 2-3 frames, reversible-loop (self-chain)
- `fire_flicker_loop.yaml` — 3-4 frames, loop
- `igniting.yaml` — 5 frames, forward (not reversible — fire doesn't un-ignite)
- `fire_fizzling.yaml` — 5 frames, forward (→ charred, ash settles)
- `water_extinguish.yaml` — 5 frames, forward (fire extinguished by water)
- `shattering.yaml` — 6 frames, **reversible** (played backward = assembling)

Each file: base_hint (what kind of input it expects), frame_count, category,
nudges list with per-step strength and delta prompts.

### Commit 4 — Seed 2 entity state-graphs

New directory `scaffolds/engine/asset_library/entities/` with:

**`tree.yaml`** — full event matrix:
- States: healthy_still, windy, on_fire, extinguished, charred, snowy, dead_bare
- Events: GUST, CALM, IGNITE, WATER, TIME, SNOW, THAW, DAMAGE, LIGHTNING
- Transitions: ~12-14 edges covering the common game scenarios
- Loops: wind_sway (in windy state), fire_flicker (in on_fire), smoke_wisp
  (in charred)

**`knight.yaml`** — character example:
- States: idle, walking, running, jumping, attacking, hurt, dying, dead, casting, blocking, crouching
- Events: MOVE, STOP, JUMP_START, JUMP_LAND, ATTACK, TAKE_HIT, DIE, CAST, BLOCK,
  UNBLOCK, CROUCH, UNCROUCH
- Transitions: ~15-18 edges
- Loops: idle_breathing, walk_cycle, run_cycle, block_hold, cast_channel

### Commit 5 — Bake tool (state-graph → sprite-sheet)

New tool `scripts/asset/bake_sprite_sheet.py`:

```
python scripts/asset/bake_sprite_sheet.py \
  --entity scaffolds/engine/asset_library/entities/tree.yaml \
  --output workspace/baked/tree_sheet.png \
  --frames-per-state 8
```

Loads the entity graph, runs every transition animation + every loop to get
per-state frame strips, concatenates into a classic spritesheet PNG with a
generated `tree_sheet.json` metadata file mapping (state, frame) → pixel-rect.

For engines that don't want the runtime state-machine — they get a classic
sprite sheet + frame index, extracted FROM the chain-edit system without
artist hand-drawing.

## Execution order

Build sequentially. Each commit must pass its own tests before the next
commits. No bundling — if commit 2 lands without commit 1's endpoint, the
loader works but can't actually run animations.

1. Commit 1 first (endpoint + test)
2. Commit 2 (schema + loader + test)
3. Commit 3 (6 primitive YAMLs + validator test)
4. Commit 4 (2 entity YAMLs + integration test)
5. Commit 5 (bake tool + end-to-end test on a seeded entity)

## Stack state precondition

To build this the operator asked to ramp down the current stack and bring
up only Qwen-Image-Edit on :8094. Memory:
- Ramped down: Qwen3.6-35B (35 GB) + ERNIE (22 GB) + embed (1 GB) + proxy (<1 GB) = ~58 GB freed
- Qwen-Image-Edit loads: ~27 GB bf16
- Plus Multi-Angles-LoRA: ~200 MB
- Total working set: ~27 GB, with ~100 GB headroom

Ramp sequence:
```bash
./tsu down
PYTHONPATH=. nohup python3 -u -m tsunami.serving.qwen_image_server \
  --port 8094 --lora multiple_angles \
  > /tmp/tsu-qwen-image.log 2>&1 &
```

Verify `:8094/healthz` returns `{pipe_loaded: true, loaded_loras: ["multiple_angles"]}`.

## Testing budget

Each commit pays its own testing cost:
- Commits 1-2: unit tests (pytest, no model calls)
- Commit 3: YAML validation only (no model calls)
- Commit 4: YAML + graph validation (no model calls)
- Commit 5: **one** end-to-end bake run using the live Qwen-Image-Edit on :8094
  to prove the whole chain works — generates ~30-50 frames as the final smoke test

Total model calls to verify the full plan: **1 bake run** (~60-120 edit calls
against the live endpoint, ~30 min of GPU time).

## Falsifiability hooks

Each commit registers a signature in `scripts/audit/fix_registry.jsonl` so
the sigma v10 production-firing audit tool can confirm the new endpoints /
loaders actually fire in production sessions:

- `animate_endpoint_fired` — signature: `"[animate] chain of"`
- `state_graph_loaded` — signature: `"[state-graph] loaded entity"`
- `primitive_applied` — signature: `"[animate] applied primitive"`
- `bake_completed` — signature: `"[bake] sprite sheet written"`

If any of these never fire, the corresponding layer is dead code (v10
principle applied to this very project).

## Out of scope for v1

- ControlNet depth-map pose guidance (deferred; add if prompt-only consistency
  fails on characters)
- Wan I2V for fluid in-between generation (deferred; add when a specific
  animation type fails on chain-edit + RIFE)
- RIFE frame interpolation (deferred; chain-edit produces sufficient frames at
  low strength for v1; add interpolation if target frame counts exceed what's
  practical to chain)
- Prompt-enhancement layer (the qwen_image_server `use_pe` pattern from
  ernie_server — skip for v1, each nudge's prompt is already minimal by design)
- Multi-character simultaneous animation in a single frame (two knights
  fighting) — entity-at-a-time for v1
- Music/audio cue alignment — visual-only for v1

## Success criteria (v1)

- `qwen_image_server` exposes `/v1/images/animate` that accepts a base image +
  chain of nudges and returns frame sequence
- `knight.yaml` + `tree.yaml` load cleanly through the schema validator
- Running `bake_sprite_sheet.py --entity tree.yaml` produces a valid sprite
  sheet with labeled per-state sub-strips and a metadata JSON
- At least one visual inspection confirms identity preservation — tree looks
  like the same tree across all its states (the whole point of chain-edit)
