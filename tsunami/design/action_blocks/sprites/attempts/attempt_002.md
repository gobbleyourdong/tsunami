# Sprite pipeline — attempt 002

> Architecture thread, fire 2. Audit of attempt_001 + absorption of
> recipes thread's 14 ops + 5 scorers + 5 non-blocking asks + one
> self-found gap (post-process fan-out).

## Confirmation-bias audit of attempt_001

**Rejection count.** For the cache layer I picked content-addressable
hash-based storage. Alternatives I didn't enumerate:
- **SQLite-backed cache.** Rejected — adds a DB dep; file-system
  CAS is simpler and greppable.
- **Flat `by_id/` only.** Rejected — would re-generate on prompt
  tweaks since the key would be id-only. CAS on content lets the
  same sprite serve many ids.
- **Git-annex-style content-addressing.** Rejected — heavy for a
  sprite cache; only useful if we ever want distributed caching.
  Logged as a v1.3+ direction if multi-machine cache is wanted.

Named now.

**Construction check.** The 8 CategoryConfig stubs in attempt_001 §1
were constructed to fit my registry shape. Recipes thread independently
authored 5 recipes; shapes match (same 8 sections per BRIEF_CONTENT.md,
same slots as CategoryConfig). Construction bias low — shape
validated by independent construction.

**Predictive test.** attempt_001 predicted new categories would
require distinct post-process chains. Recipes confirmed: 14 NEW ops
across 5 categories, each non-trivial. Prediction held.

**Self-found audit gap.** attempt_001 §1 declared
`post_process: list[str]` assuming a linear chain (each op: Image →
Image). **Tileset's `grid_cut` breaks this** — it produces a list of
tiles, subsequent ops operate per-tile, then `pack_spritesheet`
collapses back to one spritesheet. Linear list can't express fan-out.
Must fix in attempt_002. See §5 below.

## Absorbing recipes thread's 14 new post-process ops

From `observations/note_001.md`. Locked as the canonical ops table for
v1.1:

### Ops table (cumulative: existing + new)

Existing (from current `sprite_pipeline.py`):

| Op name | Signature | Notes |
|---|---|---|
| `pixel_extract` | Image → Image | Existing; perceptual-Lab bg detection + grid recovery + fringe cleanup |
| `isolate_largest` | Image → Image | Existing; scipy connected-components |
| `trim_transparent` | Image → Image | Existing; bbox crop with padding |
| `center_crop_object` | Image → Image | Existing; 55% center crop |
| `quantize_palette` | Image → Image | Existing; median-cut |
| `pixel_snap` | Image → Image | Existing; nearest-neighbor downscale |
| `normalize_height` | Image → Image | Existing; anchor-aware height normalize |

New (recipes thread proposals, v1.1):

| Op name | Signature | Category owner | v1.1? |
|---|---|---|---|
| `grid_cut` | Image → **list[Image]** | tileset | ✓ |
| `seamless_check` | list[Image] → list[Image] (pass-through + annotation) | tileset | ✓ |
| `pack_spritesheet` | **list[Image] → (Image, atlas_json)** | tileset | ✓ |
| `horizontal_tileable_fix` | Image → Image | background | ✓ |
| `flat_color_quantize` | Image → Image | ui_element | ✓ |
| `radial_alpha_cleanup` | Image → Image | effect | ✓ |
| `preserve_fragmentation` | Image → Image | effect | ✓ |
| `additive_blend_tag` | Image → Image (metadata-only side effect) | effect | ✓ |
| `eye_center` | Image → Image | portrait | ✓ |
| `head_only_crop` | Image → Image | portrait | ✓ |

Deferred to v1.2 (per recipes thread recommendation, concur):

| Op name | Signature | Category | Defer reason |
|---|---|---|---|
| `autotile_variant_gen` | Image → list[Image] | tileset | 47-wang complexity; author-curation works for v1.1 |
| `unify_palette` | list[Image] → list[Image] | tileset | Post-hoc palette harmonization; nice-to-have |
| `parallax_depth_tag` | Image → Image | background | Auto-depth tagging; author-supplied metadata works |
| `nine_slice_detect` | Image → Image (+ metadata) | ui_element | Author can supply `nine_slice` coords manually |

v1.1 ops total: **17** (7 existing + 10 new). v1.2 adds 4 more.

## Absorbing 5 new scorers

### Scorer table

| Scorer name | Weight vector | Category |
|---|---|---|
| `default_scorer` (existing) | coverage 0.25 · centering 0.25 · fragmentation 0.25 · color_diversity 0.25 | baseline |
| `character_scorer` | coverage 0.20 · centering 0.25 · fragmentation 0.30 · color_diversity 0.15 · silhouette 0.10 | character |
| `item_scorer` | coverage 0.30 · centering 0.30 · fragmentation 0.20 · color_diversity 0.20 | item |
| `texture_scorer` (existing) | coverage 0.40 · color_diversity 0.30 · tileability 0.30 | texture |
| `tileset_scorer` (NEW) | tile_count 0.25 · palette_coherence 0.20 · seamlessness 0.25 · per_tile_coverage 0.15 · edge_fringe 0.15 | tileset |
| `background_scorer` (NEW) | aspect_fidelity 0.10 · seamless_horizontal 0.35 · no_dominant_subject 0.20 · opacity 0.20 · color_diversity 0.15 | background |
| `ui_element_scorer` (NEW) | flatness 0.35 · contrast 0.25 · clean_edges 0.20 · centering 0.10 · opacity 0.10 | ui_element |
| `effect_scorer` (NEW) | radial_coherence 0.30 · brightness_range 0.25 · color_warmth 0.15 · coverage 0.15 · no_unwanted_subject 0.15 | effect |
| `portrait_scorer` (NEW) | eye_detection 0.30 · head_proportion 0.20 · centering 0.15 · palette_coherence 0.15 · no_text 0.10 · clean_silhouette 0.10 | portrait |

All derive from shared primitives in `score_sprite` (see existing
`sprite_pipeline.py:232`). Each scorer is a weighted sum over its
listed metrics. Metrics not in the existing primitive set (e.g.
`seamless_horizontal`, `eye_detection`) are new inspections to add
to the scorer module.

## Ask 3: `backend_fallback` on CategoryConfig

Accepted. Addition to the dataclass:

```python
@dataclass
class CategoryConfig:
    # ... existing fields ...
    backend: BackendName = "z_image"
    backend_fallback: BackendName | None = None   # NEW
```

Semantics: `generate_asset` first tries `backend`; if the backend
process is unreachable (connection error, 5xx after retries) OR
explicitly marked degraded, fall back to `backend_fallback` if set.
Cache key still uses the SUCCESSFUL backend's version — so a
fallback-generated sprite gets a distinct hash and an explicit
`backend_used` in its record.

Per recipes: portrait config = `{ backend: "ernie", backend_fallback: "z_image" }`.
All other categories = `{ backend: "z_image", backend_fallback: None }`.

## Ask 4: `metadata_schema` accepts typed/nested

attempt_001 had `metadata_schema: dict[str, str]`. Upgrading:

```python
@dataclass
class CategoryConfig:
    # ... existing ...
    metadata_schema: dict[str, "MetadataFieldSpec"] = field(default_factory=dict)

@dataclass
class MetadataFieldSpec:
    type: Literal[
        "string", "int", "float", "bool",
        "list[int]", "list[float]", "list[string]",
        "enum", "object",
    ]
    required: bool = False
    enum_values: list[str] | None = None    # when type='enum'
    item_type: str | None = None             # when type='object': nested type (as string reference)
    description: str = ""
```

Example for ui_element.nine_slice:
```python
metadata_schema = {
    "role": MetadataFieldSpec(type="enum", enum_values=["button","panel","icon","bar"]),
    "nine_slice": MetadataFieldSpec(type="list[int]", description="4-tuple [top,right,bottom,left] edge insets"),
    "state": MetadataFieldSpec(type="enum", enum_values=["normal","hover","pressed","disabled"]),
}
```

Validator: at `generate_asset()` call + at `assets.manifest.json`
load, typecheck metadata against schema. New error class
`metadata_schema_violation`.

## Ask 5: stretch ops v1.1 vs v1.2

Concur with recipes' recommendation. v1.1 ships without
`autotile_variant_gen`, `parallax_depth_tag`, `nine_slice_detect`,
`unify_palette`. Authors curate manually — tilesets ship as base
tiles without 47-wang auto-gen, UI nine-slice insets come from
`metadata.nine_slice`, backgrounds tagged manually, palettes
quantized per-tile.

v1.2 adds the 4 ops as automation. Logged in the ops table above.

## Self-found audit: post-process chain fan-out

**Gap.** attempt_001 §1 declared `post_process: list[str]`. But
`grid_cut` returns a list[Image], subsequent ops operate per-tile,
then `pack_spritesheet` collapses back. Linear list of
`Image → Image` can't express this.

**Fix (minimal surgery):** let ops have two arities. A "splitter" op
(like `grid_cut`) returns `list[Image]`. Ops after a splitter run
per-image over the list. A "collector" op (`pack_spritesheet`)
returns a single `Image` (or tuple of Image + atlas JSON).

Algorithm:
```python
def run_chain(img: Image, chain: list[str], ops: dict) -> PipelineResult:
    cur: Image | list[Image] = img
    for op_name in chain:
        op = ops[op_name]
        if isinstance(cur, list):
            if op.is_collector:
                cur = op(cur)           # list → Image
            else:
                cur = [op(x) for x in cur]  # element-wise
        else:
            cur = op(cur)               # Image → Image or list[Image]
    return cur
```

Ops declare their shape in a simple registry:

```python
@dataclass
class OpSpec:
    name: str
    is_splitter: bool = False      # single → list
    is_collector: bool = False     # list → single
    side_effects: list[str] = field(default_factory=list)  # e.g. ['metadata:composite_mode']

OPS: dict[str, OpSpec] = {
    "pixel_extract":         OpSpec("pixel_extract"),
    "isolate_largest":       OpSpec("isolate_largest"),
    "trim_transparent":      OpSpec("trim_transparent"),
    ...
    "grid_cut":              OpSpec("grid_cut", is_splitter=True),
    "seamless_check":        OpSpec("seamless_check"),  # list-element pass-through
    "pack_spritesheet":      OpSpec("pack_spritesheet", is_collector=True),
    "additive_blend_tag":    OpSpec("additive_blend_tag",
                                     side_effects=["metadata:composite_mode"]),
    ...
}
```

Tileset's chain becomes:
```python
post_process = [
    "pixel_extract",
    "grid_cut",              # splits to list
    "seamless_check",        # per-tile; pass-through + annotate
    "trim_transparent",      # per-tile
    "pixel_snap",            # per-tile
    "pack_spritesheet",      # collects to single + atlas
]
```

Validator: check that chain has at most one active split (a
collector must appear before another splitter). Error class
`chain_fan_out_invalid`.

**Cost:** ~30 LOC in the chain runner + ops registry. No breaking
change to existing chains (all existing ops are Image → Image, no
splitters, no collectors).

## Per-category variations tuning

Recipes proposed: effect: 5, background: 3. Concur. Update defaults:

```python
CATEGORIES = {
    "character":  CategoryConfig(..., variations=4, ...),
    "item":       CategoryConfig(..., variations=4, ...),
    "tileset":    CategoryConfig(..., variations=4, ...),
    "background": CategoryConfig(..., variations=3, ...),  # fewer failure modes
    "ui_element": CategoryConfig(..., variations=4, ...),
    "effect":     CategoryConfig(..., variations=5, ...),  # more variance needed
    "portrait":   CategoryConfig(..., variations=4, ...),
    "texture":    CategoryConfig(..., variations=4, ...),
}
```

## Cumulative CategoryConfig shape (after attempts 001 + 002)

```python
@dataclass
class CategoryConfig:
    name: str
    description: str

    # Prompting
    style_prefix: str
    style_suffix: str = ""
    negative_prompt: str

    # Generation
    gen_size: tuple[int, int] = (512, 512)
    variations: int = 4

    # Output
    target_size: tuple[int, int] = (64, 64)
    palette_colors: int | None = 16

    # Pipeline
    post_process: list[str] = field(default_factory=list)
    scorer: str = "default_scorer"

    # Backend
    backend: BackendName = "z_image"
    backend_fallback: BackendName | None = None         # NEW attempt_002

    # Metadata
    metadata_schema: dict[str, MetadataFieldSpec] = field(default_factory=dict)  # TYPED attempt_002
```

## Validator errors (cumulative)

| Error kind | Source | Condition |
|---|---|---|
| `sprite_ref_not_in_manifest` | attempt_001 | archetype `sprite_ref` not in assets.manifest.json |
| `metadata_schema_violation` | attempt_002 | asset metadata doesn't match CategoryConfig.metadata_schema |
| `chain_fan_out_invalid` | attempt_002 | post_process chain has overlapping splits |
| `backend_unavailable_no_fallback` | attempt_002 | preferred backend down + no `backend_fallback` set |
| `unknown_op` | attempt_002 | post_process references op not in OPS registry |
| `unknown_category` | attempt_001 (implied) | asset.category not in CATEGORIES registry |

## Ship criteria (cumulative)

Unchanged from attempt_001 §9 except:

6. (new) **Tileset end-to-end.** Author calls
   `generate_asset(category='tileset', prompt='grass tiles overworld',
   asset_id='grass_set')` with metadata `{tile_grid_w: 4, tile_grid_h: 4}`.
   The pipeline splits a 1024×1024 gen into 16 tiles, packs to a
   64×64-per-tile spritesheet + atlas JSON. Cache hits on second
   call.
7. (new) **Fallback backend.** Portrait with
   `backend_fallback='z_image'`: when ERNIE endpoint returns 503,
   falls back + returns a record with `backend_used='z_image'`.
8. (new) **Typed metadata check.** Providing
   `{nine_slice: ['a','b','c','d']}` for a field declared
   `list[int]` errors with `metadata_schema_violation`.

## Stop-signal projection

Fire 2 outcome: **structural movement YES** — absorbed 14 ops, 5
scorers, 4 config additions, 1 self-found gap (fan-out chain).
attempt_002 is implementer-ready for the ops-table + scorer-table +
CategoryConfig shape. Remaining work: may be minor absorption of
recipes thread's priors/fixtures in fire 3.

Expectation: fire 3 might be an audit + absorb priors/fixtures; if
nothing structural surfaces, that's 1 of 2 no-signal fires toward
Data Ceiling. Hold after fire 4 if fire 4 is also audit-only.

## Self-check

- Sprite-architecture scope? ✓
- Re-checked `sprite_pipeline.py` + recipes + note_001 **directly** (per
  priors-over-status discipline from audio thread)? ✓
- Zero-dep / LLM-authorable / category-extensible? ✓
- Each deliverable landable in one programmer-sitting? ✓ (ops table +
  scorer table + config additions + chain-runner are small focused
  changes)
- New structural movement? ✓ (ops + scorers + fan-out fix + config
  updates)

5/5 yes. Continue.

## Handoff to recipes thread

- **14 ops accepted** — continue writing fixtures + priors against
  the now-locked set.
- **5 scorers accepted** — per-metric implementations are architecture-
  thread work; your recipes already spec the weight vectors correctly.
- **`backend_fallback` shipped** — portrait recipe's `ernie` +
  fallback `z_image` now expressible in the registry.
- **Typed metadata schemas shipped** — your ui_element.nine_slice
  `list[int]` and other typed fields now expressible via
  `MetadataFieldSpec`.
- **4 stretch ops deferred to v1.2** — author-curation for v1.1.
- **Fan-out chain runner** — tileset's `grid_cut` ... `pack_spritesheet`
  flow is now valid. No recipe change needed on your side.

## Programmer handoff preview

Once attempt_003+ stabilizes (may be as soon as next fire if no new
signal), I'll land a consolidated IMPLEMENTATION.md like the audio
one — self-contained file with full spec, build order, test plan, ops
table, scorer table, ready for PR-sized execution.
