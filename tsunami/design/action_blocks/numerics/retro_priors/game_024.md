# Game 024 — Lemmings (1991, Amiga)

**Mechanics present:**
- Lemmings spawn from entrance, walk by default — **not in v0** (`PathFollower` automated)
- Player assigns roles (Climber, Floater, Bomber, Blocker, Builder, Basher, Miner, Digger) — **not in v0** (`RoleAssignment` — click lemming to change its behavior)
- Each role modifies the archetype's walking behavior (climb walls, build stairs, dig through ground) — runtime archetype behavior modification
- Level goal: save X of Y lemmings by bringing them to exit — `WinOnCount` works (count at exit >= threshold)
- Time limit per level — `LoseOnZero` on a Timer resource
- Destructible terrain — **not in v0** (physics-altering archetype state)
- Role-count limit per level (e.g. 5 builders available) — `Resource` per-role
- Level sequence with escalating difficulty — LevelSequence (noted)
- Nuke button (kill all lemmings if stuck) — `AbortAction` global
- Sound cues per role (speech clip when clicking) — audio event
- Visual-variety per role (sprites change) — archetype state → visual map

**Coverage by v0 catalog:** ~1/11

**v1 candidates from this game:**
- `RoleAssignment` — click lemming → change its AI behavior (runtime BT swap on archetype instance)
- `DestructibleTerrain` — environment archetypes with state + deletion conditions
- `RoleBudget` — limited Resource per-role, consumed on assignment
- Automated-pathing archetype (walk until obstacle, then default behavior)

**Signature move:** **role assignment as player input.** The player never directly controls a lemming — they reshape the lemmings' available behaviors. The game is "nudge a crowd by changing their rules." Conceptually close to Tower Defense (place towers to shape enemy path) but reversed: you're shaping allied units. The primitive `RoleAssignment` is a simple runtime-BT-swap but the emergent design space is large. Worth v1 if puzzle-genre is targeted.

**Genre classification:** Lemmings is puzzle + real-time. Not turn-based. Not grid-locked (movement is continuous). This is a valuable data point: puzzle genre isn't necessarily grid/turn-based — Lemmings is real-time continuous. Grid-mode (note_002) is NOT a universal puzzle requirement.
