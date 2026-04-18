# Prompt 016 — Turn-based tactics (Fire Emblem-style)

**Pitch:** grid battlefield; units with movement range, attack range, class, HP, weapon triangle; player phase then enemy phase; win by routing or seizing; permadeath for fallen units.

**Verdict:** **impossible (violates v0 assumption #1 real-time)**

**Proposed design (sketch):**
- archetypes: per-class `unit_lord/cavalier/mage/archer/...`, `terrain_tile` variants, `enemy_unit_*`
- mechanics: `GridController` + `TurnManager` (note_002 v1 candidates), `TurnOrder` (player phase/enemy phase), `UnitStats`, `WeaponTriangle`, `RangedAttack`, `MovementRange`, `SeizeObjective`, `PermadeathConsequence`

**Missing from v0:**
- Phased turn order (player → enemy → weather → player) — beyond `TurnManager`; needs `PhaseScheduler`.
- Per-unit movement range as highlighted tiles — rendering layer over grid.
- Weapon triangle (rock-paper-scissors damage multiplier) — type-interaction matrix. Generalization of damage-type resistances (exists in `HealthSystem` but as scalar) to asymmetric type ↔ type table.
- Ranged attacks with tile distance — `AttackRange` as archetype property.
- Battle forecast screen (preview damage before confirming) — UI meta on attacks.
- Permadeath with narrative consequence — dead unit removed from roster across missions.
- Support conversations between paired units — relationship graph (Sims echo).
- Mission sequence (chapter 1 → 2 → …) — `LevelSequence` direct mapping.

**Forced workarounds:** none clean — turn-based tactics violates note_005 assumption #1 (real-time) and note_002 gap (grid). Probably possible once both v1 extensions land but not a single-fix genre.

**v1 candidates raised:**
- `PhaseScheduler` — ordered phase list per round with allowable-actions per phase
- `DamageTypeTable` — asymmetric type × type multiplier matrix (generalizes HealthSystem.resistances)
- `AttackRange` / `MovementRange` component — grid-tile radius + shape (diamond, square, line)
- `UnitRoster` mechanic — cross-mission persistent unit list with permadeath

**Stall note:** FE-likes need the full stack: grid-mode (note_002) + turn-mode (new) + phase-scheduler + ranged-tile-attacks + roster persistence. High-leverage for strategy genre, high implementation cost. Likely v2 unless demand signal.
