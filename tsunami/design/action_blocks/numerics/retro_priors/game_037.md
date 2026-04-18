# Game 037 — Katamari Damacy (2004, PS2)

**Mechanics present:**
- Roll a ball (Katamari) around environments — VehicleController variant (rolling-ball physics)
- Small objects stick to the ball when touched — **`StickOnContact`** — archetype absorbs another into itself on collision
- Ball grows larger as stuff sticks — **`SizeGrowthFromContact`** — physics scale tied to absorbed-count
- Can only pick up things smaller than current ball size — **`SizeGatedPickup`** — contact trigger conditional on scale comparison
- Levels with target size (roll a 5-meter katamari in 3 minutes) — WinOnThreshold (noted DDR)
- Time limit per level — LoseOnZero on timer
- Each level has a theme (house, neighborhood, city, galaxy) — LevelSequence (v1)
- Boss levels (roll up specific objects) — WinOnCount variant
- Music + quirky presentation — content

**Coverage by v0 catalog:** ~1/9

**v1 candidates from this game:**
- **`StickOnContact`** — archetype merges into another on collision (generalization: parent-child attach at runtime, without collider alteration)
- **`SizeGrowthFromContact`** — scale component grows on stick event
- **`SizeGatedPickup`** — contact trigger conditional on physical-scale comparison

**Signature move:** **one absolutely novel physics rule** — "contact
absorbs if smaller, bounces if bigger." Katamari is the purest
single-mechanic-defines-the-game case in the corpus. Take away the
absorb-on-contact rule and the game is a ball-rolling tech demo; add
it and you have a classic. Validates the method thesis at its
extreme: one mechanic + environment content = a game.

**Method implication:** Katamari is the archetype of **"novel contact
rule → new genre."** DirectionalContact (note_003) is the structural
gap that would enable this family. Size-gated contact is a sub-case
of directional-contact-with-property-checks. Generalizes to: weight-
gated contact (switches only trigger if weighted), elemental contact
(fire vs ice immunities), faction contact (no FF).

Suggest: **contact rules are a namespace**, not individual primitives.
Once directional-contact ships, size/weight/element/faction variants
are parameter swaps, not new code.
