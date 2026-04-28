# iso_cache_poc — render-time pixel cache demo + 3D-SDF panel

Two demos in one workspace:

1. **2D destruction demo** (`object_buffer_cache.html`) — Canvas2D, no
   build step. Voronoi shatter + falling-sand particles + LAVA/WATER
   reactions over a per-archetype prebaked-buffer cache.
2. **3D-SDF POC** (`raymarch3d/`) — TS + Vite + WebGPU. Per-pixel WGSL
   raymarcher into a flat primitive-list SDF. Built fresh as a port of
   the rendering style from `engine/demos/skeleton_demo` (READ-ONLY
   upstream — that code was not modified).

## Run options

**Plain HTTP (2D demo only):**
```
python3 -m http.server 9123
```
Then `http://localhost:9123/object_buffer_cache.html`. The 3D-SDF panel
in the page will print a "raw HTTP server can't resolve .ts" hint and
stay dark — see Vite option for the full experience.

**Vite (both demos, full integration):**
```
npx vite --port 9124
```
Then visit either:
- `http://localhost:9124/object_buffer_cache.html` — 2D demo with the
  3D-SDF panel live underneath.
- `http://localhost:9124/raymarch3d/` — standalone 3D POC at full size.

`node_modules` is symlinked from `../engine/node_modules`; if that
breaks, `npm install` inside this directory will recreate it.

## What the demo proves

Each `GameObject` owns a triple buffer (color, depth, normal) baked
**once** by the SDF at init. Per-frame work is pure `drawImage`.
Transforms (translate, rotate, camera pan) never touch the buffer.
Only objects flagged `deform_full` or `deform_local` emit
cache-update events.

Watch the canvas HUD: **SDF evals this frame** stays at 0 in steady
state — no matter how fast the camera pans, how many objects are on
screen, or how the critter/fan animate. Toggle the heart pulse or
gear teeth to see the only re-bakes that actually fire.

See `../SDF_PIXEL_PRIMITIVES.md` § "Cache architecture" for the doc
backing this demo.

## Animation-flag taxonomy

| Flag | Per-frame work | Bake events |
|---|---|---|
| `static` | drawImage | once at init |
| `translate` | drawImage | once at init (motion is independent of flag) |
| `rotate` | drawImage with ctx.rotate | once at init |
| `loop` | drawImage(loopBuffers[loopTick % N]) | **N at init, then never.** Max 8 frames; all loops advance on one global tick. |
| `deform_full` | drawImage | per cache-update tick (whole buffer) |
| `deform_local` | drawImage | per cache-update tick (sub-rect(s) only) |

Cosmetic effects (palette cycling, sway, rim-light, damage-flash) run
at composite time over the prebaked buffers and are NOT bake events.

## raymarch3d (TS + WebGPU)

Lives in `raymarch3d/`. Mounts a per-pixel raymarched SDF on a WebGPU
canvas. Same rendering model that the engine's `character3d` renderer
uses (READ-ONLY upstream, copied/rewritten — not modified):

- Flat primitive list in a storage buffer (sphere, box, capsule, cylinder,
  ellipsoid, torus, roundedBox).
- 8 blend groups with smooth-union (`smin`) compositing → organic
  shapes from a few primitives.
- Palette buffer; each primitive references a slot.
- Lambert + ambient + soft rim shading; orthographic camera with slow
  Y-axis orbit so silhouettes read as 3D.
- JSON loader for `sdf_modeling_research`-style scene files (subset:
  `shape:*` parts; preset inheritance and named-anchor placement are
  out of scope for the POC).

Built-in assets: knight longsword, rock chunk(s), chibi head, palm tree.
Loaded scenes: sword on anvil (anvil only), altar with lantern.

The 2D destruction demo embeds a small 3D-SDF panel beneath itself
(see Phase E) so both rendering styles can be compared in one page.

## Architecture

```
            ┌────────────────────────────────────────┐
            │  iso_cache_poc/                        │
            │                                        │
            │  ┌──────────────┐    ┌──────────────┐  │
            │  │ 2D demo      │    │ raymarch3d   │  │
            │  │ Canvas2D     │    │ TS + WebGPU  │  │
            │  │ destruction, │    │ SDF prims +  │  │
            │  │ particles,   │    │ WGSL raymarch│  │
            │  │ Voronoi,     │    │ JSON scene   │  │
            │  │ piles        │    │ loader       │  │
            │  └──────┬───────┘    └──────┬───────┘  │
            │         │                   │          │
            │         └─────── share ─────┘          │
            │              hillHeight,               │
            │              SDF primitives,           │
            │              palette ideas             │
            └────────────────────────────────────────┘
                          ▲
                          │ READ-ONLY reference
                          │
            ┌────────────────────────────────────────┐
            │  engine/src/character3d/               │
            │  (raymarch_renderer.ts, sdf.ts, …)     │
            │  NOT MODIFIED — patterns copied.       │
            └────────────────────────────────────────┘
```

## TypeScript layout

```
iso_cache_poc/
├── object_buffer_cache.html      ← 2D destruction demo (Canvas2D)
├── package.json + tsconfig.json + vite.config.ts
├── node_modules → ../engine/node_modules (symlink)
└── raymarch3d/
    ├── index.html                ← standalone 3D POC entry
    ├── main.ts                   ← bootstrap; exports mountOn(canvas, opts)
    ├── pipeline.ts               ← WebGPU render pipeline
    ├── raymarch.wgsl             ← fullscreen vertex + raymarch fragment
    ├── sdf3d.ts                  ← TS port of upstream sdf.ts (CPU path)
    ├── assets.ts                 ← built-in primitive lists + palette
    ├── loader.ts                 ← JSON scene loader (subset)
    └── scenes/                   ← sample JSON scenes
```

See `OVERNIGHT_PLAN.md` for the phased buildout history.
