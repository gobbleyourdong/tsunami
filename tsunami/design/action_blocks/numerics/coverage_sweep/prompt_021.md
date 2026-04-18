# Prompt 021 — Sports sim (Madden-style football)

**Pitch:** 11v11 team sport; play-calling from a playbook; real-time snap execution; stats per player; season mode (16 games + playoffs); franchise mode (multi-season with draft, trades, contracts).

**Verdict:** **impossible (violates #2 single-protagonist heavily + most of #1 real-time is paused during play select)**

**Proposed design (sketch):**
- archetypes: `player_athlete` × 22 (with position/stats), `ball`, `field_zone_*`
- mechanics: `PlayCalling` (menu between snaps), `AI_Teammate` (coordinated), `StatTracking` per player, `SeasonSchedule`, `RosterManagement`, `Franchise` (multi-season)

**Missing from v0:**
- Multi-unit control (switch-to-receiver mid-play) — violates #2.
- Play-calling menu with dozens of diagrammed plays — specialized UI.
- Coordinated team AI (not one enemy; 21 teammates + opponents with shared strategy).
- Per-player stats catalog (speed, strength, awareness, INT ratings) — RPG-like stats applied to sports.
- Season/franchise persistence — multi-session save at deep depth.
- Real-world team/player licenses — not a mechanic (legal).
- Replay system with rewind/scrub — cinematic ghost like Gran Turismo.
- Penalty system (flags) — rule-based fouls detected from spatial events.

**Forced workarounds:** none practical. Sports sim is a union of RTS-style multi-unit control + RPG stats + multi-season persistence. Any one violates v0; all three makes it categorically out of reach.

**v1 candidates raised:**
- Entire `SportsMode` schema extension — out of v1 scope
- `StatBlock` generalization (per-archetype rich stat sheet) — RPG-adjacent
- `SeasonSchedule` mechanic — ordered match list with per-match state

**Stall note:** team sports join RTS (012) and TBS (016) in the multi-unit cluster. They're valid v2+ targets but share the same schema-level block: v0 is built for one player archetype. A "multi-unit mode" extension could unlock all three at once but is a large project. Flag, don't build yet.
