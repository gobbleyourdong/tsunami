# Plan: {goal}

Game-design plan — drone emits a single `game_definition.json` via
the `emit_design` tool. The engine at scaffolds/engine/ consumes that
JSON and runs the game. No raw React — scene/mechanic composition only.

Reference examples: training/gamedev_examples/*.ts (snake, pong,
flappy, asteroids, platformer, racing, etc.). Each is one scene with
a handful of mechanics (move, collide, spawn, score).

## BEFORE YOU EMIT (F-A4: source-before-priors)

**Step 0 — Read the catalog BEFORE the first emit_design call.** The
engine catalog is the source of truth for which MechanicType values
the compiler accepts. Do not invent types from priors — they will fail
validation (Qwen has a training cutoff; the catalog has moved since).

**The absolute path to each file is provided in the system prompt's
`# GAMEDEV OVERRIDE (turn-1)` block** — use those paths verbatim with
`file_read`. `schema.ts` carries the `MechanicType` string-literal
union — the complete list of accepted types. Your emitted design's
`mechanics[].type` values MUST match one of those literals.

If your prompt calls for a mechanic the catalog lacks (e.g., an exotic
fighting-game stance system), emit the closest existing type and
leave a code-comment proposing a NEW mechanic for
`scaffolds/.claude/game_essence/catalog_proposals.md`.

**Step 0b — Check the full CatalogEntry metadata for any mechanic
you're unsure about** — `catalog.ts` absolute path is also in the
GAMEDEV OVERRIDE block. Each entry carries description + example_params
+ needs_mechanic_types + tier. Use the example_params structure when
setting your design's params — don't reshape them.

## TOC
- [>] [Concept](#concept)
- [ ] [Entities](#entities)
- [ ] [Mechanics](#mechanics)
- [ ] [Scenes](#scenes)
- [ ] [Design](#design)
- [ ] [Build](#build)
- [ ] [Play](#play)
- [ ] [Deliver](#deliver)

## Concept
One-line identity: what is the game.
- Genre: arcade / platformer / puzzle / racing / rhythm / shooter /
  action-adventure / metroidvania / fps / jrpg / rts / stealth / ...
  (see injected GENRE directive when scaffold=gamedev)
- Core verb: jump / dodge / shoot / match / solve / chase / explore
- Win/lose condition: score target, reach goal, survive timer
- Reference from training/gamedev_examples/: pick the closest analog

## Entities
Game objects with position, velocity, sprite/shape, health.
- Player: one per scene, input-driven movement
- Obstacles: cars, enemies, walls (static or moving)
- Collectibles: coins, logs, power-ups
- Each entity has a `type`, optional `sprite` or `color+shape`, and
  a set of attached mechanics

**If a CONTENT CATALOG directive was injected** (prompt names a
specific game replica like "Zelda-like"), use the named enemies/
bosses/items from that directive VERBATIM. Do not invent "Enemy 1"
when the catalog says "Octorok."

## Mechanics
Declarative behaviors from the engine catalog. Each mechanic has a
`type` + `params`. The `type` must match a `MechanicType` literal from
schema.ts (read at Step 0 above).

**High-frequency mechanics by genre** (full list in schema.ts — these
are starting points, not restrictions):

| Genre              | Typical mechanics                                   |
|--------------------|-----------------------------------------------------|
| platformer         | PhysicsModifier · CameraFollow · PickupLoop · CheckpointProgression · AttackFrames |
| action_adventure   | RoomGraph · LockAndKey · ItemUse · CameraFollow · HUD · ComboAttacks |
| fps                | CameraFollow · BulletPattern · WaveSpawner · HUD · AttackFrames |
| metroidvania       | RoomGraph · LockAndKey · GatedTrigger · ItemUse · PhysicsModifier |
| jrpg               | DialogTree · Shop · InventoryCombine · LevelSequence · HUD |
| rts                | UtilityAI · RoleAssignment · CrowdSimulation · WaveSpawner · HUD |
| universal          | HUD · LoseOnZero · WinOnCount · ScoreCombos · Difficulty · ChipMusic · SfxLibrary |

Audio (always useful):
- `ChipMusic`: base_track + overlay_tracks + bpm + mixer (5-channel
  chiptune). Track arrays are lists of {note, duration, channel}
  events; tempo via BPM ref or flat number.
- `SfxLibrary`: named sfxr patches keyed to events (onJump, onCollect).

Full catalog: schema.ts (type union) + catalog.ts (metadata).

## Assets (sprites)
If the game needs visuals beyond colored shapes, emit an
`assets.manifest.json` at project root alongside game_definition.json.
Each asset has id, category (sprite|tileset|background), prompt, and
optional metadata. The build step runs `tools/build_sprites.py
<project_dir>` which:
- Calls generate_asset() per entry (ERNIE-Image-Turbo at :8092)
- Caches PNGs by prompt hash
- Copies to public/sprites/<id>.png
- Emits public/sprites/manifest.json for src/sprites/loader.ts

Reference entities in the design via `sprite: <id>` instead of a
color+shape.

## Scenes
Each scene is a bounded playfield with entities + mechanics + win/lose.
- main: the gameplay scene
- gameover: shown when lose condition hits (optional — drone can
  default to restart)
- Transitions: flow[] defines scene order

**For action_adventure / metroidvania / jrpg**: emit AT LEAST 2 scenes
(overworld + dungeon, or towns + world-map). A single-scene game in
these genres fails the genre directive's would_falsify criterion.

## Design

**Tool-call shape** — emit_design takes TWO sibling parameters:
`design` (the JSON object below) and `project_name` (a kebab-case
string). Call it like:

```
emit_design(design={...see below...}, project_name="zelda-overworld")
```

Do NOT put `project_name` INSIDE the design object — the tool validator
rejects calls with missing top-level project_name. Round N captured 3
consecutive emit_design calls failing this way.

**Design shape** — `design` payload below. Field names MATCH
`scaffolds/engine/src/design/schema.ts` DesignScript interface exactly.
Do NOT emit `entities` or `scenes` at root — those names are NOT
schema fields and the validator reads `raw.archetypes` + `raw.flow`
ONLY (see validate.ts:79, 141). Round K/L captured waves emitting
`entities: [...]` and failing validation with `tag_requirement` /
`archetype not declared` errors because no archetype existed.

```json
{
  "meta": {
    "title": "Human-facing title",
    "shape": "action",
    "vibe": ["classic", "top_down", "dungeon_crawl"]
  },
  "config": {
    "mode": "2d",
    "camera": "orthographic",
    "playfield": { "kind": "continuous", "arena": { "shape": "rect", "size": 20 } }
  },
  "singletons": {},
  "archetypes": {
    "player": {
      "controller": "topdown",
      "components": ["Health(4)", "Inventory"],
      "tags": ["player"],
      "sprite_ref": "link"
    },
    "octorok": {
      "controller": "none",
      "ai": "patrol",
      "components": ["Health(1)"],
      "tags": ["enemy"],
      "sprite_ref": "octorok_red"
    }
  },
  "mechanics": [
    { "id": "cam", "type": "CameraFollow",
      "params": { "target": "player" } },
    { "id": "rg",  "type": "RoomGraph",
      "params": { "scenes": ["overworld", "dungeon_1"] } }
  ],
  "flow": {
    "kind": "scene",
    "name": "overworld",
    "transition": { "type": "fade" }
  }
}
```

**Key rules**:
- `archetypes` is a **dict** keyed by archetype id (NOT a list)
- Each archetype has `components: string[]` and `tags: string[]` (both required)
- `mechanics` IS a list of `{ id, type, params }` objects
- `flow` is a **single FlowNode** object (NOT a list) — see schema.ts
  types for `{ kind: 'scene' | 'level_sequence' | 'room_graph' | ... }`
- If a mechanic like `CheckpointProgression` declares `requires_tags`,
  one of your `archetypes` MUST have that tag (e.g. `tags: ["checkpoint"]`)
  or validation fails with `tag_requirement`

Emit the full game_definition.json via the `emit_design` tool. It
deposits to `public/game_definition.json` which the scaffold's main.ts
loads at boot. Do NOT write App.tsx — the scaffold is engine-only.

**emit_design tool-call shape**: the `design` parameter accepts a
JSON object. Pass it as an object (`{"design": {...}}`), not as a
stringified JSON (`{"design": "{\"project_name\": ...}"}`). The Python
side handles both but the object form is cache-friendlier and avoids
tool-arg validation quirks.

If the design is large, consider splitting into multiple mechanics
definitions and referencing them by id rather than inlining
everything into a single monolithic object.

## Build
shell_exec cd {project_path} && npm run build
(tsc + vite; no React tests for gamedev — the design compiler's own
validator is the gate)

## Play
Delivery-time gate: `core/gamedev_probe.py` validates
`public/game_definition.json` shape + catalog composition.

Pass criteria:
- game_definition.json exists and parses
- ≥1 scene, ≥1 entity, ≥1 mechanic
- All mechanic `type` values are known MechanicType literals
- ≥1 catalog mechanic (not 100% invented types)

Vision gate: VLM judges the running canvas — is it rendering? Does
the scene match the declared genre?

## Deliver
message_result with a one-line description of the game built.

## Known failure modes (don't repeat)

- **Don't write src/App.tsx** — gamedev scaffold is engine-only; the
  deliver-gate will reject App.tsx writes on gamedev projects.
- **Don't pass the entire design as a string** — inline JSON strings
  >10 KB can crash some tool plumbing. Pass the design as a structured
  object in the tool arguments.
- **Don't invent MechanicType values** — unknown types fail validation
  at compile time. Read schema.ts at Step 0; when the catalog lacks
  what you need, use the nearest existing type and comment a NEW
  proposal.
- **Don't skip emit_design and try file_write on design.json** — the
  safety gate blocks writes to workspace root; and even if you write
  it yourself, the compiler validation pass won't fire.
