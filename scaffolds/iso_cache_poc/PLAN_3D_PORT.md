# PLAN_3D_PORT.md — Port 3D-SDF raymarching INTO the existing 2D demo

This is the corrected plan. The previous OVERNIGHT_PLAN.md built a
separate TS+WebGPU project alongside; that's not what was asked. **This
plan keeps the 2D demo (`object_buffer_cache.html`) exactly as-is at the
architecture level — same Canvas2D, same destruction, same particles,
same Voronoi shatter, same falling-sand reactions — and only swaps each
archetype's SDF evaluation from 2D to 3D-raymarched.**

The only visible change: shapes look like rounded 3D forms shaded by a
light source, not flat 2D silhouettes. Nothing else.

## How each `/loop` fire executes

1. Read this file top-to-bottom.
2. Find the first phase whose **Status** is `PENDING`.
3. Execute its **Deliverable** following its **Steps**.
4. Verify its **Acceptance**.
5. Update the **Status** to `COMPLETE` (or `BLOCKED — reason`).
6. Commit with the phase number in the subject.
7. End the turn — the cron interval handles re-firing.

If a phase blocks, mark it `BLOCKED` and proceed to the next `PENDING` phase.

## Hard constraints

- **No build step.** The demo stays plain JS in `<script type="module">`
  inside `object_buffer_cache.html`. Plain `python3 -m http.server` must
  continue to work.
- **No WebGPU.** CPU raymarching only.
- **Don't touch** `engine/src/character3d/` or `engine/demos/skeleton_*` —
  read-only references; copy/rewrite into iso_cache_poc as needed.
- **Don't break the existing demo.** Each phase must leave a working
  page where you can shift-click to destroy, watch particles fall, etc.
- **Additive over destructive.** Add a `sdfFn3d` field on GameObject; if
  set, bake uses the 3D path. If not, bake uses the existing 2D
  `sdfFn(lx, ly, phase)`. Convert archetypes one at a time so a broken
  3D SDF doesn't break the whole demo.

## Verify command

`python3 -m http.server 9123` from `iso_cache_poc/`, then visit
`http://localhost:9123/object_buffer_cache.html`. Hard-refresh between
phases to clear cache. The page must:
- Load (no JS errors in console).
- Render the world (terrain, all archetypes visible).
- Accept shift-click for destruction (particles fly, deposits settle).

For each phase, after editing, the verification can be:
- `node --check object_buffer_cache.html` won't work (HTML, not JS) but
  `node --check raymarch3d_cpu.js` (or wherever new JS lives) will.
- Or: pull out the inline script via grep + node syntax check on the
  extracted JS.

## Phases

### Phase 1 — JS 3D-SDF library (CPU)
**Status:** COMPLETE

**Deliverable:** A new `raymarch3d_cpu.js` ES module exporting 3D SDF
primitives (sphere, box, roundedBox, ellipsoid, cylinder, capsule, torus,
cone), compose ops (union, smoothUnion, intersect, subtract,
smoothSubtract), transforms (translate, scale, rotateX/Y/Z, mirrorX), and
helpers (gradient, normalize). All inline math, no deps.

This is a fresh JS port of `engine/src/character3d/sdf.ts` (READ-ONLY) —
the existing `raymarch3d/sdf3d.ts` is a TS sibling; we make a parallel
JS one for the no-build demo to consume.

**Files:** create `iso_cache_poc/raymarch3d_cpu.js`.

**Acceptance:** `node --check iso_cache_poc/raymarch3d_cpu.js` exits 0.

**Commit subject:** `iso_cache_poc: 3D port phase 1 — JS 3D-SDF library`

### Phase 2 — Raymarcher + shading
**Status:** COMPLETE

**Deliverable:** Same JS module gains:
- `raymarchPixel(sdfFn, worldX, worldY, opts)` → `{hit, p, normal}`.
  Orthographic camera, ray fired down -Z, March until SDF < eps or
  exit world. opts: `startZ`, `endZ`, `maxSteps`, `eps`.
- `shadeHit(normal, baseColor, lightDir?)` → `[r, g, b]` (0-255 each).
  Lambert + ambient + soft rim.

**Files:** add to `raymarch3d_cpu.js`.

**Acceptance:** `node --check` clean; export list inspectable via
`node -e "import('./raymarch3d_cpu.js').then(m => console.log(Object.keys(m)))"`.

**Commit subject:** `iso_cache_poc: 3D port phase 2 — CPU raymarcher + shader`

### Phase 3 — `sdfFn3d` route in GameObject.bake
**Status:** COMPLETE

**Deliverable:** Modify `object_buffer_cache.html` so:
- `GameObject` accepts `opts.sdfFn3d` (a 3D SDF: Vec3 → number) and
  `opts.metersPerPixel` (scale).
- `_bakeInto` checks: if `this.sdfFn3d`, raymarch each pixel; else use
  the existing 2D `sdfFn` path. Preserves all current behavior for
  archetypes that don't opt in.
- The 3D path writes color via `shadeHit(normal, this.color)`, depth
  buf via `hit.p[2]`, normal buf via packed normal.

**Files:** modify `object_buffer_cache.html` (inline script).

**Acceptance:** Page loads, all existing 2D archetypes render unchanged.

**Commit subject:** `iso_cache_poc: 3D port phase 3 — sdfFn3d path in GameObject.bake`

### Phase 4 — Convert ROCK to 3D
**Status:** COMPLETE

**Deliverable:** Replace `sdfRock` with a 3D SDF (smoothUnion of a box
and a displaced sphere; same shape concept). Wire the rock archetype
to use `sdfFn3d` instead of `sdfFn`. Verify destruction (shift-click on
rock) spawns Voronoi chunks that fly out correctly.

**Files:** modify `object_buffer_cache.html` (rock SDF + archetype).

**Acceptance:** Rock visible as a 3D-shaded shape; shift-click on it
spawns chunks; the existing 2D archetypes (heart, gear, etc.) still
render normally.

**Commit subject:** `iso_cache_poc: 3D port phase 4 — rock archetype is 3D`

### Phase 5 — Convert HEART to 3D
**Status:** COMPLETE

**Deliverable:** Heart = smoothUnion of two spheres + cone for the
bottom point. animPhase scales the whole shape (pulse). Wire the heart
archetype to `sdfFn3d`. The existing per-tick re-bake logic still
fires (heart is `animating` with `loopFrames: 6`).

**Files:** modify `object_buffer_cache.html`.

**Acceptance:** Heart pulses with 3D shading; destruction works.

**Commit subject:** `iso_cache_poc: 3D port phase 5 — heart archetype is 3D`

### Phase 6 — Convert GEAR to 3D
**Status:** COMPLETE

**Deliverable:** Gear = cylinder hub + 12 small cylinders arrayed
around for teeth (or a torus with notches). It's `rotate` flag, baked
once, with `ctx.rotate` doing the spin → no per-tick re-bake to worry
about.

**Files:** modify `object_buffer_cache.html`.

**Acceptance:** Gear visible as a 3D shape with teeth; rotation still
snaps every tick; destruction works.

**Commit subject:** `iso_cache_poc: 3D port phase 6 — gear archetype is 3D`

### Phase 7 — Convert FAN to 3D
**Status:** COMPLETE

**Deliverable:** Fan = cylinder hub + 4 boxes for blades, rotated 90°
each. Like the gear it's `rotate` so it bakes once.

**Files:** modify `object_buffer_cache.html`.

**Acceptance:** Fan visible as 3D blades; rotation works; destruction works.

**Commit subject:** `iso_cache_poc: 3D port phase 7 — fan archetype is 3D`

### Phase 8 — Convert CRITTER (walking robot) to 3D
**Status:** COMPLETE

**Deliverable:** Walker = sphere head + capsule body + 2 capsule arms
+ 2 capsule legs. Limbs swing with `animPhase`. The critter is
`animating` so it re-bakes per tick — heavy. Acceptable lag is OK for
POC; can downscale buffer if needed.

**Files:** modify `object_buffer_cache.html`.

**Acceptance:** Critter walks with 3D shading; destruction works.

**Commit subject:** `iso_cache_poc: 3D port phase 8 — critter archetype is 3D`

### Phase 9 — Convert VOLCANO (large BG)
**Status:** PENDING

**Deliverable:** Volcano = cone + animated sphere lava plume on top.
animPhase modulates the plume. Volcano is `animating` with
`loopFrames: 3` (slow). Buffer is huge (400×300) — re-bake budget
matters; may need to reduce `maxSteps` for volcano.

**Files:** modify `object_buffer_cache.html`.

**Acceptance:** Volcano renders 3D-shaded; destruction works.

**Commit subject:** `iso_cache_poc: 3D port phase 9 — volcano archetype is 3D`

### Phase 10 — Convert TERRAIN to 3D (heightfield)
**Status:** PENDING

**Deliverable:** Terrain = max(plane(y - hillHeight(x)), -ponds, -craters).
Treat it as a thick heightmap with depth in Z. The 3D path produces
proper rounded hill silhouettes. This is the largest archetype
(2000×500 = 1M pixels) — it's `static`, baked once at init, so the
slow CPU raymarch is amortized.

**Files:** modify `object_buffer_cache.html`. Keep `hillHeight()` for
collision/topY (as before).

**Acceptance:** Terrain renders 3D; the robot still walks on its
surface; destruction (craters) works.

**Commit subject:** `iso_cache_poc: 3D port phase 10 — terrain archetype is 3D`

### Phase 11 — Add iso camera tilt
**Status:** PENDING

**Deliverable:** Replace the straight-down ortho camera with an iso
tilt (~26.57° elevation, dimetric 2:1). Each pixel's ray direction is
not (0,0,-1) but a tilted direction, giving the classic 2.5D iso look
where you see top + sides of a shape.

**Files:** modify `raymarch3d_cpu.js` and any per-archetype
`metersPerPixel` to compensate for the tilt.

**Acceptance:** Shapes show top + sides (no longer straight side-view);
all archetypes still render and destruction still works.

**Commit subject:** `iso_cache_poc: 3D port phase 11 — iso camera tilt`

### Phase 12 — Documentation
**Status:** PENDING

**Deliverable:** Update `iso_cache_poc/README.md` to explain the 3D
port, link to PLAN_3D_PORT.md, and note that the previous TS+WebGPU
POC under `raymarch3d/` is a parallel reference (not the canonical
demo). Brief note on perf characteristics (per-archetype CPU bake cost).

**Files:** modify `README.md`.

**Acceptance:** Doc-only; commit.

**Commit subject:** `iso_cache_poc: 3D port phase 12 — docs`

## Status tracker

| Phase | Status |
|------:|:-------|
| 1     | COMPLETE — raymarch3d_cpu.js with primitives + compose + transforms; node --check clean |
| 2     | COMPLETE — raymarchPixel + shadeHit; smoke test (sphere hit + shade) passes |
| 3     | COMPLETE — `sdfFn3d`/`metersPerPixel` on GameObject; `_bakeInto` raymarches when set; existing 2D archetypes untouched |
| 4     | COMPLETE — rock archetype uses sdfFn3d=smoothUnion(box, sphere) with mPP=0.01; smoke test confirms hits + normals |
| 5     | COMPLETE — heart uses sdfFn3dFactory (per-tick rebuild) = 2 spheres + stretched ellipsoid; cone fallback noted |
| 6     | COMPLETE — gear = disk + 12 teeth boxes + hub bump (union, not smoothUnion); ~22ms/1000 raymarches |
| 7     | COMPLETE — fan = Z-axis hub cylinder + 4 box blades at 0/90/180/270°; smoke test 6/8 expected |
| 8     | COMPLETE — walker = sphere head + capsule body + 2 capsule legs + 2 capsule arms; limbs swing per phase via factory |
| 9     | PENDING |
| 10    | PENDING |
| 11    | PENDING |
| 12    | PENDING |

When all phases reach COMPLETE or BLOCKED the loop should stop firing.

## Failure modes

- **Per-tick re-bake too slow on animating archetypes** (heart, critter,
  volcano): drop the `loopFrames` to a slower value (e.g. heart 6 → 3),
  reduce `maxSteps` from 48 → 24, or downscale the buffer (e.g. heart
  80×80 → 56×56).
- **Destruction looks weird on 3D-shaded buffers**: the destruction
  pulls pixel colors from `colorBuf` directly so 3D-shaded pixels
  become 3D-shaded particles — that's a feature, not a bug.
- **Voronoi shatter clips weirdly with 3D shading**: shouldn't happen,
  but if so reduce chunk count per blast.

## Background: the previous misdirection

Before this plan, an OVERNIGHT_PLAN.md was executed that built a
separate TS+Vite+WebGPU POC under `raymarch3d/`. That work is preserved
as a reference (it's not in the way of this plan), but it's not what
was asked. This plan keeps everything inside `object_buffer_cache.html`
in plain JS, and only swaps the SDF eval path.
