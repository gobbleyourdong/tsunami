# Overnight Plan — Port skeleton_demo's 3D-SDF render style into iso_cache_poc

This is a self-contained execution plan. Each `/loop` fire should:

1. Read this file top-to-bottom.
2. Find the first phase whose **Status** is `PENDING`.
3. Execute its **Deliverable** following its **Steps**.
4. Verify its **Acceptance** criteria.
5. Update the **Status** to `COMPLETE` (or `BLOCKED — reason` if it can't finish).
6. Commit changes with the phase number in the message subject.
7. End the turn — the loop's interval handles re-firing.

If a phase blocks, mark it `BLOCKED — <one line reason>` and proceed to the
next `PENDING` phase. Don't sit idle; another phase may be unblockable.

---

## Goal

Port the **3D SDF rendering style** from `engine/demos/skeleton_demo` into
the `iso_cache_poc` directory using **TypeScript + WebGPU**. Constraint:
do **NOT** modify any file under `engine/src/character3d/` or
`engine/demos/skeleton_*`. Read-only reference; rewrite or copy as needed.

End-state vision: a separate `raymarch3d/` POC that renders prebuilt SDF
assets (sword, rock, chibi head, palm tree) on a WebGPU canvas, layered
beside the existing 2D destruction demo (which stays untouched). Future
follow-up: integrate the 3D shapes back into the 2D demo's pixel-cache
+ destruction pipeline.

---

## Project layout (already in place)

```
iso_cache_poc/
├── object_buffer_cache.html      ← existing 2D destruction demo (KEEP)
├── README.md                      ← existing
├── package.json                   ← TS + Vite + @webgpu/types
├── tsconfig.json                  ← strict; ESNext
├── vite.config.ts                 ← serves :9123, two HTML entrypoints
├── node_modules → ../engine/node_modules  (symlink)
├── raymarch3d/                    ← POC root
│   ├── index.html                 ← POC entry HTML (loads main.ts)
│   ├── main.ts                    ← MISSING — Phase B
│   ├── pipeline.ts                ← MISSING — Phase B
│   ├── sdf3d.ts                   ← TS port of engine sdf.ts
│   ├── raymarch.wgsl              ← fullscreen vert + raymarch fragment
│   └── assets.ts                  ← GPU primitive lists for test shapes
└── OVERNIGHT_PLAN.md              ← this file
```

---

## Build / verify commands

- **Compile check:** `cd /home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/iso_cache_poc && npx tsc --noEmit`
- **Dev server:** `cd /home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/iso_cache_poc && npx vite --port 9124` (use 9124 to avoid colliding with existing 9123 server)
- **Manual test:** open http://localhost:9124/raymarch3d/ — must render the asset, no console errors.

If `tsc` fails, fix the type errors before committing the phase.
If `vite` errors at module resolution, check `node_modules` symlink is intact.

---

## Phases

### Phase B — WebGPU pipeline + main.ts
**Status:** COMPLETE

**Deliverable:** Running POC at `/raymarch3d/` rendering ONE asset (sword).
The shader, primitive list, palette upload to GPU; fullscreen draw produces
the rendered SDF. Camera fixed at a flattering angle; static (no orbit yet).

**Files to create:**
- `raymarch3d/pipeline.ts` — exports `createRaymarchPipeline(device, format)`
  that builds the render pipeline + bind group layout from `raymarch.wgsl`.
- `raymarch3d/main.ts` — bootstrap: request adapter/device, configure canvas,
  create uniform/storage buffers (uniform: camera + counts; storage: primitives
  + palette), upload `knightLongsword()` asset, run a render-loop tick
  (`requestAnimationFrame`) that just redraws (static for now).

**Steps:**
1. In `pipeline.ts`: import `raymarch.wgsl` as a string (`?raw` Vite suffix).
   Build pipeline with vertex+fragment from the shader, single-target color
   format, no depth, triangle-list. Bind group layout: 0=uniform, 1=storage
   (read), 2=storage (read).
2. In `main.ts`:
   - `navigator.gpu.requestAdapter()` → `requestDevice()` (handle missing GPU).
   - Get canvas, configure context with `device`, format `'bgra8unorm'`.
   - Create primitives buffer from `packPrimitives(knightLongsword())`,
     palette buffer from `packPalette()`, uniform buffer (size 256 bytes).
   - Build a fixed camera: position `[0, 0.0, 1.5]`, dir `[0, 0, -1]`,
     right `[1, 0, 0]`, up `[0, 1, 0]`, orthoExtent `[0.6, 0.6]`.
   - Render-loop: write uniforms (incl. time), encode pass, draw 3 vertices.
3. Print status to `#status` div on success/failure.
4. Add a button row that lists `Object.keys(ASSETS)` and lets the user
   click to switch — clicking re-uploads the primitives buffer + redraws.

**Acceptance:**
- `npx tsc --noEmit` passes.
- `npx vite --port 9124` then `curl -s http://localhost:9124/raymarch3d/ -o /dev/null -w "%{http_code}"` returns 200.
- A separate manual browser test would show the sword. Since this loop
  runs headless, a final **commit** confirms the build is good even without
  visual verification.

**Commit subject:** `iso_cache_poc: phase B — WebGPU pipeline rendering 1st 3D-SDF asset`

---

### Phase C — Asset switcher + camera orbit
**Status:** COMPLETE

**Deliverable:** UI to switch between the 5 asset definitions in `assets.ts`,
plus a slow auto-orbit camera so the SDFs read as 3D (silhouette alone is
ambiguous; orbit shows depth).

**Files to modify:**
- `raymarch3d/main.ts` — render-loop updates camera quaternion each frame
  (orbit around Y at e.g. 0.3 rad/s); `#asset-buttons` row populated from
  `ASSETS`; click rebuilds the primitives buffer and re-uploads.

**Acceptance:** `tsc` clean; commit.

**Commit subject:** `iso_cache_poc: phase C — asset switcher + orbiting camera`

---

### Phase D — JSON loader for sdf_modeling_research/primitives/PRESETS
**Status:** COMPLETE

**Deliverable:** Load 1-2 PRESET JSON files (start with `chest.wood_iron_banded.json`
or a scene like `examples/scenes/sword_on_anvil.json`) and convert them to
`GPUPrim[]` for rendering. Skip features the POC doesn't need (anchors,
attachment modes); fall back to absolute positioning.

**Files to create:**
- `raymarch3d/loader.ts` — exports `loadPresetJSON(url)` → Promise<GPUPrim[]>.
  Parser dispatches on `type` field: `shape:rounded_box` → roundedBox primitive,
  `shape:sphere` → sphere primitive, etc. Maps `material` → palette slot.
  Supports `translate` field. Logs unknowns to console.warn but doesn't throw.

**Files to modify:**
- `raymarch3d/main.ts` — add JSON loader entries to the asset switcher.
  When the user clicks a JSON-backed asset, fetch + parse + convert + upload.
- `raymarch3d/assets.ts` — re-export `loadPresetJSON` for convenience.

**Acceptance:** `tsc` clean; visiting the page shows the JSON-backed assets in
the switcher; commit.

**Commit subject:** `iso_cache_poc: phase D — JSON preset loader for SDF assets`

---

### Phase E — Two-canvas integration: 3D SDFs alongside the 2D demo
**Status:** COMPLETE

**Deliverable:** On `object_buffer_cache.html` (the existing 2D demo), add a
second small WebGPU canvas in the layout that shows the 3D-SDF demo running
in parallel. No data-flow integration yet — just visual side-by-side so
the morning reviewer can see both styles together.

**Files to modify:**
- `object_buffer_cache.html` — add a second `<canvas id="canvas3d">` panel
  next to the main 2D canvas; load `raymarch3d/main.ts` as a module; mount
  it on that canvas (main.ts needs a `mountOn(canvas)` export).

**Files to modify in raymarch3d/:**
- `main.ts` — refactor entry point so it can target an arbitrary canvas
  passed in from outside.

**Acceptance:** `tsc` clean; commit.

**Commit subject:** `iso_cache_poc: phase E — 3D-SDF panel layered into 2D demo`

---

### Phase F — Documentation
**Status:** PENDING

**Deliverable:** Update `iso_cache_poc/README.md` to document the new
`raymarch3d/` POC alongside the existing 2D demo. Diagram the architecture:
2D destruction (Canvas2D) ↔ 3D SDF (WebGPU). Note that the engine code
(`engine/src/character3d/`) was the read-only reference and was not modified.

**Files to modify:**
- `iso_cache_poc/README.md` — add a §raymarch3d section.

**Files to create:**
- `iso_cache_poc/raymarch3d/README.md` — quick-start (`npm run dev`),
  architecture diagram, asset list, future-work TODO.

**Acceptance:** No code changes; commit doc-only.

**Commit subject:** `iso_cache_poc: phase F — docs for raymarch3d POC`

---

### Phase G (stretch) — Bake 3D SDF output into a 2D archetype buffer
**Status:** PENDING

**Deliverable:** Write a function that, given a `GPUPrim[]` asset, runs a
one-time WebGPU bake to a fixed-size offscreen texture, reads back the
pixels, and produces an RGBA `ImageData`-compatible buffer suitable for
use as an iso pixel-cache archetype's `colorBuf`. Wire it up so the 2D
demo can spawn a "rock_3d" archetype that's actually rendered by the
WebGPU raymarcher and then participates in the destruction/particle
system as a normal archetype.

**Files to create:**
- `raymarch3d/bake_to_buffer.ts` — exports `bakeAssetToImageData(prims, size)`
  that returns a Uint8ClampedArray of RGBA pixels.

**Files to modify:**
- `object_buffer_cache.html` — add a new archetype using a 3D-baked buffer.

**Acceptance:** A new "rock_3d" archetype is visible in the 2D demo, can
be shift-clicked to destroy normally; commit.

**Commit subject:** `iso_cache_poc: phase G — 3D-SDF → 2D archetype bake bridge`

---

## Failure modes / contingencies

- **`tsc` errors due to missing types:** `npm install --save-dev @webgpu/types`
  inside `iso_cache_poc/`; the symlink to engine's `node_modules` should
  already cover this, but if not, install locally.
- **WebGPU not available at runtime:** add a graceful `if (!navigator.gpu)
  { status.textContent = 'WebGPU not available in this browser' }` early
  return. Headless test envs may lack WebGPU; that's OK — the page should
  load without crashing.
- **JSON loader chokes on unknown features:** log + skip; don't fail.
  The `engine/src/character3d/anatomy.ts` is the reference implementation
  if you need to understand a specific JSON shape better, but copy logic,
  don't depend on it.
- **A phase blocks for >1 loop iteration:** mark `BLOCKED — <reason>`,
  proceed to the next `PENDING` phase. Don't infinite-loop on the same
  unsolvable thing.

---

## Status tracker (updated by each loop iteration)

| Phase | Status |
|------:|:-------|
| A     | COMPLETE — TS port of sdf.ts done, files in raymarch3d/ |
| B     | COMPLETE — pipeline.ts + main.ts; tsc clean; vite serves /raymarch3d/ 200 |
| C     | COMPLETE — Y-axis orbit @ 0.3 rad/s, 0.35 rad elevation; switcher landed in B |
| D     | COMPLETE — loader.ts handles shape:* parts; 2 scene JSONs copied + wired into switcher |
| E     | COMPLETE — main.ts exports mountOn(); object_buffer_cache.html hosts a 3D panel below the 2D demo |
| F     | PENDING |
| G     | PENDING (stretch) |

When all phases reach COMPLETE or BLOCKED, the loop should stop firing
and the task is done. The loop owner can review the commits in the
morning.
