# Game 012 — StarCraft (1998, PC)

**Mechanics present:**
- Drag-select unit groups — **not in v0**
- Right-click contextual orders — **not in v0**
- Resource harvesting (minerals, vespene gas) — **not in v0** (`ResourceGathering`)
- Build queue per building — **not in v0** (queued `ProductionCycle`)
- Tech tree (prerequisite graph for unit/upgrade) — **not in v0** (`TechGraph`)
- Population cap + supply buildings — **not in v0** (`PopulationCap` mechanic)
- Fog of war — **not in v0** (`FogOfWar`)
- Minimap — **not in v0** (HUD variant)
- Unit hotkey groups (Ctrl+1 recall) — **not in v0** (input binding extension)
- AI opponent player — **not in v0** (strategic AI beyond BT)
- Mission scripting (campaign) — partial (flow close; triggers missing)
- Cinematic cutscenes between missions — partial (Intermission noted earlier)
- Three asymmetric races (Terran/Zerg/Protoss) — not a mechanic per se but asymmetric archetype sets
- Multiplayer LAN / BattleNet — **not in v0** (network multiplayer)

**Coverage by v0 catalog:** ~0/14

**v1 candidates from this game:**
- Entire `RTSMode` — likely out of v1 scope per prompt_012 analysis
- `MissionTrigger` — authored condition → effect mid-gameplay (useful beyond RTS)
- Async multiplayer framework — v3+ priority

**Signature move:** asymmetric races. Three different economies + tech trees + unit counter-systems sharing ONE ruleset. The counter-triangle (Zealot > Zergling > Hydralisk > Zealot) is the source of emergent strategy. No v0 mechanic targets "asymmetric-archetype-factions-on-a-shared-ruleset" — worth logging as a concept but not building unless RTS is targeted.

**Sampling note:** StarCraft is the reason RTS is "impossible" in v0 (prompt_012). Confirms the prompt-side finding.
