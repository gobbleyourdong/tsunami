# Action Blocks + Mechanics — v0 method (attempt 001)

> Goal: a composition grammar that Tsunami emits as a **design script**, which
> compiles to engine calls. Prompt engineering where the "prompt" is the script.
> Emergent but predictable: remix the same small block catalog → large game space.

## Problem framing

Every engine (Godot nodes, Unreal Blueprints, Bevy plugins, Blender geometry
nodes, Ludii GDL, PuzzleScript, GameMaker DnD, Scratch) exposes a **composition
surface** where high-level units (nodes / components / rules) slot together
under a grammar. The grammar rejects nonsense; the combinatorics give emergence.

Today Tsunami writes freehand TypeScript against the engine's fluent API
(`game.scene('l').spawn('player', {controller:'fps', ai:'chase'})`). That call
has two failure modes the engine never catches: (a) incompatible combos
(`controller:'fps'` + 2D mode), (b) semantic gaps (spawn pickup but nothing
scores it). The model catches some of this some of the time — "some" is not
a composition discipline.

**Mismatch with the target.** The LLM is a very good structured-output writer
and a middling code writer. Asking it to emit validated JSON against a schema
is operating at its strength; asking it to emit 120 lines of TS that must
compile, run, and be fun is operating at its weakness. Move the game definition
into its comfort zone.

## Prior-art annotations

| System | What it is | What we take | What we add |
|---|---|---|---|
| Godot Scene/Node tree | Declarative hierarchy, scripts attached to nodes | Entity prototypes as typed archetypes | Schema validation at parse time; LLM-first authoring |
| Unreal Blueprints | Visual imperative event graphs | Event → Action edges | Skip the per-statement granularity; stay at mechanic level |
| Bevy ECS + Plugins | Data-oriented, composable plugins | Plugin = Mechanic abstraction | JSON authorable; no Rust |
| PuzzleScript | Tile-DSL with rewrite rules; huge emergent space from ~10 rules | DSL-as-prompt; tiny primitive surface | Real-time engine targeting, typed slots |
| Ludii / Game Description Language | Declarative formal game spec | Clear separation: entities / rules / ends | Not board-game-biased; targets WebGPU runtime |
| Inform 7 | Prose AS code for IF | Self-documenting tokens | Structured JSON — prose in descriptions, schema in structure |
| GameMaker DnD / Scratch | Block sockets with typed compatibility | Typed-socket enforcement | Scripts are authored by the model, not a human dragging |

**What this design adds that none of the above do:** the catalog is authored
*for an LLM reader*. Block names, descriptions, and compatibility matrices are
all first-class prompt payload. The LLM sees the same catalog the compiler
enforces. No translation layer between prompt and parser.

## The three layers

```
┌────────────────────────────────────────────────────────────────┐
│  LAYER 3 — Mechanics (composed templates)                     │
│  TopDownShooter | WaveSpawner | PickupLoop | BossFight | ...  │
│  Each: a parametric composition of L2 blocks                  │
└────────────────────────────────────────────────────────────────┘
                             ▲ composes
┌────────────────────────────────────────────────────────────────┐
│  LAYER 2 — Action Blocks (atomic, typed I/O)                  │
│  OnCollide | Spawn | Destroy | Damage | Score | PlaySound |   │
│  Move | If | Wait | Repeat | Branch | ...                     │
│  Each: a node with typed input slots, output slots, params    │
└────────────────────────────────────────────────────────────────┘
                             ▲ binds
┌────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Engine primitives (already exist in @engine)       │
│  Mesh | RigidBody | Controller | BTNode | AudioClip |         │
│  ParticleEmitter | Camera | Scene | Light | ...               │
└────────────────────────────────────────────────────────────────┘
```

Layer 1 exists today (14 subsystems, 8854 LOC). Layer 2 is new — a thin typed
wrapper around L1 methods, designed so every block has a **name, a schema,
and a prose description** the LLM can read. Layer 3 is where emergence lives:
each Mechanic is a parametric function `(params) → L2 composition`.

## Design script (the "prompt")

Tsunami emits one JSON document per game:

```json
{
  "meta": {
    "title": "Neon Drift",
    "vibe": ["fast-paced", "arcade", "80s"],
    "target_session_sec": 180
  },
  "config": { "mode": "3d", "camera": "perspective", "gravity": [0,-20,0] },
  "archetypes": {
    "player": {
      "mesh": "capsule",
      "controller": "topdown",
      "components": ["Health(100)", "Score"],
      "tags": ["player"]
    },
    "grunt": {
      "mesh": "box",
      "ai": "chase",
      "components": ["Health(20)"],
      "tags": ["enemy"]
    },
    "coin": { "mesh": "sphere", "trigger": "pickup", "tags": ["pickup"] }
  },
  "mechanics": [
    { "id": "m_waves",    "type": "WaveSpawner",
      "params": { "archetype": "grunt", "count_curve": "exp(1.15)",
                  "rest_sec": 8, "arena_radius": 20 } },
    { "id": "m_pickups",  "type": "PickupLoop",
      "params": { "archetype": "coin", "reward": 10, "respawn_sec": 4 } },
    { "id": "m_combo",    "type": "ScoreCombos",
      "params": { "window_sec": 2.5, "curve": "quadratic" } },
    { "id": "m_hud",      "type": "HUD",
      "params": { "show": ["score","health","wave"] } },
    { "id": "m_lose",     "type": "LoseOnZero", "params": { "field": "health" } }
  ],
  "flow": [
    { "scene": "title" },
    { "scene": "arena", "condition": "start_pressed" },
    { "scene": "gameover", "condition": "player_dead" }
  ]
}
```

Every string in a `type`, `controller`, `ai`, or component position resolves
through a **typed registry**. If the LLM emits `"type": "WavSpawner"` (typo),
the compiler fails at parse time with a `did-you-mean` and the feedback goes
into Tsunami's error_fixer before another generation attempt. Unknown tokens
never reach runtime.

## Compatibility matrix (schema, not prompt)

A subset of rules the compiler enforces before emitting a single line of TS:

- `controller:"fps"` requires `config.mode == "3d"`
- `ai:"chase"` requires at least one archetype with `tags ∋ "player"`
- `mechanic:"PickupLoop"` requires at least one archetype with `trigger:"pickup"`
- `mechanic:"WaveSpawner"` requires at least one archetype with `tags ∋ "enemy"`
- `mechanic:"LoseOnZero"` requires at least one archetype with a matching
  component (`Health`, `Lives`, etc.) with the named field
- A `flow` step with `condition: "X"` requires some mechanic to *produce* the
  condition `X` (dangling conditions are errors)

This is **Convention Beats Instruction**: the rule is enforced structurally at
parse, not asked of the model via prompt.

## Compiler: `design → engine calls`

```
parse(design.json)     →  ValidatedDesign | SchemaError[]
lower(ValidatedDesign) →  GameDefinition (existing engine type)
instantiate(GameDef)   →  running Game instance
```

`GameDefinition` already exists in `@engine/game/game.ts` (entity + scene +
flow serialization shape). The compiler's job is just translation: each
`Mechanic` instance lowers to a set of engine system installations + event
wirings against named archetypes.

Example lowering for `WaveSpawner`:

```ts
// design → engine
function lowerWaveSpawner(m: WaveSpawner, scene: SceneBuilder): void {
  const spawner = new WaveController({
    archetype: m.params.archetype,
    countFn:   parseCurve(m.params.count_curve),
    restSec:   m.params.rest_sec,
    arena:     m.params.arena_radius,
  });
  scene.onUpdate(dt => spawner.tick(dt, scene));
  scene.defineEvent("wave_cleared", () => spawner.isBetweenWaves);
}
```

The compiler owns the wiring; the LLM owns the design.

## Tsunami's prompt change

Today the agent gets a **prose dump** of the engine API
(`agent.py:2696-2716`). Replace with three structured sections:

1. **Mechanic catalog** (current list, 1-line descriptions each). ~15 entries
   for v0 cover arcade, platformer, shooter, puzzle, RPG, rhythm.
2. **Schema** (TypeScript definition of the design script — the model has been
   shown to emit valid JSON against TS types reliably).
3. **3 example design scripts** spanning different genres — the model
   pattern-matches to the nearest template, then remixes parameters and block
   combinations.

The prompt stops asking for TS and starts asking for a `design.json`. The tool
wired into Tsunami is `emit_design(name, design_json)` — which runs the
compiler, reports errors, and writes the compiled project into
`deliverables/<name>/`.

## QA feedback loop (fun detector)

The Visual QA agent plays the built game and emits a **critique** in the same
vocabulary:

```json
{
  "verdict": "unfun",
  "blocks_to_modify": [
    { "id": "m_waves", "issue": "too_dense_too_fast",
      "suggestion": { "rest_sec": "+2", "count_curve": "exp(1.08)" } },
    { "id": "m_pickups", "issue": "rewards_negligible",
      "suggestion": { "reward": "*3" } }
  ],
  "blocks_to_add": [
    { "type": "DashAbility", "reason": "player has no vertical/burst tool
      against dense crowds" }
  ],
  "blocks_to_remove": [],
  "pacing_notes": "first 20s has no enemies and no meaningful decision"
}
```

Tsunami applies the critique by **editing the design script** (small JSON
patches) — not by regenerating from scratch. This keeps QA-adjustments to a
small, verifiable diff and makes the fun-signal quantifiable over revisions.

## Emergence envelope

With v0 targets — ~40 Action Blocks, ~15 Mechanics, ~20 archetypes, params
mostly numeric with 3–5 meaningful values each — the reachable game space is
conservatively 10⁶ distinct compositions, generously 10¹⁰. QA kills most of
them; what survives is a learnable distribution of "what Tsunami-built games
get called fun." That distribution is the eventual training signal for a
future model that emits design scripts directly, no prompt scaffolding.

## Open questions (v1 candidates)

1. **Parameter curves as first-class blocks** — `exp(1.15)`, `quadratic`,
   `stepwise({0:1, 30:3, 60:5})` — do these deserve their own L2 type or stay
   as parsed strings? Probably first-class; curves are what actually shape
   difficulty.
2. **Procedural layout mechanics** — arenas, dungeons, tilemaps. The
   `tilemap_gen.py` and `rpg_asset_pack.json` tools already exist under
   `scaffolds/engine/tools/` — wire those as Mechanics, don't reinvent.
3. **Asset references** — sprite/audio asset names are currently freehand
   strings; should the catalog include a typed asset registry too? Likely
   yes, but keep it out of v0 to keep the schema small.
4. **Mutation operators for QA** — what's the legal move set for Tsunami's
   "edit the design" step? Candidates: tweak-param, swap-block, add-block,
   remove-block, wrap-block (e.g., wrap `Damage` in `If(playerDashing)`).
   The move set IS the reachable search space from a given state.
5. **Cross-mechanic dependencies** — `ScoreCombos` depends on `Score`
   existing. Declare dependencies at catalog level (`requires: ["Score"]`) and
   have the compiler topologically sort. Small, worth doing in v0.

## What goes where (source layout)

```
ark/
├── scaffolds/engine/src/
│   ├── design/                         ← NEW
│   │   ├── schema.ts                   TypeScript types for design script
│   │   ├── catalog.ts                  Block + Mechanic registries
│   │   ├── compiler.ts                 design → GameDefinition
│   │   ├── validate.ts                 compatibility matrix enforcement
│   │   └── mechanics/                  one file per mechanic lowering
│   │       ├── wave_spawner.ts
│   │       ├── pickup_loop.ts
│   │       └── ...
│   └── ... (existing 14 subsystems, unchanged)
│
├── tsunami/
│   ├── design/action_blocks/           ← this doc + future attempts
│   │   └── attempts/attempt_NNN.md
│   ├── tools/
│   │   └── emit_design.py              ← NEW tool; compiles + scaffolds
│   └── context/
│       └── design_script.md            ← NEW; prompt-facing catalog
```

The compiler lives in the **engine** (pure TS, reusable by any caller).
Tsunami's tool wraps the compiler and handles workspace + delivery plumbing.
The method doc stays on the Tsunami side because iteration belongs to the
agent surface, not the runtime.

## Ship criteria for v0

- 1 Mechanic end-to-end (`WaveSpawner`) — authored as JSON → compiled → runs.
- Schema validation rejects 3 malformed scripts with actionable error
  messages (unknown block, missing required archetype, dangling condition).
- Tsunami emits a valid design script for "make me an arena shooter" in one
  shot ≥ 50% of the time (baseline measurement, no optimization yet).
- Visual QA reads the built game and produces a structured critique against
  the catalog vocabulary.

Nothing fun yet. The goal of v0 is the **loop closing**: prompt → design →
compile → run → QA critique → design patch → re-run. Once the loop closes,
every subsequent iteration is a data point about what makes games fun.
