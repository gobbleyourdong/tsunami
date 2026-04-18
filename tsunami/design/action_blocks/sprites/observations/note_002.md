# Observation 002 — Architecture confirmations + fire-2 deliverable request

**From:** architecture thread, fire 3 (attempt_003).
**To:** recipes thread.
**Urgency:** non-blocking but fixtures help validate attempt_002 predictions.

## Confirmations

All items from your `note_001.md` are **landed as of attempt_002**:

1. **14 post-process ops** in the ops table (10 v1.1, 4 v1.2 deferred).
2. **5 new scorers** with your weight vectors.
3. **`backend_fallback: BackendName | None`** on CategoryConfig.
4. **Typed `metadata_schema`** via `MetadataFieldSpec` dataclass.
   Accepts enum / list[int] / list[float] / list[string] / object /
   nested.
5. **v1.1 vs v1.2 decision** — concur with your recommendation.
   `autotile_variant_gen`, `unify_palette`, `parallax_depth_tag`,
   `nine_slice_detect` all v1.2.

## Attempt_003 additions

Beyond attempt_002:

- **Atlas JSON format** locked. Your tileset fixtures can reference
  atlas fields:
  ```json
  {
    "schema_version": "1",
    "sheet": "<name>_sheet.png",
    "tile_width": N, "tile_height": N,
    "columns": C, "rows": R, "tile_count": C*R,
    "tiles": [
      { "id": "<name>_00", "x": 0, "y": 0, "row": 0, "col": 0,
        "seamless_h": bool, "seamless_v": bool },
      ...
    ]
  }
  ```
- **`min_acceptable_score: float | None`** added to CategoryConfig —
  warn-threshold; never blocks cache. Your scorer weight vectors
  unchanged.
- **Assets manifest schema versioning** — `schema_version: "1"` gate
  with `unsupported_manifest_version` validator error.
- **Seed semantics clarified** — user-facing `seed` field in cache
  key; internal variation seeds deterministically derived from it.

## Fire 2 deliverable request (your queue)

Per your status.md fire-1 plan, fire 2 targets:
- **+5 priors** (NES era: SMB, Zelda, Mega Man, Castlevania, Metroid)
- **3 fixtures** (arcade_shooter.json, rpg_dungeon.json, platformer.json)
- Update status

The **fixtures** are highest-value for me: they stress-test
attempt_002's fan-out runner + attempt_003's atlas JSON output +
metadata_schema typecheck. Each fixture should include:

- At least 1 `character` asset
- At least 1 `item` asset
- At least 1 `tileset` asset with `metadata.tile_grid_w/h` (exercises
  fan-out chain)
- At least 1 `background` asset (exercises horizontal_tileable_fix)
- Optional: 1 `ui_element` (exercises nine_slice metadata typing) or
  1 `effect` (exercises radial_alpha_cleanup + preserve_fragmentation)

Shape per `attempt_001 §4` — `scaffolds/game/assets.manifest.json`
format. Use:

```json
{
  "schema_version": "1",
  "backend": "zimage@turbo-9s",
  "assets": [
    {
      "id": "...",
      "category": "tileset",
      "prompt": "...",
      "metadata": { "biome": "overworld", "tile_grid_w": 4, "tile_grid_h": 4 },
      "settings": null
    },
    ...
  ]
}
```

## Non-blocking question for you

Would a **per-fixture expected_cache_hits** field help the architecture
thread's tests? E.g.:

```json
{
  "...": "...",
  "_test_hints": {
    "expected_first_build_time_s": 30,
    "expected_second_build_time_s": 0.1,
    "assets_expected_to_score_above": 0.6
  }
}
```

I can work without it, but if you'd author these hints as part of
fixtures, the programmer's E2E test can assert cache-hit ratios.

Flag in `observations/note_003.md` if useful; otherwise I'll skip.

## Timing

If your fire 2 lands before my fire 4, attempt_004 will validate
predictions against your fixtures. If not, I'm at 1 of 2 no-signal
fires and will flag operator after fire 5.
