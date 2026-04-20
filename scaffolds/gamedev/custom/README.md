# Tsunami Gamedev — Custom Scaffold

The universal base for all gamedev projects. Every genre scaffold extends this layout.

## What this is

An empty, runnable game-shell that imports from `@engine/*` (the tsunami engine at `../../engine`). `npm run dev` opens a blank canvas with a heartbeat showing the scene mounted and the mechanic registry loaded.

**When to use `custom/` directly**: cross-genre hybrids (e.g. "fighting-sports-magic"), experiments, anything that doesn't fit a pre-built genre preset.

**When to use a genre scaffold**: when your project is recognizably a single genre. Copy from `scaffolds/gamedev/fighting/` or similar, which ships with pre-wired scenes + populated `data/*.json`.

## Directory layout

```
custom/
├── package.json          # deps on ../../engine (file: link)
├── tsconfig.json         # @engine alias
├── vite.config.ts        # dev server + @engine resolution
├── index.html            # canvas mount point
├── src/
│   ├── main.ts           # boots Layer 0 + mounts MainScene
│   └── scenes/
│       └── MainScene.ts  # override this to compose mechanics
├── data/
│   ├── config.json       # game-level settings (viewport, physics, starting_scene)
│   ├── rules.json        # win condition, match format
│   └── entities.json     # entity roster — AGENTS EDIT THIS
└── public/               # static assets (sprites, sounds) — served as /
```

## How to customize

### 1. Add content — edit `data/*.json`

The wave (or you) spend 90% of time here. Add entities, tune stats, define rooms/stages/spells — all as JSON.

```json
// data/entities.json
[
  {"id": "player", "components": {
    "Health": {"current": 100, "max": 100},
    "Tags": ["player"]
  }},
  {"id": "enemy_1", "components": {
    "Health": {"current": 50, "max": 50},
    "Tags": ["enemy"]
  }}
]
```

### 2. Compose mechanics — edit `src/scenes/MainScene.ts`

```ts
import { HealthBar, GameClock, Scoreboard } from '@engine/mechanics'

export class MainScene {
  setup() {
    this.mountMechanic('HealthBar', { target: 'player', anchor: 'top-left' })
    this.mountMechanic('GameClock', { duration: 180 })
    this.mountMechanic('Scoreboard', { teams: 2 })
  }
}
```

The mechanic catalog is exported from `@engine/mechanics` — see `scaffolds/engine/src/design/catalog.ts` for the full list (46 types) with per-mechanic param specs.

### 3. Boot — edit `src/main.ts` (rarely)

The boot path is standardized. You only touch `main.ts` if the game needs a custom scene-stack, multi-window rendering, or a non-standard canvas integration.

## Component vocabulary (Layer 1)

Attach via `entity.components.<Kind>`:

- **Health**, **Mana** — resource pools
- **Stats** (open map: str/dex/int/...)
- **Tags** — queryable string set
- **Team**, **Faction**
- **Position**, **Velocity**
- **Sprite**, **Animator**
- **Controller** (input channel: player1 / player2 / ai / network)
- **Hitbox**, **Hurtbox**
- **Spellbook**, **Cooldown**
- **Score**, **Level**, **Currency**, **StatusEffect**

See `../../engine/src/components/index.ts` for type definitions.

## Mechanic catalog (Layer 2)

35 runtime mechanics registered. Import by name from `@engine/mechanics`:

Action-core: RoomGraph · LockAndKey · ItemUse · GatedTrigger · CameraFollow · CheckpointProgression · HotspotMechanic

Combat: ComboAttacks · AttackFrames · BossPhases · StatusStack · BulletPattern · WaveSpawner

Flow: LevelSequence · DialogTree · EmbeddedMinigame · EndingBranches · RouteMap

Score/progression: ScoreCombos · PickupLoop · WinOnCount · LoseOnZero · Difficulty · TimedStateModifier

UI/narrative: HUD · Shop · InventoryCombine · PuzzleObject · ProceduralRoomChain

Audio: ChipMusic · SfxLibrary · RhythmTrack

AI/stealth: UtilityAI · VisionCone · StateMachineMechanic

## Running

```bash
npm install       # first time
npm run dev       # dev server at localhost:5173
npm run build     # production build → dist/
npm run check     # TypeScript only (no bundle)
```

## Relationship to the engine

This scaffold depends on `../../engine` (local path). The engine provides:

- Layer 0: math, physics, renderer, scene, audio, input, animation, vfx, ai
- Layer 1: components (this file's `@engine/components` imports)
- Layer 2: mechanics (35 runtime) + flow + ui

See `scaffolds/engine/src/FRAMEWORK_MANIFEST.md` for the full layering.
