# parallax_backdrop — ERNIE asset workflow (spatial variants, no chain)

Multi-layer parallax-scrolling backdrops. Covers the `background_layer`
kind (promoted 2026-04-22). 7 sub_kinds covering 4 layout modes
(parallax_single / parallax_3layer / mode7 / skybox_static).

> **Architecture update 2026-04-22 (post-Shoal)**: parallax layers are
> **spatial variants**, not frame-sequential animations, so this workflow
> runs ERNIE-ONLY — no Qwen chain. `needs_animation = false` for every
> background_layer sub_kind by default. The shared
> `_common/base_plus_chain.py` orchestrator handles both static (ERNIE-
> only) and animated (ERNIE + Qwen chain) payloads, so scaffold authors
> don't need a separate codepath for parallax.

## Layer-mode cheat sheet

Per `anim_set.json::layer_modes`:

| Mode | Layers | ERNIE calls | Output shape | Sub_kinds |
|---|---:|---:|---|---|
| `parallax_single` | 1 | 1 | 1× 3200×224 PNG | `parallax_single` |
| `parallax_3layer` | 3 (far/mid/near) | 3 (same seed) | 3× 3200×224 PNGs | `parallax_far`/`_mid`/`_near` |
| `mode7` | 2 (horizon + floor) | 2 | 3200×112 horizon + 1024² tileable floor | `mode7_horizon`/`_floor` |
| `skybox_static` | 1 | 1 | 1× 256×224 PNG | `skybox_static` |

Seed sharing across the 3 `parallax_3layer` calls is the identity trick
— ERNIE has no parallax-layer prior, so coherence across far/mid/near
is produced by same-seed sampling with detail-density prompt variations.

## Run

```bash
cd scaffolds/engine/asset_workflows/_common

# All background_layer payloads
python3 batch_run.py --apply --kind background_layer

# Single essence (e.g. Sonic's green hill 3-layer)
python3 batch_run.py --apply --essence 1991_sonic_the_hedgehog --kind background_layer

# Post-process (horizontal feather + canvas stretch)
python3 strip_assembler.py ./out/bpc/ --recurse
```

Note: `strip_assembler.py` handles the standard N×1 strip shape — it
works fine for parallax outputs since each layer gets its own payload
directory (frames=1 each). Parallax-specific postprocess (feather-edge +
horizontal stretch from 1024² to 3200×224) is handled by this
workflow's `postprocess.py` helpers.

## Postprocess contract

`postprocess.py` exposes:

- `feather_edges_horizontal(img_path, feather_px=16)` — radial-cosine alpha ramp on left/right edges for horizontal seam blending
- `stretch_to_target(img, target_w, target_h)` — LANCZOS resize from ERNIE's 1024² to the engine-target canvas
- `assemble_single(src, out_dir, seed_label, target_w=3200, target_h=224)` — single-layer feather + stretch
- `assemble_3layer(far, mid, near, out_dir, seed_label)` — 3-layer feather + stretch, outputs far/mid/near PNGs
- `assemble_mode7(horizon, floor, out_dir, seed_label)` — horizon strip + square tileable floor
- `verify_tileable_horizontal(img_path, out_path, repeats=3)` — eyeball seam canary

## Integration with `ParallaxScroll` mechanic

After assembly, each backdrop's PNGs land in the runtime manifest as
`background_layer` sprites. The engine's `ParallaxScroll` mechanic
(see `design/mechanics/parallax_scroll.ts`) consumes them via the
`parallax_setup.ts` scaffold helpers:

```ts
import { configureParallax3LayerFromEssence } from '@engine/sprites/parallax_setup'
const instance = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player')
mechanicRegistry.create(instance!, game)
```

## Status

- **Landed**: 2026-04-22 (12th asset_workflow in the library).
- **Old canary set**: deleted (`run_canary.py` + `canary_prompts.jsonl`) — replaced by corpus-driven nudge payloads.
- **Live outputs**: pending ERNIE coming back online.
