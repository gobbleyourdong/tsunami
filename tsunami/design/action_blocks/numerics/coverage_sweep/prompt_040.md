# Prompt 040 — 3D corridor platformer (Crash Bandicoot-style)

**Pitch:** 3D platformer down a narrow corridor (into the screen or along a path); jump/spin attack enemies; collect fruit; break crates; avoid obstacles; reach end of level.

**Verdict:** **expressible with caveats (close to Mario + 3D camera)**

**Proposed design (sketch):**
- archetypes: `player_crash` (3D platformer controller), `enemy_*`, `crate` (breakable), `fruit` (pickup), `level_end_flag`
- mechanics: `PlatformerController` (v1, 3D variant), `PickupLoop` ✓ (fruit), `LoseOnZero` (lives), `WinOnCount` (flag reached), `DestructibleTerrain` (v1, crates), `LevelSequence` (v1), `CameraRailPath` (v1, light-gun bundle — camera follows predetermined path), `DirectionalContact` (v1, spin-attack = stomp from side)

**Missing from v0:**
- **3D platformer controller** — same as 2D PlatformerController but with forward/back movement in addition to left/right. Subtype of PlatformerController with `axes: 2d | 3d`.
- **Rail camera** — camera doesn't follow the player freely; it follows a predetermined path (behind, overhead, side-view per level segment). `CameraRailPath` from prompt_027 light-gun.
- **Crate variants** (bouncy, TNT, arrow, checkpoint, iron) — each a different destructible-on-contact archetype.

**Forced workarounds:**
- PlatformerController with 3rd axis — works if v1 designs 2d/3d as a mode flag rather than separate controllers.
- Rail camera via existing CameraFollow (v1) + scripted waypoint targets. Works.

**v1 candidates raised:**
- `PlatformerController` 2d/3d flag — sub-parameter, not new primitive
- `CameraRailPath` (already noted)
- `CrateVariantLibrary` — content-multiplier catalog of destructible-archetype archetypes with common patterns (bouncy, TNT, checkpoint)

**Stall note:** Crash Bandicoot is Mario in a corridor. Same genre
cluster as 2D platformer (Mario, Metroid, Braid). No new structural
gaps; just the 3D axis + rail camera. Confirms PlatformerController
needs 3D variant. Low incremental cost if v1 targets 2D first and 3D
second.
