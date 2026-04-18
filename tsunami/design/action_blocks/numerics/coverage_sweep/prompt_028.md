# Prompt 028 — Western CRPG (Baldur's Gate / Planescape: Torment-style)

**Pitch:** D&D ruleset; party of 6 with individual stats; real-time-with-pause combat; dialogue trees with stat/alignment checks; extensive inventory; area maps stitched into world map; reputation across factions.

**Verdict:** **impossible (violates note_005 #1 real-time-with-pause is mid-hybrid, #2 party of six, deep RPG stack)**

**Proposed design (sketch):** would need the full RPG stack (BattleSystem / ATBGauge / Party / Stats / XP / Equipment / StatusStack — noted in FF6/Chrono), plus:
- **Real-time-with-pause** — time flows until spacebar pauses; pause-and-queue-orders for each party member. Halfway between turn-based and realtime. Third mode beyond the two we've considered.
- **Dialogue skill checks** — dialogue options gated by Strength/Intelligence/Charisma thresholds. `DialogTree` extension: `choice_if_stat: {str: 15}`.
- **Alignment system (Lawful/Chaotic, Good/Evil)** — per-action alignment shifts affecting available choices.
- **Reputation with factions** — multi-dimensional relationship beyond per-NPC RelationshipGraph (Sims).
- **Spell system** (memorize/prepare/cast) — Resource + StatusStack + SlotSystem variant.
- **Multi-party-member spellcasting with interrupts** — timing-aware combat.

**Missing from v0:**
- Real-time-with-pause as a distinct TimeMode (not TurnManager, not realtime).
- Stat-gated dialogue choices — extension on `DialogTree` not noted before.
- Alignment / Reputation — multi-axis reputation graph beyond Sims RelationshipGraph.
- Spell preparation / slot-based casting.
- Formation movement (party stays in formation when moving).
- Inventory weight / encumbrance.
- Buffs/debuffs auras from gear/spells — StatusStack extension.

**Forced workarounds:** none at v0 scale; this is deep-RPG territory.

**v1 candidates raised:**
- `TimeMode: 'realtime-with-pause'` — new schema mode alongside real-time and turn-based
- `DialogChoice.stat_gate` — check component value against threshold
- `ReputationGraph` (multi-axis, multi-entity)
- `SpellSlot` system
- `PartyFormation` movement
- `EncumbranceSystem` — inventory-capacity via cumulative item weight

**Stall note:** western CRPG is the deepest RPG variant beyond the JRPG stack (Chrono/FF6). If JRPG stack is v2, western CRPG stack is v2.5 — many additional primitives. Flag as out-of-v1 but worth tracking because 2020s CRPG revival (BG3, Pathfinder, Disco Elysium) is commercially large.
