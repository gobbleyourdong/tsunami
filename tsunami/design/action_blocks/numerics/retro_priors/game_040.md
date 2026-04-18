# Game 040 — Crash Bandicoot (1996, PS1)

**Mechanics present:**
- 3D platformer in corridor (into-the-screen) — PlatformerController (v1, 3D variant)
- Spin attack + jump — ComboAttacks ✓ (simple moveset)
- Destructible crates (wooden/metal/bouncy/TNT/?/checkpoint/iron) — DestructibleTerrain (v1, Lemmings)
- Collectible fruit (100 → extra life) — PickupLoop ✓ + PostRunUnlock for extra-life-at-count
- Mask gives temporary protection (wear crystal head) — TimedStateModifier (v1)
- Aku Aku mask collects (3-level protection) — stackable TimedStateModifier
- Bonus rounds triggered by all-crate-break — EmbeddedMinigame (v1, note_006)
- Boss fights (N different patterns) — BossPhases ✓
- Level completion → % counter (full % for all-crate-break) — meta-progress HUD
- Warp rooms / level hub — RoomGraph (v1) selection hub
- Save via gems (complete level without dying) — conditional save gate
- Death counter / stage ranking — scoring and ranking
- Time trial mode later — ReplayGhost variant

**Coverage by v0 catalog:** ~4/13

**v1 candidates from this game:**
- Confirms PlatformerController 3D variant
- Confirms DestructibleTerrain (Lemmings)
- Confirms TimedStateModifier (noted many times)
- `ConditionalSave` — save gate triggered only on completion-under-constraint
- `CompletionPercent` — meta-HUD variant (collect-count / total)

**Signature move:** **crates as a physical puzzle layer.** Each level's
crate-break-% rewards exploration + platforming. The crate variants
(iron = needs special state, TNT = explodes on touch, ! = spawns more
crates) turn each crate into a mini-puzzle. Another small-catalog ×
composition example — 7 crate types × level design = varied play.

**Dedupe signal:** 3rd 3D platformer-adjacent (Mario via Metroid 2D,
Crash via this). 2D and 3D platformer are same mechanic set with
controller axis difference. Primitive set stable.
