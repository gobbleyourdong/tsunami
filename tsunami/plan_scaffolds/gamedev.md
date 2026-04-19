# Plan: {goal}

Game-design plan — drone emits a single `game_definition.json` via
`emit_design` tool. The engine at scaffolds/engine/ consumes that JSON
and runs the game. No raw React — scene/mechanic composition only.

Reference examples: training/gamedev_examples/*.ts (snake, pong,
flappy, asteroids, platformer, racing, etc.). Each is one scene with
a handful of mechanics (move, collide, spawn, score).

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
- Genre: arcade / platformer / puzzle / racing / rhythm / shooter
- Core verb: jump / dodge / shoot / match / solve / chase
- Win/lose condition: score target, reach goal, survive timer
- Reference from training/gamedev_examples/: pick the closest analog

## Entities
Game objects with position, velocity, sprite/shape, health.
- Player: one per scene, input-driven movement
- Obstacles: cars, enemies, walls (static or moving)
- Collectibles: coins, logs, power-ups
- Each entity has a `type`, optional `sprite` or `color+shape`, and
  a set of attached mechanics

## Mechanics
Declarative behaviors from the engine catalog. Each mechanic has a
type + params. Common ones:
- Move: direction, speed, input_source (keyboard | ai | path)
- Collide: targets[], on_hit (damage | destroy | score | bounce)
- Spawn: every_seconds, entity_type, at_position
- Score: increment_on (collide | collect | survive_time), display
- Timer: duration, on_zero (game_over | next_scene)
- ChipMusic: base_track + overlay_tracks + bpm + mixer (5-channel
  chiptune: pulse1/pulse2/triangle/noise/wave). Track arrays are
  lists of {note, duration, channel} events; tempo via BPM ref or
  flat number. See src/design/mechanics/chip_music.ts.
- SfxLibrary: named sfxr patches keyed to events (onJump, onCollect).
  8-bit classic synthesis — no external samples.

Full catalog: scaffolds/engine/src/design/mechanics/.

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

## Design
Emit the full game_definition.json via the `emit_design` tool. It
deposits to `public/game_definition.json` which the scaffold's main.ts
loads at boot. Do NOT write App.tsx — the scaffold is engine-only.

## Build
shell_exec cd {project_path} && npm run build
(tsc + vite; no React tests for gamedev — the design compiler's own
validator is the gate)

## Play
Delivery-time vision gate sees the game running. VLM judges:
- Is the canvas rendering (not blank)?
- Are player + obstacles visible?
- Does the scene match the requested genre?

Replay check (future): undertow could press arrow keys and verify
state changes.

## Deliver
message_result with a one-line description of the game built.
