# Prompt 027 — Light-gun shooter (Time Crisis / House of the Dead-style)

**Pitch:** point gun at screen; targets appear; shoot them; duck behind cover (pedal); reload when empty; on-rails camera path; boss fights at end of each stage.

**Verdict:** **awkward (close to expressible with AutoScroll + cover bindings)**

**Proposed design (sketch):**
- archetypes: `player_gun` (cursor on screen), `enemy_shooter` (pop-up, shoot, retreat), `cover_position` (pedal-bound state), `boss`
- mechanics: `AutoScroll` (on-rails camera — noted, shmup), `WaveSpawner` (enemy pop-ups), `BossPhases` ✓, `LoseOnZero`, `WinOnCount`, `PickupLoop` (ammo/health on screen), `ReloadAction` (not in v0, specific to the genre), `CoverBinding` (noted, stealth)

**Missing from v0:**
- **Cursor-aiming input** — mouse or light-gun. Not `controller:"fps"` (that's first-person body). `AimCursor` controller where pointer IS the crosshair.
- **Reload mechanic** — ammo runs out, explicit reload input with a delay + animation window. `ReloadAction` on archetype.
- **Cover bound to button-hold** — CoverBinding generalization: while button held, player is hidden (invulnerable); while released, exposed. Similar to stealth's CoverBinding but toggle-gated.
- **On-rails path** — camera moves forward along scripted spline; player has no movement, only aim + cover. `CameraRailPath`.
- **Civilian/hostage penalty** — shoot wrong target → health loss. Negative pickup shape.

**Forced workarounds:**
- Cursor via mouse input + AimCursor archetype. v0 has `KeyboardInput`; mouse isn't in the controller list. Small gap.
- Cover via `TimedStateModifier` (invuln-on-hold) — hack but works.

**v1 candidates raised:**
- `AimCursor` / `MouseController` — pointer-driven aiming (also covers adventure-games and RTS partial)
- `ReloadAction` — ammo-bound `Resource` + reload timer
- `CameraRailPath` — camera follows authored spline (subset of AutoScroll)
- `CoverHold` — button-held state flip with invuln

**Stall note:** light-gun shooter is arcade-family but v0's input assumptions don't cover mouse/pointer aim. Fixing input is cheap (`AimCursor` adds to the controller list). Reload + Cover-hold are small. Close-to-v1 genre with small primitive investment.
