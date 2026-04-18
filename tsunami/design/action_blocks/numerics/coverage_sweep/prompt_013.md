# Prompt 013 — Stealth action (MGS-style)

**Pitch:** sneak past guards; detection cones and hearing; if spotted, alert state propagates to nearby guards; alarms trigger heavy reinforcements; use cover; hide bodies.

**Verdict:** **awkward**

**Proposed design (sketch):**
- archetypes: `player` (topdown or 3rd-person), `guard` (patrol AI + vision cone), `camera_turret`, `cover_object`
- mechanics: `StateMachineMechanic` (guard states: patrol / suspicious / alert / searching), `Difficulty` (guard density/alert-decay), `HUD` (radar + alert meter), `LoseOnZero` (health), `WinOnCount` (reach exit)

**Missing from v0:**
- **Detection cones / vision geometry** — guards see in a cone; if player enters cone + line-of-sight clear → detection. No `VisionCone` mechanic.
- **Alert state propagation** — detected guard alerts nearby guards within a radius, or calls on radio. Broadcast mechanic, not per-entity.
- **Hearing / noise-generation** — player running generates noise ramp; thrown objects create noise at a distance. `NoiseEvent` shape missing.
- **Cover system** — press button to snap against a cover object. Adds an archetype relationship (player-attached-to-cover). Not a controller; a transient binding.
- **Body hiding / carry** — pick up knocked-out guard, move body. Parent-child entity relationship at runtime (player holding body).
- **Global alarm timer** — when alert fires, `AlertTimer` counts down; reinforcements spawn. Similar to `TimedStateModifier` but with a spawn effect.

**Forced workarounds:**
- Vision cone as an archetype with a funnel-shaped trigger volume. Works but requires per-guard invisible archetype + cleanup.
- Alert propagation via `TimedStateModifier` (noted frequently) with a "global alert" flag. Approximates the shape.

**v1 candidates raised:**
- `VisionCone` mechanic — archetype-attached angular + distance detection
- `NoiseEvent` / `AudioStimulus` — spatial audio trigger for AI
- `AlertState` mechanic — group-wide state propagation with falloff
- `CoverBinding` — transient archetype attachment/controller override
- `CarryRelationship` — parent-child entity binding at runtime

**Stall note:** stealth lives on perception modeling. v0 contact triggers are instant-binary (touch/not-touch). Stealth needs graded perception over distance + angle + obstruction. `TimedStateModifier` helps but isn't enough. `VisionCone` is the genre-defining gap.
