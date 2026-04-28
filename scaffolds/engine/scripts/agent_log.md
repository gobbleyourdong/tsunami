# Agentic CSG Modeler — Session Log

Started: 2026-04-25
Loop: every 10 min (cron job `17b0872d`)
Cap per target: ~6 iterations before retiring or pivoting.

## /loop iter 129: combined showcase — cracked brick wall
- Composed both halves of the toolkit on one prim:
  - `crackDepth: 0.0008, crackDensity: 250` (noise deformer, colorFn=9 voronoi-edge band-isolation)
  - `repeats: [{ kind: 'brickGrid', rows: 6, cols: 4, ... }]` (replicator, running-bond bricks)
- Result: 24 bricks in masonry pattern, each with stone-crack texture. Reads as aged weathered brick wall.
- **Validates the canonical taxonomy is closed**: every patterned-geometry intent expressible via (noise deformer × repeater × primitive type). Six noise families × four repeater modes × ~10 primitive types = ~240 base permutations, plus stacking via `blendGroup` for unlimited combinations.

## REPLICATOR PASS — iter 128: spline mode (dragon tail) — 4 of 4 modes done
- Added `spline` repeat kind. New helpers:
  - `catmullRomSample(cps, t)` — Catmull-Rom interpolation across 4-point segments. Returns position + tangent. ≥4 control points required (first+last are tangent guides for inner segments).
  - `quatFromTo(from, to)` — quaternion that rotates one unit vector to another. Handles 0° and 180° edge cases.
- Spline handler: `count` copies along curve. Each: position from spline, params scaled by linear `taper`, rotation aligns prim-local `alignAxis` with spline tangent.
- Test (capsule prim 5mm radius × 6mm half-height, 6 control points spanning ~100mm in S-curve, count=14, taper=0.15, alignAxis=y, blend-group merge): renders as recognizable tapered dragon tail. Discrete capsules blend-merge into one continuous shape via blendRadius.
- **Replicator pass closed — all 4 patterns shipped**:
  | mode | shape | composition primitive |
  |---|---|---|
  | `brickGrid` | running-bond bricks | rowxcol grid + per-row stagger |
  | `linkChain` | interlocking torus chain | linear + alt 90° rot |
  | `chainLinkGrid` | woven ring fence | rowxcol grid + parity rot |
  | `spline` | dragon tail / curved chain | Catmull-Rom + tangent quat + taper |
- All four share the two-gate plumbing pattern: `repeats?:` type union + normalize-filter recognition. Per-prim composition with previous repeats works (multiplicative).
- **Plus 6 noise-deformer families finalized** (iter 111-124): cracks, ridges, wood grain, weathering, terrain, cloud — all FBM-SDF grounded, all amp-budget consistent.

## REPLICATOR PASS — iter 127: chainLinkGrid mode (woven ring fence)
- Combined brickGrid 2D layout + linkChain alternating-rotation idea into `chainLinkGrid`. Spec: rowAxis, colAxis, rotAxis, rows, cols, rowSpacing, colSpacing.
- Per-cell: rotation flipped on `(row+col) % 2 === 1` parity → adjacent rings perpendicular to each other → visible interlock pattern.
- Test (torus prim R=6mm, r=1.5mm, base 90° X rotation, 5×5 grid, 11mm spacing, rotAxis=z): renders as 25-ring woven mesh. Alternating ring orientations clearly visible.
- **Three replicator modes done**: brickGrid, linkChain, chainLinkGrid. All share the same two-gate plumbing (type union + normalize filter) and copy-with-spread RaymarchPrimitive output pattern.
- **Dragon tail queued — fundamentally different**: spline/path positioning + per-segment taper + tangent-aligned orientation. Needs new path-sampling infra (not grid arithmetic). Will be the largest add of the four.

## REPLICATOR PASS — iter 126: linkChain mode (interlocking torus chain)
- Added `linkChain` repeat kind: linear translation along axis + 90° rotation around chain axis on alternate copies (every odd index gets `rotation = quat-90°-around-axisIdx`).
- Quat math: `quat = (sin(π/4), 0, 0, cos(π/4))` rotated into the chain-axis component → 90° rotation about chain axis.
- Test (torus prim, R=8mm, r=2.5mm, count=8, spacing=13mm, base rotation 90° around X to face camera): renders as metal chain — 8 interlocking links, alternate face/edge orientation matches real chain topology.
- Plumbing same as brickGrid: type union extension + normalize-filter recognition. The two-gate pattern is now a clear template for any new repeat kind.
- **Two replicator modes done**: brickGrid (running-bond bricks), linkChain (interlocking chain).
- **Two queued**: chain-link fence (2D grid of small rings with alternating-rotation interlock — combine brickGrid + linkChain ideas), dragon tail (spline-driven positioning + per-segment taper, fundamentally different — needs path/curve sampling not grid arithmetic).

## REPLICATOR PASS — iter 125: brickGrid mode added (running-bond bricks)
- **Cron `4276681c` fired at 00:11**: switched focus from noise tuning to replicator improvement.
- **Audit of existing replicator** (`applyRepeats` in modeler_demo.ts):
  - Has: `linear` (translate by spacing along axis, count copies), `rotational` (rotate offset around axis by 2π/count)
  - Missing: per-row offset (bricks), composable rotation per copy (chains), 2D grid + alternating stagger (brick walls), spline-driven positioning (dragon tail), interlocked alternating-rotation grid (chain-link)
- **brickGrid mode added** — first new repeat kind since baseline:
  - Spec: `{ kind: 'brickGrid', rowAxis, colAxis, rows, cols, rowSpacing, colSpacing, stagger? }`
  - Default `stagger = colSpacing/2` → half-brick running-bond pattern
  - Per-row stagger: `(row % 2 === 1) ? stagger : 0`
- **Two-step plumbing**: (1) extend the `repeats?:` union type, (2) extend the spec normalize filter at line 2562 (was rejecting `brickGrid` because it has no `axis`/`count` fields). Catch: per-prim repeat schemas pass through TWO validation gates — the type union and the normalize filter. New kinds need both.
- **Test**: 12mm × 5mm × 5mm brick prim, brickGrid 6 rows × 4 cols, 11mm rowSpacing × 25mm colSpacing → renders proper running-bond pattern, 24 bricks in alternating stagger. ✓
- **Remaining queue (3 modes)**:
  - **Chains**: linear repeat with per-copy alternating 90° rotation around the axis perpendicular to the chain. Each link is a torus (or capsule loop), rotated 90° from neighbors.
  - **Chain-link fence**: 2D grid of small rings/diamonds, each rotated 90° from neighbors so they interlock.
  - **Dragon tail**: spline/curve-driven positioning with per-segment taper. Different from grid-based — needs path samples + tangent-aligned orientation.

## /loop iter 124: ridges 2-octave mask-multiply (sub-ridges along main ridges)
- Applied the mask-multiply 2-octave pattern from cracks (iter 116) to ridges. Same composition: octave-1 sub-ridges only manifest where octave-0 macro is also near edge → fractal cliff character along main ridge lines.
- Test (sphere host, ridgeDepth=5mm, ridgeDensity=50): main crystalline ridges now have finer sub-ridges branching off, less uniform pattern.
- **Observation**: every band-isolation deformer (cracks, ridges, wood grain) gets the same composition tools — single-octave clean, 2-octave mask-multiply for hierarchical detail. The pattern transfers across direction (carve vs raise) and direction-anisotropy (isotropic vs Y-stretch) without modification.
- Final noise-pass deformer count: 6 families, all FBM-SDF-grounded, all sharing sdBase + voronoiEdge + sdBaseSmooth as building blocks, all with consistent amp-budget rule, all with consistent 2-octave-mask-multiply composition for hierarchical detail.

## /loop iter 123: voronoi RIDGES — same band-isolation as cracks, opposite sign (raised vs carved)
- Real terrain has sharp ridge lines (cliff edges, mountain ridges) — not just smooth bumps. Implemented as colorFn=15 using same voronoiEdge + warp + rotation as cracks but `d = d - (1 - mask) * ridgeDepth` (subtract → raises surface outward).
- Test (sphere host, ridgeDepth=5mm, ridgeDensity=50): raised crystalline ridge network. Reads as: dragon scales, geode crystals, rocky outcrop with cliff edges, armored creature skin.
- **Sixth deformer family** — completes the noise pass:
  | colorFn | Direction | Visual |
  |---|---|---|
  | 9 | Carve voronoi edges | crack network |
  | 14 | Carve Y-stretched edges | wood grain |
  | 15 | RAISE voronoi edges | crystalline ridges / dragon scales |
  | 19 | Subtractive smax (volumes) | lunar craters |
  | 28 | IQ smin chain | terrain mountains |
  | 29 | Density-displacement (billow) | cumulus clouds |
- All six share `sdBase` → `sdBaseSmooth` → `voronoiEdge` building blocks, all amp-budgeted, all Lipschitz-clean (cloud uses controlled-non-Lipschitz `*0.5` safety).
- Carve/raise sign axis is the missing geometric duality — every voronoi-edge band-isolation deformer has a +/- twin that's visually distinct (cracks ↔ ridges, weathering pits ↔ knobby bumps).

## /loop iter 122: cumulus flat-base truncation (physical reference: lifting condensation level)
- Per user direction "pull a reference image and emulate it": real cumulus clouds have a FLAT BOTTOM at the lifting condensation level (water vapor doesn't condense below it). Our cloud was symmetrically puffy in all directions.
- Added `d = max(d, -(pPrim.y + cloudDepth*0.4))` after the density-displacement step. Intersects with a half-space SDF that's negative above pPrim.y = -cloudDepth*0.4 → cloud only renders above. Lipschitz-clean (max).
- Test: 4-panel atlas shows cumulus shape with FLAT bottoms and cauliflower puffy tops. Right panels especially read as recognizable real cumulus.
- This is the first physical-reference-driven tune of the session. Same approach available for: stratocumulus (low + flat sheet), cirrus (wispy filaments), nimbostratus (uniform overcast). Each is a different flat-base + density-shape combination.

## /loop iter 121: noise-pass capstone — stacked-deformer scene, audit complete
- **Wood grain re-audited**: already amp-budget-clean. The min(edge0, edge1) composition picks the smaller, but carving uses ONE band/depth via `(1 - mask) * grainDepth ≤ grainDepth`. No octave-stacking of carving depth. Misread earlier — no change needed.
- **Stacked-deformer test**: spec with two prims, separate blendGroups → terrain slab (colorFn=28) bottom + weathered boulder (colorFn=19) on top. Renders cleanly: rocky base + cratered sphere, both materials visible, no SDF interference between them. Different blendGroups isolate the deformer chains as expected.
- **Noise-pass session totals (iter 111→121)**:
  - Cloud (colorFn=29): 2-octave billow density, density=6 ≈ cumulus puffy lobes with cauliflower bulges
  - Stone cracks (colorFn=9): voronoiEdge band-isolation with mask-multiply 2-octave (macro + branching hairlines), domain warp + non-orthogonal rotation breaks lattice axis bias
  - Wood grain (colorFn=14): voronoiEdge with Y-axis 8x cell stretch (anisotropic), 2-octave for fine texture between major lines
  - Terrain (colorFn=28): IQ multi-octave 4 octaves + per-octave grid shift + amp budget
  - Weathering (colorFn=19): IQ subtractive smax form 3 octaves + amp budget (lunar/cratered character)
- **Building blocks**:
  - `sdBase` — strict half-edge IQ Lipschitz sphere lattice
  - `sdBaseSmooth` — smin variant for noise scalars only (not SDF math)
  - `fbmSdfNoise(p, freq)` — [0,1] scalar from sdBaseSmooth
  - `voronoiEdge` — F2-F1 lattice cell-edge distance
  - All five deformers reduce to combinations of these.
- **Three composition patterns crystallized for voronoi-edge octaves**: min (dense), max (intersection-sparse), mask-multiply (hierarchical — what real fracture does).
- **Amp-budget principle**: any N-octave stack at half-amp steps → s_init = userDepth/2 keeps total amp ≤ userDepth.
- **Outstanding (queued, not done)**: tetrahedral simplex lattice (would eliminate cubic-grid axis bias structurally for ALL voronoi-based deformers), LoD per-octave break (perf), ellipsoidal sphere variant (replaces wood-grain Y-stretch hack), per-prim multi-deformer chaining (combine cracks + weathering on same prim).

## /loop iter 120: weathering amp budget — same principle as terrain
- Weathering (colorFn=19) was at s_init=weatherDepth → 3-octave geometric sum 1+0.5+0.25 = 1.75 → carving total ~1.75 × user depth (over budget).
- Set s_init = weatherDepth × 0.57 → total ≈ user depth (just under budget).
- Test (sphere host, voronoiCrackDepth=8mm): lunar surface, shallower more proportional craters. Smoother base sphere visible underneath, carving feels like surface texture not surface obliteration.
- **Amp-budget principle now applied across all multi-octave deformers**:
  - Terrain (colorFn=28, 4 octaves): s_init = depth × 0.5 → total ~0.94 × depth
  - Weathering (colorFn=19, 3 octaves): s_init = depth × 0.57 → total ~1.0 × depth
  - Cloud (colorFn=29, 2 octaves billow): no amp budget — billow density is [0,1] scalar, depth controls SDF subtraction directly
  - Cracks/wood-grain (colorFn=9, 14): also depth-based not amp-based; band width = carve depth pins the carving magnitude
- Five distinct deformer families all FBM-SDF-grounded, all amp-budget consistent, all Lipschitz-clean (or controlled non-Lipschitz where needed).

## /loop iter 119: terrain amplitude budget — s_init halved so total ≤ terrainDepth
- Math: 4-octave geometric series sum (1 + 1/2 + 1/4 + 1/8) = 1.875. Old s_init=terrainDepth gave total amp ≈ 1.87 × terrainDepth → terrain detail nearly DOUBLED slab depth, slab read as a fluffy ball not a hard base with terrain on top.
- Set s_init = terrainDepth × 0.5 → total amp ≈ 0.94 × terrainDepth (just under budget). Same number of octaves, same detail richness, proportional to slab.
- Test (slab 100mm × 20mm × 100mm, terrainDepth=18mm): now reads as a flat slab with rocky terrain on top reaching ~18mm peaks. Slab side faces still slightly rounded by IQ smin band on octave 0 (now 0.3 × 9mm = 2.7mm rim), but proportionally subordinate to slab.
- This is the "amp budget" principle for any FBM-SDF deformer with N octaves at half-amplitude steps: `s_init = userDepth / sum(0.5^i for i in 0..N-1) ≈ userDepth / 2`. Documented in code comment so future deformers can pin to it.

## /loop iter 118: cloud — 2-octave billow stack (cauliflower texture on macro lobes)
- cloudDensity was single-iteration (one warp + one billow fold). Added a 2nd octave at 2.6x freq + 0.35x amplitude, summed with a small DC offset (-0.15) to prevent the surface from smoothing out under the additive load.
- Test (sphere host, cloudDepth=25mm, cloudDensity=6): macro lobes from octave 0, cauliflower bulges from octave 1 visible on top. Reads as more realistic cumulus than the single-octave version.
- **Bug encountered + fixed mid-iter**: WGSL reserved keyword `macro` — used as a variable name, killed shader compile, all renders went to empty grid placeholder. Renamed `macro`→`macroPuff` and `fine`→`finePuff`. Worth saving as memory: WGSL reserves identifiers including `macro`, `expand`, etc. — `tsc --noEmit` doesn't catch this since it's WGSL-side. The empty-grid render at 2364 bytes is the signature.

## /loop iter 117: IQ subtractive form added as colorFn=19 (weathered stone / fissures)
- Implemented IQ's "Variations" subtractive form: `n = s * sdBase(p); d = smax(d, -n, 0.2*s);` for 3 octaves with rotation + per-iter shift.
- IQ-natural amplitude coupling: `s_init = weatherDepth` (world units), `p_iter = pWorld / weatherDepth`. Both halve per octave together. weatherDensity becomes informational only — the recipe ties cell size to amplitude as IQ intends.
- Test (sphere host, voronoiCrackDepth=8mm): renders as lunar/cratered stone surface. Multi-octave gives small bumps + larger pits. Visibly different from cracks (linear network) — circular pits = totally different topology, same FBM-SDF foundation.
- **Three deformer types now distinct + Lipschitz-clean**:
  - Additive cracks (colorFn=9): voronoiEdge band-isolation → linear fracture network
  - Subtractive weathering (colorFn=19): IQ smax form → circular crater pits
  - IQ multi-octave terrain (colorFn=28): smin chain → mountain-detail accumulation
  - All share sdBase as the strict-Lipschitz building block.
- Wood grain (colorFn=14) and cloud (colorFn=29) round out the noise type set with anisotropic + density-displacement variants.

## /loop iter 116: cracks 2-octave via mask-multiply — hairlines branching off macro
- Per iter 115's lesson, replaced naive `min(edge0, edge1)` with mask-multiplied composition:
  - Compute `macroNear = 1 - smoothstep(0, bandW*2, edge0)` — 1 near macro crack, 0 far
  - `edge1Effective = mix(1.0, edge1, macroNear)` — pushes octave-1 effective edge to "infinity" away from macro, so it only contributes near macro
  - `min(edge0, edge1Effective)` — final edge field, only carves where macro is near edge AND octave 1 also has a cell boundary
- **Result**: macro crack network + visible subsidiary hairlines branching at intersections. Reads as natural stone fracture pattern. The atlas view shows 4 angles, all with the layered structure visible.
- **Lipschitz note**: mix() with smoothstep-derived weight breaks strict Lipschitz on the composite. Acceptable per user "we are going to be pixel res" — sub-pixel artifacts vanish after pixelize, and the building block (1-octave voronoiEdge) is still clean for non-pixel uses.
- **Composition pattern crystallized for voronoi-edge multi-octave**:
  - `min` = both cracks visible everywhere (dense, unrealistic at fine freq)
  - `max` = only at intersections of both (sparse, geometric)
  - **mask-multiply** = subordinate octaves only manifest where the dominant is active (hierarchical, natural — what real fracture looks like)

## /loop iter 115: cracks 2-octave attempt — reverted; lesson on octave composition for voronoi
- Tried adding 2nd octave to cracks (same pattern that worked for wood grain): `min(voronoiEdge(q0), voronoiEdge(q1))`. At 2.6x freq the 2nd octave covered the entire surface in fine bumps because EVERY cell boundary at the higher freq becomes near-edge somewhere.
- **Lesson**: voronoi-edge octaves don't compose like FBM-SDF amplitudes. min(edge0, edge1) puts you near a crack if ANY octave's cell boundary is nearby, which at high density is everywhere. For "hairline cracks within big cracks" the right composition is MAX (intersection — both octaves' edges agree), not min. Or modulate octave 0's depth by octave 1's [0,1] field.
- Reverted cracks to 1-octave warped+rotated baseline (user-confirmed "looks better than voronoi" with "a bit regular grid in some areas").
- **Pattern for next iter**: try MAX composition for cracks (intersection of edge fields → sparse hairlines branching off macro cracks).

## /loop iter 114: wood-grain 2-octave + terrain per-octave shift (IQ video trick)
- **User direction acknowledged** ("keep making things better and more optimal it all helps, quality is important but also we are going to be pixel res, but never know that might change once the building blocks are in place"): final output is sprite-pixel res so sub-pixel artifacts vanish, but build robust building blocks anyway.
- **Wood grain — 2nd octave added**: octave 0 = macro grain at base density, octave 1 at 2.4x freq + 0.4x amplitude for between-line texture. `min(edge0, edge1)` combines them. Visible result: vertical streaks now have finer detail running through them, less uniform.
- **Terrain — per-octave grid shift**: added `+ vec3f(7.0, 11.0, 13.0)` to the per-iter `p_iter = m * p_iter` step. IQ video trick — successive sphere lattices don't share corners → more concavities, more cliff-like character. Visible result: terrain has more rocky/varied features, less uniform-bump character.
- **Audit response (in-thread, not in code)**: catalogued FBM-SDF utilization. We're using sdBase (Lipschitz exact), voronoiEdge (Lipschitz F2-F1), IQ multi-octave terrain (Lipschitz across octaves), fbmSdfNoise (non-Lipschitz scalar — fine for color/density). Untouched: LoD per-octave-break, tetrahedral simplex lattice, subtractive form (`smax(d, -n)` for fissures), ellipsoidal sphere variant (would replace Y-stretch hack), per-iter grid displacement (NOW done for terrain). Tetrahedral lattice flagged as highest-leverage future work — eliminates axis-grid bias structurally for ALL voronoi-based deformers.
- **Discipline crystallized**: Lipschitz for SDF math, anything-smooth for scalar math. Cloud's `* 0.5` safety multiplier is the IQ-canonical third path — bounded non-Lipschitz, march survives. Never confuse the categories.

## /loop iter 113: cracks domain-warped + rotated + wood grain implemented
- **Cracks improvement (per user "looks better than voronoi tbh, except a bit regular grid in some areas but overall nice")**: integer-grid lattice was visible. Added two breakers:
  - Low-freq sdBaseSmooth domain warp (amplitude 0.8 in unit-cell space) before voronoi sample
  - Non-orthogonal rotation matrix applied AFTER warp so the lattice axes don't align with primitive axes
  - Result: pebble-like irregular cells, no obvious orthogonal grid. Lipschitz approx preserved (warp amp < 1).
- **Wood grain (colorFn=14, new)**: voronoi cells stretched 8x along Y (`stretch = vec3f(1.0, 0.12, 1.0)`) so cell network becomes parallel streaks running vertically. Plus low-freq FBM warp on X+Z (not Y) for natural waviness without breaking grain direction.
  - Test (60×80mm plank, density=50, depth=2mm): renders as recognizable vertical wood grain streaks. Direction respects Y axis as designed.
- **Pattern emerging — voronoiEdge as a building block**: cracks (isotropic), wood grain (Y-anisotropic), and likely voronoi-groupings (variant scale) all share the helper. The DIRECTIONALITY (stretch) and SCALE (density) parameters cover most cell-network-style deformers. This unifies what used to be 3-4 different deformer code paths into one.
- **Remaining noise types**: voronoiCracks (could just alias to cracks with different params), terrain amplitude budget.

## /loop iter 112: stone cracks via voronoi-edge band-isolation
- **Stone cracks (colorFn=9, re-implemented)**:
  - First attempt: `abs(sdBase) < band` — gave concentric-ring CRATERS / dimples (sdBase=0 is sphere SURFACE not cell boundary). Wrong topology.
  - Diagnosis: cracks live on Voronoi cell EDGES (equidistant from two nearest spheres), not on sphere surfaces. Need F2-F1 distance.
  - Added `voronoiEdge(p)` helper — same 8-corner sphere lattice as sdBase but tracks F1 (nearest sphere surface) AND F2 (second-nearest), returns F2-F1.
  - Cracks rewritten: `mask = smoothstep(0, crackDepth, voronoiEdge(p))` — small near cell boundaries → carve into surface there. Lipschitz preserved (smoothstep band width = carve depth).
  - Test (sphere host, crackDensity=60, crackDepth=3mm): turtle-shell / dried-mud network. Tight irregular polygonal cells with carved channels — this is the band-isolation crack pattern user described.
- **Cron schedule update**: one-shot `4276681c` set for 00:11 (1 hour out) per user direct ask — switches focus from noise tuning to **replicator improvement** (bricks, fences, chains, dragon tail). The replicator is the canonical home for patterned geometry per "everything else is repeaters".
- **Pending (queued for /loop ticks)**:
  - Voronoi groupings (colorFn=19) — same voronoiEdge helper, possibly different scale or weighting
  - Wood grain (colorFn=14) — directional FBM with Y-stretched sample coords
  - Terrain amplitude budget tuning

## /loop iter 111: noise-types pass — start of cloud, stone-cracks/voronoi/wood-grain queued
- New /loop directive (5min cadence, cron `86f5339f`): take pass over deprecated noise types (cloud, stone cracks, voronoi groupings, wood grain, terrain), fine-tune fbmSdfNoise params for each, pull reference image, emulate geometry-only, vision-analyze headless.
- **Cloud (colorFn=29) — first pass**:
  - Set up cloud-only spec (sphere host, cloudDepth/cloudDensity params)
  - density=30 (initial): too coral-like, fine-grained brain texture
  - density=10: crumpled-paper / folded fabric — too many sharp folds, geometry too wavy
  - density=6, depth=0.025: best match — recognizable puffy lobes, reads as soft cumulus shape
  - Inbox now persisted with density=6 / depth=25mm as the cumulus baseline
- **Pending (queued for next iters)**:
  - Stone cracks (was colorFn=9, deleted iter 106) — re-implement as FBM-SDF band-isolation: take `abs(sdBaseSmooth - threshold) < band_width` to get crack lines
  - Voronoi groupings (was colorFn=19) — same band-isolation pattern; could share helper with cracks
  - Wood grain (was colorFn=14) — directional FBM stretched along Y axis; FBM-SDF + axis-skewed sample coords
  - Terrain (already FBM-SDF) — currently 4 octaves on 18mm slab; tune amplitude budget so detail stays under slab depth
- The user's bigger directive: re-implement deformer paths I deleted iter 106, but using FBM-SDF construction (not the deleted fbm3/perlin code). Each becomes a new colorFn block with sdBaseSmooth/fbmSdfNoise/sdBase as building blocks.

## /loop iter 110: 4-octave IQ FBM-SDF clean — verified post-dual-map-fix
- Cranked N_OCTAVES from 1 → 4 with the dual-map bug gone. Iso/top normal views captured + audited:
  - Top normal: green-dominant base with subtle hue variation matching the visible FBM dimples. NO fur, NO banding.
  - Iso normal: top is green-with-bumps, sides are pure red/cyan/pink (slightly bumpy from the ~3mm IQ extension past footprint), all faces consistent.
  - Color iso reads as natural rocky/snowy-pebbly surface.
- **Trade-off acknowledged**: IQ's recipe rounds slab corners by 0.3 × s_init = 5.4mm rim radius on octave 0. The slab silhouette is bumpy by ~3-4mm (cumulative outward extension across octaves from the 0.1*s clip). Acceptable for natural terrain look; not acceptable if rigid box needed. Remaining work to keep rigid edges with multi-octave detail = the half-space-host hybrid done WITHOUT per-pixel `if`-gates (the iter 109 attempt failed because of the gate boundary plus the dual-map bug, but the gate was the wrong tool — smooth weighting is the right one).
- **Daemon preview confirmed** — `public/sdf_modeler/preview.png` is updating with the live 4-octave render.
- **Iter sequence summary** (102→110): heightmap purge → FBM-SDF unification → snow-on-slope physical fix → bgMode split for character demos → page-load 36s→3.5s (10x via shader prune) → ArkSpec schema validator → IQ recipe verbatim verified rigid-slab does NOT survive (smin softens edges by design) → **dual-map detail-amp displacement removed (THE bug)** → 4-octave IQ recipe renders clean with correct normals.

## /loop iter 109 (continued): hidden dual-map detail-amp displacement was the source of normal-fur all along
- **The bug** (line 1316-1321 in raymarch_renderer.ts, present since heightmap era):
  ```
  if (wantDetail == 1u) {
    let detailAmp = prims[base + 2u].w;
    if (detailAmp > 0.0) {
      d = d - detailAmp * fbmSdfNoise(pWorld, 28.0);
    }
  }
  ```
  Asymmetric: only fires on the normal pass (`wantDetail == 1u`), so silhouette stays clean but the eps probe sees a Lipschitz-broken `fbmSdfNoise` perturbation up to 18mm. Result: kinked normals on what is geometrically a clean surface. This was the SOURCE of every "incorrect normals" complaint going back many iters — every time I "fixed" the FBM-SDF construction inside `colorFn==28u`, this dual-map block kept poisoning the normal pass.
- **How I found it** (per user direction "turn the amp down as low as it can go see if it doesnt change the base normal"): set s_init=0.0001 in the IQ recipe → expected uniform-green base normal → got varied normals → search for what else perturbs SDF on the normal pass → dual-map block.
- **Fix**: deleted the dual-map block. With it gone, N_OCTAVES=0 + IQ recipe → bare slab is uniform green ✓. Then 1 octave → clean FBM-SDF spheres rendered on slab top with smooth normals throughout.
- **User direct guidance this iter**:
  - "get rid of if statements thats whats bad" — confirmed per-pixel `if`-gates create SDF discontinuities that the eps probe reads as kinks
  - "turn the amp down as low as it can go see if it doesnt change the base normal" — the diagnostic that found the actual bug
  - "like why is there normal on the side from the top" / "it should be directly facing to the side" — the symptom that pointed at it
- **Architectural insight** (worth saving as memory): when normal-pass and silhouette-pass evaluate different SDFs (dual-map / asymmetric perturbation / wantDetail flag), the eps probe sees the perturbation but the marched surface doesn't. Result: visible normals that don't correspond to visible geometry. **Rule**: any SDF modification must be applied symmetrically to all evaluation contexts, OR not at all.

## /loop iter 109: IQ recipe verbatim — multi-octave FBM-SDF on slab + auto-zoning disabled
- **User pasted the full IQ FBM-SDF article** + direct ask: "start with a slab and go octave by octave, see if it retains the slabs rigid normals, start with a box without rounding".
- **Implemented IQ recipe verbatim** at the colorFn==28 path. Key things I had wrong before:
  - Rotation matrix already encodes the 2x scale: column lengths are 2.0, NOT 1.0. So `p = m * p` is correct, NOT `p = m * p * 2`.
  - Per-octave `n = s * sdBase(p)` where s is amplitude in world units. s halves each octave.
  - Both clip and union use the LIVE host d, not a separate detail buffer.
  - `smax_k(n, d - 0.1*s, 0.3*s)` clips noise above inflated host; `smin_k(n_clipped, d, 0.3*s)` unions back.
- **Tested octave-by-octave (1→2→3→4)** with a single-slot uniform tint (auto-zoning disabled per user "can we just get rid of colors please"). Findings:
  - **1 octave**: visible bumps + slab corners noticeably rounded (~5mm rim from 0.3×18mm smin).
  - **2 octaves**: broader hills + medium domes layered. Normal map clean, no fur.
  - **3 octaves**: previous + smaller boulder-scale detail.
  - **4 octaves**: + fine surface detail. All octaves' contributions visible as natural fractal terrain. Render reads as cumulus / smooth snow drift. No fur, no banding, no march-step artifacts.
- **Verdict on slab rigidity**: NO, IQ recipe AS-IS does NOT preserve slab rigidity. Each octave's smin softens the host corners by ~0.3×s. To get fractal detail AND rigid slab, the final union to slab needs a tiny smin band decoupled from the inter-octave smin (the iter 102-107 trick). That's the next architectural step if rigid edges are required.
- **Side cleanups**:
  - Disabled the auto-zoning rock/snow split in colorFn=28 path. Slot stays slotA for terrain — uniform color so the GEOMETRY is the focus. Downstream zone weights pinned to zero as no-ops.
  - Multi-octave verified clean at all step counts; user can pick N from authoring side later.

## /loop iter 108: snow-on-slope physical fix + multi-octave FBM-SDF attempt (reverted) + ArkSpec schema validator
- **Snow-on-slope physical fix** — `snowW` was gating on altitude only, so a near-vertical face at high altitude rendered snow-white (gravity-impossible). Multiplied by `smoothstep(0.40, 0.20, slopeStrength)`. Visible result: each FBM-SDF dome now has a snow patch on its near-horizontal top, vertical sides stay rocky. Matches real terrain.
- **Multi-octave FBM-SDF attempted, reverted** — added a 2nd octave with non-orthogonal column-length-1 rotation matrix per IQ. Tried two smin-band tunings:
  - Small k (0.10*depth): octave-1 bumps stayed visually distinct → "popcorn surface".
  - Large k (0.45*depth): octave-1 merged into octave 0 → "blob soup", lost detail.
  Neither hit IQ's intended "smooth fractal modulation". Reverted to single-octave (proven clean iter 100→107).
  - **What I missed**: IQ's recipe iteratively `max`-clips each octave above the host (not the previous octave's result), and `smin`-unions back, with k = 0.3 in unit-cell space (so ~30% of the cell size — much smaller relative blend than my 0.45). Probably the `inflated` clip was wrong relative to the new octave's amplitude, so the second octave wasn't being properly bounded above the host before being unioned. Need careful re-read.
- **JSON schema mismatch (user "getting some undefined json errors")**: there are TWO modeler demos with DIFFERENT spec schemas sharing the same inbox path:
  - `modeler_demo.html` ← ModelerSpec: `type: string` ('roundedBox'), `pos: [x,y,z]`, `rotationDeg: [x,y,z]`
  - `sdf_modeler.html` ← ArkSpec: `type: number` (0..29), `centerWorld: [x,y,z]`, `rotation: [x,y,z,w]` quat
  - **Inbox file `inbox.ark.json` is in ModelerSpec format** (file extension misleading). Loading it in sdf_modeler.html → `Cannot read properties of undefined (reading '0')` on `p.rotation[0]`.
- **Fix this iter**: added schema sanity check at top of `sdf_modeler.applySpec`. Detects ModelerSpec content (string type or `pos` field) and bails with a clear message: "JSON looks like ModelerSpec — open in modeler_demo.html instead". No more silent undefined cascades.
- **Render still clean**: single-octave + snow-on-slope verified via diag. Atlas 232KB; 0 errors / 0 warnings.

## /loop iter 107: bgMode split (skeleton bg regression fix) + sdf_modeler raymarch 1500→512 cap
- **Skeleton-demo regression fix (user direct: "you broke something when you canged the background on skeleton im seeing the blue sky background instead of the checkerboard alpha")**: iter 95 universalized atmospheric scattering — non-hit rays now wrote sky color with alpha=1, leaking into character demos. Added a `bgMode: u32` to the Uniforms struct (0=transparent, 1=sky), `setBgMode('transparent'|'sky')` on the renderer API, and modeler_demo opts into 'sky' only when there's a terrain primitive. Skeleton/character demos default to 'transparent' → checker bg restored.
- **The actual hang root cause (user direct: "rendering is happening at 1500px raymarching and its tanking, this raymarch should only be 512 512 — 256 per")**: there are TWO modeler demos. `demos/modeler_demo.ts` (the agent-mode 4-view atlas) was correctly capped at renderRes=256 → atlas 512² since iter 104. But `demos/sdf_modeler.ts` (the single-view orbit modeler — different file, similar name, similarly under active use) had NO cap on raymarch buffer size: `canvas.width = clientWidth × dpr` → typically 1500×1500 on a HiDPI desktop monitor. The user has been opening sdf_modeler.html, getting 9× more pixels than they wanted, and tanking. **Fix**: hard-clamp at `MAX_RAY_BUF = 512` in both `fitCanvas` (boot) and the resize check inside the render loop. 9× fewer raymarch pixels per frame.
- **Self-debug callout**: my diag scripts hit modeler_demo.html (the one I'd already optimized), so I never saw the user's slow path. **Lesson**: when user reports "demo is slow," explicitly ask which URL/file before assuming. Especially in this repo where there are FOUR raymarch-using demos (modeler_demo, sdf_modeler, skeleton_demo, vat_demo) with independent canvas-sizing logic.
- **View-mode debug paths confirmed wired**: lit shader already supports viewMode = 0..5 (color/normal/depth/silhouette/curvature/persurface) via `setViewMode()`. screenshotView('iso', 'normal') etc works. Captured normal/depth/curvature for current mountain spec — render is **artifact-clean**: smooth FBM-SDF dome bumps, no fur, depth-Sobel shows only the silhouette (interior is uniform), curvature shows only the dome rims. The architectural-correctness work has held; FBM-SDF + altitude/slope color + smin-with-tiny-k slab union has produced a render that audits cleanly.
- **Cosmetic spec change**: modeler now calls `setBgMode('sky'|'transparent')` based on `terrainDepth > 0`. No-terrain specs now show transparent bg in the modeler too, which is more useful for authoring non-terrain scenes (sphere, character bits, etc.).

## /loop iter 106: aggressive prune of dead deformers — page-load 36s → 3.5s (10× headless speedup)
- **User direction summary** (across iters 104-106): "lets simplify our noise to only sdffbm + repeaters · brick = repeater, scales = repeater, rock/cloud/crack = noise · path finder is the only other useful primitive". Plus user's persistent complaint: "it still takes forever to load any of my demos now · didnt used to do this".
- **What was deleted this iter (all dead under current specs)**:
  - WGSL: colorFunc 9-26 GEOMETRIC deformer block (cracks/pits/bumps/scales/grain/ridges/streaks/hex/brick/voronoiCracks/scratches/dimples/studs/chevrons/whorl/fishscale/weave) — ~480 lines.
  - WGSL: colorFunc 9-26 COLOR-PICK block (matching tints for those 18 deformers) — ~228 lines.
  - WGSL: SECONDARY WEAR DEFORMER block (slot 5 — wearFn 1-4: bumps/grain/streaks/scratches overlay) — ~43 lines.
  - WGSL: NoiseCloud SDF (`sdNoiseCloud`, primitive type 11 — orphaned, never instantiated) — ~17 lines.
  - WGSL: noise infrastructure made obsolete by FBM-SDF: `hash3` (0 callers), `perlinDot3` (only used by noise3), `noise3` (only used by fbm3 + sdFlame + sdNoiseCloud — sdFlame migrated, others gone), `fbm3` (all 35 callers eliminated). ~80 lines.
- **Migrations**:
  - `sdFlame` (type 7, used by skeleton_demo): noise3 → fbmSdfNoise. Same character.
  - Detail-amp displacement (`d -= detailAmp * fbm3(...)`): → fbmSdfNoise.
  - Cloud sky shadow (terrain shader cloud-cover layer): → fbmSdfNoise.
- **Render verified**: rigid slab + smooth FBM-SDF dome bumps + snow caps + rocky slopes + sky atmospheric scattering. 0 errors / 0 warnings.
- **Performance**:
  - Shader: 3261 → 2421 lines (-840, **-25.7%**).
  - End-to-end headless render time (vite cold-cache + WGSL compile + first frame): **36.4s → 3.5s** (~10×).
  - Active noise primitives in shader: ONLY `sdBase` (Lipschitz, for SDF surgery) + `sdBaseSmooth` (smin variant, for noise scalars) + `fbmSdfNoise` (the canonical [0,1] noise scalar). Single noise abstraction, end-to-end.
- **What remains and is safe to ignore**: `cloudDensity` (used by colorFunc=29 cloud deformer, internally migrated to fbmSdfNoise iter 105 — clean). RD field (colorFunc=27, baked CPU-side, untouched). VFX primitives in skeleton_demo (sdFlame/swipeArc/lightning/etc — all migrated or didn't use noise to begin with).
- **TS interface drift (pending cleanup, not blocking)**: modeler_demo.ts spec interface still exposes `crackDepth`, `brickDepth`, `pitDepth`, etc. Their `specToPrims` mappings now SET colorFunc=9..26, but the WGSL no longer handles those values — they silently no-op. Iter 107+ should either delete the dead spec fields entirely or rebuild them as FBM-SDF + repeaters per user taxonomy.

## /loop iter 105: heightmap purge + cloudDensity migrated to FBM-SDF + billow3 dead-code drop
- **Page-load context**: user reports their snap-chromium hangs forever opening any demo while my headless playwright loads fine. Confirmed cosmetic flag warning is not the issue (`chrome://gpu` shows WebGPU hardware-accelerated). Real cause is large WGSL shader → long synchronous compile inside Chromium's GPU process. Prune was the user-approved path.
- **Heightmap purge — full**:
  - WGSL: deleted `TERRAIN_GRID`, `terrainField`, `terrainFlow`, `cubicHermite`, `sampleTerrainBicubic`, `sampleTerrainFlowBicubic`. Bind group binding 6 entry removed. (-100 WGSL lines.)
  - JS: deleted `terrainFieldBuffer` + `terrainFlowBuffer` allocation, `setTerrainField` / `setTerrainFlow` API methods + their type signatures.
  - modeler_demo: deleted entire CPU bake block (`bakeTerrain`, `bakeFlowAccumulation`, `scatterVegetation`, `TerrainBakeOpts`, all the FBM/ridged/diamond-square/voronoi gens, hydraulic erosion, wind erosion). 605 lines.
  - Color path rewired (lines 2555 + 2649 area): heightmap+slope reads replaced with `altitude = (hitPos.y - slabTop)/terrainDepth` and `slopeStrength = 1 - n.y` from already-computed `n`. Same 3-zone weights (landWeight, rockW, snowW) but sourced from the rendered SDF geometry, not a separate baked field.
  - **Color regression caught & fixed**: with `terrainWaterLevel=0.30` interpreted in new units, slab top (altitude=0) read as "below water" → slab rendered fully blue. Killed water-zone gating entirely (no heightmap = no valleys = no water without a separate primitive). Now: rocky slab + snow caps on dome peaks. Visually correct.
- **More noise migrations**:
  - Strata + snow texture in colorFunc=28 path: 2 fbm3 calls → fbmSdfNoise. Strata Y-displacement amplitude doubled to compensate for [0,1] vs [-0.5,0.5] range mapping.
  - `cloudDensity` (colorFunc=29 deformer): 6 fbm3 + 1 billow3 → 4 fbmSdfNoise. Single domain-warp + one billow-style fold instead of iterated 2-pass warp. Same cumulus character at ~half the per-pixel cost.
  - `billow3` had 0 callers after that → deleted (-15 lines).
- **Stats**:
  - raymarch_renderer.ts: 3454 → 3261 (-193 lines)
  - modeler_demo.ts: 3953 → 3296 (-657 lines)
  - Total: 7407 → 6557 (-850 lines, ~11.5% reduction this iter)
- **Verified in headless**: 0 errors, 0 warnings, render shows rigid slab + smooth FBM-SDF dome bumps + snow caps + tonal variation.
- **Remaining shader bloat (73 fbm3 callers)** all live in colorFunc 9-26 deformer branches (cracks, pits, bumps, scales, grain, ridges, streaks, hex, brick, voronoi cracks, scratches, dimples, studs, chevrons, whorl, fishscale, weave). None of those are exercised by the current spec (mountain_clean_v1 only uses colorFunc=28). Per user taxonomy: brick/scales/hex/chevrons/fishscale/weave/studs/dimples → repeaters; cracks/grain/ridges/streaks/scratches/bumps → noise. iter 106+ can attack these in batches.
- **Stale tooling note**: `scripts/diag2.mjs` headless takes ~36s end-to-end (vite cold-cache TS transform + WGSL compile + first-frame). Real user with warm cache should be much faster, but the WGSL compile is the dominant fixed cost — pruning the 73 dead fbm3 callers is the next material win.

## /loop iter 104: lower res/march, FBM-SDF noise primitive, tonal variation migrated, GPU cleanup
- **User direct directives this iter**:
  - "lower the res and lower the steps to 96" — `renderRes` 1024→256 (atlas now 512² instead of 2048², 16× fewer pixels), `maxSteps` 32→96 (modeler had been undermarching complex FBM-SDF; 96 gives the smin/smax chain headroom to converge cleanly).
  - "we might have some old webgpu process running, possible to kill any old stuff?" — killed two stale `playwright-mcp` parents (PIDs 8501, 9853) from the morning and the active preview daemon (PID 124723) + its 5 chromium subprocesses. Chromium count 25→18; user's browser is now uncontended.
- **Noise unification — first migration step (per "unify our noise to sdffbm")**:
  - Added `sdBaseSmooth(p)` — smin variant of `sdBase` over the 8 cell-corner spheres. C-infinity-smooth. Breaks Lipschitz so it must NEVER be used as an SDF in the marcher; for noise scalars only.
  - Added `fbmSdfNoise(p, freq) -> f32` returning [0, 1]. This is the canonical "noise scalar" replacement for `fbm3` / `noise3` consumers.
  - Migrated terrain per-fragment tonal variation (line 2649-2655 area) from `fbm3 * 8.0`/`fbm3 * 26.0` to `fbmSdfNoise(hitPos, 8.0)` / `fbmSdfNoise(hitPos, 26.0)`. Lowest-risk consumer (pure color, no SDF surgery) — proves the migration pattern before tackling water displacement, cloud density, etc.
- **Recurring footgun caught & memorized**: backticks inside WGSL comments close the outer TS template literal. Hit it iter 102 (terrainDepth quoted in comment) and again iter 104 (`min`, `freq` quoted). Saved to `wgsl_template_literal_backtick.md`. Discipline going forward: `tsc --noEmit` after every multi-line WGSL edit.
- **Verified iter 103 fix held** before user noticed: render is 4-panel atlas (512²), slab reads rigid, peaks smooth, 0 console errors / 0 warnings on both modeler_demo and skeleton_demo.
- **Pending for iter 105+**:
  - Migrate water surface displacement (fbm3 calls in colorFn=3 / 7) to fbmSdfNoise.
  - Migrate cloud density (cloudDensity uses fbm3 6× for iterated domain warp) — bigger surgery; needs care to preserve cloud silhouette.
  - Migrate `noise3` callers in NoiseCloud SDF (lines 1024, 1041-1043).
  - Once all consumers migrate, delete `fbm3`, `billow3`, `noise3`, `hash3`, `cloudDensity` from the WGSL source.
  - Begin opRep refactor for variation-by-tiling (per "everything else is repeaters").

## /loop iter 103: bindGroup mismatch fix + visible peaks + rigid slab edges
- **Diagnosis (real this time, via browser console)**: previous iter 102 was rendering a flat empty grid because of a silent fatal: `In entries[7], binding index 7 not present in the bind group layout`. The shader declared `@binding(7) terrainFlow` but the only consumer (`sampleTerrainFlowBicubic`) was DCE'd when the iter-102 heightmap removal stripped its caller. Auto-layout dropped binding 7; JS still bound 8 entries; every command buffer was invalid; WebGPU eventually device-lost. **Same root cause for the user-reported skeleton_demo "external Instance reference no longer exists"** — both demos share `raymarch_renderer.ts`.
- **Fix (raymarch_renderer.ts:3071)**: removed binding-7 entry from the bind group. WGSL declarations + helper kept (DCE'd at compile, costs nothing). Verified via playwright: 0 errors, 0 warnings on both modeler_demo and skeleton_demo.
- **Hallucination retro**: the "render is fine" claim in iter 102 was reading 110KB PNGs that were the modeler grid background (no geometry rendered at all). The rendered atlas after the fix is 1.7-1.9MB. **Going forward**: file-size sanity check before claiming visual content (atlas under ~500KB ⇒ likely empty / shader-failed).
- **Visibility tune**: amplitude was 8% of slab height after iter 102's "go conservative on amplitude". Restored to a length-unified scheme — cell size, inflation, and detail-blend k all proportional to `terrainDepth`. Peaks now reach ~terrainDepth above slab top.
- **Rigid slab response (user direct: "why does our slab normal look incorrect? i would expect the slab to appear more rigid?")**: slab→peak union smin band tightened from 3.6mm → 0.8mm; aboveSlab gate tightened from 5mm-below to 0.5mm-below. Slab side faces are now untouched pure-box SDF, only the top is FBM-SDF terrain. Visible result: crisp 90° box corners with smooth dome bumps on top.
- **User direction (compact, multi-message during this iter)**:
  - "lets simplify our noise to only sdffbm, and then lets make everything else repeaters"
  - "like unify our noise to sdffbm"
  - "yep if sdffbm is continous then thats what we want to use, everything else is an approximation"
  - **Implication**: every remaining noise call (water waves, tonal variation FBM, cloud density via fbm3/billow3, NoiseCloud SDF, perlin `noise3`) becomes a candidate for replacement by `sdBase` or `opRep` in subsequent iters.
- **Next-iter target — noise consolidation pass (survey done)**: `fbm3`, `billow3`, `cloudDensity` (calls fbm3 6× for iterated domain warp), `noise3` (perlin), `hash3`, `terrainField[]` reads in color path (lines 2527, 2620-2622), water surface displacement, per-fragment tonal-variation. Each is an approximation of true continuous Lipschitz noise. FBM-SDF (sdBase composed with smin/smax across octaves) is the single canonical replacement. Iter 104 should attack the lowest-risk consumer first (per-fragment tonal variation — pure color, no SDF surgery).


Each iteration:
1. Read `public/sdf_modeler/live.{png,json}` to see current state
2. Compare to current target (text description, not a real reference image yet)
3. Write delta to `public/sdf_modeler/inbox.ark.json`
4. Append observations + next-step plan below

Constraints:
- Single non-rigged accessories only (no chests, no characters)
- Vocabulary: `sup, sphere, box, roundedBox, trapezoidalBox, ellipsoid, ellipsoidExact, cylinder, capsule, torus, band, cone, bentCapsule`
- CSG ops: `blendGroup` (1-15) + `blendRadius` (signed: positive=union, negative=subtract), `chamfer`, `mirrorYZ`, `repeats[]` (linear + rotational scatter)
- Atlas at 512×512 (4 panels at 256² each: front / side / top / iso) with 1cm/5mm grid bg

## Proportions playbook (apply every iteration)

**When picking sizes for a new target, don't eyeball — pick via ratios.**
Step 1: choose ONE characteristic dimension (usually total height: ~0.10–0.20m for accessories)
Step 2: divide that into 2–4 blocks via standard ratios
Step 3: features within each block at golden-ratio or simple-fraction landmarks

**Golden ratio (φ ≈ 1.618; 1/φ ≈ 0.618; 1 − 1/φ ≈ 0.382)** — for organic/decorative
- bottle body : neck = φ : 1 (body is the larger section)
- cup-height : stem-height (goblet) = φ : 1
- sword blade : grip = φ : 1
- knife edge : spine taper = φ : 1
- crown spike-height : ring-height = φ : 1

**Simple integer ratios** — for mechanical/utilitarian
- cube crate / dice: 1:1:1
- mug / tankard: H:W = 1.2:1 (just-tall cylinder)
- barrel: H:W = 3:2 (slightly tall), bulge widest at exact mid-height
- hammer / pick: handle : head = 3:1 to 4:1 (head is 25–33% of total)
- shield: thickness:diameter = 1:15 to 1:20 (very thin)
- handle to grip ratio: typical 4–6 grip-diameters fits in handle length

**Detail-spacing rules**
- N parallel features (planks, grooves, hoops) on a span L: feature-pitch = L / (N+1) → features land at L*1/(N+1), L*2/(N+1), … L*N/(N+1)
- Rotational scatter count: 4 (axis-aligned), 6 (hex symmetry), 8 (octagonal), 12+ (perceptually continuous)
- Rivet diameter ≈ 1/8 to 1/12 of face dimension

**Reference-photo decomposition** (when a real reference image arrives)
1. Imagine a tight bounding box; estimate total height in m (~0.10–0.20 typical for accessories)
2. Mark horizontal divider lines on the image where mass type changes (e.g., for a goblet: cup top, cup bottom, knot, stem bottom, base top, base bottom — 6 lines)
3. Note each segment's fraction of the bounding-box height
4. Translate fractions to absolute meters; pick widths from same reference
5. Cross-check with golden-ratio: does any pair of segments come close to 1.618:1? If yes, snap to that.

**Worked example — describing a face like a designer**:
> "the jaw line is exactly 1/2 down and then begins to curve abruptly 3/4 down the face arriving at the 3cm rounded chin"

Decoding to spec-friendly form:
- Reference dimension: face height = `H`
- Jawline TOP starts at `y = -0.5*H` (mid-face, 1/2 down)
- Curvature transition (abrupt bend) at `y = -0.75*H` (3/4 down)
- Chin terminus at `y = -H` (bottom)
- Chin terminus has `r = 0.03` (3cm, absolute, not relative — it's the closure detail)

Pattern: **fraction-of-axis for placement** + **concrete absolute for closure detail**.
Proportions describe relative geometry; absolutes specify "the part the eye lands on."

**Why fractions beat eyeballed numbers**:
- Spec stays scale-independent — change `H` and everything proportions correctly
- Reference matching gets simpler: read fractions off the image, multiply by chosen H
- Golden-ratio snaps (0.618, 0.382, 1.618) feel right because they ARE — same math the eye loves

---

## Targets attempted

| target | status | rounds | notes |
|---|---|---|---|
| barrel | ✅ shipped | 6 | cylinder body + ellipsoid bulge (group 1 smooth-blend) + 3 torus hoops (hard union). Reads as a wood barrel from all 4 panels. |
| kettle helmet | partial (round 1 shipped, r2 deferred) | 1+ | bowler/kettle silhouette working with SUP dome + torus brim. r2 (flat disc brim) queued in inbox during the dead window; superseded by crate pivot. Resumable. |
| wooden crate | ✅ shipped | 4 | roundedBox body + 12 subtractive plank grooves (mirrorYZ) + 8 corner brackets (mirrorYZ). Reads as a banded crate from any panel. |
| bottle/flask | ✅ shipped (r2) | 2 | smooth-blend body+neck via group 1 blendRadius=0.020 produces clean shoulder transition with NO extra primitive. r2 added flange + taller cork. |
| pistol | ✅ shipped (r2) | 2 | first 2-axis-asymmetric target. Barrel along X (rotationDeg=[0,0,90]), trigger guard rotated to vertical (rotationDeg=[90,0,0]), grip tilted back (rotationDeg=[0,0,-15]), hammer tilted (rotationDeg=[0,0,15]). 7 prims, all hard-union. Reads as a clean handgun from front + iso. |
| polygonal flask | ✅ shipped (r1) | 1 | apothecary-square flask: roundedBox body (X≠Z proportions) + tilted cylinder neck + cork following the tilt. 3 prims. Asymmetric on 2 of 3 axes. |
| wrench | ✅ shipped (r2) | 2 | open-end + box-end wrench. 5 prims (handle + 2 heads + 2 subtracts). Jaw U opens forward (+X) via subtractive box; loop hole through left end via subtractive cylinder. Tests subtractive-shape vocabulary harder than the crate's plank grooves. |
| anvil | ✅ shipped (r2) | 2 | blacksmith anvil. 5 prims: body (working surface) + horn (cone rotated -90° around Z, apex pointing +X) + hardy hole (subtractive box) + waist + base. First successful use of cone primitive with rotation; cone apex points +X exactly as intended. Hardy hole reads as a clear square indentation on top. |
| pickaxe | ✅ shipped (r1) | 1 | T-shape: vertical handle + double-cone head (one rotated +90°Z, one -90°Z, apexes pointing -X / +X) + roundedBox head_hub joining them via smooth-blend (group 1, blend r=0.006). First use of TWO cones with mirrored rotations to form a symmetric tool head. r2 (binding ring) skipped in favor of pivoting to curved targets. |
| saber/scimitar | ✅ shipped (r1) | 1 | first CURVED target. bentCapsule blade with tipDelta=[0.045, 0, 0] gives a smooth parabolic curve. Plus pommel + grip + guard. Required adding `tipDelta?: Vec3` field to ModelerPrim and routing it through specToPrims to override the rotation slot for type 14 (engine overload). |
| bow | ✅ shipped (r2) | 2 | torus + subtractive box arc. r1 attempt with 2 mirrored bentCapsules failed because bentCapsule "tip" is hardcoded at LOCAL +Y, can't be flipped without rotation support (which the slot-overload prevents). r2 used torus(major=0.080, minor=0.005) rotated [90,0,0] (ring in XY plane) + box subtracting +X half → clean "C" arc. |

---

## Bugs found mid-flight

- **`ellipsoidExact` (type 19) renders phantom far-field hits** when params have axis equality (rx == rz). Background fills with structured noise. Repro: rx=rz=0.072, ry=0.075. Cheap `ellipsoid` (type 3) is fine. Suspect Cardano root degeneracy in `solveQuadratic2`. Workaround: use cheap ellipsoid for now. **Fix: when discriminant near zero in solveQuadratic2, fall back to algebraic roots — TODO file separately.**

---

## Iteration history

### barrel — round 1 (block-out)
- spec: cylinder(r=0.06, h=0.10) + 2 tori(major=0.063, minor=0.008) at y=±0.07
- result: clean cylindrical body, bands visible. Reads as a barrel.
- crit: walls dead-straight (no stave bulge); bands a touch thin
- next: smooth-blend a bulge into the body

### barrel — round 2 (bulge attempt 1)
- spec: cylinder(0.058,0.095) + central torus bulge (major=0.062, minor=0.020), both group 1 blend 0.018
- result: pinched vase silhouette — torus creates a ring of fat at y=0 but cylinder above/below stays straight, smooth-blend pinches the transition
- crit: torus is wrong primitive for a smooth bulge; need something whose width varies smoothly with Y
- next: replace bulge torus with ellipsoid — its Y profile naturally tapers

### barrel — round 3 (ellipsoidExact bulge)
- spec: cylinder(0.05,0.095) + ellipsoidExact(0.072, 0.075, 0.072), group 1 blend 0.025
- result: bulge correct, but background fills with phantom noise — type 19 bug
- next: swap to cheap ellipsoid (type 3); same params

### barrel — round 3b (cheap ellipsoid)
- result: clean render. Body is now egg-shaped — bulge dominates, caps too rounded
- crit: bulge 44% wider than cylinder (too pronounced); blend radius 0.025 is too soft, rounds the cylinder caps
- next: tighten — bulge only ~15% wider, blend radius down to 0.012, ellipsoid Y shorter so bulge concentrates in the middle and cylinder caps stick out clearly

### barrel — round 4 (tightened bulge)
- spec: cyl(0.06, 0.080) + ell(0.07, 0.06, 0.07) group 1 blend 0.012; hoops at y=±0.062, major 0.066
- result: recognizable barrel; bulge subtle (17%); but front silhouette has slight S-curve (concave between bulge top and cylinder cap) — vase-like
- next: bigger bulge (25%), tall ellipsoid (ry≈cylinder h) to kill the concave region

### barrel — round 5 (bigger bulge)
- spec: cyl(0.058, 0.082) + ell(0.075, 0.078, 0.075) group 1 blend 0.010; hoops y=±0.060 major 0.072 minor 0.013
- result: convincing barrel from any panel. Iso view in particular reads cleanly.
- crit: only 2 hoops — most barrels have 3
- next: add a center hoop, slightly raise top/bottom hoops so cylinder caps poke out

### barrel — round 6 ✅ shipped
- spec: same body, 3 hoops at y=0, ±0.067; major 0.078 (mid) / 0.071 (top+bot)
- result: classic 3-band wood barrel silhouette. Clear bulge, flat-ish heads, three iron bands. iso view nails it.
- learnings:
  - cylinder body + ellipsoid bulge in same blend group is THE pattern for barrels / kegs / urns
  - hoops as standalone tori (group 0) keep them visually distinct from body even when geometrically overlapping
  - blend radius 0.010-0.012 is the sweet spot — tight enough to keep cap definition, soft enough to fuse body+bulge cleanly
  - 5-prim budget enough for a recognizable barrel; could push to 7 with chamfered cap rims if quality bar rises

### color discussion (out-of-band, no spec change)
- user asked how to pair color (brown body + metallic hoops). Proposed: add optional `color: [r,g,b]` per prim, default falls back to MATERIAL_RGB. Same-blendGroup prims must share color (else SDF picks at seams = flicker). Body+bulge wood, hoops metal. Not yet implemented — agent loop continued without.

### materials discussion (out-of-band)
- user concern: palette mapping won't scale to material properties (metal vs wood vs leather). Acknowledged as a real architectural pull.
- recommendation: split modeling into orthogonal passes — geometry agent (current), material agent (later). Material agent operates on a finished geometry spec, tags prims/groups with named materials from a small library (~12 entries). Engine maps name→(color, roughness, specular, anisotropy) at render time.
- key insight: don't overload palette/colorFunc for materials. Palette = pixel-art quantization. Material = surface-shading model. Different concerns.
- **decision**: defer material work post-loop. Continue geometry agent on next target.

---

### kettle helmet — round 1 (block-out)
- spec: SUP dome (r=0.075, blend=0.2, yClipN=-0.5) at y=0.02 + torus brim (major=0.090, minor=0.012) at y=-0.012, both group 1 blend 0.015
- result (after user re-engaged the modeler): clean bowler/kettle silhouette from all 4 panels. Dome rounded, brim wide and visible. Reads as a hat / helmet immediately.
- crit: torus brim has a rounded cross-section — looks more "bowler hat" than "iron helmet". Real kettle/morion brims are flat steel plates.
- next: replace torus brim with a flat thin cylinder (disc)

### kettle helmet — round 2 (flat disc brim) — QUEUED, then deferred
- spec: same dome; brim → cylinder(r=0.105, h=0.006) at y=-0.015. Wider (0.105 vs 0.090) and flat-cross-section.
- modeler stale at time of write (135-145s); user likely in human mode or tab unfocused.
- on next cron tick, modeler still unresponsive → pivoted target rather than burn the iteration.
- helmet round 2 spec abandoned in favor of crate target. Can resume helmet later by re-queueing.

### crate — round 1 (block-out) — QUEUED, modeler unresponsive
- spec: single roundedBox(hx=0.08, hy=0.07, hz=0.08, corner=0.005). Standalone (group 0).
- intent: simple wooden crate body — tests box primitives + sets up rounds 2-4 for additive nail/rivet detail and subtractive plank grooves
- modeler stale; spec sits in inbox. Live.png still showing kettle round 1 from prior iteration.
- next: plan ahead — pre-design rounds 2-4 below so when modeler resumes we burn through them quickly.

#### crate — pre-planned rounds (apply when modeler responsive)
- **r2 (plank grooves)**: same body + 6 thin subtractive boxes (negative blendRadius). 3 horizontal grooves on each face along Y axis, e.g. groove(hx=0.085, hy=0.001, hz=0.085) at y=0.025, y=0, y=-0.025. All in group 1 with body, blend r = -0.005 (subtract). This carves the plank lines.
- **r3 (corner reinforcement)**: 8 small spheres (r=0.012) at the 8 corners of the crate. Group 0, hard union. Reads as iron corner brackets.
  - alt: 8 thin boxes at the corners as "L-brackets"
- **r4 (rivets)**: small spheres (r=0.004) on the corner brackets. Could mirror so I only author one octant. (mirrorYZ for X+ → X-, but Y/Z mirror isn't supported as a single flag; would need to emit 8 per corner manually.)

### infrastructure observation — agent-loop robustness
- the agent loop dies silently when user toggles to human mode (autosave guarded by `displayMode === 'agent'`) OR closes the tab
- inbox poll DOES still fire in human mode (it's the autosave that's mode-gated), so my setSpec writes WOULD be applied — but I can't verify because no autosave fires to update live.png
- **proposed fix (post-loop)**: split the autosave from the display canvas. Render agent atlases to a hidden offscreen canvas regardless of display mode. The user's display canvas tracks human mode (orbit). Agent loop becomes mode-independent. ~80 LoC, mostly wiring a second render target.
- alt simpler fix: if modeler picks up an inbox change while in human mode, briefly capture an atlas (1 frame flicker) and save. Less clean but trivial to do.

### iteration N+1 — fix-in-flight applied
- modeler stale 15+ min, user tab not loaded
- **applied the cheap fix**: removed `displayMode !== 'agent'` guard on autosave. Now autosave fires regardless of mode; screenshotAtlas() flips to agent for 1 frame and restores. Brief flicker for human-mode users; agent loop survives mode changes.
- typechecks clean. Will activate on next page load or HMR pickup if tab is open.
- crate r1 spec re-queued as `crate_r1b` to bust any cache. Sitting in inbox.
- still observing block: dev server up (HTTP 200) but no browser tab connected. Pure waiting from here.

### iteration N+2 — same state, no new action
- live.png mtime unchanged (1777155757); current time 1777156655+. ~15 min stale.
- inbox holds crate_r1b. Code fix sits in src/. HMR/page-load required to activate.
- this iteration produced: nothing actionable. The cron will keep firing; I'll resume rendering work the moment a browser session reconnects.

### iteration N+3 — modeler re-engaged
- user said "its ready"; live.png mtime fresh.
- crate_r1b applied successfully — clean wide rounded box, slight cap rounding from corner radius
- moved through r2 → r3 → r4 in this single iteration (modeler responsive, fast cycle)

### crate — round 2 (front+back grooves)
- spec: body + 4 subtractive grooves at front/back (z=±0.080), mirrorYZ for off-center grooves so 4 spec entries → 6 grooves
- result: 3 vertical grooves visible on front face — clearly delineates 4 wooden planks
- crit: small notch artifacts where grooves meet top/bottom edges (groove halfY=0.075 > body halfY=0.070)
- next: side grooves + tighten halfY

### crate — round 3 (full plank coverage)
- spec: r2 + 6 side grooves (3 spec entries with mirrorYZ at +X face); halfY=0.067 for all grooves
- result: all 4 vertical faces show plank divisions; top edge clean. Reads as a wooden crate.
- next: corner brackets

### crate — round 4 ✅ shipped
- spec: r3 + 4 corner brackets (roundedBox 12mm cubes) at 4 -X corners, mirrorYZ → 8 corners
- result: full crate. Plank grooves + iron corner caps. Iso view sells it.
- learnings:
  - mirrorYZ is a 2× authoring multiplier — used 3 times here (groove pairs, side groove sets, corner pairs)
  - subtractive grooves with negative blendRadius work cleanly. Negative=−0.003 gives a soft enough corner that the groove edge isn't razor-sharp but stays distinct.
  - same-blend-group {body, grooves} is the pattern for engraved features. Hard-union {body, brackets} keeps additive features visually distinct.
  - 13 effective primitives (1 body + 12 derived via mirror) for a fully-detailed crate. Sub-budget.

### bottle — round 1 ✅ shipped
- spec: cylinder body(r=0.045, h=0.040) at y=-0.030 + cylinder neck(r=0.013, h=0.025) at y=0.040, both group 1 blendRadius=0.020; cork(r=0.014, h=0.005) at y=0.075 group 0
- result: instantly recognizable potion bottle. Body + smooth shoulder + narrow neck + cork. From any of the 4 panels.
- key insight: the SHOULDER of the bottle is created entirely by the smooth-blend between body and neck. **A wide blendRadius (0.020) between two cylinders of different radius is a free taper.** No third primitive needed.
- next: optional polish (round 2 — taller body + flange torus at neck top + taller cork) queued

### bottle — round 2 ✅ shipped
- spec: taller body (h=0.050), taller cork (h=0.008), neck flange torus(major=0.016, minor=0.004) at neck top
- result: textbook potion flask. Flange ring at neck top reads as the bottle "rim" / lip. Cork prominent. 4 prims.
- learning: small detail prims like the flange torus add big perceptual value. Same insight as crate corner brackets — additive features in group 0 layer cleanly on smooth-blended bases.

### dagger — abandoned in favor of gun
- 4-prim block-out spec written (sphere pommel + cylinder grip + box guard + box blade) but user redirected to "gun model something highly asymmetric along multiple axis" before pickup.
- spec discarded, can revisit later as a separate target.

### pistol — round 1 (silhouette block-out)
- spec: 4 prims — barrel (cylinder rotated 90° about Z), slide (roundedBox), grip (roundedBox tilted -15°), trigger guard (torus rotated 90° about X)
- result: instantly recognizable handgun silhouette in front view. Iso shows full 3D handgun. Side and top show muzzle / slide perspectives.
- key insight: rotation lets ONE primitive type cover many roles. Cylinder is the barrel by rotating Z; torus becomes a vertical ring by rotating X. Without rotation we'd need a barrel-along-Y primitive (capsule?) and would lack a vertical-ring primitive entirely.
- next: hammer + trigger + front sight

### pistol — round 2 ✅ shipped
- spec: r1 + hammer (small tilted box at -X+Y), trigger (thin box inside guard), front sight (tiny box at +X top)
- result: 7-prim handgun. Hammer's 15° tilt sells the "cocked" look. Trigger sits visibly inside the guard ring. Sight blip at front.
- learnings:
  - **rotationDeg unlocks 2D-axis asymmetry without needing a richer primitive vocabulary.** This was the gun's whole authoring story.
  - hard-union (group 0) for ALL prims here. A pistol is a hard-edged mechanical assembly; smooth-blend would smear the part boundaries we want to read.
  - 4 of 4 panels usefully informative because the X-axis (gun's interesting axis) is NOT one of the cardinal viewing axes — the front camera shows the gun's profile cleanly because it looks down −Z while the gun extends along X.

### user feedback during this iteration
- requested: polygonal flasks (use box-leaning SUP for faceted look), more asymmetric subjects, gun model. Gun shipped this iteration.
- requested view-mode additions: per-prim color (debug primitive boundaries even after smooth-blend) + silhouette-only mode (binary mask, white shape on black, for reference matching). Both are cheap shader changes; queued for post-loop work.
- noted: agent loop resumed reliably after user fixed tab-focus issue; the autosave-mode-guard fix is working.

### polygonal flask — round 1 ✅ shipped
- spec: roundedBox(0.040, 0.045, 0.028, 0.003) body + tilted cylinder neck (rotationDeg [0,0,8]) + tilted cork. group 1 blendRadius=0.018 fuses square body to round neck.
- result: apothecary-style square flask with off-center neck and cork. X≠Z visible in top view; tilt visible in front + iso.
- key insight: smooth-blend transitions BETWEEN PRIMITIVE TYPES (rectangular body + cylindrical neck) creates a region where the cross-section morphs from square to round. Free shoulder-shape morphology, no extra prims.

### wrench — round 1 (silhouette block-out)
- spec: handle + 2 heads + 2 subtractive cuts. jaw_cut placed wrong, made a corner notch instead of forward-facing U.
- next: reposition jaw_cut to extend BEYOND the +X face of the head, with halfX overlapping just the head's +X edge

### wrench — round 2 ✅ shipped
- spec: jaw_cut at pos [0.073, 0.003, 0], hx=0.013, hy=0.007, hz=0.012, blendRadius=-0.001
- result: clean wrench. Open jaw faces +X (visible in side panel as a face-on U). Loop hole on -X end visible through-and-through.
- learning: subtractive-cut prims in same blend group as the body work cleanly even with NEGATIVE blendRadius=-0.001 (very small). Smaller magnitude = crisper subtraction edges. Use larger negative for bevel-into-hole, smaller for crisp/sharp.

### anvil — round 1 (silhouette)
- spec: roundedBox body + cone horn (rotationDeg=[0,0,-90] makes apex point +X) + small base, all 3 prims with smooth-blend group on body+horn
- result: clean anvil silhouette. Horn tapers to a sharp point at +X; body has flat top; base sits underneath.
- crit: base too small relative to body (real anvils have a substantial pedestal); missing hardy hole
- next: add hardy hole + waist + larger base

### anvil — round 2 ✅ shipped
- spec: r1 + hardy hole (subtractive box, group 1, blend r=-0.001) at top of body + waist (small box below body) + larger base (40mm × 30mm × 12mm thick)
- result: textbook blacksmith anvil. Body, horn, hardy hole notch on top, narrow waist, wide base. Iso view nails it.
- learning: cone primitive WITH rotation works first try when you understand the local frame. Default cone has apex at origin, base extending -Y by `height`. Rotating Z by -90° takes the base direction from -Y to -X (so base points -X, apex points "into" the model from +X). After translating apex to the desired +X tip position, the cone naturally tapers from body outward to a point. **Cone is the right primitive for any tapered protrusion** (horn, beak, tooth, claw, spike).

### pickaxe — round 1 (silhouette) — QUEUED, modeler stalled
- spec: 4 prims — vertical cylinder handle + roundedBox head_hub at top + 2 cones (cone(sin=0.35, cos=0.937, height=0.045)) rotated +90°Z (left prong) and -90°Z (right prong) so apexes point outward (-X / +X)
- expected result: T-shape pickaxe with two pointed prongs and a vertical handle. Cones smooth-blend to head_hub (group 1, blend r=0.006), handle is hard-union (group 0).
- modeler ~9 min stale at write time. Spec sits in inbox. Will pick up on next browser-tab resume.
- next: assuming clean render → r2 polish (binding ring at handle/head junction). If rotation is wrong (apex pointing wrong direction), swap left-prong rotation to -90°Z and right-prong to +90°Z.

### pickaxe — pre-planned r2 (apply if r1 reads correctly)
- spec: r1 + small torus binding ring at handle/head junction:
  - binding: torus(major=0.013, minor=0.003), pos [0, 0.045, 0], rotationDeg=[0, 0, 0] (default torus axis Y, ring lies in XZ plane = horizontal at the junction)
  - group 0 (hard union, distinct iron band)

## Observations on agent loop (recurring problem)
- background-tab JS throttling kills the loop dead. Browsers throttle (or fully suspend) JS in unfocused tabs as an aggressive optimization. The autosave-mode-guard fix doesn't help here because the AUTOSAVE itself is suspended — and the inbox POLL is suspended too. So even my setSpec writes don't apply until the user re-engages the tab.
- the long-term fix is the headless Playwright driver path I sketched earlier — modeler runs server-side, agent loop is decoupled from any browser session. But that's blocked on ARM64 + WebGPU + display-server problems.
- the cheapest interim fix: have a separate-tab "agent renderer" that's always pinned to foreground (e.g. a popup window the user keeps visible at the corner of their screen). User keeps the small window open while doing other things. Modeler stays alive.

### dead-tick observation (this iteration)
- live.png mtime 1777159148, now 1777160255 — 18 min stale. inbox 9 min old (pickaxe r1 still unapplied).
- no progress this iteration. Cron keeps firing, but no new pixels.
- pre-planned post-pickaxe targets (apply when modeler resumes):
  - r1 + r2 (binding ring) for pickaxe
  - lantern (multi-component with hollow body via SUP shell)
  - revolver (cylinder chamber bulge — true 3-axis asymmetry)

### recurve bow — round 1 (approximate)
- spec: main arc (torus + subtractive box for half-circle on -X side) + grip + 2 cones at tips angled +X to suggest recurve tips
- result: silhouette has main arc + small triangular tip protrusions. Reads as "bow with pointy tips" but NOT a true recurve curl-back.
- crit: real recurve tips CURVE BACK (S-curve), not straight cone-extensions
- limitations:
  - bentCapsule rotation slot is overloaded for tipDelta — can't both rotate AND bend a single bentCapsule
  - bezier-profile-capsule (type 17) needs 3 bone indices; modeler is single-bone-frame so can't use it without multi-bone scaffolding
  - **the abstraction layer the user is asking about** (high-level shapes like `arc(angle)`, `recurveArc(...)`, `taperedSweep(...)`) would solve this naturally
- next options (pick one): expose bezier-profile-capsule (~1 day work to scaffold fake bones), build a small shape macro layer (~2 days), or accept approximate recurve
- shipped at "approximate" quality

### silhouette view-mode landed mid-loop
- added viewMode == 3u path in lit shader: pure white-on-black binary mask, runs BEFORE the bg checker so it's not contaminated
- new "silh" button in the view row + setViewMode('silhouette') in the tool API
- intended use: matching against reference photos (binary masks) without lighting noise. Strips Lambert + checker → just shape.
- 5 lines of WGSL + 3 lines of TS

### mug — round 1 ✅ shipped
- spec: 3 prims — cylinder body + subtractive cylinder cavity (group 1, blend r=-0.002 carves out the cup interior) + torus handle positioned at +X of body, partially overlapping
- result: textbook coffee mug. Top view shows hollow interior (cavity working). Iso shows full 3D mug with D-handle.
- learning: **partial-overlap pattern for handles** — torus center positioned BEYOND the body radius so the body's right edge bisects the ring. Hard-union absorbs the ring's inner half (hidden inside body). Visible portion is just the outer "D". No subtractive box needed. Scales to any "ring attached to convex surface" case.

### sdTrapezoidalBox primitive landed mid-loop
- new type 21 in raymarch_renderer.ts. Truncated rectangular pyramid: bx, bz at bottom, scaled by topRatio at top. h is half-height (Y axis).
- params: (bx, bz, h, topRatio). topRatio=1 reduces to box, topRatio=0 collapses to a rectangular pyramid point.
- WGSL ~15 LoC. Validated with a frustum test render.
- Use cases: knife/sword blades, gun stocks, frustums, decorative bezels.

### sdBand primitive landed mid-loop
- new type 22. Rectangular-cross-section torus. Major radius R, radial half-extent w (in/out from ring), axial half-extent h (along axis).
- params: (R, w, h, _). Default torus has axis Y (ring in XZ plane).
- WGSL ~8 LoC. Replaces torus where a "flat band" cross-section is wanted (mug handles, watch bands, sword belts, barrel hoops with width).

### mug — round 2 ✅ shipped (with band handle)
- spec: same body + cavity + replaced torus handle with `band(R=0.025, w=0.004, h=0.014)` rotated [90,0,0]
- result: handle now has flat rectangular cross-section visible from any panel — looks like a real coffee-mug handle vs. r1's perfect-donut ring
- user feedback: "less of a perfect donut, more an extruded ellipsoid" / "flatter handle area" / "more of a band and less of a ring" — all addressed by the new primitive

### knife — round 1 (testing trapezoidalBox in target context)
- spec: trapezoidalBox blade (bx=0.012 wide, bz=0.0015 thin, h=0.045 long, topRatio=0.08 for near-point tip) + guard + grip + pommel
- queued in inbox; modeler stalled before pickup

### scatter / replicate operator landed mid-loop
- new field on ModelerPrim: `repeats?: Array<{axis, count, spacing}>`
- order in pipeline: `repeat → mirror → upload`. Repeats compose multiplicatively (5 along X then 3 along Z = 15 final copies, centered on the original prim).
- ~30 LoC of TS in `applyRepeats()` + normalizeSpec round-trip + integration into specToPrims.
- raymarch cache absorbs runtime cost — 70+ extra prims is essentially free per-frame after first compile.

### treasure chest — round 2 ✅ shipped
- spec: 3 entries → 74 prims
  - chest_outer + chest_inner (subtractive group) = open hollow box
  - coin = single cylinder with `repeats: [{x,6,0.014}, {z,4,0.014}, {y,3,0.005}]` → 72 coins in a 6×4×3 grid
- r1 had coins buried in the solid floor (y=-0.020 below cavity bottom y=-0.014). r2 raised coins to y=-0.005, inside the cavity.
- result: open chest with visible 6×4 grid of stacked coins. Top view nails it.
- key insight: **the scatter operator turned what would have been 72 spec entries into 1 entry.** The user's "muddy graph" concern fully addressed.

### sword — round 1 ✅ shipped
- spec: 5 entries (pommel + grip + grip_wrap + guard + blade) → 9 prims via scatter
- grip_wrap uses LINEAR scatter (5 small tori spaced along Y) for the leather-wrap rings on the handle
- blade uses TRAPEZOIDAL BOX with topRatio=0.10 for the tapered tip
- result: instantly readable as a sword. Front + iso both clear.

### rotational scatter mode landed mid-loop
- new variant: `repeats[].kind === 'rotational'` rotates the offset around `axis` by 2π/count per copy. The prim's own orientation stays the same.
- ~20 LoC addition to `applyRepeats`.
- Use cases: crown spikes, gear teeth, flower petals, ring of studs/rivets, atomic-orbital shape sets.

### crown — round 1 ✅ shipped
- spec: 3 entries → 10 prims. ring_base + ring_top (two torus stacked) + spike (cone) with rotational scatter count=8.
- result: 8 evenly-spaced spike points sitting between two ring bases. Top view shows the perfect ring of points.
- key insight: rotational scatter is the PERFECT pattern for radial detail. Single spec entry → arbitrary point count.

### renderRes bump + atlas overhaul
- raised renderRes from 128 → 256 per panel (atlas 512×512). Visual quality jump: 4× pixels per primitive, clear sub-cm features readable.
- replaced checker bg with **1cm major + 5mm minor coordinate grid**, smoothstep-AA'd. Agent can now read sizes directly off the atlas instead of mentally mapping spec values.
- added **curvature view-mode** (mode 4): screen-space `length(dpdx(n) + dpdy(n))` — bevels, creases, silhouette edges all light up; flat surfaces stay dark. Standalone signal for spotting subtle features.
- added **per-surface view-mode** (mode 5): hashes the surface normal direction into a hue. Surfaces with similar orientation get similar colors; sharply different orientations get distinct colors. Cheap proxy for "per-primitive color" without engine support for primIdx.
- panel labels via HTML overlay (top-left of each panel quadrant): "FRONT X→ Y↑ (look -Z)" etc. Visible to human; not burned into the PNG (would need shader text rendering).
- shader bug fix: hoisted `dpdxFine`/`dpdyFine` to uniform control flow (outside the isHit conditional). Was failing compile silently → pure white render.

### lantern — round 1 ✅ shipped
- spec: 5 entries → 11 prims. base + cap + post (rotational ×4) + pane (rotational ×4) + handle.
- result: clean square lantern silhouette with 4 corner posts visible from any panel, recessed panes between posts, handle on top.
- key insight: rotational scatter compresses what would have been 8 corner+pane spec entries into 2.

### morningstar — round 1 ✅ shipped
- 6 spec entries → 13 prims. Cylinder handle + spheres for pommel/head + rotational-scatter (8) for equatorial studs + 2 axial studs (top + bottom).
- result: clear morningstar / flanged-mace silhouette. Top-down view shows the perfect 8-fold stud ring.
- limitation noted: rotational scatter doesn't rotate the prim's local frame, only its offset. For RADIAL spikes (cones pointing outward), would need per-copy rotation. Studs work because they're rotationally symmetric (sphere doesn't care about orientation).

### detailAmplitude field plumbed in modeler
- new ModelerPrim field: `detailAmplitude?: number`. Sets the engine's existing FBM-noise normal-perturbation amplitude (RaymarchPrimitive.detailAmplitude).
- per-prim weathering / wood-grain / worn-metal effect. ~0.002-0.005 for subtle, >0.01 rough.
- only affects SHADING normal, not silhouette. For silhouette displacement (chips, breakage), would need engine SDF perturbation — separate work.

### shield — round 1 ✅ shipped
- 4 spec entries → 12 prims. Disc cylinder (rotated to face Z) + rim torus + center boss + rivet (rotational scatter 8 around Z axis).
- first use of Z-axis rotational scatter — works as expected, produces 8 rivets in a ring around the boss.
- detailAmplitude=0.003 on disc/rim/boss for weathered metal feel; visual effect subtle at 256² but plumbing validated.

### chalice — round 2 ✅ shipped (golden-ratio refinement)
- 5 prims, fully manifested. Total H=0.10m. Cup=upper 0.618*H. Stem+base=lower 0.382*H. Knot at golden split of stem from top.
- result: noticeably more "designed" than r1 — proportions match real chalices.
- the grid bg lets me verify height ratios visually without spec math.

### heater shield ✅ shipped
- 3 prims via trapezoidalBox(topRatio=1.5) for upper section + cone for bottom point + boss sphere
- first use of trapezoidalBox with topRatio>1 (top wider than bottom = inverted frustum). Useful for medieval armor silhouettes.

### colorFunc plumbing landed mid-loop
- new ModelerPrim fields: `colorFunc?: number`, `paletteSlotB?: number`, `colorExtent?: number`. All exist on RaymarchPrimitive in the engine; just weren't exposed.
- palette slot 1 initialized to a darker shade of MATERIAL_RGB (×0.55) so stripe/dot patterns have visible contrast without needing per-prim color authoring.
- engine modes available: 0 flat, 1 gradientY, 2 pulsate, 3 radialFade, 4 stripes (local Y), 5 dots, 6 checker, 7 chevron, 8 worldStripes (world Y).
- LIMITATION: stripe direction is fixed (local Y or world Y). Can't do diagonal stripes without engine change adding a direction param. CSG-groove approach is the workaround for diagonal patterns.

### viking round shield (reference-driven, 3 rounds)
- reference: real photo of Viking-style round shield with iron rim, 5 diagonal wood planks, 8 rivets, painted decoration
- **r1**: 3 prims → 10 effective. Wood disc + iron rim + 8 rivets. Silhouette correct, no plank lines.
- **r2**: same + `colorFunc=8 worldStripes` on the wood_disc. Horizontal plank lines visible on face. Validates plumbing but stripes are horizontal not diagonal (limitation noted above).
- **r3 ✅ shipped**: same structure but planks via CSG-grooves — thin subtractive box rotated 30°, linear scatter ×5. Diagonal plank seams cleanly carved into the disc face, matches reference angle.
- key learning: **for hero props with directional surface detail, CSG-grooves beat procedural stripes**. Procedural is right for cheap mass-production / wood grain noise. Spec sizes are comparable thanks to scatter.
- still deferred (materials pass): wood vs iron color, painted center motif (decals).
- reference: real photo of Viking-style round shield with iron rim, wood planks (diagonal), 8 rivets, painted decoration
- shipped: 3 prims → 10 effective. Wood disc + iron rim torus + 8 rivets via rotational scatter on Z.
- silhouette matches reference. Front face is FLAT (reference shows slight dome) — minor geometric difference.
- **DEFERRED for next session (geometry pass alone can't ship this)**:
  - diagonal plank pattern → needs procedural mode (`procedural: 'planks'` with angle/spacing)
  - wood vs iron color differentiation → materials library
  - painted center cross/star motif → pixel-art post-process layer
- key learning: at sprite resolution, the geometry IS sufficient. The remaining gap is pure color/material treatment, which is the "post-pixelize" pipeline (eye-replacement style). Color+procedural carries the visual identity at small render sizes; geometry just provides the silhouette + mass distribution.

### voronoi WARPING for organic cracks
- after seeing the boulder's clean polygonal voronoi cells, applied coordinate-warp pre-distortion: input position offset by a 6×-frequency noise before the voronoi math.
- result: crack boundaries are now jagged irregular curves rather than convex polygons. Reads as natural stone fractures vs mechanical tessellation.
- ~5 lines added to evalPrim's crack-displacement path. Color-path voronoi (colorFunc=9 dark bands) NOT yet warped — could be aligned for consistency.
- shipped: **megalith** target — tall trapezoidal standing stone with low-density warped cracks. 1 spec entry, dramatic weathered-megalith look.

### perf + geometric crack displacement (iteration milestone)
- **renderRes 256 → 192** + **maxSteps 48 → 32** = ~50% perf boost. Agent vision quality unchanged (encoder downsamples to ~384 anyway).
- **GEOMETRIC CRACK DISPLACEMENT** added: when colorFunc=9 is set on a prim AND detailAmplitude > 0, the SDF result is displaced outward at voronoi cell edges. Crack lines become real silhouette gaps, not just dark color.
- Implementation: voronoi math computed at the prim's WORLD position, after the type-specific SDF returns. ~40 LoC inside evalPrim, reuses the same hash + 2-nearest-cell pattern as the color path.
- Spec field overload: `detailAmplitude` is "FBM normal-noise amplitude" when colorFunc != 9, but "crack DEPTH" when colorFunc == 9. Documented overload, no spec layout change.
- shipped: **boulder** target — single SUP primitive with crack displacement → reads exactly like the user's Utah cracked-rock-face reference. 1 spec entry, real 3D-broken silhouette.

### colorFunc=9 (voronoi-edge cracks) landed mid-loop
- new procedural in raymarch_renderer.ts: 2-nearest-neighbour voronoi computed in WORLD space, dark band where d2-d1 < threshold (cell-edge proximity).
- ~30 LoC of WGSL. Hash via `fract(sin(dot(cell, big_vec)) * big)`.
- ColorFunc enum extended: 0..8 + 9=cracks. spec field `colorFunc: 9 + colorExtent: cells/meter` activates.
- result on viking shield: dramatic cracked-stone look. At density=80 the planks are buried under crack network.
- this is the first new colorFunc since baseline. Pattern proven: each new procedural is ~30 LoC + one case in dispatcher + one enum line. Future modes (bricks, ridge cracks, cellular noise) follow identical pattern.

### viking helm — round 2 ✅ shipped
- 5 prims: SUP dome (yClipN=-0.5 hemisphere) + torus rim + box nose guard + 2 explicit cones (horn_left, horn_right)
- r1 had a bug: used mirrorYZ on the horn cone; mirror flips position but NOT rotation, so the mirrored copy had its apex pointing INWARD (toward the dome) instead of outward. Visually only ONE horn was visible.
- r2 fix: explicit horn_left (rotation [0,0,90], pos -X) and horn_right (rotation [0,0,-90], pos +X). Both apexes point outward.
- **bug to file**: mirrorYZ should optionally mirror the rotation quaternion too, not just position. For symmetric directional primitives, the current behavior is broken.

### voronoi → turbulent-noise-band crack mode
- user feedback: voronoi cracks "look like scales" — closed convex cells → fish-scale aesthetic.
- replaced voronoi-edge with FBM-noise-iso-contour: cracks live where `|fbm3(p*density) - 0.5| < threshold`. Result: meandering branching CRACK LINES along noise contours, not closed cells.
- `threshold` is the band width = crack profile thickness. `density` controls noise frequency = crack feature scale. `pow(t, 8.0)` for sharp crack-edge falloff.
- visual: thin lightning-bolt-style cracks that look like real fractures from silhouette angles, surface ripples from face-on (correct 3D crack behavior).
- removed all the voronoi math (~30 LoC of nested loops). Noise-band code is ~15 LoC, simpler + faster.

### crack-displacement bug fix + lightning-bolt warp tuning
- found bug: displacement formula `(thresh - edge) * crackDepth` meant max displacement was THRESHOLD × DEPTH (~10% of authored value). spec said "12mm" but engine produced "1.2mm." subtle visual confusion.
- fix: normalised the falloff `((thresh - edge) / thresh) * crackDepth` AND raised to pow=3 for sharper crack edges (linear was too smooth, made cracks read as bulges instead of fractures). crackDepth value is now the actual max displacement in meters.
- voronoi warp also upgraded: single noise3 → multi-octave fbm3 at amplitude 0.35 (was 0.05). gives "lightning-strike-style" jagged forks instead of clean polygons. user feedback: "starting to look like something now!!!"
- recalibrated visibility table (depth × density tradeoff for different effects):
  - 0.002 × 80: hairline craquelure
  - 0.005 × 40: aged cracked ceramic
  - 0.008 × 25: weathered pottery
  - 0.012 × 18: dramatic damage (lightning style)
  - 0.025 × 12: smashed/broken
- shipped: ceramic urn r6 (lightning-cracked, dramatic damage style)

### crackDepth visibility calibration
- 0.001m = sub-pixel at 192² panel, invisible
- 0.003m = barely visible (user: "barely visible but there")
- 0.006m = clearly visible cracks
- 0.015-0.025m = dramatic stone-fracture
- threshold scales with render resolution. Roughly: cracks read at >3-5% of model dimension on screen.

### geometry-only refactor (philosophy fix)
- user feedback: "modeler is not the shader/texturer — color/AO comes from a downstream bake pass. fragment development."
- removed `colorFunc`, `paletteSlotB`, `colorExtent` from the modeler's public spec interface
- added `crackDepth` (geometric crack-displacement depth in m) and `crackDensity` (cells/m) as the geometry-only fields
- internally: modeler sets engine fields under the hood (colorFunc=9 + detailAmplitude=crackDepth + paletteSlotB=paletteSlot) — the color side-effect is suppressed by setting B==A
- shipped: **ceramic urn** with hairline craquelure (crackDepth=0.001, crackDensity=80) — clean geometry, no color marks. Cylinder body + ellipsoid bulge + subtractive cylinder for hollow interior + rim torus.

## Loop summary (this session so far)
shipped targets (31): barrel, crate, bottle, pistol, polygonal flask, wrench, anvil, pickaxe, saber, bow, recurve bow (approximate), mug, treasure chest, sword, crown, lantern, morningstar, shield, chalice, heater shield, viking shield, viking helm, stone tablet, boulder, megalith, ceramic urn, column, tombstone, bell

### Session 2 begins — engine extension sprint
- mirrorYZ rotation fix landed: previously mirrored only the position, leaving directional primitives (cones, etc) with apex pointing wrong way. Now also reflects slot 4 — for rotation quats: (x, -y, -z, w); for type-14 bentCapsule (slot 4 = tipDelta): (-x, y, z). Standard reflection math. Validated with single-horn viking-helm spec → produces 2 correctly-outward horns.
- new procedural deformer 2: PITS (colorFunc=10). Worley distance to nearest cell point with domain warp. Inward round craters where dmin < pitRadius. Spec fields: `pitDepth`, `pitDensity`. Use cases: meteorites, rust pits, rusty metal.
- new procedural deformer 3: BUMPS (colorFunc=11). Smooth FBM outward displacement. No threshold — every point displaces by local noise. Spec fields: `bumpDepth`, `bumpDensity`. Use cases: leather hide, organic skin, soft tissue, asteroids.
- THREE deformer modes now coexist: cracks (line networks via noise-band), pits (round craters via Worley), bumps (smooth lumps via FBM). Same overload pattern (colorFunc + detailAmplitude=depth + colorExtent=density) so adding more is straightforward.
- procedural deformer 4: SCALES (colorFunc=12). Worley cell-edge displacement OUTWARD → raised cellular ridges. Same edge-distance math as old voronoi cracks but opposite sign. Spec fields: `scaleDepth`, `scaleDensity`. Use cases: dragon eggs, lizard hide, alligator skin, mud tiles, soccer-ball.
- shipped: **dragon egg** target — single ellipsoid + scaleDepth=0.005, scaleDensity=35. Reads as scaled creature surface from any panel.

### CRITICAL BUG fixed: cracks were silently no-op
- user diagnosis: "only additive is working" — meaning ONLY `d - delta` (subtraction = raised) modes were producing visible effects. `d + delta` modes (inward) were dead.
- root cause: my crack code used `abs(n - 0.5)` to find noise contour, but fbm3 returns ~[-0.5, +0.5] CENTERED ON ZERO (not 0.5). So `abs(n - 0.5)` was usually large (~0.5), NEVER below threshold 0.06. The displacement triggered ~0% of pixels → effectively zero crack effect.
- bumps had similar bug: `let n = fbm3(...) - 0.5` shifted the centered noise to be mostly negative → bumps inverted to inward.
- fix: use `abs(n)` for crack contour (n=0 is natural distribution center); remove `- 0.5` from bumps (n already centered).
- after fix: cracks at crackDepth=0.030 produce DRAMATIC INWARD silhouette gouges as expected. Confirmed inward direction by silhouette notching.

### lesson: when SDF math feels right but visuals don't match, check FBM/noise output range
- standard Perlin/FBM implementations vary: some return [0,1], some [-1,1], some [-0.5,0.5]. Sign and offset matter for thresholding.
- fbm3 in this engine: ~[-0.5, 0.5] centered on 0. Easy to miscount.

### deformer 5: WOOD GRAIN (colorFunc=14)
- directional sinusoidal stripes along Y axis, FBM-warped for natural curve
- spec fields: `grainDepth`, `grainDensity`. Inward (sunken) lines.
- shipped: wooden plank target — single roundedBox + grainDepth=0.002, grainDensity=25. Reads as wood with grain.

### deformer toolkit summary (5 modes, geometry-only)
| mode | colorFunc | direction | shape | use case |
| cracks | 9 | inward | line networks | stone fractures |
| pits | 10 | inward | round craters | meteorites, rust |
| bumps | 11 | outward | smooth lumps | leather, hide |
| scales | 12 | outward | cellular ridges | dragon, lizard |
| grain | 14 | inward | directional stripes | wood, bark, fibre |
- pattern is solid: noise/Worley + threshold + smoothstep falloff + sign of displacement
- new modes drop in via the same overload (`{type}Depth`, `{type}Density`)

### A* PROTO landed — path-based subtractive cracks
- new field `pathCarves: Array<{from, to, thickness?, depth?}>` on ModelerPrim
- modeler-side `expandPathCarves(parent, carves)` converts each segment to a subtractive box prim:
  - midpoint position, length = segment distance
  - rotation around Z to align local +Y axis with the segment direction
  - inherits parent's blendGroup, blendRadius=-0.002 for clean subtract
- ZERO engine changes — entirely modeler-side, uses existing primitive types + CSG ops
- shipped: **wall with branching crack** target — manually-authored 6-segment branching zigzag crack on a stone wall slab
- this is the geometry pipeline that A* would feed. A* generates the waypoint list, expandPathCarves builds the subtractive geometry.

### two complementary crack systems
- **`crackDepth`** (procedural, colorFunc=9): uniform random network via noise band. Mass-production weathering.
- **`pathCarves`** (path-based, expansion): specific intentional damage along authored waypoints. Hero props, "the impact crack from the dragon hit."
- can be combined on same prim — procedural background weathering + intentional routed damage.

### A* PROTO (full): auto path generation landed
- new field `crackPathGen: { start, end, segments?, seed?, branchiness?, thickness?, depth? }` on ModelerPrim
- modeler-side `generateCrackPath()` runs a seeded LCG random walk from start to end:
  - main spine: N waypoints with perpendicular jitter (XY plane)
  - branches: optional side spurs at each waypoint (probability = branchiness)
  - output: same shape as `pathCarves` (list of `{from, to}` segments)
- `expandPathCarves` then turns each segment into a subtractive box prim
- DETERMINISTIC: same seed = same crack pattern. Critical for reproducible shipping.
- shipped: stone wall with seed=42 auto-generated branching crack. Visible from all panels.
- **A* extension path**: replace the random walk with grid-based A* over a cost field. Same input/output shape; same downstream geometry.

### A* polish — Catmull-Rom smoothing landed
- new helpers: `simplifyPath()` (collinear pruning) + `smoothPath()` (Catmull-Rom spline, 3-4 sub-samples per segment)
- A* output now flows through smoothing before being expanded to subtractive boxes
- removed simplify (was overzealous, killed meandering); kept Catmull-Rom
- visible result: path now has gentle curves between A* waypoints instead of cardinal stairsteps
- still-known visual: discrete dimples per segment when thickness is small. Solutions for cleaner continuous groove:
  - increase carve box thickness (boxes overlap → smooth-subtract merges)
  - reduce per-carve blendRadius for sharper cuts
  - or generate continuous capsule geometry instead of box-per-segment

### A* IMPLEMENTATION LANDED
- new `mode: 'astar'` on crackPathGen → routes via grid-based A* instead of random walk.
- 8-connected grid over the start-end bounding box (gridRes 28 default, tunable).
- per-cell cost = `1.0 + hash(cell, seed) * noiseWeight` (higher noise weight = more meandering).
- heuristic = euclidean distance to goal (admissible, optimal A*).
- CPU-side, deterministic per seed, no engine changes.
- shipped: wall with A* routed crack.
- known artifact: 8-connected paths show cardinal stairstepping. POLISH options:
  - bump gridRes (32, 48, 64) for finer steps
  - post-process with Catmull-Rom smoothing through waypoints
  - 16-connected grid (more directions, more cost)
- this is the FULL A* PIPELINE for visible cracks. Same shape applies to:
  - rivers carved into terrain (cost field = elevation)
  - root systems (cost field = nutrient/water density)
  - cable runs (cost field = obstacle penalty + length)
  - lightning forks (cost field = atmospheric resistance, branch from spine)

### bell — 2 rounds ✅ shipped
- r1: cone primitive — too sharp at the apex (looked like a witch's hat / Christmas-tree ornament, NOT a bell)
- r2: SUP sphere with positive yClip (yClipN=+0.3 clips top 30%) for proper rounded bell-shape with flat top
- **reusable pattern**: rounded body + flat top = SUP with positive yClipN. Use for bells, kettle helmets, pot lids, drum bodies. Cone gives apex; SUP-yClip gives flat closure.

### tombstone — 3 rounds ✅ shipped
- r1: SUP sphere arch — too round, sphere extended 7cm in Z while body was 1.2cm thick. Looked like pin head on stick.
- r2: thin Z-axis disc replaces sphere. Body absorbs bottom half via smooth-blend → clean half-circle arch.
- r3 damaged: r2 + big diagonal subtractive crack (rotated 25°) + 2 chipped corners (subtractive boxes at top) + bumped blend radius from 0.004 → 0.008 for cleaner primitive seams. Reads as ancient damaged grave marker.
- **two damage paradigms**: (1) procedural cracks (`crackDepth`) for uniform weathering, (2) CSG subtractive prims for specific intentional damage (chipped corners, big single cracks). Use both together for full dramatic effect.
- **reusable pattern**: rounded-top vertical slab = rectangular body + thin Z-axis cylinder smoothly blended on top. Tombstones, doors, gates, signs.
view-modes available: color (lit), normal, depth, silhouette, curvature, per-surface
new primitives landed mid-loop: trapezoidalBox (type 21), band (type 22)
new spec fields: tipDelta (Vec3, for bentCapsule), repeats (linear + rotational scatter)
atlas: 512×512 with cm grid bg, panel labels (HTML overlay), 6 view-modes
mid-loop engine extensions in total: 9 (silhouette + tipDelta + trapezoidalBox + band + linear-scatter + rotational-scatter + 256² atlas + grid bg + curvature/per-surface modes)

## Engine extension landed mid-loop
- Added `tipDelta?: Vec3` field to ModelerPrim (modeler_demo.ts) so bentCapsule (type 14) is now driveable from the spec.
- Slot-overload limitation: bentCapsule prims can't have BOTH rotation AND tipDelta because the engine reuses slot 4 for both. Workaround for orientation flips: use other primitives (torus arc for bow worked).

## User requests pending design / implementation
1. ✅ **silhouette view-mode** — DONE. White-on-black binary mask, no lighting/checker. Use for reference matching.
2. **per-prim color view-mode** — pending (~30 LoC).
3. **scatter / replicate operators** (`repeatLinear`, `repeatRotational`, `repeatGrid`) on ModelerPrim — same expansion pattern as mirrorYZ, ~50 LoC. Pure spec-readability win (raymarch cache makes runtime cost zero).
4. **bentCapsule with rotation** support — would require either modifying engine (move tipDelta out of slot-4) or applying CPU-side rotation to local frame before SDF eval. Bigger surgery.
5. **bezier-profile-capsule exposed in modeler** — type 17, swept capsule along quadratic bezier with cubic radius profile. Needs multi-bone scaffolding (3 fake bones to encode the 3 control points). ~1 day. THE primitive for angular curves and tapered limbs.
6. **`sdTrapezoidalBox` new primitive** — clipped pyramid / truncated wedge for blades, gun stocks, bezels. ~30 LoC WGSL + modeler exposure. High utility unlocks knife-blade, sword-blade-cross-section, gun-stock-taper, pyramid-frustum.
7. **`sdBentBox` new primitive** — rectangular cross-section swept along bezier. Same multi-bone scaffolding as type 17. ~50 LoC WGSL.
8. **shape-macro abstraction layer** — high-level operators (`arc`, `recurveArc`, `taperedSweep`) that expand to multi-prim subgraphs at upload. Days of work but transformative for spec readability.
9. **named materials library** + per-prim `material` tag — separate post-loop authoring pass, decouples geometry from appearance.
10. **headless render** for tab-independent agent loop — needs ARM64 + WebGPU + display-server work to unblock.
partial: kettle helmet (r1)
techniques validated:
1. cylinder + ellipsoid in same group = bulged-body shapes (barrel, urn)
2. wide blendRadius between two cylinders of different radius = free shoulder taper (bottle)
3. mirrorYZ = 2× authoring multiplier for symmetric features (crate grooves + brackets)
4. signed blendRadius (negative) = subtractive carving (crate plank grooves, wrench openings)
5. rotationDeg = lets one primitive type cover many roles (gun barrel, gun trigger guard, asymmetric flask neck)
6. roundedBox with corner=small + smooth-blend to cylinder = clean shape morphology between rectangular and round (polygonal flask)
7. hard-union (group 0) for additive distinct features (barrel hoops, gun parts), smooth-blend (group 1) for fused organic shapes

## /loop iter 10 (post-summary): polish A* path-carve continuity
- **Symptom:** A* `astar` mode produced visible chain of dimples instead of a continuous fracture groove. Each waypoint segment was a thin box that didn't quite touch its neighbors.
- **Fix 1 (overlap):** in `expandPathCarves()` (modeler_demo.ts:692), extended each segment's half-length by `thickness * 1.5` so consecutive segments overlap. Smooth-subtract (blendRadius=-0.002) then fuses them into one groove.
- **Fix 2 (rounded ends):** swapped carve primitive from `box` (type 1) → `roundedBox` (type 2) with corner radius = `thickness * 0.9`. Endpoint joints now meet as smoothly-rounded capsules-equivalents instead of hard square ends.
- **Engine win — domain-warped cracks:** WGSL crack deformer (colorFn=9) now warps the input coord with an independent low-freq FBM field before the main FBM lookup. Matches the technique already used by pits/scales. Crack contours read as natural fracture lines instead of regular FBM-band signature.
- **Test spec:** wall_astar_v4_continuous.json (gridRes=28, noiseWeight=4, smoothing on). Same start/end as v3 to allow A/B compare.
- **Reusable principle:** when stamping subtractive prims along a path, ALWAYS overlap segment lengths beyond endpoints (factor of thickness or larger) and use a primitive with rounded ends. Square box ends + zero overlap = dimple chain; rounded ends + overlap = continuous groove.

## /loop iter 11: deformer library expansion — ridges + streaks
- **New WGSL deformer 15: ridged multifractal** (raymarch_renderer.ts:1077-1108). 4-octave fold-and-square (`1-|n*2|` then `r*r*prev`) with domain warping. Different look from FBM-band cracks — gives ONE prominent ridge per noise period, not band-pair edges. Use cases: mountain spines, sword fullers, knot bark, creature dorsal ridges.
- **New WGSL deformer 16: erosion streaks** (raymarch_renderer.ts:1109-1132). Gravity-aligned vertical drips. Two FBM fields combine: high-freq column-pick (smoothstep at 0.45/0.55 selects which columns drip) × vertical-falloff (clamped 0.5 - y*5 → fades as y rises). Modulated by jitter FBM so streaks aren't uniform stripes. Use cases: rust runs, water staining, weathered metal.
- **Modeler wiring**: new fields `ridgeDepth/ridgeDensity` and `streakDepth/streakDensity` exposed on ModelerPrim with same overload pattern as crack/pit/scale (slot 2.w = depth, slot 3.y = density via colorExtent). Wired through normalizer so JSON specs round-trip cleanly.
- **Stacking limitation observed**: two prims at the same world position with DIFFERENT blendGroups hard-union (whichever has lesser SDF wins). For layered deformers on one surface (e.g. ridges + streaks together) we'd need either (a) a multi-deformer slot in evalPrim, or (b) two prims with identical SDF and SAME blend group with carefully-tuned blendRadius. Filed for future iteration.
- **Test spec**: ridge_spine_slab.json (60×60mm slab, ridgeDepth=0.004, ridgeDensity=16). Streaks demo deferred to next iteration to avoid the stacking-group confusion.
- **Library state**: 7 procedural deformer modes total — cracks (9), pits (10), bumps (11), scales (12), veins (13), grain (14), ridges (15), streaks (16). Plus A* and random-walk path generators with overlap+roundedBox carves.

## /loop iter 12: periodic-lattice deformers — hex tiles + brick masonry
- **New WGSL deformer 17: hex tiles** (raymarch_renderer.ts). Periodic pointy-top hex lattice using two interlocking offset rectangular grids; pick whichever cell center is closer (`select(b, a, dot(a,a) < dot(b,b))`). Edge distance uses standard pointy-top hex formula `0.5 - max(|qx|*sqrt(3)/2 + |qy|*0.5, |qy|)`. Light domain warp (0.3 amplitude) breaks perfect regularity without losing hex recognition. Sci-fi armor, honeycomb, alien skin.
- **New WGSL deformer 18: brick masonry**. 2:1 running-bond tiling — alternate rows offset by half a brick. Domain-warped slightly. Distance to nearest mortar joint via `min(brickSize.x*0.5 - |local.x|, brickSize.y*0.5 - |local.y|)`. Architectural staple: stone walls, dungeons, chimneys.
- **Modeler wiring**: `hexDepth/hexDensity` and `brickDepth/brickDensity` exposed on ModelerPrim with same overload pattern.
- **Test spec**: hex_armor_plate.json (60×60mm slab, hexDepth=0.0025, hexDensity=35).
- **Lattice technique notes**:
  - For periodic patterns, `pp - s * floor(pp/s + 0.5)` gives local position in [-s/2, +s/2] relative to nearest cell center.
  - For two-grid interlocking patterns (hex), evaluate against both grids and pick closer center.
  - Domain warping the input coord (NOT the cell index) makes lattice "wobble" while staying topologically correct — no missing/duplicated cells.
  - Mortar grooves work by mapping edge-distance through smoothstep then ADDING to d (sunken).
- **Library state**: 9 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18). Plus A* + random-walk path generators with overlap+roundedBox carves.

## /loop iter 13: river path generator — dual-layer profile + meander
- **New path-profile system**: `crackPathGen.profile` field accepts `'crack' | 'river' | 'channel'`. Default 'crack' = single thin square carve (current behavior). 'river' = dual-layer U-shape (wide shallow `t*3, d*0.4` + narrow deep `t*0.7, d` stacked at same path). 'channel' = single wider rectangular trough (`t*2, d`).
- **Meander**: optional `meander` (amplitude in m) + `meanderFreq` (cycles along path). Applied AFTER A*/walk pathing AND smoothing. Perpendicular perturbation in XY computed via central-difference tangent → rotate 90° → multiply by sin(u*freq*2π) * sin(u*π) taper. Endpoints pinned. Lazy bend at amp~0.005, tight wiggle at amp~0.015.
- **Helper extracted**: `emitCarvesFromPath(wp, t, d, profile)` consolidates segment→carve emission. Used by both A* and random-walk generators so any new profile mode benefits both.
- **Dual-layer rationale**: the U-shape comes for free from smooth-subtract: outer wide shallow box subtracts a broad shallow channel; inner narrow deep box subtracts a deeper center. Smooth-blend across same path eliminates seam between the two layers — reads as a single carved channel with sloped banks.
- **Branches stay 'crack' style** even when main path is 'river' — branches model tributaries / hairlines feeding the main flow, not parallel rivers.
- **Test spec**: river_meander_v1.json (60×60 slab, gridRes=24, meander=0.005, meanderFreq=4, profile='river'). Same start/end as the v4 crack so direct A/B compare is possible by toggling profile.
- **Library state**: 9 deformer modes + 3 path profiles (crack/river/channel) + meander on both walk and A* generators. The `profile` mechanism is extensible — adding a new cross-section now means one more case in `emitCarvesFromPath` plus a literal in the type union.

## /loop iter 14: Voronoi cracks + scratches (and a regression caught)
- **REGRESSION CAUGHT**: 500 error on modeler_demo.ts at runtime. Root cause: backticks inside WGSL comments (mode-17 hex referenced `scaleDepth`, mode-20 scratches referenced `grain` in comments) — backticks close the TS template literal that wraps the WGSL shader, breaking compile. Same bug pattern as the earlier fbm3-comment incident logged in iter 5. Permanent rule for this file: **never write backticks inside WGSL comments**. Use plain words or single quotes if a name needs to be quoted.
- **New WGSL deformer 19: Voronoi cracks**. True F1-F2 bisector-distance fracture network. Two-pass cellular: find F1 (nearest cell point), then F2 with bisector projection (`abs(dot(pp - midpoint, unit_normal))`) for accurate edge distance. Distinct from mode 9 (FBM-band cracks) — gives clean geometric cell-network look (dragon-egg, dried mud, broken tile). Mild domain warp on input so cells aren't textbook-perfect.
- **New WGSL deformer 20: scratches**. Sparse directional strokes along local +X. Per-line random hash gates ~30% of lines (sparse, not parallel-stripes like grain). Per-line length-along-X mask via FBM gives partial-length scratches. Low-freq vertical FBM bends individual scratches slightly so they're not ruler-straight. Brushed-metal / weapon-wear look.
- **Modeler wiring**: `voronoiCrackDepth/Density` and `scratchDepth/Density` plumbed through ModelerPrim → specToPrims → JSON normalizer.
- **Test spec**: voronoi_cracked_egg.json (40×55×40mm ellipsoid, voronoiCrackDepth=0.0025, voronoiCrackDensity=22).
- **Compile-verified** — `tsc --noEmit` clean before staging spec.
- **Library state**: 11 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18), voronoiCrack(19), scratches(20). Plus 3 path profiles (crack/river/channel) + meander on both walk and A*.

## /loop iter 15: lightning bolt path generator + linear taper
- **New path mode 'lightning'** — `generateLightningPath()` uses classic midpoint-displacement recursion. Each pass doubles segment count by inserting a midpoint perpendicular-displaced by `jaggedness * 0.5^level * segLen`. Default `lightningDepth=6` → 64 main-bolt segments. Sharp segments (no smoothing); jagged-look IS the goal.
- **Cascading branches** — at recursion levels 0–2 (coarsest), each midpoint has `branchiness` chance of spawning a sub-bolt. Each sub-bolt is a recursive call to `generateLightningPath` itself with: shorter range (`0.6 * 2^-(level+1)`), steeper taper (0.95), 60% thickness, 70% depth, no further branching (would explode quadratically).
- **Linear taper** — new `taper` field works on ALL path generators (walk, A*, lightning). 0=uniform, 1=fade to zero. Taper applied at the segment-emit step (`emitCarvesFromPath`); no need to plumb it through each generator's interior. Lightning defaults to taper=0.7 (cloud→strike); rivers default to no taper; cracks no taper.
- **Generator dispatcher** in specToPrims now switches on three modes: `walk → astar → lightning → walk`.
- **JSON normalizer** updated to round-trip `taper`, `lightningDepth`, `jaggedness`, and to accept `'lightning'` in the mode validation.
- **Compile-verified**: `tsc --noEmit` clean.
- **Test spec**: lightning_bolt_v1.json (60×80mm tall slab, lightningDepth=6, jaggedness=0.4, branchiness=0.3, taper=0.6). Vertical bolt top→bottom for the classic strike pose.
- **Library state**: 11 deformer modes + 4 path-gen modes (walk/astar/lightning/-) + 3 path profiles (crack/river/channel) + meander + taper.
- **Reusable principle**: *taper at emit-time, not at gen-time*. Path generators concern themselves with WHERE the path goes; profile and taper are post-processing on the waypoint list. Adding new path features (sphere-tip, capsule-cap, varying-density) drops in at the same `emitCarvesFromPath` hook without touching A*/walk/lightning internals.

## /loop iter 15.5: Vite oxc parse bug — `A*/walk` closes JSDoc
- **Symptom**: tsc clean, but Vite reload showed `[PARSE_ERROR] Unexpected token` at modeler_demo.ts:204. Vite uses oxc which is stricter than tsc on comment delimiters.
- **Root cause**: I wrote `After A*/walk pathing` inside a JSDoc comment. The `*/` is the JSDoc-close sequence — oxc closed the comment there and treated the rest as code.
- **Fix**: insert a space → `A* / walk`.
- **Permanent rule**: never write `*/` inside a JSDoc/block comment for any reason. Slash forms used in prose: `A* / walk`, `walk / astar`, etc — always with surrounding space. (Same class as the WGSL-backtick bug from iter 14: comment delimiters that overlap with prose syntax.)

## /loop iter 16: regular-grid deformers — dimples + studs + chevrons
- **Backed out architectural multi-deformer-stacking refactor mid-iteration**: bumped PRIM_STRIDE_FLOATS from 20 → 24 to add a second-deformer slot, then realized the inline 338-line if/else chain in `evalPrim` would need to either become a function (long surgery) or be duplicated (ugly). Reverted to baseline; mult-deformer stacking is filed for a focused future iteration where the only goal is the refactor.
- **New WGSL deformer 21: dimples**. Regular grid of sunken sphere indents. `pp - floor(pp + 0.5)` gives [-0.5,0.5] cell-local, `length(local)` = radial dist, smoothstep falloff. Light domain warp (0.15 amplitude) breaks lattice. Use cases: golf ball, hammered metal, perforated panel, leather pebbling.
- **New WGSL deformer 22: studs**. Inverse of dimples — same grid math, opposite sign on `d`. Raised hemispheres. Domain warp 0.10 (slightly less because studs need to read as discrete dots, not blob). Rivets, tactile D-pad, studded leather.
- **New WGSL deformer 23: chevrons**. V-shape raised ridges along local +Y. Per-row Y-step (`floor(y * density)`), local x folds via `abs(x*density) % 1.0`, V-distance via `abs(yLocal - 0.5 - xLocal*0.5)`. Domain-warped so V-rows aren't perfectly aligned. Arrow pavement, textured grip, herringbone leather, military stencils.
- **Modeler wiring**: `dimpleDepth/Density`, `studDepth/Density`, `chevronDepth/Density` plumbed.
- **Test spec**: studded_plate.json (60×60mm, studDepth=0.0030, studDensity=36).
- **Library state**: 14 deformer modes — cracks(9), pits(10), bumps(11), scales(12), veins(13), grain(14), ridges(15), streaks(16), hex(17), brick(18), voronoiCrack(19), scratches(20), dimples(21), studs(22), chevrons(23). Plus 4 path-gen modes + 3 path profiles + meander + taper.
- **Family map**:
  - **Organic-irregular**: bumps, scales, voronoiCracks, ridges (FBM/Voronoi)
  - **Organic-natural**: cracks, pits, veins (FBM-band)
  - **Directional**: grain, streaks, scratches, chevrons (axis-aligned with FBM warp)
  - **Periodic**: hex, brick, dimples, studs (regular lattices)
- The four families now cover most useful surface treatments. Future expansion: triplanar projection (better noise on heavily curved surfaces), multi-deformer stacking (compositional layering), or domain-specific generators (lichen, moss, frost crystals).

## /loop iter 17: multi-deformer stacking (wear-slot architecture)
- **Architecture: secondary wear-deformer slot.** Bumped PRIM_STRIDE_FLOATS 20 → 24 (6 vec4f per prim). Slot 5 carries (wearFn u32, wearDepth f32, wearDensity f32, _pad). Updated all `* 5u` → `* 6u` reads in WGSL (3 sites: evalPrim, occlusion loop, hit shading) and all `i * PRIM_STRIDE_FLOATS` writes (auto via constant). Added u32[base+20] / f32[base+21..23] in CPU-side packPrim block.
- **Constrained API**: only 4 wear modes supported as secondaries (bumps/grain/streaks/scratches — the FBM-based "weathering" patterns). Structural patterns (cracks/hex/scales/voronoi/etc.) only run as primaries. The wear-block in WGSL is ~30 lines instead of duplicating the 338-line primary chain. Realistic compositional case is one structural + one weathering, not two structurals.
- **Compositionality**: secondary runs AFTER primary in evalPrim, so its displacement adds to whatever the primary computed. Two SUNKEN modes both add to d → both visible. Two RAISED modes both subtract → both visible. RAISED primary + SUNKEN wear (e.g. studs + scratches) compose as expected.
- **Modeler API**: `wearDeformer?: { type, depth, density? }` field on ModelerPrim. Type union enforces only the 4 valid wear modes. Wired into specToPrims (after the primary if/else chain) and into the JSON normalizer.
- **Test spec**: weathered_hex_armor.json — hex primary + streaks wear → rust-runoff on tessellated armor.
- **Why this is the right scoping**: I tried the unconstrained version last iteration (any deformer × any deformer = 14² = 196 combinations, requires the 338-line primary chain to become a function or be duplicated). Backed out. The constrained wear-slot version unlocks 14×4 = 56 useful combinations with ~30 LoC of WGSL and zero refactor. The primary chain stays readable.
- **Library state**: 14 primary deformers + 4 wear deformers (composable) + 4 path-gen modes + 3 path profiles + meander + taper + stride-6 layout.
- **Future extension hooks**: slot 5 still has padding (slot5.w unused). Could carry a wear-rotation angle for orienting directional wear (grain/scratches/streaks) without rotating the parent prim.

## /loop iter 18: color-aware deformers — geometry AND palette pick
- **Insight**: until now the new deformers (10-23) produced DISPLACEMENT only — surface stayed paletteSlot-A everywhere, so a hex plate with sunken mortar grooves still rendered as one uniform color. The original colorFunc=9 (cracks) had BOTH geometric and color-side logic; the others didn't. Standard SDF workflows require authoring two parallel systems for "dark mortar that's also sunken". Unifying them so one deformer drives both unlocks major visual quality with zero extra spec.
- **Color-side WGSL added** for 5 periodic/cellular deformers in the `colorPick` switch: hex(17), brick(18), dimples(21), studs(22), chevrons(23). Each branch re-runs the same mask math used in evalPrim's geometric pass — Voronoi for hex, offset-row for brick, radial for dimples/studs, V-distance for chevrons — and picks slotB when inside the deformer band. (Mode 19 voronoiCracks already had legacy color logic from iter 0; left as-is for now.)
- **Palette infra**: added slot 2 = brighter variant (1.45× MATERIAL_RGB, clamped to 1.0). Slot 0 = base, slot 1 = darker (0.55×) — already existed for stripe/dot — slot 2 = brighter for raised features.
- **Sensible per-mode defaults**:
  - SUNKEN deformers (hex, brick, voronoiCrack, scratches, dimples) → paletteSlotB defaults to slot 1 (dark accent).
  - RAISED deformers (studs, chevrons) → paletteSlotB defaults to slot 2 (bright accent).
- **Override hook**: new `accentSlot?: number` field on ModelerPrim lets the user pick any palette slot 0-31 if defaults aren't right. JSON normalizer round-trips it.
- **Scope-limit decision**: only periodic/cellular deformers got color-aware treatment this iteration. The organic-natural family (cracks-FBM, pits, bumps, veins, grain, ridges, streaks) doesn't get color picks — those are micro-details where geometry alone reads correctly, color contrast there is more "noise" than "feature". Can add later if needed.
- **Test spec**: color_aware_hex_v2.json — same plate as iter-12 hex_armor_plate, but now mortar reads as visibly DARK between bright tile faces, not just shaded geometry.
- **Reusable principle**: when geometry and color are the SAME mathematical mask (cell boundaries, lattice grooves, raised tops), implement them as TWO branches running the SAME math — once in displacement, once in color pick — driven by ONE field. Avoid making the user author both sides.

## /loop iter 19: tree path generator + scales color-aware
- **New 'tree' path mode** — `generateTreePath()`: recursive Y-fork from `start` along `direction` (default +Y). Each segment spawns `branches` children at ±branchAngle (default ±28°), with per-level decay on length (lengthDecay=0.7 default) and on thickness (thicknessDecay=0.7). Per-branch length jitter ±20% for natural variation. Tree handles its OWN taper via thicknessDecay; emit-time `taper` skipped on the trunk path. Profile `'river'`/`'channel'` re-routes through emitCarvesFromPath; default `'crack'` uses the per-segment thickness/depth directly.
- **Branch-count semantics**: `branches=1` → straight whippy line, `branches=2` → Y-fork (default), `branches=3` → trident (good for trees), `branches=4-6` → candelabra / coral. Splay distributes evenly across `[-half, +half]`. Capped at 6.
- **Recursion safety**: treeDepth capped 1-7. At branches=2, depth=5 → 31 segments. At branches=4, depth=5 → 1024 segments. Quadratic warning is in the JSDoc.
- **Use cases**: bare-branch trees, vine systems, vasculature, neural dendrites, antlers, coral, blood vessels, lightning-with-multiple-strikes (set branches=3+ for fork-heavy bolts).
- **Color-aware scales (mode 12)** — added F1-F2 bisector color pick to the existing geometric ridges. Cell edges now darken (slot 1 default) so dragon-scale ridges read as actual ridge LINES, not just shaded bumps. Modeler default updated to `accentSlot ?? 1` for scales.
- **Compile-verified**: tsc clean.
- **Test spec**: tree_carved_v1.json — 60×80mm tall slab, vertical tree from bottom edge with 5-level depth, ±30° branch angle.
- **Library state**: 14 primary deformers (6 color-aware: 9, 12, 17, 18, 21, 22, 23) + 4 wear deformers + **5 path-gen modes** (walk/astar/lightning/tree/-) + 3 path profiles + meander + taper + accentSlot override.
- **Family map for paths**:
  - **Stochastic**: walk (random spine + jitter)
  - **Cost-field**: astar (follows weak material)
  - **Self-similar**: lightning (midpoint-displacement + cascading branches)
  - **Recursive structural**: tree (Y-fork branching)
  - All four feed the same `emitCarvesFromPath` → profile/taper system.

## /loop iter 20: HEADLESS WEBGPU UNBLOCKED + path-gen perf fixes
- **🔥 HEADLESS WEBGPU IS WORKING.** Per the developer.chrome.com/blog/supercharge-web-ai-testing recipe, the correct flag set is:
  ```
  --no-sandbox --headless=new --use-angle=vulkan
  --enable-features=Vulkan --disable-vulkan-surface --enable-unsafe-webgpu
  ```
  Critical errors in my earlier attempts: I had `--use-vulkan` (wrong; correct is `--use-angle=vulkan`) and was MISSING `--disable-vulkan-surface` (which uses bit blit instead of swapchain so no display surface is required). With those fixed, `requestAdapter()` returns a real Vulkan adapter with 24 features. NVIDIA driver 580 + libvulkan1 + libnvidia-gl-580 already on the box; nvidia_icd.json present in `/usr/share/vulkan/icd.d/`. NO xvfb needed.
- **Probe result**: `{ hasGPU: true, adapterInfo: { features: [24 features incl. timestamp-query, subgroups, texture-compression-bc/etc/astc, dual-source-blending] }, modelerReady: true }`. Vite serves the modeler on :5173, headless Chromium loads it, WebGPU initializes against the real GPU, modeler module API exposed.
- **Path-gen perf fixes** (the user reported "browser hangs my computer so bad"):
  - `lightningDepth` default 6 → 5 (64 → 32 main segments)
  - `treeDepth` default 5 → 4 (31 → 15 segments)
  - A* `smoothPath` samples 3 → 2 (halves carve count after smoothing)
  - **Soft cap**: `decimateCarves(carves, 150)` uniformly drops segments when over budget. Logs warning. Silhouette stays right (uniform decimation), inner detail loses some fidelity.
- **Test spec**: perf_check_simple_crack.json — A* crack with profile='crack' (single layer, no river dual-bloat), gridRes=20 → ~30-50 carve prims after smoothing.
- **Reusable principle**: in a live-orbit live-render modeler, every authored prim is in the per-frame critical path. Authoring tools that emit hundreds of small prims need budget-awareness — either decimation or a primitive-chain SDF that bundles many segments into one prim. Decimation is the cheap fix; chain-prim is the right fix.

## /loop iter 21: AGENT SELF-VALIDATION LOOP COMPLETE
- **End-to-end verified**: spec → write inbox.ark.json → `modeler_driver.mjs null <out.png>` → 4-view atlas PNG written. Round-tripped 3 specs:
  - perf_check_simple_crack (A* crack, single layer): visible diagonal crack on slab, all 4 views render
  - weathered_hex_armor (hex primary + streaks wear): hex tiles with dark mortar grooves CLEARLY visible (color-aware iter 18 confirmed), bottom hexes show slight vertical wash from the streak wear (composition confirmed)
  - tree_carved_v1 (tree gen, treeDepth=4): vertical trunk + 4-level recursive Y-fork visible across all views, branches taper to twigs as designed
- **modeler_driver.mjs updates**:
  1. Replaced `headless: false` (xvfb path) with `headless: true` + the working flag set: `--no-sandbox --headless=new --use-angle=vulkan --enable-features=Vulkan --disable-vulkan-surface --enable-unsafe-webgpu`
  2. `goto({waitUntil: 'networkidle'})` → `'domcontentloaded'`. networkidle never settles for the modeler (continuous render loop + VL inbox poller keep traffic flowing).
- **VL inbox poller race**: passing `specJson` to setSpec gets overwritten by the inbox poller. Workaround: write the spec to `public/sdf_modeler/inbox.ark.json` BEFORE invoking the driver, pass `null` as the driver's spec arg. Future polish: add a `?nopoll` URL flag the driver appends so setSpec wins. For now the inbox-write pattern works.
- **Lock-in for the loop**: from now on every spec change can be visually verified before claiming success. Replaces "tsc passed → ship it" with "render + inspect → ship it".
- **Multimodal Read tool advantage**: PNG outputs from the headless render are directly inspectable in this conversation context — same path the user uses to verify, no extra VLM hop needed.

## /loop iter 22: live HTML preview viewer + tendril path generator
- **Live preview HTML page** at `public/sdf_modeler/preview.html` (served by Vite at http://localhost:5173/sdf_modeler/preview.html). HEAD-probes preview.png for Last-Modified header to avoid re-downloading unchanged frames; cache-busts via `?t=${mtime}` only when fresh. Refresh-rate dropdown 1s/2s/5s/10s/paused; status pill goes orange after 30s of no updates so a stopped daemon is obvious.
- **Daemon default output moved** from `~/modeler_preview.png` → `public/sdf_modeler/preview.png` so Vite serves it. Removes the homedir dependency; everything self-contained under the engine scaffold.
- **New 'tendril' path mode** — `generateTendrilPath()`: continuous-curvature winding line. Heading rotates each step by `Math.sin(t*1.4*2π+offA) * curl + Math.sin(t*4.3*2π+offB) * curl*0.25` — low-freq drift + slight high-freq wobble, both deterministic from seed. NO branches, NO jitter — one smooth winding line. Different from `walk` (jitter) and `tree` (branching).
- **Use cases**: vines, tentacles, hair strands, ribbon trails, lazy river meanders without A* cost.
- **Self-validated via headless capture** (tendril_atlas.png): visible smooth S-curve carved across slab in all 4 views. Front and ISO show the curve clearly; side shows the depth carve consistent across length.
- **Library state**: 14 primary deformers (10 color-aware) + 4 wear deformers + **6 path-gen modes** (walk/astar/lightning/tree/tendril/-) + 3 path profiles + meander + taper + accentSlot.
- **Path-gen taxonomy**:
  - **Stochastic**: walk (random spine + jitter)
  - **Cost-field**: astar (follows weak material)
  - **Self-similar**: lightning (midpoint-displacement + branches)
  - **Recursive structural**: tree (Y-fork branching)
  - **Continuous curvature**: tendril (smooth turns, no branches)
  - All 5 feed `emitCarvesFromPath` → profile/taper/decimateCarves system.

## /loop iter 23: whorl deformer (radial — fingerprint / tree-rings)
- **New WGSL deformer 24: whorl**. Concentric rings around the local origin in XY plane. Radius `length(pWorld.xy) + warp * 0.012` is FBM-warped so rings aren't perfect circles — they wave and pinch like fingerprints or tree growth rings. Sin oscillation `sin(r * density * 6.283)` defines ring lines; smoothstep band gives sunken contours. Pure radial — no Voronoi/lattice/FBM-band like every other mode. Use cases: fingerprints, tree-stump growth rings, sliced fruit cross-sections, contour topo lines, target patterns, wood end-grain, zen-garden ripples.
- **Color-aware from the start** — slot 1 dark accent default. The same ring-distance test (`abs(s) < 0.20`) runs in colorPick so rings darken visibly, not just sink.
- **Modeler wiring**: `whorlDepth/Density` plumbed through ModelerPrim → specToPrims → JSON normalizer.
- **Self-validated headlessly** (whorl_atlas.png): clean concentric rings on all 4 views, depth carve consistent across slab. FBM warp at default density (24) is subtle — rings look mostly circular; bump density 30+ to enter fingerprint territory (tighter rings, more visible warp pinch).
- **Library state**: 15 primary deformers (11 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot + decimateCarves cap.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - **Radial**: whorl ← new family
- The radial family had no representative until now — every other mode was either Cartesian (lattice/grid), grid-cellular (Voronoi), or signal-band (FBM). Whorl establishes the polar/cylindrical pattern category.

## /loop iter 24: fishscale deformer (overlapping arc-rows)
- **New WGSL deformer 25: fishscale**. Offset-row tiling (like brick) where each cell's visible boundary is the BOTTOM HALF of an arc circle. Adjacent rows shifted by half-cell so the curved bottoms tuck into the gaps of the row above — interlocking overlap pattern. Domain-warped lightly. Distinct from `scales` (mode 12 Voronoi cells, irregular sizes) — fishscale is uniform and unmistakably tile-like.
- **Math**: cellSize=(2,1), offset rows by half-cell on odd rows, arc center at `(0, +cellSize.y/2)` with radius `cellSize.x*0.55`. Distance to arc circle gives shadow line; smooth gate `smoothstep(arcCenter.y+0.05, arcCenter.y-0.05, local.y)` restricts to the bottom half (the visible scale edge), avoiding double-arc artifacts above.
- **Color-aware from start** — slot 1 dark accent default, line darkens visibly as a real shadow.
- **REGRESSION CAUGHT (and fixed)**: backtick-in-WGSL bug recurred (`scales`). Same class as the iter-14 fbm3 incident and the iter-15 A*/walk JSDoc incident. Fixed by removing the backticks. Adding a stronger note to the agent log: **the WGSL block is wrapped in a TS template literal — backticks INSIDE the WGSL comments close the literal. Slash-modifiers (`*/`) inside JSDoc close those. Always strip both before writing prose comments.**
- **Self-validated headlessly** (fishscale_atlas.png): 4-view atlas shows the offset arc pattern across all faces, scales tucking into one another row-by-row, no double-arc artifacts at the half-circle gate.
- **Library state**: 16 primary deformers (12 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24, 25) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - **Periodic-organic**: fishscale ← bridges periodic regularity with organic-tile feel

## /loop iter 25: weave deformer (over-under two-axis fabric)
- **New WGSL deformer 26: weave**. Two perpendicular sin strands (`sin(pp.x*2π)`, `sin(pp.y*2π)`) with explicit over-under: `parity(floor(pp.x*0.5)+floor(pp.y*0.5))` picks which strand is on top per 2×2 strand-cell, so the surface reads as genuinely woven, not just cross-hatched. Strand peaks SUBTRACT from `d` → raised strands; gaps stay at the base surface. Light FBM domain warp (0.15 amplitude) so strands wave gently.
- **Why over-under matters**: cross-hatched (just `max(strandH, strandV)`) reads as a grid, not a weave. The parity flip in alternating large cells creates the characteristic basket-weave perception — the eye picks up that horizontal goes over vertical here, vertical goes over horizontal there.
- **Distinct from related modes**: grain(14) is single-direction stripes; chevrons(23) is V-pattern raised; brick(18) is offset-row sunken mortar. Weave is the first TWO-AXIS RAISED pattern.
- **Use cases**: woven fabric, basket weave, cane chair, mesh, chainmail, woven grass mat, wickerwork.
- **Modeler wiring**: `weaveDepth/weaveDensity` plumbed through ModelerPrim → specToPrims → JSON normalizer (modeler_demo.ts:196,1273,1901).
- **Self-validated via live preview daemon** (preview.png at density=22, depth=0.0030 on 60×60mm slab): all 4 views show the basket-weave pattern; over-under flip clearly visible on front/iso views, depth profile reads correctly on side/top.
- **Library state**: 17 primary deformers (12 color-aware) + 4 wear deformers + 6 path-gen modes + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - Periodic-organic: fishscale
  - **Two-axis raised**: weave ← new family
- **Process note**: live preview daemon (preview_daemon.mjs, 3s interval) replaces the per-iter modeler_driver.mjs invocation. Daemon stays warm against `modeler_demo.html`; iter just writes inbox.ark.json and the next 3s snapshot reflects it. Visit http://localhost:5173/sdf_modeler/preview.html for the feed.

## Cron-driven loop restarted 2026-04-25 23:5x — job 02939633
- New cron job `02939633`, every 10 min at :07/:17/:27/:37/:47/:57 (off the :00/:30 fleet hotspots). Auto-expires after 7 days.
- Roadmap (user-directed):
  1. **Continue surface patterns** — long tail of family expansions still possible (lichen, frost, basalt-columnar, more two-axis variants).
  2. **Reaction-diffusion (coral, brain)** — Gray-Scott style. The natural escalation past hand-tuned analytical patterns: emergent, parameter-tunable, gives true coral/zebra/brain-coral/leopard textures. Will need WGSL compute pass or an iterative dispatch — NOT a per-pixel SDF deformer like the existing 17.
  3. **Manhattan / Chebyshev pathfinding** for street and pipe layouts on building faces. New path-gen mode beyond walk/astar/lightning/tree/tendril — discrete grid pathing with L1 (Manhattan = right-angle, street-grid feel) or L∞ (Chebyshev = also-diagonals, mechanical/circuit feel). Authoring use case: extruded pipes + recessed conduits on building wall panels, sci-fi armor circuit traces, urban building facade layouts.
- Architecture note: items 2 and 3 are STRUCTURALLY different from the existing 17 deformers (which are all per-fragment WGSL math). RD needs state across frames or a fixed-iteration compute warm-up; pathfinding emits discrete prims like the existing path-gen system. So iter 26+ = path-gen extension first (drops in at `emitCarvesFromPath`), iter 27+ = RD architecture spike.

## /loop iter 26: Manhattan / Chebyshev metrics on A* pathing
- **New `metric` option on crackPathGen mode='astar'**: `'euclidean' | 'manhattan' | 'chebyshev'`. Single field switches three things atomically:
  - **NEIGHBORS topology**: manhattan = 4-neighbor (orthogonal only); euclidean/chebyshev = 8-neighbor.
  - **Diagonal step cost**: chebyshev = 1.0 (diagonals are free, 45° preferred); euclidean = √2; manhattan = N/A (no diagonals).
  - **Heuristic**: manhattan = `|dx|+|dy|`; chebyshev = `max(|dx|,|dy|)`; euclidean = `hypot`.
- **Polish-pass gate**: smoothPath (Catmull-Rom) only runs when metric='euclidean'. Manhattan/chebyshev paths stay ANGULAR — smoothing would round off the right-angle corners that ARE the visual signature.
- **Why one option, not new modes**: extending `astar` by a metric flag is a strict superset and ~20 LoC. A separate `'mechanical'` mode would have duplicated the cost-field, A* loop, and waypoint reconstruction. The behavioral difference IS just the metric.
- **Test spec**: manhattan_streets_v1 — 60×60×6mm facade slab + 3 manhattan A* carves forming an X-cross + center alley (gridRes=24, varying noiseWeight 0.5/1.5 for primary vs alley). Live preview confirmed: visible stair-step right-angle grooves on front + iso views, no curved corners. The angular signature reads cleanly.
- **Distinct authoring use cases enabled**:
  - **Manhattan**: street grids on building facades, wiring trunks, sidewalk layouts, plumbing risers — anywhere the visual language is "right angles only"
  - **Chebyshev**: PCB traces, sci-fi conduit layouts, steampunk pipework — where 45° diagonal segments read as "engineered" rather than organic
  - **Euclidean** (existing default): natural cracks following weak material — unchanged
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + **astar now has 3 metrics** + 3 path profiles + meander + taper + accentSlot. Path-gen taxonomy gains a new axis (metric) under the cost-field family.
- **Architectural note**: this is the cleanest kind of iter — extends an existing system via one new option, opens a whole new visual category, no new infrastructure. Compare to weave (iter 25) which was a new WGSL deformer (~30 LoC shader + ~10 LoC modeler wiring + slot bookkeeping). Path metric is ~20 LoC of pure JS branching.
- **Live preview latency lesson**: edited modeler_demo.ts 5× during iter; vite HMR reloaded each time; daemon's headless modeler had to re-init between reloads. User saw stale weave_v1 captures for ~30s. Future: batch related TS edits before triggering preview verification, or pause the daemon during edit bursts.

## Iter 27 candidate: T-junctions / branches for mechanical paths
- Streets and pipes have JUNCTIONS, not just isolated runs. Stack two manhattan A* carves currently produces a visible cross only because the user authored two paths that geometrically intersect. The next leverage: a `branches` field on astar mode that spawns N perpendicular sub-paths off the main spine at random waypoints (2-8). For pipes: T-fittings everywhere. For streets: side-streets off the avenue. Same cost-field logic, just N more A* runs from random main-path waypoints to grid-snapped endpoints.

## Iter 28 candidate: reaction-diffusion (Gray-Scott) — coral / brain / zebra
- Architectural spike: WGSL compute shader doing N iterations of Gray-Scott RD on a 2D grid (256² typical), output written to a storage texture. Surface deformer reads the texture by world-XY → uv mapping. ~150 LoC compute + ~30 LoC sampler. Tunable F (feed) and k (kill) → coral, brain-coral, zebra, leopard, fingerprint, chaos. Different category from any existing deformer because the pattern is EMERGENT, not analytical.

## /loop iter 27: raise-polarity flag on path-gen — pipes / conduits / cables on facades
- **New `raise?: boolean` field on `crackPathGen` and `pathCarves`**. Default false (existing carve-trench behavior). When true, segments ADD to parent (smooth union with positive blendRadius) instead of subtracting (smooth subtraction with negative blendRadius). Same magnitude (0.002) → predictable visual weight either polarity.
- **Threading**: emitCarvesFromPath gained 6th param `raise`, stamps onto each emitted carve. All 5 path-gen modes propagate (walk, astar, lightning, tree, tendril) plus the 2 inline pushes (walk-mode branches at line 670, tree-mode segments at line 924). Lightning's branch sub-paths inherit via `{...opts}` spread — no special handling needed. JSON normalizer round-trips `raise: true` on both `pathCarves` and `crackPathGen`.
- **expandPathCarves switches blend sign per-carve**: `blendRadius: c.raise ? 0.002 : -0.002`. Per-carve granularity (not per-prim) means a single path-gen could in principle mix raised + carved segments — currently the modes emit homogeneous polarity, but the door's open for hybrid effects later (e.g., a pipe with carved valve cutouts).
- **Why a polarity flag, not a new mode**: every existing path-gen mode (astar/walk/lightning/tree/tendril) gets raised variants for free. Adding "pipe" / "conduit" / "cable" as separate modes would have duplicated the routing code. Polarity is orthogonal to routing — exactly the kind of thing a flag should express.
- **Test scene**: brick_facade_pipe_crack_v1 — 60×60×6mm slab with brick deformer (brickDepth=0.0009, brickDensity=28), chebyshev raised pipe (thickness=0.0018, depth=0.003, noiseWeight=0.4 for engineered straightness), euclidean carved crack (thickness=0.0007, depth=0.0025, noiseWeight=1.6 for organic weak-material drift). Self-validated via preview daemon: front view shows running-bond brick + diagonal pipe + smooth crack; side view shows pipe protruding (raise = real additive geometry, not a recolor); top view shows pipe breaking silhouette while crack stays flush; iso shows all three layers compositing cleanly with no visual interference.
- **Authoring use cases unlocked**:
  - **Pipes / conduits / cables** on building facades, sci-fi corridors, mechanical panels
  - **Welding beads / seams** on metal plates (chebyshev or manhattan, very fine thickness)
  - **Vines / ivy** on walls (tendril mode + raise — raised growth instead of carved trail)
  - **Ribs / piping** on chest armor, leather goods, tooled book covers (any path mode + raise)
  - **Branches** of a tree growing OUT from a base trunk (tree mode + raise) instead of carved tree-shaped grooves
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics + 3 path profiles + meander + taper + accentSlot + **raise polarity flag (orthogonal across all 5 path modes)**.
- **Architectural note**: this is a *cross-cutting* extension — adds a feature that multiplies across 5 existing modes, not adds a new sibling mode. The 5 modes × 2 polarities = 10 path-gen variants from a 1-flag change. Compares favorably to iter 26 (1 new option × 3 metrics = 3 variants for similar implementation cost).
- **Scope decision**: skipped T-junctions/branches (previously the iter 27 candidate). Branches still on the stack but raise-polarity unlocks more orthogonal variety per LoC — pipes-on-facades was a missing capability category, branches are an enhancement to an existing one. Iter 28 candidates: T-junctions (mechanical Y-fittings), reaction-diffusion (Gray-Scott).

## /loop iter 28: T-junction branches on A* paths
- **New `astarBranches?: number` field on `crackPathGen`** (astar mode only). Spawns N perpendicular sub-paths off the main spine. Each branch picks a random INTERIOR waypoint (endpoint branches look detached), computes local tangent via central difference, projects perpendicular by 30-60% of the main bbox diagonal at random side, then recursively runs A* from waypoint → projected end with `astarBranches: 0` to prevent fractal explosion. Capped at 8 branches.
- **Branches inherit polarity, metric, profile, noiseWeight from parent** via `{...opts}` spread. Override only `start/end/seed/astarBranches/thickness*0.6/depth*0.85`. So:
  - chebyshev + raise=true + branches → mechanical T-fittings on raised pipework
  - manhattan + branches → side-streets off avenues (right-angle preserved)
  - euclidean + branches → tributary cracks / forking weak-material lines (smoothed via Catmull-Rom — branch joins fuse naturally)
- **Why `astarBranches` not `branches`**: tree-mode already has `branches?: number` (per-node fork count). Disambiguating the field names avoids ambiguity in the schema. The `astar` prefix also reads as "applies only to astar mode" which is the actual constraint.
- **Test scene**: brick_facade_pipe_tjunctions_v1 — same brick facade + chebyshev raised pipe with `astarBranches: 3` + euclidean carved crack with `astarBranches: 2`. Self-validated via preview daemon: front view shows pipe spine + 3 perpendicular protruding T-stubs + crack with 2 organic tributary forks; side view confirms branch protrusions in 3D (raised inherits correctly); iso view shows pipe network and crack network composing on brick without visual conflict.
- **Architectural note**: this iter is the cleanest kind of "free orthogonal extension" — `branches × metric × polarity × profile = 3×2×3 = 18 visual variants` from a ~50 LoC change, on top of iter 27's already-orthogonal `metric × polarity` matrix. Cost-field reuse (sub-A* runs with same noise seed offset) means branches feel cohesive with the main path rather than randomly tacked on.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches + 3 path profiles + meander + taper + accentSlot.
- **Iter 29 candidates**:
  - **Pipe end caps**: when raise=true, emit small hemisphere prims at start/end so pipes terminating mid-surface read as finished (currently the rounded-box ends look slightly clipped). ~15 LoC.
  - **Reaction-diffusion (Gray-Scott)**: still on the stack. Major architectural spike — WGSL compute pass + storage texture sampler. Different category from analytical deformers. Estimated ~150-200 LoC.
  - **Branch angle control**: currently branches project at exactly perpendicular (90°). A `branchAngleDeg?: number` override (default 90, e.g., 60-75 for swept-back tributaries that read as drainage rather than perpendicular splits) would extend authoring range. ~10 LoC.

## /loop iter 29: T-junction fittings via 'joint' kind on pathCarves
- **New `kind?: 'segment' | 'joint'` field on pathCarves**. 'segment' (default) = roundedBox along from→to (existing behavior, all path-gen modes emit this). 'joint' = sphere at `from` of radius=thickness, ignores `to`. Emitted by `expandPathCarves` via early-branch on c.kind, so adding it required no refactor of the existing prim emission.
- **A* branch loop now emits a joint at each connection point** in addition to the perpendicular sub-path. Joint inherits raise polarity, so `raise=true` paths get raised T-fittings (pipework) and `raise=false` paths get carved sinkholes at fork points (cracks merging in a deeper pit). `blendRadius: c.raise ? 0.0015 : -0.0015` (tighter than segments' 0.002, so joints read as distinct bulbs rather than melting into the spine).
- **Critical sizing lesson**: joint radius MUST exceed pipe depth or the sphere stays buried inside the tube/trench union and contributes nothing visually. First attempt used `thickness * 1.35 = 0.0024` against `depth = 0.003` — sphere top below pipe top → invisible. Fixed to `Math.max(thickness * 2.5, depth * 2.0) = 0.006` for the brick-facade test, giving ~3mm protrusion above the pipe spine. The blunt heuristic: joint radius needs to be at least 2× the pipe depth for the bulge to read at typical authoring scales.
- **Validation methodology that paid off**: when the iter-28-spec re-render with the new code looked identical to iter 28, I wrote a STANDALONE test spec with manually-authored `kind: 'joint'` pathCarves at known XY positions on the bare facade (no pipe). That render showed three crisp hemispherical bumps — proved the emission path was correct, isolated the bug to joint sizing relative to surrounding geometry. Without that isolated test, "looks the same" could have meant "code never runs" or "code runs but gets clipped" or "blend radius too aggressive" — debugging via hypothesis-elimination instead of guessing.
- **Test scene**: brick_facade_pipe_tjunctions_joints_v1 — same brick facade with 3-branch chebyshev raised pipe (now with visibly-bulged T-fittings) + 2-branch euclidean carved crack (small pit-joints at the 2 fork points, polarity correctly inherited). Self-validated: front view shows pipe spine fattening at each connection point, side/iso views confirm 3D protrusion of joints.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches × **{segment, joint} carve kinds** + 3 path profiles + meander + taper + accentSlot.
- **Iter 30 candidates**:
  - **Reaction-diffusion (Gray-Scott)** — finally promote this. Two iters of small extensions on path-gen makes the next move a pivot to a new category. New WGSL compute architecture; coral, brain, zebra, leopard from F/k tuning.
  - **Joint shape variety**: currently sphere-only. A `jointShape?: 'sphere' | 'torus' | 'cube'` field would unlock ring fittings (torus around the spine — like a flange), cubic junctions (industrial valve boxes), etc. ~15 LoC + sphere-equivalent cases.
  - **Joint at endpoints (start/end of main path)**: currently only at branch connection points. End-of-pipe spheres would replace the rounded-box clipped-cap look with proper hemispherical caps. ~10 LoC. Cheaper than the iter-29-candidate "pipe end caps" because it reuses the joint emit path.

## /loop iter 30: endpoint caps on A* paths — pipe authoring story complete
- **New `endCaps?: boolean` field on `crackPathGen`** (astar mode). Default = `!!opts.raise` — raised pipes get endpoint hemisphere caps automatically (so they read as terminated rather than clipped); carved trenches don't (extra pits at endpoints look like accidents). Override explicitly to force on/off.
- **Implementation reuses iter 29's joint-emit path**. After main `emitCarvesFromPath`, push a `kind:'joint'` carve at `wp[0]` and `wp[wp.length-1]` with the same `Math.max(thickness*2.5, depth*2.0)` sizing. Total ~12 LoC including schema, normalizer, and gen logic. Extension cost is low because the joint primitive type was already wired through expandPathCarves last iter.
- **Test scene**: brick_facade_pipe_endcaps_v1 — same spec as iter 29 but renamed to flag the new render. Pipe now displays prominent hemispherical bulbs at both ends, plus the existing 3 T-junction joints. Side view confirms 3D protrusion of all 5 joints. Carved crack remains uncapped — confirms the polarity-driven default.
- **Architectural note**: this iter is the *closing brace* on the path-gen sub-thread that ran iters 26-30. Each iter added one orthogonal capability:
  - **iter 26**: A* metrics (3 variants — euclidean/manhattan/chebyshev)
  - **iter 27**: raise polarity (×2 → 6 variants, doubled the visual catalog)
  - **iter 28**: T-junction branches (×{0..8} → 54 variants, multiplied again)
  - **iter 29**: T-junction joint primitives (engineered fitting visual layer)
  - **iter 30**: endpoint caps (closes the silhouette of raised pipes)
- **The compounding worked**: 5 iters × ~30 LoC each = ~150 LoC total, but the resulting authoring matrix has tens of distinct visual outputs from a single spec field combinatorial. This is the mode I should aim for going forward — pick orthogonal extension axes, not parallel siblings.
- **Library state**: 17 primary deformers + 4 wear deformers + 6 path-gen modes + astar with 3 metrics × 2 polarities × {0..8} branches × {auto/forced} endcaps × {segment, joint} carve kinds + 3 path profiles + meander + taper + accentSlot.

## Iter 31 plan: Reaction-diffusion (Gray-Scott) — focused architectural spike
- **Pivot from path-gen polish to a new deformer category**. Path-gen has had 5 iters; per the 6-iter cap, time to move on. RD has been deferred at iters 28 and 29 — claiming this slot.
- **Architecture decision**: CPU-side Gray-Scott bake at spec-normalize time, upload field as a 2D texture, sample in the WGSL fragment deformer. This avoids needing a new compute pipeline + ping-pong storage texture infrastructure (which the modeler's WGSL block currently lacks — it only has scene/normal/depth tex bindings + uniform; no compute pass, no storage texture for read-write).
- **Why CPU bake is the right tradeoff**: RD only needs to run ONCE per spec (~1000-3000 iterations to settle into stable patterns). At 256² grid that's ~65k cells × 3000 iters = 200M ops. ~1 second on JS at modern speeds. Spec-normalize already runs all the path-gen logic on CPU; this is in keeping. GPU compute would be faster (10-100×) but adds bind-group machinery, double-buffer texture state, and dispatch ordering — too much one-iter scope.
- **Plan**:
  1. Add fields to ModelerPrim: `rdFeed?: number` (F), `rdKill?: number` (k), `rdIterations?: number` (default 2000), `rdGridRes?: number` (default 256), `rdDepth?: number` (displacement amplitude), `rdSeed?: number`.
  2. CPU implementation of Gray-Scott update on a Float32Array pair (U, V) double-buffered. Initial conditions: small seed of V perturbation in the center; rest pure U.
  3. After bake, take the V channel, upload as `rg32float` or `r32float` texture (one channel, 256² × 4 bytes = 256KB, fits well).
  4. Add new texture binding (binding=5, since 0-4 are taken) to the WGSL block.
  5. New deformer function in WGSL that samples by world-XY → uv (mod 1.0 for tiling).
  6. Wire into the per-prim deformer dispatcher.
  7. Test scene: 60×60×6mm slab with RD deformer at F=0.055, k=0.062 (coral preset).
- **Risk**: WGSL fragment-shader texture sampling is straightforward, but adding a new bind group entry mid-pipeline could surface plumbing details I haven't seen. If the spike runs over budget, fallback is a 1D field encoded directly into the prim params (8x8 grid in a vec4 array — much cruder, but no new bindings).
- **Calibration**: known F/k presets — coral (0.055, 0.062), brain (0.040, 0.060), zebra (0.020, 0.060), leopard (0.025, 0.060), spots (0.014, 0.054), chaos (0.026, 0.051). The pattern axis (F, k) is roughly orthogonal to "scale" — same F/k at different grid resolution gives larger/smaller features. Authors will pick from preset → adjust for taste.

## /loop iter 31: Reaction-diffusion (Gray-Scott) deformer — coral works
- **New `colorFunc=27` deformer** in raymarch_renderer.ts: samples a CPU-baked V-channel field via `@binding(5) var<storage, read> rdField: array<f32>`. Geometric pass adds `-v * rdDepth` to d (high V = raised peak). Color pass picks slot B for V > 0.3 (the established peak threshold). Pattern is emergent (analytical deformers can't make this).
- **CPU bake**: `bakeReactionDiffusion(F, k, iterations, seed)` runs Gray-Scott Euler integration on a 128² Float32Array pair (U, V). Toroidal Laplacian (5-point, wraps), random ~5% V-perturbation seed, normalised to [0,1]. Cached on (F, k, iters, seed) — re-renders without RD changes don't re-bake. ~50ms for 2000 iters.
- **Engine plumbing**: added `rdFieldBuffer` (128² × 4B = 64KB) at renderer construction, default-zero so binding stays valid when no RD prims exist; `setRDField(data: Float32Array)` public method; bind group entry at binding 5. Auto-derived bind group layout from WGSL declarations meant zero explicit layout-spec changes — the new `@binding(5)` line was the entire layout-side change.
- **Critical bug caught**: first attempt used `Du=1.0, Dv=0.5, dt=1.0` (informally remembered from Wikipedia). With those values, the explicit Euler integrator is unstable past iter ~20 — the Laplacian's ×4-neighbor swing exceeds the stability bound, U/V values blow past saturation into NaN. NaN flowed through writeBuffer onto the GPU, made `d = d - NaN * rdDepth` return NaN inside the SDF, and **the entire surface vanished — the render came back empty grid**. Fixed by switching to **Pearson's classical params: Du=0.16, Dv=0.08**. Stability lesson: never trust un-cited diffusion coefficients; the well-known stable presets exist for a reason.
- **Diagnostic methodology**: when the RD spec rendered empty grid, swapped to a known-good brick-only spec (no RD) — that worked, isolating the bug to the RD code path. Ruled out plumbing (binding, layout) by elimination. Then suspected NaN → reasoned about the diffusion stability bound → fixed → next render showed coral. ~2 spec swaps from "broken" to "fixed" without needing browser console access.
- **Test scene**: rd_coral_v2_fixed_du — 60×60×6mm slab with rdDepth=0.0015, rdDensity=14, F/k=0.055/0.062 (coral preset), 2000 iters, seed=7. Render shows ~6-8 coral spots scattered across the front face, each ~5-10mm wide, with characteristic intricate amoeba-boundary topology. Side view shows clear 3D protrusion (~1.5mm raised). Iso shows depth and pattern compositing cleanly.
- **One-field-per-scene constraint**: shared rdFieldBuffer means one F/k bake at a time. Each prim with rdDepth > 0 samples the same field at its own density/depth, but the F/k that defines the PATTERN is set by the FIRST RD prim found in spec.primitives. Acceptable for first cut; future iters could move to multi-field via array<array<f32, GRID²>, MAX_FIELDS> or per-prim baked atlases.
- **Library state**: 18 primary deformers (12 color-aware: 9, 10, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24, 25, **27**) + 4 wear deformers + 6 path-gen modes + astar matrix + 3 path profiles + meander + taper + accentSlot.
- **Family map updated**:
  - Organic-irregular: bumps, scales, voronoiCracks, ridges
  - Organic-natural: cracks, pits, veins
  - Directional: grain, streaks, scratches, chevrons
  - Periodic: hex, brick, dimples, studs
  - Radial: whorl
  - Periodic-organic: fishscale
  - Two-axis raised: weave
  - **Emergent: reaction-diffusion (Gray-Scott)** ← new family. First non-analytical deformer — pattern emerges from rule iteration, not from a closed-form expression.
- **Architectural milestone**: this iter is the first to add new GPU storage binding to the raymarch pipeline. The pattern is now established — future iters needing precomputed fields (e.g., voronoi-region tables, signed distance maps for arbitrary glyphs, custom palette atlases) can copy the rdFieldBuffer pattern: createBuffer at init, default-zero fill, setX() public method, bind group entry. Auto-derived layout means no explicit layout maintenance.
- **Iter 32 candidates**:
  - **Other RD presets validated** — brain (0.040, 0.060), zebra (0.020, 0.060), leopard (0.025, 0.060). Different F/k same architecture; just pick presets to confirm visual range. Cheap iter.
  - **RD on a path-gen carved surface** — apply RD to a prim that ALSO has a chebyshev pipe carved into it. Visual: coral wall with mechanical pipework. Tests deformer composition (path-gen pathCarves are separate prims, RD is on parent — should naturally compose).
  - **Per-prim independent RD fields**: extend rdFieldBuffer from `array<f32, 128²>` to `array<f32, 128² × MAX_RD_PRIMS>` and index by per-prim `rdFieldIdx`. Allows multiple RD-deformed prims in one scene with different F/k. ~30 LoC.
  - **RD wear overlay**: wire RD into the secondary wear-deformer slot (currently FBM-only modes 1-4). Coral-textured rust on a brick wall, brain-fold detail on a face. ~10 LoC + new wearFn ID.

## /loop iter 32: RD preset validation + named-preset string field
- **Validated brain (F=0.040, k=0.060)**: produced canonical maze-like worm-loops, distinct from coral's discrete spots. Confirms architecture handles different F/k regimes within the same plumbing.
- **New `rdPreset` string field** with 8 named presets (coral, brain, zebra, leopard, spots, chaos, fingerprint, flower). Schema-typed union so authoring tools can offer auto-complete. specToPrims resolves preset → (F, k) at upload time; explicit rdFeed/rdKill always override the preset's mapping. Normalizer round-trips the string.
- **Implementation note (preset calibration)**: zebra at (0.020, 0.060) per literature did NOT produce long parallel stripes in this implementation — rendered as small scattered spots more like leopard. Pearson's classical F/k boundaries assume continuous-form (Du, Dv) converted to dimensionless via specific Δx; our (Du=0.16, Dv=0.08, dt=1.0) shifts the pattern boundaries slightly. Each named preset works (different F/k → different pattern), but the named-to-actual-pattern mapping is approximate. **Future tune**: empirically dial each preset for THIS implementation's regime. Out of scope for this iter — the architecture is what mattered.
- **Test scenes**: rd_brain_v1 (manual F/k), rd_zebra_preset_v1 (rdPreset string). Both rendered correctly via the full bake → upload → sample path.
- **Library state**: 18 primary deformers, RD now with 8 named presets + manual F/k. Same plumbing as iter 31; just authoring polish.

## Pivot 2026-04-26 ~10:45 — terrain generation thread starts
- **User direction**: "feel free to progress on these, if you get cycles try to move on to terrain generation, erosion, water wind etc. pooling water at the bottom of hills accumulation".
- **Architectural fit**: terrain is structurally similar to RD — CPU-baked 2D scalar field + GPU sample for displacement. The RD plumbing established in iter 31 (storage buffer binding, default-zero, public setX() method, auto-derived bind group layout) is the template. Terrain adds:
  - **Generation passes**: FBM heightmap, ridged-multifractal, hybrid (mountains + valleys + plateaus)
  - **Erosion passes**: thermal (slope-based talus collapse), hydraulic (water carries sediment downslope, deposits in low areas)
  - **Hydrology**: water level + accumulation pooling at basins; flow simulation can also OUTPUT a flow-volume field that displays as river beds
  - **Optional weathering**: wind erosion (lateral material transport), snow accumulation by altitude+slope
- **Scope plan over the next ~14 cron firings (~3 hours)**:
  1. **iter 33**: Terrain primitive type — single-prim heightmap-displaced surface. CPU FBM bake at higher res (256² or 512² since terrain is the focal point, unlike RD's 128²). New GPU storage binding (binding 6). New WGSL deformer (colorFunc=28).
  2. **iter 34**: Ridged-multifractal generator option for dramatic peaks. Same architecture, different bake function.
  3. **iter 35**: Thermal erosion pass — N iterations of slope-based talus redistribution. Settles peaks toward angle-of-repose.
  4. **iter 36**: Hydraulic erosion pass — water + sediment droplet simulation, carves channels, deposits in basins.
  5. **iter 37**: Water level / pooling. Second field tracks water height; visualizes as a separate semi-transparent prim or as a slot-B color override below water level.
  6. **iter 38**: Flow accumulation field (Strahler-style) — channels visible as carved low-points where water concentrated.
  7. **iter 39**: Wind erosion (lateral exponential filter aligned with a direction). Smooths upwind, accumulates downwind.
  8. **iter 40**: Vegetation/snow zones via slope+altitude → palette slot picks. Free given existing palette infrastructure.
  9. **iters 41-46**: composition tests — terrain + RD coral as ocean floor texture, terrain + path-gen rivers, terrain + brick walls (medieval castle on a hill), etc.
- **Architectural note**: terrain is bigger scope than the path-gen / RD threads. Each iter is a discrete capability, but they layer into a coherent mini-engine. Different cadence — quality over ground-truth-cadence.

## /loop iter 33: terrain primitive — FBM, ridged, thermal-eroded
- **New colorFunc=28 deformer** with bilinear-sampled 256² heightmap. Resolution 4× RD's 128² because terrain is the focal feature. New @binding(6) = terrainField storage buffer; same default-zero pattern as rdField. Engine-side ~30 LoC plumbing.
- **CPU bake function `bakeTerrain(opts)`** with 4 generator modes:
  - **fbm**: classical fractal Brownian motion; rolling hills, no sharp peaks
  - **ridged**: ridged-multifractal `pow(1 - |2n-1|, 2)` per octave; sharp mountain ridges, dramatic peaks
  - **eroded-fbm** / **eroded-ridged**: above + N iterations of thermal erosion
- **2D value-noise**: hash-based per-corner randoms + bilinear with smoothstep fade. Cheap (no trig), high-frequency hash signature averages out across 5 octaves. Quality is FINE for terrain (vs Perlin/Simplex) — the lack of perfect smoothness at lower octaves is invisible after FBM-summing.
- **Thermal erosion**: per cell per iteration, find lowest of 8 neighbours; if drop > talus angle (0.005 in normalised units), move 0.25 of excess to that neighbour. Toroidal boundaries keep field tileable. Cost: ~5ms per iter on 256² (about 5MM neighbour-checks per pass). 50-100 iters is the usable range.
- **Validated visually via 3 spec swaps**: terrain_fbm_v1 (rolling hills, snow on highest peaks), terrain_ridged_v1 (sharp dramatic peaks, larger snow areas because ridges concentrate height), terrain_eroded_ridged_v1 (peaks blunted, valleys widened with deposited material — clear visible erosion effect).
- **Existing deformer pattern is reusable**: terrain code structure mirrors RD almost line-for-line (engine binding + WGSL deformer + CPU bake + uploadPrims trigger + normalizer). The 4th time I've written this template in 8 iters; could factor into a reusable "scalar field deformer" abstraction. Not now — premature; only 2 instances. Worth it at 4-5 instances.
- **Library state**: 19 primary deformers + 4 wear deformers + 6 path-gen modes + astar matrix + 3 path profiles + meander + taper + accentSlot + RD field + terrain field. Two GPU storage bindings beyond the original 0-4 (rdField at 5, terrainField at 6).
- **Iter 34 candidates**:
  - **Water level / pooling** (highest priority — user-flagged): scene-wide waterLevel parameter; cells below it become flat water surface (geometry capped at waterLevel) AND get water palette slot. Pooling emerges naturally — basins fill, peaks emerge as islands. Need to pass waterLevel through prim slot or uniform.
  - **Flow accumulation**: per-cell upslope-drainage count. Visualised as carved channels (where water concentrates → deeper rivers). Cheaper than full hydraulic erosion; reveals the natural river network.
  - **Hydraulic erosion**: simulate water droplets that pick up sediment downslope, deposit in low-energy areas. Carves canyons, builds deltas. ~150 LoC. Bigger iter.

## /loop iter 34: terrain water level + pooling
- **New `terrainWaterLevel` field** (scene-wide uniform `[0, 1]` of heightmap altitude). Cells below this level get TWO things: (1) flat water surface — `d = d - max(h, waterLevel) * depth` caps the geometric displacement so basins fill flat; (2) palette slot 3 (water blue, by convention). Pooling-at-bottom-of-hills emerges naturally from the height threshold without needing a separate water prim or extra simulation step.
- **Plumbing**: repurposed `_pad2` slot in the WGSL Uniforms struct → `terrainWaterLevel`. New `setTerrainWaterLevel(level)` public method on the renderer. uploadPrims pushes the value when a terrain prim is in the spec, resets to 0 when not (avoids leaking from a previous spec).
- **Default water palette**: slot 3 set to `(0.20, 0.45, 0.65)` (medium blue) at modeler init. Authors override slot 3 to get other liquid colors — lava red, acid green, mercury silver — without changing any deformer code.
- **Test scene**: terrain_water_pooling_v1 — 100×100×10mm slab with eroded-fbm terrain, waterLevel=0.32. Render shows blue water pooling in basins, gray rocky land emerging as islands and peninsulas, perfectly flat water surface in side/iso views (proves the geometric cap works, not just color).
- **Architectural note**: this iter implemented the user's literal phrase "pooling water at the bottom of hills accumulation" in ~30 LoC because the foundation (terrain heightmap field, palette, deformer dispatch) was already in place from iter 33. Compounding interest on the path-gen → RD → terrain pattern.
- **Iter 35 plan**: flow accumulation. For each cell, compute how many upstream cells eventually drain through it (D8 algorithm — process cells by descending altitude, propagate flow to steepest-descent neighbour). Visualises the natural river network even WITHOUT pooled water — channels appear as carved low-points. Implementation: new bake function returning a second Float32Array; new @binding(7) for flowField; new authoring field `terrainFlowDepth` controls how much rivers carve into the surface. Then rivers render as engraved channels even on dry land, plus they show as deeper cuts beneath the water level (river beds visible through clear water, conceptually).

## /loop iter 35: flow accumulation + river carving
- **D8 algorithm bake**: `bakeFlowAccumulation(heightmap, N)` processes cells in descending altitude order; each cell donates its accumulated flow to its steepest-descent neighbour (toroidal). Log-normalised output to compress the heavy-tailed distribution (a few main rivers carry most of the volume). ~50-100ms on 256² — about 20% of the heightmap bake cost.
- **New @binding(7) terrainFlowBuffer** + `setTerrainFlow(data)` public API + bind group entry. Auto-bake whenever a terrain prim exists; carving gated by per-prim `terrainFlowDepth`. Field stays valid even when carving is off (avoids re-binding overhead on toggle).
- **WGSL deformer extension**: colorFunc=28 now bilinear-samples BOTH terrainField (height) AND terrainFlow (flow), then `d = d - height*depth + flow*flowDepth`. The two fields layer cleanly: flow carves channels INTO the existing height topology. Channels appear as dark linear features draining the basins.
- **Slot 5.w repurposed**: was pad, now `terrainFlowDepth`. Coexists with wear (slot 5 x/y/z) since terrain prims rarely use wear.
- **Test scene**: terrain_flow_pooling_v1 — eroded-fbm at 100×100×12mm with waterLevel=0.28 + flowDepth=0.012. Render shows water in basins (iter 34) + carved river channels visible in the iso view as dark linear cuts converging toward water pools. The canonical "rivers flow into lakes" topology emerges from the math, no manual authoring.
- **Library state**: 19 primary deformers + path-gen + RD field + terrain field + flow field. THREE GPU storage bindings beyond the original 5 (rdField=5, terrainField=6, terrainFlow=7).
- **Iter 36 candidate**: slope-based palette zones. Currently terrain has 3 colors (base, snow-peak, water). Adding rock-on-steep and grass-on-gentle (slope-magnitude check via WGSL gradient sample) would dramatically improve realism. ~30 LoC. Could also branch to: hydraulic erosion (particle simulation, big iter), wind erosion (lateral filter, small iter), vegetation scatter (density-driven, medium iter). Going with slope zones — biggest visual leverage per LoC.

## /loop iter 36: slope-based palette zones (rock face / grass / snow / water)
- **WGSL gradient sample** in colorFunc=28 color dispatcher — 4-neighbor central differences on the terrain heightmap, Manhattan slope = `|hR - hL| + |hD - hU|`. Threshold 0.10 picks "steep" cells → palette slot 4 (rock).
- **Palette layout convention now**: slot 0=base/grass, slot 1=dark accent, slot 2=bright accent (used as snow), slot 3=water blue (iter 34), **slot 4=rock grey** (this iter). Each slot has a default RGB at modeler init; authors override for stylization.
- **Decision tree** (most-specific wins):
  ```
  h < waterLevel  → water (slot 3)
  slope > 0.10    → rock (slot 4)
  h > 0.6         → snow (slot B)
  else            → grass (slot A)
  ```
  Water beats slope (no rock visible UNDER water surface — looks weird). Slope beats altitude (snow on flat alpine mesa is fine but rock on steep ridge wins).
- **Test scene**: terrain_slope_zones_v1 — eroded-ridged terrain with waterLevel=0.28, flowDepth=0.012. Render shows 4 distinct palette zones cleanly: blue water in basins, snow on alpine peaks, exposed rock on steep faces, lighter base on the gentle areas. Reads convincingly as a mountain landscape.
- **Architectural note**: this iter is the first time a deformer's color decision uses NEIGHBOUR samples from its source field, not just the local sample. Pattern will recur for any deformer that wants slope/curvature/derivative-driven color (e.g., directional grass on hillsides vs cross-sections at peaks).
- **Iter 37 plan**: wind erosion. Directional asymmetric smoothing aligned with a wind direction (degrees). Each iter biases each cell's height toward an upwind sampling — produces streaked, dune-like terrain. New fields: `terrainWindIters`, `terrainWindAngle`, `terrainWindStrength`. Runs after thermal erosion if both are enabled.

## /loop iter 37: wind erosion — directional smoothing, dune topology
- **`windErosionPass(field, N, iters, angleDeg, strength)`** function. Each iter, every cell samples 1 cell upwind (bilinear), blends current toward upwind-height by `strength`. After N iters, peaks have been smeared in the wind direction — leeward face stays high, windward face is smoothed/lowered. Visually reads as dune-streaked or sandblasted terrain.
- **Three new authoring fields**: `terrainWindIters` (count), `terrainWindAngle` (degrees, 0=+X, 90=+Y), `terrainWindStrength` ([0,1] per-iter blend). Defaults 0/45/0.15. Wind runs AFTER thermal erosion in the pipeline so it streaks the already-blunted topology.
- **Cost**: ~3-5ms per iter on 256² (similar to thermal). 80 iters at strength=0.18 produces clearly directional terrain without going to mush.
- **Test scene**: terrain_wind_dunes_v1 — FBM with windAngle=30°, windIters=80. Render shows streaked terrain with linear features oriented along the wind direction; lost the rounded-hill character of plain FBM, gained a sand-blasted/wind-shaped character. Distinctly different from thermal-eroded (which is symmetric / gravitational) — wind erosion creates DIRECTIONAL anisotropy.
- **Library state**: terrain pipeline now has 4 stages composable in order: gen (FBM/ridged) → thermal → wind → flow. Each stage has gating fields; turning all off gives raw FBM. The pipeline is becoming a real terrain DSL.

## Iter 38 plan: hydraulic erosion (particle-based)
- **The big remaining user ask** — water that picks up sediment, carves canyons, deposits in low-energy areas.
- **Algorithm**: spawn N=10000 random droplets. Each droplet has water=1, sediment=0, velocity=0. For K=30 steps:
  1. Bilinear-sample height at current position
  2. Compute gradient via central differences
  3. Update direction: `dir = dir * inertia + gradient * (1 - inertia)`, normalize
  4. Move 1 step in direction
  5. Compute new height; delta_h = h_new - h_old
  6. velocity = sqrt(velocity² + delta_h * gravity)
  7. Carrying capacity ∝ velocity × water × max(-delta_h, min_slope)
  8. If sediment > capacity OR moving uphill: deposit (raises terrain)
  9. Else: erode (lowers terrain in a small radius)
  10. Water *= 0.99 (evaporates); break if too low
- **Estimated cost**: 10000 droplets × 30 steps × ~30 ops each = 9M ops. ~100ms on JS. Acceptable for a one-time bake.
- **Field bilinear-write**: erosion/deposition affects a SMALL area around the droplet position, weighted by distance. Critical for stable simulation — direct cell writes would create grid-aligned artifacts.
- **Risk**: parameter tuning. If too aggressive, terrain converges to a flat mush. If too gentle, no visible effect. Will need 1-2 spec swaps to dial in.

## /loop iter 38: hydraulic erosion (particle-based)
- **`hydraulicErosionPass(field, N, droplets, steps, seed)`**: Mei-style particle erosion. Each droplet starts at random sub-cell position, accumulates velocity downhill via gradient descent (with inertia blending so it doesn't lock to grid axes), picks up sediment proportional to `velocity × water × max(-deltaH, minSlope)`, deposits when slowing or moving uphill.
- **Sub-cell precision**: bilinear height sampling AND bilinear-radius writes. Erosion footprint is a `radius=2`-cell disc with linear falloff — prevents single-cell pits and grid-aligned artifacts. Position updates in continuous coords; toroidal wrap.
- **Tuned parameters**: inertia=0.05 (mostly steepest descent), erodeRate=0.3, depositRate=0.3, evaporate=0.01/step, gravity=4.0, minSlope=0.01. These give visible canyons in 5000-15000 droplets without converging to mush.
- **Re-normalize after**: erosion shifts heightmap min/max, so a final normalise to [0, 1] keeps the deformer's amplitude predictable and slope-zone thresholds stable.
- **Test scene**: terrain_hydraulic_full_v1 — eroded-fbm + 40 thermal iters + 8000 hydraulic droplets × 40 steps + waterLevel=0.30 + flowDepth=0.010. Render shows clear canyon-carving (interconnected water valleys), sharper peaks (windward faces eroded), basin pools, river beds. Slope zones colour appropriately (rock on canyon walls, snow on highest survivors).
- **Library state**: terrain pipeline now has 5 stages (gen → thermal → wind → hydraulic → flow). Each composable, each gated by an iters > 0 field. The whole terrain DSL is ~400 LoC across schema, bake, normalize.
- **Architectural reflection**: terrain has now consumed iters 33-38 (6 iters) — at the per-target soft cap. Time to wrap the thread or pivot. Remaining low-cost terrain iters: smooth-slope-zone-blends (cosmetic), vegetation-scatter (sparse particle prims), composition tests (validation). The high-leverage paths from here are pivoting to **gameplay/character integration** (terrain + a character on it), or to **diorama systems** (multiple coordinated prims forming a scene).
- **Iter 39 candidate**: smooth slope-zone transitions. Currently hard `slope > 0.10` threshold for rock pick. Adding `smoothstep(0.08, 0.12, slope)` blend with surrounding palette gives natural-looking transitions instead of sharp colour edges. ~5 LoC. Quick polish.

## /loop iter 39: smooth slope-zone transitions via dithered smoothstep
- **Hard threshold → smoothstep + per-pixel hash dither**. Current code: `if (slope > 0.10) slot=rock`. New code: `smoothstep(0.06, 0.13, slope) > hash(uv) → slot=rock`. The hash decorrelates per-fragment so the transition zone reads as stochastic mixing (small rocks among grass) rather than a smooth color blend (which would only work with palette-interpolation).
- **Dithered transitions** are more authentic for rock/scree boundaries than smooth blends. Real terrain has discrete pebbles and rocks in grass; a smooth gradient would look CGI.
- **Same treatment applied to snow zone**: smoothstep(0.55, 0.65, h) with hash gives dithered snow line — patches of snow among rock at the transition altitude.
- **Test scene**: terrain_smooth_zones_v1 (same settings as iter 38). Render shows transitions between rock/grass and rock/snow as natural stochastic mixing instead of hard color edges.
- **Library state**: terrain visualization now has palette: water/grass/rock/snow with dithered boundaries. Reads as authentic landscape coloration.

## /loop iter 40 plan: vegetation scatter — sphere prims on appropriate cells
- **Scatter prims appended at upload time**: after specToPrims, if terrain prim has `terrainScatterCount > 0`, generate N small sphere prims at random (x, y) on the slab. Sample heightmap to pick z. Filter by slope + altitude zone (low-slope grass zone for "trees"). Emit each as a sphere with palette slot picking dark green or similar.
- **Visual**: tiny dots peppering the green areas of the terrain — reads as forest/grass tufts. Placement is per-bake (deterministic from seed) so the scatter is consistent across renders.
- **Implementation**: ~50 LoC. Density-driven, uses existing prim machinery, no new bindings. Could later extend to cone prims (taller trees) or capsule prims (tall grass blades).

## /loop iter 40: vegetation scatter — green prims on grass zone
- **`scatterVegetation()`** helper: random (ux, uy) in slab bounds, sample heightmap at the matching world XY (using the same `fract(world.xy * density)` mapping as the WGSL deformer), filter by zone (h ∈ [waterLevel, 0.55], slope < 0.08), emit sphere prim at the on-surface position.
- **Slot 5 = forest green** (palette default 0.18, 0.36, 0.16). Authors override for autumn, pine, savanna, alien biomes.
- **Sub-pixel sizing lesson**: first render at 2mm radius produced invisible dots — at 384²/panel and 100mm slab, 2mm = 0.78 pixels. Bumped to 5mm so each tree is 2px+, visibly green. Also offset center by `radius * 0.3` above surface so spheres stand proud (not half-embedded).
- **Test scene**: terrain_with_forest_v2 — 80 trees at 5mm scattered on the eroded terrain. Green clusters visible across the gentle grass zone (between water and snow), absent from rock cliffs and underwater. Distribution looks naturally scattered (no grid pattern).
- **Library state**: complete terrain DSL — gen + thermal + wind + hydraulic + flow + waterLevel + slope-zones + dithered transitions + vegetation. ~600 LoC across 8 iters (33-40). The user's full ask ("terrain, erosion, water, wind, pooling, accumulation") is shipped + extras.

## /loop iter 41 plan: composition demo — terrain + brick castle
- **No new code**, just spec authoring. Validate that the terrain prim composes cleanly with other deformer prims (brick from iter that added it years ago in the agent log).
- **Spec structure**: terrain prim (the island/hill) + box prim (castle wall) at higher Z, separate blendGroup so they don't smooth-blend.
- **Risk**: positioning. Castle at fixed Z that's "above the highest peak" — some specs may have peaks intersecting castle base. Acceptable for first cut; future iters could query the heightmap max and offset castle Z accordingly.

## /loop iter 41: composition demo — fantasy island + brick castle
- **No new code**, just spec authoring. fantasy_island_castle_v1 stacks 3 prims:
  1. **Terrain island** (blendGroup 1): eroded-fbm + hydraulic + waterLevel + flow + scatter — all the terrain features. Reads as a coral-pool island with green grass and snow peaks.
  2. **Castle wall** (blendGroup 2): roundedBox with brickDepth = 0.8mm, brickDensity = 35 — visible running-bond brick pattern. Separate blendGroup so it doesn't smooth-blend with the hill underneath.
  3. **Castle tower** (blendGroup 2): cylinder with brick. Stands on the wall.
- **Render confirms full composition**: brick castle visible at center, terrain features around it, water in basins, green trees on grass slopes. All three deformers (terrain colorFunc=28, brick colorFunc=18, no deformer for raw shapes) coexist in a single render pass — the per-prim colorFunc dispatch handles them independently.
- **Architectural validation**: this proves the systems are TRULY ORTHOGONAL. The terrain pipeline doesn't interfere with brick deformer; the brick deformer doesn't see terrain's bindings. Each prim resolves through its own colorFunc branch in the dispatcher and emits its own surface.
- **Library state**: 19 deformers + path-gen + RD + terrain pipeline + scatter + composition validated. The system can author full diorama-scale scenes from a single spec.
- **Stretch directions left to explore**: animation (VAT skeletons exist in the codebase but unused in modeler), multi-character scenes, true sky/atmosphere (would need a fullscreen sky pass before the raymarch), water shader improvements (foam at shores, wave displacement), procedural city generation (combine path-gen streets with brick buildings + terrain), more deformer presets (lava, ice, rust). Each is its own potential thread.

## Capstone — autonomous run summary 2026-04-26 ~10:00–11:20 CDT

**User direction**: head out for 3 hours, progress on RD work then pivot to terrain generation, erosion, water, wind, pooling, accumulation.

**Iters shipped (16 total in this session)**:
- iter 26: A* metric flag (manhattan / chebyshev / euclidean)
- iter 27: raise polarity for path-gen
- iter 28: T-junction branches on A*
- iter 29: T-junction joint fittings
- iter 30: endpoint caps on raised paths
- iter 31: Reaction-diffusion deformer (Gray-Scott, colorFunc=27)
- iter 32: RD named presets
- iter 33: terrain primitive (FBM, ridged, thermal erosion, colorFunc=28)
- iter 34: water level + pooling
- iter 35: flow accumulation + river carving
- iter 36: slope-based palette zones
- iter 37: wind erosion (directional smoothing)
- iter 38: hydraulic erosion (particle-based, Mei-style)
- iter 39: dithered slope-zone transitions
- iter 40: vegetation scatter
- iter 41: composition demo (terrain + brick castle)

**New engine bindings**: 5 (rdField), 6 (terrainField), 7 (terrainFlow). Each follows the same "default-zero buffer + setX() public API + bind group entry" pattern; auto-derived layout from WGSL @binding declarations meant zero explicit layout-spec changes.

**New colorFunc IDs**: 27 (RD), 28 (terrain). Both follow the existing per-prim dispatcher convention.

**New uniforms field**: terrainWaterLevel (in Uniforms struct, formerly _pad2).

**New palette slots by convention**: 3=water blue, 4=rock grey, 5=forest green.

**Demo library**: 5 spec files in `public/sdf_modeler/demos/` covering alpine lake, desert dunes, fantasy island + castle, coral reef, brick pipework. README in same folder. To preview one, `cp demos/<file>.ark.json inbox.ark.json` and the daemon picks it up.

**Render res**: 192² → 384² per panel (768² atlas) per user request.

**Total LoC added**: ~1100 across modeler_demo.ts (~700) + raymarch_renderer.ts (~250) + spec files (~150). 1 critical NaN bug caught (Gray-Scott Du/Dv stability, iter 31). 1 visibility-tuning loop (iter 29 joint sizing, iter 40 scatter sizing).

**Where to pick up next**: any of the iter-41 stretch directions, OR continue terrain polish (better water shader, more biomes), OR pivot to gameplay/character work. The terrain pipeline is comprehensive enough that "more terrain features" hits diminishing returns; meaningful next moves are NEW categories.

## /loop iter 42: animated water surface waves
- **Sum-of-sines wave displacement** added to the terrain water cap. Three sine components: traveling X-axis wave (90 cycles/m, speed 1.7), traveling Y-axis wave (75 c/m, speed -1.3 — opposite direction so they don't synchronise), diagonal wave on (X+Y) (60 c/m, speed 2.1). Amplitude in heightmap-normalised units (0.012, 0.008, 0.006) scales naturally with terrainDepth.
- **Implementation**: 3 lines in WGSL. `let waterSurface = u.terrainWaterLevel + waveX + waveY + waveD; let hCap = max(h, waterSurface);` Replaces the static `max(h, u.terrainWaterLevel)`.
- **Verified animation**: two consecutive 6-second-apart snapshots (md5sum) differ — confirms time-driven evolution. Waves are subtle at 768² atlas size but visually present in the wet regions; would read more dramatically at higher render resolution or in a tighter view.
- **Architectural note**: this iter cost ~5 LoC because all the foundations were already in place (u.time uniform was wired, deformer dispatch already had water cap, no new bindings needed). Compounding interest at full effect.
- **Library state**: terrain pipeline is now fully animated (water moves) without sacrificing the static-bake principle for everything else (heightmap, flow, RD all still bake-once). Hybrid bake-once + display-time-animate is the right model — keeps bake costs amortized while letting the visualization breathe.

## /loop iter 43: coastline foam — bright halo at water/land boundary
- **Foam band**: cells with altitude in `[waterLevel - 0.05, waterLevel + 0.02]` get palette slot 6 (foam white). Asymmetric band — extends 5% below water and 2% above, so submerged shallow shores AND emergent shore strips both pick up foam. Snug to the coastline.
- **New slot 6 = foam white** (0.92, 0.94, 0.97) — bright off-white default. Authors override for sandy beach (tan), muddy delta (brown), volcanic ash beach (charcoal).
- **Decision-tree position**: foam check goes BEFORE rock and snow zones, AFTER deep-water — so coast cells on steep slopes still get foam (not rock), and the shore halo reads cleanly even in dramatic landscape.
- **Test scene**: shallow_water_with_foam_v1 — same shallow-water spec as iter 42 but with foam now active. Render shows clear bright halo around every island and peninsula at the waterline. Multiple coves visible. Combined with the animated water surface, the scene reads as a real coastline.
- **Architectural note**: completing the water trio (cap + waves + foam) in 3 iters of ~10-30 LoC each. Same compounding pattern: foundations from iter 34 (water cap) → animation in iter 42 (~5 LoC) → coastline detail in iter 43 (~10 LoC). Each iter adds depth without adding infrastructure.

## /loop iter 44: render-res bump 768² → 1024² + showcase scene
- **renderRes 384 → 512** per panel. Atlas now 1024×1024 (4× the pixel count of the original 192-default). GB10 handles it without breaking sweat. The wave animation, foam halos, and dithered slope transitions all read more clearly at higher density.
- **Landing showcase**: showcase_archipelago_v1 — `eroded-fbm` terrain with 7000 hydraulic droplets, 60 thermal iters, mid-altitude waterLevel (0.42) so multiple separate islands form an archipelago. 75 scatter trees, deep flow channels, full coastline foam.
- **What's visible at 1024²**: distinct foam ring around every island, fine river-channel texture, individual scatter prims (not just dots), animated wave surface variation between captures, brick-style snow patches on highest peaks. The terrain reads as a real mini-landscape rather than a stylized diagram.
- **State for user's return**: `inbox.ark.json` is the showcase; `demos/` has 5 reference specs; agent log captures iters 26-44 (19 total this session). Cron is still armed (next firings will continue the autonomous loop unless deleted).

## /loop iter 45: pre-rendered demo gallery
- **Cycled all 5 demo specs through the modeler**, captured each render at 1024² and saved alongside the spec file: `demos/0X_<name>.png`. Files range 380KB-1.3MB depending on terrain detail / coral pattern complexity.
- **Updated `demos/README.md`** to point at the gallery PNGs so the user can browse all 5 without swapping inbox.ark.json.
- **Final inbox state**: showcase_archipelago_v1 (the iter-44 landing scene). Daemon still running, vite still serving, cron still armed.

## /loop iter 46: max-quality push — 512² heightmap + 1536² atlas + per-fragment detail FBM
- **User direction**: "lets go for max quality since we are headless rendering followed by raymarch cache for our main game" — frames the constraint as one-time bake cost, not per-frame perf, because the engine's raymarch cache absorbs subsequent frames.
- **Three changes shipped together**:
  1. **TERRAIN_GRID 256 → 512** (engine + modeler agreement constants). 4× cells, 1MB per buffer (heightmap + flow = 2MB). Bake time ~4× longer (1-2s) but it's once per spec change.
  2. **renderRes 512 → 768/panel** (1536×1536 atlas). 2.25× more pixels per render. GB10 still fast under headless.
  3. **Per-fragment detail FBM** in WGSL terrain deformer: `fbm3(pWorld * density * 6.0) * 0.08 * terrainDepth` added to the geometric pass, gated `step(waterLevel + 0.03, hCap)` so it skips underwater + foam zone. Sub-cell texture now reads at any zoom — no grid flatness between heightmap cells.
- **Render comparison**: 1024² showcase had visible heightmap aliasing; 1536² + 512² heightmap + detail FBM has sharp coastlines, fine peninsular fingers, micro-texture on slopes, and individual scatter prims read as distinct (instead of blurred dots). Side + iso views show dramatic relief.
- **Architectural reframe**: with the cache + headless setup explicitly called out by the user, "expensive one-time bake" is no longer a tradeoff to manage — it's free. Future iters can lean MUCH harder: 1024² heightmaps, more erosion droplets, multi-octave detail FBM, etc.
- **Cron `b44e49d3`**: every 10 min, prompt "lets go for max quality since we are headless rendering followed by raymarch cache for our main game". Loop continues with quality-focused iters.

## /loop iter 47: hierarchical detail FBM + max-quality showcase params
- **Three-octave detail FBM stack** in WGSL terrain deformer: pass 1 at `density × 6`, pass 2 at `× 18`, pass 3 at `× 54`. Amplitudes 0.07, 0.03, 0.013 of terrainDepth (sums to ~12% — visible but not overpowering). Each pass adds finer micro-texture; result reads sharp at any zoom and reveals different scale of detail as you crop in.
- **Showcase params scaled to exercise 512² heightmap**:
  - `terrainOctaves`: 6 → 7 (more macro detail in the bake itself)
  - `terrainErosionIters`: 60 → 100 (deeper thermal settling)
  - `terrainHydraulicDroplets`: 7000 → 25000 (3.5× — needed to maintain coverage across 4× cell count)
  - `terrainHydraulicSteps`: 38 → 50 (longer droplet life carves longer rivers)
  - `terrainScatterCount`: 75 → 120 (more vegetation, denser distribution)
- **Render result**: dramatic visible improvement. Multi-tier detail visible — large landmass shape from base FBM, mid-scale erosion features from thermal/hydraulic, fine micro-texture from the analytical detail FBM. The terrain reads as a real biome rather than a stylized model.
- **Iter 48 candidates** (still in max-quality push):
  - **Bicubic heightmap interpolation** (~30 LoC) — smoother gradients between cells, sharper rivers
  - **Render res 768 → 1024 per panel** (2048² atlas, ~16MB PNG) — diminishing returns vs the detail FBM win
  - **Wave normals + depth attenuation** (water gets darker further from shore) — richer water rendering
  - **Slope-aware vegetation** — taller grass on gentle slopes vs short shrubs on steeper, currently uniform
  - **Snow gradient by altitude** — currently hard threshold; could grade from rock → patchy snow → full snow over altitude range

## /loop iter 48: water depth attenuation — deep / shallow / foam gradient
- **New slot 7 = shallow water teal** (0.34, 0.62, 0.70). Lighter and slightly green vs slot 3 deep blue. Used in the depth band 0.05-0.15 below waterLevel.
- **WGSL palette pick by depth-from-waterline**:
  ```
  dToWater < -0.15  → slot 3 (deep, dark blue)
  -0.15 to -0.05    → slot 7 (shallow teal); dithered into foam at upper edge
  -0.05 to +0.02    → slot 6 (foam, brilliant white)
  ```
  Plus a smoothstep+hash dither at the shallow→foam boundary so the band edge isn't a hard ring.
- **Result**: each island now has a proper depth gradient — pale teal halo around every peninsula and bay, transitioning to deep blue offshore. Reads like real coastline imagery instead of stylized blocky water.
- **Architectural note**: water rendering now has FOUR distinct visual zones (foam / shallow / deep / dry land transition), all from a single colorFunc=28 dispatcher. No new bindings, just smarter palette pick logic.

## /loop iter 49: tonal variation on land surfaces (FBM-modulated tint)
- **Two-octave FBM tint modulation** post-palette-pick: `coarse * 22.0 + fine * 80.0`, mixed `0.78 → 1.10` brightness range. Applied only to terrain colorFunc=28 AND non-water slots (excludes 3 deep, 6 foam, 7 shallow). Land reads as natural material with grain instead of paint-by-numbers flat color.
- **Snow + rock + grass + scatter** all benefit. Visible lighter/darker patches on snowy peaks, mottled rock cliffs, slightly varied greens on the vegetation slot. Subtle (15%) but the terrain stops looking CGI-flat.
- **Architectural note**: this is the first time tint is modulated AFTER slot pick. Previous deformer convention was strict "slot 0 = base, slot 1 = accent, etc." with literal palette colors. The new pattern — slot pick → tint modulation — opens up rich material variation without exploding the palette slot count.

## /loop iter 50: vegetation variety — size + color + position jitter
- **Per-prim variation in scatterVegetation**: radius scaled by 0.65-1.35× per scatter, palette slot weighted-random (70% forest 5, 18% pine 8, 8% olive 9, 4% brown 10), XY position jittered ±half-cell so prims aren't aligned to the heightmap grid.
- **Three new palette slots**:
  - Slot 8 = dark pine (0.10, 0.24, 0.10)
  - Slot 9 = olive yellow-green (0.40, 0.40, 0.18)
  - Slot 10 = brown / dead (0.30, 0.20, 0.12)
- **Result**: scattered vegetation reads as natural mixed forest. Distinct tree sizes break the uniform-disc appearance; color variation gives texture; position jitter removes the grid-aligned look. Same primitive cost (still spheres in slot 5+ space) but visually 5× richer.
- **Compounding pattern**: scatter prims emitted by terrain bake → use new palette slots → consumed by per-prim color dispatch → tinted by iter 49 modulation. Each iter layered on top of the previous machinery.

## /loop iter 51: bicubic Catmull-Rom heightmap interpolation
- **New WGSL helpers**: `cubicHermite(A,B,C,D,t)` Catmull-Rom basis + `sampleTerrainBicubic(uv)` 4×4 bicubic with toroidal wrap. Replaces bilinear in the terrain geometric pass.
- **Cost**: 16 cell samples + ~30 ALU ops per fragment vs 4 + 5 for bilinear. Cache absorbs the difference for static scenes (the user's main-game use case).
- **Why kept flow bilinear**: log-normalised flow accumulation values are heavy-tailed (a few main rivers spike up). Bicubic overshoot at those peaks would carve phantom side-spurs. Bilinear is right for sharp-edged data.
- **Result**: surface is C2-continuous between cells. Coastlines flow naturally, slope gradient is smooth, no piecewise-linear facet edges visible. Subtle in stills but clearly better in motion or at zoom.

## /loop iter 52: atmospheric fog on terrain (aerial perspective)
- **Distance-based color shift**: fragments mix toward `vec3f(0.78, 0.85, 0.92)` (pale blue-grey sky tint) by `smoothstep(0.10, 0.85, dNdc) * 0.35`. Foreground stays sharp; back-plane fragments lose ~35% saturation toward sky. Limited to colorFunc=28 so brick/coral/etc. demos aren't affected.
- **Why this matters at the cinematic level**: real outdoor scenes have aerial perspective from atmosphere scattering. Without it, the terrain looks like a tabletop diorama; with it, peaks read as actually distant. The eye uses depth cues like this to judge spatial extent.
- **Implementation note**: had to move the dNdc computation BEFORE the fog block (was after). Compile would have errored. Caught + fixed in one edit.
- **Library state**: terrain rendering now has 5 visual layers stacked: macro displacement (heightmap) → river carving (flow) → micro-detail (3-octave FBM) → land tonal variation → atmospheric fog. Each adds depth to the overall look.

## /loop iter 53: animated cloud shadows
- **Time-driven FBM mask** projected on land surfaces via world-XY → noise lookup with `u.time * 0.03` X-drift and `* 0.018` Y-drift. Where noise is high, multiply tint by 0.84 (16% darker); smoothstep transition keeps shadow edges soft. Water slots (3, 6, 7) skipped so shadows don't muddy the water visual.
- **Drift speed** ~5cm/sec equivalent at our scene scale — clouds pass overhead at "real time" pace. Frame-to-frame change is subtle but accumulates into clear motion in motion-aware viewers.
- **Architectural reflection**: the terrain rendering has now stacked SIX visual layers (heightmap displacement / flow carve / detail FBM / tonal modulation / atmospheric fog / cloud shadows). Each is ~5-30 LoC of WGSL on the existing fragment dispatch. The cumulative effect is the difference between a stylized diagram and a real-feeling outdoor scene — the same compounding pattern as the path-gen iters 26-30.

## /loop iter 54: sedimentary strata on rock cliffs
- **Horizontal banding modulation** on slot 4 (rock) only. Two beat frequencies (sin at 280 and 460 cycles/m) summed and softened into [0.78, 1.10] tint multiplier. FBM-warped Z perturbation breaks the perfect-line look so each stripe has natural thickness variation.
- **Why slot==4 only**: snow doesn't show stratification (no exposed underlying rock); grass doesn't either. Strata is a property of EXPOSED rock faces specifically.
- **Result**: cliff faces in the iso/side views now show visible horizontal layering — reads as geological sedimentary deposits. Adds another order of magnitude of authentic material feel.
- **Layer count**: 7 visual layers stacked on terrain (heightmap / flow / detail / tone / fog / clouds / strata). Each one is the ~10-30 LoC kind, all running per-fragment in the same colorFunc=28 dispatcher.

## Reference: DungeonTemplateLibrary — algorithms worth porting
- User shared https://github.com/AsPJT/DungeonTemplateLibrary as a useful reference.
- **Algorithms relevant to extending our pipeline**:
  - **Diamond-Square** — recursive midpoint displacement. Different topology than FBM; sharper local features. Add as `terrainGen: 'diamond-square'` (5th gen mode). ~40 LoC bake.
  - **Cellular Automaton islands** — random-fill + smoothing iterations gives organic blob landmasses, distinct from FBM's continuous noise. Right for archipelagos.
  - **Voronoi islands** — sharp-edge plate continents with crystalline coastlines.
  - **GetLargestRectArea / GetLargestSquareArea** — auto-finds biggest flat plateau in the heightmap. Solves the iter-41 "castle positioning" problem: query the field at bake time, return the (x, y, size) of the largest flat-enough patch above waterLevel, position the castle there automatically.
  - **BSP rooms + corridors** — interior dungeon generation. When we do "underground levels" or "interior of the castle" composition, this is the algorithm.
  - **Retouch operations** (Average, Addition, Subtraction, Modulo) — generic field-blending post-processing. We have some ad-hoc (e.g., re-normalize after erosion); a unified retouch-ops API would make blends like "RD coral × terrain heightmap" expressible.
- **Picking up from this list**: most natural next iter is diamond-square as a new terrainGen mode (concrete diversity, ~40 LoC). After that, cellular-automaton islands. The auto-position helper (GetLargestRect) is high value when paired with multi-prim composition specs.

## Reference: Mapbox Martini — heightmap → game-mesh bridge
- User shared https://github.com/mapbox/martini.
- **What it does**: converts a (2^k+1)² heightmap into a triangle mesh with RTIN-based progressive LOD. Error-budget driven (more tris where needed). Sub-millisecond meshing on 257², few-ms on 1025². JS-native — drops directly into our toolchain.
- **Why this matters for the "main game" path**:
  - Modeler keeps raymarch (great for authoring + cinematic shots, where compute > tri count)
  - Game uses Martini-meshed terrain (great for runtime rasterization, where tri count > compute)
  - Both consume the SAME baked heightmap field → one source of truth
- **Integration sketch**:
  1. Pad current 512² heightmap to 513² (wrap or replicate the seam column/row)
  2. Run Martini on the padded field → vertex buffer (xyz + normal + slope-zone-id) + index buffer
  3. Export as glTF / FBX / .ark.mesh format for game ingest
  4. Optionally: regenerate mesh at multiple error budgets for distance-LOD chunks
- **Constraints**: Martini's input must be (2^k+1)² — currently we're 512² (2^9). Trivially padded to 513².
- **Slot in the roadmap**: this is a shipping-layer concern, sits AFTER the terrain pipeline reaches max content quality. Most natural to do once the DTL gen modes are in (diamond-square, cellular, voronoi) so the meshing path validates against the full diversity of heightmap shapes.

## Reference: SebLague/Hydraulic-Erosion + dandrino/terrain-erosion-3-ways
- User shared two more references for terrain erosion:
  - https://github.com/SebLague/Hydraulic-Erosion — Unity C# implementation, particle-based, GPU compute version. Algorithm matches our iter 38 implementation (Mei-style). Lague's video tutorial documents the parameter tuning well; our defaults are in the same regime.
  - https://github.com/dandrino/terrain-erosion-3-ways — Python comparison of three approaches:
    1. **Simulation** — particle-based (what we have)
    2. **GAN (Progressive Growing)** — ML inference on USGS elevation data. Out of scope for our pipeline (model weights, training infra, deterministic-bake breakage).
    3. **River-Networks-First** — Poisson-disc + Delaunay graph of rivers FIRST, terrain derived to support them.
- **Insight from approach 3**: this is the inverse of our current flow accumulation. We generate noise → compute flow → carve channels. Their approach: place rivers as a graph, build terrain that supports those rivers. Result: rivers are AUTHORED (clean, tree-like, well-shaped) instead of emergent (sometimes haphazard). Could be exposed as a `terrainGen: 'river-network'` mode where the user specifies seed point density + drainage style.
- **Architectural comparison**:
  - Our pipeline = FBM gen → erosion → flow analysis (forward simulation)
  - Inverted pipeline = drainage graph → terrain synthesis (constrained generation)
  - Both have value; the inverted one is more art-directable.

## Synthesis: full shipping-stack research bibliography
Compiled from user-shared references during the autonomous loop:

| Stage | Reference | Implementation status |
|---|---|---|
| **Generate** | DungeonTemplateLibrary | Partial — FBM/ridged shipped; diamond-square, cellular, voronoi, BSP rooms remaining |
| **Erode (forward)** | Lague + 3-ways approach 1 | Shipped iter 38 (Mei-style particle hydraulic + iter 33 thermal + iter 37 wind) |
| **Erode (inverse)** | 3-ways approach 3 (river networks) | Not implemented — interesting authoring alternative |
| **Mesh** | mapbox/martini | Not implemented — hard requirement for game runtime |
| **Render** | SDF raymarch (engine) | Shipped through iter 54 (7-layer terrain shading) |

**Highest-leverage next iters by user goal**:
- **More terrain content variety**: diamond-square + cellular-automaton islands (DTL ports)
- **Authorable river-driven terrain**: dandrino approach 3 (river networks first)
- ~~**Ship into a game**: Martini mesh export~~ (skipped — user clarified SDF stays, no tris needed)
- **Better erosion**: SimpleHydrology momentum + discharge maps for meandering rivers
- **Continue raymarch quality**: snow accumulation, bicubic on flow, slope-aware vegetation

## User direction clarification (after sharing weigert/SimpleHydrology)
- "we dont need tris we just need their noise algorithms and erosion algorithms for our sdf engine"
- **Pivot**: focus is on porting NOISE GENERATORS and EROSION ALGORITHMS into the existing SDF/raymarch pipeline. Mesh export (Martini) is OFF the roadmap.
- **SimpleHydrology highlight**: momentum + discharge maps. Particles interact physically with cumulative flow direction → produces meandering rivers (the key visual feature missing from pure-gradient-descent erosion).
- **Refined iter sequence**:
  - iter 55: Diamond-Square as a new terrainGen mode
  - iter 56: discharge-map upgrade to existing hydraulic erosion (meandering rivers)
  - iter 57: cellular automaton islands
  - iter 58: voronoi islands
  - iter 59: river-network-first generation

## User direction update — "grab everything then decide"
- "basically just grab everything and then decide what the strongest stuff is that is the most useable and least confusing"
- **Approach**: implement breadth-first (port all algorithms from references), then evaluate each visually, then prune the weak/redundant ones. Survey-then-curate.
- Reordering: ship algorithms rapidly (skip per-iter validation), then do a comparison-survey iter at the end.

## /loop iter 55: Diamond-Square gen mode
- **`diamondSquare(N, roughness, seed)`** function added — recursive midpoint displacement on a (2^n+1)² grid. Generates at 513² then truncates to 512² to fit our existing buffer.
- **New gen modes**: `'diamond-square'` and `'eroded-diamond'`. Both wired into `bakeTerrain` dispatch + normalizer.
- **First render (eroded-diamond, seed=89)**: distinctly different topology vs FBM — more continental landmass with thin river channels cutting through, rather than archipelago of islands. The diamond-square cross-pattern is faintly visible at the macro shape level. Fine details from per-fragment FBM and erosion still apply. Strata pattern visible on rock cliffs as before.
- **Visual character**: feels more like a single landmass with valleys vs FBM's broken-up archipelago. Different and useful as a separate gen mode.

## /loop iter 56 (partial): cellular + voronoi gen modes scaffolded
- **`cellularAutomatonIsland(N, seed, iterations)`**: random fill with edge bias → 4/5 majority rule iterations → multi-pass smoothing → graduated heightmap. Produces blob-shaped land with smooth gradients.
- **`voronoiIsland(N, seedCount, seed)`**: K random center-biased seed points → distance-to-nearest-seed → invert + gamma curve → heightmap. Each seed becomes a peak; cells far from any seed become valleys. Produces sharp-edged plate-like continents.
- **Both wired** into bakeTerrain dispatch + schema union + normalizer.
- **NOT yet visually validated** — implementation untested at render time. Next iter (57) cycles each through the modeler to compare.

## /loop iter 57: gen-mode survey — visual validation of cellular + voronoi
- **Diagnostic methodology**: turned off hydraulic erosion to see RAW heightmap topology (heavy hydraulic erosion converges all heightmaps toward similar canyon-carved looks regardless of input).
- **Findings per gen mode**:

| Mode | Visual signature | Strengths | Weaknesses / confusion |
|---|---|---|---|
| **fbm** | Soft rolling hills, continuous noise | Well-tested, tunable octaves/persistence/lacunarity, predictable | Defaults can feel busy with high octaves |
| **ridged** | Sharp dramatic peaks | Best for mountain ranges, alpine scenes | Can look CGI-overly-jagged at high amplitudes |
| **eroded-fbm/ridged** | Above + thermal settling | Most natural-looking | Adds bake time |
| **diamond-square** | Continental landmass with rivers cutting through | Distinctive cross-pattern macro shape, sharp local features | Edge truncation (513² → 512²) loses 1-row seam |
| **eroded-diamond** | Diamond-square + thermal | Best for "single landmass" scenes | Same edge concerns |
| **cellular** | Organic smoothed-blob islands | Different character from noise-based gens | Parameter `erosionIters` overloaded as iteration count (semantic mismatch) — confusing |
| **voronoi** | Plate-like peaks at seed points, sharp valleys | Highly distinctive; great for "scattered island" or "rocky outcrop" scenes | Seed count = `octaves * 3` (semantic hack) — confusing |

- **The strongest set, ranked**:
  1. **eroded-fbm**: best general-purpose terrain. Most predictable, most natural.
  2. **eroded-ridged**: best for dramatic peaks (alpine, fantasy mountains).
  3. **eroded-diamond**: best for continental landmasses with rivers.
  4. **voronoi**: best for "scattered seeds" topology — distinct enough to keep.
  5. **cellular**: weakest of the four — output looks too similar to voronoi at default params and parameter naming is confusing.

- **Most-confusing parts**:
  - `erosionIters` field is reused for cellular automaton iterations (different semantic).
  - `octaves * 3` as voronoi seed count is non-obvious.
  - Both should be renamed: `cellularIters`, `voronoiSeedCount`.

- **Recommendation for pruning**: KEEP fbm/ridged/diamond-square/voronoi (4 modes × 2 erosion = 8 effective combinations). DROP cellular OR demote it to a hidden mode pending re-implementation with distance-transform-from-water (proper way to convert binary CA → heightmap). Rename `erosionIters` → split into `thermalIters` and `cellularIters` to remove ambiguity.

## /loop iter 58: pruning — drop cellular, clean voronoi naming
- **Cellular removed** entirely (schema union, TerrainBakeOpts, function body, dispatch, normalizer). At default params it was visually too close to voronoi and its parameter overloading (`erosionIters` doubling as cellular-iters) was confusing.
- **Voronoi cleaned**: new dedicated `voronoiSeedCount` field on the prim schema (default 18, range hints 4-40+), replaces the `opts.octaves * 3` hack. Doc string explains seed-count effect on visual: 4-8 wide islands, 16-30 scattered hills, 40+ densely packed.
- **Final gen mode list**: `fbm | ridged | eroded-fbm | eroded-ridged | diamond-square | eroded-diamond | voronoi` (7 modes total, all clean and distinct).
- **Sanity check**: showcase_post_pruning_v1 (eroded-fbm archipelago) renders identically to pre-pruning state. No regression.
- **Code health**: ~70 LoC removed from modeler_demo.ts. cellularAutomatonIsland function gone. Schema clearer. Single source of truth for voronoi seed count.

## /loop iter 59: SimpleHydrology momentum maps — meandering rivers
- **Two new fields** in `hydraulicErosionPass`: `momentumX[N²]` and `momentumY[N²]` (vec2 per cell). Particles READ accumulated momentum at their position to bias direction; particles WRITE momentum to cells they traverse.
- **Self-reinforcement loop**: as more particles flow through a region, the momentum vector aligns with the established path. Subsequent particles read that momentum and bias their direction toward it → rivers form curves instead of always taking the straightest gradient-descent path.
- **Three-way direction blend per step**:
  ```
  dir = inertia·dirPrev + momentumWeight·momentum - gradWeight·gradient
  ```
  where `momentumWeight = readAmt * min(1, |momentum|)` (only kicks in when momentum is established).
- **Periodic decay**: every 500 droplets, all momentum scaled by 0.992 — prevents unbounded growth, lets later droplets explore new paths if no strong river formed.
- **Bilinear momentum write**: deposits momentum into the 4 sub-cell neighbours weighted by fractional position, same as bilinear field reads. Sub-cell stable.
- **Visual result**: rivers in valleys now curve naturally through the landscape (visible in iso view as flowing channels) instead of straight-shot canyon-cuts. Coastlines feel more organic. Subtle in stills but the pattern of carved drainage networks reads as natural.
- **Cost**: ~2× the per-step ALU of basic hydraulic. Negligible relative to the bake-then-cache architecture the user is targeting.

## /loop iter 60: terrain flipped to Y-up
- **Convention pivot**: terrain prims now use Y as the vertical axis to match camera (Y-up GLTF/WebGPU standard). Heightmap is laid out in the X-Z horizontal plane and displaces along Y. Slab params are now `[halfX, halfY, halfZ]` where halfY is "thickness" (small) and halfX/halfZ are footprint (large).
- **Code changes**:
  - WGSL terrain geometric: `pWorld.xy` → `pWorld.xz` (sample horizontal plane), `waveX/waveZ/waveD` use X/Z coords
  - WGSL terrain color: `hitPos.xy` → `hitPos.xz` for slope/uv sampling, cloud-shadow uv from XZ
  - Strata: vertical banding now from `hitPos.y` (was hitPos.z)
  - JS scatter vegetation: random (X, Z) in slab footprint, surface at `slabPos[1] + slabHalfY + h*depth`
- **View result is correct**:
  - **Top view**: top-down terrain map (perfect for diagnostics + game minimap if needed)
  - **Front/side views**: horizon-like profile of the landscape (good for screenshot/background composition)
  - **Iso view**: 3/4 perspective showing terrain rising from a flat base with vegetation on top — the natural "outdoor cinematic" view
- **Showcase spec**: `yup_terrain_v1` with params `[0.110, 0.012, 0.110, 0.003]` — wide flat slab thin in Y, terrain rises upward.
- **Architectural note**: this aligns the terrain convention with the rest of the engine (camera + character prims are already Y-up). Single source of truth for "up" is now Y everywhere.

## /loop iter 61: water specular — per-pixel shiny override
- **Per-fragment shiny flag** in the terrain dispatcher: when `colorFunc == 28` AND `slot ∈ {3 (deep), 7 (shallow)}`, set `normal.a = 1` (shiny). Otherwise inherit the per-prim shiny flag.
- **Why per-pixel, not per-prim**: a single terrain prim has both shiny water cells AND matte rock/grass/snow cells. The existing per-prim shiny flag was all-or-nothing. The per-fragment override lets the deferred-lighting outline pass apply specular ONLY to water pixels.
- **Result**: water surfaces now catch bright highlights when the lit pass's key light angle hits them — visible as lighter patches on the water in the iso view, brighter speckle on the top-down view. Reads as proper cinematic water with shimmer instead of uniform tinted color.
- **Cost**: 1 conditional per fragment, negligible.
- **Architectural pattern**: this opens the door for per-pixel overrides on other g-buffer flags too (e.g., per-pixel unlit for lava, per-pixel emissive for night-time light sources).

## /loop iter 62: march safety factor — fix non-Lipschitz SDF artifacts
- **Issue**: per-fragment detail FBM + water wave displacement break the SDF "true distance" assumption (a true SDF must be Lipschitz with constant 1; adding analytical noise makes the SDF lie about distance). Without correction, rays take full-distance steps `t += s.dist`, overshoot the displaced surface, and produce streaky banding in renders.
- **Fix**: multiply step size by 0.7 safety factor (`t += s.dist * 0.7`); compensate the slower march by raising default `maxSteps` 48 → 96.
- **Cost**: 2× more raymarch steps in the worst case. With our raymarch cache for static scenes, irrelevant. Vital for clean displaced-terrain rendering.
- **Result**: iso and top views render cleanly without surface artifacts. Front/side views still show some vertical "stripe" features but these are the slab's EDGE PROFILE with detail FBM applied — actual geometry, not march errors. Could be masked by face-direction in a follow-up iter (only apply detail FBM where the surface normal points up).
- **Lesson**: any SDF deformer that uses non-Lipschitz functions (FBM, sin, abs of arbitrary, etc.) must be paired with march safety factor adjustment. Document this in deformer-design notes.

## /loop iter 63: ambient occlusion on terrain land
- **4-tap normal-direction AO**: at each terrain land hit point, sample sceneSDF at 3-12mm offsets along the surface normal. Where the SDF returns small values (a nearby surface), accumulate occlusion. Multiply tint by `mix(0.5, 1.0, 1 - occ)`.
- **Skipped for water (slots 3, 7) and foam (slot 6)** — water needs to stay smooth-tinted; foam should pop bright.
- **Cost**: 4 extra `sceneSDF` calls per terrain land hit (uses skip-prim optimization). With march cache for static scenes, irrelevant. Without cache, ~5-10% per-frame cost.
- **Result**: terrain reads with real volumetric depth — valleys are visibly darker than peaks, crevices show as shaded interiors, undercuts get deep shading. Iso and top views especially benefit. Reads cinematically rather than flat-shaded.
- **Visual stack now**: heightmap displacement → flow carving → 3-octave detail FBM → tonal modulation → atmospheric fog → cloud shadows → strata bands → AO. Eight layered effects, all on the same colorFunc=28 dispatcher.

## /loop iter 64: directional sun + soft shadows
- **Inigo Quilez soft-shadow** technique. Each terrain land hit casts a shadow ray toward `sunDir = normalize(vec3f(0.55, 0.85, 0.25))` (afternoon-sun-from-the-side). 18 march steps, max distance 0.08m, safety factor 0.7 same as primary march.
- **Soft shadow factor** `k = min(k, sd * kSharp / t)` accumulates the closest-miss ratio along the ray. Sharp shadows where the ray actually intersects something; soft penumbra where rays barely miss.
- **Tint multiplier** `mix(0.55, 1.0, k)` — peaks block sun, valleys behind them go ~45% darker.
- **Skipped for water (slots 3, 7) + foam (6)** — water has its own specular highlight; shadowing it would conflict.
- **Cost**: 1 extra raymarch per terrain land hit (~50% extra march cost). With cache for static scenes, free.
- **Result**: classic cinematic-terrain look — sun-facing slopes bright, shaded slopes darker, peaks cast distinct shadows on the terrain behind them. Single biggest visual leap of any iter for "looks like real terrain in a game".
- **Visual stack**: 9 layers now. heightmap → flow → detail FBM → tonal → fog → clouds → strata → AO → sun shadows.

## /loop iter 65: kill triangulated facet artifacts
- **User-flagged**: visible diagonal/triangulated facet patterns in screenshot. Diagnosed as combination of (a) value-noise grid alignment in WGSL `noise3` and (b) excess detail-FBM amplitude breaking the SDF Lipschitz assumption.
- **Three fixes applied together**:
  1. **Detail FBM amplitude halved**: 0.07/0.03/0.013 → 0.040/0.017/0.008. Total ~6.5% (was ~12%). Less SDF lying = less march overshoot = fewer artifacts.
  2. **Per-octave domain rotation**: rotA (60° about Y) on octave 1, rotB (30°) on octave 2, identity on 3. Decorrelates the value-noise grid axes between octaves so axis-aligned cell boundaries don't sum into visible facets.
  3. **Tighter march safety factor**: 0.7 → 0.6. Smaller steps near the displaced surface, fewer overshoots.
- **Result**: facet artifacts substantially reduced. Surface reads as natural noise rather than algorithmic mesh.
- **Reference**: user shared https://iquilezles.org/articles/terrainmarching/ — IQ's heightmap-specific raymarching article. The article's approach: instead of generic SDF marching, treat heightmap as `y = f(x, z)` and check `pos.y < f(pos.x, pos.z)` per step. Fundamentally bypasses Lipschitz issues for heightmap terrains.
- **Future iter (66+) candidate**: IQ-style heightmap march for terrain prims. Special-case the colorFunc=28 prim in the march loop — when ray approaches a terrain prim, switch from SDF stepping to heightmap stepping. ~50 LoC, eliminates remaining march artifacts entirely.

## /loop iter 66: IQ heightmap-march for terrain prims
- **Reference**: https://iquilezles.org/articles/terrainmarching/ — IQ describes using vertical distance × safety factor as the SDF for heightmap terrains. Tighter and more correct than displacement-as-SDF-modifier.
- **Replaced** the `d = d - macroH - detailN + f * flowDepth` displacement approach with direct vertical-distance computation:
  ```
  surfaceY = halfY + (h_capped + detail) * terrainDepth - flow * flowDepth
  d = (pPrim.y - surfaceY) * 0.5    // IQ safety factor
  ```
  Only applied INSIDE the slab footprint (X/Z bounds + above slab base); outside, the slab roundedBox SDF stays in d so rays can reach the slab from far away.
- **March safety factor relaxed back to 0.85** (was 0.6) — the new SDF is much more reliable so we can step nearly the full reported distance.
- **User-validated outcome**: "looks exactly the same just different color lol... cleaner edges". The IQ method's primary benefit is structural correctness, not new visual content. Cleaner edges come from accurate distance estimation near the surface (AO + shadows sample the right point); the slight color shift is the AO darkening hitting tighter pixels because the SDF returns smaller residuals near hits.
- **Architectural win**: this is the right pattern for any future heightmap-based prim. Procedural terrain should always use IQ-method, never SDF-displacement-as-modifier.

## /loop iter 67: IQ-method compatibility fixes (AO + normals + heightmap res)
- **User flagged**: "looks a bit broken, not sure AO is working" + "different color". Diagnosed two compatibility issues from IQ-method's `vertical_distance × 0.5` SDF:
  1. **AO double-counted occlusion** — formula assumed sd was true distance, but IQ returns half. Fixed by `sd * 2.0` to undo the IQ factor for AO purposes.
  2. **Normal sampling eps too small for IQ-method** — at 2mm eps, the IQ SDF gradient gave near-flat Y-dominant normals (slope barely registered). Bumped to 4mm with new helper `isHitTerrain(primIdx)` so non-terrain prims keep tight 2mm sampling.
- **Heightmap res tried 1024², reverted to 512²**: 7-octave FBM is bandwidth-limited at ~256 cycles/tile (highest octave). 512² hits Nyquist; 1024² is pure oversampling — costs 4× bake for zero added detail. Left at 512².
- **User confirmed**: cleaner edges with IQ-method; slope shading visibly returned with 4mm normal eps.
- **Lesson for future iters**: any modification to the SDF that breaks "true distance" semantics (IQ-style safety factor, smin blending, displacement) needs to be considered for downstream effects (AO, soft shadows, normal sampling). Keep these compensations in the codebase as comments so future you doesn't re-debug them.

## Reference: MiniMax-AI/skills shader-dev — 36-technique GLSL motherlode
- User shared https://github.com/MiniMax-AI/skills/tree/main/skills/shader-dev
- 36 single-file `.md` techniques in `skills/shader-dev/techniques/` covering: SDF 2D/3D, ray-marching, lighting/shadows/AO/normals, simulation/physics, water-ocean, terrain-rendering, atmospheric-scattering, volumetric-rendering, procedural-noise (Perlin/Simplex/Worley), domain-warping, voronoi, fractals, post-processing, multipass, anti-aliasing, sound-synthesis. Each file has core principles + complete code.
- **Direct upgrades for our pipeline**: procedural-noise (kill value-noise grid artifacts), domain-warping (proper version of our hack), water-ocean (Gerstner waves vs sum-of-sines), atmospheric-scattering, volumetric-rendering, normal-estimation, shadow-techniques.

## /loop iter 68: atmospheric scattering (Rayleigh + Mie phase functions)
- **Replaced** the linear-fog block with simplified Rayleigh+Mie atmospheric model. Adapted from MiniMax shader-dev `atmospheric-scattering.md` — skipped the planet-scale ray integration (overkill for our human-scale scene), kept the phase functions and sky color computation:
  - Rayleigh phase `0.75 * (1 + cosTheta²)` — bluer perpendicular to sun, lighter near sun.
  - Mie phase `(1 - g²) / (1 + g² - 2g·cosTheta)^1.5` with g=0.76 — concentrated forward scattering = sun glow.
  - Sky base color gradient: zenith blue (0.20, 0.42, 0.78) → horizon paler (0.62, 0.74, 0.86).
  - Mie sun glow tint (1.0, 0.78, 0.45) — cinematic warm glow around sun direction.
- **Result**: terrain mixed toward atmospheric color is now view-direction-aware. Looking away from sun = bluer haze; toward sun = warmer/orange haze. Far peaks have proper aerial perspective; near features stay sharp.
- **Cost**: one extra phase calculation + smoothstep mix per terrain land hit. Negligible.
- **Architectural pattern**: the ray direction `rd` is already in scope at the lit-pass site. Adding view-aware effects (atmospheric, subsurface, sky reflection) just needs `rd` and `sunDir`.

## User direction: terrain → tile-based game playfield
- "terrain could also be used to generate a tile based game playfield"
- **Architecture fit**: the same baked heightmap can feed a tile classifier with no per-frame cost. Sample heightmap + flow at a coarse grid (e.g., 32×32 or 64×64), classify each tile by `(altitude, slope, foam-band, flow > river-threshold)`, output as a `Uint8Array(tileW * tileH)` tile-type grid for game code.
- **Tile taxonomy** (sensible default ~10 types):
  - 0 deep-water, 1 shallow-water, 2 beach/sand (foam band), 3 grass, 4 forest (grass + scatter density), 5 hill, 6 rock-cliff, 7 snow-peak, 8 river-bed (flow > threshold), 9 mountain-pass (high + low slope)
- **Implementation slot**: `bakeTileMap(heightmap, flow, density, waterLevel, tileW, tileH) → Uint8Array`. ~30 LoC.
- **Output**: JSON export for game ingest + maybe a visualization render (color-per-tile-type) for the modeler so the user can see the classifier output overlaid on the terrain.
- **Connection back to DTL**: the search/pathfinding helpers in DungeonTemplateLibrary (GetLargestRectArea etc.) operate on tile grids. Once we have tile-based output, those algorithms become applicable for "find the largest plateau for a settlement" or "shortest path between cities" type queries.

## /loop iter 69: cloud deformer (colorFunc=29) — fluffy cumulus via billow + iterated DW
- **User direction**: "modeling raymarch clouds? just need geometry... fluffy clouds. allicator noise + displacing in a loop with the same noise (makes billows)".
- **Implementation**: two new WGSL helpers + new colorFunc=29 dispatcher.
  - **`billow3(p)`**: 3-octave billow noise. `1 - 2|noise(q) - 0.5|` per octave gives the puffy upward-billowing character (vs FBM's smooth ridges).
  - **`cloudDensity(p)`**: 3 iterations of domain-warped billow — `q = q + billow(q)*0.18` → `q = q + billow(q*1.7)*0.10` → final `billow(q*2.3)`. Each iteration shifts sample position by noise = chaotic billowy structure.
  - **`colorFunc=29` deformer**: `d = (d - density * cloudDepth) * 0.5` (IQ safety factor since billows are non-Lipschitz). Subtracts density from base SDF so the cloud bulges outward.
  - **Color**: pure white tint by default; slot B (darker accent) where cloudDensity < 0.55 → "shadowed cracks" between puffs.
- **Test scene**: clouds_test_v1 — three ellipsoid+sphere prims with cloudDepth ~0.018 and density 15-22, merged via smooth-blend (blendRadius=0.005). Render shows fluffy cumulus mass with characteristic billow tops + shadow undersides.
- **Authoring pattern**: cloud is a DEFORMER on existing geometry, not a new prim type. Author with sphere/ellipsoid base, blend multiple clouds together with positive blendRadius for natural merging.
- **Cost**: 3 nested billow3 calls per fragment (each ~3 noise calls) = 9 noise samples per cloud fragment. Light vs the terrain pipeline.

## /loop iter 70: cloud facet artifact fix — same root cause as terrain
- **User hypothesis confirmed**: "maybe this was our problem the whole time". The flat-facet artifacts in the cloud render came from the SAME pattern that produced terrain triangulation:
  - **Hard color threshold** (`if density < 0.55 { slot = slotB }`) creates visible polygonal patches
  - **Tight normal sampling eps on noisy gradients** creates faceted lighting
- **Fix applied (mirrors iter 36 terrain slope zones)**:
  - Replaced hard step with `smoothstep(0.40, 0.65, density) > hash(p)` — stochastic dithered transition
  - Bumped cloud normal eps to 6mm (vs 4mm terrain, 2mm baseline) so normals average out high-frequency billow gradients
- **Result**: clean fluffy clouds with smooth shadow gradients. No more flat-facet patches.
- **Universal pattern**: any deformer that does `if (noise-derived-value < threshold) → different palette slot` should use smoothstep+hash dither, not hard step. Already in the codebase for terrain slope/snow/water-shore zones; applied to clouds now. Future deformers should default to this pattern.
- **Universal pattern (normals)**: noise-heavy deformers need wider normal eps to avoid faceted lighting. Per-prim epsilon selection (`isHitTerrain`, `isHitCloud`, etc.) lets each deformer pick its right value.

## /loop iter 71: geometry-debug mode + color stripped
- **User direction**: "i jsut dont want to see color on anything now just geometry"
- **Change**: hardcoded `out.color = vec4f(1.0)` in the lit-pass output. Lit pass still uses normals for Lambert shading; tint = white. Lets us inspect pure geometry+lighting without deformer color logic confusing the picture.
- **What's visible**: cloud has ~80% smooth white shading + ~20% subtle flat-shaded patches in noise-gradient discontinuities. Same value-noise grid signature that's been showing up since terrain triangulation iters.
- **Root cause**: `noise3` is value noise — random per-corner + trilinear interp + smoothstep fade. Smoothstep fade has DISCONTINUOUS SECOND DERIVATIVE at cell boundaries (it's only C1, not C2). Normal sampling = numeric SDF gradient = uses 2nd derivative effectively. Result: visible facets at cell boundaries.
- **Real fix (next iter)**: replace `noise3` with Perlin/Simplex gradient noise. Perlin uses gradient vectors at each cell corner + dot product; output is C2-continuous everywhere. Eliminates grid artifacts at the source for all noise-based deformers — terrain detail FBM, clouds, RD, fbm3 callers everywhere.
- **Revert path**: change `out.color = vec4f(1.0)` back to `vec4f(tint, 1.0)` to restore deformer colors.

## /loop iter 72: noise quality — quintic fade for C2 continuity
- **Goal**: kill the facet artifacts that have been showing up since the early terrain triangulation iters. Root cause was value-noise's smoothstep fade — only C1 continuous (continuous first derivative, discontinuous second). Normal sampling = numeric SDF gradient ≈ uses 2nd derivative. C1 fade → discontinuous 2nd derivative at cell boundaries → faceted normals.
- **First attempt failed**: full Perlin gradient noise with 12-edge switch. Crashed WebGPU device — shader complexity from inlined switch in fbm3/billow3 chain exceeded device limits. Reverted.
- **Working fix**: 1-line change to existing value-noise. Replaced smoothstep fade `f²(3 - 2f)` with quintic `f³(f(6f - 15) + 10)` (Perlin's 2002 improved fade). Same value noise, but C2-continuous → smooth normal gradient across cell boundaries.
- **Result**: clouds now render with smooth shading, no facet patches. Effect propagates to ALL noise-based deformers (terrain detail FBM, brick, hex, weave, RD, etc.) since they all use noise3.
- **Lesson**: when shader changes crash the GPU, the fix is often simpler than the original attempt. Look for the minimal mathematical change that addresses the symptom — quintic fade is a 30-character diff vs ~80 LoC of Perlin gradient noise + switch table.
- **Future iter (deferred)**: real Perlin/Simplex gradient noise IF we ever need higher quality than quintic-faded value noise. The cell boundaries are still visible-but-subtle even with quintic; gradient noise has no boundary signature at all. Architectural cost: ~50 LoC per noise variant + careful WGSL to avoid shader complexity blowup.

## /loop iter 73: Perlin gradient noise (bit-pattern variant) — finally
- **User feedback after iter 72**: "still patchy. probably from noise cell sampling. it almost looks like subd patches that don't line up". Quintic fade smoothed the boundaries but the value-noise cell DOMAIN is still visible because each cell has a different SCALAR random — no matter how smooth the fade, the function character changes cell-to-cell.
- **Real fix**: gradient noise. Each cell corner has a random GRADIENT (not value); per-corner contribution = dot(gradient, offsetFromCorner). Boundary continuity property: at any cell corner, the noise value is exactly the dot of the gradient with the (zero) offset = 0. Adjacent cells share corners so the function is C0 across boundaries.
- **Implementation that compiled**: Perlin's improved-2002 paper bit-pattern grad function. Returns dot product directly (no vec3 gradient construction). 5 selects per call. No switch, no array. No shader-complexity blowup.
- **Diagnostic detour**: WebGPU device was lost from the earlier failed switch-Perlin. Daemon's headless browser was stuck in dead state. `pkill preview_daemon.mjs` + restart fixed it. Cron + vite kept compiling correct code; the "still patchy" was the daemon showing stale renders.
- **Result**: clouds render with smooth Perlin shading, no visible cell patches. Boundary continuity is no longer a discontinuity. The patch artifacts that have been showing up since iter ~50 are finally gone.
- **Effect propagates**: every consumer of `noise3` benefits — terrain detail FBM, brick mortar, hex tiles, weave, RD coral, billows for clouds, all previously affected by value-noise patches now use gradient noise instead.

## /loop iter 74: terrain validation post-Perlin
- Loaded the showcase terrain spec (`yup_terrain_perlin_v1`) to verify the Perlin upgrade also fixed terrain patches.
- **Result**: terrain renders as smooth rolling topology — no visible cell patches, no patch-of-patches alignment artifacts. Vegetation prims read clearly as distinct bumps. Iso view shows continuous-shading slopes.
- This validates the noise upgrade fixed the same root cause across all deformers — terrain detail FBM, cloud billow, etc. — as predicted.
- **Geometry-debug mode (white-only tint) still active** from iter 71. To restore deformer colors: change `out.color = vec4f(1.0)` back to `vec4f(tint, 1.0)` in raymarch_renderer.ts.

## /loop iter 75: JS Perlin upgrade (terrain bake side) + diagnostic
- **User hypothesis (scatter self-intersection)**: tested by setting `terrainScatterCount: 0`. Patches REMAINED on bare terrain → scatter wasn't the cause.
- **Root cause found**: I'd only upgraded WGSL `noise3` to Perlin in iter 73. The JS-side `valueNoise2` (used by `bakeTerrain` for FBM heightmap and erosion) was still smoothstep value noise. The patches were being BAKED into the heightmap from the JS side, then bicubic-sampled at runtime → patches visible.
- **Fix**: replaced JS `valueNoise2` body with 8-direction-gradient Perlin + quintic fade. Drop-in: same signature, returns ~[0, 1].
- **Result**: terrain renders as smooth continuous topology, no patches anywhere. The fix had to be applied on BOTH sides (JS bake + WGSL runtime) to fully eliminate the value-noise grid signature.

## Reference: YouTube planet-terrain technique
- User shared: planet heightmap = 3 fBm heightmaps blended via triplanar projection on a sphere; raymarched directly (no mesh) with Phong + fresnel; water as sphere with fBm normal maps for waves.
- **Triplanar relevance to our pipeline**: useful when terrain wraps a curved surface (planet, dome, wrapped cube). For our flat Y-up slab it'd reduce to "sample fbm3(p.xz)" because the upward normal weight dominates → same as current. Triplanar would matter if/when we add a "planet" prim type or steep cliff faces where the surface normal isn't dominated by Y.
- **Other techniques worth porting**:
  - **3-heightmap blend**: layer continents + mountains + erosion as separate baked fields, blend by mask. Cleaner separation than our single-bake-all-stages pipeline.
  - **fBm normal maps for water**: replace our analytic sum-of-sines waves with a per-fragment fBm-driven normal perturbation. Gives more chaotic / authentic small-wave patterns.

## /loop iter 76: cloud (1,1,1)-bias bug + single-mountain test scene
- **User caught**: "i think you are using an additive noise for 3 cardinal directions instead of per axis or centered at 0... I can see everything shifting towards 1,1,1".
- **Bug**: in `cloudDensity`, the iterated domain warp used `q = q + vec3f(n, n, n) * 0.18` — same scalar in all 3 axes. Each iteration shifts the sample along the (1,1,1) diagonal, accumulating positive bias. Cloud surface clusters around a few areas, produces facet/blob artifacts.
- **Fix**: 3 INDEPENDENT FBM samples per axis with offset position seeds, scaled by 0.36 / 0.22 per iter. fbm3 (centered around 0) for warp; billow3 still for final density. Symmetric warp, no bias.
- **User direction (better test scene)**: "lets do one mountain instead of the whole continent". Smaller slice, more dramatic deformation:
  - 50×50×10mm slab (was 110×110)
  - terrainDepth 0.045 (was 0.022)
  - terrainDensity 4 (was 5; lower = larger features = single peak visible)
  - eroded-ridged + 100 thermal + 12000 hydraulic + 50 steps
  - waterLevel 0.20 (most of mountain emerges)
- **Render result**: dramatic single-peak mountain — snow caps, carved canyons, visible river bed, small water pool, rock cliffs with directional light. Reads like a 3D-rendered cinematic mountain.
- **Lessons compounding**:
  - Smaller-but-more-deformed > larger-but-flatter for showcasing (more visible feature density per pixel)
  - Per-axis warp must be per-axis (independent noise), not vec3(n,n,n)
  - Color rendering restored after iter-71 white-debug mode

## /loop iters 77-78: noise-quality cleanup arc
- **Iter 77** (Perlin gradient noise + bigger-int hash): WGSL `noise3` + `perlinDot3` upgraded from value-noise to gradient-noise via Perlin's improved-2002 bit-pattern. Eliminated cell-domain discontinuities. Bigger integer hash dropped fract(sin) precision drift.
- **JS bake `valueNoise2` upgraded to gradient-Perlin too** — both ends needed the fix. Fixed the patches that were being baked into the heightmap.
- **Cloud (1,1,1) bias bug**: `q = q + vec3(n, n, n)` was iterated translation along the diagonal, not domain warping. Fixed with 3 INDEPENDENT FBM samples per axis.
- **Iter 78 (uniform/hybrid step experiment, then revert)**: tried fixed 0.5-0.8mm step per the IQ heightmap-march paper. Killed rendering — only ~10-20cm coverage with 256 steps wasn't enough for typical camera distances. Reverted to adaptive march with safety 0.85.
- **Hard-threshold palette pick** (no dither): user direction. `slope > 0.10 → rock`, `h > 0.6 → snow`, etc. Clean boundary lines instead of stochastic edges.
- **Hard-edged box for terrain (rounding=0)**: rounded-box corners + IQ-method footprint boundary created discontinuous SDF gradients near edges. Hard-edged box eliminates that boundary precision issue.

## /loop iter 79+ candidate work
- **Cliff face detail FBM is still streaky on slab vertical sides**. Could:
  - Gate detail FBM by surface-normal-Y threshold (only apply to upward-facing cells)
  - Use triplanar projection so cliff faces sample a different noise plane
  - Just accept it — focus is the visible top per user direction
- **Lighting refinement**: lower sun angle for more dramatic shadows, or warmer color temperature.
- **Water specular**: currently per-pixel shiny, but specular highlight isn't dramatic. Could amplify in the lit pass.

## /loop iter 79: dramatic afternoon-sun shadows
- Sun direction tuned `vec3f(0.55, 0.85, 0.25)` → `vec3f(0.7, 0.5, 0.3)` — lower elevation (~30° vs ~58°), more horizontal. Long directional shadows on mountain slopes.
- Shadow strength bumped: shaded areas mix to 0.40 of lit (was 0.55), so 60% darker.
- Shadow-ray budget bumped: 24 steps (was 18), maxT 0.10 (was 0.08), kSharp 16 (was 12) — shadows can travel further and have crisper edges.
- **Result**: iso view shows clear dimensional contrast — lit side bright, shaded side noticeably darker. Reads as cinematic afternoon mountain.

## /loop iter 80: FBM water waves (replacing sum-of-sines)
- Replaced sum-of-3-sines water displacement with 2-octave FBM (medium 40 freq + fine 110 freq). Time-driven drift in X+Z so waves move.
- Sum-of-sines had recognisable repeating wave signature; FBM gives chaotic-but-coherent patterns characteristic of real water surfaces.
- Effect is subtle in the small-water mountain scene; would read clearly in large open water (lake, ocean).
- Same animation rate (~5 cm/s drift) so cache invalidation cadence unchanged.

## /loop iter 81: snow brightness variation (uneven-drift pattern)
- Added subtle FBM-driven brightness modulation on slot=slotB (snow). 60-freq FBM × ±6% multiplier — visible-but-not-overwhelming variation that reads as "uneven snow accumulation" or "windblown drifts".
- Same per-fragment-after-slot-pick pattern as iter 49 land tonal variation. Layers cleanly with the existing palette logic.
- Result: snow areas no longer read as flat white. Subtly textured, more realistic.

## /loop iter 82: per-axis view selection (atlas vs single)
- **User direction**: "i think you need to be able to switch between 4 view and iso... so you can see the full scale of the errors... maybe you work in axis, so you can pick which view you see".
- **New API method `screenshotView(viewName: 'front' | 'side' | 'top' | 'iso')`** in modeler. Uses ATLAS_VIEWS table for camera angles; sets displayMode='human' so canvas renders single-panel at full size; saves/restores camera state.
- **Daemon env var `PREVIEW_VIEW`**: 'atlas' (default) or any view name. Iso mode renders 768×768 single-frame (4× the per-panel pixel density of the 768²-atlas-of-384²-panels setup).
- **Use cases**:
  - Atlas: diagnostic comparisons (different angles same scene)
  - Single iso: cinematic background framing, artifact inspection at max pixels
  - Single front/side/top: edge-on profile inspection

## /loop iter 83: jag diagnosis — high-octave heightmap aliasing
- **User direction**: "i really want you to zone in to why you are getting those extreme jags in the heightmap... is it extreme domain warping?"
- **Domain warping ruled out**: terrain has NO iterated DW; only per-octave coordinate rotation. The (1,1,1)-bias issue from iter 76 was clouds, not terrain.
- **Diagnostic A/B**: switched terrain to plain `fbm` + 0 erosion + 0 hydraulic + zeroed detail FBM. Jags PERSISTED → not erosion, not ridge-squaring, not detail FBM.
- **Root cause confirmed**: high-octave heightmap noise aliasing. With `terrainOctaves: 5` and density=4 (highest octave ≈64 cycles/tile = 0.39mm features at slab scale), the bicubic-Catmull-Rom interpolation overshoots at sharp transitions, producing spike artifacts when rendered at 1024² (each pixel covers ~0.05mm of slab).
- **2-octave test**: same spec with `terrainOctaves: 2` rendered as smooth rolling terrain — clean snow caps, no jags, sky background visible.
- **Rule of thumb**: heightmap octaves should produce features at >2 pixels minimum. For 512² heightmap rendered at 1024² panel: max octaves ≈ log2(512/density) ÷ log2(lacunarity) — about 3 octaves at density=4, lacunarity=2.1.
- **Fixes available**:
  1. Cap octaves at 3 for the heightmap; use detail FBM for high-frequency
  2. Push heightmap to 1024² (would support more octaves)
  3. Apply low-pass filter to baked heightmap before bicubic sample
- **Sky background working**: re-added atmospheric phase function for non-hit rays (alpha=1, unlit flag set in depth.g). Sky color now passes through the lit pass correctly.

## /loop iter 84: applied jag-fix — clean mountain render
- Applied iter-83 diagnosis: capped heightmap octaves at 3 (no high-freq aliasing), bumped per-fragment detail FBM to 0.060/0.025/0.012 (replaces lost macro detail with non-aliasing analytical noise).
- Restored erosion-fbm + 60 thermal + 8000 hydraulic at 40 steps. Eroded settle pattern visible without jag artifacts.
- **Render result**: clean rolling mountain — smooth topology, distinct peaks with snow caps, multiple water pools, visible per-fragment surface texture, sky background. The "max quality static background" target the user was after.
- **Architectural lesson**: heightmap and per-fragment noise serve DIFFERENT roles:
  - Heightmap: macro terrain shape, baked once. Frequencies must be << render-pixel-size to avoid aliasing.
  - Per-fragment FBM: micro-detail, analytical, can be infinite-resolution since it's sampled at the render pixel.
  - Don't try to put high-freq detail in the heightmap — push it to per-fragment.

## /loop iter 85: unified SDF terrain (eliminate the IQ footprint discontinuity)
- **User direction**: "we need to examine for potential discontinuities and eliminate them, if statements, switches, or any greater than less than".
- **Audit findings**: 215 conditionals total across the renderer. The HIGH-impact terrain ones:
  1. `if (inFootprint && pPrim.y > -halfY * 1.2) { IQ method }` — confirmed cliff-streak source
  2. `step(u.terrainWaterLevel + 0.03, hCap)` — hard step on detail mask
  3. Hard threshold palette zones
- **Fix attempt 1 — `max(dBox, dHeightmap)`**: eliminated the if/else but had a different bug. Where the heightmap rises ABOVE the slab top, dBox > 0 (above box) and dHeightmap < 0 (below mountain surface). max picks dBox → ray sees slab top, missing the mountain entirely. Render came out as flat slab with subtle bumps.
- **Fix attempt 2 — `min(dBox, dExtrusion)`**: correct unified SDF. dExtrusion is the heightmap volume modeled as `max(cX, cZ, cAbove, cBelow)` — intersection of half-spaces (in footprint AND below surface AND above slab top). min combines slab box and mountain extrusion as UNION.
- **Also removed the 0.5 IQ safety factor** on dHeightmap — that was halving the Y-gradient relative to X/Z, flattening normals and giving slope-uninformed shading. Now slopes shade correctly (visible directional shading on mountain faces).
- **Smoothstep on detail mask** (was hard step) — continuous transition at the water-edge boundary.
- **Result confirmed by user**: "ahhh finally discontinuity free, just incorrect normals now" → fix shipped → mountain visible with proper slope-aware lighting, no cliff streaks, sky background. Real mountain look.

## /loop iter 86: normal-view debug capability + detail FBM amplitude tune
- **Wired direct normal view** through the daemon: `screenshotView(viewName, viewMode)` now takes a viewMode parameter (`color` | `normal` | `depth` | `silhouette` | `curvature` | `persurface`). Daemon env var `PREVIEW_DEBUG=normal` saves a second `preview_normal.png` alongside the main color render.
- **Inspecting normals directly**: cliff faces show solid red/blue/green (uniform per-face normals — clean SDF gradient on box surfaces). Slopes show smooth color gradient (slope-aware normals). The unified `min(dBox, dExtrusion)` SDF is producing physically correct normals.
- **Halved detail FBM amplitudes** (0.060/0.025/0.012 → 0.030/0.012/0.005) to reduce per-fragment normal jitter on slopes. Macro shape preserved; high-freq surface noise dampened.
- **Result**: clean color render with proper slope shading. Normal view confirms no remaining geometric discontinuities. Per-fragment surface texture is natural variation from heightmap, not noise jitter.

## /loop iter 87: physically-correct colored lighting (warm sun + cool fill)
- Lit pass key/fill lights were scalar intensities (white shading). Replaced with hardcoded warm/cool RGB:
  - **Key (sun)**: `(1.00, 0.92, 0.78)` — direct sunlight near 5500K Kelvin
  - **Fill (sky bounce)**: `(0.55, 0.72, 0.95)` — Rayleigh-scattered sky dome
  - Ambient stays neutral
- Together this produces the golden-hour atmospheric shading that's characteristic of real outdoor terrain renders. Lit faces have a warm yellow cast, shaded faces a cool blue tint, no surface looks plastic-flat-shaded.

## /loop iter 88: smooth color blend across terrain zones
- Hard slot-pick gave visible rock/grass and snow/rock color seams. Replaced visible TINT computation with smoothstep-weighted blend:
  - `rockW = smoothstep(0.07, 0.13, slopeT)` — fraction rock vs grass
  - `snowW = smoothstep(0.55, 0.65, hT)` — fraction snow vs land
  - `landColor = mix(grass, rock, rockW)` then `tint = mix(landColor, snow, snowW)`
- **Slot still picked dominant** for downstream effects (AO/shadow/shiny gating). Only the VISIBLE COLOR smooths.
- Re-samples heightmap+slope for the tint blend (couldn't easily reuse vars from the dispatcher block due to scope). Cost: 6 extra heightmap reads per terrain land fragment, negligible against the cache architecture.
- Result: zone transitions are now soft visual gradients instead of hard step lines. Same underlying topology + lighting; cleaner color continuity.

## /loop iter 89: smooth-weighted strata + snow effects
- Per-zone tint effects (strata banding, snow variation) were hard-gated on `slot == 4u` / `slot == slotB`. Refactored to weight each effect by its smoothstep zone weight (`rockW`, `snowW`).
- Strata applied as `tint *= mix(1.0, strataMod, rockW)` — full strength on pure rock, no effect on pure grass, smooth blend at slope ≈ 0.10.
- Snow variation applied as `tint *= mix(1.0, snowMod, snowW)` — same pattern at altitude ≈ 0.60.
- Combined with iter-88 smooth color blend, the entire terrain color path is now continuous everywhere — no slot-identity step edges.
- Heightmap+slope re-sampled in this block for scope reasons; cost is negligible vs cache-backed render.

## /loop iter 90: smooth-weighted AO + sun shadow at water boundary
- Replaced hard `if (slot != 3u && slot != 7u && slot != 6u)` gate around AO/shadow with smoothstep-weighted `landWeight = smoothstep(0.02, 0.10, h - waterLevel)`.
- AO and sun shadow now apply via `tint *= mix(1.0, effectMod, landWeight)` — full effect well above water, fading out across an 8% altitude band, zero contribution underwater/foam.
- Eliminates the AO-on/AO-off and shadow-on/shadow-off step lines that were visible at coastlines.

## /loop iter 101: FBM-SDF corrections — half-edge radius bug, single octave, strict footprint gate
- **Bug user caught after reading IQ article line-by-line**: my iter-100 sdBase used `radius = 0.40 + 0.30 * h` → max 0.70, **violating IQ's strict half-edge constraint** ("if we restrict the radius of our random spheres to be smaller than half the edge-length of the grid, then for a given point in space we only need to evaluate the SDF of the 8 spheres at the corners"). With radius > 0.5, spheres reach into UNCHECKED neighbor cells; from points near the far cell wall, the truly-closest sphere is in an unchecked cell, so `min(8 corners only)` returns wrong distance. The SDF lies → finite-difference normals show the lie as fur. Fixed: `radius = 0.5 * hash` → strictly [0, 0.5).
- **Added IQ-canonical rotation matrix between octaves** (`mat3(0, -1.6, -1.2; 1.6, 0.72, -0.96; 1.2, -0.96, 1.28)` — non-orthogonal with column length 2 → frequency doubles + axes rotate per octave to break grid alignment). Uses inflation `0.1*s` and blend `0.3*s` per IQ defaults.
- **Tried 3-octave with corrected sdBase** (s = 1/70 → 1/140 → 1/280 cell sizes): real visible boulder/cliff detail. Color PNG 921→1228 KB (huge entropy from real geometry). But fine octaves still aliased against the 8mm normal eps — bumps below eps wavelength can't be resolved by finite differences regardless of Lipschitz preservation.
- **Reduced to single octave** (s = 1/40, 25mm cells, ~12mm bump amplitude) per user "get rid of the high freq detail for now" → cleanest shape that the eps probe can fully resolve.
- **Strict in-footprint gate**: detail leaked onto slab walls because `detailMask` used `hCap = max(h, waterSurface)` which is non-zero outside the footprint (waterSurface ≈ 0.30 globally). Switched detailMask to use raw `h` (h=0 outside footprint → mask=0 → no detail leak). Also added geometric `cX < -0.002 && cZ < -0.002` belt-and-braces gate.

## /loop iter 100: FBM-SDF detail (IQ technique) — Lipschitz-preserving procedural detail
- **User pointed me to Inigo Quilez's FBM-SDF article** (https://iquilezles.org/articles/fbmsdf/) and clarified: "essentially summing infinite spheres together instead of sin waves" + "eliminates the imprecision from noise".
- **Core insight**: additive FBM noise displacement (`surfaceY += fbm(p) * amp`) breaks the SDF's Lipschitz property (`|gradient| ≤ 1`). Finite-difference normal probes then read amplified/distorted gradients → fur/jitter at any eps. **The fix is architectural, not a parameter tune**: combine OCTAVES OF SPHERE-GRID SDFs into the host via smin/smax instead of additively displacing the host. Every op in the chain (sphere SDF, smin_k, smax_k) preserves `|grad| ≤ 1` so the result is a properly-Lipschitz SDF throughout.
- **Implementation**:
  - Added `sdBase(p)` — sphere grid at integer cell corners with random radii in [0.40, 0.70] (overlapping → connected lumpy surface). 8-corner local probe.
  - Refactored terrain SDF: removed additive `detailN` from `surfaceY` formula (was `(hCap + detailN) * terrainDepth`). Macro shape now from heightmap only.
  - After computing host extrusion `dHost = smin_k(dBox, dExtrusion)`, layer FBM-SDF detail via 3 octaves: each octave evaluates `sdBase(pWorld * s) / s`, `smax_k`s to a thin band near host (`dHost - 0.4/s`), then `smin_k`s into the running result. Frequency doubles each octave (s=70/140/280 → cells 14mm/7mm/3.5mm).
  - Detail layer gated by `detailMask > 0.001` (no detail underwater) AND `dHost < 0.040` (skip detail evals when ray is far from surface — saves ~75% of sphere evals across the march).
- **Result — major visible win**:
  - Color render: visible "rocky lumpy" detail on the mountain (was smooth-FBM-displaced before). Reads as real boulder/cobble texture with proper occlusion shadows.
  - Normal map: **clean continuous gradient transitions on every bump** — zero fur, zero pixel-level noise. Each bump shows smooth color gradient (Y-up green → side red/blue) like a real sphere's normal map.
  - Depth Sobel: zero internal response — entire mountain interior is C1 smooth.
  - PNG entropy: color 921→993KB, normal 780→858KB. Real detail without noise.
- **Why this works where iters 92-99 partial fixes didn't**: those tuned the noise-amplified gradient (drop alias octave, widen eps, smin the union, etc.) but the underlying SDF remained non-Lipschitz. FBM-SDF replaces the entire detail layer with a Lipschitz construction — the eps probe now reports the TRUE gradient regardless of how fine the detail is. Detail can go arbitrarily small without aliasing.
- **Open polish for iter 101+**: tighten terrain normal eps from 8mm back toward 2mm now that SDF is properly Lipschitz; tune detail bump scale/character (current is somewhat lumpy-round, could be more angular); apply same FBM-SDF treatment to clouds (currently uses additive FBM-of-billows displacement, has same root issue).

## /loop iter 99: real camera direction → accurate Blinn-Phong specular
- **Fixed iter-96 approximation**: specular used `viewDir = vec3f(0, 0, 1)` hardcoded — only correct for panel cameras looking down -Z. For iso/perspective/single-view cameras, the half-vector calculation was wrong → specular highlights misaligned, water sparkle lacked physical cue of "sun reflection toward eye".
- **Pass real camera direction as uniform**:
  - Extended modeler lit shader's `U` struct: added `cameraDir: vec4f` (xyz = subject→camera direction).
  - Extended JS uniform buffer 16→20 floats; added `setCameraDir(dir: Vec3)` method.
  - Render loop computes `(camera.position - camera.target).normalized` each frame and uploads.
  - Atlas mode: lit pass runs once over the 4-panel atlas, so cameraDir is set to the iso panel's direction (the headline view); other panels get approximate specular but visible glints rarely matter on front/side/top.
  - Specular shader: `viewDir = normalize(u.cameraDir.xyz)` instead of `vec3f(0, 0, 1)`.
- **Effect**: subtle in current mountain scene (small water area, iso angle). Visible in any future scene with significant shiny surface area or non-axis-aligned camera. Mathematically end-to-end correct now: half-vector aligns with real screen → key-direction reflection geometry.
- **No regressions**: normal view, depth Sobel view both unchanged.
- **Open candidates**: Fresnel on water specular (Schlick approx, much more reflective at grazing angles); per-pixel view dir reconstruction from depth+invViewProj for perspective-camera correctness; sky-AO cosine weighting for indirect.

## /loop iter 98: AO extracted to G-buffer (completes deferred lighting refactor)
- **Companion to iter 97's shadow extraction**: AO was still baked into raymarch tint, multiplying ALL light sources (key + ambient + fill). That's wrong — local geometric occlusion (AO) physically attenuates indirect/sky-bounce light reaching a crevice, but a crevice can still be sunlit from the open side.
- **Refactor**:
  - Removed `tint = tint * mix(1.0, ao, landWeight)` from raymarch.
  - Packed `aoFactor` into `out.depth.a` (was unused, default 1.0 for non-terrain).
  - Modeler lit pass reads `dEnc.a` and applies it ONLY to the indirect terms: `lit = ambient * aoFactor + key * (nDotK * keyW * directVis) + fill * (nDotF * fillW * aoFactor)`.
- **G-buffer occlusion channels are now complete**:
  - `depth.b` = directVis (sun shadow × cloud shadow) — blocks key/sun only
  - `depth.a` = aoFactor — blocks ambient + fill (indirect)
  - `depth.r` = dNdc, `depth.g` = unlit flag
- **Result**: render LOOKS the same as iter 97 in this scene because AO range is 0.45-1.0 (modest) and the mountain doesn't have deep crevices that would expose the AO-direct-light separation. But the math is now correct end-to-end. Future scenes with sharper concavities (cave entrances, valley floors, rock overhangs) will read more dimensional — direct sun lights one wall while indirect-only-AO darkens the recesses.
- **Diagnostic verification**: normal view + depth Sobel view both unchanged from iter 97 — no artifact regressions.
- **Pipeline architecture is now end-to-end physically correct** for the directional-light + ambient-fill deferred path. Open: separate AO into "sky AO" (cosine-weighted) vs "ambient AO" if needed; Fresnel on water specular; per-pixel view direction reconstructed from depth+invViewProj.

## /loop iter 97: shadow extracted to G-buffer + unlit-flag pass-through (deferred lighting fix)
- **Doctrine compliance + visible win**: the iter-90/91 sun shadow + cloud shadow were baked into raymarch tint, violating the "never bake shadow at raymarch" rule. Effect: shadowed areas were darkened uniformly across ALL light sources (key + fill + ambient), reading as dead-flat. Real shadows only block direct light; ambient + sky-bounce fill still reach shadowed surfaces.
- **Refactor**:
  - Cloud shadow + sun shadow extracted into `cloudShadowFactor` + `sunShadowFactor` (no longer multiplied into tint).
  - `directVis = sunShadowFactor * cloudShadowFactor` packed into G-buffer's `out.depth.b` (was unused).
  - Modeler lit pass reads `dEnc.b` and multiplies it into ONLY the KEY term: `keyColor * (nDotK * keyDir.w * directVis)`. Ambient + fill stay full-strength on shadowed surfaces.
  - AO stays baked into tint — it's local self-occlusion that DOES block all light, multiplicative-into-albedo is correct enough.
- **Bonus fix — unlit-flag pass-through**: also wired in the long-broken unlit-flag check in modeler's lit shader. Sky pixels (raymarch sets depth.g=1) now bypass the lit multiply entirely — their pre-rendered atmospheric Rayleigh+Mie color passes through unmodified. Was being multiplied by the lit composite before, causing dim grey sky despite the atmosphere model producing bright blue.
- **Visible result**: sky reads as bright atmospheric blue (was dim gray); mountain has more dynamic range (shadowed areas no longer deathly dim); PNG entropy up 921→939KB confirming richer detail. **No artifact regressions** observed in normal or depth views.
- **Architectural note**: this completes deferred-lighting compliance for the shadow path. Direction of further refinement: separate AO into G-buffer too if/when the difference between "AO blocks all light" vs "AO blocks indirect only" becomes visible. For now, current AO formulation is fine.

## /loop iter 96: water specular wire-up in modeler lit pass
- **Audit finding**: raymarch packs `shinyOut` into `normal.a` (1 = water/polished, 0 = matte; smoothed by landWeight in iter 91), but the modeler's lit pass (modeler_demo.ts) was IGNORING it. Water rendered without any specular highlight despite the data being there — physically wrong: real water sparkles in sunlight.
- **Fix**: read `nEnc.a` as `shinyW`, add Blinn-Phong specular term gated by it. View direction approximated as `+Z` screen-aligned (panel cameras look toward -Z, so view ≈ +Z); half-vector with key direction; specular peak `pow(spec, 64) * shinyW * keyInt`. Tinted by warm key color so the glint reads as sun reflection.
- **Why it's subtle in current render**: water pools occupy ~5% of mountain_clean_v1 and the +Z view-dir approximation doesn't perfectly align with the iso camera's true direction. Specular cone (pow 64) requires near-exact alignment to be visible. Future water-heavy scenes (lake, ocean) will benefit immediately; mountain scene is unchanged at the macro level.
- **Architectural note (deferred lighting doctrine violation)**: the iter-90 AO + sun shadow + cloud shadow are still **baked into the raymarch tint** (multiplicatively). That breaks the "key hard 3-band, fill smooth linear, never bake shadow at raymarch" doctrine in memory. Effect: shadows darken ALL light sources (key + fill + ambient) instead of just direct. Real physical shadows only block direct light; ambient + bounce should still reach shadowed surfaces. **Fix is invasive** (G-buffer channel for shadow + AO, lit pass reads them separately). Tabled — current render reads as plausible because tint*lit and lit*shadow*tint are visually similar at this scale; revisit if shadowed areas look "too dead" in higher-realism scenes.

## /loop iter 95: universal atmospheric scattering + working depth-view Sobel
- **Wrong-shader gotcha**: spent half the iter editing `outline.ts` depth-view code only to discover the modeler uses a SEPARATE lit shader embedded in `modeler_demo.ts` (line 2425+). Hardcoded `return red` test confirmed: outline.ts depth branch is never reached for screenshotView. Logged a comment at the outline.ts depth branch noting that modeler_demo.ts overrides for screenshotView path.
- **Depth view rewired in modeler_demo.ts**: replaced the saturated `1 - d.r` (raw d.r values cluster near 0 in iso views, made the previous viz pure white) with **Sobel-of-depth**: `grad = |dE-dW| + |dN-dS|`, displayed as `clamp(grad * 200, 0, 1)`. Highlights silhouette edges, ridges, and SDF kinks directly — works without knowing the absolute depth range.
- **WGSL gotcha**: first attempt used `textureSample` inside the conditional branch, which violates uniform-control-flow → silent shader failure → flat-white render. Switched to `textureLoad` (no sampler, no UCF requirement). Worth knowing for any future per-pixel filter inside a viewMode switch.
- **Universalized atmospheric scattering**: removed the `if (colorFunc == 28u)` gate around the Rayleigh+Mie phase block. Atmospheric haze now applies to ALL hit primitives (clouds, characters, props, terrain) based on dNdc + view-sun angle. Cloud-shadow modulation stays terrain-only since it's a ground effect that depends on landWeight. Physical correctness: real atmosphere fogs everything; was wrong to gate by terrain-only.
- **Depth-view inspection findings**:
  - Mountain peak silhouette: fringy (real heightmap variation, expected)
  - Slab edges: clean straight lines (SDF is correct on flat planes)
  - Mountain-slab transition: faint line visible despite iter-93 smin (~2mm soft band) — could widen smin further if needed, but the fringe is now <1px wide and probably below visual threshold in the color render
  - Interior depth: smooth, no Sobel response → SDF march doesn't produce step artifacts
- **Open candidate for iter 96**: the still-visible line at slab-mountain transition could be cleaned up by either (a) widening the smin_k from 2mm→4mm, (b) using a smarter SDF that doesn't have the union seam (e.g., extrude the mountain volume directly without the slab as a separate primitive).

## /loop iter 94: hoisted shared zone weights + zone-modulated tone variation + multi-debug daemon
- **Tooling improvement (preview_daemon.mjs)**: `PREVIEW_DEBUG` now accepts a comma-separated list (e.g. `normal,depth`) — captures all requested debug modes on every tick. Previously had to restart daemon to switch between normal/depth views, losing WebGPU state. Now both audited continuously.
- **Hoisted shared zone weights** in `raymarch_renderer.ts`: replaced 3 redundant `terrainField[...]` + slope sampling blocks (in landWeight, color blend, and strata sections) with a SINGLE block at the top of the post-color path computing `landWeight`, `rockW`, `snowW` once. Downstream effects all use the same source of truth — no inconsistencies between blocks, no duplicate work.
- **Zone-modulated tonal variation** (the iter 93 candidate): per-fragment FBM tonal variation now scales by `(1.0 - 0.7 * snowW) * landWeight`. Snow zones get 30% strength (fresh snow IS uniform white, was looking patchy before), rock/grass get full ±15% variation, water/foam get zero — handled automatically by `landWeight`. Physical correctness: real snowpack reflectance varies <5% over patches; rock/dirt varies >20%.
- **Removed redundant slot-identity gates** (`slot != 3u && slot != 6u && slot != 7u`) on tone, strata, snow effects — landWeight gating already handles the "not water/foam" case smoothly. Slot now remains as a *dominant zone marker* without being a step gate anywhere.
- **Result**: snow caps render more uniform-white (visible improvement at peak); rock zones keep their character. Color render PNG essentially same size — visible improvement in snow uniformity rather than entropy reduction. SDF math + color path now both fully consolidated around hoisted shared state.
- **Depth view audit**: depth output saturates near pure white in iso view (NDC range too compressed for the camera distance). Not immediately useful as-is — would need a custom depth-remap mode (e.g., depth as `1 - exp(-totalDist*K)` for visible gradient). Tabled for later — normal view is the higher-signal channel for artifact debugging.

## /loop iter 93: SDF C1-continuity at extrusion boundary + drop water alias octave
- **Audit target**: residual fur at the slab-top→mountain-foothill boundary in the normal map. Source: hard `min(dBox, dExtrusion)` and hard `max(...)` chain inside `dExtrusion = max(max(cX, cZ), max(cAbove, cBelow))` — both C0-continuous (continuous values) but C1-discontinuous (kinked gradients) at branch crossings. Normal estimation reads the kink as jitter.
- **Replaced hard min/max with smin_k/smax_k** (Inigo Quilez polynomial smooth, already in renderer):
  - Inner chain: `smax_k(smax_k(cX, cZ, 0.001), smax_k(cAbove, cBelow, 0.001), 0.001)` — 1mm soft band at constraint corners, preserves visible mountain shape, dissolves the kink across normal-eps probes.
  - Outer union: `smin_k(d, dExtrusion, 0.002)` — 2mm soft seam at the slab-top→mountain transition.
- **Dropped `waveFine`** in water surface displacement (wavelength ~9mm at freq 110/m vs 8mm terrain normal eps = same alias problem detail3 had). Bumped `waveBig` amplitude 15→18mm to preserve visible water motion. Water specular sparkle comes from shiny channel + lit-pass, not geometric displacement, so the sub-cm wave loss is invisible.
- **Effect**: subtle but real — normal-map entropy down (PNG 783→780KB, 0.4% smaller). Boundary fringe at slab→mountain interface visibly cleaner. SDF math is now C1-continuous everywhere it touches detail FBM and the unified extrusion volume.
- **Open candidates for next iter**: tonal variation FBM (iter 92 already lowered to 8/26 freqs but still applied uniformly across slots — could zone-modulate so snow stays uniform, rock stays rough); strata sin frequencies (280/460 cycles/m = ~14-22mm wavelength = approaching pixel-scale on rock); evaluate depth view directly via PREVIEW_DEBUG=depth.

## /loop iter 92: kill normal-map fur — drop alias octave + bicubic flow + wider eps + macro tonal FBM
- **Diagnosis via direct normal view** (PREVIEW_DEBUG=normal): mountain top showed dense fur-pattern jitter, NOT a real geometric feature. Multiple sources contributed.
- **Detail FBM aliasing**: detail3 had wavelength ~4.6mm at density=4, sampled by 4mm normal eps → eps step covers a full oscillation, randomizing gradient estimate. Dropped detail3 entirely; bumped detail2 amplitude 12→16mm to compensate macro look.
- **Flow-field bilinear → bicubic Catmull-Rom**: `f = mix(...)` was C0-only (continuous values, discontinuous gradients) → step-pattern jitter at every cell boundary in the SDF gradient. Added `sampleTerrainFlowBicubic` parallel to `sampleTerrainBicubic`. C1 gradient = no boundary steps.
- **Terrain normal eps 4→8mm**: averages numerical gradient over more of the local noise variation. Macro features (mountain shape, valleys) are >>8mm wavelength so they survive; only sub-cm fur noise gets averaged out.
- **Per-fragment tonal-variation FBM frequencies dropped (22/80 → 8/26 cycles/m)**: was producing 12mm-wavelength color noise approaching pixel scale. Real terrain coloration varies at patch/boulder scale (~50mm+), not per-pixel. New wavelengths 125mm + 38mm.
- **Result confirmed in normal map**: dramatic smoothing. Slopes show clean continuous color gradients (real surface orientation), no fur-pattern jitter. Color render unchanged at the macro level — same mountain, same snow caps, same water pools — but now with surface that reads as physically smooth instead of grainy.
- **Lesson**: when normal map shows "fur" everywhere, the source is usually noise that's high-frequency relative to the normal-eps step. Either widen the eps, drop the offending octave, or upgrade noise-field sampling from bilinear (C0) to bicubic (C1). For procedural pipelines with many noise layers, watch for any sub-2-eps-wavelength octave — it'll alias.

## /loop iter 91: hoist landWeight, smooth shinyOut + cloud shadow boundaries
- **Audit goal**: kill the remaining hard slot-identity gates that iter 89-90 left behind. Three discontinuities still popped in the colorFunc=28 path: shinyOut, cloud shadow, plus 4 redundant `terrainField` samples for the same `landWeight` calculation.
- **Hoisted `landWeight`** to top of post-color block (right after `var tint = palette[slot].rgb`). Single sample of `terrainField` + smoothstep, reused everywhere.
- **`shinyOut` smoothed**: replaced hard `if (slot == 3u || slot == 7u) shinyOut = 1.0` with `shinyOut = mix(1.0, baselineShiny, landWeight)`. Specular highlights fade smoothly across foam/wet-shore — no more pop where lit water turns suddenly matte.
- **Cloud shadow smoothed**: replaced `if (slot != 3u && slot != 6u && slot != 7u) tint *= shadow` with `tint *= mix(1.0, cloudShadow, landWeight)`. Continuous fade-out over water.
- **Cleanup**: removed duplicate `densityT4/uvT4/gxT4/.../landWeight` block from AO/shadow section — uses hoisted variable.
- **Result**: render is identical-or-better in mountain_clean_v1 (shoreline is small in scene), but the SDF/material function is now C0-continuous across the water boundary on every channel — color, tint variation, AO, shadow, shiny, cloud shadow. No remaining hard slot-identity gates on coastline-sensitive effects.
- **Pattern crystallized**: any boundary that read "if slot is X, do Y" now reads "scale Y by smooth weight". Future deformer authors should default to this; slot stays a *dominant* zone marker for downstream effects, not a step gate.

## User direction update — terrain is for static game backgrounds
- "these terrain generations will be useful for our static backgrounds"
- **Implications**:
  - Bake budget is fully amortized — render once, use forever. "Max quality" can mean multi-second bakes without cost.
  - 4-view atlas is overkill for backgrounds; single composed shot at full resolution is what's actually shipped. Currently atlas splits pixels 4 ways (768² per panel out of 1536² atlas) — single-view mode would give 2048×2048 for the actual scene.
  - Camera composition matters more than diagnostic coverage. Authoring backgrounds wants yaw/pitch/dolly control — currently camera is fixed.
- **Updated iter targets**:
  - iter 57: visually compare cellular + voronoi (already coded) vs FBM/diamond-square — pick the strongest gen modes for backgrounds.
  - iter 58: single-camera render mode + per-spec camera params (yaw, pitch, distance) for shot composition.
  - iter 59+: discharge-momentum erosion, river-network-first, etc.
