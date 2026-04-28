/**
 * CSG Modeler — single-window authoring tool for accessory / prop SDF models.
 *
 * Plugs the engine's existing raymarch_renderer pipeline (same shader path
 * skeleton_demo uses) and exposes a CSG-style edit graph: a flat list of
 * primitives with per-prim op flags (blendGroup + blendRadius + chamfer for
 * smooth/chamfer union, mirrorYZ for free symmetry). Output is plain JSON
 * that round-trips into the engine as `RaymarchPrimitive[]` plus a palette.
 *
 * Surface for VL / Tsunami: every authoring action is also reachable via
 * `window.modeler.*` so an external agent can drive the same UI state. See
 * the bottom of this file for the tool-API table.
 *
 * Architecture (mirrors PIPELINE.md's Layer-1/2 split):
 *   ModelerSpec (this file)        ←→  Edit graph (UBS .ubs)
 *   raymarch_renderer's prims[]    ←→  Surface-Nets mesh (their derived layer)
 *
 * We keep the spec authored, regenerate the prim-list on every change, then
 * push to the GPU. No mesh stage — raymarch directly = always fresh, no
 * dirty-flag bookkeeping.
 */

import { initGPU } from '../src/renderer/gpu'
import { Camera } from '../src/renderer/camera'
import { FrameLoop } from '../src/renderer/frame'
import { mat4 } from '../src/math/vec'
import {
  createRaymarchRenderer,
  expandMirrors,
  type RaymarchPrimitive,
  type VATData,
} from '../src/character3d/raymarch_renderer'
// (outline pass intentionally NOT used — that's the engine's pixel-art
// cel + dark-outline post; we want a clean modeling-tool look here.)

// --- Spec types ----------------------------------------------------------

type PrimType =
  | 'sphere'
  | 'box'
  | 'roundedBox'
  | 'ellipsoid'
  | 'ellipsoidExact'
  | 'cylinder'
  | 'capsule'
  | 'torus'
  | 'cone'
  | 'bentCapsule'
  | 'sup'
  | 'trapezoidalBox'
  | 'band'

type Vec3 = [number, number, number]
type Vec4 = [number, number, number, number]

interface ModelerPrim {
  id: string
  type: PrimType
  pos: Vec3
  /** Type-specific params (4 floats max). See TYPE_META for layout. */
  params: Vec4
  /** Euler XYZ degrees — runtime converts to quat for the renderer. */
  rotationDeg: Vec3
  blendGroup: number
  blendRadius: number
  chamfer: boolean
  mirrorYZ: boolean
  /** Bend-deflection vector for type 14 (bentCapsule). The engine's slot-4
   *  uniform is overloaded for type 14 to carry tipDelta in primitive-local
   *  space (xyz, w ignored). Tip displaces by tipDelta * (t/halfH)² along
   *  the capsule, so the root stays straight and the curve concentrates
   *  near the tip. Ignored for non-bentCapsule prims. */
  tipDelta?: Vec3
  /** Spec-level scatter / replicate. Each entry duplicates the current set
   *  of primitives N times. Modes:
   *   - `linear` (default): translate by `spacing` along `axis`, centered.
   *   - `rotational`: rotate position around `axis` by 2π/count per copy
   *     (the prim's own orientation is unchanged — only its OFFSET rotates).
   *  Multiple entries compose multiplicatively. Expanded CPU-side. */
  repeats?: Array<
    | { kind?: 'linear'; axis: 'x' | 'y' | 'z'; count: number; spacing: number }
    | { kind: 'rotational'; axis: 'x' | 'y' | 'z'; count: number }
    | { kind: 'brickGrid'; rowAxis: 'x' | 'y' | 'z'; colAxis: 'x' | 'y' | 'z';
        rows: number; cols: number; rowSpacing: number; colSpacing: number;
        /** Per-row offset along colAxis. Default = colSpacing * 0.5 (running-bond half-brick stagger). */
        stagger?: number }
    | { kind: 'linkChain'; axis: 'x' | 'y' | 'z'; count: number; spacing: number }
    | { kind: 'chainLinkGrid'; rowAxis: 'x' | 'y' | 'z'; colAxis: 'x' | 'y' | 'z';
        rotAxis: 'x' | 'y' | 'z'; rows: number; cols: number;
        rowSpacing: number; colSpacing: number }
    | { kind: 'spline'; controlPoints: [number, number, number][]; count: number;
        /** Scale at last copy; first copy is always 1.0. Linear interp between. Default 1.0 (no taper). */
        taper?: number;
        /** Which prim-local axis aligns with the spline tangent. Default 'x'. */
        alignAxis?: 'x' | 'y' | 'z' }
  >
  /** FBM noise amplitude (m) — perturbs the SHADING normal only, not the
   *  silhouette. 0 = smooth. ~0.002–0.005 reads as "weathered / wood grain /
   *  worn metal." Higher values get noisier; >0.01 reads as "rough rock."
   *  Engine field: RaymarchPrimitive.detailAmplitude. */
  detailAmplitude?: number
  /** Geometric crack displacement depth (m). When > 0, noise-band contour
   *  lines displace the SDF surface outward, creating visible silhouette
   *  gaps. ~0.001 = hairline craquelure, ~0.01 = visible cracks, ~0.025+ =
   *  dramatic stone-fracture. */
  crackDepth?: number
  /** Crack density (cells per meter for the underlying noise). Lower =
   *  fewer/larger cracks; higher = more/finer. */
  crackDensity?: number
  /** Pit/crater depth (m). When > 0, Worley-distance to random points
   *  displaces the SDF outward at those points → round inward craters
   *  (meteorite pock-marks, rust pitting, splatter damage). Mutually
   *  exclusive with crackDepth + bumpDepth (one deformer at a time). */
  pitDepth?: number
  /** Pit density (cells per meter). Each cell has one pit. */
  pitDensity?: number
  /** Smooth outward bump amplitude (m). Continuous FBM displacement →
   *  organic lumpy surface (leather, hide, fruit skin, asteroid). */
  bumpDepth?: number
  /** Bump density (cycles per meter for the underlying FBM). */
  bumpDensity?: number
  /** Cellular ridge height (m). When > 0, raised ridges along Worley cell
   *  boundaries → dragon scales / lizard hide / alligator skin / mud-tile
   *  pattern. Each cell becomes a raised tile with valleys between. */
  scaleDepth?: number
  /** Scale density (cells per meter). Lower = larger scales/tiles. */
  scaleDensity?: number
  /** Wood-grain stripe depth (m). Sunken parallel lines along Y axis,
   *  warped by FBM for natural curve. */
  grainDepth?: number
  /** Grain density (stripes per meter). */
  grainDensity?: number
  /** Ridged-multifractal raised spine height (m). 4-octave folded noise →
   *  sharp peaks, smooth valleys. Mountain ridges, sword-blade fullers,
   *  creature spines, knotted bark. Different from `bumpDepth` (smooth
   *  bumps) and `scaleDepth` (cellular tiles). */
  ridgeDepth?: number
  /** Ridge density (cycles per meter for the underlying multifractal). */
  ridgeDensity?: number
  /** Erosion-streak depth (m). Vertical drips/runs aligned with world +Y.
   *  Use for rust runoff, water-staining on stone, weathered metal panels. */
  streakDepth?: number
  /** Streak density (column picks per meter — controls how often streaks
   *  appear horizontally). Lower = sparse, higher = dense. */
  streakDensity?: number
  /** Hex-tile mortar depth (m). Periodic hexagonal lattice of raised plates
   *  with sunken grooves between. Pointy-top orientation. Domain-warped so
   *  the grid isn't ruler-perfect. Use for sci-fi armor, honeycomb, alien
   *  skin, tessellated shields. */
  hexDepth?: number
  /** Hex density (cells per meter — diameter of each hex). Lower = bigger
   *  plates; higher = finer mesh. */
  hexDensity?: number
  /** Brick-mortar depth (m). Offset rectangular running-bond tiling with
   *  sunken mortar joints. Brick aspect 2:1, alternate rows shifted by half
   *  a brick. Use for stone walls, chimneys, dungeon walls, building facades. */
  brickDepth?: number
  /** Brick density (bricks-per-meter on the short axis). Lower = bigger
   *  blocks; higher = finer brickwork. */
  brickDensity?: number
  /** Voronoi-crack depth (m). Geometric cell-network cracks: thin sunken
   *  lines along true Voronoi cell boundaries (F1-F2 bisector). Distinct
   *  from `crackDepth` (FBM-band) — this gives clean cell-network look
   *  for cracked dried mud, dragon-egg shell, broken tile, parched earth. */
  voronoiCrackDepth?: number
  /** Voronoi-crack density (cells per meter). Lower = bigger cells. */
  voronoiCrackDensity?: number
  /** Scratch depth (m). Sparse directional strokes along local +X axis
   *  (rotate the prim to redirect). Brushed-metal, weapon-wear look. */
  scratchDepth?: number
  /** Scratch density (lines per meter). ~30% of lines are randomly populated. */
  scratchDensity?: number
  /** Dimple depth (m). Regular grid of sunken sphere indents. Golf ball,
   *  hammered metal, perforated panel, leather pebbling. Lightly domain-
   *  warped so the grid isn't ruler-perfect. */
  dimpleDepth?: number
  /** Dimple density (cells per meter). Lower = bigger / fewer dimples. */
  dimpleDensity?: number
  /** Stud height (m). Inverse of dimples — raised grid hemispheres.
   *  Rivets, tactile D-pad dots, studded leather, decorative dot patterns. */
  studDepth?: number
  /** Stud density (cells per meter). */
  studDensity?: number
  /** Chevron ridge height (m). V-shaped raised ridges along local +Y axis,
   *  domain-warped. Arrow pavement, textured rubber grip, military stencil
   *  chevrons, herringbone leather. */
  chevronDepth?: number
  /** Chevron density (chevrons per meter). */
  chevronDensity?: number
  /** Whorl ring depth (m). Concentric rings around local origin (XY plane),
   *  domain-warped via FBM so rings aren't perfect circles. Use cases:
   *  fingerprints, tree-stump growth rings, sliced fruit cross-sections,
   *  contour topo lines, target patterns, wood end-grain. */
  whorlDepth?: number
  /** Whorl ring density (rings per meter). Higher = finer growth rings;
   *  lower = wider zen-garden ripples. */
  whorlDensity?: number
  /** Fishscale groove depth (m). Offset rows of arc-bounded scales — the
   *  shadow line between overlapping scales becomes a sunken groove.
   *  Use cases: fish scales, roof tiles, overlapping armor plates,
   *  pinecone bracts. Different from `scaleDepth` (Voronoi cells) — fishscale
   *  is uniform / regular / unmistakably tile-like. */
  fishscaleDepth?: number
  /** Fishscale density (rows per meter). */
  fishscaleDensity?: number
  /** Reaction-diffusion (Gray-Scott) deformer depth (m). When > 0, prim
   *  surface is displaced by a CPU-baked Gray-Scott V-channel field. High V
   *  = raised features (coral spots, brain ridges, zebra stripes). Pattern
   *  is emergent from F (feed) and k (kill) tuning — analytical deformers
   *  can't produce it. Bake runs once at spec ingest (~50ms for default
   *  iterations on 128²); never per-frame. ONE shared field per scene (the
   *  first RD prim's F/k/iters/seed wins; subsequent RD prims sample the
   *  same field at their own density/depth). */
  rdDepth?: number
  /** RD density (tiles-per-meter). Lower = larger pattern features.
   *  Default 12 ≈ one full tile per ~80mm — matches typical facade/panel
   *  authoring scale. Higher densities tile the pattern more, useful for
   *  small accessory props. */
  rdDensity?: number
  /** RD feed rate F. Tunable parameter of Gray-Scott. Combined with k,
   *  picks the pattern: coral=0.055, brain=0.040, zebra=0.020,
   *  leopard=0.025, spots=0.014, chaos=0.026. Default 0.055 (coral).
   *  Explicit value overrides any rdPreset selection. */
  rdFeed?: number
  /** RD kill rate k. See rdFeed for presets. Default 0.062 (coral).
   *  Explicit value overrides any rdPreset selection. */
  rdKill?: number
  /** Named RD pattern preset. Convenience over manual F/k tuning — picks
   *  a (F, k) pair from a curated lookup. Use this for legibility ("coral"
   *  beats "0.055/0.062"); use rdFeed/rdKill explicitly only when you want
   *  to deviate from a named preset. Explicit rdFeed/rdKill override the
   *  preset's mapping at any time. */
  rdPreset?: 'coral' | 'brain' | 'zebra' | 'leopard' | 'spots' | 'chaos' | 'fingerprint' | 'flower'
  /** Terrain heightmap deformer depth (m). When > 0, surface is displaced
   *  by a CPU-baked heightmap field (FBM by default; ridged/eroded options
   *  via terrainGen). High value = elevated peak. Bilinear-sampled in WGSL
   *  for smooth slope shading. Field is shared scene-wide (one bake) — see
   *  rdDepth for the same one-field-per-scene constraint. */
  terrainDepth?: number
  /** Terrain density (tiles-per-meter). Default 12 ≈ one full 256-cell
   *  tile per ~80mm. Lower = larger terrain features per surface area. */
  terrainDensity?: number
  /** Terrain generator.
   *    'fbm'             = standard fractal Brownian motion, soft rolling hills (default)
   *    'ridged'          = ridged multifractal, sharp peaks
   *    'eroded-fbm'      = FBM + thermal erosion
   *    'eroded-ridged'   = ridged + thermal erosion
   *    'diamond-square'  = classic recursive midpoint displacement, continental landmass
   *    'eroded-diamond'  = diamond-square + thermal erosion
   *    'voronoi'         = peaks at seed points, plate-like topology
   *  Pick eroded-* for naturalistic biomes, raw for stylized. */
  terrainGen?: 'fbm' | 'ridged' | 'eroded-fbm' | 'eroded-ridged' | 'diamond-square' | 'eroded-diamond' | 'voronoi'
  /** FBM octaves. Default 5. More octaves = finer detail at the cost of
   *  bake time (roughly linear). */
  terrainOctaves?: number
  /** FBM persistence (per-octave amplitude decay). Default 0.5 — each
   *  octave half the amplitude of the previous. Lower = smoother. */
  terrainPersistence?: number
  /** FBM lacunarity (per-octave frequency multiplier). Default 2.0 —
   *  each octave doubles the frequency. */
  terrainLacunarity?: number
  /** Initial-condition seed. Same seed = same heightmap. Default 1. */
  terrainSeed?: number
  /** Voronoi-only: number of seed points (peaks). 4-8 = wide open island
   *  pattern; 16-30 = scattered hills; 40+ = densely packed bumps.
   *  Default 18. */
  voronoiSeedCount?: number
  /** Thermal erosion iterations (eroded-* generators only). Each iteration
   *  redistributes material from steep slopes toward valleys. ~50-200 is
   *  a usable range. Default 50. */
  terrainErosionIters?: number
  /** Scene-wide water level in heightmap [0, 1] units. Cells of the
   *  terrain heightmap below this altitude get a flat water surface
   *  (basins fill — this is the natural pooling-at-the-bottom-of-hills
   *  visualization) and palette slot 3 (water blue, by convention).
   *  0 = no water (default); 1 = entire terrain submerged. */
  terrainWaterLevel?: number
  /** River-channel carving depth (m). When > 0, the flow-accumulation
   *  field (computed alongside the heightmap via the D8 algorithm) carves
   *  channels into the terrain surface. Cells where many upstream cells
   *  drain through them get cut deeper, so natural river networks emerge
   *  from the heightmap geometry. ~0.5-1.5× of terrainDepth produces
   *  visible-but-not-overwhelming river beds. Default 0 (no carving). */
  terrainFlowDepth?: number
  /** Wind-erosion iteration count. When > 0, runs N passes of upwind-
   *  biased smoothing AFTER any thermal erosion. Each pass shifts each
   *  cell's height a fraction of the way toward its upwind neighbour
   *  height — visually produces streaked, dune-like terrain. Default 0
   *  (no wind). 50-200 is a usable range. */
  terrainWindIters?: number
  /** Wind direction in XY plane (degrees, 0 = +X, 90 = +Y). Default 45°. */
  terrainWindAngle?: number
  /** Per-iteration wind blend strength [0, 1]. 0 = no shift, 1 = full
   *  replacement with upwind sample (terrain becomes constant after a
   *  few iters). Default 0.15. Higher values combined with high iters
   *  produce extreme smearing — useful for sand-blasted desert looks. */
  terrainWindStrength?: number
  /** Cloud deformer depth (m). Applied to a base sphere/ellipsoid prim;
   *  iterated-domain-warp billow noise carves out the characteristic
   *  cumulus "fluff" silhouette. ~30-60% of prim radius is a usable
   *  range. Authors get fluffier clouds by raising depth + density. */
  cloudDepth?: number
  /** Cloud noise density (cycles per meter). Lower = larger billows,
   *  higher = finer puffs. Default 12. */
  cloudDensity?: number
  /** Hydraulic erosion droplet count. Each droplet spawns at a random
   *  position, picks up sediment as it flows downhill, deposits when
   *  it slows or reverses. ~5000-15000 produces visible canyons on
   *  256². Default 0 (no hydraulic erosion). Runs AFTER thermal+wind. */
  terrainHydraulicDroplets?: number
  /** Hydraulic erosion droplet life (max steps). Each step is one cell-
   *  width of travel (bilinear). Default 30 steps. Higher values let
   *  droplets travel further before evaporating, carving longer rivers
   *  but at proportionally more compute cost. */
  terrainHydraulicSteps?: number
  /** Vegetation scatter count. When > 0, that many small sphere prims
   *  are placed on the terrain at random (x, y) within the slab,
   *  filtered to grass zone (above water, below snow line, slope < 0.08).
   *  Sphere palette slot 5 (forest green by default). Reads as scattered
   *  trees / grass tufts depending on size. Default 0. */
  terrainScatterCount?: number
  /** Vegetation scatter prim radius (m). Default 0.002 (2mm — reads as
   *  grass tuft on a 100mm slab). Bump up to 0.005-0.010 for tree-sized
   *  blobs. */
  terrainScatterRadius?: number
  /** RD iteration count. ~1500-3000 is the settled-pattern range; lower
   *  values give half-formed transient patterns (sometimes more interesting
   *  than steady-state). Default 2000. */
  rdIterations?: number
  /** RD initial-condition seed. Same seed = same starting V perturbation
   *  pattern = same final field (deterministic). Default 1. */
  rdSeed?: number
  /** Weave depth (m). Two-axis over-under fabric pattern — horizontal and
   *  vertical strands raise alternately based on cell parity. Use cases:
   *  woven fabric, basket weave, cane, mesh, chainmail, woven grass mat. */
  weaveDepth?: number
  /** Weave density (strands per meter on each axis). */
  weaveDensity?: number
  /** Optional secondary "wear" deformer that runs AFTER the primary
   *  deformer (cracks/hex/scales/...). Lets one prim composite a base
   *  structural pattern with a weathering overlay (e.g. hex armor + bumps,
   *  or brick + streaks). Limited to FBM-based wear modes; structural
   *  modes only run as primaries. */
  wearDeformer?: {
    type: 'bumps' | 'grain' | 'streaks' | 'scratches'
    depth: number
    density?: number
  }
  /** Optional override for the deformer's color-side accent palette slot
   *  (paletteSlotB). Defaults: sunken-feature deformers (hex/brick/dimples
   *  /voronoiCrack/scratches) → slot 1 (darker base color, used for mortar
   *  / dimple interior / scratch line). Raised-feature deformers (studs/
   *  chevrons) → slot 2 (brighter base color, used for stud tops / ridge
   *  peaks). Set to override per-prim. */
  accentSlot?: number
  /** Path-based carves. List of waypoint segments; each expands into a
   *  thin box that either subtracts from the parent (carved trench, default)
   *  or adds to it (raised tube). Author manually OR via crackPathGen (auto). */
  pathCarves?: Array<{
    from: Vec3
    to: Vec3
    thickness?: number
    depth?: number
    /** When true, segment ADDS to parent (raised tube/pipe/conduit). When
     *  false/omitted, segment SUBTRACTS (carved trench, original behavior). */
    raise?: boolean
    /** Geometry kind. 'segment' (default) = roundedBox along from→to —
     *  the standard tube/trench shape. 'joint' = sphere at `from` with
     *  radius=thickness, ignores `to` — used at T-junction connection
     *  points so branches read as engineered fittings rather than two
     *  paths crossing. */
    kind?: 'segment' | 'joint'
  }>
  /** Auto-generate a branching crack path. Modeler routes a path from
   *  start to end. `mode='walk'` uses a seeded random walk with jitter
   *  (cheap, fork-friendly). `mode='astar'` runs grid-based A* over a
   *  noise cost field so paths follow "weak" material naturally. */
  crackPathGen?: {
    start: Vec3
    end: Vec3
    /** Path-generation algorithm.
     *  'walk'      = seeded random-walk spine + perpendicular jitter (cheap, branchy)
     *  'astar'     = grid A* over noise cost field (follows weak material; smooth)
     *  'lightning' = midpoint-displacement recursion with cascading branches
     *                (sharp, jagged, asymmetric — lightning bolts, fault lines).
     *  'tree'      = recursive Y-fork from `start` along `direction` (default +Y).
     *                Each node spawns `branches` children at ±branchAngle, with
     *                length decay per level.
     *  'tendril'   = continuous-curvature drift along `direction`. Heading
     *                turns smoothly via FBM-driven rotation; no discrete
     *                branches, no jitter — one winding line. Vines, tentacles,
     *                hair strands, ribbon trails, river meanders without A*.
     *  Default: 'walk'. */
    mode?: 'walk' | 'astar' | 'lightning' | 'tree' | 'tendril'
    /** Tree initial growth direction in XY plane. Default [0,1,0] (up). Only
     *  used when mode='tree'; ignored by other modes. */
    direction?: Vec3
    /** Tree initial trunk length (m). Default 0.04. */
    length?: number
    /** Tree branch splay angle (degrees, half-angle from parent direction).
     *  Default 28°. Higher = wider tree. */
    branchAngle?: number
    /** Tree per-level length multiplier. Default 0.7 → each level 70% as
     *  long as its parent. */
    lengthDecay?: number
    /** Tree per-level thickness multiplier (also applied to depth). Default
     *  0.7. Branches taper as they recurse. */
    thicknessDecay?: number
    /** Tree branches per node. 2 = Y-fork (default), 3 = trident, 4 = candelabra. */
    branches?: number
    /** Tree recursion depth. Default 5. Higher = more leaves but quadratic
     *  segment count (4^depth at depth=5 = 1024 segments for 4 branches). */
    treeDepth?: number
    /** Tendril number of segments. Default 32. */
    tendrilSteps?: number
    /** Tendril per-step heading curvature scale (radians). Default 0.18.
     *  Higher = tighter curls; lower = lazier. */
    curlIntensity?: number
    /** Walk: # of spine segments. A*: ignored (path length is grid-derived). */
    segments?: number
    /** PRNG seed — same seed = same path. */
    seed?: number
    /** Chance per waypoint of spawning a branch (0-1). */
    branchiness?: number
    /** A*: grid resolution in cells per side of bounding box. Default 32. */
    gridRes?: number
    /** A*: weight on noise cost (higher = paths bend harder around weakness). */
    noiseWeight?: number
    /** A*: distance metric.
     *  'euclidean' (default) = 8-neighbor with diagonal cost √2; smooth post-pass.
     *  'manhattan' = 4-neighbor (orthogonal only). Heuristic |dx|+|dy|.
     *      Right-angle paths only — street-grid / wiring-trunk look. NO smooth.
     *  'chebyshev' = 8-neighbor, diagonal cost = orthogonal cost. Heuristic
     *      max(|dx|,|dy|). 45°-preferring paths — PCB traces, mechanical
     *      conduits, sci-fi pipework. NO smooth. */
    metric?: 'euclidean' | 'manhattan' | 'chebyshev'
    /** Half-width of trenches (m). */
    thickness?: number
    /** Penetration depth (m). */
    depth?: number
    /** Cross-section profile.
     *  'crack' (default) = single thin carve, square cross-section.
     *  'river' = dual-layer U-shape (wide shallow base + narrow deep center).
     *  'channel' = single wider carve with rounded floor (capsule-like).
     */
    profile?: 'crack' | 'river' | 'channel'
    /** Meander amplitude (m). After A* / walk pathing and smoothing, perturb
     *  each waypoint perpendicular to its local tangent by a sinusoid of
     *  this amplitude. ~0.005-0.015 = lazy river bend; 0 = straight path. */
    meander?: number
    /** Meander frequency (cycles along path). Higher = tighter wiggles. */
    meanderFreq?: number
    /** Linear taper. 0 = uniform (default). 1 = thickness/depth fade to zero
     *  along path. Lightning naturally tapers from cloud→strike; vines taper
     *  from stem→tip. Branches inherit a steeper taper. */
    taper?: number
    /** Polarity. false (default) = subtractive carved trenches (cracks,
     *  streets, channels). true = additive raised tubes (pipes, conduits,
     *  cables, wires, mechanical traces). Same path-gen, opposite blend. */
    raise?: boolean
    /** A*-only: spawn N perpendicular T-junction branches off the main
     *  spine. Each branch is a sub-A* from a random main-path waypoint
     *  to a grid-snapped perpendicular endpoint, with thickness/depth
     *  scaled down to 60% / 85% so it reads as a side-branch. Branches
     *  inherit metric, raise polarity, profile, and noiseWeight from the
     *  parent. Use cases: T-fittings on raised pipework, side-streets on
     *  manhattan grids, tributary cracks on euclidean weak-material paths.
     *  Default 0. Cap 8 to bound prim explosion. */
    astarBranches?: number
    /** A*-only: emit `kind:'joint'` sphere caps at the path's start and
     *  end waypoints. Default = same as `raise`: raised pipes get capped
     *  ends (so they read as terminated rather than clipped); carved
     *  trenches don't (extra pits at endpoints look like accidents).
     *  Override explicitly to force on/off. */
    endCaps?: boolean
    /** Lightning recursion depth (# of midpoint-displacement passes).
     *  Each pass doubles segment count. 5–7 is a good range; >8 → diminishing
     *  visual returns and quadratic cost. Default 6. */
    lightningDepth?: number
    /** Lightning jaggedness (perpendicular displacement scale relative to
     *  segment length, applied at depth-0). Decays by 0.5 each level. ~0.4
     *  for natural lightning, 0.7 for chaotic, 0.15 for subtle ripple. */
    jaggedness?: number
  }
}

interface ModelerSpec {
  version: 1
  name: string
  primitives: ModelerPrim[]
}

// --- Type registry -------------------------------------------------------

interface ParamDef {
  label: string
  min: number
  max: number
  step: number
  /** True = scaled with primitive size. Affects the "fit" auto-zoom. */
  isSize?: boolean
}

interface TypeMeta {
  /** Numeric ID matching the WGSL dispatcher in raymarch_renderer.ts. */
  id: number
  display: string
  /** Up to 4 entries; the rest are zero-padded. */
  params: ParamDef[]
  defaults: Vec4
}

const TYPE_META: Record<PrimType, TypeMeta> = {
  sphere: {
    id: 0, display: 'sphere',
    params: [{ label: 'radius', min: 0.001, max: 1.0, step: 0.001, isSize: true }],
    defaults: [0.05, 0, 0, 0],
  },
  box: {
    id: 1, display: 'box',
    params: [
      { label: 'half-x', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-y', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-z', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.05, 0.05, 0.05, 0],
  },
  roundedBox: {
    id: 2, display: 'roundedBox',
    params: [
      { label: 'half-x', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-y', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-z', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'corner', min: 0.001, max: 0.5, step: 0.001 },
    ],
    defaults: [0.05, 0.05, 0.05, 0.01],
  },
  ellipsoid: {
    id: 3, display: 'ellipsoid (cheap)',
    params: [
      { label: 'rx', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'ry', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'rz', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.05, 0.07, 0.05, 0],
  },
  ellipsoidExact: {
    id: 19, display: 'ellipsoid (exact)',
    params: [
      { label: 'rx', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'ry', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'rz', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.05, 0.07, 0.05, 0],
  },
  cylinder: {
    id: 4, display: 'cylinder',
    params: [
      { label: 'radius', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-h', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.04, 0.06, 0, 0],
  },
  capsule: {
    id: 5, display: 'capsule',
    params: [
      { label: 'radius', min: 0.001, max: 0.5, step: 0.001, isSize: true },
      { label: 'half-h', min: 0.0, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.03, 0.05, 0, 0],
  },
  torus: {
    id: 6, display: 'torus',
    params: [
      { label: 'major', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'minor', min: 0.001, max: 0.3, step: 0.001 },
    ],
    defaults: [0.06, 0.015, 0, 0],
  },
  cone: {
    id: 12, display: 'cone',
    params: [
      { label: 'sin a', min: 0.0, max: 1.0, step: 0.005 },
      { label: 'cos a', min: 0.0, max: 1.0, step: 0.005 },
      { label: 'height', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.5, 0.866, 0.08, 0],
  },
  bentCapsule: {
    id: 14, display: 'bent capsule',
    params: [
      { label: 'radius', min: 0.001, max: 0.3, step: 0.001, isSize: true },
      { label: 'half-h', min: 0.001, max: 1.0, step: 0.001, isSize: true },
    ],
    defaults: [0.03, 0.06, 0, 0],
  },
  sup: {
    id: 18, display: 'SUP (sphere<->box)',
    params: [
      { label: 'radius', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'blend', min: 0.0, max: 1.0, step: 0.005 },
      { label: 'shell', min: 0.0, max: 0.5, step: 0.001 },
      { label: 'y-clip', min: -1.0, max: 1.0, step: 0.005 },
    ],
    defaults: [0.06, 0.5, 0.0, 0.0],
  },
  trapezoidalBox: {
    id: 21, display: 'trapezoidal box',
    params: [
      { label: 'bot-x', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'bot-z', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'half-h', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'topRatio', min: 0.0, max: 2.0, step: 0.01 },
    ],
    defaults: [0.04, 0.04, 0.04, 0.5],
  },
  band: {
    id: 22, display: 'band (rect torus)',
    params: [
      { label: 'major', min: 0.001, max: 1.0, step: 0.001, isSize: true },
      { label: 'rad-w', min: 0.001, max: 0.3, step: 0.001 },
      { label: 'axial-h', min: 0.001, max: 0.3, step: 0.001 },
    ],
    defaults: [0.06, 0.005, 0.012, 0],
  },
}

const TYPE_ORDER: PrimType[] = [
  'sup', 'sphere', 'box', 'roundedBox', 'trapezoidalBox',
  'ellipsoid', 'ellipsoidExact',
  'cylinder', 'capsule', 'torus', 'band', 'cone', 'bentCapsule',
]

// --- Defaults ------------------------------------------------------------

/** Single neutral material colour used for ALL primitives. The modeler is a
 *  geometry tool — colour / palette is intentionally stripped so the LLM
 *  reasons purely about shape + ops, and the spec output has no display
 *  metadata. */
const MATERIAL_RGB: Vec3 = [0.78, 0.79, 0.82]

const STORAGE_KEY = 'tsunami.modeler.spec.v3'
const POLL_MS = 250
const DEFAULT_POLL_PATH = '/sdf_modeler/inbox.ark.json'

function emptySpec(): ModelerSpec {
  return { version: 1, name: 'untitled', primitives: [] }
}

/** Spec used on very first run so the canvas isn't blank.
 *  A single SUP at origin, mid-blend (visible sphere↔box compromise). */
function demoSpec(): ModelerSpec {
  const s = emptySpec()
  s.name = 'default'
  s.primitives.push({
    id: 'sup_demo',
    type: 'sup',
    pos: [0, 0, 0],
    params: [0.08, 0.4, 0, 0],
    rotationDeg: [0, 0, 0],
    blendGroup: 1,
    blendRadius: 0.01,
    chamfer: false,
    mirrorYZ: false,
  })
  return s
}

let nextIdCounter = 0
function newId(type: PrimType): string {
  return `${type}_${(++nextIdCounter).toString(36)}`
}

function newPrim(type: PrimType, pos: Vec3 = [0, 0, 0]): ModelerPrim {
  const meta = TYPE_META[type]
  return {
    id: newId(type),
    type,
    pos: [...pos] as Vec3,
    params: [...meta.defaults] as Vec4,
    rotationDeg: [0, 0, 0],
    blendGroup: 1,
    blendRadius: 0.01,
    chamfer: false,
    mirrorYZ: false,
  }
}

function clone<T>(v: T): T { return JSON.parse(JSON.stringify(v)) }

// --- Math helpers --------------------------------------------------------

/** Euler XYZ (degrees) -> quaternion (x, y, z, w). */
function eulerToQuat(deg: Vec3): Vec4 {
  const rx = (deg[0] * Math.PI) / 180
  const ry = (deg[1] * Math.PI) / 180
  const rz = (deg[2] * Math.PI) / 180
  const cx = Math.cos(rx / 2), sx = Math.sin(rx / 2)
  const cy = Math.cos(ry / 2), sy = Math.sin(ry / 2)
  const cz = Math.cos(rz / 2), sz = Math.sin(rz / 2)
  const x = sx * cy * cz + cx * sy * sz
  const y = cx * sy * cz - sx * cy * sz
  const z = cx * cy * sz + sx * sy * cz
  const w = cx * cy * cz - sx * sy * sz
  return [x, y, z, w]
}

function isIdentityRotation(deg: Vec3): boolean {
  return deg[0] === 0 && deg[1] === 0 && deg[2] === 0
}

/** Apply linear repeats to a single primitive. Each repeat entry takes the
 *  current set of N primitives and multiplies it by `count`, offsetting each
 *  copy by spacing along the axis. Repeats are centered on the original.
 *  Multiple entries compose: 5x along X then 3 along Z = 15 final copies. */
/** Catmull-Rom spline position at parameter t in [0,1] across the inner
 *  segments (control points 1..n-2 are interpolated; first and last act
 *  as tangent guides). Returns position only. */
function catmullRomSample(
  cps: [number, number, number][],
  tGlobal: number,
): { pos: [number, number, number]; tan: [number, number, number] } {
  const n = cps.length
  const segs = n - 3
  const tSeg = tGlobal * segs
  const i = Math.min(Math.floor(tSeg), segs - 1)
  const t = tSeg - i
  const p0 = cps[i], p1 = cps[i + 1], p2 = cps[i + 2], p3 = cps[i + 3]
  const t2 = t * t, t3 = t2 * t
  const pos: [number, number, number] = [0, 0, 0]
  const tan: [number, number, number] = [0, 0, 0]
  for (let k = 0; k < 3; k++) {
    pos[k] = 0.5 * (
      (2 * p1[k]) +
      (-p0[k] + p2[k]) * t +
      (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
      (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3
    )
    tan[k] = 0.5 * (
      (-p0[k] + p2[k]) +
      (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * 2 * t +
      (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * 3 * t2
    )
  }
  return { pos, tan }
}

/** Quaternion that rotates `from` (unit) to `to` (unit). */
function quatFromTo(from: [number, number, number], to: [number, number, number]): [number, number, number, number] {
  const dot = from[0]*to[0] + from[1]*to[1] + from[2]*to[2]
  if (dot > 0.999999) return [0, 0, 0, 1]
  if (dot < -0.999999) {
    // 180° — pick a perpendicular axis
    const axis: [number, number, number] = Math.abs(from[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0]
    const cross: [number, number, number] = [
      from[1]*axis[2] - from[2]*axis[1],
      from[2]*axis[0] - from[0]*axis[2],
      from[0]*axis[1] - from[1]*axis[0],
    ]
    const m = Math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)
    return [cross[0]/m, cross[1]/m, cross[2]/m, 0]
  }
  const cross: [number, number, number] = [
    from[1]*to[2] - from[2]*to[1],
    from[2]*to[0] - from[0]*to[2],
    from[0]*to[1] - from[1]*to[0],
  ]
  const w = 1 + dot
  const n = Math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2 + w*w)
  return [cross[0]/n, cross[1]/n, cross[2]/n, w/n]
}

function applyRepeats(
  prim: RaymarchPrimitive,
  repeats: NonNullable<ModelerPrim['repeats']> | undefined,
): RaymarchPrimitive[] {
  if (!repeats || !repeats.length) return [prim]
  let current: RaymarchPrimitive[] = [prim]
  for (const r of repeats) {
    if (!r) continue
    const next: RaymarchPrimitive[] = []
    if ((r as { kind?: string }).kind === 'spline') {
      // Spline-based positioning. Place `count` copies along a Catmull-Rom
      // spline through controlPoints (need ≥4: first+last are tangent
      // guides). Each copy: position from spline, rotation aligns the
      // prim's chosen local axis with the spline tangent, params scaled
      // by linear taper from 1.0 (first) to taper (last).
      const sp = r as { controlPoints: [number, number, number][]; count: number; taper?: number; alignAxis?: 'x'|'y'|'z' }
      if (sp.controlPoints.length < 4 || sp.count < 1) { current = next; continue }
      const taperEnd = sp.taper ?? 1.0
      const alignAxis = sp.alignAxis ?? 'x'
      const localAxis: [number, number, number] = alignAxis === 'x' ? [1,0,0] : alignAxis === 'y' ? [0,1,0] : [0,0,1]
      for (const p of current) {
        for (let i = 0; i < sp.count; i++) {
          const tGlobal = sp.count === 1 ? 0.5 : i / (sp.count - 1)
          const { pos, tan } = catmullRomSample(sp.controlPoints, tGlobal)
          const tlen = Math.sqrt(tan[0]**2 + tan[1]**2 + tan[2]**2) || 1
          const tanU: [number, number, number] = [tan[0]/tlen, tan[1]/tlen, tan[2]/tlen]
          const scale = 1 + (taperEnd - 1) * tGlobal
          const newPrim: RaymarchPrimitive = {
            ...p,
            offsetInBone: [
              p.offsetInBone[0] + pos[0],
              p.offsetInBone[1] + pos[1],
              p.offsetInBone[2] + pos[2],
            ],
            params: [p.params[0] * scale, p.params[1] * scale, p.params[2] * scale, p.params[3]],
            rotation: quatFromTo(localAxis, tanU),
          }
          next.push(newPrim)
        }
      }
      current = next
      continue
    }
    if ((r as { kind?: string }).kind === 'chainLinkGrid') {
      // 2D grid of rings with alternating rotation around rotAxis on each
      // (row+col) parity → interlock pattern (real chain-link fence).
      const cl = r as { rowAxis: 'x'|'y'|'z'; colAxis: 'x'|'y'|'z'; rotAxis: 'x'|'y'|'z';
        rows: number; cols: number; rowSpacing: number; colSpacing: number }
      if (cl.rows < 1 || cl.cols < 1) continue
      const rowIdx = cl.rowAxis === 'x' ? 0 : cl.rowAxis === 'y' ? 1 : 2
      const colIdx = cl.colAxis === 'x' ? 0 : cl.colAxis === 'y' ? 1 : 2
      const rotIdx = cl.rotAxis === 'x' ? 0 : cl.rotAxis === 'y' ? 1 : 2
      const half = Math.PI / 4
      const sinH = Math.sin(half), cosH = Math.cos(half)
      const rotQuat: [number, number, number, number] = [0, 0, 0, cosH]
      rotQuat[rotIdx] = sinH
      for (const p of current) {
        for (let row = 0; row < cl.rows; row++) {
          const rowOffset = (row - (cl.rows - 1) / 2) * cl.rowSpacing
          for (let col = 0; col < cl.cols; col++) {
            const colOffset = (col - (cl.cols - 1) / 2) * cl.colSpacing
            const o: [number, number, number] = [p.offsetInBone[0], p.offsetInBone[1], p.offsetInBone[2]]
            o[rowIdx] += rowOffset
            o[colIdx] += colOffset
            const newPrim: RaymarchPrimitive = { ...p, offsetInBone: o }
            if ((row + col) % 2 === 1) newPrim.rotation = rotQuat
            next.push(newPrim)
          }
        }
      }
      current = next
      continue
    }
    if ((r as { kind?: string }).kind === 'brickGrid') {
      const br = r as { rowAxis: 'x'|'y'|'z'; colAxis: 'x'|'y'|'z';
        rows: number; cols: number; rowSpacing: number; colSpacing: number; stagger?: number }
      if (br.rows < 1 || br.cols < 1) continue
      const rowIdx = br.rowAxis === 'x' ? 0 : br.rowAxis === 'y' ? 1 : 2
      const colIdx = br.colAxis === 'x' ? 0 : br.colAxis === 'y' ? 1 : 2
      const stagger = br.stagger ?? br.colSpacing * 0.5
      for (const p of current) {
        for (let row = 0; row < br.rows; row++) {
          const rowOffset = (row - (br.rows - 1) / 2) * br.rowSpacing
          const rowStagger = (row % 2 === 1) ? stagger : 0
          for (let col = 0; col < br.cols; col++) {
            const colOffset = (col - (br.cols - 1) / 2) * br.colSpacing + rowStagger
            const o: [number, number, number] = [p.offsetInBone[0], p.offsetInBone[1], p.offsetInBone[2]]
            o[rowIdx] += rowOffset
            o[colIdx] += colOffset
            next.push({ ...p, offsetInBone: o })
          }
        }
      }
      current = next
      continue
    }
    if (r.count < 2) continue
    const axisIdx = r.axis === 'x' ? 0 : r.axis === 'y' ? 1 : 2
    if ((r as { kind?: string }).kind === 'linkChain') {
      // Chain: alternating 90° rotation around chain axis so adjacent
      // links interlock (real metal chain topology).
      const lc = r as { axis: 'x'|'y'|'z'; count: number; spacing: number }
      const half = Math.PI / 4
      const sinH = Math.sin(half), cosH = Math.cos(half)
      const rotQuat: [number, number, number, number] = [0, 0, 0, cosH]
      rotQuat[axisIdx] = sinH
      for (const p of current) {
        for (let i = 0; i < lc.count; i++) {
          const offset = (i - (lc.count - 1) / 2) * lc.spacing
          const o: [number, number, number] = [p.offsetInBone[0], p.offsetInBone[1], p.offsetInBone[2]]
          o[axisIdx] += offset
          const newPrim: RaymarchPrimitive = { ...p, offsetInBone: o }
          if (i % 2 === 1) newPrim.rotation = rotQuat
          next.push(newPrim)
        }
      }
    } else if ((r as { kind?: string }).kind === 'rotational') {
      // Rotational: each copy's offset rotates around `axis` by i*(2π/count).
      // The prim itself stays in its original orientation — only the position
      // sweeps around the axis.
      for (const p of current) {
        const o = p.offsetInBone
        for (let i = 0; i < r.count; i++) {
          const a = (i / r.count) * Math.PI * 2
          const c = Math.cos(a), s = Math.sin(a)
          // Rotate the offset around the named axis.
          let ox = o[0], oy = o[1], oz = o[2]
          if (r.axis === 'y') { ox = c * o[0] + s * o[2]; oz = -s * o[0] + c * o[2] }
          else if (r.axis === 'x') { oy = c * o[1] - s * o[2]; oz = s * o[1] + c * o[2] }
          else { ox = c * o[0] - s * o[1]; oy = s * o[0] + c * o[1] }
          next.push({ ...p, offsetInBone: [ox, oy, oz] })
        }
      }
    } else {
      // Linear: translate each copy along the axis, centered on the original.
      const spacing = (r as { spacing: number }).spacing
      for (const p of current) {
        for (let i = 0; i < r.count; i++) {
          const offset = (i - (r.count - 1) / 2) * spacing
          next.push({
            ...p,
            offsetInBone: [
              p.offsetInBone[0] + (axisIdx === 0 ? offset : 0),
              p.offsetInBone[1] + (axisIdx === 1 ? offset : 0),
              p.offsetInBone[2] + (axisIdx === 2 ? offset : 0),
            ],
          })
        }
      }
    }
    current = next
  }
  return current
}

/** Seeded LCG PRNG → returns deterministic [0, 1) sequence for a seed. */
function makeRng(seed: number): () => number {
  let s = (seed | 0) || 1
  return () => {
    s = (Math.imul(s, 1103515245) + 12345) | 0
    return ((s >>> 0) % 65536) / 65536
  }
}

/** Auto-generate a branching crack path from start to end. Random walk
 *  with perpendicular jitter, plus optional side branches. Same shape
 *  as A* output (a list of waypoint segments) — A* would replace this
 *  with cost-field routing later. */
function generateCrackPath(opts: NonNullable<ModelerPrim['crackPathGen']>): NonNullable<ModelerPrim['pathCarves']> {
  const segments = Math.max(2, opts.segments ?? 10)
  const seed = opts.seed ?? 1
  const branchiness = Math.max(0, Math.min(1, opts.branchiness ?? 0.3))
  const thickness = opts.thickness
  const depth = opts.depth
  const rand = makeRng(seed)
  const dirX = opts.end[0] - opts.start[0]
  const dirY = opts.end[1] - opts.start[1]
  const dirZ = opts.end[2] - opts.start[2]
  const len = Math.hypot(dirX, dirY, dirZ) || 1e-5
  // Normalised perpendicular in XY plane (cracks live on a face).
  const perpX = -dirY / len
  const perpY = dirX / len
  const jitter = (len / segments) * 0.7

  // Build main spine.
  const spine: Vec3[] = [[...opts.start] as Vec3]
  for (let i = 1; i < segments; i++) {
    const t = i / segments
    const offset = (rand() - 0.5) * 2 * jitter
    spine.push([
      opts.start[0] + dirX * t + perpX * offset,
      opts.start[1] + dirY * t + perpY * offset,
      opts.start[2] + dirZ * t,
    ])
  }
  spine.push([...opts.end] as Vec3)

  // Optional meander on top of the spine.
  let smoothSpine = spine
  if (opts.meander && opts.meander > 0) {
    smoothSpine = meanderPath(spine, opts.meander, opts.meanderFreq ?? 3)
  }

  // Spine segments via profile-aware emitter (river → dual-layer U).
  const out: NonNullable<ModelerPrim['pathCarves']> = []
  out.push(...emitCarvesFromPath(smoothSpine, thickness, depth, opts.profile, opts.taper, opts.raise))

  // Optional branches off the spine waypoints (always single-layer 'crack'
  // even when main path is 'river' — branches are tributaries / hairlines).
  for (let i = 1; i < spine.length - 1; i++) {
    if (rand() < branchiness) {
      const branchLen = jitter * (1 + rand() * 1.5)
      const angle = (rand() - 0.5) * Math.PI * 1.4
      const c = Math.cos(angle), s = Math.sin(angle)
      const bx = (dirX / len) * c - (dirY / len) * s
      const by = (dirX / len) * s + (dirY / len) * c
      const branchEnd: Vec3 = [
        spine[i][0] + bx * branchLen,
        spine[i][1] + by * branchLen,
        spine[i][2],
      ]
      out.push({
        from: spine[i], to: branchEnd,
        ...(thickness !== undefined ? { thickness } : {}),
        ...(depth !== undefined ? { depth } : {}),
        ...(opts.raise ? { raise: true } : {}),
      })
    }
  }
  return out
}

/** Drop waypoints that lie on the line between their neighbours. A* output
 *  on a cardinal grid often has many collinear cells along a diagonal —
 *  pruning them gives fewer, cleaner waypoints to smooth. Threshold is
 *  the cross-product magnitude (area of the triangle a-b-c) — small =
 *  nearly-collinear, drop. */
function simplifyPath(wps: Vec3[], threshold = 0.0002): Vec3[] {
  if (wps.length < 3) return wps
  const out: Vec3[] = [wps[0]]
  for (let i = 1; i < wps.length - 1; i++) {
    const a = out[out.length - 1]
    const b = wps[i]
    const c = wps[i + 1]
    const ab0 = b[0] - a[0], ab1 = b[1] - a[1]
    const ac0 = c[0] - a[0], ac1 = c[1] - a[1]
    const cross = Math.abs(ab0 * ac1 - ab1 * ac0)
    if (cross > threshold) out.push(b)
  }
  out.push(wps[wps.length - 1])
  return out
}

/** Catmull-Rom spline through `wps`. Generates `samplesPerSeg` interpolated
 *  points between each pair of waypoints, smoothing the path while passing
 *  through the original points. Boundary handled via endpoint replication. */
function smoothPath(wps: Vec3[], samplesPerSeg = 4): Vec3[] {
  if (wps.length < 2) return wps
  if (wps.length === 2 || samplesPerSeg < 2) return wps
  const out: Vec3[] = [wps[0]]
  for (let i = 0; i < wps.length - 1; i++) {
    const p0 = wps[Math.max(0, i - 1)]
    const p1 = wps[i]
    const p2 = wps[i + 1]
    const p3 = wps[Math.min(wps.length - 1, i + 2)]
    for (let s = 1; s <= samplesPerSeg; s++) {
      const t = s / samplesPerSeg
      const t2 = t * t, t3 = t2 * t
      const cmf = (a: number, b: number, c: number, d: number) =>
        0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3)
      out.push([
        cmf(p0[0], p1[0], p2[0], p3[0]),
        cmf(p0[1], p1[1], p2[1], p3[1]),
        cmf(p0[2], p1[2], p2[2], p3[2]),
      ] as Vec3)
    }
  }
  return out
}

/** Apply sinusoidal perpendicular perturbation to a smoothed path. The
 *  perturbation is in the XY plane (perpendicular to local tangent),
 *  modulated by sin(t * freq * 2π). Endpoints are pinned (no perturbation
 *  at start/end). Use after smoothPath for natural river-meander effect. */
function meanderPath(wps: Vec3[], amplitude: number, freq: number): Vec3[] {
  if (wps.length < 3 || amplitude <= 0) return wps
  const n = wps.length
  const out: Vec3[] = []
  for (let i = 0; i < n; i++) {
    if (i === 0 || i === n - 1) { out.push(wps[i]); continue }
    // Tangent via central difference.
    const a = wps[Math.max(0, i - 1)]
    const c = wps[Math.min(n - 1, i + 1)]
    const tx = c[0] - a[0], ty = c[1] - a[1]
    const tlen = Math.hypot(tx, ty) || 1
    // Perpendicular = rotate tangent 90° in XY (px, py) = (-ty, tx) / |t|.
    const px = -ty / tlen, py = tx / tlen
    // Falloff toward endpoints so amplitude tapers smoothly.
    const u = i / (n - 1)
    const taper = Math.sin(u * Math.PI)              // 0 at ends, 1 at middle
    const w = Math.sin(u * freq * Math.PI * 2) * amplitude * taper
    out.push([wps[i][0] + px * w, wps[i][1] + py * w, wps[i][2]] as Vec3)
  }
  return out
}

/** Convert a smoothed waypoint chain into carve segments based on profile.
 *  - 'crack' (default): one carve per segment with given thickness/depth.
 *  - 'river': two layers stacked. Wide shallow base (thickness*3, depth*0.4)
 *    and narrow deep center (thickness*0.6, depth). Smooth-subtract fuses
 *    them into a U-shape cross-section.
 *  - 'channel': single carve with width=thickness*2, depth=depth (wider
 *    rectangular trough, like a culvert). */
function emitCarvesFromPath(
  wp: Vec3[],
  thickness: number | undefined,
  depth: number | undefined,
  profile: 'crack' | 'river' | 'channel' | undefined,
  taper: number | undefined,
  raise: boolean | undefined = false,
): NonNullable<ModelerPrim['pathCarves']> {
  const out: NonNullable<ModelerPrim['pathCarves']> = []
  const t = thickness ?? 0.0008
  const d = depth ?? 0.010
  const tap = taper ?? 0
  const n = wp.length - 1
  const r = raise ? { raise: true } : {}
  for (let i = 0; i < n; i++) {
    // Linear taper: scale at midpoint of segment i = lerp(1, 1-tap, mid/n).
    const u = (i + 0.5) / Math.max(1, n)
    const k = 1 - tap * u             // 1 at start, 1-tap at end
    if (k <= 0) break
    const tk = t * k
    const dk = d * k
    if (profile === 'river') {
      out.push({ from: wp[i], to: wp[i + 1], thickness: tk * 3.0, depth: dk * 0.4, ...r })
      out.push({ from: wp[i], to: wp[i + 1], thickness: tk * 0.7, depth: dk, ...r })
    } else if (profile === 'channel') {
      out.push({ from: wp[i], to: wp[i + 1], thickness: tk * 2.0, depth: dk, ...r })
    } else {
      out.push({ from: wp[i], to: wp[i + 1], thickness: tk, depth: dk, ...r })
    }
  }
  return out
}

/** Lightning bolt path via midpoint-displacement recursion. Classic algorithm:
 *  start with a single segment; recursively subdivide each segment by inserting
 *  a midpoint displaced perpendicular to the segment by a random amount that
 *  decays with recursion depth. Spawns smaller divergent branches at random
 *  midpoints. Output is sharp (no smoothing) — that's the look. */
function generateLightningPath(
  opts: NonNullable<ModelerPrim['crackPathGen']>,
): NonNullable<ModelerPrim['pathCarves']> {
  const seed = opts.seed ?? 1
  // Default depth lowered 6 → 5 to keep typical segment count near 32 instead
  // of 64. Each segment becomes a roundedBox carve prim that every ray must
  // step through; high counts murder browser perf at modeler resolutions.
  const depth = Math.max(1, Math.min(8, opts.lightningDepth ?? 5))
  const jaggedness = Math.max(0, Math.min(1.0, opts.jaggedness ?? 0.4))
  const branchiness = Math.max(0, Math.min(1, opts.branchiness ?? 0.25))
  const thickness = opts.thickness
  const segDepth = opts.depth
  const taper = opts.taper ?? 0.7   // lightning tapers strongly by default
  const profile = opts.profile
  const rand = makeRng(seed)

  // Build main bolt by recursively splitting each segment.
  let segs: Array<[Vec3, Vec3]> = [[opts.start as Vec3, opts.end as Vec3]]
  const branchSeeds: Array<{ from: Vec3; tangent: Vec3; level: number }> = []
  for (let level = 0; level < depth; level++) {
    const next: Array<[Vec3, Vec3]> = []
    const amp = jaggedness * Math.pow(0.5, level)
    for (const [a, b] of segs) {
      const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2]
      const slen = Math.hypot(dx, dy, dz) || 1e-6
      // Perpendicular in XY plane.
      const px = -dy / slen, py = dx / slen
      const j = (rand() - 0.5) * 2 * amp * slen
      const mid: Vec3 = [
        (a[0] + b[0]) * 0.5 + px * j,
        (a[1] + b[1]) * 0.5 + py * j,
        (a[2] + b[2]) * 0.5,
      ]
      next.push([a, mid])
      next.push([mid, b])
      // Spawn branch from this midpoint at coarsest levels (more visible).
      if (level < 3 && rand() < branchiness) {
        // Branch direction: perturb the parent direction by ±30-70°.
        const angle = ((rand() - 0.5) * 1.4) * (Math.PI / 2)
        const c = Math.cos(angle), s = Math.sin(angle)
        const tx = (dx / slen) * c - (dy / slen) * s
        const ty = (dx / slen) * s + (dy / slen) * c
        branchSeeds.push({ from: mid, tangent: [tx, ty, 0] as Vec3, level })
      }
    }
    segs = next
  }
  // Final main-bolt waypoints (in order along path).
  const wp: Vec3[] = [segs[0][0]]
  for (const [, b] of segs) wp.push(b)
  const out = emitCarvesFromPath(wp, thickness, segDepth, profile, taper, opts.raise)

  // Branches: each is a smaller, jaggier sub-bolt. Use shorter range, steeper
  // taper, half the input thickness/depth.
  for (const b of branchSeeds) {
    const range = (1 / Math.pow(2, b.level + 1)) * 0.6
    const end: Vec3 = [
      b.from[0] + b.tangent[0] * range,
      b.from[1] + b.tangent[1] * range,
      b.from[2],
    ]
    const subOpts = {
      ...opts,
      start: b.from,
      end,
      lightningDepth: Math.max(2, depth - b.level - 2),
      jaggedness: jaggedness * 1.2,
      branchiness: 0,                  // no sub-sub branches (would explode)
      thickness: thickness !== undefined ? thickness * 0.6 : undefined,
      depth: segDepth !== undefined ? segDepth * 0.7 : undefined,
      taper: 0.95,
      seed: seed + Math.floor(rand() * 1e9),
    }
    out.push(...generateLightningPath(subOpts))
  }
  return out
}

/** Recursive Y-fork tree path. Grows from `start` along `direction` for
 *  `length`, then recursively spawns `branches` children at ±branchAngle
 *  with length × lengthDecay. Per-segment thickness/depth scale by
 *  thicknessDecay^level so branches naturally taper to twigs. Use cases:
 *  bare-branch trees, vine systems, vasculature, neural dendrites,
 *  antlers, root networks, lightning trees. */
function generateTreePath(
  opts: NonNullable<ModelerPrim['crackPathGen']>,
): NonNullable<ModelerPrim['pathCarves']> {
  const seed = opts.seed ?? 1
  const initLen = opts.length ?? 0.04
  const branchAngleDeg = opts.branchAngle ?? 28
  const lengthDecay = opts.lengthDecay ?? 0.7
  const thicknessDecay = opts.thicknessDecay ?? 0.7
  const branches = Math.max(1, Math.min(6, opts.branches ?? 2))
  // Default 5 → 4: at branches=2, depth=4 → 15 segments. depth=5 → 31. depth=6
  // → 63. Each becomes a roundedBox prim — keep the default in the live-perf
  // sweet spot. User can opt into deeper trees explicitly.
  const treeDepth = Math.max(1, Math.min(7, opts.treeDepth ?? 4))
  const baseT = opts.thickness ?? 0.0014
  const baseD = opts.depth ?? 0.010
  const profile = opts.profile
  const dir0: [number, number] = [
    opts.direction?.[0] ?? 0,
    opts.direction?.[1] ?? 1,
  ]
  const dlen = Math.hypot(dir0[0], dir0[1]) || 1
  const startDir: [number, number] = [dir0[0] / dlen, dir0[1] / dlen]
  const z0 = opts.start[2]
  const rand = makeRng(seed)

  const out: NonNullable<ModelerPrim['pathCarves']> = []
  const recurse = (
    pos: [number, number],
    dir: [number, number],
    length: number,
    level: number,
  ): void => {
    if (level >= treeDepth || length < 1e-4) return
    // This segment.
    const end: [number, number] = [pos[0] + dir[0] * length, pos[1] + dir[1] * length]
    const taperK = Math.pow(thicknessDecay, level)
    out.push({
      from: [pos[0], pos[1], z0],
      to: [end[0], end[1], z0],
      thickness: baseT * taperK,
      depth: baseD * taperK,
      ...(opts.raise ? { raise: true } : {}),
    })
    // Spawn child branches from `end`, splayed ±branchAngle.
    // For 2 branches: ±half-angle. For 3+: even spread across full ±range.
    const halfAngle = (branchAngleDeg * Math.PI) / 180
    for (let i = 0; i < branches; i++) {
      // Per-branch angle offset across [-half, +half], plus jitter.
      const t = branches === 1 ? 0 : (i / (branches - 1)) * 2 - 1   // -1 .. +1
      const baseAngle = t * halfAngle
      const jitter = (rand() - 0.5) * halfAngle * 0.4
      const a = baseAngle + jitter
      const c = Math.cos(a), s = Math.sin(a)
      const newDir: [number, number] = [
        dir[0] * c - dir[1] * s,
        dir[0] * s + dir[1] * c,
      ]
      // Per-branch length jitter ±20% so branches aren't all identical length.
      const lenJitter = 1 + (rand() - 0.5) * 0.4
      recurse(end, newDir, length * lengthDecay * lenJitter, level + 1)
    }
  }
  recurse(
    [opts.start[0], opts.start[1]],
    startDir,
    initLen,
    0,
  )
  // Tree paths handle their own taper via thicknessDecay; skip emit-time taper.
  // Profile is honoured by re-routing through emitCarvesFromPath only when
  // profile != 'crack' (trees usually want default thin square cross-section).
  if (profile === 'river' || profile === 'channel') {
    // Convert each carve back to a 2-waypoint chain for the profile emitter.
    const reEmit: NonNullable<ModelerPrim['pathCarves']> = []
    for (const c of out) {
      reEmit.push(...emitCarvesFromPath(
        [c.from, c.to],
        c.thickness, c.depth, profile, 0, opts.raise,
      ))
    }
    return reEmit
  }
  return out
}

/** Tendril path: continuous-curvature winding line. Heading rotates each
 *  step by an FBM-driven curvature value (smooth turns, not random jitter).
 *  Different from `walk` (straight line + perpendicular jitter at endpoints
 *  → looks like a fractured spine) and `tree` (discrete Y-fork branches).
 *  One winding line; use repeats / mirror for multiples. Use cases: vines,
 *  tentacles, hair strands, ribbon trails, lazy river meanders without A*. */
function generateTendrilPath(
  opts: NonNullable<ModelerPrim['crackPathGen']>,
): NonNullable<ModelerPrim['pathCarves']> {
  const seed = opts.seed ?? 1
  const steps = Math.max(4, Math.min(96, opts.tendrilSteps ?? 32))
  const totalLen = opts.length ?? 0.10
  const stepSize = totalLen / steps
  const curl = opts.curlIntensity ?? 0.18
  const profile = opts.profile
  const taper = opts.taper ?? 0
  const baseT = opts.thickness ?? 0.0014
  const baseD = opts.depth ?? 0.010
  const dir0: [number, number] = [
    opts.direction?.[0] ?? 1,
    opts.direction?.[1] ?? 0,
  ]
  const dlen = Math.hypot(dir0[0], dir0[1]) || 1
  let dir: [number, number] = [dir0[0] / dlen, dir0[1] / dlen]
  let pos: [number, number, number] = [opts.start[0], opts.start[1], opts.start[2]]
  const rand = makeRng(seed)
  // Two seeded base offsets feed two FBM-equivalent curvature samples for
  // smooth low-freq + slight high-freq detail. Implement as sin chains so we
  // don't need shader fbm here.
  const offA = rand() * 1000
  const offB = rand() * 1000
  const wp: Vec3[] = [pos]
  for (let i = 0; i < steps; i++) {
    // Heading turn: low-freq sin gives gentle drift; high-freq adds wobble.
    const t = i / steps
    const turn =
      Math.sin(t * 6.283 * 1.4 + offA) * curl +
      Math.sin(t * 6.283 * 4.3 + offB) * curl * 0.25
    const c = Math.cos(turn), s = Math.sin(turn)
    dir = [
      dir[0] * c - dir[1] * s,
      dir[0] * s + dir[1] * c,
    ]
    pos = [
      pos[0] + dir[0] * stepSize,
      pos[1] + dir[1] * stepSize,
      pos[2],
    ]
    wp.push(pos)
  }
  return emitCarvesFromPath(wp, baseT, baseD, profile, taper, opts.raise)
}

/** Grid-based A* path-find from start to end through a noise cost field.
 *  Returns the route as a list of waypoint segments. Paths prefer "weak"
 *  cells (low noise cost), giving naturally meandering routes that look
 *  like real fractures following material weakness. 8-connected grid.
 *  Cost field is deterministic per seed so paths are reproducible. */
function generateAStarPath(opts: NonNullable<ModelerPrim['crackPathGen']>): NonNullable<ModelerPrim['pathCarves']> {
  const seed = opts.seed ?? 1
  const grid = Math.max(8, Math.min(64, opts.gridRes ?? 32))
  const noiseWeight = opts.noiseWeight ?? 3.0
  const thickness = opts.thickness
  const depth = opts.depth
  // Bounding box of start+end with padding for path room.
  const padX = Math.abs(opts.end[0] - opts.start[0]) * 0.4 + 0.02
  const padY = Math.abs(opts.end[1] - opts.start[1]) * 0.4 + 0.02
  const minX = Math.min(opts.start[0], opts.end[0]) - padX
  const maxX = Math.max(opts.start[0], opts.end[0]) + padX
  const minY = Math.min(opts.start[1], opts.end[1]) - padY
  const maxY = Math.max(opts.start[1], opts.end[1]) + padY
  const dx = (maxX - minX) / grid
  const dy = (maxY - minY) / grid
  // Deterministic per-cell hash → noise cost in [1.0, 1+noiseWeight].
  const costAt = (x: number, y: number): number => {
    let h = ((x | 0) * 374761393 + (y | 0) * 668265263 + seed) | 0
    h = (h ^ (h >>> 13)) | 0
    h = Math.imul(h, 1274126177)
    return 1.0 + (((h >>> 0) % 1000) / 1000) * noiseWeight
  }
  // World ↔ grid mappers
  const worldToGrid = (wx: number, wy: number): [number, number] => [
    Math.max(0, Math.min(grid - 1, Math.floor((wx - minX) / dx))),
    Math.max(0, Math.min(grid - 1, Math.floor((wy - minY) / dy))),
  ]
  const gridToWorld = (gx: number, gy: number): [number, number] => [
    minX + (gx + 0.5) * dx,
    minY + (gy + 0.5) * dy,
  ]
  const [sx, sy] = worldToGrid(opts.start[0], opts.start[1])
  const [tx, ty] = worldToGrid(opts.end[0], opts.end[1])
  const idx = (x: number, y: number): number => y * grid + x
  // A* — neighbor topology + heuristic + diagonal-step cost all driven by metric.
  // Manhattan = 4-neighbor (right-angle paths only). Chebyshev = 8-neighbor with
  // diagonal cost == orthogonal (45°-preferring). Euclidean = 8-neighbor √2 cost.
  const metric = opts.metric ?? 'euclidean'
  const NEIGHBORS = metric === 'manhattan'
    ? [[1,0],[-1,0],[0,1],[0,-1]]
    : [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]
  const diagCost = metric === 'chebyshev' ? 1.0 : 1.414
  const heuristic = metric === 'manhattan'
    ? (x: number, y: number): number => Math.abs(x - tx) + Math.abs(y - ty)
    : metric === 'chebyshev'
      ? (x: number, y: number): number => Math.max(Math.abs(x - tx), Math.abs(y - ty))
      : (x: number, y: number): number => Math.hypot(x - tx, y - ty)
  const cameFrom = new Map<number, number>()
  const gScore = new Map<number, number>()
  const fScore = new Map<number, number>()
  gScore.set(idx(sx, sy), 0)
  fScore.set(idx(sx, sy), heuristic(sx, sy))
  const open: Array<[number, number]> = [[idx(sx, sy), heuristic(sx, sy)]]
  let foundEnd = -1
  while (open.length > 0) {
    // Pop lowest f-score
    let bestI = 0
    for (let i = 1; i < open.length; i++) if (open[i][1] < open[bestI][1]) bestI = i
    const [cur] = open.splice(bestI, 1)[0]
    const cx = cur % grid, cy = (cur / grid) | 0
    if (cx === tx && cy === ty) { foundEnd = cur; break }
    for (const [ddx, ddy] of NEIGHBORS) {
      const nx = cx + ddx, ny = cy + ddy
      if (nx < 0 || ny < 0 || nx >= grid || ny >= grid) continue
      const ni = idx(nx, ny)
      const stepLen = (ddx !== 0 && ddy !== 0) ? diagCost : 1.0
      const stepCost = costAt(nx, ny) * stepLen
      const tentativeG = (gScore.get(cur) ?? Infinity) + stepCost
      if (tentativeG < (gScore.get(ni) ?? Infinity)) {
        cameFrom.set(ni, cur)
        gScore.set(ni, tentativeG)
        const f = tentativeG + heuristic(nx, ny)
        fScore.set(ni, f)
        if (!open.some(([i]) => i === ni)) open.push([ni, f])
      }
    }
  }
  if (foundEnd < 0) return []  // pathfinding failed
  // Reconstruct grid path
  const gridPath: number[] = [foundEnd]
  let p = foundEnd
  while (cameFrom.has(p)) { p = cameFrom.get(p)!; gridPath.unshift(p) }
  // Convert grid path to world waypoints.
  let wp: Vec3[] = gridPath.map((cell) => {
    const [wx, wy] = gridToWorld(cell % grid, (cell / grid) | 0)
    return [wx, wy, opts.start[2]] as Vec3
  })
  if (wp.length) {
    wp[0] = [opts.start[0], opts.start[1], opts.start[2]] as Vec3
    wp[wp.length - 1] = [opts.end[0], opts.end[1], opts.end[2]] as Vec3
  }
  // Polish: Catmull-Rom smooth ONLY. Don't pre-simplify — A* output
  // includes diagonal moves we want to keep, and overzealous simplify
  // straightens the meandering. Sample 3 sub-points per segment.
  // 3 sub-points per segment was visibly smooth but ~3× the prim count of
  // the raw A* path. 2 reads almost identical and halves the live cost.
  // Manhattan/Chebyshev paths are kept ANGULAR — smoothing would round off
  // the right-angle corners that ARE the visual signature.
  if (metric === 'euclidean') wp = smoothPath(wp, 2)
  // Optional sinusoidal meander on top of the smoothed path.
  if (opts.meander && opts.meander > 0) {
    wp = meanderPath(wp, opts.meander, opts.meanderFreq ?? 3)
  }
  const main = emitCarvesFromPath(wp, thickness, depth, opts.profile, opts.taper, opts.raise)

  // Optional endpoint caps. Default-on for raised paths (pipes need to
  // terminate visibly); default-off for carved (extra pits at trench ends
  // read as accidents). Reuses the joint sphere geometry from iter 29.
  const endCaps = opts.endCaps ?? !!opts.raise
  if (endCaps && wp.length >= 2) {
    const tubeT = thickness ?? 0.0018
    const tubeD = depth ?? 0.003
    const capR = Math.max(tubeT * 2.5, tubeD * 2.0)
    for (const pt of [wp[0], wp[wp.length - 1]]) {
      main.push({
        from: pt,
        to: pt,
        thickness: capR,
        depth: tubeD,
        kind: 'joint',
        ...(opts.raise ? { raise: true } : {}),
      })
    }
  }

  // Optional T-junction branches off the main spine. Each branch picks a
  // random INTERIOR waypoint, computes the local tangent via central
  // difference, projects perpendicular by a random length (40-70% of
  // main bbox diagonal), then runs a sub-A* from waypoint → projected end.
  // Recurses with branches=0 so we don't get a fractal explosion.
  const branchCount = Math.max(0, Math.min(8, opts.astarBranches ?? 0))
  if (branchCount > 0 && wp.length > 4) {
    const bRng = makeRng(seed ^ 0x9e3779b1)
    const mainLen = Math.hypot(opts.end[0] - opts.start[0], opts.end[1] - opts.start[1]) || 0.04
    const bThickness = thickness !== undefined ? thickness * 0.6 : undefined
    const bDepth = depth !== undefined ? depth * 0.85 : undefined
    const usedWp = new Set<number>()
    for (let b = 0; b < branchCount; b++) {
      // Random interior waypoint (not endpoints — endpoint branches look detached)
      let wpIdx = -1
      for (let tries = 0; tries < 8; tries++) {
        const cand = 1 + Math.floor(bRng() * (wp.length - 2))
        if (!usedWp.has(cand)) { wpIdx = cand; break }
      }
      if (wpIdx < 0) wpIdx = 1 + Math.floor(bRng() * (wp.length - 2))
      usedWp.add(wpIdx)
      const branchStart = wp[wpIdx]
      // Local tangent: central difference
      const wPrev = wp[wpIdx - 1]
      const wNext = wp[wpIdx + 1]
      const tnx = wNext[0] - wPrev[0]
      const tny = wNext[1] - wPrev[1]
      const tlen = Math.hypot(tnx, tny) || 1
      // Perpendicular in XY, random side
      const side = bRng() < 0.5 ? -1 : 1
      const px = (-tny / tlen) * side
      const py = (tnx / tlen) * side
      // Branch length 30-60% of main bbox diagonal
      const bLen = mainLen * (0.3 + bRng() * 0.3)
      const branchEnd: Vec3 = [
        branchStart[0] + px * bLen,
        branchStart[1] + py * bLen,
        branchStart[2],
      ]
      const subOpts: NonNullable<ModelerPrim['crackPathGen']> = {
        ...opts,
        start: branchStart,
        end: branchEnd,
        seed: (opts.seed ?? 1) + (b + 1) * 1000,
        astarBranches: 0,                       // no recursive branching
        thickness: bThickness,
        depth: bDepth,
      }
      main.push(...generateAStarPath(subOpts))
      // Engineered-fitting joint at the branch connection point. Sphere
      // radius must exceed pipe depth or the sphere stays buried inside
      // the tube/trench union and contributes nothing visually. Take the
      // max of (1.5× thickness, 1.2× depth) so the joint always bulges
      // above the spine. Inherits raise polarity → raised T-fitting /
      // carved sinkhole.
      const tubeT = thickness ?? 0.0018
      const tubeD = depth ?? 0.003
      // 2.5× / 2.0× empirically gives joints that read as distinct fittings
      // rather than dissolving into the spine. Lower multipliers (1.5×/1.2×)
      // produced bumps inside the pipe's smooth-union envelope — invisible.
      const jointR = Math.max(tubeT * 2.5, tubeD * 2.0)
      main.push({
        from: branchStart,
        to: branchStart,
        thickness: jointR,
        depth: tubeD,
        kind: 'joint',
        ...(opts.raise ? { raise: true } : {}),
      })
    }
  }
  return main
}

/** Expand a list of path-segments into box prims that either carve trenches
 *  (default) or extrude raised tubes (when c.raise is true) along each
 *  segment. The waypoints are generated externally (manual, A*, random walk,
 *  lightning, tree, tendril); this function builds the geometry. Each
 *  segment becomes a thin box rotated to align its long axis (local Y) with
 *  the segment direction (XY plane only — Z direction is currently flat).
 *  The boxes inherit the parent prim's blendGroup; blendRadius is negative
 *  for carves (smooth subtraction), positive for raised tubes (smooth
 *  union — small fillet at wall-tube interface). */
function expandPathCarves(
  parent: RaymarchPrimitive,
  carves: NonNullable<ModelerPrim['pathCarves']>,
): RaymarchPrimitive[] {
  const out: RaymarchPrimitive[] = []
  for (let i = 0; i < carves.length; i++) {
    const c = carves[i]
    if (c.kind === 'joint') {
      // Sphere fitting at c.from. Radius = thickness; ignores c.to.
      // T-junction connection points so branches read as engineered
      // fittings rather than two paths crossing.
      const r = c.thickness ?? 0.0008
      out.push({
        type: 0,                                       // sphere
        paletteSlot: 0,
        boneIdx: 0,
        params: [r, 0, 0, 0],
        offsetInBone: [c.from[0], c.from[1], c.from[2]],
        blendGroup: parent.blendGroup ?? 1,
        // Slightly tighter blend than segments so the joint reads as a
        // distinct bulb rather than melting fully into the spine.
        blendRadius: c.raise ? 0.0015 : -0.0015,
        rotation: [0, 0, 0, 1],
      })
      continue
    }
    const dx = c.to[0] - c.from[0]
    const dy = c.to[1] - c.from[1]
    const dz = c.to[2] - c.from[2]
    const len = Math.sqrt(dx * dx + dy * dy + dz * dz)
    if (len < 1e-5) continue
    const cx = (c.from[0] + c.to[0]) * 0.5
    const cy = (c.from[1] + c.to[1]) * 0.5
    const cz = (c.from[2] + c.to[2]) * 0.5
    const thickness = c.thickness ?? 0.0008
    const depth = c.depth ?? 0.010
    // Extend each segment beyond its endpoints so adjacent segments overlap;
    // smooth-subtract then fuses them into a continuous groove instead of
    // reading as a chain of discrete dimples.
    const overlap = thickness * 1.5
    const angleRad = Math.atan2(dy, dx)
    const angleDeg = (angleRad * 180) / Math.PI - 90
    const halfA = (angleDeg * Math.PI) / 360
    const quat: Vec4 = [0, 0, Math.sin(halfA), Math.cos(halfA)]
    out.push({
      type: 2,                                       // roundedBox — naturally rounded ends merge cleanly with neighboring segments
      paletteSlot: 0,
      boneIdx: 0,
      params: [thickness, len * 0.5 + overlap, depth, thickness * 0.9],
      offsetInBone: [cx, cy, cz],
      blendGroup: parent.blendGroup ?? 1,
      // Carves subtract (-0.002), raised tubes add (+0.002 fillet at the
      // wall-tube join). Same magnitude → predictable visual weight.
      blendRadius: c.raise ? 0.002 : -0.002,
      rotation: quat,
    })
  }
  return out
}

// --- Reaction-diffusion (Gray-Scott) CPU bake ----------------------------

const RD_GRID_SIZE = 128 // must match raymarch_renderer's RD_GRID

/** Named Gray-Scott (F, k) presets. Lifted from Pearson 1993 + community-
 *  curated ranges. Each pattern emerges only inside a narrow F/k band — the
 *  presets pick a stable point inside each band. Authors who want
 *  experimental drift override via rdFeed/rdKill explicitly. */
const RD_PRESETS = {
  coral:       [0.055, 0.062],   // discrete amoeba spots, intricate boundaries
  brain:       [0.040, 0.060],   // maze-like worm-loops (brain-coral)
  zebra:       [0.020, 0.060],   // long parallel stripes
  leopard:     [0.025, 0.060],   // larger scattered spots, less intricate than coral
  spots:       [0.014, 0.054],   // small bright pinpricks on dark
  chaos:       [0.026, 0.051],   // unstable mixture, never settles
  fingerprint: [0.038, 0.061],   // ridges + bifurcations, near-brain but tighter
  flower:      [0.062, 0.061],   // hex-packed bulbs, almost periodic
} as const satisfies Record<string, readonly [number, number]>

interface RDBakeOpts { feed: number; kill: number; iterations: number; seed: number }

/** Cached last bake — keyed on opts. Avoids re-computing if spec re-ingests
 *  with the same parameters (typical when authoring non-RD prims). */
let rdBakeCache: { key: string; field: Float32Array } | null = null

/** Run N iterations of the Gray-Scott reaction-diffusion model on a
 *  RD_GRID²-sized 2D field. Returns the V channel, normalised so that the
 *  highest value in the field maps to ~1.0 (the deformer expects roughly
 *  [0, 1]). Toroidal boundaries (wraps), so the field tiles cleanly.
 *
 *  Gray-Scott classical setup: U + 2V → 3V (V eats U via autocatalysis),
 *  V → P (V decays to inert P at rate k+F). Initial conditions: U=1, V=0
 *  everywhere except a small seed patch where V=0.5. Standard Du=1, Dv=0.5
 *  diffusion-coefficient ratio. dt=1, 5-point Laplacian.
 *
 *  Param presets (F, k):
 *    coral    = (0.055, 0.062)
 *    brain    = (0.040, 0.060)
 *    zebra    = (0.020, 0.060)
 *    leopard  = (0.025, 0.060)
 *    spots    = (0.014, 0.054)
 *    chaos    = (0.026, 0.051) */
function bakeReactionDiffusion(opts: RDBakeOpts): Float32Array {
  const key = `${opts.feed}|${opts.kill}|${opts.iterations}|${opts.seed}`
  if (rdBakeCache && rdBakeCache.key === key) return rdBakeCache.field

  const N = RD_GRID_SIZE
  // Pearson's classical params (1993). Du=0.16, Dv=0.08 with dt=1.0 keeps
  // the explicit Euler integration stable. With Du=1.0 the 5-point
  // Laplacian's swing (×4 neighbor count) blows past the dt=1 stability
  // bound, producing NaN — and NaN propagates to the GPU buffer, making
  // d = d - NaN*amp return NaN and the surface vanishes.
  const Du = 0.16, Dv = 0.08, dt = 1.0
  const F = opts.feed, k = opts.kill
  const iters = Math.max(50, Math.min(8000, opts.iterations | 0))

  // Double buffers. U starts at 1.0, V at 0.0 (steady state).
  let U = new Float32Array(N * N).fill(1.0)
  let V = new Float32Array(N * N).fill(0.0)
  let U2 = new Float32Array(N * N)
  let V2 = new Float32Array(N * N)

  // Seed: random ~5% of cells get a V-perturbation. Deterministic from seed.
  const rand = makeRng(opts.seed)
  for (let i = 0; i < N * N; i++) {
    if (rand() < 0.05) { U[i] = 0.5; V[i] = 0.25 + rand() * 0.25 }
  }

  // Update loop. 5-point Laplacian with toroidal wraps.
  for (let it = 0; it < iters; it++) {
    for (let y = 0; y < N; y++) {
      const yp = (y - 1 + N) % N, yn = (y + 1) % N
      const yRow = y * N, ypRow = yp * N, ynRow = yn * N
      for (let x = 0; x < N; x++) {
        const xp = (x - 1 + N) % N, xn = (x + 1) % N
        const i = yRow + x
        const Ucenter = U[i], Vcenter = V[i]
        // 5-point Laplacian: 4 neighbors - 4×center.
        const Lu = U[yRow + xp] + U[yRow + xn] + U[ypRow + x] + U[ynRow + x] - 4 * Ucenter
        const Lv = V[yRow + xp] + V[yRow + xn] + V[ypRow + x] + V[ynRow + x] - 4 * Vcenter
        const reac = Ucenter * Vcenter * Vcenter
        U2[i] = Ucenter + dt * (Du * Lu - reac + F * (1 - Ucenter))
        V2[i] = Vcenter + dt * (Dv * Lv + reac - (k + F) * Vcenter)
      }
    }
    // Swap.
    const tU = U, tV = V
    U = U2; V = V2; U2 = tU; V2 = tV
  }

  // Normalize V to ~[0, 1] so the deformer's amplitude reads predictably.
  let vMax = 0
  for (let i = 0; i < V.length; i++) if (V[i] > vMax) vMax = V[i]
  if (vMax > 1e-4) {
    const scale = 1 / vMax
    for (let i = 0; i < V.length; i++) V[i] *= scale
  }

  rdBakeCache = { key, field: V }
  return V
}


// --- Spec -> prims --------------------------------------------------------

function specToPrims(spec: ModelerSpec): RaymarchPrimitive[] {
  const out: RaymarchPrimitive[] = []
  for (const p of spec.primitives) {
    const meta = TYPE_META[p.type]
    if (!meta) continue
    const prim: RaymarchPrimitive = {
      type: meta.id,
      paletteSlot: 0,                  // single material slot — see MATERIAL_RGB
      boneIdx: 0,
      params: [p.params[0], p.params[1], p.params[2], p.params[3]],
      offsetInBone: [p.pos[0], p.pos[1], p.pos[2]],
      blendGroup: p.blendGroup,
      blendRadius: p.blendRadius,
      chamfer: p.chamfer,
      mirrorYZ: p.mirrorYZ,
    }
    if (p.type === 'bentCapsule' && p.tipDelta) {
      // Engine overloads slot 4 (rotation) as tipDelta for bentCapsule.
      // xyz = tip displacement in primitive-local space, w ignored.
      prim.rotation = [p.tipDelta[0], p.tipDelta[1], p.tipDelta[2], 0]
    } else if (!isIdentityRotation(p.rotationDeg)) {
      prim.rotation = eulerToQuat(p.rotationDeg)
    }
    if (p.detailAmplitude && p.detailAmplitude > 0) {
      prim.detailAmplitude = p.detailAmplitude
    }
    // crackDepth: geometric crack-displacement, color side suppressed by
    // setting paletteSlotB == paletteSlot so the colorFunc=9 dark-band code
    // path is a no-op visually. Modeler stays GEOMETRY-ONLY.
    if (p.crackDepth && p.crackDepth > 0) {
      prim.colorFunc = 9
      prim.detailAmplitude = p.crackDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.crackDensity ?? 30
    } else if (p.pitDepth && p.pitDepth > 0) {
      // pits (colorFunc=10) — same overload pattern as cracks
      prim.colorFunc = 10
      prim.detailAmplitude = p.pitDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.pitDensity ?? 30
    } else if (p.bumpDepth && p.bumpDepth > 0) {
      // bumps (colorFunc=11) — smooth FBM outward displacement
      prim.colorFunc = 11
      prim.detailAmplitude = p.bumpDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.bumpDensity ?? 30
    } else if (p.scaleDepth && p.scaleDepth > 0) {
      // scales (colorFunc=12) — raised cellular ridges, dark cell-edge accent
      prim.colorFunc = 12
      prim.detailAmplitude = p.scaleDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.scaleDensity ?? 30
    } else if (p.grainDepth && p.grainDepth > 0) {
      // grain (colorFunc=14) — sunken FBM-warped stripes along Y
      prim.colorFunc = 14
      prim.detailAmplitude = p.grainDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.grainDensity ?? 30
    } else if (p.ridgeDepth && p.ridgeDepth > 0) {
      // ridges (colorFunc=15) — 4-octave folded ridged multifractal
      prim.colorFunc = 15
      prim.detailAmplitude = p.ridgeDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.ridgeDensity ?? 20
    } else if (p.streakDepth && p.streakDepth > 0) {
      // streaks (colorFunc=16) — gravity-aligned erosion drips
      prim.colorFunc = 16
      prim.detailAmplitude = p.streakDepth
      prim.paletteSlotB = 0
      prim.colorExtent = p.streakDensity ?? 25
    } else if (p.hexDepth && p.hexDepth > 0) {
      // hex tiles (colorFunc=17) — sunken mortar between raised plates → dark
      prim.colorFunc = 17
      prim.detailAmplitude = p.hexDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.hexDensity ?? 30
    } else if (p.brickDepth && p.brickDepth > 0) {
      // brick masonry (colorFunc=18) — sunken mortar joints → dark
      prim.colorFunc = 18
      prim.detailAmplitude = p.brickDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.brickDensity ?? 25
    } else if (p.voronoiCrackDepth && p.voronoiCrackDepth > 0) {
      // Voronoi cracks (colorFunc=19) — sunken cell-edge fractures → dark
      prim.colorFunc = 19
      prim.detailAmplitude = p.voronoiCrackDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.voronoiCrackDensity ?? 28
    } else if (p.scratchDepth && p.scratchDepth > 0) {
      // scratches (colorFunc=20) — sunken stroke wear → dark
      prim.colorFunc = 20
      prim.detailAmplitude = p.scratchDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.scratchDensity ?? 40
    } else if (p.dimpleDepth && p.dimpleDepth > 0) {
      // dimples (colorFunc=21) — sunken indents → dark interior
      prim.colorFunc = 21
      prim.detailAmplitude = p.dimpleDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.dimpleDensity ?? 30
    } else if (p.studDepth && p.studDepth > 0) {
      // studs (colorFunc=22) — RAISED hemispheres → bright tops by default
      prim.colorFunc = 22
      prim.detailAmplitude = p.studDepth
      prim.paletteSlotB = p.accentSlot ?? 2
      prim.colorExtent = p.studDensity ?? 30
    } else if (p.chevronDepth && p.chevronDepth > 0) {
      // chevrons (colorFunc=23) — RAISED V-ridges → bright ridge tops
      prim.colorFunc = 23
      prim.detailAmplitude = p.chevronDepth
      prim.paletteSlotB = p.accentSlot ?? 2
      prim.colorExtent = p.chevronDensity ?? 25
    } else if (p.whorlDepth && p.whorlDepth > 0) {
      // whorl (colorFunc=24) — concentric ring lines, sunken with dark accent
      prim.colorFunc = 24
      prim.detailAmplitude = p.whorlDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.whorlDensity ?? 28
    } else if (p.fishscaleDepth && p.fishscaleDepth > 0) {
      // fishscale (colorFunc=25) — offset arc-rows, sunken shadow line, dark accent
      prim.colorFunc = 25
      prim.detailAmplitude = p.fishscaleDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.fishscaleDensity ?? 28
    } else if (p.weaveDepth && p.weaveDepth > 0) {
      // weave (colorFunc=26) — RAISED strands, dark gaps between
      prim.colorFunc = 26
      prim.detailAmplitude = p.weaveDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.weaveDensity ?? 22
    } else if (p.rdDepth && p.rdDepth > 0) {
      // reaction-diffusion (colorFunc=27) — RAISED peaks (high V), accent
      // slot picks coral/spot color. Field is shared globally per scene
      // (one bake) — first RD prim's F/k/iters/seed wins.
      prim.colorFunc = 27
      prim.detailAmplitude = p.rdDepth
      prim.paletteSlotB = p.accentSlot ?? 2
      prim.colorExtent = p.rdDensity ?? 12
    } else if (p.cloudDepth && p.cloudDepth > 0) {
      // cloud (colorFunc=29) — pure white puff, slot B for shadowed cracks
      prim.colorFunc = 29
      prim.detailAmplitude = p.cloudDepth
      prim.paletteSlotB = p.accentSlot ?? 1
      prim.colorExtent = p.cloudDensity ?? 12
    } else if (p.terrainDepth && p.terrainDepth > 0) {
      // terrain heightmap (colorFunc=28) — RAISED peaks. Snow/peak slot
      // for high altitudes; one shared field per scene.
      prim.colorFunc = 28
      prim.detailAmplitude = p.terrainDepth
      prim.paletteSlotB = p.accentSlot ?? 2
      prim.colorExtent = p.terrainDensity ?? 12
      if (typeof p.terrainFlowDepth === 'number' && p.terrainFlowDepth > 0) {
        prim.terrainFlowDepth = p.terrainFlowDepth
      }
    }
    // Secondary wear deformer (optional, runs AFTER the primary).
    if (p.wearDeformer && p.wearDeformer.depth > 0) {
      const wearMap = { bumps: 1, grain: 2, streaks: 3, scratches: 4 } as const
      prim.wearFn = wearMap[p.wearDeformer.type] as 1 | 2 | 3 | 4
      prim.wearDepth = p.wearDeformer.depth
      prim.wearDensity = p.wearDeformer.density ?? 30
    }
    // Order: repeat → mirror. So a repeating prim gets duplicated N times,
    // then each duplicate is mirrored if mirrorYZ is set.
    out.push(...applyRepeats(prim, p.repeats))
    // Soft cap on total carves: live-render perf melts above ~150 carve prims
    // per parent (each becomes a roundedBox the ray must step through).
    // When over budget, decimate uniformly so the silhouette stays right.
    const decimateCarves = (carves: NonNullable<ModelerPrim['pathCarves']>, budget: number) => {
      if (carves.length <= budget) return carves
      const step = carves.length / budget
      const out: NonNullable<ModelerPrim['pathCarves']> = []
      for (let i = 0; i < budget; i++) out.push(carves[Math.floor(i * step)])
      console.warn(`path-carves: decimated ${carves.length} → ${budget} (live-perf cap)`)
      return out
    }
    // Resolve crack path: explicit pathCarves OR auto-generated.
    // crackPathGen.mode picks generator: walk / astar / lightning / tree / tendril.
    const generated = p.crackPathGen
      ? (p.crackPathGen.mode === 'astar'
          ? generateAStarPath(p.crackPathGen)
          : p.crackPathGen.mode === 'lightning'
            ? generateLightningPath(p.crackPathGen)
            : p.crackPathGen.mode === 'tree'
              ? generateTreePath(p.crackPathGen)
              : p.crackPathGen.mode === 'tendril'
                ? generateTendrilPath(p.crackPathGen)
                : generateCrackPath(p.crackPathGen))
      : []
    const carves = decimateCarves([...(p.pathCarves ?? []), ...generated], 150)
    if (carves.length) {
      out.push(...expandPathCarves(prim, carves))
    }
  }
  return expandMirrors(out)
}

// --- DOM helpers ---------------------------------------------------------

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  opts: { class?: string; text?: string; title?: string; style?: Record<string,string>; children?: Node[] } = {},
): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag)
  if (opts.class) n.className = opts.class
  if (opts.text != null) n.textContent = opts.text
  if (opts.title) n.title = opts.title
  if (opts.style) for (const k in opts.style) (n.style as Record<string, string>)[k] = opts.style[k]
  if (opts.children) for (const c of opts.children) n.appendChild(c)
  return n
}
function clearNode(node: Element) { while (node.firstChild) node.removeChild(node.firstChild) }
function $<T extends HTMLElement = HTMLElement>(id: string): T { return document.getElementById(id) as T }

function rgbToHex(c: Vec3): string {
  const r = Math.round(Math.max(0, Math.min(1, c[0])) * 255)
  const g = Math.round(Math.max(0, Math.min(1, c[1])) * 255)
  const b = Math.round(Math.max(0, Math.min(1, c[2])) * 255)
  return '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')
}
function hexToRgb(hex: string): Vec3 {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) return [0.5, 0.5, 0.5]
  const n = parseInt(m[1], 16)
  return [((n >> 16) & 0xff) / 255, ((n >> 8) & 0xff) / 255, (n & 0xff) / 255]
}

// --- Agent-mode 4-view atlas -------------------------------------------
//
// 2×2 panels, each is the same scene rendered from a different orientation:
//   ┌─────────┬─────────┐
//   │  front  │  side   │     front: looks down −Z   (X right, Y up)
//   ├─────────┼─────────┤     side : looks down −X   (Z right, Y up)
//   │  top    │  iso    │     top  : looks down −Y   (X right, Z up)
//   └─────────┴─────────┘     iso  : 3-quarter (vibe check)
//
// Orthographic measurements live in front/side/top; iso is the gestalt
// check. Same atlas works for VLM input and human verification.

interface AtlasView {
  name: 'front' | 'side' | 'top' | 'iso'
  /** Yaw radians (0 = +Z forward). */
  yaw: number
  /** Pitch radians (0 = horizon, +π/2 = top-down). */
  pitch: number
  /** Up vector — top view needs a different up to avoid lookAt singularity. */
  up: Vec3
}

const ATLAS_VIEWS: AtlasView[] = [
  { name: 'front', yaw: 0,                pitch: 0,                up: [0, 1, 0] },
  { name: 'side',  yaw: Math.PI * 0.5,    pitch: 0,                up: [0, 1, 0] },
  { name: 'top',   yaw: 0,                pitch: Math.PI * 0.5 - 0.001, up: [0, 0, -1] },
  { name: 'iso',   yaw: Math.PI * 0.25,   pitch: Math.PI * 0.20,   up: [0, 1, 0] },
]

function eyeFromOrbit(target: Vec3, yaw: number, pitch: number, dist: number): Vec3 {
  const cp = Math.cos(pitch)
  return [
    target[0] + dist * cp * Math.sin(yaw),
    target[1] + dist * Math.sin(pitch),
    target[2] + dist * cp * Math.cos(yaw),
  ]
}

// --- Clean modeler-tool lit pass --------------------------------------
// Reads the raymarch G-buffer (color/normal/depth), composites with smooth
// Lambert + half-Lambert fill + a soft rim + a checker background. No cel
// banding, no outlines. Intended to give a VLM (and a human) a clean view
// of geometry, surface orientation, and silhouettes.

const LIT_SHADER = /* wgsl */ `
struct U {
  viewMode: u32,    // 0 = lit color, 1 = normal-debug, 2 = depth-debug
  _pad0: u32, _pad1: u32, _pad2: u32,
  keyDir:  vec4f,   // xyz = direction TO key light, w = intensity
  fillDir: vec4f,   // xyz = direction TO fill light, w = intensity
  ambient: vec4f,   // rgb ambient floor, w = rim strength
  cameraDir: vec4f, // xyz = direction subject→camera (view direction), w unused
}

@group(0) @binding(0) var sceneTex:  texture_2d<f32>;
@group(0) @binding(1) var normalTex: texture_2d<f32>;
@group(0) @binding(2) var depthTex:  texture_2d<f32>;
@group(0) @binding(3) var smp:       sampler;
@group(0) @binding(4) var<uniform> u: U;

struct VsOut {
  @builtin(position) clip: vec4f,
  @location(0) uv: vec2f,
}

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  let corners = array<vec2f, 3>(vec2f(-1.0, -1.0), vec2f(3.0, -1.0), vec2f(-1.0, 3.0));
  var out: VsOut;
  out.clip = vec4f(corners[vid], 0.0, 1.0);
  // Flip Y so uv (0,0) is top-left like screen pixels.
  out.uv = vec2f((corners[vid].x + 1.0) * 0.5, 1.0 - (corners[vid].y + 1.0) * 0.5);
  return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4f {
  let scene = textureSample(sceneTex,  smp, in.uv);
  let nEnc  = textureSample(normalTex, smp, in.uv);
  let dEnc  = textureSample(depthTex,  smp, in.uv);

  // alpha=1 from raymarch hit, alpha=0 from miss — see raymarch fs_main.
  let isHit = scene.a > 0.5;

  // Background: subtle checker so the LLM has a spatial anchor and the
  // canvas isn't a flat colour. 16-pixel cells, two near-grays.
  // Compute normal + curvature UNCONDITIONALLY so dpdx/dpdy are called in
  // uniform control flow. Garbage values for non-hit pixels are fine —
  // they get gated by the mode/isHit branches below.
  let n = normalize(nEnc.xyz * 2.0 - 1.0);
  let nDx = dpdxFine(n);
  let nDy = dpdyFine(n);
  let curv = clamp((length(nDx) + length(nDy)) * 0.6, 0.0, 1.0);

  // Silhouette mode (3): pure binary mask, no grid, no shading.
  if (u.viewMode == 3u) {
    return vec4f(vec3f(select(0.0, 1.0, isHit)), 1.0);
  }

  if (!isHit) {
    // Coordinate grid bg: 1cm and 5mm lines on a panel ~30cm wide.
    let dim   = vec2f(textureDimensions(sceneTex));
    let cm    = (in.uv - vec2f(0.5)) * 30.0;
    let major = abs(fract(cm + vec2f(0.5)) - vec2f(0.5));
    let lineWidthCm = 30.0 / dim.x;                  // 1 px in cm at this res
    let majorLine = 1.0 - smoothstep(0.0, lineWidthCm * 0.8, min(major.x, major.y));
    let minor = abs(fract(cm * 2.0 + vec2f(0.5)) - vec2f(0.5));
    let minorLine = (1.0 - smoothstep(0.0, lineWidthCm * 0.6, min(minor.x, minor.y))) * 0.45;
    let line = max(majorLine, minorLine);
    let bg = mix(vec3f(0.14, 0.15, 0.18), vec3f(0.32, 0.34, 0.40), line);
    return vec4f(bg, 1.0);
  }

  if (u.viewMode == 1u) { return vec4f(nEnc.xyz, 1.0); }
  if (u.viewMode == 2u) {
    // Depth view: Sobel-of-depth highlights surface curvature + edges
    // directly, sidestepping the saturation problem (raw d.r clusters
    // at one end of [0,1]). Sobel shows WHERE of depth-discontinuities
    // (silhouette edges, ridges, SDF kinks) without needing an absolute
    // range. Uses textureLoad (no sampler) to satisfy WGSL's uniform-
    // control-flow requirement on conditional branches.
    let dim = vec2i(textureDimensions(sceneTex));
    let px = vec2i(in.uv * vec2f(dim));
    let dN = textureLoad(depthTex, clamp(px + vec2i( 0, -1), vec2i(0), dim - vec2i(1)), 0).r;
    let dS = textureLoad(depthTex, clamp(px + vec2i( 0,  1), vec2i(0), dim - vec2i(1)), 0).r;
    let dE = textureLoad(depthTex, clamp(px + vec2i( 1,  0), vec2i(0), dim - vec2i(1)), 0).r;
    let dW = textureLoad(depthTex, clamp(px + vec2i(-1,  0), vec2i(0), dim - vec2i(1)), 0).r;
    let grad = abs(dE - dW) + abs(dN - dS);
    let g = clamp(grad * 200.0, 0.0, 1.0);
    return vec4f(vec3f(g), 1.0);
  }
  if (u.viewMode == 4u) {
    return vec4f(vec3f(curv), 1.0);
  }
  if (u.viewMode == 5u) {
    let h = abs(n.x * 0.7 + n.y * 1.1 + n.z * 0.4) * 7.0;
    let r = 0.5 + 0.5 * cos(h);
    let g = 0.5 + 0.5 * cos(h + 2.094);
    let b = 0.5 + 0.5 * cos(h + 4.189);
    return vec4f(r, g, b, 1.0);
  }

  // Unlit pixels (sky, VFX with own emissive, anything raymarch flagged)
  // pass their albedo through unmodified. depth.g = 1 packed by raymarch.
  if (dEnc.g > 0.5) {
    return vec4f(scene.rgb, 1.0);
  }

  // Lit composite. Smooth Lambert key + half-Lambert wrap fill so back-
  // facing surfaces aren't pure black — keeps detail visible from any
  // panel's camera.
  let kDir = normalize(u.keyDir.xyz);
  let fDir = normalize(u.fillDir.xyz);
  let nDotK = max(dot(n, kDir), 0.0);
  let nDotF = dot(n, fDir) * 0.5 + 0.5;   // wrap to [0,1] across the sphere

  // Physically-plausible colored lights:
  //   Key (sun): warm yellow — direct sunlight near 5500K
  //   Fill (sky bounce): cool blue — Rayleigh scatter from sky dome
  // Ambient stays neutral. Together they produce golden-hour
  // atmospheric shading characteristic of real outdoor terrain.
  // G-buffer occlusion channels:
  //   depth.b = directVis  (sun shadow × cloud) — blocks KEY only
  //   depth.a = aoFactor   (local AO)            — blocks ambient + fill
  // AO never touches direct light; a crevice can still be sunlit from
  // the open side. Sun shadow never touches indirect light; sky-bounce
  // fill still reaches the shaded ground. Defaults 1.0 for non-terrain.
  let directVis = clamp(dEnc.b, 0.0, 1.0);
  let aoFactor  = clamp(dEnc.a, 0.0, 1.0);
  let keyColor  = vec3f(1.00, 0.92, 0.78);
  let fillColor = vec3f(0.55, 0.72, 0.95);
  let lit = u.ambient.rgb * aoFactor
          + keyColor  * (nDotK * u.keyDir.w  * directVis)
          + fillColor * (nDotF * u.fillDir.w * aoFactor);

  var rgb = scene.rgb * lit;

  // Specular highlight on shiny surfaces (water, polished prims). Reads
  // shinyOut from normal.a packed by the raymarch pass — 1 = shiny, 0
  // = matte. Blinn-Phong with TRUE view direction (passed as uniform
  // by JS each frame; was previously approximated as +Z which only
  // worked for panel cameras looking down -Z). Highlight tint is the
  // warm key color (sun reflection); narrow specular peak (pow 64).
  let shinyW = nEnc.a;
  if (shinyW > 0.01) {
    let viewDir = normalize(u.cameraDir.xyz);
    let halfDir = normalize(kDir + viewDir);
    let specBase = max(dot(n, halfDir), 0.0);
    let spec = pow(specBase, 64.0) * shinyW * u.keyDir.w;
    rgb = rgb + keyColor * spec * 0.85;
  }

  // Soft rim — boosts silhouette clarity for the VLM. Pulls light from
  // grazing angles (1 - n·v). Cheap and reads as a halo effect.
  if (u.ambient.w > 0.0) {
    // Reconstruct view direction from depth + screen position would need
    // invViewProj; use a proxy: where the normal is grazing relative to a
    // fixed camera-aligned axis. Here we approximate v = (0,0,1) screen-Z
    // — most panel cameras look mostly toward -Z, so n.z encodes the
    // facing factor reasonably for all 4 panels. Small inaccuracy on the
    // top panel is invisible at 128px.
    let facing = abs(n.z);
    let rim = pow(1.0 - facing, 3.0) * u.ambient.w;
    rgb += vec3f(rim);
  }

  return vec4f(rgb, 1.0);
}
`

interface LitPass {
  run(encoder: GPUCommandEncoder, destView: GPUTextureView): void
  rebindSources(scene: GPUTextureView, normal: GPUTextureView, depth: GPUTextureView): void
  setViewMode(m: 'color' | 'normal' | 'depth' | 'silhouette' | 'curvature' | 'persurface'): void
  setKeyLight(dir: Vec3, intensity: number): void
  setFillLight(dir: Vec3, intensity: number): void
  setAmbient(rgb: Vec3, rim: number): void
  setCameraDir(dir: Vec3): void
}

function createLitPass(
  device: GPUDevice,
  format: GPUTextureFormat,
  scene: GPUTextureView,
  normal: GPUTextureView,
  depth: GPUTextureView,
): LitPass {
  const shader = device.createShaderModule({ code: LIT_SHADER, label: 'modeler-lit' })
  const sampler = device.createSampler({ magFilter: 'linear', minFilter: 'linear' })

  const pipeline = device.createRenderPipeline({
    label: 'modeler-lit-pipeline',
    layout: 'auto',
    vertex:   { module: shader, entryPoint: 'vs_main' },
    fragment: { module: shader, entryPoint: 'fs_main', targets: [{ format }] },
    primitive: { topology: 'triangle-list' },
  })

  const ubo = device.createBuffer({
    size: 20 * 4,   // U is 20 floats (was 16; +1 vec4 for cameraDir)
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uData   = new Float32Array(20)
  const uDataU  = new Uint32Array(uData.buffer)
  // viewMode = 0 (lit). pads in [1..3].
  uDataU[0] = 0
  // Default lights — same vibe as the outline pass's defaults but pure
  // smooth (no banding) so the LLM gets continuous gradient signal.
  uData[4]  = -0.4; uData[5]  = 0.7; uData[6]  = 0.6;  uData[7]  = 0.85   // key
  uData[8]  =  0.5; uData[9]  = 0.3; uData[10] = -0.7; uData[11] = 0.30   // fill
  uData[12] = 0.18; uData[13] = 0.20; uData[14] = 0.24; uData[15] = 0.25  // ambient + rim
  // cameraDir default — points roughly into scene from a default camera
  // angle. JS overrides each frame via setCameraDir before lit.run().
  uData[16] = -0.5; uData[17] = -0.4; uData[18] = -0.7; uData[19] = 0.0

  let curScene = scene, curNormal = normal, curDepth = depth
  let bindGroup = makeBindGroup()

  function makeBindGroup(): GPUBindGroup {
    return device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: curScene },
        { binding: 1, resource: curNormal },
        { binding: 2, resource: curDepth },
        { binding: 3, resource: sampler },
        { binding: 4, resource: { buffer: ubo } },
      ],
    })
  }

  function flush() {
    device.queue.writeBuffer(ubo, 0, uData)
  }
  flush()

  return {
    run(enc, dest) {
      flush()
      const pass = enc.beginRenderPass({
        label: 'modeler-lit-pass',
        colorAttachments: [{
          view: dest, loadOp: 'clear', storeOp: 'store',
          clearValue: { r: 0, g: 0, b: 0, a: 1 },
        }],
      })
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.draw(3)
      pass.end()
    },
    rebindSources(s, n, d) {
      curScene = s; curNormal = n; curDepth = d
      bindGroup = makeBindGroup()
    },
    setViewMode(m) {
      uDataU[0] = m === 'normal' ? 1 :
                  m === 'depth' ? 2 :
                  m === 'silhouette' ? 3 :
                  m === 'curvature' ? 4 :
                  m === 'persurface' ? 5 : 0
    },
    setKeyLight(dir, intensity) {
      uData[4] = dir[0]; uData[5] = dir[1]; uData[6] = dir[2]; uData[7] = intensity
    },
    setFillLight(dir, intensity) {
      uData[8] = dir[0]; uData[9] = dir[1]; uData[10] = dir[2]; uData[11] = intensity
    },
    setAmbient(rgb, rim) {
      uData[12] = rgb[0]; uData[13] = rgb[1]; uData[14] = rgb[2]; uData[15] = rim
    },
    setCameraDir(dir) {
      uData[16] = dir[0]; uData[17] = dir[1]; uData[18] = dir[2]; uData[19] = 0
    },
  }
}

// =========================================================================
// MAIN
// =========================================================================

async function main() {
  const canvas = $<HTMLCanvasElement>('canvas')
  const statsEl = $('stats')
  const statusEl = $('status-banner')
  const errorEl = $('error')

  let gpu
  try { gpu = await initGPU(canvas) }
  catch (e) {
    errorEl.style.display = 'block'
    errorEl.textContent = `WebGPU init failed: ${(e as Error).message}\n\nNeeds Chrome/Edge with WebGPU.`
    return
  }
  const { device, format, context } = gpu

  // Bone-0 identity VAT: every prim sits in world space.
  const vatData = new Float32Array(16); mat4.identity(vatData)
  const vatBuffer = device.createBuffer({
    label: 'modeler-vat', size: vatData.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(vatBuffer, 0, vatData)
  const vat: VATData = { buffer: vatBuffer, numInstances: 1, numFrames: 1 }

  // Renderer still needs a palette buffer (engine contract). Slot 0 is the
  // default material; slot 1 is a darker shade for sunken-feature contrast
  // (mortar grooves, dimple interiors, crack lines); slot 2 is a brighter
  // shade for raised-feature contrast (stud tops, ridge peaks, chevron
  // ridges). Color-aware deformers pick into 1 or 2 based on geometry.
  const initialPalette = new Float32Array(32 * 4)
  for (let i = 0; i < 32; i++) {
    initialPalette[i * 4 + 0] = MATERIAL_RGB[0]
    initialPalette[i * 4 + 1] = MATERIAL_RGB[1]
    initialPalette[i * 4 + 2] = MATERIAL_RGB[2]
    initialPalette[i * 4 + 3] = 1.0
  }
  initialPalette[1 * 4 + 0] = MATERIAL_RGB[0] * 0.55
  initialPalette[1 * 4 + 1] = MATERIAL_RGB[1] * 0.55
  initialPalette[1 * 4 + 2] = MATERIAL_RGB[2] * 0.55
  initialPalette[2 * 4 + 0] = Math.min(1, MATERIAL_RGB[0] * 1.45)
  initialPalette[2 * 4 + 1] = Math.min(1, MATERIAL_RGB[1] * 1.45)
  initialPalette[2 * 4 + 2] = Math.min(1, MATERIAL_RGB[2] * 1.45)
  // Slot 3 = water-blue, by convention used by the terrain deformer
  // (colorFunc=28) when a cell's heightmap altitude is below the
  // scene-wide terrainWaterLevel uniform. Authors override slot 3 to
  // get different water colors (lava red, acid green, etc.).
  initialPalette[3 * 4 + 0] = 0.20
  initialPalette[3 * 4 + 1] = 0.45
  initialPalette[3 * 4 + 2] = 0.65
  // Slot 4 = rock-grey, by convention used by colorFunc=28 when a cell
  // exceeds the slope threshold (steep — exposed rock face, no soil).
  // Slightly darker and warmer than the base material.
  initialPalette[4 * 4 + 0] = 0.42
  initialPalette[4 * 4 + 1] = 0.40
  initialPalette[4 * 4 + 2] = 0.38
  // Slot 5 = forest-green, by convention used by terrain vegetation
  // scatter prims. Authors override slot 5 to get autumn (orange),
  // pine (dark green), savanna (yellow), or alien (purple) foliage.
  initialPalette[5 * 4 + 0] = 0.18
  initialPalette[5 * 4 + 1] = 0.36
  initialPalette[5 * 4 + 2] = 0.16
  // Slot 6 = foam white, by convention used by terrain colorFunc=28 in
  // the thin band right around waterLevel. Coastlines and shores read
  // as a bright halo separating water from land. Authors override for
  // sandy shore (yellow-tan) or muddy delta (brown).
  initialPalette[6 * 4 + 0] = 0.92
  initialPalette[6 * 4 + 1] = 0.94
  initialPalette[6 * 4 + 2] = 0.97
  // Slot 7 = shallow water teal (lighter + greener than slot 3 deep
  // water). Used by terrain colorFunc=28 in the shallow zone (cells
  // 0.05-0.15 below waterLevel — between the foam band and deep water).
  // Gives real depth gradient: pale teal near shore → deep blue offshore.
  initialPalette[7 * 4 + 0] = 0.34
  initialPalette[7 * 4 + 1] = 0.62
  initialPalette[7 * 4 + 2] = 0.70
  // Slot 8 = dark pine green. Used by vegetation scatter for variety —
  // 18% of scatter prims pick this slot to break the uniform forest.
  initialPalette[8 * 4 + 0] = 0.10
  initialPalette[8 * 4 + 1] = 0.24
  initialPalette[8 * 4 + 2] = 0.10
  // Slot 9 = olive / yellow-green. Used by vegetation scatter — 8% of
  // prims; reads as autumn or arid grass.
  initialPalette[9 * 4 + 0] = 0.40
  initialPalette[9 * 4 + 1] = 0.40
  initialPalette[9 * 4 + 2] = 0.18
  // Slot 10 = brown/dead. Used by vegetation scatter — 4% of prims;
  // reads as bare branches, dead trees, dirt patches.
  initialPalette[10 * 4 + 0] = 0.30
  initialPalette[10 * 4 + 1] = 0.20
  initialPalette[10 * 4 + 2] = 0.12
  // Slot 11 = cloud-underside light gray-blue. Used by colorFunc=29
  // when the billow density dips below the dither-shadow threshold —
  // gives clouds a subtle shadowed look instead of harsh dark-grey.
  initialPalette[11 * 4 + 0] = 0.78
  initialPalette[11 * 4 + 1] = 0.83
  initialPalette[11 * 4 + 2] = 0.90
  const placeholder: RaymarchPrimitive[] = [{
    type: 0, paletteSlot: 0, boneIdx: 0,
    params: [0.0001, 0, 0, 0], offsetInBone: [0, -1000, 0],
  }]
  const raymarch = createRaymarchRenderer(device, format, placeholder, initialPalette, vat, { maxSteps: 96 })

  // Mode: agent (default, 2x2 ortho atlas) or human (single orbiting view).
  // Agent first because authoring is mostly LLM-driven; human mode toggles
  // on for manual inspection / orbit drag.
  type DisplayMode = 'agent' | 'human'
  let displayMode: DisplayMode = 'agent'

  // Per-panel resolution. Atlas (agent mode) is 2×renderRes × 2×renderRes.
  // Single-view (human mode, used by screenshotView) renders at renderRes.
  // 256 → 512² atlas / 256² single. Cheap enough that the daemon does not
  // contend hard for the GPU.
  let renderRes = 256

  /** Per-frame view+proj matrices for the agent atlas. Computed each frame
   *  because scene bounds (and thus distance) can change as the spec is
   *  edited. Reused across frames to avoid allocation churn. */
  const atlasView = new Float32Array(16)
  const atlasProj = new Float32Array(16)

  // Forward-declared so ensureMRT's closure can rebind it once it exists.
  let lit: LitPass | null = null

  // G-buffer (3 color attachments + 1 depth-stencil for the raymarch pass).
  // All three color textures need TEXTURE_BINDING so the outline pass can
  // sample them; depth-stencil is internal to raymarch only.
  let sceneTex:  GPUTexture | null = null
  let normalTex: GPUTexture | null = null
  let depthTex:  GPUTexture | null = null
  let depthStencilTex: GPUTexture | null = null
  let sceneView:  GPUTextureView | null = null
  let normalView: GPUTextureView | null = null
  let depthView:  GPUTextureView | null = null
  let depthStencilView: GPUTextureView | null = null
  let lastW = 0, lastH = 0
  function ensureMRT(w: number, h: number) {
    if (w === lastW && h === lastH && normalTex) return
    sceneTex?.destroy(); normalTex?.destroy(); depthTex?.destroy(); depthStencilTex?.destroy()
    const gbufUsage = GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING
    sceneTex   = device.createTexture({ label: 'modeler-scene',  size: [w, h], format, usage: gbufUsage })
    normalTex  = device.createTexture({ label: 'modeler-normal', size: [w, h], format, usage: gbufUsage })
    depthTex   = device.createTexture({ label: 'modeler-depth',  size: [w, h], format, usage: gbufUsage })
    depthStencilTex = device.createTexture({ label: 'modeler-ds', size: [w, h], format: 'depth24plus-stencil8', usage: GPUTextureUsage.RENDER_ATTACHMENT })
    sceneView  = sceneTex.createView()
    normalView = normalTex.createView()
    depthView  = depthTex.createView()
    depthStencilView = depthStencilTex.createView()
    lastW = w; lastH = h
    if (lit) lit.rebindSources(sceneView, normalView, depthView)
  }

  // Pre-allocate at boot so the lit pass has views to bind to.
  ensureMRT(renderRes, renderRes)
  lit = createLitPass(device, format, sceneView!, normalView!, depthView!)
  lit.setKeyLight([-0.4, 0.7, 0.6], 0.85)
  lit.setFillLight([0.5, 0.3, -0.7], 0.30)
  lit.setAmbient([0.18, 0.20, 0.24], 0.25)

  // Camera
  const camera = new Camera({
    mode: 'perspective', fov: 35, near: 0.01, far: 50,
    position: [0.4, 0.3, 0.7], target: [0, 0, 0],
    controls: 'orbit',
  })
  camera.setAspect(canvas.width || 512, canvas.height || 512)
  camera.update()

  // Boot in agent mode → auto-orbit off (atlas is fixed views).
  // Toggling to human mode flips this on; user can still pause via UI.
  let autoOrbit = false
  let dragging = false, dragLastX = 0, dragLastY = 0
  canvas.addEventListener('mousedown', (e) => {
    dragging = true; dragLastX = e.clientX; dragLastY = e.clientY
    autoOrbit = false; setSpinUI()
  })
  window.addEventListener('mouseup', () => { dragging = false })
  window.addEventListener('mousemove', (e) => {
    if (!dragging) return
    const dx = e.clientX - dragLastX, dy = e.clientY - dragLastY
    dragLastX = e.clientX; dragLastY = e.clientY
    camera.orbitRotate(-dx * 0.01, -dy * 0.01)
  })
  canvas.addEventListener('wheel', (e) => {
    e.preventDefault()
    camera.orbitZoom(e.deltaY * 0.001)
  }, { passive: false })
  canvas.addEventListener('dblclick', () => setView('iso'))

  function setView(name: 'iso'|'front'|'side'|'top'|'back') {
    const presets: Record<string, [number, number]> = {
      iso:   [Math.PI * 0.25,  Math.PI * 0.20],
      front: [0,               0],
      back:  [Math.PI,         0],
      side:  [Math.PI * 0.5,   0],
      top:   [0,               Math.PI * 0.45],
    }
    const orbit = camera.getOrbitAngles()
    const [yaw, pitch] = presets[name] ?? [orbit.yaw, orbit.pitch]
    camera.setOrbitAngles(yaw, pitch)
  }

  /** Axis-aligned scene bbox center + extent. Used by both fit + atlas. */
  function specBounds(s: ModelerSpec): { center: Vec3; extent: number } {
    if (!s.primitives.length) return { center: [0, 0, 0], extent: 0.1 }
    let minX = Infinity, minY = Infinity, minZ = Infinity
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
    for (const p of s.primitives) {
      const meta = TYPE_META[p.type]
      let r = 0
      for (let i = 0; i < meta.params.length; i++) {
        if (meta.params[i].isSize) r = Math.max(r, Math.abs(p.params[i]))
      }
      r = Math.max(r, 0.02)
      const [cx, cy, cz] = p.pos
      minX = Math.min(minX, cx - r); maxX = Math.max(maxX, cx + r)
      minY = Math.min(minY, cy - r); maxY = Math.max(maxY, cy + r)
      minZ = Math.min(minZ, cz - r); maxZ = Math.max(maxZ, cz + r)
    }
    return {
      center: [(minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2],
      extent: Math.max(maxX - minX, maxY - minY, maxZ - minZ),
    }
  }

  function fitCameraToSpec(s: ModelerSpec) {
    const { center, extent } = specBounds(s)
    camera.target = [center[0], center[1], center[2]]
    const dist = Math.max(0.25, extent * 2.0)
    ;(camera as unknown as { orbitDistance: number }).orbitDistance = dist
    const o = camera.getOrbitAngles()
    camera.setOrbitAngles(o.yaw, o.pitch)
  }

  // ------------------------------------------------------------------
  // STATE
  // ------------------------------------------------------------------
  let spec: ModelerSpec = loadFromStorage() ?? demoSpec()
  let selectedIdx = -1

  function loadFromStorage(): ModelerSpec | null {
    try {
      const txt = localStorage.getItem(STORAGE_KEY)
      if (!txt) return null
      const obj = JSON.parse(txt) as Partial<ModelerSpec>
      if (!obj || obj.version !== 1) return null
      return normalizeSpec(obj as ModelerSpec)
    } catch { return null }
  }
  function saveToStorage() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(spec)) } catch { /* quota */ }
  }
  function normalizeSpec(s: ModelerSpec): ModelerSpec {
    const primitives: ModelerPrim[] = (s.primitives ?? []).map((p) => {
      const type = (TYPE_META[p.type] ? p.type : 'sphere') as PrimType
      const meta = TYPE_META[type]
      const params: Vec4 = [
        p.params?.[0] ?? meta.defaults[0],
        p.params?.[1] ?? meta.defaults[1],
        p.params?.[2] ?? meta.defaults[2],
        p.params?.[3] ?? meta.defaults[3],
      ]
      const norm: ModelerPrim = {
        id: p.id || newId(type),
        type,
        pos: [p.pos?.[0] ?? 0, p.pos?.[1] ?? 0, p.pos?.[2] ?? 0],
        params,
        rotationDeg: [p.rotationDeg?.[0] ?? 0, p.rotationDeg?.[1] ?? 0, p.rotationDeg?.[2] ?? 0],
        blendGroup: p.blendGroup ?? 1,
        blendRadius: p.blendRadius ?? 0.01,
        chamfer: !!p.chamfer,
        mirrorYZ: !!p.mirrorYZ,
      }
      if (p.tipDelta) norm.tipDelta = [p.tipDelta[0] ?? 0, p.tipDelta[1] ?? 0, p.tipDelta[2] ?? 0]
      if (typeof p.detailAmplitude === 'number' && p.detailAmplitude > 0) {
        norm.detailAmplitude = p.detailAmplitude
      }
      if (typeof p.crackDepth === 'number' && p.crackDepth > 0) {
        norm.crackDepth = p.crackDepth
        if (typeof p.crackDensity === 'number') norm.crackDensity = p.crackDensity
      }
      if (typeof p.pitDepth === 'number' && p.pitDepth > 0) {
        norm.pitDepth = p.pitDepth
        if (typeof p.pitDensity === 'number') norm.pitDensity = p.pitDensity
      }
      if (typeof p.bumpDepth === 'number' && p.bumpDepth > 0) {
        norm.bumpDepth = p.bumpDepth
        if (typeof p.bumpDensity === 'number') norm.bumpDensity = p.bumpDensity
      }
      if (typeof p.scaleDepth === 'number' && p.scaleDepth > 0) {
        norm.scaleDepth = p.scaleDepth
        if (typeof p.scaleDensity === 'number') norm.scaleDensity = p.scaleDensity
      }
      if (typeof p.grainDepth === 'number' && p.grainDepth > 0) {
        norm.grainDepth = p.grainDepth
        if (typeof p.grainDensity === 'number') norm.grainDensity = p.grainDensity
      }
      if (typeof p.ridgeDepth === 'number' && p.ridgeDepth > 0) {
        norm.ridgeDepth = p.ridgeDepth
        if (typeof p.ridgeDensity === 'number') norm.ridgeDensity = p.ridgeDensity
      }
      if (typeof p.streakDepth === 'number' && p.streakDepth > 0) {
        norm.streakDepth = p.streakDepth
        if (typeof p.streakDensity === 'number') norm.streakDensity = p.streakDensity
      }
      if (typeof p.hexDepth === 'number' && p.hexDepth > 0) {
        norm.hexDepth = p.hexDepth
        if (typeof p.hexDensity === 'number') norm.hexDensity = p.hexDensity
      }
      if (typeof p.brickDepth === 'number' && p.brickDepth > 0) {
        norm.brickDepth = p.brickDepth
        if (typeof p.brickDensity === 'number') norm.brickDensity = p.brickDensity
      }
      if (typeof p.voronoiCrackDepth === 'number' && p.voronoiCrackDepth > 0) {
        norm.voronoiCrackDepth = p.voronoiCrackDepth
        if (typeof p.voronoiCrackDensity === 'number') norm.voronoiCrackDensity = p.voronoiCrackDensity
      }
      if (typeof p.scratchDepth === 'number' && p.scratchDepth > 0) {
        norm.scratchDepth = p.scratchDepth
        if (typeof p.scratchDensity === 'number') norm.scratchDensity = p.scratchDensity
      }
      if (typeof p.dimpleDepth === 'number' && p.dimpleDepth > 0) {
        norm.dimpleDepth = p.dimpleDepth
        if (typeof p.dimpleDensity === 'number') norm.dimpleDensity = p.dimpleDensity
      }
      if (typeof p.studDepth === 'number' && p.studDepth > 0) {
        norm.studDepth = p.studDepth
        if (typeof p.studDensity === 'number') norm.studDensity = p.studDensity
      }
      if (typeof p.chevronDepth === 'number' && p.chevronDepth > 0) {
        norm.chevronDepth = p.chevronDepth
        if (typeof p.chevronDensity === 'number') norm.chevronDensity = p.chevronDensity
      }
      if (typeof p.whorlDepth === 'number' && p.whorlDepth > 0) {
        norm.whorlDepth = p.whorlDepth
        if (typeof p.whorlDensity === 'number') norm.whorlDensity = p.whorlDensity
      }
      if (typeof p.fishscaleDepth === 'number' && p.fishscaleDepth > 0) {
        norm.fishscaleDepth = p.fishscaleDepth
        if (typeof p.fishscaleDensity === 'number') norm.fishscaleDensity = p.fishscaleDensity
      }
      if (typeof p.cloudDepth === 'number' && p.cloudDepth > 0) {
        norm.cloudDepth = p.cloudDepth
        if (typeof p.cloudDensity === 'number') norm.cloudDensity = p.cloudDensity
      }
      if (typeof p.terrainDepth === 'number' && p.terrainDepth > 0) {
        norm.terrainDepth = p.terrainDepth
        if (typeof p.terrainDensity === 'number') norm.terrainDensity = p.terrainDensity
        if (p.terrainGen === 'fbm' || p.terrainGen === 'ridged' || p.terrainGen === 'eroded-fbm' || p.terrainGen === 'eroded-ridged' || p.terrainGen === 'diamond-square' || p.terrainGen === 'eroded-diamond' || p.terrainGen === 'voronoi') norm.terrainGen = p.terrainGen
        if (typeof p.voronoiSeedCount === 'number') norm.voronoiSeedCount = p.voronoiSeedCount | 0
        if (typeof p.terrainOctaves === 'number') norm.terrainOctaves = p.terrainOctaves | 0
        if (typeof p.terrainPersistence === 'number') norm.terrainPersistence = p.terrainPersistence
        if (typeof p.terrainLacunarity === 'number') norm.terrainLacunarity = p.terrainLacunarity
        if (typeof p.terrainSeed === 'number') norm.terrainSeed = p.terrainSeed | 0
        if (typeof p.terrainErosionIters === 'number') norm.terrainErosionIters = p.terrainErosionIters | 0
        if (typeof p.terrainWaterLevel === 'number') norm.terrainWaterLevel = p.terrainWaterLevel
        if (typeof p.terrainFlowDepth === 'number') norm.terrainFlowDepth = p.terrainFlowDepth
        if (typeof p.terrainWindIters === 'number') norm.terrainWindIters = p.terrainWindIters | 0
        if (typeof p.terrainWindAngle === 'number') norm.terrainWindAngle = p.terrainWindAngle
        if (typeof p.terrainWindStrength === 'number') norm.terrainWindStrength = p.terrainWindStrength
        if (typeof p.terrainHydraulicDroplets === 'number') norm.terrainHydraulicDroplets = p.terrainHydraulicDroplets | 0
        if (typeof p.terrainHydraulicSteps === 'number') norm.terrainHydraulicSteps = p.terrainHydraulicSteps | 0
        if (typeof p.terrainScatterCount === 'number') norm.terrainScatterCount = p.terrainScatterCount | 0
        if (typeof p.terrainScatterRadius === 'number') norm.terrainScatterRadius = p.terrainScatterRadius
      }
      if (typeof p.rdDepth === 'number' && p.rdDepth > 0) {
        norm.rdDepth = p.rdDepth
        if (typeof p.rdDensity === 'number') norm.rdDensity = p.rdDensity
        if (typeof p.rdFeed === 'number') norm.rdFeed = p.rdFeed
        if (typeof p.rdKill === 'number') norm.rdKill = p.rdKill
        if (typeof p.rdIterations === 'number') norm.rdIterations = p.rdIterations | 0
        if (typeof p.rdSeed === 'number') norm.rdSeed = p.rdSeed | 0
        if (typeof p.rdPreset === 'string' && p.rdPreset in RD_PRESETS) norm.rdPreset = p.rdPreset
      }
      if (typeof p.weaveDepth === 'number' && p.weaveDepth > 0) {
        norm.weaveDepth = p.weaveDepth
        if (typeof p.weaveDensity === 'number') norm.weaveDensity = p.weaveDensity
      }
      const wd = p.wearDeformer
      if (wd && typeof wd.depth === 'number' && wd.depth > 0
          && (wd.type === 'bumps' || wd.type === 'grain' || wd.type === 'streaks' || wd.type === 'scratches')) {
        norm.wearDeformer = {
          type: wd.type,
          depth: wd.depth,
          ...(typeof wd.density === 'number' ? { density: wd.density } : {}),
        }
      }
      if (typeof p.accentSlot === 'number' && p.accentSlot >= 0 && p.accentSlot < 32) {
        norm.accentSlot = p.accentSlot | 0
      }
      if (Array.isArray(p.pathCarves) && p.pathCarves.length) {
        norm.pathCarves = p.pathCarves
          .filter((c) => Array.isArray(c?.from) && Array.isArray(c?.to))
          .map((c) => ({
            from: [c.from[0] || 0, c.from[1] || 0, c.from[2] || 0] as Vec3,
            to: [c.to[0] || 0, c.to[1] || 0, c.to[2] || 0] as Vec3,
            ...(typeof c.thickness === 'number' ? { thickness: c.thickness } : {}),
            ...(typeof c.depth === 'number' ? { depth: c.depth } : {}),
            ...(c.raise === true ? { raise: true } : {}),
            ...(c.kind === 'joint' ? { kind: 'joint' as const } : {}),
          }))
        if (!norm.pathCarves.length) delete norm.pathCarves
      }
      if (p.crackPathGen && Array.isArray(p.crackPathGen.start) && Array.isArray(p.crackPathGen.end)) {
        const g = p.crackPathGen
        norm.crackPathGen = {
          start: [g.start[0] || 0, g.start[1] || 0, g.start[2] || 0] as Vec3,
          end:   [g.end[0]   || 0, g.end[1]   || 0, g.end[2]   || 0] as Vec3,
          ...(g.mode === 'astar' || g.mode === 'walk' || g.mode === 'lightning' || g.mode === 'tree' || g.mode === 'tendril' ? { mode: g.mode } : {}),
          ...(typeof g.segments === 'number' ? { segments: g.segments } : {}),
          ...(typeof g.seed === 'number' ? { seed: g.seed } : {}),
          ...(typeof g.branchiness === 'number' ? { branchiness: g.branchiness } : {}),
          ...(typeof g.gridRes === 'number' ? { gridRes: g.gridRes } : {}),
          ...(typeof g.noiseWeight === 'number' ? { noiseWeight: g.noiseWeight } : {}),
          ...(typeof g.thickness === 'number' ? { thickness: g.thickness } : {}),
          ...(typeof g.depth === 'number' ? { depth: g.depth } : {}),
          ...(g.profile === 'crack' || g.profile === 'river' || g.profile === 'channel' ? { profile: g.profile } : {}),
          ...(typeof g.meander === 'number' ? { meander: g.meander } : {}),
          ...(typeof g.meanderFreq === 'number' ? { meanderFreq: g.meanderFreq } : {}),
          ...(typeof g.taper === 'number' ? { taper: g.taper } : {}),
          ...(typeof g.lightningDepth === 'number' ? { lightningDepth: g.lightningDepth } : {}),
          ...(typeof g.jaggedness === 'number' ? { jaggedness: g.jaggedness } : {}),
          ...(Array.isArray(g.direction) ? { direction: [g.direction[0]||0, g.direction[1]||0, g.direction[2]||0] as Vec3 } : {}),
          ...(typeof g.length === 'number' ? { length: g.length } : {}),
          ...(typeof g.branchAngle === 'number' ? { branchAngle: g.branchAngle } : {}),
          ...(typeof g.lengthDecay === 'number' ? { lengthDecay: g.lengthDecay } : {}),
          ...(typeof g.thicknessDecay === 'number' ? { thicknessDecay: g.thicknessDecay } : {}),
          ...(typeof g.branches === 'number' ? { branches: g.branches } : {}),
          ...(typeof g.treeDepth === 'number' ? { treeDepth: g.treeDepth } : {}),
          ...(typeof g.tendrilSteps === 'number' ? { tendrilSteps: g.tendrilSteps } : {}),
          ...(typeof g.curlIntensity === 'number' ? { curlIntensity: g.curlIntensity } : {}),
          ...(g.metric === 'manhattan' || g.metric === 'chebyshev' || g.metric === 'euclidean' ? { metric: g.metric } : {}),
          ...(g.raise === true ? { raise: true } : {}),
          ...(typeof g.astarBranches === 'number' ? { astarBranches: g.astarBranches } : {}),
          ...(typeof g.endCaps === 'boolean' ? { endCaps: g.endCaps } : {}),
        }
      }
      if (p.repeats && Array.isArray(p.repeats)) {
        const axisOK = (a: unknown): a is 'x'|'y'|'z' => a === 'x' || a === 'y' || a === 'z'
        norm.repeats = p.repeats
          .filter((r): r is NonNullable<ModelerPrim['repeats']>[number] => {
            if (!r) return false
            if ((r as { kind?: string }).kind === 'brickGrid') {
              const br = r as { rowAxis?: unknown; colAxis?: unknown; rows?: number; cols?: number }
              return axisOK(br.rowAxis) && axisOK(br.colAxis) && (br.rows ?? 0) >= 1 && (br.cols ?? 0) >= 1
            }
            if ((r as { kind?: string }).kind === 'chainLinkGrid') {
              const cl = r as { rowAxis?: unknown; colAxis?: unknown; rotAxis?: unknown; rows?: number; cols?: number }
              return axisOK(cl.rowAxis) && axisOK(cl.colAxis) && axisOK(cl.rotAxis) && (cl.rows ?? 0) >= 1 && (cl.cols ?? 0) >= 1
            }
            if ((r as { kind?: string }).kind === 'spline') {
              const sp = r as { controlPoints?: unknown; count?: number }
              return Array.isArray(sp.controlPoints) && sp.controlPoints.length >= 4 && (sp.count ?? 0) >= 1
            }
            return axisOK((r as { axis?: unknown }).axis) && (r as { count?: number }).count! > 1
          })
          .map((r) => {
            if ((r as { kind?: string }).kind === 'brickGrid') {
              const br = r as { rowAxis: 'x'|'y'|'z'; colAxis: 'x'|'y'|'z';
                rows: number; cols: number; rowSpacing?: number; colSpacing?: number; stagger?: number }
              return {
                kind: 'brickGrid' as const,
                rowAxis: br.rowAxis, colAxis: br.colAxis,
                rows: Math.max(1, br.rows|0), cols: Math.max(1, br.cols|0),
                rowSpacing: br.rowSpacing ?? 0.01, colSpacing: br.colSpacing ?? 0.01,
                ...(typeof br.stagger === 'number' ? { stagger: br.stagger } : {}),
              }
            }
            if ((r as { kind?: string }).kind === 'chainLinkGrid') {
              const cl = r as { rowAxis: 'x'|'y'|'z'; colAxis: 'x'|'y'|'z'; rotAxis: 'x'|'y'|'z';
                rows: number; cols: number; rowSpacing?: number; colSpacing?: number }
              return {
                kind: 'chainLinkGrid' as const,
                rowAxis: cl.rowAxis, colAxis: cl.colAxis, rotAxis: cl.rotAxis,
                rows: Math.max(1, cl.rows|0), cols: Math.max(1, cl.cols|0),
                rowSpacing: cl.rowSpacing ?? 0.01, colSpacing: cl.colSpacing ?? 0.01,
              }
            }
            if ((r as { kind?: string }).kind === 'spline') {
              const sp = r as { controlPoints: [number, number, number][]; count: number; taper?: number; alignAxis?: 'x'|'y'|'z' }
              return {
                kind: 'spline' as const,
                controlPoints: sp.controlPoints.map((p): [number, number, number] => [p[0], p[1], p[2]]),
                count: Math.max(1, sp.count|0),
                ...(typeof sp.taper === 'number' ? { taper: sp.taper } : {}),
                ...(sp.alignAxis ? { alignAxis: sp.alignAxis } : {}),
              }
            }
            const lr = r as { axis: 'x'|'y'|'z'; count: number; spacing?: number; kind?: string }
            if (lr.kind === 'rotational') {
              return { kind: 'rotational' as const, axis: lr.axis, count: Math.max(2, lr.count|0) }
            }
            if (lr.kind === 'linkChain') {
              return { kind: 'linkChain' as const, axis: lr.axis, count: Math.max(2, lr.count|0), spacing: lr.spacing || 0.01 }
            }
            return { axis: lr.axis, count: Math.max(2, lr.count|0), spacing: lr.spacing || 0.01 }
          })
        if (!norm.repeats.length) delete norm.repeats
      }
      return norm
    })
    return { version: 1, name: s.name || 'untitled', primitives }
  }
  function uploadPrims() {
    const prims = specToPrims(spec)
    if (!prims.length) {
      raymarch.setPrimitives([{
        type: 0, paletteSlot: 0, boneIdx: 0,
        params: [0.0001, 0, 0, 0], offsetInBone: [0, -1000, 0],
      }])
    } else {
      raymarch.setPrimitives(prims)
    }
    // RD bake: scan spec for the first prim with rdDepth > 0 and bake its
    // (F, k, iterations, seed). One field shared scene-wide. Skipped (no
    // upload) when no RD prims exist — the renderer's default-zero buffer
    // keeps the binding valid.
    const terrainPrim = spec.primitives.find((p) => typeof p.terrainDepth === 'number' && p.terrainDepth > 0)
    if (terrainPrim) {
      raymarch.setTerrainWaterLevel(terrainPrim.terrainWaterLevel ?? 0)
      raymarch.setBgMode('sky')
    } else {
      raymarch.setTerrainWaterLevel(0)
      raymarch.setBgMode('transparent')
    }
    const rdPrim = spec.primitives.find((p) => typeof p.rdDepth === 'number' && p.rdDepth > 0)
    if (rdPrim) {
      // Resolve preset → (F, k); explicit rdFeed/rdKill always win over preset.
      const presetFK = rdPrim.rdPreset ? RD_PRESETS[rdPrim.rdPreset] : undefined
      const F = rdPrim.rdFeed ?? presetFK?.[0] ?? 0.055
      const k = rdPrim.rdKill ?? presetFK?.[1] ?? 0.062
      const field = bakeReactionDiffusion({
        feed: F,
        kill: k,
        iterations: rdPrim.rdIterations ?? 2000,
        seed: rdPrim.rdSeed ?? 1,
      })
      raymarch.setRDField(field)
    }
  }

  function rebuildAll(opts: { fitCamera?: boolean } = {}) {
    uploadPrims()
    if (opts.fitCamera) fitCameraToSpec(spec)
    renderUI()
    saveToStorage()
    scheduleAutosave()
    statusEl.textContent = `${spec.primitives.length} prim${spec.primitives.length === 1 ? '' : 's'} - "${spec.name}"`
    statusEl.className = 'fresh'
  }

  // ------------------------------------------------------------------
  // VISION SCRATCHPAD — every spec change autosaves the atlas + spec
  // to public/sdf_modeler/{live.png, live.json} so an external agent can
  // read the latest state without a round-trip through the page. Debounced
  // 200ms so a flurry of slider drags doesn't hammer the disk.
  // ------------------------------------------------------------------
  let autosaveTimer: number | null = null
  let autosaveBusy = false
  function scheduleAutosave() {
    if (autosaveTimer != null) clearTimeout(autosaveTimer)
    autosaveTimer = window.setTimeout(runAutosave, 200)
  }
  async function runAutosave() {
    autosaveTimer = null
    if (autosaveBusy) { scheduleAutosave(); return }    // skip if a prior save is mid-flight
    // Always autosave so the agent loop stays alive when user toggles human
    // mode. screenshotAtlas() temporarily flips to agent mode (1-frame flicker
    // in human mode) and restores. Cheap; can revisit with offscreen RT later.
    autosaveBusy = true
    try {
      const url = await api.screenshotAtlas()
      await fetch('/__modeler/save_image', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'live.png', dataUrl: url }),
      })
      await fetch('/__modeler/save_spec', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'live.json', spec: api.getSpec() }),
      })
    } catch { /* dev-server may be down; silent */ }
    autosaveBusy = false
  }

  // ------------------------------------------------------------------
  // UI: PRIM LIST
  // ------------------------------------------------------------------
  function renderPrimList() {
    const root = $('prim-list')
    clearNode(root)
    $('prim-count').textContent = `(${spec.primitives.length})`
    if (!spec.primitives.length) {
      root.appendChild(el('div', { text: 'empty - add a primitive below', style: { padding: '8px', color: '#6a7585', textAlign: 'center', fontStyle: 'italic' }}))
      return
    }
    spec.primitives.forEach((p, i) => {
      const row = el('div', { class: 'prim-row' + (i === selectedIdx ? ' sel' : '') })
      row.appendChild(el('span', { class: 'badge', text: TYPE_META[p.type].display.split(' ')[0] }))
      row.appendChild(el('span', { class: 'name', text: p.id }))
      const flags: string[] = []
      if (p.chamfer) flags.push('CH')
      if (p.mirrorYZ) flags.push('MX')
      if (p.blendGroup > 0) flags.push(`G${p.blendGroup}`)
      if (p.blendRadius < 0) flags.push('SUB')
      if (flags.length) row.appendChild(el('span', { class: 'flags', text: flags.join(' ') }))
      row.onclick = () => { selectedIdx = i; renderUI() }
      root.appendChild(row)
    })
  }

  // ------------------------------------------------------------------
  // UI: SELECTED PRIM EDITOR
  // ------------------------------------------------------------------
  function renderEditor() {
    const root = $('editor')
    clearNode(root)
    if (selectedIdx < 0 || selectedIdx >= spec.primitives.length) {
      root.className = 'empty'
      root.textContent = 'select a primitive above'
      return
    }
    root.className = ''
    const p = spec.primitives[selectedIdx]
    const meta = TYPE_META[p.type]

    // ID + type
    {
      const row = el('div', { class: 'field' })
      row.appendChild(el('label', { text: 'id' }))
      const idIn = el('input') as HTMLInputElement
      idIn.type = 'text'; idIn.value = p.id
      idIn.onchange = () => { p.id = idIn.value || p.id; rebuildAll() }
      ;(idIn.style as Record<string, string>).gridColumn = '2 / 4'
      row.appendChild(idIn)
      root.appendChild(row)
    }
    {
      const row = el('div', { class: 'field' })
      row.appendChild(el('label', { text: 'type' }))
      const sel = el('select') as HTMLSelectElement
      ;(sel.style as Record<string, string>).gridColumn = '2 / 4'
      for (const t of TYPE_ORDER) {
        const o = el('option') as HTMLOptionElement
        o.value = t; o.textContent = TYPE_META[t].display
        if (t === p.type) o.selected = true
        sel.appendChild(o)
      }
      sel.onchange = () => {
        const newType = sel.value as PrimType
        if (newType === p.type) return
        p.type = newType
        p.params = [...TYPE_META[newType].defaults] as Vec4
        rebuildAll()
      }
      row.appendChild(sel)
      root.appendChild(row)
    }

    addVec3Field(root, 'pos',  p.pos,         -1, 1, 0.001, () => rebuildAll())
    addVec3Field(root, 'rot d', p.rotationDeg, -180, 180, 1, () => rebuildAll())

    meta.params.forEach((pd, i) => {
      addScalarField(root, pd.label, p.params[i], pd.min, pd.max, pd.step, (v) => {
        p.params[i] = v; rebuildAll()
      })
    })

    addScalarField(root, 'group',   p.blendGroup,   0, 15, 1,    (v) => { p.blendGroup = v|0; rebuildAll() })
    addScalarField(root, 'blend r', p.blendRadius, -0.1, 0.1, 0.001, (v) => { p.blendRadius = v; rebuildAll() })

    const flagRow = el('div', { class: 'checkbox-row' })
    flagRow.appendChild(checkbox('chamfer',  p.chamfer,  (v) => { p.chamfer = v; rebuildAll() }))
    flagRow.appendChild(checkbox('mirror x', p.mirrorYZ, (v) => { p.mirrorYZ = v; rebuildAll() }))
    root.appendChild(flagRow)
  }

  function addVec3Field(
    root: HTMLElement, label: string, v: Vec3,
    min: number, max: number, step: number, onChange: () => void,
  ) {
    const row = el('div', { class: 'field' })
    row.appendChild(el('label', { text: label }))
    const grid = el('div', { class: 'vec' })
    for (let i = 0; i < 3; i++) {
      const inp = el('input') as HTMLInputElement
      inp.type = 'number'; inp.min = String(min); inp.max = String(max); inp.step = String(step)
      inp.value = (Math.round(v[i] * 1000) / 1000).toString()
      inp.oninput = () => {
        const x = parseFloat(inp.value); if (!Number.isFinite(x)) return
        v[i] = x; onChange()
      }
      grid.appendChild(inp)
    }
    row.appendChild(grid)
    root.appendChild(row)
  }

  function addScalarField(
    root: HTMLElement, label: string, value: number,
    min: number, max: number, step: number, onChange: (v: number) => void,
  ) {
    const row = el('div', { class: 'field' })
    row.appendChild(el('label', { text: label }))
    const slider = el('input') as HTMLInputElement
    slider.type = 'range'; slider.min = String(min); slider.max = String(max); slider.step = String(step)
    slider.value = String(value)
    const num = el('input') as HTMLInputElement
    num.type = 'number'; num.min = String(min); num.max = String(max); num.step = String(step)
    num.value = (Math.round(value * 1000) / 1000).toString()
    slider.oninput = () => {
      const v = parseFloat(slider.value); num.value = (Math.round(v * 1000) / 1000).toString()
      onChange(v)
    }
    num.oninput = () => {
      const v = parseFloat(num.value); if (!Number.isFinite(v)) return
      slider.value = String(v); onChange(v)
    }
    row.appendChild(slider); row.appendChild(num)
    root.appendChild(row)
  }

  function checkbox(label: string, value: boolean, onChange: (v: boolean) => void): HTMLLabelElement {
    const wrap = el('label')
    const cb = el('input') as HTMLInputElement
    cb.type = 'checkbox'; cb.checked = value
    cb.onchange = () => onChange(cb.checked)
    wrap.appendChild(cb)
    wrap.appendChild(document.createTextNode(label))
    return wrap
  }

  function renderJsonOut() {
    const ta = $<HTMLTextAreaElement>('json-out')
    ta.value = JSON.stringify(spec, null, 2)
  }

  function renderUI() {
    renderPrimList()
    renderEditor()
    renderJsonOut()
    ;($('btn-dup') as HTMLButtonElement).disabled = selectedIdx < 0
    ;($('btn-del') as HTMLButtonElement).disabled = selectedIdx < 0
    ;($('model-name') as HTMLInputElement).value = spec.name
  }

  // ------------------------------------------------------------------
  // ACTIONS / TOOL API
  // ------------------------------------------------------------------
  const api = {
    setSpec(s: Partial<ModelerSpec>) {
      spec = normalizeSpec(s as ModelerSpec)
      selectedIdx = spec.primitives.length ? 0 : -1
      rebuildAll({ fitCamera: true })
      return clone(spec)
    },
    getSpec(): ModelerSpec { return clone(spec) },
    clear() {
      spec = emptySpec(); selectedIdx = -1
      rebuildAll({ fitCamera: true })
      return clone(spec)
    },
    addPrim(patch: Partial<ModelerPrim> & { type: PrimType }) {
      if (!TYPE_META[patch.type]) throw new Error(`unknown type: ${patch.type}`)
      const p = newPrim(patch.type, patch.pos)
      Object.assign(p, patch)
      if (!patch.id) p.id = newId(patch.type)
      spec.primitives.push(p)
      selectedIdx = spec.primitives.length - 1
      rebuildAll()
      return p.id
    },
    updatePrim(target: number | string, patch: Partial<ModelerPrim>) {
      const i = typeof target === 'string' ? spec.primitives.findIndex((p) => p.id === target) : target
      if (i < 0 || i >= spec.primitives.length) throw new Error(`bad prim target: ${target}`)
      const p = spec.primitives[i]
      if (patch.type && patch.type !== p.type) {
        p.params = [...TYPE_META[patch.type].defaults] as Vec4
      }
      Object.assign(p, patch)
      rebuildAll()
      return clone(p)
    },
    deletePrim(target: number | string) {
      const i = typeof target === 'string' ? spec.primitives.findIndex((p) => p.id === target) : target
      if (i < 0 || i >= spec.primitives.length) throw new Error(`bad prim target: ${target}`)
      const removed = spec.primitives.splice(i, 1)[0]
      if (selectedIdx >= spec.primitives.length) selectedIdx = spec.primitives.length - 1
      rebuildAll()
      return removed
    },
    duplicatePrim(target: number | string) {
      const i = typeof target === 'string' ? spec.primitives.findIndex((p) => p.id === target) : target
      if (i < 0 || i >= spec.primitives.length) throw new Error(`bad prim target: ${target}`)
      const src = spec.primitives[i]
      const copy: ModelerPrim = clone(src)
      copy.id = newId(copy.type)
      copy.pos = [src.pos[0] + 0.02, src.pos[1], src.pos[2]]
      spec.primitives.splice(i + 1, 0, copy)
      selectedIdx = i + 1
      rebuildAll()
      return copy.id
    },
    setCamera(opts: { yaw?: number; pitch?: number; distance?: number; target?: Vec3 }) {
      const orbit = camera.getOrbitAngles()
      const yaw = opts.yaw ?? orbit.yaw
      const pitch = opts.pitch ?? orbit.pitch
      if (opts.distance !== undefined) {
        ;(camera as unknown as { orbitDistance: number }).orbitDistance = opts.distance
      }
      if (opts.target) camera.target = [opts.target[0], opts.target[1], opts.target[2]]
      camera.setOrbitAngles(yaw, pitch)
      autoOrbit = false; setSpinUI()
    },
    fitView() { fitCameraToSpec(spec) },
    pause() { autoOrbit = false; setSpinUI() },
    resume() { autoOrbit = true; setSpinUI() },
    /** Capture the canvas as a PNG dataURL using the current view mode. */
    async screenshot(): Promise<string> {
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      return canvas.toDataURL('image/png')
    },
    /** Switch display mode. Agent = 2x2 ortho atlas (default). Human = single
     *  orbiting view. Returns the new mode. */
    setMode(m: DisplayMode): DisplayMode {
      displayMode = m
      autoOrbit = m === 'human'
      setSpinUI()
      // Reflect on the UI toggle row as well.
      document.querySelectorAll('button[data-mode]').forEach((b) => {
        const btn = b as HTMLButtonElement
        btn.classList.toggle('on', btn.getAttribute('data-mode') === m)
      })
      return m
    },
    getMode(): DisplayMode { return displayMode },

    /** Render the agent atlas (front/side/top/iso in a 2x2) and return the
     *  PNG dataURL. Forces agent mode for one frame and restores. This is
     *  the recommended VLM input — measurable axis info per panel + iso
     *  vibe check. */
    async screenshotAtlas(): Promise<string> {
      const prevMode = displayMode
      const prevView = (document.querySelector('button[data-vmode].on')?.getAttribute('data-vmode') ?? 'color') as 'color' | 'normal' | 'depth'
      displayMode = 'agent'
      lit!.setViewMode('color')
      // 3 rAFs to let canvas resize, MRT rebuild, and the atlas land.
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      const url = canvas.toDataURL('image/png')
      // Restore previous state.
      displayMode = prevMode
      lit!.setViewMode(prevView)
      return url
    },
    /** Render a SINGLE view at full canvas size. Pick angle by viewName
     *  ('front' | 'side' | 'top' | 'iso') and channel by viewMode
     *  ('color' | 'normal' | 'depth' | 'silhouette' | 'curvature' |
     *  'persurface'). Use 'normal' to inspect normal-vector continuity —
     *  any visible artifacts in normal-mode are SDF gradient discontinuities. */
    async screenshotView(viewName: 'front' | 'side' | 'top' | 'iso', viewMode: 'color' | 'normal' | 'depth' | 'silhouette' | 'curvature' | 'persurface' = 'color'): Promise<string> {
      const prevMode = displayMode
      const prevView = (document.querySelector('button[data-vmode].on')?.getAttribute('data-vmode') ?? 'color') as 'color' | 'normal' | 'depth'
      const prevAuto = autoOrbit
      const prevAngles = camera.getOrbitAngles()
      const view = ATLAS_VIEWS.find((v) => v.name === viewName) ?? ATLAS_VIEWS[3]
      autoOrbit = false
      camera.setOrbitAngles(view.yaw, view.pitch)
      displayMode = 'human'
      lit!.setViewMode(viewMode)
      // 4 rAFs to let canvas resize, camera reorient, MRT rebuild, render.
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      await new Promise((res) => requestAnimationFrame(() => res(null)))
      const url = canvas.toDataURL('image/png')
      displayMode = prevMode
      autoOrbit = prevAuto
      camera.setOrbitAngles(prevAngles.yaw, prevAngles.pitch)
      lit!.setViewMode(prevView)
      return url
    },
    /** Render an atlas-of-MRTs: a 2x2 of (color / normal / depth / depth-as-greyscale).
     *  Same panels as screenshotAtlas but with full G-buffer signals. Returns
     *  one PNG dataURL per channel — VLM can be fed all three or pick one. */
    async screenshotAtlasMRT(): Promise<{ color: string; normal: string; depth: string }> {
      const prevMode = displayMode
      const prevView = (document.querySelector('button[data-vmode].on')?.getAttribute('data-vmode') ?? 'color') as 'color' | 'normal' | 'depth'
      displayMode = 'agent'
      const out = { color: '', normal: '', depth: '' } as { color: string; normal: string; depth: string }
      for (const m of ['color', 'normal', 'depth'] as const) {
        lit!.setViewMode(m)
        await new Promise((res) => requestAnimationFrame(() => res(null)))
        await new Promise((res) => requestAnimationFrame(() => res(null)))
        out[m] = canvas.toDataURL('image/png')
      }
      displayMode = prevMode
      lit!.setViewMode(prevView)
      return out
    },
    /** Capture all three view modes (color, normal, depth) as PNG dataURLs.
     *  Each mode is rendered for two frames to ensure the swap chain settles
     *  before readout. The viewMode is restored to whatever it was set to.
     *  This is the right input for a VLM doing scene reasoning — color shows
     *  palette / silhouette, normal shows surface orientation, depth shows
     *  occlusion / scene structure. */
    async screenshotMRT(): Promise<{ color: string; normal: string; depth: string }> {
      const out = { color: '', normal: '', depth: '' }
      const modes: Array<'color' | 'normal' | 'depth'> = ['color', 'normal', 'depth']
      // Remember current selection so we can restore.
      const prev = (document.querySelector('button[data-vmode].on')?.getAttribute('data-vmode') ?? 'color') as 'color' | 'normal' | 'depth'
      for (const m of modes) {
        lit!.setViewMode(m)
        // 2 rAFs — one to flush the new viewMode, one to render with it.
        await new Promise((res) => requestAnimationFrame(() => res(null)))
        await new Promise((res) => requestAnimationFrame(() => res(null)))
        out[m] = canvas.toDataURL('image/png')
      }
      lit!.setViewMode(prev)
      return out
    },
    exportJSON(): string {
      const blob = new Blob([JSON.stringify(spec, null, 2)], { type: 'application/json' })
      return URL.createObjectURL(blob)
    },
    listTypes(): PrimType[] { return [...TYPE_ORDER] },
  }

  function setSpinUI() {
    const btn = $<HTMLButtonElement>('spin-toggle')
    btn.textContent = autoOrbit ? 'auto' : 'paused'
    btn.className = autoOrbit ? 'on' : 'off'
  }

  // ------------------------------------------------------------------
  // UI BINDINGS
  // ------------------------------------------------------------------
  {
    const sel = $<HTMLSelectElement>('add-type')
    for (const t of TYPE_ORDER) {
      const o = el('option') as HTMLOptionElement
      o.value = t; o.textContent = TYPE_META[t].display
      sel.appendChild(o)
    }
    sel.value = 'sup'
  }
  $<HTMLButtonElement>('btn-add').onclick = () => {
    const t = ($<HTMLSelectElement>('add-type').value) as PrimType
    api.addPrim({ type: t })
  }
  $<HTMLButtonElement>('btn-dup').onclick = () => {
    if (selectedIdx >= 0) api.duplicatePrim(selectedIdx)
  }
  $<HTMLButtonElement>('btn-del').onclick = () => {
    if (selectedIdx >= 0) api.deletePrim(selectedIdx)
  }
  $<HTMLButtonElement>('btn-new').onclick = () => {
    if (spec.primitives.length && !confirm('discard current model?')) return
    api.clear()
  }
  $<HTMLButtonElement>('btn-export').onclick = () => {
    const url = api.exportJSON()
    const a = el('a') as HTMLAnchorElement
    a.href = url; a.download = `${spec.name || 'model'}.json`
    document.body.appendChild(a); a.click()
    setTimeout(() => { URL.revokeObjectURL(url); a.remove() }, 100)
  }
  $<HTMLButtonElement>('btn-import').onclick = () => {
    $<HTMLInputElement>('file-input').click()
  }
  $<HTMLInputElement>('file-input').addEventListener('change', async (e) => {
    const f = (e.target as HTMLInputElement).files?.[0]
    if (!f) return
    try {
      const txt = await f.text()
      api.setSpec(JSON.parse(txt))
    } catch (err) {
      statusEl.textContent = `import error: ${(err as Error).message}`
      statusEl.className = 'error'
    }
  })
  $<HTMLButtonElement>('btn-copy').onclick = async () => {
    try { await navigator.clipboard.writeText($<HTMLTextAreaElement>('json-out').value) }
    catch { /* clipboard denied */ }
  }
  $<HTMLButtonElement>('btn-apply-json').onclick = () => {
    try { api.setSpec(JSON.parse($<HTMLTextAreaElement>('json-out').value)) }
    catch (err) {
      statusEl.textContent = `JSON error: ${(err as Error).message}`
      statusEl.className = 'error'
    }
  }
  $<HTMLInputElement>('model-name').onchange = (e) => {
    spec.name = (e.target as HTMLInputElement).value || 'untitled'
    rebuildAll()
  }
  $<HTMLButtonElement>('spin-toggle').onclick = () => { autoOrbit = !autoOrbit; setSpinUI() }
  document.querySelectorAll('button[data-view]').forEach((btn) => {
    (btn as HTMLButtonElement).onclick = () => setView(btn.getAttribute('data-view') as 'iso')
  })
  document.querySelectorAll('button[data-res]').forEach((btn) => {
    (btn as HTMLButtonElement).onclick = () => {
      renderRes = parseInt(btn.getAttribute('data-res') || '128', 10)
      document.querySelectorAll('button[data-res]').forEach((b) => (b as HTMLButtonElement).classList.remove('on'))
      ;(btn as HTMLButtonElement).classList.add('on')
    }
  })
  document.querySelectorAll('button[data-vmode]').forEach((btn) => {
    (btn as HTMLButtonElement).onclick = () => {
      const m = btn.getAttribute('data-vmode') as 'color' | 'normal' | 'depth'
      lit!.setViewMode(m)
      document.querySelectorAll('button[data-vmode]').forEach((b) => (b as HTMLButtonElement).classList.remove('on'))
      ;(btn as HTMLButtonElement).classList.add('on')
    }
  })
  function updateModeUI(m: DisplayMode) {
    const wrap = document.getElementById('canvas-wrap')
    if (wrap) wrap.classList.toggle('human-mode', m === 'human')
  }
  updateModeUI(displayMode)
  document.querySelectorAll('button[data-mode]').forEach((btn) => {
    (btn as HTMLButtonElement).onclick = () => {
      const m = btn.getAttribute('data-mode') as DisplayMode
      displayMode = m
      autoOrbit = m === 'human'   // agent mode is fixed views; human can spin
      setSpinUI()
      updateModeUI(m)
      document.querySelectorAll('button[data-mode]').forEach((b) => (b as HTMLButtonElement).classList.remove('on'))
      ;(btn as HTMLButtonElement).classList.add('on')
    }
  })

  // ------------------------------------------------------------------
  // VL inbox poll
  // ------------------------------------------------------------------
  // Default ON so the agent loop closes automatically: agent writes to
  // /sdf_modeler/inbox.ark.json, modeler picks it up + applies, autosave
  // writes /sdf_modeler/live.png. User can toggle off for manual work.
  let pollOn = true
  let pollPath = DEFAULT_POLL_PATH
  let pollTimer: number | null = null
  let lastEtag: string | null = null
  let lastBody: string | null = null

  async function pollOnce() {
    const ps = $('poll-status')
    try {
      const r = await fetch(pollPath, { cache: 'no-cache' })
      if (!r.ok) { ps.textContent = `${r.status}...`; return }
      const etag = r.headers.get('ETag') ?? r.headers.get('Last-Modified')
      const body = await r.text()
      if (etag && etag === lastEtag) { ps.textContent = `idle ${new Date().toLocaleTimeString()}`; return }
      if (!etag && body === lastBody) { ps.textContent = `idle ${new Date().toLocaleTimeString()}`; return }
      lastEtag = etag; lastBody = body
      api.setSpec(JSON.parse(body))
      ps.textContent = `applied ${new Date().toLocaleTimeString()}`
    } catch (e) { ps.textContent = `err: ${(e as Error).message}` }
  }
  function setPolling(on: boolean) {
    pollOn = on
    const btn = $<HTMLButtonElement>('poll-toggle')
    btn.textContent = on ? 'ON' : 'OFF'
    btn.className = on ? 'on' : 'off'
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    if (on) { pollOnce(); pollTimer = window.setInterval(pollOnce, POLL_MS) }
  }
  $<HTMLButtonElement>('poll-toggle').onclick = () => setPolling(!pollOn)
  $<HTMLInputElement>('poll-path').addEventListener('change', (e) => {
    pollPath = (e.target as HTMLInputElement).value.trim() || DEFAULT_POLL_PATH
    lastEtag = lastBody = null
    if (pollOn) { setPolling(false); setPolling(true) }
  })

  ;(window as unknown as { modeler: typeof api }).modeler = api

  if (selectedIdx < 0 && spec.primitives.length) selectedIdx = 0
  rebuildAll({ fitCamera: true })
  setSpinUI()
  setPolling(true)   // start the VL inbox poll so the agent loop is closed by default

  // Boot diagnostics — prints to console once so we can isolate CSS vs.
  // GPU vs. camera issues if the canvas comes up blank.
  // eslint-disable-next-line no-console
  console.log('[modeler] boot:', {
    wrapSize: { w: $('canvas-wrap').clientWidth, h: $('canvas-wrap').clientHeight },
    canvasBuffer: { w: canvas.width, h: canvas.height },
    canvasCSS: { w: canvas.clientWidth, h: canvas.clientHeight },
    primCount: spec.primitives.length,
    cameraOrbit: camera.getOrbitAngles(),
    cameraTarget: camera.target,
  })

  // ------------------------------------------------------------------
  // RENDER LOOP
  // ------------------------------------------------------------------
  let frameIdx = 0
  let firstFrameLogged = false
  const loop = new FrameLoop()

  /** Render one raymarch pass that fills a viewport, then run the outline
   *  pass over the entire G-buffer. Used for both modes — the difference
   *  is whether we run 1 or 4 raymarch passes before the outline. */
  function raymarchInto(
    enc: GPUCommandEncoder,
    view: Float32Array, proj: Float32Array, eye: [number, number, number],
    viewport: [number, number, number, number] | null,
    loadAttachments: boolean,
  ) {
    const loadOp: GPULoadOp = loadAttachments ? 'load' : 'clear'
    const dsLoad: GPULoadOp = loadAttachments ? 'load' : 'clear'
    const rmPass = enc.beginRenderPass({
      label: 'modeler-raymarch',
      colorAttachments: [
        { view: sceneView!,  loadOp, storeOp: 'store', clearValue: { r: 0, g: 0, b: 0, a: 0 }},
        { view: normalView!, loadOp, storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1.0, a: 0 }},
        { view: depthView!,  loadOp, storeOp: 'store', clearValue: { r: 1, g: 0, b: 0, a: 0 }},
      ],
      depthStencilAttachment: {
        view: depthStencilView!,
        depthLoadOp: dsLoad, depthStoreOp: 'store', depthClearValue: 1.0,
        stencilLoadOp: dsLoad, stencilStoreOp: 'store', stencilClearValue: 0,
      },
    })
    if (viewport) rmPass.setViewport(viewport[0], viewport[1], viewport[2], viewport[3], 0, 1)
    raymarch.draw(rmPass, view, proj, eye, 0)
    rmPass.end()
  }

  /** Compute view + proj for one atlas panel given the current spec bounds. */
  function atlasMatrices(av: AtlasView, target: Vec3, dist: number, aspect: number) {
    const eye = eyeFromOrbit(target, av.yaw, av.pitch, dist)
    mat4.lookAt(atlasView, eye, target, av.up)
    mat4.perspective(atlasProj, (35 * Math.PI) / 180, aspect, 0.01, 50)
    return { view: atlasView, proj: atlasProj, eye }
  }

  loop.onRender = (st) => { try {
    // Resize canvas based on current mode. Agent: 2×panel atlas. Human: single panel.
    const tw = displayMode === 'agent' ? renderRes * 2 : renderRes
    const th = tw
    if (tw !== canvas.width || th !== canvas.height) {
      canvas.width = tw; canvas.height = th
      camera.setAspect(renderRes, renderRes)  // human-mode aspect (square panel)
    }
    ensureMRT(canvas.width, canvas.height)
    raymarch.setTime(st.elapsed)

    const swap = context.getCurrentTexture().createView()

    if (displayMode === 'human') {
      if (autoOrbit) camera.orbitRotate(0.005, 0)
      camera.update()
      const enc = device.createCommandEncoder({ label: 'modeler-human' })
      raymarchInto(
        enc, camera.view, camera.projection,
        [camera.position[0], camera.position[1], camera.position[2]],
        null, false,
      )
      // Camera direction = subject→camera = view direction toward eye.
      // Used by the lit pass for accurate Blinn-Phong specular. Computed
      // each frame because orbit can move the camera continuously.
      const dx = camera.position[0] - camera.target[0]
      const dy = camera.position[1] - camera.target[1]
      const dz = camera.position[2] - camera.target[2]
      const dlen = Math.hypot(dx, dy, dz) || 1
      lit!.setCameraDir([dx / dlen, dy / dlen, dz / dlen])
      lit!.run(enc, swap)
      device.queue.submit([enc.finish()])
    } else {
      // Agent atlas: 4 panels. Each panel needs its own submit because
      // raymarch.draw writes to a SHARED uniform buffer via queue.writeBuffer
      // and the queue serializes all writes BEFORE the submit's commands
      // run — putting all 4 in one submit means every pass reads the last
      // matrix. Splitting into 4 submits pairs each writeBuffer with its
      // own submit, so each pass sees its own camera. (Trivial perf cost
      // at 128² panels.) Final submit runs the outline over the full atlas.
      const { center, extent } = specBounds(spec)
      const dist = Math.max(0.25, extent * 2.0)
      const target = [center[0], center[1], center[2]] as Vec3
      const r = renderRes
      const tiles: Array<[number, number]> = [[0, 0], [r, 0], [0, r], [r, r]]
      for (let i = 0; i < ATLAS_VIEWS.length; i++) {
        const m = atlasMatrices(ATLAS_VIEWS[i], target, dist, 1)
        const penc = device.createCommandEncoder({ label: `modeler-atlas-${i}` })
        raymarchInto(penc, m.view, m.proj, m.eye,
          [tiles[i][0], tiles[i][1], r, r], i > 0)
        device.queue.submit([penc.finish()])
      }
      // Atlas tiles each have different camera directions; lit pass runs
      // once over the whole atlas with a single cameraDir uniform. Set it
      // to the iso panel's direction since that's the headline view —
      // other panels' specular will be approximate but visible glints
      // mostly happen when the iso panel reads water/shiny.
      const isoView = ATLAS_VIEWS[3]
      const isoEye = eyeFromOrbit(target, isoView.yaw, isoView.pitch, dist)
      const idx = isoEye[0] - target[0], idy = isoEye[1] - target[1], idz = isoEye[2] - target[2]
      const ilen = Math.hypot(idx, idy, idz) || 1
      lit!.setCameraDir([idx / ilen, idy / ilen, idz / ilen])
      const oenc = device.createCommandEncoder({ label: 'modeler-outline' })
      lit!.run(oenc, swap)
      device.queue.submit([oenc.finish()])
    }
    frameIdx++

    statsEl.textContent = `${st.fps.toFixed(0)} fps - ${spec.primitives.length} prim - ${displayMode} - ${canvas.width}x${canvas.height}`
    if (!firstFrameLogged) {
      firstFrameLogged = true
      // eslint-disable-next-line no-console
      console.log('[modeler] first frame OK', { canvasW: canvas.width, canvasH: canvas.height })
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[modeler] render error', err)
    statusEl.textContent = `RENDER: ${(err as Error).message}`
    statusEl.className = 'error'
    loop.stop()
  } }
  loop.start()
}

main().catch((e) => {
  console.error(e)
  const errEl = document.getElementById('error')
  if (errEl) {
    errEl.style.display = 'block'
    errEl.textContent = `Fatal: ${(e as Error).message}`
  }
})

/*
  ---------------------------------------------------------------------------
  TOOL API REFERENCE - accessible as `window.modeler.*` in the browser console
  or from a VL agent's tool runtime.
  ---------------------------------------------------------------------------

  Authoring:
    listTypes()                    -> PrimType[]
    addPrim({ type, pos?, params?, blendGroup?, blendRadius?,
             chamfer?, mirrorYZ?, rotationDeg?, id? }) -> id
    updatePrim(idxOrId, patch)     -> ModelerPrim
    deletePrim(idxOrId)            -> ModelerPrim
    duplicatePrim(idxOrId)         -> id of copy

  Spec:
    getSpec()                      -> ModelerSpec  (deep-cloned)
    setSpec(spec)                  -> ModelerSpec  (normalized + rendered)
    clear()                        -> fresh empty spec
    exportJSON()                   -> blob URL for download

  Camera + capture:
    setCamera({ yaw?, pitch?, distance?, target? })
    fitView()
    pause() / resume()
    screenshot() : Promise<string> -> PNG dataURL (for VL eyes)
*/
