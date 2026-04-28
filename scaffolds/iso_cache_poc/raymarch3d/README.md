# raymarch3d — TS + WebGPU 3D-SDF POC

Per-pixel WGSL raymarcher into a flat primitive-list SDF. Built fresh
for the iso_cache_poc workspace as a port of the rendering style from
`engine/demos/skeleton_demo` (READ-ONLY upstream — that code is
referenced, never modified).

## Quick start

```sh
cd /home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/iso_cache_poc
npx vite --port 9124
```

Open **http://localhost:9124/raymarch3d/** for the standalone POC, or
**http://localhost:9124/object_buffer_cache.html** for the 2D demo with
a 3D-SDF mini-panel embedded.

`node_modules` is a symlink to `../engine/node_modules`; if missing,
`npm install` inside this directory reproduces it.

## Architecture

```
   index.html              ┌────────────────────┐
   #canvas + #status   ←───│ main.ts (bootstrap)│
   #asset-buttons          │  - mountOn(canvas) │
                           │  - render loop     │
                           │  - asset switcher  │
                           └──────────┬─────────┘
                                      │
              ┌───────────────────────┼─────────────────────────┐
              ▼                       ▼                         ▼
   ┌────────────────┐    ┌────────────────────┐    ┌────────────────────┐
   │ pipeline.ts    │    │ assets.ts          │    │ loader.ts          │
   │  WebGPU device │    │  built-in primitive│    │  JSON scene loader │
   │  bind groups   │    │  lists + palette + │    │  (subset of the    │
   │  pipeline      │    │  packPrimitives()  │    │  sdf_modeling      │
   └────────┬───────┘    └─────────┬──────────┘    │  research format)  │
            │                      │               └────────────────────┘
            ▼                      ▼
   ┌─────────────────────────────────────┐
   │ raymarch.wgsl                       │
   │  vertex: fullscreen triangle        │
   │  fragment:                          │
   │    - decode flat primitive array    │
   │    - smooth-union by blend group    │
   │    - march ray from ortho plane     │
   │    - normal via finite-diff gradient│
   │    - Lambert + ambient + rim shade  │
   │    - palette-slot color lookup      │
   └─────────────────────────────────────┘
```

## Primitive vocabulary

Same set as the engine's `character3d` raymarcher:

| Type | Name        | Params                                  |
|----:|-------------|-----------------------------------------|
| 0   | sphere      | radius                                  |
| 1   | box         | half-extents (xyz)                      |
| 2   | capsule     | radius, half-length                     |
| 3   | cylinder    | radius, half-height                     |
| 4   | ellipsoid   | radii (xyz)                             |
| 5   | torus       | major-radius, minor-radius              |
| 6   | roundedBox  | half-extents (xyz), corner-radius       |

Each primitive carries: type, blendGroup (0 = standalone), blendRadius
(smin radius when shared with other primitives in the same group),
paletteSlot, params (vec4), offset (vec3), rotation (quaternion xyzw).

## Built-in assets

| Name (asset switcher)         | Primitives | Notes                                    |
|-------------------------------|------------|------------------------------------------|
| `sword (knight longsword)`    | 4          | blade · guard · grip · pommel            |
| `rock chunk`                  | 2          | smooth-union of box + sphere             |
| `rock chunk #2`               | 2          | seeded variant                           |
| `chibi head`                  | 2          | skull ellipsoid + hair ellipsoid         |
| `palm tree`                   | 7          | trunk + coconut + 5 splayed fronds       |
| `scene: sword on anvil`       | from JSON  | renders the anvil only (sword extends)   |
| `scene: altar offering`       | from JSON  | renders the lantern only                 |

The "scene:" entries fetch from `./scenes/*.json`; objects that
reference a preset via `extends` are skipped (their parts aren't
inlined). Adding a JSON scene with explicit `parts[]` Just Works.

## Future work

- **Phase G (stretch in OVERNIGHT_PLAN.md)**: bake a 3D-SDF render to
  an offscreen WebGPU texture, read it back as `ImageData`, and feed
  that into the 2D demo's archetype `colorBuf` — so a 3D-rendered
  rock can participate in the destruction/particle/Voronoi pipeline
  as a normal archetype.
- Skeletal animation (per-bone primitives + VAT pose driver).
- Anchor + extends resolution in the JSON loader.
- Color funcs (gradientY, stripes, dots) ported from the engine
  raymarcher; would let one primitive show a multi-color material.
- WebGPU compute pass for parallel bake into a texture atlas of
  archetype thumbnails.

## What was NOT touched

`engine/src/character3d/*` and `engine/demos/skeleton_*` are read-only
references. Patterns from those files were studied; nothing was
imported, modified, or moved. This POC is a from-scratch
reimplementation in the iso_cache_poc workspace.
