# Plan: {goal}

Game-dev plan — drone provisions a **pre-built genre scaffold** and then
edits `data/*.json` + `src/scenes/*.ts` to specialize it. Scaffolds ship
PLAYABLE: scenes, mechanics, placeholder assets, and catalog wiring are
all prewired from `@engine/mechanics`. Your job is **content**, not
skeleton-building.

Available genres (scaffolds at `scaffolds/gamedev/<genre>/`):

| genre              | ships                                                          |
|--------------------|----------------------------------------------------------------|
| `custom`           | universal base — single scene, mountMechanic helper            |
| `action_adventure` | Overworld + Dungeon + GameOver; CameraFollow + RoomGraph + LockAndKey + BossPhases; 4 enemy archetypes + 6 items (Zelda/Metroid/Tomb Raider heritage) |
| `fighting`         | CharSelect → VsScreen → Fight → Victory; ComboAttacks + AttackFrames + HUD; 6 fighters + 6 stages (SF2/MK2/Tekken3 heritage) |
| `magic_hoops`      | Single Match scene — cross-genre canary (sports + fighting + RPG magic); 2 wizards, 6 spells, 2 goals, score_vs_clock rules |

## TOC
- [>] [Concept](#concept)
- [ ] [Provision](#provision)
- [ ] [Customize](#customize)
- [ ] [Build](#build)
- [ ] [Play](#play)
- [ ] [Deliver](#deliver)

## Concept

One-line identity: what is the game. Pick the closest genre; if the
prompt spans multiple (e.g. "sports game with magic PvP"), use
`magic_hoops` as the cross-genre template.

- Genre: action-adventure / fighting / custom / magic_hoops
- Core verb: explore / combo / shoot / match / chase
- Win/lose condition: ships with the scaffold — tune in `data/rules.json`

## Provision

**Step 1** — call `project_init_gamedev` with a project name + genre:

```
project_init_gamedev(name="zelda-like", genre="action_adventure")
```

The tool copies `scaffolds/gamedev/<genre>/` → `workspace/deliverables/<name>/`,
symlinks the engine as a sibling, rewrites path aliases so `@engine/*`
resolves, runs `npm install`, and starts the dev server. It returns a
list of files that are the **primary edit surface** — typically
`data/*.json` and `src/scenes/*.ts`.

**Do NOT** write `game_definition.json`, `App.tsx`, or hand-author a
scaffold. The genre scaffolds are the scaffolding.

## Customize

The genre scaffold is already playable. You're tuning its **content**
(characters, items, rooms, spells, rules) and possibly adding a new
scene or remounting a different mechanic.

### Data files (`data/*.json`)

Every genre scaffold has at minimum:
- `config.json` — viewport, starting scene, mode
- `rules.json` — win condition, timers, HP-per-respawn, etc.

Plus genre-specific files:
- `action_adventure`: `rooms.json` (room graph), `entities.json` (enemy
  archetypes + items)
- `fighting`: `characters.json` (6 fighters), `moves.json` (frame data
  per fighter), `stages.json`
- `magic_hoops`: `arena.json` (court + goals + ball), `characters.json`
  (wizards + HP + mana), `spells.json` (6 spells with mana + cooldowns)

**If a CONTENT CATALOG directive was injected** (prompt names a specific
replica like "Zelda-like"), use the named enemies/bosses/items from
that directive VERBATIM in `data/entities.json`. Don't invent "Enemy 1"
when the catalog says "Octorok."

### Scenes (`src/scenes/*.ts`)

Each scene already mounts its mechanics via `mountMechanic('Type',
params)` from `@engine/mechanics`. Common customizations:
- Add a scene (boss room, victory screen) by copying an existing scene
  and wiring its mechanics
- Swap a mechanic (e.g. replace `CameraFollow` with `FixedCamera` in
  action_adventure) by editing `tryMount()` calls
- Add a cross-genre mechanic — look up the type in
  `scaffolds/engine/src/design/schema.ts` `MechanicType` union

**Architecture rule:** scenes import ONLY from `@engine/mechanics`.
Never `from '../../mechanics'` or `../../components`. The magic_hoops
canary test enforces this — treat it as the ceiling for every scaffold.

### Adding a new mechanic type

If the catalog in `scaffolds/engine/src/design/schema.ts` lacks the
exact mechanic you need, **don't invent one inline**. Options:
1. Find the closest match from the 46 `MechanicType` literals and tune
   its params.
2. If genuinely novel, propose it in
   `scaffolds/.claude/game_essence/catalog_proposals.md` — a future
   pass will land the runtime + tests. Do NOT block a scaffold build
   on a new mechanic.

## Build

```
shell_exec cd {project_path} && npm run build
```

The scaffold's `tsc` step catches missing imports. If it fails, read
the error and edit the offending scene/data file — don't rebuild the
scaffold from scratch.

## Play

Delivery gate checks:
- `package.json`, `tsconfig.json`, `vite.config.ts` exist (scaffold
  was provisioned correctly)
- `data/*.json` all parse
- Every `tryMount('X', ...)` mechanic name in `src/scenes/*.ts` is a
  registered `MechanicType` (the canary invariant)
- Scene imports come from `@engine/mechanics` (no relative-up imports
  bypassing the Layer 2 barrel)

Vision gate: VLM judges the running canvas — is the scene rendering,
is content visible, does it match the declared genre?

## Deliver

`message_result` with a one-line description of what was built. The
scaffold ships with a README documenting the genre's default
customization paths — don't restate it, just point to the deliverable.

## Known failure modes (don't repeat)

- **Don't call `emit_design`** on a gamedev task when a matching genre
  scaffold exists. `emit_design` is a fallback for genres without a
  scaffold (rts, tbs, interactive fiction, etc.) and even those are
  better served by widening the catalog than by bespoke JSON emission.
- **Don't write `App.tsx`** — gamedev scaffolds are engine-only. The
  delivery gate rejects `App.tsx` writes on gamedev projects.
- **Don't hand-author `game_definition.json`** — the genre scaffold
  replaces this with `data/*.json` files that the scene loads at boot.
  The old flow used a single compiled design; the new flow uses
  multiple live-loaded JSON files + prewired scenes.
- **Don't import mechanics via relative paths** from a scene — always
  `from '@engine/mechanics'`. The magic_hoops canary test fails if
  any scaffold breaks this; treat it as an invariant.
- **Don't invent `MechanicType` values** — use `catalog.ts` for the
  full registered list. If the catalog lacks something, propose it in
  `catalog_proposals.md` and use the nearest existing type for now.
