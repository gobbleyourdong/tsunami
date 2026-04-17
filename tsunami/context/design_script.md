# Building games with design scripts

Game projects use a **design script** — a typed JSON document
describing archetypes, mechanics, and flow — instead of freehand
TypeScript against the engine API. A compiler translates the script to
engine calls. Schema validation catches mistakes before any code runs.

## When to use this

- Project prompt names a game / mentions gameplay / asks for playable
  content.
- Do NOT use for: dashboards, landing pages, chatbots, CRUD apps,
  form apps — those go through the existing `project_init` scaffolds.

## The tool

Call `emit_design(name, design)` with a JSON-serializable object
matching the schema below. The tool:

1. Runs the validator. Errors return as structured feedback — apply
   the suggested fix at the indicated path and retry.
2. Compiles validated design → `GameDefinition` → `src/main.ts`.
3. Builds and reports. No hand-written `App.tsx` needed.

## Domain

v1 targets **real-time single-protagonist spatial games**. Three
implicit assumptions:

1. Real-time: mechanics tick at frame rate
2. Single-protagonist: one player archetype drives input
3. Spatial: archetypes have positions in a scene

Genres that violate any assumption are out of scope. See *Decline
prompts* below.

## Script shape

```
{
  "meta": {
    "title": "...",
    "shape": "action|puzzle|sandbox|rhythm|narrative_adjacent|skater|fighter|metroidvania|maze_chase",
    "vibe": ["..."],
    "target_session_sec": 180
  },
  "config": {
    "mode": "2d|3d",
    "playfield": { "kind": "continuous", "arena": {"shape": "rect|disk", "size": N} }
                | { "kind": "grid",       "width": N, "height": N, "cell_size": N },
    "sandbox": false
  },
  "singletons": {
    "flags": { "components": ["WorldFlags"], "exposes": {"boss_defeated": "boolean"} }
  },
  "archetypes": {
    "player": {
      "mesh": "capsule",
      "controller": "topdown",
      "components": ["Health(100)", "Score", "Inventory", "Resource(mana, 50)"],
      "tags": ["player"]
    },
    "grunt": {
      "mesh": "box",
      "ai": "chase",
      "components": ["Health(20)"],
      "trigger": {
        "kind": "damage",
        "contact_side": "side",
        "on_contact": {"kind": "damage", "archetype": "player", "amount": 1},
        "on_reverse": {"kind": "damage", "archetype": "grunt",  "amount": 999},
        "when_state": "alive"
      },
      "tags": ["enemy"]
    }
  },
  "mechanics": [
    { "id": "diff", "type": "Difficulty",
      "params": { "drive": "wave_index", "easy": {"spawnRateMul": 0.6},
                  "hard": {"spawnRateMul": 2.0}, "max_level": 10 },
      "exposes": {"level": "number"} },
    { "id": "waves", "type": "WaveSpawner",
      "params": { "archetype": "grunt", "difficulty_ref": "diff",
                  "base_count": 4, "rest_sec": 6, "arena_radius": 20 },
      "exposes": {"wave_index": "number"} },
    { "id": "hud", "type": "HUD",
      "params": { "fields": [
                    { "archetype": "player", "component": "Health" },
                    { "archetype": "player", "component": "Score" },
                    { "mechanic":  "waves",  "field": "wave_index" }
                  ], "layout": "corners" } },
    { "id": "lose", "type": "LoseOnZero",
      "params": { "archetype": "player", "field": "Health",
                  "emit_condition": "player_dead" } }
  ],
  "flow": {
    "kind": "linear",
    "name": "main",
    "steps": [
      {"scene": "title"},
      {"scene": "arena", "condition": "start_pressed"},
      {"scene": "gameover", "condition": "player_dead"}
    ]
  }
}
```

Every string in `type`, `controller`, `ai`, or component-spec position
resolves through a typed registry. Unknown tokens fail validation with
`did you mean` suggestions.

## Mechanic catalog (35 mechanics, v1.1)

Order is by composability — high-composability primitives first. These
multiply outward; author from the top.

### Universal / load-bearing
- **HUD** — renders named archetype / mechanic / singleton fields on screen.
- **Difficulty** — S-curve ramp. Other mechanics multiply its exposed fields.
- **TimedStateModifier** — temporary named state with auto-expiry.
- **WorldFlags** (singleton) — global persistent boolean/enum state.
- **EmbeddedMinigame** — horizontal composition: suspend outer, run inner, resume.

### Action-core
- **WaveSpawner** — enemy-archetype waves scaled by Difficulty.
- **LoseOnZero** — emit flow condition on archetype field → 0.
- **WinOnCount** — emit flow condition on archetype-count threshold.
- **PickupLoop** — reward + respawn on pickup archetype contact.
- **ScoreCombos** — windowed or event-banked score multipliers.
- **CheckpointProgression** — respawn/restore from latest checkpoint.
- **ComboAttacks** — input-sequence recognition (state-gatable).
- **CameraFollow** — camera tracks archetype with deadzone + bounds.
- **BossPhases** — health-threshold FSM with on_phase_enter actions.

### Grid-puzzle — NOT in this scaffold
Grid-based puzzles (Sokoban, Tetris, tile-rewrite) belong in a separate
grid-puzzle scaffold (not yet built). Decline prompts that are primarily
grid-based; offer the closest real-time-spatial match.

### Narrative + adventure
- **DialogTree** — branching conversation with state-gated choices.
- **HotspotMechanic** — clickable scene regions.
- **InventoryCombine** — recipe table combining items.
- **ItemUse** — inventory → ActionRef mapping.
- **PointerController** — cursor-driven input.
- **PuzzleObject** — mutable world object with state transitions.

### Level + flow
- **LevelSequence** — ordered authored levels with per-level win/fail.
- **RoomGraph** — directed graph of rooms with gated edges.
- **GatedTrigger** — condition-gated door/path.
- **LockAndKey** — key-tag opens lock-tag on contact.
- **EndingBranches** — multi-ending selection by predicates.

### Systems + meta
- **Shop** — vendor + currency-gated purchases.
- **StateMachineMechanic** — declarative FSM on archetype.
- **StatusStack** — poison/sleep/haste multi-slot with conflicts.
- **UtilityAI** — action selection by utility score over needs.
- **VisionCone** — stealth: cone + LoS + alert-state FSM.
- **AttackFrames** — fighter hitbox/hurtbox frame windows.
- **RhythmTrack** — beat timeline synced to audio.

### Sound (v1.1 audio extension)
- **ChipMusic** — 4+1 channel chiptune: pulse1, pulse2, triangle,
  noise, optional custom wave. ADSR per note, BPM can be a number or
  `{mechanic_ref, field}` to tempo-follow Difficulty or similar.
  Supports N overlay tracks parallel-indexed to `overlay_conditions`
  (fade in/out per condition). Channel routes to `'music'` or
  `'ambient'`.
- **SfxLibrary** — named catalog of sfxr parameter sets. Consumers
  fire presets through `ActionRef { kind: 'play_sfx_ref',
  library_ref: '<mechanic_id>', preset: '<name>' }`.

```jsonc
// ChipMusic example — looping action chiptune + boss overlay
{ "id": "music", "type": "ChipMusic",
  "params": {
    "base_track": {
      "bpm": { "mechanic_ref": "diff", "field": "level" },
      "loop": true, "bars": 4,
      "channels": {
        "pulse1":   [{"time": 0, "note": "C4", "duration": 0.5}, ...],
        "triangle": [{"time": 0, "note": "C3", "duration": 2}],
        "noise":    [{"time": 0, "note": "kick",  "duration": 0.25},
                     {"time": 1, "note": "snare", "duration": 0.25}]
      }
    },
    "overlay_tracks":     [ /* layer A */, /* layer B */ ],
    "overlay_conditions": ["intensity_high", "boss_phase_2"],
    "channel": "music"
  }
}
```

```jsonc
// SfxLibrary example — named presets pre-rendered at load
{ "id": "sfx", "type": "SfxLibrary",
  "params": {
    "sfx": {
      "coin":    { /* sfxr params — see cheat-sheet */ },
      "jump":    { ... },
      "hit":     { ... }
    }
  }
}
```

Sfxr parameter cheat-sheet (27 fields; start from an archetype and
tweak):
- `waveType`: `'square' | 'sawtooth' | 'sine' | 'noise'`
- envelope: `envelopeAttack`, `envelopeSustain`, `envelopePunch`,
  `envelopeDecay` (all 0..1)
- pitch: `baseFreq` (0..1, higher = higher pitch), `freqRamp`
  (positive = pitch-up, negative = pitch-down)
- vibrato: `vibratoStrength`, `vibratoSpeed`
- arpeggio: `arpMod`, `arpSpeed`
- filters: `lpFilterCutoff`, `hpFilterCutoff`, `lpFilterResonance`
- `masterVolume`: 0..1 · `sampleRate`: 44100 | 22050 | 11025
- Archetypes (pickup, laser, explosion, powerup, hit, jump, blip) —
  good starting points; reduce `envelopePunch` for softer SFX.

Drum names on the `noise` channel: `kick`, `snare`, `hat`,
`hat_closed`, `hat_open`, `crash`, `tom_hi`, `tom_lo`.

Quantization: audio ActionRefs accept `quantize_to: 'beat'|'half'|
'bar'` to snap SFX firing to the grid of a running ChipMusic track
(via `quantize_source: '<chipmusic_id>'`). Useful for rhythm-coupled
games.

## Archetypes — trigger shapes

A `trigger` can be a string (sugar for simple triggers) or a
`TriggerSpec` object with directional contact + actions:

```
// Simple pickup (sugar)
"trigger": "pickup"

// Directional damage (Goomba-style)
"trigger": {
  "kind": "damage",
  "contact_side": "top|bottom|side|front|back|any",
  "on_contact": { "kind": "damage", "archetype": "player", "amount": 1 },
  "on_reverse": { "kind": "damage", "archetype": "self",   "amount": 999 },
  "when_state": "alive",
  "exclusive": false
}
```

## Decline prompts — out-of-scope genres

When a prompt names one of these genres, do NOT attempt a design
script. Respond with a redirect message + optionally suggest the
closest in-scope match.

- **Text adventure / Zork / interactive fiction / parser-driven** →
  "Use Inform 7 or Twine — this method targets real-time spatial
  games. Closest supported: narrative-adjacent adventure with
  hotspots and dialogue."
- **Real-time strategy (RTS) / StarCraft / multi-unit command** →
  "v1 is single-protagonist. Use a dedicated RTS engine."
- **Turn-based strategy / Fire Emblem / Civilization / Advance Wars** →
  "v2 — requires PhaseScheduler + grid + roster persistence. Not
  supported yet. Closest in-scope: grid-puzzle (Sokoban-style)."
- **JRPG battle system / ATB / Chrono-like combat** →
  "v2 — requires BattleSystem sub-schema. Overworld-only Chrono-
  style exploration IS supported; the combat overlay is v2."
- **Racing simulator / lap-based / track geometry** →
  "v2 — requires VehicleController + TrackSpline. Trick-scorer
  style (THPS) IS supported."
- **Persistent simulation / SimCity / multi-day** →
  "v2 — requires persistent timeline + save system. Short-session
  sandbox (sandbox flag) IS supported."

## Sprites (v1.1 sprite extension)

Archetypes can reference a generated sprite via `sprite_ref`:

```jsonc
"archetypes": {
  "player": {
    "controller": "topdown",
    "components": ["Health(100)", "Score"],
    "tags": ["player"],
    "sprite_ref": "player_hero"      // ← points at assets.manifest.json
  }
}
```

The game's `assets.manifest.json` declares the sprite source alongside
the design script:

```jsonc
// scaffolds/<game>/assets.manifest.json
{
  "schema_version": "1",
  "backend": "ernie@turbo-8s",
  "assets": [
    {
      "id": "player_hero",
      "category": "character",       // one of 8 registered categories
      "prompt": "pixel art hero with sword, side view, green tunic",
      "metadata": { "class": "hero", "facing": "side" }
    },
    {
      "id": "grass_tiles",
      "category": "tileset",
      "prompt": "pixel art grass tiles, 4x4 grid, overworld, top-down",
      "metadata": {
        "biome": "overworld",
        "tile_grid_w": 4,
        "tile_grid_h": 4
      }
    }
  ]
}
```

**8 categories** (pick the most specific match):
- `character` — full-body figure, side/front view, one subject
- `item` — small centered pickupable: coin, potion, key, weapon
- `texture` — seamless tileable pattern
- `tileset` — N×N grid of terrain tiles (needs `tile_grid_w`/`tile_grid_h`
  in metadata; builder splits + emits atlas.json)
- `background` — wide horizontal parallax layer, no centered subject
- `ui_element` — flat menu/HUD chrome (button, panel, icon, bar)
- `effect` — radial visual effect (explosion, magic, impact, glow)
- `portrait` — JRPG-style head-and-shoulders dialogue portrait

**Every archetype's `sprite_ref` must be declared in the manifest.**
Missing id → validator fires `sprite_ref_not_in_manifest`. Unknown
category → `unknown_category`. Metadata type mismatch →
`metadata_schema_violation`.

For content-heavy designs (metroidvanias, RPGs with many enemies) just
list every archetype's sprite in the manifest — the pipeline caches
content-addressably, so a prompt/setting revision re-generates only
the affected assets.

## Conditions must be emitted

Every `condition` key you reference in `flow.linear.steps[*].condition`
or in a trigger's `when_state` / `on_contact { kind: 'emit' }` etc.
MUST be emitted by a mechanic in the same design. Emitters are:

- `LoseOnZero { emit_condition: "player_dead" }` → emits when its
  field hits 0
- `WinOnCount { emit_condition: "all_collected" }` → emits when count
  matches target
- `CheckpointProgression { emit_condition_on_reach: "checkpoint_1" }`
- An explicit `{ "kind": "emit", "condition": "key" }` ActionRef
  dispatched from a trigger or timeline event

**Do NOT invent bare condition keys** (e.g. `start_pressed`,
`menu_dismissed`) expecting input-handling mechanics to exist — they
don't. If a scene needs to auto-advance, leave off `condition`; the
linear flow steps through in order. Dangling conditions are the #1
validator failure.

Good:
```jsonc
"flow": { "kind": "linear", "name": "run",
  "steps": [
    { "scene": "gameplay" },
    { "scene": "game_over", "condition": "player_dead" }
  ]
}
// + a LoseOnZero mechanic with emit_condition: "player_dead"
```

Bad:
```jsonc
"flow": { "kind": "linear", "name": "run",
  "steps": [
    { "scene": "title" },
    { "scene": "arena", "condition": "start_pressed" },  // ← dangling!
    { "scene": "game_over", "condition": "player_dead" }
  ]
}
// No mechanic emits "start_pressed" → validator kills this design.
```

## Error feedback protocol

When validation fails:

```
SchemaError: unknown mechanic type 'WavSpawner' at mechanics[1].type
  did you mean: WaveSpawner
  catalog: reference/catalog.ts

ReferenceError: mechanics[0].params.archetype references 'grunts'
  which is not declared.
  Declared: player, grunt, coin

DanglingConditionError: flow.children[2].condition 'player_dead' is
  never emitted.
  Mechanics that could emit this: LoseOnZero, LoseOnCount

TagRequirementError: mechanics[1] (WaveSpawner) requires at least one
  archetype with tag 'enemy'. Archetypes tagged: player.

CompatibilityError: archetype 'player' has controller='fps' which
  requires config.mode='3d'. Current mode: '2d'.

CycleError: mechanics form a cycle through exposed fields:
  'enemy_ai' reads 'hud.last_damage' → 'hud' reads 'enemy_ai.alert'.
```

Apply the suggested fix. Do NOT regenerate the whole script — edit the
indicated path.

## Mechanic arbitration

Lowering order is: singletons → archetypes → mechanics by priority
class. Priority classes (earliest → latest): `pre_update` → `sensors`
→ `state_modifiers` → `default` → `effects` → `hud`. Within a class,
declaration order breaks ties.

Example: damage source and `TimedStateModifier(invuln)` — the
modifier lands in `state_modifiers`, damage handlers land in `effects`.
Invuln applies before damage reads state. Deterministic regardless of
declaration order.

## Three example scripts

### Arena shooter (action-core)

```
(full Stage-1 script from attempt_003 — action shape; arena shooter with
 grunts, waves, difficulty ramp, lose-on-player-death)
```

### Sokoban variant — NOT in this scaffold
Grid puzzles belong in a separate scaffold. Example retired at
`context/examples/_retired_sokoban_grid_scaffold_seed.json` as a seed
for the grid-puzzle scaffold when it is built.

### Point-and-click adventure (narrative-adjacent)

```
(pointer controller + HotspotMechanic + DialogTree + InventoryCombine +
 PuzzleObject mechanisms; rooms via RoomGraph; EndingBranches by flags)
```

Tsunami receives these three scripts rendered inline; the model
nearest-matches to the prompt and remixes parameters + composes
mechanics.

## Authoring rules

- Never write `App.tsx` or `src/main.ts` for game projects. The
  compiler emits both.
- Never call engine APIs (`new Game(...)`, `game.scene(...).spawn(...)`)
  in emitted code. The compiler generates these.
- Never invent mechanic types. Only the 33 types above are valid.
- Always cite existing archetypes by key when a mechanic references
  them. Unknown references fail validation.
- Always include at least one archetype tagged `player` in
  non-sandbox designs.
- For sandbox designs (`config.sandbox: true`), LoseOnZero / WinOnCount
  are optional; the game runs forever.
