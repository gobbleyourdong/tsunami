# Shoal 🐟 — ERNIE Sprite & Asset Pipeline (the hard push)

> Role: **the entire visual-assets surface of tsunami.** Build the canonical sprite pipeline with explicit animation sets per category, tileset conventions (autotile, wang, slope tiles), and generation flows for every category of sprite a scaffold might need. Non-animated categories are still first-class deliverables — a tree without wind is a single canonical PNG with a declared convention.
> Output: `scaffolds/engine/asset_workflows/<category>/` (prompt template + animation-set declaration + postprocess + canary corpus) + `scaffolds/engine/asset_library/` (pre-rendered reference sprites) + `tsunami/tools/asset_*.py` (specialized tools where `generate_image` isn't enough).
> Runtime state: `~/.tsunami/crew/shoal/`

---

## Reads from other instances

1. `~/.tsunami/crew/coral/asset_gap.jsonl` — scaffolds with broken/missing asset pipelines (if empty, walk `workspace/.history/session_*.jsonl` and mine asset failures yourself)
2. `~/.tsunami/crew/current/attacks/assets/*.json` — adversarial sprite findings (magenta-leak, resolution-mismatch, prompt-injection via asset name)
3. `scaffolds/gamedev/*/` + `scaffolds/gamedev/cross/*/` — every scaffold Reef ships; each must have a declared asset workflow reference
4. `tsunami/serving/ernie_server.py` + `tsunami/tools/generate_image.py` + `tsunami/tools/edit_image.py` — existing ERNIE plumbing, DO NOT duplicate
5. `tsunami/tools/riptide.py` + `tsunami/tools/undertow.py` — grounding + delivery-QA gates; your sprites must pass both
6. `scaffolds/engine/assets/` if present — current conventions

---

## ERNIE constants (load-bearing)

- Model: **ERNIE-Image-Turbo bf16**, swap-capable to Base for keeper quality (50-step)
- **Endpoint:** `$SHOAL_ERNIE_URL` (env var). Defaults to `http://localhost:8092` if unset — the shared Spark instance used by interactive flows + other crew members' sporadic asset needs.
  - **Production setup:** operator runs a dedicated RunPod GPU with ERNIE-Image-Turbo on it; export `SHOAL_ERNIE_URL=http://<runpod-ip>:8092` before `crew.sh launch` so Shoal doesn't contend with local :8092.
  - **Fallback behavior:** if `$SHOAL_ERNIE_URL` is set but unreachable, Shoal retries 3× with exponential backoff, then falls back to `http://localhost:8092` and logs a `contended` warning to `~/.tsunami/crew/shoal/log.jsonl`. Better to be slow on a shared endpoint than to block entirely.
  - **Implementation hook:** `tsunami/tools/generate_image.py` reads `SHOAL_ERNIE_URL` when `caller == "shoal"`; use the existing `ernie_url` parameter; add it if missing.
- Defaults: **steps=8, CFG=1.0, 1024×1024**
- **`use_pe=false` FOREVER** — pe degrades text rendering and adds decorative artifacts (literal quotes/asterisks, glitch nudges)
- **`mode='icon'`** → magenta chromakey drop → transparent PNG. Use for sprite cutouts, characters, items, VFX.
- **`mode='photo'`** (default) → no chromakey. Use for backgrounds, tilesets, tileable terrain.
- **No alpha composites** — don't emit `_on_white.png` / `_on_magenta.png` reference outputs; alpha counts are sufficient
- **No literal quotes in prompts** — ERNIE renders them as glyphs

---

## SPRITE CATEGORY CHECKLIST (the big one)

Every category below is a separate deliverable: `scaffolds/engine/asset_workflows/<category>/` with `prompt_template.md`, `anim_set.json`, optional `postprocess.py`, `canary_prompts.jsonl`, `README.md`.

### Taxonomy by animation flag

- **ANIM** — requires full animation set
- **STATIC** — single base sprite only
- **LOOP** — single continuous loop animation (no discrete states)
- **OPTIONAL-ANIM** — base sprite is the primary deliverable, animated variant is a secondary workflow

---

### CHARACTERS (ANIM)

#### 1. Top-down character
- **Flag:** ANIM
- **Projection:** orthographic top-down (camera directly above). Shadow directly below.
- **Canvas:** 1024×1024; character occupies ~25% (effective 256×256 per frame in a 4×4 sheet); final per-frame size after slice: 128×128 or 256×256
- **Anim set** (`anim_set.json`):
  - `idle` — 4 frames — breathing loop
  - `walk` — 8 frames × 4 directions (N/E/S/W) = 32 frames
  - `run` — 8 frames × 4 directions = 32 frames
  - `attack_light` — 5 frames × 4 directions = 20 frames
  - `attack_heavy` — 7 frames × 4 directions = 28 frames
  - `hurt` — 3 frames
  - `death` — 6 frames
  - `interact` — 3 frames (picks up / talks)
- **Anchors:** Zelda: A Link to the Past, Stardew Valley, Hyper Light Drifter
- **mode:** `icon`
- **Output count:** ~130 frames total across all anims

#### 2. Isometric character
- **Flag:** ANIM
- **Projection:** 2:1 dimetric (26.57° elevation angle, 30° azimuth increments)
- **Canvas:** 1024×1024; character ~30%; sliced frames 256×256 or 512×512
- **Anim set:**
  - `idle` — 4 frames × 8 directions = 32 frames
  - `walk` — 8 frames × 8 directions = 64 frames (N/NE/E/SE/S/SW/W/NW)
  - `run` — 8 × 8 = 64 frames
  - `attack` — 6 × 8 = 48 frames
  - `hurt` — 3 frames (direction-agnostic acceptable)
  - `death` — 6 frames
  - `cast` — 5 × 8 = 40 frames (for magic-capable)
- **Anchors:** Diablo II, Fallout Tactics, Hades
- **mode:** `icon`
- **Output count:** ~250+ frames

#### 3. Side-scroller character
- **Flag:** ANIM
- **Projection:** pure profile. Facing-left is the baseline; facing-right = horizontal flip (halves work)
- **Canvas:** 1024×1024; character ~30%; sliced 256×256
- **Anim set:**
  - `idle` — 6 frames
  - `walk` — 8 frames
  - `run` — 8 frames
  - `jump_up` — 3 frames (takeoff → peak → apex)
  - `jump_peak` — 1 frame (held at apex)
  - `jump_down` — 2 frames (falling)
  - `land` — 2 frames
  - `attack_light` — 5 frames
  - `attack_heavy` — 8 frames
  - `hurt` — 3 frames
  - `death` — 6 frames
  - `wall_slide` — 2 frames (if the game has walls)
  - `dash` — 4 frames
  - `crouch` — 2 frames
  - `crouch_walk` — 6 frames
- **Anchors:** Super Mario Bros, Castlevania: SOTN, Celeste, Metal Slug, Hollow Knight
- **mode:** `icon`
- **Output count:** ~70 frames

#### 4. Fighting-game character
- **Flag:** ANIM
- **Projection:** profile, full body, hi-fidelity
- **Canvas:** 1024×1024; character ~70% of frame
- **Anim set:**
  - `stance_idle` — 6 frames (breathing)
  - `walk_forward` — 8 frames
  - `walk_back` — 8 frames
  - `dash_forward` — 4 frames
  - `dash_back` — 4 frames
  - `jump_up` — 2 frames
  - `jump_peak` — 1 frame
  - `jump_down` — 2 frames
  - `light_punch` — 4 frames
  - `medium_punch` — 5 frames
  - `heavy_punch` — 7 frames
  - `light_kick` — 4 frames
  - `medium_kick` — 5 frames
  - `heavy_kick` — 8 frames
  - `special_1` — 10 frames (signature move)
  - `special_2` — 12 frames
  - `super` — 16 frames
  - `block_high` — 2 frames
  - `block_low` — 2 frames
  - `hurt_light` — 3 frames
  - `hurt_heavy` — 5 frames
  - `hurt_aerial` — 4 frames
  - `knockdown` — 4 frames
  - `getup` — 6 frames
  - `ko` — 8 frames
  - `victory_pose` — 10 frames
- **Anchors:** Street Fighter II, Guilty Gear Strive, Skullgirls, Third Strike
- **mode:** `icon`
- **Output count:** ~140 frames (the expensive one)

#### 5. Top-down JRPG character
- **Flag:** ANIM (minimal)
- **Projection:** top-down, 3-frame "retro RPG" convention
- **Canvas:** 512×512; sliced to 48×48 or 64×64 — the classic RPG Maker scale
- **Anim set:**
  - `walk` — 3 frames × 4 directions = 12 frames (middle → left-foot → middle → right-foot pattern)
  - `idle` — reuse walk's middle frame per direction (no separate frames)
- **Anchors:** Chrono Trigger, Final Fantasy VI, every RPG Maker game
- **mode:** `icon`
- **Output count:** 12 frames

---

### ENEMIES (ANIM, usually reduced set)

#### 6. Top-down enemy (humanoid)
- **Flag:** ANIM
- Same as #1 but anim_set reduced: idle+walk+attack+hurt+death (no run, no interact). ~60 frames.

#### 7. Isometric enemy
- **Flag:** ANIM
- Same as #2, reduced: idle+walk+attack+hurt+death. ~150 frames.

#### 8. Side-scroller enemy (walker)
- **Flag:** ANIM (tiny)
- **Anim set:** walk 4 frames, hurt 2 frames, death 3 frames. Goomba-style. ~9 frames.

#### 9. Side-scroller enemy (jumper/flyer)
- **Flag:** ANIM
- `fly_loop` (4 frames), `dive` (3), `hurt` (2), `death` (4). ~13 frames.

#### 10. Boss sprite (any projection)
- **Flag:** ANIM (big)
- Canvas: 1024×1024, boss ~80-90%. Full move-set similar to a fighter but genre-adapted.
- Anim set per boss-phase: idle+telegraph+attack×3+transition+hurt+defeat. Usually 3 phases → ~80+ frames.

---

### NPCs (ANIM minimal)

#### 11. Shopkeeper / quest-giver
- **Flag:** ANIM minimal
- **Anim set:** `idle` (4 frames), `talk` (6 frames — mouth-movement), `wave` (4 frames). ~14 frames.
- Projection matches scaffold (top-down/iso/side/portrait).

#### 12. Ambient NPC (crowd)
- **Flag:** ANIM minimal
- `idle` (2-3 frames), `walk` (4 frames). Single-direction acceptable. ~7 frames.

#### 13. Dialogue portrait
- **Flag:** STATIC + emotion variants
- **Canvas:** 512×512 or 768×768
- **Variants (not anims, but set):** neutral, happy, sad, angry, surprised, determined, hurt. 7 outputs per character.
- **mode:** `icon` or `photo` with clean background
- Anchors: Fire Emblem portraits, Persona 5, Undertale

---

### VFX (ANIM / LOOP)

#### 14. Impact burst
- **Flag:** ANIM (one-shot)
- **Canvas:** 1024×1024, VFX centered
- **Anim set:** `burst` — 6-8 frames, radial bloom → peak → fade
- Anchors: SF4 super-combo bursts, Hades dash dust
- **mode:** `icon` (black background → transparent)

#### 15. Dash trail / motion streak
- **Flag:** LOOP
- **Anim set:** `trail_loop` — 4-6 frames, seamlessly loopable
- **mode:** `icon`

#### 16. Magic circle / sigil
- **Flag:** LOOP
- **Anim set:** `rotate_loop` — 8 frames, full 360° rotation
- **mode:** `icon`

#### 17. Explosion
- **Flag:** ANIM (one-shot)
- **Anim set:** `explode` — 10-12 frames with smoke-tail
- **mode:** `icon`
- Anchors: Metal Slug explosions, Vampire Survivors cluster-bursts

#### 18. Projectile (bullet/arrow/spell)
- **Flag:** ANIM + impact + trail
- **Anim set:** `fly_loop` (2-4 frames), `impact` (4 frames), optional `trail_loop` (4 frames)
- **mode:** `icon`

#### 19. Continuous effect (fire, water flow, electricity)
- **Flag:** LOOP
- **Anim set:** `loop` — 8-12 frames, seamless
- **mode:** `icon` (for standalone) or `photo` (for baked-into-scene)

---

### OBJECTS / PROPS (STATIC or OPTIONAL-ANIM)

#### 20. Tree (base)
- **Flag:** STATIC
- **Canvas:** 1024×1024, tree ~70%
- **Projection:** 3/4 for iso/side, orthographic for top-down (two variants if scaffold is iso+top-down)
- **Anim set:** NONE
- **Optional-anim workflow:** `wind_sway_loop` (8 frames, ±5° rotation blend) — separate deliverable
- **mode:** `icon`

#### 21. Rock / boulder
- **Flag:** STATIC
- **Variants:** small / medium / large (3 output size classes); mossy / bare / cracked (3 surface variants) = 9 outputs
- **mode:** `icon`

#### 22. Chest
- **Flag:** OPTIONAL-ANIM
- **Base:** STATIC closed chest
- **Animated variant:** `open` — 4 frames (closed → lid rising → lid open → gleam)
- **mode:** `icon`

#### 23. Barrel / crate
- **Flag:** OPTIONAL-ANIM (destruction)
- **Base:** STATIC
- **Animated variant:** `destroy` — 5 frames (intact → cracking → breaking → shards → gone)
- **mode:** `icon`

#### 24. Sign / signpost
- **Flag:** STATIC
- **mode:** `icon`
- Note: sign TEXT is rendered by the engine (DOM/canvas overlay), NOT by ERNIE. The prompt should request a blank-text sign.

#### 25. Door
- **Flag:** OPTIONAL-ANIM
- **Base:** STATIC closed door
- **Animated variant:** `open` — 4 frames
- **mode:** `icon`

#### 26. Fountain / water feature
- **Flag:** LOOP
- **Anim set:** `splash_loop` — 6-8 frames, seamless water motion
- **mode:** `icon` (for standalone prop) or `photo` (for baked background)

#### 27. Torch / flame source
- **Flag:** LOOP
- **Anim set:** `flame_loop` — 6 frames, seamless flicker
- **mode:** `icon`

#### 28. Crystal / glowing gem (env)
- **Flag:** LOOP
- **Anim set:** `pulse_loop` — 4 frames, brightness modulation
- **mode:** `icon`

#### 29. Gear / mechanical rotator
- **Flag:** LOOP
- **Anim set:** `rotate_loop` — 8 frames, 360° rotation
- **mode:** `icon`

---

### TILESETS / TERRAIN (STATIC, tileset convention)

#### 30. Realistic tileable terrain
- **Flag:** STATIC (tileable)
- **Canvas:** 1024×1024, sampled down to 64×64 or 128×128 tiles
- **Types:** grass, stone, sand, water, snow, lava, dirt, gravel, wood-plank, tile-floor, brick, moss
- **Prompt additive:** `" seamless tileable repeating texture, top-down orthographic view"`
- **mode:** `photo`
- **Seed discipline:** one seed per base-tile so the tileable region stays consistent

#### 31. Autotile set (47-tile Wang)
- **Flag:** STATIC (derived)
- **Base input:** 2 texture samples (e.g. grass + stone border) from #30
- **Output:** 47 tile variants covering all edge/corner combinations (Wang 2-edge 47-tile)
- **Implementation:** `postprocess.py` composites the 47 variants from the base samples + mask templates shipped in `scaffolds/engine/asset_library/autotile_masks/` (one-time ERNIE gen per mask set)
- Reference: see `## TILESET CONVENTIONS` below

#### 32. RPG Maker-style A/B/C tilesets
- **Flag:** STATIC (set)
- **A1** (animated terrain, water): 4-frame loop
- **A2** (ground + border): 48 tiles (per terrain type)
- **A3** (buildings/roofs): 16 tiles
- **A4** (walls): 48 tiles
- **A5** (ground, no border): 20 tiles
- **B/C/D/E** (objects, doodads): 256 tiles each
- See `## TILESET CONVENTIONS` for RPG Maker schema

#### 33. Platformer slope tiles
- **Flag:** STATIC (set)
- **Types:** 45° slope (up+down), 30° / 22.5° sloped (2 tiles each for gradual), 60° steep
- **Variants:** grass-top, stone-top, ice-top, etc. (coordinate with #30 base tiles)
- **mode:** `photo`

---

### BLOCKS / ARCHITECTURE (STATIC, often TILEABLE)

#### 34. Platformer block (floating)
- **Flag:** STATIC (variants)
- **Types:** grass-block, brick-block, ice-block, metal-block, wood-block, question-mark-block (has OPTIONAL-ANIM: `pulse_loop` 4 frames)
- **Canvas:** 1024×1024 per tile; sliced to 64×64 or 128×128
- **mode:** `icon`

#### 35. Wall tile (3-layer: top, face, base)
- **Flag:** STATIC (set)
- **Output:** 3 connected tiles per material; corner-aware 8-tile minisets
- **mode:** `icon`

#### 36. Fence / railing
- **Flag:** STATIC (set)
- **Output:** horizontal, vertical, corner (4 variants), end-cap (2). 7 tiles per material.
- **mode:** `icon`

#### 37. Pillar / column
- **Flag:** STATIC
- **Canvas:** 1024×512 (tall); projection matches scaffold
- **mode:** `icon`

#### 38. Arch / gate
- **Flag:** STATIC
- **Canvas:** 1024×1024
- **mode:** `icon`

---

### INTERACTIVE / ITEMS (STATIC + anim on interact)

#### 39. Weapon icon
- **Flag:** STATIC
- **Canvas:** 256×256 (small — UI-scale)
- **Types:** sword, axe, bow, staff, dagger, spear, gun, shield (8 baseline)
- **mode:** `icon`

#### 40. Consumable icon
- **Flag:** STATIC
- **Canvas:** 128×128 or 256×256
- **Types:** potion (red/blue/green), food, gold-coin, gem, key, scroll, bomb, elixir
- **mode:** `icon`

#### 41. Equipment icon (armor)
- **Flag:** STATIC
- **Canvas:** 256×256
- **Types:** helmet, chest-plate, gloves, boots, cloak, amulet, ring
- **mode:** `icon`

#### 42. Collectible pickup (world-sprite, not icon)
- **Flag:** OPTIONAL-ANIM (shimmer)
- **Base:** STATIC world sprite (overhead view of item)
- **Animated variant:** `shimmer_loop` — 6 frames, sparkle + gentle bob
- **mode:** `icon`

---

### PROJECTILES

#### 43. Bullet / arrow
- **Flag:** ANIM (fly + impact)
- Reuse #18 workflow. Per-scaffold variants: pistol-bullet, rifle-bullet, wooden-arrow, magic-arrow, energy-bolt.

#### 44. Magic projectile
- **Flag:** ANIM (fly_loop + impact + trail)
- **Anim set:** `fly_loop` (4 frames), `impact` (6 frames), `trail_loop` (4 frames)
- **mode:** `icon`

#### 45. Area-of-effect marker
- **Flag:** LOOP
- **Anim set:** `pulse_loop` — 6 frames
- **mode:** `icon`

---

### UI / HUD (STATIC, non-sprite category but in scope)

#### 46. HUD frame / panel
- **Flag:** STATIC
- **Canvas:** varies per panel shape; 9-slice frame-borders for stretchable panels
- **mode:** `icon`

#### 47. Button / widget
- **Flag:** STATIC + state variants
- **Variants:** idle, hover, active, disabled (4 states)
- **mode:** `icon`

#### 48. Health bar / resource meter
- **Flag:** STATIC (base) or LOOP (animated fill)
- **mode:** `icon`

#### 49. Minimap icon
- **Flag:** STATIC
- **Canvas:** 64×64 or 128×128
- **mode:** `icon`

#### 50. Logo / title screen
- **Flag:** STATIC
- **Canvas:** 1920×1080 or 1024×1024
- **mode:** `icon` (for overlay) or `photo` (for full title card)

---

### ENVIRONMENTAL (mixed)

#### 51. Sky / backdrop
- **Flag:** STATIC or LOOP
- **Types:** daytime, night, sunset, storm, alien, space
- **Canvas:** 2048×1024 (wide for parallax layering)
- **mode:** `photo`

#### 52. Parallax layer (mid-ground / far-ground)
- **Flag:** STATIC (tileable horizontal)
- **Canvas:** 2048×512 (wide, short)
- **Tileable horizontally** for infinite-scroll
- **mode:** `photo`

#### 53. Weather overlay (rain, snow, fog)
- **Flag:** LOOP
- **Anim set:** `particle_loop` — 8 frames, seamless, semi-transparent
- **mode:** `icon`

#### 54. Lighting / sunbeam / god-ray
- **Flag:** STATIC or LOOP
- **mode:** `icon`

#### 55. Water surface (top-down)
- **Flag:** LOOP (tileable)
- **Anim set:** `ripple_loop` — 8 frames, seamless in space AND time
- **mode:** `photo`

---

## TILESET CONVENTIONS (research primer)

### Autotile / Wang tiles

- **2-edge 16-tile minimal (blob):** 4 edges (N/E/S/W) each on/off = 2^4 = 16 variants. Covers most common edge-cases with 16 tiles.
- **2-edge 47-tile (Wang corners):** 4 edges × 4 corners = 2^8 = 256 theoretical, reduced to 47 by symmetry and corner-dependency. Standard for smooth-border tilesets. Used by RPG Maker autotile, Godot's `auto_tile_coord`, GameMaker's autotile.
- **Meta-tile / template:** each variant has a defined pixel pattern. Ship the mask templates in `scaffolds/engine/asset_library/autotile_masks/47_tile_template.png` — 1024×1024 image with 47 regions outlined.

### RPG Maker tileset schema

RPG Maker VX Ace / MZ conventions, inherited by many 2D JRPG frameworks:

- **A1 (animated terrain):** 2×3 grid of 4-frame animations — water, lava, waterfalls
- **A2 (ground with autotile borders):** 8×2 grid of 48-variant Wang sets — grass, dirt, stone
- **A3 (building exteriors):** 8×2 grid, 16-variant sets for walls + roofs
- **A4 (interior walls):** similar layout for indoor tilesets
- **A5 (no-border ground):** simple 8×4 tile grid, 20 tiles
- **B/C/D/E (doodads):** 16×16 tiles each = 256 sprites of objects, furniture, decorations

### Slope tiles (platformer)

Standard set:
- 45° slope up + down (2 tiles)
- 30° slope: 2 tiles per slope (gradual)
- 22.5° slope: 4 tiles per slope (very gradual) 
- 60° steep slope: 1 tile (stairs)
- Corner fillers (5-8 tiles)

Shipped as a family per base-material (`grass_slopes_47plus_slopes/`, `stone_slopes_47plus_slopes/`).

### Bitmask autotiles (Godot / GameMaker)

Modern convention — each tile has a neighbor-bitmask specifying which of its 8 neighbors are "same terrain." The renderer picks the variant matching the bitmask. 47 variants covers the space (same as Wang).

### 9-slice / 3×3 panels

For stretchable UI frames: 1 panel → 9 regions (4 corners, 4 edges, 1 center). Corners and edges don't stretch; edges stretch in one axis; center stretches both. One source image, infinite sizes.

---

## PHASE CHECKLIST (per workflow — 55+ workflows total)

Per category above, execute:

- [ ] **Research anchor review** — read one reference game's wiki / open-source assets for the category; note frame counts, canvas sizes
- [ ] **Prompt template** — parameterized ERNIE prompt. Placeholders: `<character_name>`, `<style_variant>`, `<projection>`, `<anim_name>`, `<frame_count>`
- [ ] **Anim set declaration** — `anim_set.json` with frame-count + direction-count + loop/oneshot flag per animation
- [ ] **Postprocess** — slicer (grid → individual frames), palette normalization, alpha cleanup
- [ ] **Canary corpus** — 3 prompts through the template; render; manually verify; checkin 3 canary PNGs (keep size < 50 KB each, downscale if needed)
- [ ] **Library seed** — at least one pre-rendered reference in `scaffolds/engine/asset_library/<category>/` that future scaffolds can reuse
- [ ] **Scaffold integration** — patch 2–3 affected scaffolds to point at the workflow; update their READMEs
- [ ] **README** — explain when to use this workflow vs. siblings; embed one canary PNG
- [ ] **Commit** — atomic per category: `asset_workflow: add <N>_<category> — <one-line pitch>`
- [ ] **Push & update Coral** — append to `~/.tsunami/crew/shoal/completed.jsonl`

---

## Known failure modes (don't repeat)

- Do NOT pass `use_pe=true`
- Do NOT put literal quotes in ERNIE prompts — they render as glyphs
- Do NOT duplicate `generate_image` logic — extend, don't rewrite
- Do NOT produce a workflow without an anim_set.json — downstream consumers can't plan animation loading without it
- Do NOT produce canary PNGs bigger than 100 KB each; use pngcrush or downscale
- Do NOT bundle multiple workflows in one commit — one per commit, for clean attack coverage by Current
- Do NOT skip the library seed — un-seeded workflows regen every time; seeding halves ERNIE load
- Do NOT generate alpha composites (`_on_white.png`) — mode='icon' alpha is sufficient
- Do NOT commit binary assets bigger than 100 KB — production assets live in workspace, only canary thumbnails in the repo

---

## Bonus long churn infinite 🔁

After 55+ workflows ship:

1. **Style-mode matrix** — for each workflow × each of (pixel-art, painterly, cel-shaded, watercolor, manga, vaporwave, retrowave, dark-fantasy) = 55 × 8 = 440 sub-templates
2. **Palette conditioning** — optional `--palette <name>` quantizer in postprocess: pico8, gameboy, c64, nes, msx, commodore-16color, custom
3. **Character-sheet auto-slicer** — `slice_to_frames(sheet_png, grid_w, grid_h) -> list[Path]` with frame-anchor normalization (auto-detect pivot point)
4. **Animation preview GIF** — every sliced anim_set emits a preview GIF for undertow visual QA
5. **47-tile autotile auto-tiler** — take a single "grass + stone" sample, emit all 47 variants via carefully-placed masks + edit_image
6. **VFX library** — pre-render 20+ canonical VFX spritesheets (burst, ring, shockwave, dash-trail, hit-flash, slash, explosion, puff, sparkle, lightning, freeze, burn, heal, poison, bleed, confusion, charm, sleep, stun, death-spiral) — scaffolds pull from this instead of generating per-project. Cuts ERNIE calls ~70% on typical gamedev.
7. **Character-archetype library** — pre-render 10 baseline archetypes per projection × 4 projections = 40 reference characters (warrior, mage, archer, rogue, priest, knight, barbarian, ninja, samurai, monk). Scaffolds customize via edit_image, not from-scratch generation.
8. **Prop library** — 50+ static props: trees (oak/pine/palm/dead/cherry-blossom), rocks (5 sizes × 3 types), chests (wood/gold/magical), barrels/crates/vases, signs, doors (5 materials), furniture (throne/table/chair/bed/bookshelf)
9. **Tileset library** — 20 baseline tileable terrains (grass/stone/sand/snow/water/lava/dirt/brick/wood/tile/grass-path/stone-path/marble/volcanic-rock/ice/cloud/crystal/moss/tentacle-flesh/tech)
10. **Adversarial-prompt safety** — coordinate with Current; prompt-inject ERNIE via attack corpus; ensure mode=icon + postprocess rejects bad content
11. **Portrait archetype library** — 20 base dialogue portraits × 7 emotions = 140 reference portraits that scaffolds can adapt
12. **Seasonal variants** — for the prop/tileset libraries, generate spring/summer/autumn/winter variants = 4× the library
13. **Weather variants** — same libraries with rain/snow/fog overlays baked in
14. **Day/night variants** — daytime + dusk + night + dawn lighting conditions per environmental asset

Log per round to `~/.tsunami/crew/shoal/log.jsonl`:
```json
{"ts": "...", "round": N, "workflow": "...", "action": "template|postprocess|canary|library_seed|scaffold_integration|style_variant", "anim_frames": K, "sha": "..."}
```

The visual-asset surface of tsunami is combinatorially unbounded. Pace yourself — breadth first, depth second, library-reuse third.
