# Prompt 017 — Deckbuilder (Slay the Spire-style)

**Pitch:** draw 5 cards per turn; play cards to attack/block/apply effects; energy as per-turn resource; deck shuffles; discard pile; add cards between combats; map of branching encounters.

**Verdict:** **impossible (violates #1 real-time + #3 spatial partial)**

**Proposed design (sketch):**
- archetypes: `player_entity`, `enemy_*`, `card_*` (many instances), `relic_*`
- mechanics: `CardDeck` + `Hand` + `DiscardPile` + `DrawRule` + `EnergyPool` + `CardEffectDispatch` + `EnemyIntent` + `RouteMap` — none in v0

**Missing from v0:**
- **Card as first-class entity** — every card is a typed instance with effects/cost/rarity. `card_*` as archetypes works but cards are *data*, not scene entities. v0 archetype = scene mesh + controller + AI; a card has none.
- **Deck/hand/discard lifecycle** — cards move between piles with shuffle. Sequence-of-states mechanic. Not a pool of pickups.
- **Turn phases** (enemy shows intent → player plays cards → enemy attacks) — `PhaseScheduler` from prompt_016.
- **Card effect DSL** — "Deal 6 damage", "Gain 5 block", "Apply 2 Vulnerable". Each card is a small program. `ActionRef` union in v0 is 5 kinds — too narrow for hundreds of card effects.
- **Resource: energy** — per-turn refilled `Resource`.
- **Status effects** (Vulnerable, Weak, Poison, Strength) — stackable, decayable numeric modifiers. Not `TimedStateModifier`; richer: component-per-status with count + turn-decay rule.
- **Branching path map** (choose boss/elite/shop/rest at each node) — graph traversal with player choice. Similar to `RoomGraph` but player-driven selection, not location-triggered.
- **Relics (passive modifiers)** — always-on effects altering global rules. Like `GlobalModifier` toggles from SimCity note.

**Forced workarounds:** none clean. Deckbuilder is fundamentally a turn-based card-effect engine.

**v1 candidates raised:**
- Entire `CardMode` schema extension (analogous to grid-mode for grids)
- `CardDeck` / `Hand` / `DiscardPile` mechanic triad
- Card-effect DSL (expansion of `ActionRef` with ~20–30 kinds)
- `StatusStack` component (count-based decayable status)
- `RouteMap` mechanic (branching node graph with player-choice edges)
- `GlobalModifier` toggle set (noted in SimCity)

**Stall note:** deckbuilders are hot in 2020s indie. But the schema distance is big. Consider whether a narrow `cards: true` mode is valuable, or whether deckbuilder authorship belongs in its own tool. Likely v2+.
