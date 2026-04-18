# Prompt 015 — Tony Hawk-style trick scorer

**Pitch:** skate around an open level; chain grinds/manuals/tricks without falling; score multipliers stack per combo; 2-minute timer; goals (score targets, gap-jumps, letter collection).

**Verdict:** **expressible with caveats — surprisingly close fit**

**Proposed design (sketch):**
- archetypes: `skater` (platformer-ish + rail-snap controller), `rail` (grindable edge), `ramp` (launch surface), `gap` (named jump trigger), `letter_S/K/A/T/E` (pickup)
- mechanics: `ComboAttacks` (trick input sequences — genuine good fit), `ScoreCombos` (combo multiplier — good fit), `Difficulty` (n/a for THPS, but session timer works), `PickupLoop` (letters — with `max_simultaneous: 1` + no respawn), `WinOnCount` (all 5 letters collected), `LoseOnZero` (timer expires — NOT health)

**Missing from v0:**
- **Rail-snap controller** — when near rail, press button → lock to rail trajectory. Controller mode variant.
- **Ramp / launch geometry** — on ramp exit, apply upward velocity proportional to speed. Surface-typed physics interaction.
- **Trick input combos mid-air** — only valid while airborne. State-gated `ComboAttacks`. Current v0 combos fire anytime input sequence matches.
- **Combo drop on land** — if player lands with combo active, score multiplier banks; if falls/bails, resets to 0. Event-bank vs. event-drop semantics. `ScoreCombos` is close but window-based, not event-based.
- **Session timer → goals meta** — THPS has a 2-minute timer per run with multiple goals completable in one run. `MultiGoalRun` meta-mechanic missing.
- **Gaps as named named-trigger pickups** — "Manny That Rail" jump. Named-trigger-on-arc mechanic.

**Forced workarounds:**
- Rail-snap as ai:"patrol" on a rail archetype with forced player velocity alignment. Hack.
- Trick combos expressible via ComboAttacks with `ActionRef: award_score`. ✅ clean fit.
- Combo-on-land via `LoseOnZero`-style emit-on-event (land event) that commits the combo score. Half-hack.

**v1 candidates raised:**
- `RailSnapController` / `SurfaceAwareController`
- State-gated `ComboAttacks` (add `gated_by: string` param — only fire if named flag true)
- `BankOnEvent` variant of ScoreCombos — event-commit vs. window-commit
- `MultiGoalRun` — parallel completion tracking within a session timer
- Ramp-surface physics component (generalizes to surf, snowboard, etc.)

**Stall note:** THPS is the cleanest-fit non-arcade entry so far. ComboAttacks + ScoreCombos are the right-shape mechanics but need variants (state-gated, event-commit). Validates those two v0 choices. The "combo of air tricks → multiplier → bank on land" is very close to what the catalog already describes.
