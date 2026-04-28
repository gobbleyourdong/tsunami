# iso_cache_poc — render-time pixel cache demo + 3D-SDF rendering

The canonical demo is **`object_buffer_cache.html`**. It runs on plain
`python3 -m http.server` (no build step). All the original 2D systems
(per-archetype pixel cache, destruction, Voronoi shatter, falling-sand
particles, LAVA/WATER reactions, robot ↔ ball physics) are intact.

The change vs the original 2D pipeline: each archetype's SDF is now
**3D**, raymarched per pixel on the CPU into the same `colorBuf`. Shapes
look like rounded 3D forms shaded by a light source instead of flat 2D
silhouettes. See `PLAN_3D_PORT.md` for the per-archetype conversion.

A separate **`raymarch3d/`** directory holds an earlier TS+WebGPU
exploration. It's a parallel reference, not the canonical demo. Read
`raymarch3d/README.md` for context. The skeleton renderer source under
`engine/src/character3d/` was a READ-ONLY upstream the whole way — never
modified, only patterns copied.

## Run

```
python3 -m http.server 9123
```
Then `http://localhost:9123/object_buffer_cache.html`. First load takes
3–4s while the terrain heightfield (1M px buffer) bakes — only happens
once, then the cache holds. After that the demo runs as before.

For the auxiliary TS+WebGPU POC under `raymarch3d/` use Vite:
```
npx vite --port 9124
```
`node_modules` is symlinked from `../engine/node_modules`.

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

## 3D-SDF rendering path (PLAN_3D_PORT.md)

Each `GameObject` can opt into the 3D path by passing `sdfFn3d` (a
3D distance function `Vec3 → number`) and `metersPerPixel` (scale).
For animated archetypes, `sdfFn3dFactory(animPhase)` returns a fresh
SDF per bake.

`_bakeInto` then routes through a per-pixel CPU raymarch:
1. Pixel `(lx, ly)` → world `(wx, wy)` via `metersPerPixel`.
2. `R3.raymarchPixel(sdfFn, wx, wy, { maxSteps, elevation })` — ortho
   ray with optional iso tilt; returns `{hit, p, normal, steps}`.
3. On hit: `R3.shadeHit(normal, baseColor, lightDir)` (Lambert +
   ambient + soft rim) → RGB. Normal stored in normal buffer; depth
   from `p.z` in depth buffer.
4. On miss: alpha 0.

Local-damage hard masking still applies (destruction circles clear
pixels strictly inside any carve regardless of the 3D SDF result).

### Tuning knobs per archetype

| opt | default | purpose |
|---|---|---|
| `sdfFn3d` | null | static 3D SDF |
| `sdfFn3dFactory` | null | (animPhase) → 3D SDF, called per bake |
| `metersPerPixel` | 0.01 | buffer pixel grid scale into SDF world units |
| `bakeMaxSteps` | 48 | march budget per pixel; lower for big buffers |
| `bakeElevation` | `ISO_ELEVATION` (0.20 rad ≈ 11.5°) | per-archetype iso override |
| `lightDir` | `[0.4, 0.7, 0.6]` | upper-front-right key light |

### Archetypes converted

| archetype | flags | mPP | maxSteps | notes |
|---|---|---:|---:|---|
| `terrain` | static | 0.01 | 12 | heightfield slab from `hillSurfaceMeters`; 1M px, init bake ~4s |
| `volcano` | animating, loopFrames=2 | 0.011 | 24 | ellipsoid body + animated plume sphere |
| `rock` | static | 0.01 | 48 | smoothUnion(box, sphere) |
| `heart` | animating, loopFrames=6 | 0.006 | 48 | factory: 2 spheres + stretched ellipsoid; pulses |
| `gear` | rotate | 0.009 | 48 | disk + 12 teeth boxes + hub bump |
| `fan` | rotate | 0.009 | 48 | hub cylinder + 4 box blades |
| `critter` | animating, loopFrames=4 | 0.011 | 48 | factory: head + body + 2 arms + 2 legs swinging |

Balls and other small archetypes still use the 2D path (their flat
silhouette reads fine and the 3D bake adds no value).

### Performance

CPU raymarching on the main thread is the cost. Animating archetypes
re-bake on tick boundaries; the per-bake budget per archetype is
roughly `pixels × maxSteps × prims × 1μs`. Big buffers (terrain,
volcano) compensate via `bakeMaxSteps` and slower `loopFrames`.
Rough numbers from the smoke tests:

- 1000 raymarches ≈ 5–22 ms (varies with prim count + step count)
- Terrain init bake (one-time): ~3–4 s for 2000×500 buffer
- Per second: heart 6×, critter 4×, volcano 2×, gear/fan/rock 0×
- Aggregate: ~150–250 ms / sec compute budget on a modern CPU

### Future work

The cone primitive in `raymarch3d_cpu.js` has a known bug — heart
fell back to a stretched ellipsoid for the bottom point. Fixing it
would let real triangular profiles show up in volcano + heart + others.

A WebGPU bake fast-path (compute-shader version of `raymarchPixel`
writing directly to a texture) would 100× the bake speed and unlock
much bigger buffers / per-tick rebakes for everything. The
`raymarch3d/` POC has the building blocks if needed.

## raymarch3d (TS + WebGPU) — auxiliary reference

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

## File layout

```
iso_cache_poc/
├── object_buffer_cache.html      ← canonical demo (2D + 3D-SDF baked path)
├── raymarch3d_cpu.js             ← JS 3D-SDF lib + raymarcher + shader
├── README.md                      ← this file
├── PLAN_3D_PORT.md                ← per-archetype 3D conversion plan + status
├── OVERNIGHT_PLAN.md              ← (older) TS+WebGPU build plan; superseded
├── package.json + tsconfig.json + vite.config.ts
├── node_modules → ../engine/node_modules (symlink, only needed for raymarch3d/)
└── raymarch3d/                    ← auxiliary TS+WebGPU reference
    ├── index.html, main.ts, pipeline.ts
    ├── raymarch.wgsl              ← fullscreen vertex + raymarch fragment
    ├── sdf3d.ts                   ← TS port of upstream sdf.ts
    ├── assets.ts, loader.ts
    ├── scenes/, bake_to_buffer.ts
    └── README.md
```

See `PLAN_3D_PORT.md` for the canonical demo's per-archetype build
history and `OVERNIGHT_PLAN.md` for the auxiliary TS+WebGPU work.
