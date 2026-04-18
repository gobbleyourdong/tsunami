# Sprite generation pipeline — attempt 001

> Architecture thread, fire 1. Core design: Category Registry, cache
> layer, `generate_asset` API, asset manifest, action-blocks tie-in,
> backend abstraction.

## Scope

Per-asset sprite generation with cache + manifest + action-blocks
integration. Single-frame only. Pluggable backend.

Reference: `BRIEF.md` for goal + existing pipeline audit.

## 1. Category Registry

Declarative. Lives at
`ark/scaffolds/engine/tools/sprite_categories.py` (or JSON). One
entry per category.

```python
from dataclasses import dataclass, field
from typing import Callable, Literal

@dataclass
class CategoryConfig:
    name: str
    description: str

    # Prompting
    style_prefix: str                  # prepended to every prompt
    style_suffix: str = ""              # appended (rare; used by tileset for grid hints)
    negative_prompt: str

    # Generation
    gen_size: tuple[int, int] = (512, 512)
    variations: int = 4                 # best-of-N per request

    # Output
    target_size: tuple[int, int] = (64, 64)
    palette_colors: int | None = 16     # None = no quantize

    # Post-processing: list of named operations applied in order.
    # Each op is a function (PIL.Image + config → PIL.Image).
    post_process: list[str] = field(default_factory=list)

    # Scorer: named function that returns (score 0..1, reasons dict).
    scorer: str = "default_scorer"

    # Metadata schema — fields Tsunami can set in assets.manifest
    metadata_schema: dict[str, str] = field(default_factory=dict)

    # Which backend is canonical for this category
    backend: Literal["ernie", "z_image"] = "z_image"
```

Initial registry (8 categories, 3 existing + 5 new). Existing
categories absorb from `sprite_pipeline.py:STYLE_PREFIXES` with the
new typed shape. New categories are stubs the recipes thread fleshes
out.

```python
CATEGORIES: dict[str, CategoryConfig] = {
    "character": CategoryConfig(
        name="character",
        description="Single animate subject (player / enemy / NPC)",
        style_prefix=(
            "single pixel art game character sprite, one character only, "
            "clean silhouette, centered, full body head to feet, solid "
            "magenta background, bright magenta #FF00FF background, "
            "no ground, no shadow, no other characters, no props on ground, "
            "sharp pixels, 16-bit style, "
        ),
        negative_prompt=NEGATIVE_PROMPT_DEFAULT,
        target_size=(64, 64),
        post_process=[
            "pixel_extract",        # existing: bg + grid recovery
            "isolate_largest",      # existing
            "trim_transparent",     # existing
            "height_normalize_bottom_anchor",  # existing normalize_height + anchor
        ],
        scorer="character_scorer",
        metadata_schema={
            "class": "string?",      # 'knight', 'mage', 'rogue'
            "facing": "string?",     # 'left' | 'right' | 'front' | 'back'
            "palette_hint": "string?",
        },
    ),

    "item": CategoryConfig(         # renamed from 'object'
        name="item",
        description="Single inanimate object (pickup / weapon / gear)",
        style_prefix=(
            "single pixel art game item sprite, one item only, centered, "
            "clean edges, solid magenta background, bright magenta #FF00FF "
            "background, no shadow, no other objects, sharp pixels, "
            "16-bit style, "
        ),
        negative_prompt=NEGATIVE_PROMPT_DEFAULT,
        target_size=(32, 32),
        post_process=[
            "pixel_extract",
            "isolate_largest",
            "center_crop_object",   # existing: 55% center crop
            "trim_transparent",
        ],
        scorer="item_scorer",
        metadata_schema={
            "rarity": "string?",
            "equipment_slot": "string?",
        },
    ),

    "tileset": CategoryConfig(
        name="tileset",
        description="Grid of tiles, seamless-within-set",
        style_prefix="",            # recipes thread fills
        negative_prompt="",         # recipes thread fills
        target_size=(16, 16),       # per-tile
        post_process=["<recipe-driven>"],
        scorer="tileset_scorer",    # scorer thread defines
        metadata_schema={
            "biome": "string?",     # 'forest' | 'desert' | 'cave' | 'dungeon' | ...
            "tile_grid_w": "int?",  # tiles across
            "tile_grid_h": "int?",  # tiles down
            "autotile_variants": "string?",  # 'basic' | '47' | 'blob' | 'none'
        },
    ),

    "background":  CategoryConfig(..., target_size=(512, 256), ...),   # recipes fills
    "ui_element":  CategoryConfig(..., target_size=(64, 32), ...),
    "effect":      CategoryConfig(..., target_size=(96, 96), ...),
    "portrait":    CategoryConfig(..., target_size=(128, 128), ...),

    "texture": CategoryConfig(
        name="texture",
        description="Seamless repeating surface",
        style_prefix=(
            "pixel art seamless tileable texture, top-down view, "
            "game asset, repeating pattern, sharp pixels, 16-bit style, "
        ),
        negative_prompt=NEGATIVE_PROMPT_DEFAULT,
        target_size=(64, 64),
        post_process=[],            # passthrough in existing pipeline
        scorer="texture_scorer",
        metadata_schema={
            "biome": "string?",
        },
    ),
}
```

## 2. Cache layer (content-addressable)

### Location

```
~/ComfyUI/CelebV-HQ/ark/workspace/sprite_cache/
  by_hash/
    ab/
      abcd1234ef567890.png
      abcd1234ef567890.json
  by_id/
    character/
      player_knight/
        current          (symlink or small JSON → by_hash/ab/abcd...)
        history.json     (list of past hashes if id was regenerated)
```

### Hash key shape

```python
def cache_key(
    category: str,
    prompt: str,
    settings: dict,         # normalized (sorted, non-default-stripped)
    backend_version: str,   # e.g. 'ernie@2026-04-15' or 'zimage@turbo-9s'
    seed: int | None,       # None means "cache first gen, don't re-gen"
) -> str:
    payload = {
        "category": category,
        "prompt": prompt.strip().lower(),
        "settings": _normalize_settings(settings),
        "backend": backend_version,
        "seed": seed,
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]

def _normalize_settings(s: dict) -> dict:
    # Drop None values; sort keys; apply per-category default-strip
    # so that "settings = { variations: 4 }" and "settings = {}" hash
    # the same when 4 is the default.
    ...
```

### Invalidation

Cache never auto-invalidates. Explicit controls:

- Changing `backend_version` invalidates everything for that backend
  (new model = new hash).
- Changing `category.style_prefix` in the registry invalidates via
  `backend_version` bump (convention: treat registry as part of
  backend config).
- `sprite_cache clear --id player_knight` removes the `by_id` pointer
  but leaves `by_hash` content for forensic value.
- `sprite_cache clear --category character` batch version.

### Record shape

```json
// sprite_cache/by_hash/ab/abcd...xyz.json
{
  "hash": "abcd1234ef567890",
  "category": "character",
  "asset_id": "player_knight",        // the ID that requested this first
  "prompt": "pixel art knight with sword",
  "settings": { "variations": 4, "target_size": [64, 64] },
  "metadata": { "class": "knight", "facing": "side" },
  "backend": "zimage@turbo-9s",
  "seed": 428713992,
  "generated_at": "2026-04-17T15:42:18Z",
  "gen_time_ms": 2847,
  "score": 0.82,
  "score_reasons": { "coverage": 0.42, "fragments": 1, "unique_colors": 14 },
  "image_path": "by_hash/ab/abcd1234ef567890.png"
}
```

### Cache semantics

- **Hit**: return record immediately. No backend call.
- **Miss**: run pipeline. Write hash record + update by_id pointer.
- **Duplicate-id-different-prompt**: allowed. New hash, new record,
  by_id pointer updates + old hash goes into `history.json`.
- **Same-prompt-different-id**: allowed. Both ids point to same hash.
- **Force regenerate** (`--force`): skip cache lookup; write new record.

## 3. `generate_asset` function

```python
@dataclass
class AssetRecord:
    hash: str
    category: str
    asset_id: str
    prompt: str
    settings: dict
    metadata: dict
    image_path: Path
    cache_hit: bool
    score: float

def generate_asset(
    category: str,
    prompt: str,
    asset_id: str,
    settings: dict | None = None,
    metadata: dict | None = None,
    backend: Backend | None = None,
    force: bool = False,
) -> AssetRecord:
    cfg = CATEGORIES[category]
    effective_settings = _merge(cfg.default_settings(), settings or {})

    backend = backend or _get_backend(cfg.backend)
    key = cache_key(category, prompt, effective_settings,
                    backend.version, effective_settings.get("seed"))

    if not force and _cache_has(key):
        rec = _cache_load(key)
        _update_by_id(category, asset_id, key)
        rec.cache_hit = True
        return rec

    # Miss: generate
    img = _run_pipeline(cfg, prompt, effective_settings, backend)
    score, reasons = _score(cfg.scorer, img, cfg)
    rec = AssetRecord(hash=key, category=category, asset_id=asset_id,
                       prompt=prompt, settings=effective_settings,
                       metadata=metadata or {},
                       image_path=_cache_write(key, img, ...),
                       cache_hit=False, score=score)
    _update_by_id(category, asset_id, key)
    return rec
```

`_run_pipeline` does: backend call → category's post_process chain →
PIL.Image. Replaces the hardcoded chain in current `sprite_pipeline.py`.

## 4. Asset manifest format

Per-project (lives alongside game source):

```json
// scaffolds/game/assets.manifest.json
{
  "schema_version": "1",
  "backend": "zimage@turbo-9s",    // locks the cache key; bump to force regen
  "assets": [
    {
      "id": "player_knight",
      "category": "character",
      "prompt": "pixel art knight with sword, side view, blue cape",
      "metadata": { "class": "knight", "facing": "side" },
      "settings": null              // use category defaults
    },
    {
      "id": "coin",
      "category": "item",
      "prompt": "pixel art gold coin, shiny, round",
      "metadata": { "rarity": "common" }
    },
    {
      "id": "grass_field",
      "category": "tileset",
      "prompt": "pixel art grass tiles, overworld",
      "metadata": { "biome": "overworld", "tile_grid_w": 4, "tile_grid_h": 4 }
    }
  ]
}
```

## 5. Build integration

Build step at scaffold level (`scaffolds/game/scripts/build_sprites.py`
or run as part of `vite build`):

```
1. Read assets.manifest.json
2. For each asset:
     rec = generate_asset(...)
3. Copy all cached sprites into public/sprites/<asset_id>.png
4. Write public/sprites/manifest.json mapping:
     { "player_knight": { "path": "sprites/player_knight.png",
                          "category": "character",
                          "metadata": { "class": "knight", ... } }, ... }
5. Vite picks up public/sprites/ at build time; runtime reads
   manifest.json to resolve sprite_ref → path
```

Runtime sprite resolver (engine-side):

```ts
// engine/src/sprites/loader.ts
export async function loadSpriteManifest(): Promise<SpriteManifest> { ... }
export function resolveSpriteRef(ref: string): string | null { ... }
```

## 6. Action-blocks schema tie-in

Add optional field to `Archetype` (in `reference/schema.ts`). Frozen
schema v1.0.3 — but this is v1.1 extension analogous to audio:

```ts
export interface Archetype {
  // ... existing fields ...
  mesh?: MeshName                  // 3D mesh (existing)
  sprite_ref?: string              // NEW: id in assets.manifest.json
                                   // takes precedence over mesh in 2d mode
}
```

Validator check: `sprite_ref_not_in_manifest` — if an archetype's
`sprite_ref` is not present in the project's `assets.manifest.json`,
error out at compile time (before the build step) so the error is
actionable.

## 7. Backend abstraction

```python
# sprite_backend.py
from abc import ABC, abstractmethod

class Backend(ABC):
    version: str

    @abstractmethod
    def generate(self, prompt: str, width: int, height: int,
                 steps: int | None = None,
                 guidance: float | None = None,
                 seed: int | None = None) -> Image.Image: ...

class ZImageBackend(Backend):
    version = "zimage@turbo-9s"
    endpoint = "http://localhost:8090/v1/images/generate"
    default_steps = 9
    default_guidance = 0.0
    # ... uses existing sprite_pipeline.generate_image shape

class ErnieBackend(Backend):
    version = "ernie@turbo-8s"
    endpoint = "http://localhost:8091/v1/images/generate"  # or whatever
    default_steps = 8
    default_guidance = 1.0
    default_size = (1024, 1024)
    # Per memory: use_pe=false forever; pe=slop
```

Selected per `CATEGORY.backend` (default per-category) or explicit
`backend=` arg to `generate_asset`.

## 8. Implementation order

Independently PR-sized steps:

1. **Backend abstraction + registry + cache layer.** No behavior change
   for current CLI; just internal refactor of `sprite_pipeline.py` to
   route through registry and cache. Tests: same CLI invocations
   produce same outputs; second invocation hits cache.
2. **`generate_asset` function.** New entry point. Old CLI still works.
3. **Category expansion**: wire up 5 new categories once recipes
   thread has filled stubs. Tests: each category produces non-broken
   sprites against example prompts.
4. **Asset manifest + build integration.** New file at scaffold level;
   new build script. Tests: manifest with 5 assets materializes
   5 files in `public/sprites/`.
5. **Action-blocks tie-in.** `sprite_ref?: string` on `Archetype`;
   validator error; runtime resolver. Tests: design script with
   `sprite_ref` compiles + runs + renders.

## 9. Ship criteria

- Same CLI + batch work as before (backward compat).
- `generate_asset('character', '...', 'player_knight')` twice: 1st
  gens, 2nd cache-hit in <10ms.
- All 8 categories have working recipes + at least 1 test asset that
  scores > 0.6.
- Asset manifest in `scaffolds/game/` materializes N sprites in one
  build step.
- Tsunami can emit design script with `sprite_ref` and build it end-
  to-end.
- Cache hit rate ≥ 70% on repeated `vite build` runs with unchanged
  manifest.

## 10. Open questions

1. **Cache location in multi-user environments.** Right now it's
   `~/ComfyUI/CelebV-HQ/ark/workspace/sprite_cache/`. If multiple
   users share a tsunami server, they should share the cache. Revisit
   when that matters.
2. **Model version bumps.** When ERNIE updates, `backend.version`
   should change. Manual or auto? Start manual.
3. **Seed handling.** If `settings.seed` is None, cache first gen
   permanently. If seed is fixed, same seed → same hash → same output
   (makes cache key stable across clears of `by_id` only). OK.
4. **Post-processing chain ordering.** Current ops in `sprite_pipeline
   .py` are position-sensitive (pixel_extract must come first). Lock
   order via registry list. Named ops lookup in a table.

## 11. Handoff to recipes thread

- Your 5 new categories have CategoryConfig stubs in §1 with empty
  `style_prefix` / `negative_prompt` / `post_process`. Fill them.
- Your recipes get referenced as named ops — if you propose a new
  post-process function (e.g. "autotile_variant_gen"), write it in
  `recipes/<category>.md` and I'll add a matching op in the pipeline's
  ops table.
- Your example fixtures under `recipes/fixtures/<scene>.json` match
  the assets.manifest.json format from §4. Use it directly.
- Your palette_MAP.md is the prompt-scaffold content for what Tsunami
  sees when authoring — same role as audio's palette_MAP.

## 12. Self-check

- Audio extension experience carries over. Same Sigma patterns.
- Every piece independently landable (PR-sized).
- Existing pipeline preserved — this is extension, not rewrite.
- Cache shape is the single highest-leverage piece: nail the key
  normalizer + storage layout, everything else follows.
- Stop-signal: if attempt_002 doesn't add structural beyond absorbing
  recipes-thread signals, hit Data Ceiling → hold.
