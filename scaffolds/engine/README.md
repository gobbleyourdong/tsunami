# WebGPU engine — AI-authored games

> A WebGPU-native real-time engine + a declarative design stack an LLM
> can drive end-to-end. Author a game by emitting typed JSON; the
> compiler lowers it to engine calls. Tsunami emits the JSON.

**Status: v1.0 ships on the 29-mechanic action-blocks catalog, v1.1
content extensions (audio + sprites) merged.** 4/4 ship gates green.

---

## TL;DR

| | |
|---|---|
| Engine TS | 16,642 LOC across 16 subsystems |
| Python tooling | 3,585 LOC (sprite pipeline + compiler wrapper) |
| Tests | 326 passing in 22 files (4,296 LOC) |
| Mechanics | 35 implemented (+5 v2 placeholders = 40 catalog entries) |
| ActionRefs | 20 kinds (game + audio) |
| Validator errors | 23 kinds (design + audio + sprites) |
| Sprite pipeline | 8 categories / 17 post-process ops / 9 scorers / 26 metrics |
| Image backend | ERNIE-Image-Turbo @ `:8092` (sole shipping backend) |
| Ship gates | #12 🟢 #13 🟢 #14 🟢 (20/20) #15 🟢 (33/33) |

---

## What's here

### 1. Engine core (`src/`)

| Subsystem | Files | LOC | What |
|---|---|---|---|
| `math` | 2 | 389 | Vec / matrix / quat / geometry primitives |
| `renderer` | 9 | 1,231 | WebGPU pipeline, camera, materials, shader graph |
| `physics` | 9 | 1,484 | 2D/3D bodies, collisions, triggers, joints |
| `animation` | 7 | 904 | Skeletal + transform + procedural |
| `audio` | 4 | 1,143 | AudioEngine + Sfxr + ChipSynth (v1.1) |
| `input` | 7 | 557 | Keyboard + action map + gesture recognisers |
| `scene` | 7 | 812 | SceneManager, GameScene, spawn/despawn, properties |
| `flow` | 7 | 771 | GameFlow (scene/linear/level_sequence/room_graph/round_match) |
| `ai` | 4 | 401 | Behaviour-tree-lite + utility AI + vision cone |
| `vfx` | 5 | 1,094 | Particle systems + trails + impact FX |
| `systems` | 5 | 417 | ECS-style system runner, frame loop glue |
| `game` | 3 | 421 | Top-level Game class + SceneBuilder |
| `cli` | 2 | 101 | Headless build/compile entrypoints |
| `sprites` | 1 | 80 | Runtime sprite-manifest loader (fetches the Python build's output) |
| **`design`** | 43 | 6,818 | **The AI authoring layer — see §2** |

All subsystems have vitest coverage; the full suite runs in <1s headless.

### 2. Design stack — the AI surface (`src/design/`)

The "AI authors games" claim rests entirely on this module:

- **`schema.ts` (751 LOC)** — the authored type: `DesignScript` (meta + config + archetypes + mechanics + flow). Discriminated-union types for `MechanicParams`, `ActionRef`, `FlowNode`, `TriggerSpec`, `SingletonSpec`. Branded id types (`ArchetypeId`, `MechanicId`, `ConditionKey`, `SceneName`) prevent string-mixups at the type level.
- **`catalog.ts` (737 LOC)** — metadata for each of the 40 `MechanicType` entries: description, example params, emitted fields, required tags, playfield/mode requirements, sandbox compatibility, tier (`v1_core | v1_ext | v2`).
- **`validate.ts` (669 LOC)** — single-pass structural validator over `DesignScript`. 23 distinct error kinds, each carrying `{path, message, hint?, suggestions?}`. Pre-compile gate — no partial validation.
- **`compiler.ts` (307 LOC)** — `ValidatedDesign → GameDefinition`. Lowers flow trees to a linear step list + `SceneDefinition[]`, wires mechanic instances into scene property bags, threads archetype specs.
- **`cli.ts` (72 LOC)** — stdin JSON → stdout `GameDefinition`, stderr = structured JSON validator errors. Invoked by `tsunami/tools/emit_design.py` as a subprocess.
- **`mechanics/*.ts` (35 files + registry)** — the runtime half. Each mechanic is a factory (`MechanicFactory`) registered into `mechanicRegistry`; scene activation walks the list and constructs a `MechanicRuntime` bound to the live `Game`.

#### The 35 shipped mechanics

**Content multipliers (Phase 1):**
RhythmTrack · DialogTree · ProceduralRoomChain · BulletPattern · PuzzleObject

**Composability (Phase 2):**
EmbeddedMinigame · WorldFlags (helper)

**Action core (Phase 3 — 13):**
Difficulty · WaveSpawner · HUD · LoseOnZero · WinOnCount · PickupLoop · ScoreCombos · CheckpointProgression · LockAndKey · CameraFollow · TimedStateModifier · LevelSequence · RoomGraph

**Extensions (Phase 4 — 14):**
StateMachineMechanic · ComboAttacks · BossPhases · ItemUse · GatedTrigger · AttackFrames · Shop · UtilityAI · HotspotMechanic · InventoryCombine · StatusStack · EndingBranches · VisionCone · RouteMap

**Audio v1.1 (Phase 5 — 2):**
ChipMusic · SfxLibrary

**v2 placeholders (catalog-declared, compiler-declined):**
5 types flagged for future extensions; validator emits `out_of_scope` on use.

### 3. Python tooling (`tools/`)

| File | What |
|---|---|
| `sprite_backends.py` | `Backend` ABC + `ErnieBackend` against `:8092` |
| `sprite_cache.py` | Content-addressable cache (`by_hash/<ab>/…` + `by_id/<cat>/<id>/current`) |
| `sprite_ops.py` + `sprite_ops_impl.py` | 17-op registry + chain runner (splitter/collector semantics, `chain_fan_out_invalid` detection) |
| `sprite_metrics.py` | 26 metric inspectors (image → [0, 1]) |
| `sprite_scorers.py` | 9 named weighted scorers |
| `sprite_categories.py` | 8 `CategoryConfig` entries with style_prefix / negative_prompt / post_process chain / metadata_schema |
| `generate_asset.py` | Public API: category + prompt + asset_id → cached `AssetRecord` |
| `sprite_manifest.py` | Authoring manifest loader + version gate |
| `build_sprites.py` | CLI: reads `assets.manifest.json` → generates each asset → writes `public/sprites/` + runtime `manifest.json` |
| `sprite_pipeline.py` | Legacy CLI preserved, now delegates to `ErnieBackend` |
| `tilemap_gen.py` · `game_from_text.py` | Older prototypes — pre-design-stack, kept for reference |

### 4. How AI drives it end-to-end

```
  ┌──────────────────────────────────────────────────────────────┐
  │ Tsunami agent (tsunami/agent.py)                              │
  │  - project_init: detects "game" prompt, rejects 7 genres      │
  │  - loads tsunami/context/design_script.md into system prompt  │
  │  - picks nearest-match example (arena_shooter/rhythm/…)        │
  └───────────────┬──────────────────────────────────────────────┘
                  │ 1. emit JSON
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ emit_design(design, project_name, auto_fix=True)              │
  │  = subprocess → scaffolds/engine/src/design/cli.ts            │
  │    • validate (23 error kinds)                                │
  │    • compile  (ValidatedDesign → GameDefinition)              │
  │  on failure: error_fixer.fix_design_validation_errors         │
  │    → deterministic patches (17 patchers) → recompile one pass │
  └───────────────┬──────────────────────────────────────────────┘
                  │ 2. valid GameDefinition JSON
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ deliverables/<name>/                                          │
  │  ├── game_definition.json                                      │
  │  └── assets.manifest.json    (if archetypes reference sprites) │
  │      │                                                          │
  │      ▼ python tools/build_sprites.py <name>                    │
  │      │   • validate metadata schema                             │
  │      │   • generate_asset() per entry → ERNIE :8092             │
  │      │   • content-addressable cache hit/miss                   │
  │      │   • post-process chain (pixel_extract, grid_cut, …)     │
  │      │   • scorer picks best variation                          │
  │      │   • write public/sprites/<id>.png (+ .atlas.json)        │
  │      └── public/sprites/manifest.json                          │
  └───────────────┬──────────────────────────────────────────────┘
                  │ 3. bundle + run
                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ Browser (WebGPU)                                              │
  │  - loader.ts fetches sprites/manifest.json                    │
  │  - Game reads game_definition.json → SceneBuilder             │
  │  - mechanicRegistry.create(instance, game) per mechanic       │
  │  - frame loop ticks systems + mechanics                       │
  └──────────────────────────────────────────────────────────────┘
```

### 5. Ship-gate results (v1.0 scorecard)

| Gate | Criteria | Result |
|---|---|---|
| **#12** Validator 5+5 | Known-good + known-bad scripts map to correct error kinds | 🟢 10/10 (`design_validate.test.ts`) |
| **#13** 3 e2e games | arena_shooter + rhythm + narrative + audio_demo build + 60s autoplay | 🟢 13/13 (`design_e2e.test.ts`) |
| **#14** One-shot ≥50% valid (N=20) | Tsunami emits valid arena-shooter N/20 | 🟢 **20/20 raw** (71s avg) |
| **#15** Re-sweep ≥60% expressible | 29 in-scope prompts compile clean-or-caveated | 🟢 **33/33** (100%) |

**Joint monoculture diagnosis** (from #14 + #15 raw sweeps): 41/46 of all failures collapsed to one error class — `dangling_condition` on `flow.steps[].condition` keys. `error_fixer._patch_dangling_condition` catches them deterministically; the prevention paragraph in `design_script.md` drives raw validity to 100%. **Zero auto-generated v1.1 mechanic backlog** from either sweep.

---

## Gaps

Grouped by whether they block shipping games today, or are v1.2 / v2+
scheduled.

### Blocking — things that make the system feel half-built

1. **`sprite_ref` isn't yet consumed by the renderer.** The schema field lands, the validator checks it, the pipeline builds the PNG, `loader.ts` fetches the manifest — but the renderer still looks at `archetype.mesh` first in both 2D and 3D paths. Needs: 2D renderer fallback that resolves `sprite_ref` → billboard/quad with the texture from the manifest. Estimate: ~200 LOC + one test.

2. **Scaffold-level build wiring.** `build_sprites.py` is a manual CLI; there's no Vite plugin or npm script that runs it before `vite build`. Each project currently has to remember. Needs: a `scripts/prebuild.mjs` shim or a Vite plugin that invokes it when `assets.manifest.json` exists. Estimate: ~50 LOC.

3. **No bundled sprites example.** `examples/audio_demo.json` shows the audio surface but no fixture shows `sprite_ref` across all archetypes. Needs: `examples/sprites_demo.json` + an `assets.manifest.json` sibling. Estimate: ~150 LOC.

4. **Design-step `sprite_manifest` plumbing.** `validate.ts` looks for `(raw as any).sprite_manifest` to gate the `sprite_ref_not_in_manifest` check, but `DesignScript`'s type doesn't declare that field. Either Tsunami emits two documents (design + manifest) and the build cross-checks them, or `DesignScript` gains an optional `sprite_manifest` field. Estimate: decision + ~30 LOC.

### v1.2 — planned content extensions

From `sprites/IMPLEMENTATION.md` §"Out of scope":

- **`autotile_variant_gen`** — 47-wang autotile synthesis from a primary tile. Author-curation OK for v1.1 tilesets.
- **`unify_palette`** — cross-tile palette coherence. Current path does per-tile quantize; visually usable.
- **`parallax_depth_tag`** — auto-detect near/mid/far from image content. Currently author-supplied.
- **`nine_slice_detect`** — auto-detect stretch regions on UI panels. Currently author-supplied `nine_slice` metadata.
- **Animation / multi-frame sprites** — biggest gap. `animation/` subsystem has the runtime plumbing (skeletal + transform), but the sprite pipeline is single-frame; no `frame_set` synthesis or pose-consistency path. Needs either a multi-frame backend or a keyframe-interpolation op on top of single-frame gen.
- **Style-transfer / IP-lock / LoRAs** — no character consistency across prompts today. `player_knight_happy` and `player_knight_sad` come back as different-looking knights. Deferred to v1.3+.

### v2+ — genre scope

Per `project_init._OOS_REDIRECT_MESSAGES`, 7 genres are explicitly out of scope and the agent redirects:

| Genre | Blocker |
|---|---|
| Interactive fiction / Zork | Parser-driven; non-spatial |
| RTS / StarCraft | Multi-unit command, no single protagonist |
| TBS / Fire Emblem | PhaseScheduler + grid + roster persistence |
| JRPG battle system | Needs BattleSystem sub-schema (overworld-only IS supported) |
| Racing sim | VehicleController + TrackSpline (arcade kart IS supported) |
| Persistent sim / SimCity | Needs save system + multi-day timeline |
| Deckbuilder | Card-draw / deck / rule-synthesis primitives |
| MMO / CRPG | Networking, persistence, content scale |

Ship gate #15's sweep confirmed these by design — 7/40 prompts classified `impossible`. Adding any of them is a v2 scaffold, not a v1.x extension.

### Known rough edges

- **`ErnieBackend.generate` has no retry / model-swap wait.** If `:8092` is mid-swap (`pipe_loaded=false`) the caller sees `BackendUnavailableNoFallback`. Z-Image fallback was retired 2026-04-17 because we don't run Z-Image on this deployment; that removes a whole class of fallback machinery but also removes the graceful-degradation path. A short retry-with-backoff on 503s would paper over most transient mid-swap windows.
- **No image-level regression tests on the sprite pipeline.** `sprite_e2e.py` only checks structural invariants (shape, cache, atlas count). Scorer outputs drift with ERNIE model updates — we'd catch regressions only via reviewer eyeballs.
- **Tsunami agent doesn't inspect score warnings.** `AssetRecord.score_warning=True` is logged by `build_sprites.py` but the agent doesn't see it or decide whether to regenerate. Would be a small `emit_design`-equivalent wrapper for sprite builds.
- **`StatusStack`, `StateMachineMechanic`, `ChipMusic` are runtime-tested but gate-#15 unexercised.** None of the 33 sweep prompts needed them. Not a gap in coverage, but a gap in *real-world validation* — they ship with unit tests only.

---

## File layout (orientation map)

```
scaffolds/engine/
├── src/
│   ├── audio/              chipsynth + sfxr + AudioEngine
│   ├── ai/                 behaviour/utility runners
│   ├── animation/          skeletal + transform + procedural
│   ├── cli/                build helpers
│   ├── design/             ←── AI authoring surface
│   │   ├── schema.ts         types + branded ids + discriminated unions
│   │   ├── catalog.ts        40 mechanic metadata entries
│   │   ├── validate.ts       23-kind error taxonomy
│   │   ├── compiler.ts       Validated → GameDefinition lowering
│   │   ├── cli.ts            subprocess entrypoint
│   │   └── mechanics/        35 runtime implementations
│   ├── flow/               GameFlow + step scheduling
│   ├── game/               top-level Game + SceneBuilder
│   ├── input/              keyboard + action map + gestures
│   ├── math/               vec/mat/quat/geometry
│   ├── physics/            bodies + contacts + triggers
│   ├── renderer/           WebGPU + camera + materials
│   ├── scene/              SceneManager + GameScene + entities
│   ├── sprites/            loader.ts (manifest fetch + resolve)
│   ├── systems/            frame loop glue
│   └── vfx/                particles + trails
├── tools/                  (Python)
│   ├── sprite_backends.py  ErnieBackend against :8092
│   ├── sprite_cache.py     content-addressable cache
│   ├── sprite_ops.py[+_impl] 17-op registry + chain runner
│   ├── sprite_metrics.py   26 metrics
│   ├── sprite_scorers.py   9 scorers
│   ├── sprite_categories.py 8 CategoryConfig entries
│   ├── generate_asset.py   public API
│   ├── sprite_manifest.py  authoring loader
│   └── build_sprites.py    CLI: manifest → public/sprites/
├── tests/                  22 test files, 326 tests
└── package.json
```

## Quick start

```bash
# Engine tests (TS)
cd scaffolds/engine
npm test

# Validate + compile a design script end-to-end
cd /path/to/repo
PYTHONPATH=$PWD python3 -c "
from tsunami.tools.emit_design import emit_design
import json
d = json.load(open('tsunami/context/examples/arena_shooter.json'))
r = emit_design(d, project_name='demo', deliverables_dir='/tmp/demo_out')
print(r['ok'], r.get('stage'), len(r.get('errors', [])))
"

# Generate a sprite + cache + score
PYTHONPATH=$PWD python3 -c "
import sys; sys.path.insert(0, 'scaffolds/engine/tools')
from generate_asset import generate_asset
r = generate_asset('character', 'pixel art knight with sword, side view',
                   'player_knight', metadata={'class': 'knight', 'facing': 'side'})
print(r.image_path, 'score:', r.score, 'cached:', r.cache_hit)
"

# Build all sprites for a project
python3 scaffolds/engine/tools/build_sprites.py /path/to/game_project
```

## Constraints

- **WebGPU only.** WebGL2 fallback is not planned. Target Chrome/Edge/Safari-TP.
- **Authoring-side only.** Sprite generation hits ERNIE at `:8092` — not embeddable in shipped games. Output is a frozen PNG + atlas.
- **Real-time single-protagonist spatial games.** Three assumptions, enforced by `project_init._detect_out_of_scope_genre` + `validate.playfield_mismatch` + `validate.out_of_scope`.
- **No animation pipeline for sprites in v1.** Single-frame output. Engine `animation/` handles skeletal + transform on synthesized sprites as static textures.

## History

- **2026-04-17**: Z-Image retired, ERNIE-Image-Turbo (8 steps, CFG 1.0, `use_pe=false`) is the sole shipping backend.
- **2026-04-17**: Sprite v1.1 extension landed (10 phases, 14 new files, 12 ship-gate tests).
- **2026-04-17**: Audio v1.1 extension landed (ChipSynth + Sfxr + SfxLibrary + ChipMusic).
- **2026-04-17**: v1.0 ships — ship gates #12–#15 all green.
