# Game 010 — Chrono Trigger (1995, SNES)

**Mechanics present:**
- Overworld exploration (topdown) — ✅ (topdown controller)
- Random encounter → turn-based combat (actually: visible-enemy touch-to-battle) — **not in v0** (`EncounterTrigger` + `BattleScene` transition)
- Turn-based combat system with ATB (Active Time Battle) gauge — **not in v0** (entire `BattleSystem` mechanic; ATB is its own sub-mechanic)
- Party management (up to 3 of 7 characters) — **not in v0** (`Party` mechanic)
- Character stats + level-up on XP — **not in v0** (`Stats`/`XPLeveling` mechanic)
- Equippable gear with stat mods — **not in v0** (`Equipment` mechanic; `Inventory` component is flat)
- Tech moves (per-character abilities, combo techs between party members) — **not in v0** (`AbilitySlot` + cross-character `ComboTech`)
- Multiple endings via branching choices — **not in v0** (`EndingBranches` mechanic)
- New Game+ (carry progress forward) — **not in v0** (persistent cross-save state)
- Dialogue trees with character-specific choices — partial (Dialog exists, branching/choice tree doesn't)
- Item shop + inn (rest = heal) — `Shop` gap (noted in Zelda)
- Time travel as narrative mechanic (era switching) — not mechanical per se, but shapes `RoomGraph` structure (same world, multiple eras)

**Coverage by v0 catalog:** ~1/12

**v1 candidates from this game:**
- `BattleSystem` (entire turn-based combat scaffold) — biggest single mechanic needed for JRPG coverage
- `ATBGauge` — hybrid real-time-turn-based timing
- `Party` — multi-character player controllable
- `Stats` + `XPLeveling` — RPG stat system
- `Equipment` — slotted gear with stat mods
- `AbilitySlot` / `ComboTech`
- `EndingBranches` — narrative flow with multiple terminal states

**Signature move:** combo techs. Cross-character abilities that require 2+ specific party members. Emergent from pairing choices. Echoes the Pac-Man lesson: heterogeneous agents in the same arena produce combinatorial design space from a small primitive count.
