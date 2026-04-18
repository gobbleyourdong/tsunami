# Prompt 007 — Harvest Moon-style farming sim

**Pitch:** plant seeds → water daily → crops grow over time → harvest → sell for money → buy better seeds/tools → marry an NPC. Day/night cycle, seasons.

**Verdict:** **awkward (genre-bending; attempt_002 flagged)**

**Proposed design (sketch):**
- archetypes: `player` (topdown), `crop` (stateful growth), `npc_villager` (dialogue), `shop`, `tool` (hoe/water/seed)
- mechanics: `DayNightClock` (exists), `PickupLoop` (harvest — but awkward), `Difficulty` (misfit), `StateMachineMechanic` (crop growth states)

**Missing from v0:**
- **`ProductionCycle`** — seed → sapling → mature → harvestable → spoiled, each transition gated on `DayNightClock` ticks. Not a pickup, not a state machine in the normal sense — it's a timed-progression-over-fields pattern.
- **`Resource` (money/energy)** — player has energy that depletes with actions, refills on sleep. Money is a currency with buy/sell interfaces. Neither is Health/Score/Lives.
- **`Shop`** — authored menu of items with prices; transactions against `Resource`.
- **`NPCRelationship`** — per-NPC affection counter, dialogue branches, gift preferences. Well beyond `DialogTree`.
- **`Season`** — multi-day cyclic state that modulates crop viability, NPC events. `DayNightClock` is single-period; needs a multi-period overlay.
- **`Inventory` slot limits + item stacking** — `Inventory` component exists but semantics are vague.
- **Save progress across sessions** — farming sims run for dozens of hours; per-session checkpoint isn't enough.

**Forced workarounds:**
- Encode crop stages as per-archetype FSM transitions keyed on a day-counter. Works but every crop archetype needs identical boilerplate.
- `Resource(money)` bolted via a `Score` component renamed. Loses semantic distinction.

**v1 candidates raised:**
- `ProductionCycle` mechanic (named as a gap in attempt_002; confirmed here)
- `Resource` generic component (named in SF2 super meter entry)
- `Shop` (named in Zelda entry)
- `Season` mechanic (period-stacked over DayNightClock)
- `NPCRelationship` mechanic
- Persistent `Save` beyond within-session checkpoint

**Stall note:** Sim games live on multi-day-scale state. v0 is session-scale. The temporal granularity of the schema is a structural mismatch. Adding `ProductionCycle` fixes the canonical farming sim case; the deeper fix is a schema-level concept of "persistent timeline."
