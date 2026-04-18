# Sprite pipeline — attempt 003

> Architecture thread, fire 3. Recipes thread hasn't landed fire 2
> yet (no priors, no fixtures). Using this fire for a confirmation-
> bias audit of attempt_002 + fill 4 self-found gaps. This is
> structural — not re-statement — so Data Ceiling counter stays at 0.

## Confirmation-bias audit of attempt_002

**Rejection count — alternatives I didn't fully name in attempt_002.**

- **Fan-out chain shape.** attempt_002 §5 named 1 alternative
  (structured pre/split/per_tile/collect/post). Missed a third:
  polymorphic ops that internally handle `Image | list[Image]`.
  Rejected because op implementations would all have to be
  list-aware — duplicating the chain-runner logic inside each op.
  Flat list + OpSpec.flags centralizes the dispatch. Named now.

- **Backend fallback.** attempt_002 picked single `backend_fallback:
  BackendName | None`. Alternative: priority list
  `backends: [BackendName, ...]` — try each in order. Rejected for
  v1.1 because only portrait needs fallback today; single optional
  is enough. Flag for v1.2 if a 3rd backend enters (e.g. OpenAI
  image API).

- **metadata_schema shape.** attempt_002 picked a `MetadataFieldSpec`
  dataclass. Alternative: JSON Schema subset (draft-07 style).
  Rejected for v1.1 complexity; `MetadataFieldSpec` covers the
  recipe cases with ~20 LOC of validator logic. JSON Schema is v1.3+
  candidate if schema composition (oneOf/allOf) becomes a need.

**Construction check.** attempt_002's OpSpec/scorer shapes were
derived from recipes' note_001. Shapes match recipes' independent
authoring — construction bias low. But: I haven't actually
stress-tested the fan-out runner against the full tileset chain.
Need recipes' fixtures to exercise it end-to-end.

**Predictive test.** attempt_002 predicts:
1. Tileset fan-out (grid_cut → per-tile → pack) works end-to-end.
2. Portrait backend_fallback gracefully degrades when ERNIE is down.
3. Typed metadata_schema catches `nine_slice` type violations.

All 3 await recipes' fixtures + programmer integration tests. None
falsified yet; not validated yet either.

**Audit outcome:** attempt_002 stands. 3 alternatives newly named for
the record. 3 predictions awaiting validation via fixtures.

## 4 self-found gaps in attempt_002

### G1 — Atlas JSON format for `pack_spritesheet`

`pack_spritesheet` returns `(Image, atlas_json)` but the atlas JSON
shape isn't spec'd. Scaffolds reading it at runtime need the shape.

**Fix:** canonical atlas JSON, matches the existing
`assemble_spritesheet` output in `sprite_pipeline.py:436` (already
well-formed):

```json
{
  "schema_version": "1",
  "sheet": "grass_set_sheet.png",
  "tile_width": 16,
  "tile_height": 16,
  "columns": 4,
  "rows": 4,
  "tile_count": 16,
  "tiles": [
    { "id": "grass_set_00", "x": 0, "y": 0, "row": 0, "col": 0,
      "seamless_h": true, "seamless_v": true },
    { "id": "grass_set_01", "x": 16, "y": 0, "row": 0, "col": 1,
      "seamless_h": true, "seamless_v": false },
    ...
  ]
}
```

Seamlessness flags come from `seamless_check` op's annotations (per
tile), persisted through the chain's side-effects channel.

**Cost:** ~15 LOC to `pack_spritesheet`. Reuses existing
`assemble_spritesheet` shape.

### G2 — Score threshold for cache acceptance

attempt_002 doesn't say what to do when the best-of-N variation
scores poorly. If best score < threshold, should we cache it?
Regenerate with more variations? Fail?

**Fix:** policy — **always cache the best-of-N result**, regardless
of score. Score is part of the cached record; authors/operators can
force-regenerate via `generate_asset(..., force=True)`. Regeneration
policy is explicit, not automatic.

Rationale: the pipeline is deterministic given cache-key inputs; an
auto-regen loop would diverge depending on RNG, making the cache
non-deterministic. Authors own the "is this good enough" decision.

Add to CategoryConfig:

```python
@dataclass
class CategoryConfig:
    # ... existing ...
    min_acceptable_score: float | None = None  # warn-only; never blocks cache
```

When `best_score < min_acceptable_score`, `generate_asset` returns
the record with a `score_warning: True` flag in the AssetRecord.
Build step can log / surface to operator. No error, no block.

**Cost:** ~10 LOC. Small but important for operator ergonomics.

### G3 — Seed semantics + variations interaction

attempt_001 said `seed: None` means "cache first gen permanently."
But `variations: 4` + existing `generate_variations()` uses
time-based seeds per variation — those individual seeds don't enter
the cache key.

**Fix (clarification, not change):** the cache key uses
`settings.seed` which is the USER-PROVIDED seed (or None). The
internal per-variation seeds are implementation details; they vary
each gen call but we only keep the best. So:
- `seed = None`: first gen picks random-best, caches. Subsequent
  calls return cached. Stable.
- `seed = 12345`: deterministic — same integer seed → same internal
  seed sequence → same best pick → same cached record.

This is what attempt_001 intended but worth making explicit for the
programmer: **the `seed` field in cache key is user-facing; internal
variation seeds are derived deterministically from it.**

Add to `_normalize_settings`:

```python
def _normalize_settings(s: dict) -> dict:
    # ... existing ...
    # Seed: None is a distinct hash input vs 0. Don't collapse.
    if "seed" not in out:
        out["seed"] = None
    return out
```

**Cost:** 0 LOC; clarification only.

### G4 — Assets manifest schema versioning

attempt_001 §4 showed `schema_version: "1"` in the manifest example
but didn't spec validation. If the schema evolves (say v1.2 adds
`animation: {...}` nesting), older manifests should still load.

**Fix:** simple version field + compatibility contract:

```python
MANIFEST_SCHEMA_VERSION = "1"

def load_manifest(path: Path) -> AssetManifest:
    raw = json.loads(path.read_text())
    ver = raw.get("schema_version", "0")
    if ver not in SUPPORTED_VERSIONS:
        raise ValidationError("unsupported_manifest_version", ver)
    # v0 → v1 upgrade path: auto-promote if trivial
    return AssetManifest(**raw)
```

Add to validator error table:

| Error kind | Condition |
|---|---|
| `unsupported_manifest_version` | `schema_version` not in SUPPORTED_VERSIONS |

Total validator errors: **7** (was 6 in attempt_002).

**Cost:** ~15 LOC.

## Cumulative state (attempts 001 + 002 + 003)

| Component | State |
|---|---|
| CategoryConfig | 8 fields including `backend_fallback`, typed `metadata_schema`, + `min_acceptable_score` (G2) |
| Ops table | 17 v1.1 ops (7 existing + 10 new) + 4 v1.2 deferred, with `OpSpec` flags for fan-out |
| Scorer table | 5 new scorers with explicit weight vectors |
| Cache layer | content-addressable sha256[:16] key; seed semantics clarified (G3); by_hash + by_id |
| `generate_asset()` | cache-first, N-variation best-of, score-warning surfaced |
| Asset manifest | JSON with `schema_version: "1"` (G4) + typed metadata |
| Action-blocks tie-in | `Archetype.sprite_ref?: string` |
| Atlas JSON format | spec'd (G1) |
| Validator error kinds | 7 total |
| Backend abstraction | ABC + Z-Image + ERNIE, single `backend_fallback` |

## Ship criteria (cumulative updates)

Unchanged from attempt_002 except:

9. (new) **Atlas JSON structural.** `pack_spritesheet` output atlas
   JSON validates against the shape from G1; fields match; tile_count
   equals `columns × rows` minus any rejected tiles.
10. (new) **Score warning surfaces.** Scenario: gen produces
    `best_score = 0.3` against `min_acceptable_score = 0.5`. Record
    has `score_warning: True`. Build log prints warning. No error.
11. (new) **Manifest version gate.** Manifest with
    `schema_version: "99"` errors at load with
    `unsupported_manifest_version`.

Total ship tests: **11** (unchanged to user count; 9-11 added here
to the explicit list).

## Architecture-thread stop-signal projection

- Fire 2 (attempt_002): major structural absorption. YES.
- Fire 3 (this): minor structural — 3 rejected alternatives named,
  4 gaps fixed. **Still YES**, but smaller than fire 2.
- Fire 4 outlook: depends on recipes thread. If priors/fixtures land
  before fire 4, I'll stress-test attempt_002's predictions and
  likely find 0–2 more gaps. If recipes remain on standby, fire 4 is
  an audit-only fire → counter = 1 of 2 no-signal fires.

**Implementer-ready state:** architecture is effectively at ship
quality as of attempt_003. Remaining work in the architecture thread
is validation-driven (stress-test via fixtures). I could land the
consolidated `IMPLEMENTATION.md` now, but I'll wait for recipes' fire
2 to include fixtures as canonical test inputs.

## Signal to recipes thread

Not writing to your dirs. Notes in `observations/note_002.md` (this
fire):

1. **14 ops + 5 scorers ALL ACCEPTED** as of attempt_002. No
   revisions.
2. **4 stretch ops v1.2**, NOT in v1.1. Author-curation for v1.1
   tilesets: no autotile variants; palette coherence via prompt +
   post-quantize only.
3. **Atlas JSON shape locked** (G1 above). Your fixtures can
   reference atlas fields directly.
4. **`min_acceptable_score` added** (G2). Your per-category scorer
   weight vectors stand; this is just a warn-threshold field.
5. **Fire 2 deliverables still pending:** your 15 priors + 3
   fixtures would stress-test my predictions. Fixtures especially
   — arcade_shooter.json, rpg_dungeon.json, platformer.json with
   tileset + character + item + background + ui would exercise the
   full chain end-to-end.

If you land fire 2 before the architecture cron fires again,
attempt_004 will validate predictions against your fixtures. If not,
attempt_004 is an audit + hold.

## Self-check

- Sprite-architecture scope? ✓
- Re-checked files directly (priors-over-status)? ✓ — confirmed
  recipes fire 2 hasn't landed yet; no priors, no fixtures.
- Zero-dep / LLM-authorable / category-extensible? ✓
- Each deliverable landable in one programmer-sitting? ✓ — each gap
  fix is ~10–15 LOC.
- New structural movement? ✓ — 4 gaps fixed, 3 rejected alternatives
  named. Not re-stating.

5/5 yes. Counter: 0 of 2 no-signal fires. Continue.
