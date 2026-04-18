# Prompt 035 — Platform fighter (Smash Bros-style)

**Pitch:** 4 fighters on 2D stage; damage percentage increases with hits; higher % = more knockback; ring out to lose stock; multiple playable characters with distinct movesets; items drop randomly.

**Verdict:** **expressible but incomplete (closer than SF2 — arcade variant)**

**Proposed design (sketch):**
- archetypes: `fighter_*` per character (distinct stats + moves), `stage_platform`, `item_*` (random weapons/power-ups)
- mechanics: `ComboAttacks` ✓ (move list), `Lives`/`Stocks` component, `LoseOnZero` (stocks), `WinOnCount` (last fighter standing), `RandomEvent` (item spawn — noted), `PickupLoop` (items), `PlatformerController` (v1 — movement + jump + recovery), `DamagePercent` (NOT Health — knockback scales with damage taken)

**Missing from v0:**
- **Damage percent (not health)** — Smash's % rises; knockback = f(% + move). Inverted health model. `DamagePercent` component variant of Health.
- **Knockback physics** — hit applies force × (damage × move power). Directional velocity transfer. Physics with a formula, not existing rigidbody.
- **Stocks (lives that persist across a match)** — Lives component; respawn-on-ringout with invuln; match-ends-on-zero-stocks.
- **Ring-out detection** — leaving stage bounds → lose stock. `BoundaryExit` trigger.
- **Character-specific movesets** — ComboAttacks per-character, plus "special" moves with recovery frames. AttackFrames (noted SF2) applies.
- **Items drop randomly in play** — RandomEvent + PickupLoop combined.
- **Final Smash / super move** — `Resource` (smash meter) + special mode activation (TimedStateModifier).
- **Stages with hazards** — environmental archetypes that harm fighters.

**Forced workarounds:**
- `DamagePercent` via custom component (inversion of Health's onDamage hook).
- Knockback via ad-hoc physics in onDamage callback.

**v1 candidates raised:**
- `DamagePercent` — inverted health model (rising instead of falling)
- `KnockbackImpulse` — damage-scaled force transfer on hit (shared with physics-combat)
- `BoundaryExit` trigger — leaving defined region → emit condition
- `StockLives` — persist-across-match lives counter
- Confirms AttackFrames + character movesets from SF2

**Stall note:** platform fighter is easier than SF2 — damage model is simpler (no block-stun, no frame advantage dominating design), but still needs `DamagePercent` + `KnockbackImpulse` as new primitives. Arcade-variant-of-fighter. If v1 targets fighter genre, starting with Smash-style is cheaper than starting with SF2-style.
