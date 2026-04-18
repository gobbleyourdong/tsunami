# Prompt 020 — Idle/clicker (Cookie Clicker-style)

**Pitch:** click to earn currency; buy upgrades that auto-generate currency; exponential scaling; prestige resets with permanent buff; no fail state; watch numbers go up.

**Verdict:** **awkward (sandbox + no-spatial)**

**Proposed design (sketch):**
- archetypes: `clickable_object` (visual), `upgrade_*` per purchasable
- mechanics: `Resource` (currency, noted as v1), `TickIncome` (per-second auto-gen), `UpgradeShop` (purchase upgrades), `Prestige` (reset with multiplier), `HUD` (numbers everywhere)

**Missing from v0:**
- **Per-second resource accumulation** — `TickIncome(amount, interval)`. Simple but not in v0. Could be a `PickupLoop` with self-targeting and `respawn_sec` — semantically wrong.
- **Upgrade shop with exponential cost** — `Shop` (noted) with price function (base × multiplier^count). Need cost-as-function, not cost-as-number.
- **Click-as-input** — `HotspotMechanic` (noted) covers the click; reward granting on click needs binding.
- **Prestige / soft reset** — wipe most state, keep a small persistent multiplier. Generalizes NewGame+ (noted in RE, Chrono).
- **Number-heavy HUD** — v0 HUD renders component values fine; scientific notation for `1.23e47` might need a formatter hint.
- **No fail state** — `sandbox: true` flag (note_004) handles.

**Forced workarounds:**
- `TickIncome` via custom onUpdate inside a dummy mechanic — works but that's a hack every clicker game will need to rewrite.
- Upgrade cost as component with manual increment — clunky. A `CostFunction` primitive would be cleaner.

**v1 candidates raised:**
- `TickIncome` mechanic — timed auto-increment of a Resource/component field on an archetype
- `UpgradeShop` generalization — adds cost-function spec (linear, exponential, polynomial) and scales with purchase count
- `PrestigeReset` mechanic — wipes named archetypes/components, preserves named persistent modifiers
- `BigNumberFormat` HUD hint (minor)

**Stall note:** clicker is trivially simple mechanically but v0 lacks ALL the primitives. Every clicker reimplements the same 5 mechanics. Adding them is cheap and covers a surprisingly popular genre (idle games on mobile = billions in revenue). Worth v1. Compose with `sandbox: true` from note_004.
