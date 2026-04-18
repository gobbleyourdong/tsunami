# Prompt 012 — Real-time strategy (StarCraft-style)

**Pitch:** gather resources; build base; produce units; control them in group battles; tech tree; fog of war; win by eliminating opponent.

**Verdict:** **impossible**

**Proposed design (sketch):**
- archetypes: `worker` (gather), `combat_unit_*` (many), `building_*` (many), `resource_node`
- mechanics: `ResourceGathering`, `BuildOrder`, `TechTree`, `FogOfWar`, `UnitSelection`, `GroupCommand`, `AIPlayer` (opponent), `Economy` — **none in v0**

**Missing from v0:**
- **Selection-driven input** — drag-to-select multiple archetypes, right-click to command. v0 keyboard/controller input model can't do unit selection at all.
- **Order queue per unit** — right-click-move, shift-queue. Each unit has an instruction stack. `ai:"idle"` + user commands is the shape; v0 has no "player-commands-AI-unit" concept.
- **Resource gathering + economy** — workers loop: walk-to-node → harvest → return → deposit. Stateful loops with resource flows. Pipe structure between archetypes (`Resource` flow). Not `PickupLoop` (worker doesn't accumulate; player's money pool does).
- **Build queue on buildings** — building archetype produces units over time. `ProductionCycle` (noted in farming sim) but with a queue.
- **Tech tree / prerequisite graph** — "can build Barracks only after Supply Depot." Dependency DAG of unit/building unlocks.
- **Fog of war** — vision per friendly unit; enemy hidden until revealed. Global shader effect over entire map.
- **Opposing AI player** — strategic AI that plays the game like a player would. Beyond BT scale — goal-oriented planning.
- **Minimap** — canvas render of whole map + unit dots. HUD variant.
- **Group control** — bind-to-number (1-9), recall group. Input shortcut system.

**Forced workarounds:** none worth naming. RTS is fundamentally a different game model.

**v1 candidates raised:**
- Entire `RTSMode` schema extension — probably a third schema like IF
- Or: v3-priority. Narrow target for v1: skip RTS.

**Stall note:** RTS joins IF as a genre that v0's schema assumption (one player archetype in a real-time scene, keyboard/gamepad controlled) fundamentally doesn't serve. Recommend documenting v0 as **"real-time single-protagonist spatial games"** and pushing RTS/IF out of scope until a clear demand signal appears.
