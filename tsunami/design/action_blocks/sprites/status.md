# Sprites — status

> Shared state between architecture + recipes threads. Read before write.

**Last updated:** architecture thread, fire 5 — **HOLD**.

## Threads

- **Architecture thread** (main): **HOLD declared at attempt_005.**
  Fire 5 is audit-only — no new content signals to incorporate.
  Counter: 1 of 2 no-signal fires. Per Sigma v8 Data Ceiling, pulled
  the hold forward rather than burn fire 6 on the same state.
  Deliverables complete: attempts 001–005 + IMPLEMENTATION.md.
  **Architecture is implementer-ready.** Operator flag with 3
  options in attempt_005 (start implementer / kill crons /
  keep-idle-not-recommended).
- **Recipes thread**: no advancement in 3 architecture fires. Fire-1
  deliverables (5 recipes) stand as canonical category config. Fire-2
  targets (priors 15, fixtures 3) pending.
- **attempt_003** (prev): audit of attempt_002 + 4 gap fixes (atlas
  JSON, min_acceptable_score, seed semantics, manifest versioning).
- **Recipes thread**: fire 2 still pending. No priors, no fixtures
  landed. note_001 (their fire 1) remains the last content signal.
- **attempt_002** (previous): absorbed 10 new ops + 5 scorers + 4
  config additions + fan-out chain fix.
- **Recipes thread** (helper): fire 1 complete. 5 recipes landed with
  the 14 ops + 5 scorers now canonical in attempt_002. Queued for
  fire 2: priors (15 target) + fixtures (3 target).

## Contracts held

- No path collisions. Architecture writes `attempts/`; recipes writes
  `recipes/` + `priors/`. Both write `observations/` + status.
- Read-before-write on status. ✓
- `CategoryConfig` stubs in attempt_001 §1 correspond to my recipes —
  same 5 new categories. ✓

## Recipes-thread progress

### Recipes — 5 / 5 ✓ (all required new categories)

| # | Category | Target size | Backend | New ops needed | Special |
|---|---|---|---|---|---|
| tileset | grid of tiles | 16×16 per-tile | z_image | grid_cut, seamless_check, pack_spritesheet | (+autotile v2, unify_palette v1.2) |
| background | parallax layer | 512×256 | z_image | horizontal_tileable_fix | (+parallax_depth_tag v2) |
| ui_element | button/panel/icon | 64×32 | z_image | flat_color_quantize | (+nine_slice_detect v1.2 stretch) |
| effect | explosion/magic/impact | 96×96 | z_image | radial_alpha_cleanup, preserve_fragmentation, additive_blend_tag | |
| portrait | dialog head close-up | 128×128 | **ernie** (fallback z_image) | eye_center, head_only_crop | |

Each recipe has all 8 sections per BRIEF_CONTENT.md: style prefix,
negative prompt, default settings, post-process chain, scorer,
example prompts (5-7 each), metadata schema, common failures +
mitigations, handoff notes.

### Priors — 0 / 15 (fire 2+ work)

Target games per BRIEF_CONTENT.md:
- NES: SMB, Zelda, Mega Man, Castlevania, Metroid
- SNES: Chrono Trigger, Link to the Past, Super Metroid, FF6
- Game Boy: Link's Awakening, Pokémon R/B, Tetris
- Arcade: Pac-Man, SF2, Metal Slug
- Modern indie: Shovel Knight, Celeste, Cave Story

### Fixtures — 0 / 3 (fire 2+ work)

Target: arcade_shooter.json, rpg_dungeon.json, platformer.json.

### palette_MAP — not started (fire 3+ / optional)

## Observations

- **recipes → architecture** (`note_001.md` this fire): 14 new post-
  process ops, 5 new scorers, 5 per-category metadata schemas, per-
  category backend preferences (portrait prefers ernie), + 5 non-
  blocking follow-ups for architecture attempt_002.

## Signal saturation check

Recipes fire 1 produced 5 category specs + 14 op proposals + 5
scorer specs. All novel; none restate. Not at Data Ceiling.
Architecture is at attempt_001 (1/3 implicit target).

## Stop-signal check

Per `BRIEF.md` §Stop-signal:
- 5 recipes ✓
- ≥ 12 priors — 0/12
- ≥ 3 fixtures — 0/3
- architecture attempt_003+ — at attempt_001
- 2 consecutive no-signal fires — fire 1 had signal

Not at stop. Continue.

## Fire 2 plan (recipes thread)

- +5 priors (NES era: SMB, Zelda, Mega Man, Castlevania, Metroid)
- 3 fixtures (arcade_shooter, rpg_dungeon, platformer) matching
  attempt_001 §4 assets.manifest.json shape
- Update status with progress

## Architecture → recipes (note_002, this fire)

Confirmations + fixture request. All of recipes' fire-1 note_001
asks are landed. Requesting fire-2 fixtures to stress-test
attempt_002's fan-out runner + attempt_003's atlas JSON.

## Non-blocking asks to architecture thread — ALL RESOLVED attempt_002

From `observations/note_001.md`:
1. ✅ 14 ops in ops table (10 v1.1, 4 v1.2)
2. ✅ 5 scorers in scorer table (with weight vectors)
3. ✅ `backend_fallback: BackendName | None` on CategoryConfig
4. ✅ `metadata_schema: dict[str, MetadataFieldSpec]` — typed, supports
   enum/list/object/nested
5. ✅ v1.1 vs v1.2 decision: stretch ops deferred to v1.2 (concur with
   recipes recommendation)

Plus 1 self-found gap addressed:
6. ✅ Post-process chain fan-out (`grid_cut` → per-tile → `pack_spritesheet`)
   via OpSpec.is_splitter / is_collector flags
