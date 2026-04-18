# Prompt 003 — Pac-Man-style maze chase

**Pitch:** navigate a maze collecting pellets; four ghosts chase you; power pellets reverse roles briefly; clear all pellets to advance.

**Verdict:** **expressible with caveats**

**Proposed design (sketch):**
- archetypes: `pacman` (player, topdown controller), `ghost_blinky` / `pinky` / `inky` / `clyde` (each with distinct AI profile), `pellet`, `power_pellet`, `wall`
- mechanics: `PickupLoop` (pellets), `WinOnCount` (all pellets eaten), `LoseOnZero` (lives), `Difficulty` (ghost speed vs. level)
- flow: title → maze_1 → maze_2 → ... → gameover

**Missing from v0:**
- Power-pellet reversal: needs a **temporary mode flip** — `power_pellet.trigger:"pickup"` should toggle a global state that changes ghost `ai` from `chase` to `flee` for N seconds. No `TimedStateModifier` mechanic exists.
- Distinct ghost AIs: v0 has `ai:"chase"` monolithic. Blinky/Pinky/Inky/Clyde use four different targeting heuristics (direct, ahead-4-tiles, Blinky-reflection, distance-toggle). Need `ai:"bt:<tree_name>"` with per-ghost BT definitions.
- Maze geometry: hand-authored level. See prompt_001 LevelSequence note.
- `Lives` component: present in ComponentSpec ("Lives(3)") but the LoseOnZero → respawn cycle isn't spec'd — does LoseOnZero tear down the scene or just respawn the archetype?

**Forced workarounds:**
- Use four archetypes with `ai:"bt:blinky"` etc. — but the BT catalog needs authoring. Lift into v1.
- Power-pellet via a custom component `PowerTimer` — ad-hoc.

**v1 candidates raised:**
- `TimedStateModifier` — on trigger, flip a named flag for N seconds, flip back on expire
- `BehaviorTreeLibrary` — authored BTs referenced by `ai:"bt:<name>"`, authored in the same design script
- Clarify `LoseOnZero` semantics: respawn-in-place vs. scene-transition (param on the mechanic)

**Stall note:** the four-ghost personality system is the core Pac-Man insight. Without custom BTs, all ghosts feel identical. AI authoring is a major gap.
