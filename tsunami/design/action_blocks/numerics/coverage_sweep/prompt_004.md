# Prompt 004 — 2D platformer (Mario 1-1-style)

**Pitch:** side-scrolling jump-and-stomp; enemies die if jumped on from above, damage you from the side; reach the flagpole.

**Verdict:** **awkward**

**Proposed design (sketch):**
- archetypes: `mario` (player, platformer controller), `goomba` (enemy, patrol AI), `coin` (pickup), `block_brick` (destructible), `block_question` (item source), `flagpole` (goal trigger)
- mechanics: `PickupLoop` (coins), `WinOnCount` (flagpole touched), `LoseOnZero` (lives), `CheckpointProgression` (level segment saves), `Difficulty` (enemy speed by world)

**Missing from v0:**
- `controller:"platformer"` — not in v0 controller list. Needs: horizontal move, variable-height jump (button hold), coyote time, ground-slam-from-above detection.
- **Directional collision** — "stomp from above kills goomba, side hit damages player." v0's `trigger:"damage"` is symmetric. Need contact-side discrimination.
- Scrolling camera — v0's camera is scene-fixed. Needs `camera_follow: <archetype_id>` parameter.
- Destructible blocks from below (head-bump) — `trigger:"break"` with a direction filter. Directional triggers again.
- `block_question` items spawn power-ups on head-bump — two mechanics chained: directional trigger → spawn archetype.

**Forced workarounds:**
- Bolt side-detection logic into a custom component (not mechanic-level). Breaks the "JSON is the game" goal.

**v1 candidates raised:**
- `PlatformerController` — distinct from fps/topdown/orbit; jump mechanics
- `DirectionalCollision` / `ContactSide` in trigger definitions — `trigger:"damage"` becomes `trigger:{type:"damage", from_dir:"side"}` and `trigger:{type:"stomp", from_dir:"above"}`
- `CameraFollow` mechanic — named target archetype + offset + deadzone
- `ChainedTrigger` / event-on-event — A trigger fires → B trigger spawns

**Stall note:** platformer feel lives in directional collision + jump tuning. The first is a schema gap; the second is why `PlatformerController` needs its own parameter profile (hop_height, jump_buffer, coyote_ms).
