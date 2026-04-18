# Game 017 — Civilization II (1996, PC)

**Mechanics present:**
- Hex/grid world map — **not in v0** (GridPlayfield giant-scale)
- Turn-based play — **not in v0** (TurnManager)
- Cities as production archetypes with build queues — **not in v0** (queued ProductionCycle per archetype)
- Tech tree (prerequisite DAG) — **not in v0** (TechGraph — noted in StarCraft)
- Diplomatic relations between civs — **not in v0** (`DiplomacyMatrix` per-civ pair relationship state)
- Fog of war + map exploration — **not in v0** (FogOfWar — noted)
- Multiple win conditions (conquest, space race, score) — partial (multiple WinOnCount with OR semantics — v0 flow doesn't currently express OR)
- Random events (famine, barbarians) — **not in v0** (RandomEvent — noted in SimCity)
- Government types (despotism/monarchy/democracy) — **not in v0** (`GovernmentMode` — GlobalModifier variant)
- Happiness/unhappiness mechanic per city — **not in v0** (Resource per-archetype local)
- Scenarios (authored start conditions) — `LevelSequence` variant
- Save/load across hours of play — persistent save gap again

**Coverage by v0 catalog:** ~0/12

**v1 candidates from this game:**
- Same as StarCraft (prompt_012) list + Civ-specific:
- `MultipleWinConditions` with OR semantics — flow enhancement, not mechanic
- `DiplomacyMatrix`
- `GovernmentMode` / `GlobalModifier` toggle set (confirmed from StarCraft + SimCity)

**Signature move:** tech trees and multiple win paths. A game where the player chooses their own victory. Mechanically: many orthogonal progress tracks (military, tech, culture, space), any of which can terminate the game. v0's single `WinOnCount` + single `LoseOnZero` pattern can't express "EITHER conquest OR science OR score>threshold." Flow needs boolean composition of conditions.

**Structural finding:** Civ confirms the same "turn-based multi-unit strategy" bucket as StarCraft. Both violate assumptions #1 and #2. Bundling them as "strategy mode" (TurnManager + GridPlayfield + UnitSelection + PhaseScheduler) is probably the right v2+ path.
