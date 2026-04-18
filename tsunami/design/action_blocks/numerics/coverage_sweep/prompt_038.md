# Prompt 038 — Minigame collection (WarioWare-style)

**Pitch:** rapid-fire 5-second microgames flash on screen with a simple instruction ("JUMP!"); player has seconds to respond correctly; failure reduces lives; speed increases; eventually impossible.

**Verdict:** **awkward → novel composition with anthology pattern**

**Proposed design (sketch):**
- archetypes: varies per microgame (one archetype per microgame instance, dynamically swapped)
- mechanics: `MinigamePool` (from prompt_036, random select), `TimedChallenge` (per-microgame timer, 3-5 sec), `LoseOnZero` (lives), `Difficulty` ✓ (speed ramp), `HUD` (instruction text + timer)

**Missing from v0:**
- **Rapid anthology** — 200+ tiny microgames played in sequence. Extension of `MinigamePool` with auto-advance (player doesn't choose; system does).
- **Per-microgame mini-schema** — each microgame is its own tiny design script. Schema-within-schema.
- **Text-instruction HUD** — large "DUCK!" text at start of each microgame. Fast-fading HUD variant.
- **Global speed dial** — everything in every microgame runs at scaled speed as progress advances.

**Forced workarounds:**
- Each microgame as a scene transition — loses the rapid-fire feel (scene transitions take time).
- One archetype per microgame, enabled/disabled rapidly — works if archetype set is pre-loaded.

**v1 candidates raised:**
- Extends prompt_036 `MinigamePool` with `auto_advance: true` + per-game timer
- `GlobalTimeScale` — speed-up multiplier applied to all mechanics (Braid-adjacent `PhysicsModifier`)

**Stall note:** WarioWare confirms the **anthology pattern** (note_011
draft). Its specific spin is rapid-fire + accelerating. Single-player
feasible. The schema-within-schema concern is real but manageable:
each microgame fits in ~5–15 lines of design script, so a 200-game
WarioWare clone is a 2000-line design script (still reasonable).
