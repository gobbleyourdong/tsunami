/**
 * Raymarch renderer — the bf16 reference for our SDF→pixel chain.
 *
 * Per-pixel raymarch across a flat primitive buffer. Skeletal deformation
 * lives in the primitive: each primitive names its parent bone, and per
 * ray step we transform the march point into that bone's local frame
 * before evaluating the primitive's SDF. The rig's VAT drives animation
 * identically to how the cube skeleton + chunk meshes get deformed —
 * same data buffer, different renderer.
 *
 * WHY THIS FIRST
 * ==============
 * This is the ground-truth baseline. Isosurface bake + chunk mesh path
 * is the optimization tier. We start with the reference so "wrong" has
 * a concrete signal (SDF params), not ambiguous blame split between SDF
 * and bake resolution. Same discipline we used on fp8 vs bf16 models —
 * validate at full precision first, quantize with reference in hand.
 *
 * COST AT SPRITE RESOLUTION
 * -------------------------
 * For 80² pixels × 32 march steps × 10 primitives × (~30 ops per
 * primitive eval + bone-inverse) ≈ 60M GPU ops/frame. A rounding error
 * on any modern GPU. At 1080p the same kernel would be ~320× more
 * expensive, which is why raymarching is "expensive" in big engines
 * and cheap here.
 *
 * PRIMITIVE TYPES
 * ---------------
 *   0 sphere        params = [radius, _, _, _]
 *   1 box           params = [halfX, halfY, halfZ, _]
 *   2 roundedBox    params = [halfX, halfY, halfZ, cornerR]
 *   3 ellipsoid     params = [rX, rY, rZ, _]
 *   4 cylinder      params = [radius, halfHeight, _, _]
 *   5 capsule       params = [radius, halfLength, _, _]
 *   6 torus         params = [majorR, minorR, _, _]
 *   7 flame         params = [radius, halfHeight, noiseAmp, noiseFreq]
 *                    capsule with surface noise displacement — advects
 *                    upward with `time`. First VFX primitive; validates
 *                    the procedural-SDF-as-VFX extension surface.
 *   8 swipeArc      params = [majorR, halfThick, arcAngleRad, innerRatio]
 *                    oblate shell clipped to an angular sector in XZ.
 *                    Drive arcAngleRad from CPU time for the wipe-in.
 *                    The "intersecting oblate spheroids" sword-swipe.
 *   9 logPolarSineTrail  params = [amplitude, frequency, decay, thickness]
 *                    Curve r(θ) = A·sin(ω·θ)·exp(-k·θ) in YZ plane,
 *                    given tube thickness in X. The damped-oscillation
 *                    slash trail.
 *  10 lightning     params = [halfLen, amplitude, thickness, _]
 *                    Zigzag bolt along Y with multi-octave sin
 *                    displacement in X and Z, re-seeded by time so it
 *                    crackles. Short lifetime (~150ms) reads as flash.
 *  11 noiseCloud    params = [halfX, halfY, halfZ, threshold]
 *                    3D value-noise field clipped to a bbox. Surface is
 *                    where noise > threshold. Advects slowly via time
 *                    for drifting smoke / fog / dust.
 *  12 cone          params = [sinHalfAngle, cosHalfAngle, height, _]
 *                    Standard IQ 2D cone SDF swept around Y. Tip at origin,
 *                    opens downward to base at y = -height. Nose/muzzle/
 *                    arrow-head/funnel primitive. Encoded as (sin, cos) of
 *                    half-angle so the shader avoids a trig call per eval.
 *
 * BLEND GROUPS
 * ------------
 * Each primitive names a `blendGroup` (0 = standalone). Primitives that
 * share a non-zero group ID smooth-blend with each other via `blendRadius`:
 *   radius > 0   → smooth-union (smin) — blends two surfaces into a single
 *                  tangent-continuous surface. This is how a face reads as
 *                  "skin stretched over bone" rather than "ellipsoids taped
 *                  together" — Inigo Quilez Girl (WsSBzh) pattern.
 *   radius < 0   → smooth-subtract (smax with negated d). Carves a hollow
 *                  into the group surface. Used for eye sockets, mouth.
 *   radius = 0   → hard union. Same as standalone but accumulated into
 *                  the group (useful for adding a small crisp detail like
 *                  a nose-tip sphere on top of a smooth-blended face).
 * Cross-group and cross-standalone combine with plain min(). Hard cap of
 * 16 groups per scene — enforced in shader; expand if a character needs more.
 *
 * Primitive's own offset from its parent bone origin is stored on the
 * primitive record, along with an optional rotation quaternion (x, y, z, w).
 * The quat lives in the primitive's local frame — i.e. it orients the
 * primitive RELATIVE to the bone, so a sword at 30° off the hand's +Y axis
 * is a quat with no per-frame rig change. Identity quat (0,0,0,1) = axis-
 * aligned, which is the common case — defaulted when omitted.
 */

/** Face mark — a bone-attached surface-color stroke. Eyes, mouths, tears,
 *  scars. NOT part of the SDF geometry; just a color override at hit time.
 *  Each mark has a tangent plane in bone-local space and a 2D shape
 *  evaluated on that plane.
 *
 *   shape        param interpretation
 *   'circle'     size = [radius, _]
 *   'rect'       size = [halfW, halfH]
 *   'line'       size = [halfLen, halfThickness]   (same test as rect)
 *   'triangle'   (planned)                         (future)
 */
export interface FaceMark {
  shape: 'circle' | 'rect' | 'line'
  boneIdx: number
  paletteSlot: number
  localCenter: [number, number, number]
  localNormal: [number, number, number]
  size: [number, number]
}

/** Color function enum — evaluated at raymarch hit time, picks between
 *  paletteSlot and paletteSlotB based on a per-function rule. All results
 *  palette-quantized so pixel-art consistency holds.
 *
 *  Patterns (4-6) evaluate in PRIMITIVE-LOCAL space — the same coordinate
 *  the SDF eval already computes via worldToLocal(). That gives bind-space
 *  anchoring for free: a stripe pattern stays glued to the bone surface
 *  through any animation (no world-space drift). */
export type ColorFunc =
  | 0  // flat: always paletteSlot
  | 1  // gradientY: hitPos.y / colorExtent → slotA (bottom) ↔ slotB (top), 3 crisp bands
  | 2  // pulsate: time-oscillating swap between A and B
  | 3  // radialFade: radial distance from primitive origin → A (center) ↔ B (edge)
  | 4  // stripes: alternating slotA/slotB along primitive-local Y. colorExtent = stripes/meter
  | 5  // dots: dot grid on primitive-local XY plane. colorExtent = cell size in meters
  | 6  // checker: 3D checker in primitive-local space. colorExtent = cell size in meters
  | 7  // chevron: V-shaped bands by |x|+y in primitive-local. colorExtent = chevrons/meter
  | 8  // worldStripes: stripes along WORLD Y — continuous across multi-prim chains
  | 9  // cracks: voronoi edge bands → irregular dark fracture lines on the surface. colorExtent = cells/meter

export interface RaymarchPrimitive {
  type: number             // 0..15, see header comment + sdLineCapsule3D for type 15
  paletteSlot: number      // primary palette LUT index (slotA)
  boneIdx: number          // index into VAT buffer's per-joint matrices
  params: [number, number, number, number]
  offsetInBone: [number, number, number]
  /** Optional procedural color. Default = 0 (flat). */
  colorFunc?: ColorFunc
  /** Secondary palette slot for ramp / pulsate. Defaults to paletteSlot. */
  paletteSlotB?: number
  /** Function-specific magnitude. For gradientY: half-extent along Y
   *  within which the ramp plays out. For pulsate: frequency in Hz.
   *  For radialFade: the radius at which we transition to slotB. */
  colorExtent?: number
  /** Blend-group membership. 0 (default) = standalone primitive, contributes
   *  to the scene via hard-union min(). 1..15 = group index; primitives in
   *  the same group smooth-combine (see `blendRadius`). Groups beyond MAX_GROUPS
   *  silently fall back to standalone. */
  blendGroup?: number
  /** Signed blend radius in world meters. Only meaningful when blendGroup > 0.
   *  Positive = smooth-union (smin k = radius). Negative = smooth-subtract
   *  (smax(-d, group, k=|radius|)). Zero = hard-union into the group. */
  blendRadius?: number
  /** When true, the group blend uses CHAMFER (Mercury hg_sdf 45° bevel)
   *  instead of polynomial smin. Sharper edges — useful for armor /
   *  weapons / mecha. Encoded as bit 4 of the packed blendGroup u32 in
   *  the storage buffer; the shader masks it out for the group lookup. */
  chamfer?: boolean
  /** When true, this primitive is duplicated at emit time with its
   *  offsetInBone.x sign-flipped — effectively mirroring across the
   *  YZ plane. Halves authoring effort for symmetric features (horns,
   *  ears, decorative trim). Expansion is a CPU pass before upload via
   *  `expandMirrors()`; the shader sees just two regular prims. */
  mirrorYZ?: boolean
  /** Optional rotation quaternion (x, y, z, w) applied in the primitive's
   *  local frame. Omit (or pass identity) for axis-aligned primitives.
   *  Useful for: angled weapons, tilted face features, oriented cones.
   *  Runtime inverts the quat and rotates the march point, not the
   *  primitive, so the SDF eval stays cheap and exact. */
  rotation?: [number, number, number, number]
  /** FBM micro-displacement amplitude in world meters — read ONLY by the
   *  normal pass (dual-map pattern). Zero (default) = smooth surface.
   *  Values around 0.002–0.005 give subtle skin/wood-grain detail at
   *  sprite resolution. Does not affect silhouette or shadows; only
   *  shading via the 3-band cel normal. */
  detailAmplitude?: number
  /** Selective specular highlight flag. When true, the surface picks
   *  up a tight hot-spot on the lit side (`n·keyDir > 0.85`) tinted by
   *  the key light's colour. When false, surface is fully matte (no
   *  highlight). Per-primitive boolean — replaces the old roughness
   *  scalar with a simpler authored choice. Bit-packed into colorFunc's
   *  upper bit on the GPU side, no per-prim storage cost. */
  shiny?: boolean
  /** Unlit flag — when true, the outline pass skips ALL lighting for
   *  this primitive's pixels (no cel band, no point lights, no specular).
   *  Pixels render with the raw palette colour authored by colorFunc /
   *  paletteSlot. For VFX (flames, beams, magic, lightning) which are
   *  meant to glow with their own pre-coloured intensity. Bit-packed
   *  into colorFunc's bit 6 alongside shiny in bit 7. */
  unlit?: boolean
  /** Optional secondary "wear" deformer that runs AFTER the primary
   *  colorFunc deformer in evalPrim. Lets one prim layer a base structural
   *  pattern (cracks/hex/scales/etc.) PLUS a weathering overlay (bumps for
   *  pitting, grain for striation, streaks for drips, scratches for wear).
   *  IDs (1-based to leave 0 as off): 1=bumps, 2=grain, 3=streaks,
   *  4=scratches. */
  wearFn?: 0 | 1 | 2 | 3 | 4
  /** Wear-deformer depth (m). Same units as the primary deformer's depth. */
  wearDepth?: number
  /** Wear-deformer density (cycles/cells per meter). */
  wearDensity?: number
  /** Terrain flow-channel carve depth (m). Used only when colorFunc=28
   *  (terrain deformer). Carves rivers into the surface based on the
   *  flow accumulation field. Stored in slot 5.w (formerly pad). */
  terrainFlowDepth?: number
}

/** Expand any RaymarchPrimitive with `mirrorYZ` into a pair: original
 *  + X-flipped sibling. Other fields copy verbatim. The sibling's name
 *  isn't needed (RaymarchPrimitive has no name field), so the shader
 *  just sees two regular prims. Call before `setPrimitives()`.
 *
 *  Note: `mirrorYZ` only flips `offsetInBone.x`. If the primitive's
 *  shape itself isn't symmetric (e.g. a quat-rotated cone or a typed
 *  cube whose params use signed values for direction), the caller is
 *  responsible for additional sign flips on `params` / `rotation`. */
export function expandMirrors(prims: RaymarchPrimitive[]): RaymarchPrimitive[] {
  const out: RaymarchPrimitive[] = []
  for (const p of prims) {
    out.push(p)
    if (p.mirrorYZ) {
      const m: RaymarchPrimitive = {
        ...p,
        mirrorYZ: false,   // prevent re-expansion if expandMirrors runs twice
        offsetInBone: [-p.offsetInBone[0], p.offsetInBone[1], p.offsetInBone[2]],
      }
      // Mirror slot-4 too. For most prims, slot 4 = rotation quaternion.
      // Reflecting a rotation across the YZ plane (x-flip): the rotation
      // axis x-component is reflected (q.x stays since it represents
      // sin(θ/2)*axis.x and axis.x flips, BUT the handedness flip from
      // mirroring makes the angle reverse, which negates y,z components).
      // Net effect: (x, y, z, w) → (x, -y, -z, w). Standard reflection rule.
      // Type 14 (bentCapsule) overloads slot 4 as tipDelta (xyz, w unused);
      // for that, mirror tipDelta.x → -tipDelta.x (it's an offset in
      // primitive-local space, mirrors with the prim).
      if (p.rotation) {
        if (p.type === 14) {
          // bentCapsule: rotation slot is tipDelta vector. Mirror x.
          m.rotation = [-p.rotation[0], p.rotation[1], p.rotation[2], p.rotation[3]]
        } else {
          // Standard rotation quaternion: (x, -y, -z, w) for X-axis reflection.
          m.rotation = [p.rotation[0], -p.rotation[1], -p.rotation[2], p.rotation[3]]
        }
      }
      out.push(m)
    }
  }
  return out
}

/** Same VATData interface used by skeleton_renderer + chunk_renderer. */
export interface VATData {
  buffer: GPUBuffer
  numInstances: number
  numFrames: number
}

// Storage-buffer layout per primitive (24 floats = 96 bytes):
//   [0..3]    typeAndSlots as u32 cast: type, paletteSlot, boneIdx, colorFunc
//   [4..7]    params x/y/z/w
//   [8..11]   offsetInBone x/y/z/detailAmplitude (normal-pass FBM, 0 = off)
//   [12..15]  slotB (u32) | colorExtent (f32) | blendGroup (u32) | blendRadius (f32, signed)
//   [16..19]  rotation quat (x, y, z, w) — identity (0,0,0,1) if axis-aligned
//   [20..23]  wearFn (u32) | wearDepth (f32) | wearDensity (f32) | _pad
//             Secondary "wear" deformer that runs after the primary colorFunc
//             deformer. Limited to FBM-based wear modes: 1=bumps, 2=grain,
//             3=streaks, 4=scratches. 0 = off. Lets one prim composite a base
//             structural pattern with a weathering overlay.
const PRIM_STRIDE_FLOATS = 24

const RAYMARCH_SHADER = /* wgsl */ `
struct Uniforms {
  invViewProj: mat4x4<f32>,   // reconstruct world-space ray from NDC
  view:        mat4x4<f32>,   // world → view (for view-space pixel snap)
  eye:         vec4f,          // camera world position (xyz, w unused)
  numPrims:    u32,
  numJoints:   u32,
  frameIdx:    u32,
  maxSteps:    u32,
  time:        f32,            // seconds since engine start — drives VFX evolution
  pxPerM:      f32,            // pixels per world meter — snap grid for primitive centers
  numFaceMarks: u32,           // count of active face marks (<=MAX_FACE_MARKS)
  terrainWaterLevel: f32,      // water level threshold in [0, 1]; cells of
                               // colorFunc=28 deformer below this height are
                               // capped (flat water surface) and palette-
                               // overridden to slot 3 (water blue).
  bgMode:           u32,       // 0 = transparent miss (alpha=0, character demos);
                               // 1 = atmospheric sky on miss (terrain scenes)
}

@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var<storage, read> prims: array<vec4f>;     // PRIM_STRIDE_FLOATS per primitive
@group(0) @binding(2) var<storage, read> vatMats: array<vec4f>;   // forward bone matrices
@group(0) @binding(3) var<storage, read> palette: array<vec4f>;
// Face marks — surface-color overrides bolted to bones. Same idea as the
// accessory/primitive attachment system, but these don't participate in
// the SDF geometry — they only decide per-pixel palette slot at hit time.
// Each mark = 4 vec4f (64 bytes):
//   [0] slots u32: shape, boneIdx, paletteSlot, enable
//   [1] center.xyz, _pad         (position in bone-local space)
//   [2] normal.xyz, _pad         (surface normal — tangent plane)
//   [3] size.x, size.y, _, _     (half-extents: circle→.x=radius, rect→.xy)
//
// Shapes: 0=circle, 1=rect, 2=line, 3=triangle (future).
@group(0) @binding(4) var<storage, read> faceMarks: array<vec4f>;
// Reaction-diffusion (Gray-Scott) field. RD_GRID²-element f32 array sampled
// by world-XY → uv (mod 1.0 for tiling). Baked CPU-side at spec ingest, not
// updated per-frame. Default-zero buffer when RD is not in use.
const RD_GRID: u32 = 128u;
@group(0) @binding(5) var<storage, read> rdField: array<f32>;
struct VsOut {
  @builtin(position) clip: vec4f,
  @location(0) ndc: vec2f,
}

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  // One fullscreen triangle covering NDC [-1,1]^2.
  let corners = array<vec2f, 3>(
    vec2f(-1.0, -1.0),
    vec2f( 3.0, -1.0),
    vec2f(-1.0,  3.0),
  );
  var out: VsOut;
  out.clip = vec4f(corners[vid], 0.0, 1.0);
  out.ndc  = corners[vid];
  return out;
}

fn readMat4(base: u32) -> mat4x4<f32> {
  return mat4x4<f32>(
    vatMats[base + 0u],
    vatMats[base + 1u],
    vatMats[base + 2u],
    vatMats[base + 3u],
  );
}

// Transform a world-space point into a bone's local frame, correctly
// handling per-axis scale baked into the bone's display matrix.
//
// Display matrix layout (from glb_loader.ts::createRetargetComposer):
//   col 0 = R_x * sx
//   col 1 = R_y * sy
//   col 2 = R_z * sz
//   col 3 = (translation, 1)
// where R_* are unit rotation basis vectors and s* come from the per-joint
// proportion scale. Inverse is: diag(1/s²) · M^T · (p - t)
// = (dot(col0, d)/|col0|², dot(col1, d)/|col1|², dot(col2, d)/|col2|²).
//
// If ANY axis scale collapses to zero (body-part sliders default to 0),
// the local-space projection is undefined — we substitute a far-field
// point so the primitive contributes nothing to the scene SDF. The old
// transpose-only inverse collapsed all world points to the origin in that
// case, which made zero-scale primitives register as "always inside" and
// hit every ray. This is the fix for that.
fn worldToLocal(m: mat4x4<f32>, pWorld: vec3f) -> vec3f {
  let c0 = m[0].xyz;
  let c1 = m[1].xyz;
  let c2 = m[2].xyz;
  let s0sq = dot(c0, c0);
  let s1sq = dot(c1, c1);
  let s2sq = dot(c2, c2);
  if (min(min(s0sq, s1sq), s2sq) < 1e-10) {
    return vec3f(1e6);   // degenerate bone → primitive effectively invisible
  }
  let d = pWorld - m[3].xyz;
  return vec3f(dot(c0, d) / s0sq, dot(c1, d) / s1sq, dot(c2, d) / s2sq);
}

// Rotate a vec3 by a quat (x,y,z,w). Standard v' = v + 2*cross(q.xyz, cross(q.xyz, v) + q.w*v).
// Used to transform the march point into a primitive's oriented local frame.
// We apply the INVERSE quat (negate xyz, keep w) in the caller so primitive
// SDFs stay axis-aligned in their own eval space — cheaper than rotating
// the primitive surface per sample.
fn rotateByQuat(v: vec3f, q: vec4f) -> vec3f {
  let u = q.xyz;
  let s = q.w;
  return v + 2.0 * cross(u, cross(u, v) + s * v);
}

// SDF primitive evaluators — point is already in primitive-local space.

fn sdSphere(p: vec3f, r: f32) -> f32 {
  return length(p) - r;
}
fn sdBox(p: vec3f, h: vec3f) -> f32 {
  let q = abs(p) - h;
  return length(max(q, vec3f(0.0))) + min(max(q.x, max(q.y, q.z)), 0.0);
}
fn sdRoundedBox(p: vec3f, h: vec3f, r: f32) -> f32 {
  let hi = max(h - vec3f(r), vec3f(0.0));
  return sdBox(p, hi) - r;
}
// Band (rectangular-cross-section torus / "rectangular ring"): a torus
// where the cross-section perpendicular to the ring is a rectangle of
// half-width w (radial in/out) and half-height h (along axis Y) instead
// of a circle. The "band" / "flat strap" form factor — barrel hoops with
// width, sword-belt buckles, mug handles with rectangular grip cross-section.
// R = major radius (ring radius), w = radial half-extent, h = axial half-extent.
fn sdBand(p: vec3f, R: f32, w: f32, h: f32) -> f32 {
  let q = vec2f(length(p.xz) - R, p.y);
  let d = vec2f(abs(q.x) - w, abs(q.y) - h);
  return length(max(d, vec2f(0.0))) + min(max(d.x, d.y), 0.0);
}
// Trapezoidal box (truncated rectangular pyramid / frustum): bottom face has
// half-extents (bx, bz), top face uniformly scaled by topRatio. Height 2h
// along Y. topRatio==1 reduces to a regular box; topRatio==0 collapses the
// top to a point (rectangular pyramid).
//
// Use cases: knife/sword blades (taper from spine to edge), gun stocks,
// pyramid frustums, decorative bezels, cone-like shapes with rectangular
// cross-section. Params packed as (bx, bz, h, topRatio).
fn sdTrapezoidalBox(p: vec3f, bx: f32, bz: f32, h: f32, topRatio: f32) -> f32 {
  // Vertical position [0..1] along the height; clamped for outside-box query.
  let t  = clamp((p.y + h) / (2.0 * h), 0.0, 1.0);
  let ex = mix(bx, bx * topRatio, t);
  let ez = mix(bz, bz * topRatio, t);
  // 2D distance to rectangle (ex, ez) at this height.
  let q  = vec2f(abs(p.x) - ex, abs(p.z) - ez);
  let d2D = length(max(q, vec2f(0.0))) + min(max(q.x, q.y), 0.0);
  // Vertical distance outside the height range.
  let dy = abs(p.y) - h;
  // Combine: max for inside, length-of-outside for outside.
  let outside = vec2f(max(d2D, 0.0), max(dy, 0.0));
  let inside  = min(max(d2D, dy), 0.0);
  return length(outside) + inside;
}
fn sdEllipsoid(p: vec3f, r: vec3f) -> f32 {
  let k0 = length(p / r);
  let k1 = length(p / (r * r));
  return (k0 * (k0 - 1.0)) / k1;
}
// Exact ellipsoid SDF via quadratic-root formulation. Solves
//
//     ax² + bx + c = 0    where a, b, c are derived from |p| and r²
//
// for the ray parameter t such that p - t·dir lies on the ellipsoid
// surface. Combined with three axis-projection solves, recovers a
// signed distance that's tighter than the IQ "inexact bound" type 3
// uses (the inexact one degrades linearly with distance from surface).
//
// Public formula — see Inigo Quilez' SDF article + Unbound's _metallic_2
// deobfuscated form. ~5× more ALU than type 3 but the correct distance
// matters when ellipsoids are highly anisotropic (e.g. r = (0.05, 0.30,
// 0.05) for a long crest ridge) — type 3 over-shoots dramatically.
fn solveQuadratic2(a: f32, b: f32, c: f32) -> vec2f {
  let disc = b * b - 4.0 * a * c;
  if (disc < 0.0) { return vec2f(1e20, 1e20); }
  let q = -b / (2.0 * a);
  let s = sqrt(disc) / (2.0 * a);
  return vec2f(q - s, q + s);
}
// Cardano cubic root solver — returns the smallest non-negative real
// root in [0, 1] of the depressed cubic x³ + px + q = 0 (caller must
// pre-depress general ax³ + bx² + cx + d = 0 via x = t - b/(3a)).
// Used for exact closest-point on a quadratic Bezier (the minimization
// d/dt|B(t) - p|² = 0 is a cubic in t). Returns 1e20 if no root in
// [0, 1] (caller falls back to clamped endpoints).
//
// Discriminant cases:
//   D > 0  → one real root (use Cardano + cube roots)
//   D = 0  → triple or double root (use linear-style fallback)
//   D < 0  → three real roots (use trigonometric form)
//
// Public formula — see Inigo Quilez's 2D Bezier distance article.
fn solveCubicCardano(p: f32, q: f32) -> vec3f {
  let disc = q * q + (4.0 / 27.0) * p * p * p;
  if (disc > 0.0) {
    let sqd = sqrt(disc);
    let u = -0.5 * q + 0.5 * sqd;
    let v = -0.5 * q - 0.5 * sqd;
    let cuRoot = sign(u) * pow(abs(u), 1.0 / 3.0) + sign(v) * pow(abs(v), 1.0 / 3.0);
    return vec3f(cuRoot, 1e20, 1e20);
  }
  // D <= 0: three real roots via trig form.
  let r = sqrt(-p / 3.0);
  let cosArg = clamp(1.5 * q / (p * r), -1.0, 1.0);
  let theta = acos(cosArg) / 3.0;
  let twoR = 2.0 * r;
  return vec3f(
    twoR * cos(theta),
    twoR * cos(theta - 2.094395102),   // - 2π/3
    twoR * cos(theta - 4.188790205),   // - 4π/3
  );
}
fn sdEllipsoidExact(p: vec3f, r: vec3f) -> f32 {
  let ap = abs(p);
  let r2 = r * r;
  let invR2 = vec3f(1.0) / r2;
  let neg2pInvR2 = -2.0 * ap * invR2;
  let p2InvR2 = ap * ap * invR2;
  let cIn = (p2InvR2.x + p2InvR2.y + p2InvR2.z) - 1.0;
  // Surface solve.
  let aSum = invR2.x + invR2.y + invR2.z;
  let bSum = neg2pInvR2.x + neg2pInvR2.y + neg2pInvR2.z;
  let roots = solveQuadratic2(aSum, bSum, cIn);
  var d = min(abs(roots.x), abs(roots.y));
  // Inside? — sign flip.
  if (cIn <= 0.0) { return -d; }
  // Three axis projections — refine when point is closer to a box-axis
  // face than to the ellipsoid surface (handles very flat / elongated
  // shapes where the surface solve overestimates).
  let r2yz = solveQuadratic2(invR2.y + invR2.z, neg2pInvR2.y + neg2pInvR2.z, p2InvR2.y + p2InvR2.z - 1.0);
  d = min(d, max(min(abs(r2yz.x), abs(r2yz.y)), ap.x));
  let r2xz = solveQuadratic2(invR2.x + invR2.z, neg2pInvR2.x + neg2pInvR2.z, p2InvR2.x + p2InvR2.z - 1.0);
  d = min(d, max(min(abs(r2xz.x), abs(r2xz.y)), ap.y));
  let r2xy = solveQuadratic2(invR2.x + invR2.y, neg2pInvR2.x + neg2pInvR2.y, p2InvR2.x + p2InvR2.y - 1.0);
  d = min(d, max(min(abs(r2xy.x), abs(r2xy.y)), ap.z));
  return d;
}
fn sdCylinder(p: vec3f, r: f32, h: f32) -> f32 {
  let dx = length(vec2f(p.x, p.z)) - r;
  let dy = abs(p.y) - h;
  return length(max(vec2f(dx, dy), vec2f(0.0))) + min(max(dx, dy), 0.0);
}
fn sdCapsule(p: vec3f, r: f32, h: f32) -> f32 {
  let y = clamp(p.y, -h, h);
  return length(vec3f(p.x, p.y - y, p.z)) - r;
}
// Bent capsule — straight at the root, displaces toward tipDelta
// quadratically along Y so the tip carries the most bend. tipDelta is
// in PRIMITIVE-LOCAL coordinates (the same frame p is in). For sprite-
// tier strand wisps the bend is small (a few cm at most) so the SDF
// stays a reasonable approximation despite not being an exact swept
// distance — round-tripped against the original capsule formula at
// tipDelta=0 and matches.
fn sdBentCapsule(p: vec3f, r: f32, h: f32, tipDelta: vec3f) -> f32 {
  let t = clamp((p.y + h) / (2.0 * h), 0.0, 1.0);
  let bend = tipDelta * (t * t);
  let bp = p - bend;
  let y = clamp(bp.y, -h, h);
  return length(vec3f(bp.x, bp.y - y, bp.z)) - r;
}
// Line capsule — distance from a WORLD-space point to the line
// segment (a, b), with linearly interpolated radius (ra at a, rb at b).
// The "queen swoop" architecture: limbs are SDFs of distance-to-line
// between two JOINT positions. Length is implicit (|b - a|), driven by
// animation + proportion changes; joint scale becomes only thickness.
// Decouples skeletal motion from limb shape — no bone-local frame, no
// non-uniform-scale Lipschitz issues, no joint squish.
fn sdLineCapsule3D(p: vec3f, a: vec3f, b: vec3f, ra: f32, rb: f32) -> f32 {
  let pa = p - a;
  let ba = b - a;
  let denom = max(dot(ba, ba), 1e-8);
  let h = clamp(dot(pa, ba) / denom, 0.0, 1.0);
  let r = mix(ra, rb, h);
  return length(pa - ba * h) - r;
}

// Oval cross-section variant. Operates in jointA's local frame.
// caller passes pLocal (= worldToLocal(boneA, p)) and bLocal (jointB
// position in jointA-local). Cross-section is the XZ plane in jointA-
// local (Mixamo convention: bone +Y points to first child, so XZ is
// perpendicular). raX/raZ + rbX/rbZ are per-axis radii at A and B,
// linearly interpolated along t. Ellipse SDF is approximate (not
// strict Lipschitz) — multiplied by avgR to scale to world distance.
// Same caveat as cloud density: march survives at conservative steps.
// Directional-Z variant: separate radii on +Z (front) and -Z (back) at
// each end. Lets a segment express front/back asymmetry — chest pushes
// forward (raZpos > raZneg), glute pushes back (raZneg > raZpos), etc.
// X radius is still symmetric (same on +X / -X).
fn sdLineCapsuleOvalDirZ(pLocal: vec3f, bLocal: vec3f,
                          raX: f32, rbX: f32,
                          raZpos: f32, raZneg: f32,
                          rbZpos: f32, rbZneg: f32) -> f32 {
  let bLen = max(length(bLocal), 1e-6);
  let bDir = bLocal / bLen;
  let hSigned = dot(pLocal, bDir);
  let h = clamp(hSigned / bLen, 0.0, 1.0);
  let onAxis = bDir * (h * bLen);
  let perp = pLocal - onAxis;
  let rx = mix(raX, rbX, h);
  let rzPos = mix(raZpos, rbZpos, h);
  let rzNeg = mix(raZneg, rbZneg, h);
  let rz = select(rzNeg, rzPos, perp.z >= 0.0);
  // MIN (not avg) of the two radii — Lipschitz-safe for elongated
  // cross-sections. avg overestimates distance along the thin axis,
  // making the raymarcher overshoot and miss the surface. Same fix
  // as sdLineCapsuleOval — both formulas had the same latent bug.
  let minR = min(rx, rz);
  let scaledLen = sqrt((perp.x * perp.x) / max(rx * rx, 1e-8) + (perp.z * perp.z) / max(rz * rz, 1e-8));
  let dPerp = (scaledLen - 1.0) * minR;
  let dAxial = max(-hSigned, hSigned - bLen);
  let dq = vec2f(dPerp, dAxial);
  return min(max(dq.x, dq.y), 0.0) + length(max(dq, vec2f(0.0)));
}

// Type 23 — RIBBON CHAIN. Polyline ribbon: a 2D rectangle (halfW across
// the curve's right axis, halfT along the curve's normal axis) extruded
// along up to 6 bones whose indices are passed in explicitly. Tangent
// at each segment is the unit direction from current bone to next bone.
// Cross-section frame is rebuilt robustly per segment: first try
// projecting the bone-0 X axis perpendicular to the tangent; if that
// degenerates (tangent aligns with the X axis), fall back to projecting
// world +Y instead. Either way the resulting (R, F) basis is orthonormal
// and perpendicular to the tangent.
fn sdRibbonChainSeg(p: vec3f, prevPos: vec3f, curPos: vec3f,
                    rightRef: vec3f, halfW: f32, halfT: f32) -> f32 {
  let ab = curPos - prevPos;
  let abLen = max(length(ab), 1e-6);
  let tang = ab / abLen;
  // Robust right axis: project rightRef perpendicular to tang. If that
  // collapses (tang ‖ rightRef), use world +Y as the reference.
  var R = rightRef - tang * dot(rightRef, tang);
  if (dot(R, R) < 1e-4) {
    let upWorld = vec3f(0.0, 1.0, 0.0);
    R = upWorld - tang * dot(upWorld, tang);
    if (dot(R, R) < 1e-4) {
      R = vec3f(0.0, 0.0, 1.0) - tang * tang.z;
    }
  }
  R = normalize(R);
  let F = cross(tang, R);
  // PROPER 3D box SDF in the segment's local frame:
  //   T axis = tangent (axial), half-extent = abLen / 2
  //   R axis = right (cross-section width),  half-extent = halfW
  //   F axis = forward (cross-section thick), half-extent = halfT
  // Origin = midpoint of segment. Without the axial half-extent we
  // were evaluating an INFINITE tube along tang past each endpoint,
  // which compounded into the "exploded everywhere" look at the join.
  let mid = prevPos + tang * (abLen * 0.5);
  let diff = p - mid;
  let lx = dot(diff, R);
  let ly = dot(diff, tang);
  let lz = dot(diff, F);
  let q = vec3f(abs(lx) - halfW, abs(ly) - abLen * 0.5, abs(lz) - halfT);
  let outer = length(max(q, vec3f(0.0)));
  let inner = min(max(q.x, max(q.y, q.z)), 0.0);
  return outer + inner;
}

// Per-segment 3D box SDF, with each segments cross-section frame read
// directly from the start bones matrix. Cape physics parallel-transports
// the R axis down the chain so adjacent segments share the same frame
// at their shared vertex — boxes meet without rotation around the
// tangent axis (no twist). A SMALL smin (1cm radius) between segments
// rounds the wedge corners at vertices into a smooth fillet — visible
// continuity without the bulge/distortion that a large smin produces.
fn sdRibbonChain(p: vec3f, startBone: u32, count: u32,
                 halfW: f32, halfT: f32) -> f32 {
  if (count < 2u) { return 1e9; }
  var d: f32 = 1e9;
  let segSmin: f32 = 0.030;
  for (var i: u32 = 0u; i < count - 1u; i = i + 1u) {
    let mat0 = readMat4((u.frameIdx * u.numJoints + startBone + i) * 4u);
    let mat1 = readMat4((u.frameIdx * u.numJoints + startBone + i + 1u) * 4u);
    let prevPos = mat0[3].xyz;
    let curPos  = mat1[3].xyz;
    let R0Raw = mat0[0].xyz;
    let F0Raw = mat0[2].xyz;
    let R0Len = max(length(R0Raw), 1e-6);
    let F0Len = max(length(F0Raw), 1e-6);
    let R = R0Raw / R0Len;
    let F = F0Raw / F0Len;
    let ab = curPos - prevPos;
    let abLen = max(length(ab), 1e-6);
    let tang = ab / abLen;
    let mid = prevPos + tang * (abLen * 0.5);
    let diff = p - mid;
    let lx = dot(diff, R);
    let ly = dot(diff, tang);
    let lz = dot(diff, F);
    let q = vec3f(abs(lx) - halfW, abs(ly) - abLen * 0.5, abs(lz) - halfT);
    let outer = length(max(q, vec3f(0.0)));
    let inner = min(max(q.x, max(q.y, q.z)), 0.0);
    let segD = outer + inner;
    if (i == 0u) {
      d = segD;
    } else {
      d = smin_k(d, segD, segSmin);
    }
  }
  return d;
}

fn sdLineCapsuleOval(pLocal: vec3f, bLocal: vec3f,
                     raX: f32, raZ: f32, rbX: f32, rbZ: f32) -> f32 {
  // Project pLocal onto the segment axis. h in [0,1] = within segment.
  let bLen = max(length(bLocal), 1e-6);
  let bDir = bLocal / bLen;
  let hSigned = dot(pLocal, bDir);          // axial position in metres
  let h = clamp(hSigned / bLen, 0.0, 1.0);  // normalized 0..1
  let onAxis = bDir * (h * bLen);
  let perp = pLocal - onAxis;
  // Cross-section radii at the (clamped) axial position.
  let rx = mix(raX, rbX, h);
  let rz = mix(raZ, rbZ, h);
  // Use MIN of the two radii (not average) for the Lipschitz factor.
  // For highly-elongated cross-sections (e.g., cape: rx=0.15, rz=0.025,
  // ratio 6:1), avg overestimates the distance along the THIN axis by
  // up to ratio×, causing the raymarcher to overshoot and miss the
  // surface entirely. min underestimates a bit along the WIDE axis,
  // which just costs extra march steps — safe and never misses.
  let minR = min(rx, rz);
  // Perpendicular ellipse SDF (signed, scaled by minR for world units).
  let scaledLen = sqrt((perp.x * perp.x) / max(rx * rx, 1e-8) + (perp.z * perp.z) / max(rz * rz, 1e-8));
  let dPerp = (scaledLen - 1.0) * minR;     // <0 inside ellipse, >0 outside
  // Axial slab signed distance: <0 inside [0, bLen], >0 past either end.
  let dAxial = max(-hSigned, hSigned - bLen);
  // Canonical extruded-2D-shape SDF (IQ): combine the 2D (radial, axial)
  // signed pair. Inside both → return less-negative; outside one → that
  // axis's distance; outside both → L2 of positive parts.
  let dq = vec2f(dPerp, dAxial);
  return min(max(dq.x, dq.y), 0.0) + length(max(dq, vec2f(0.0)));
}
// Bezier-profile capsule — the anatomy primitive.
//   3D shape: quadratic Bezier curve through three joints A, B, C.
//   1D radius: cubic Bezier of 4 control radii r0..r3 sampled along the
//              same parameter t. The profile is the muscle / silhouette
//              curve — wider at bicep peak, narrower at elbow, etc.
// N=8-segment subdivision: for each segment, take the line-distance with
// linearly-interpolated radius across that segment, accumulate min. Not
// a tight Lipschitz SDF (overestimates step size when the curve is high-
// curvature), but at sprite res with sane bezier control points the
// raymarch converges in 32 steps no problem.
fn sdBezierProfileCapsule(p: vec3f, a: vec3f, b: vec3f, c: vec3f,
                          r0: f32, r1: f32, r2: f32, r3: f32) -> f32 {
  let N: u32 = 8u;
  var d: f32 = 1e9;
  var prevP: vec3f = a;
  var prevR: f32 = r0;
  for (var i: u32 = 1u; i <= N; i = i + 1u) {
    let t  = f32(i) / f32(N);
    let mt = 1.0 - t;
    // Quadratic 3D Bezier: B(t) = (1-t)²A + 2(1-t)t·B + t²C
    let pos = mt * mt * a + 2.0 * mt * t * b + t * t * c;
    // Cubic 1D Bezier on radii: r(t) = (1-t)³r0 + 3(1-t)²t·r1 + 3(1-t)t²·r2 + t³r3
    let r = mt * mt * mt * r0
          + 3.0 * mt * mt * t * r1
          + 3.0 * mt * t * t * r2
          + t * t * t * r3;
    // Line-segment distance with interpolated radius across this segment.
    let pa = p - prevP;
    let ba = pos - prevP;
    let h  = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-8), 0.0, 1.0);
    let rs = mix(prevR, r, h);
    d = min(d, length(pa - ba * h) - rs);
    prevP = pos;
    prevR = r;
  }
  return d;
}
// EXACT bezier-profile capsule — replaces type 17's N=8 segment
// approximation with the Cardano-cubic closest-point on a quadratic
// Bezier. Same authoring shape (3 joints + 4-control radius profile)
// but tighter SDF — the marcher takes fewer steps because the
// distance is genuinely the minimum, not an upper-bounded sample.
//
// The closest-point math: for B(t) = (1-t)²A + 2(1-t)t·B + t²·C,
// d/dt|B(t) - p|² = 0 expands to a cubic in t. We solve it via the
// Cardano helper, evaluate the radius at the root from the 1D radius
// profile, and return distance - radius. Endpoints t=0 and t=1 are
// also tested in case the cubic root falls outside [0, 1].
fn sdBezierExactCapsule(p: vec3f, a: vec3f, b: vec3f, c: vec3f,
                         r0: f32, r1: f32, r2: f32, r3: f32) -> f32 {
  // m0 = A - P, m1 = B - A, m2 = A - 2B + C  (so B(t) = m0 + 2t·m1 + t²·m2 + P)
  let m0 = a - p;
  let m1 = b - a;
  let m2 = a - 2.0 * b + c;
  // Cubic coefficients of (B(t) - P) · B'(t) = 0:
  //   a₃·t³ + a₂·t² + a₁·t + a₀ = 0
  let a3 = dot(m2, m2);
  let a2 = 3.0 * dot(m1, m2);
  let a1 = 2.0 * dot(m1, m1) + dot(m0, m2);
  let a0 = dot(m0, m1);
  // Sample distance at three candidate t values: 0, 1, and the cubic
  // root closest to [0, 1]. Take the min — covers all "what if the
  // closest point is on the curve OR at an endpoint" cases.
  var best = 1e20;
  var bestT = 0.0;
  // Endpoint t=0.
  let d0 = length(m0);
  if (d0 < best) { best = d0; bestT = 0.0; }
  // Endpoint t=1.
  let d1 = length(m0 + 2.0 * m1 + m2);
  if (d1 < best) { best = d1; bestT = 1.0; }
  // Cubic root via Cardano. Depress: a₃·t³ + a₂·t² + a₁·t + a₀ → s³ + p·s + q
  // with t = s - a₂/(3·a₃).
  if (abs(a3) > 1e-8) {
    let invA3 = 1.0 / a3;
    let A = a2 * invA3;
    let B = a1 * invA3;
    let C = a0 * invA3;
    let pCoef = B - A * A / 3.0;
    let qCoef = 2.0 * A * A * A / 27.0 - A * B / 3.0 + C;
    let roots = solveCubicCardano(pCoef, qCoef);
    let shift = A / 3.0;
    let candidates = vec3f(roots.x - shift, roots.y - shift, roots.z - shift);
    for (var k = 0; k < 3; k = k + 1) {
      let t = clamp(candidates[k], 0.0, 1.0);
      // Skip 1e20 sentinels.
      if (abs(candidates[k]) > 1e10) { continue; }
      let bt = m0 + 2.0 * t * m1 + t * t * m2;
      let d = length(bt);
      if (d < best) { best = d; bestT = t; }
    }
  }
  // Cubic Bezier of radii sampled at the closest t.
  let t = bestT;
  let mt = 1.0 - t;
  let r = mt * mt * mt * r0
        + 3.0 * mt * mt * t * r1
        + 3.0 * mt * t * t * r2
        + t * t * t * r3;
  return best - r;
}
fn sdTorus(p: vec3f, R: f32, r: f32) -> f32 {
  let qx = length(vec2f(p.x, p.z)) - R;
  return length(vec2f(qx, p.y)) - r;
}
// SUP — superellipsoid-style parametric primitive. ONE function covers
// sphere / box / rounded-box / bowl / hemisphere / open-top-box via four
// continuous parameters. Mirrors Unbound's _bsdf_2 + IQ rounded-box +
// shell + Y-clip composition.
//
//   r       — base radius (uniform scale of the volume)
//   blend   — 0 = sphere, 1 = box, in-between = rounded-box morph
//   shell   — 0 = solid; > 0 = hollow shell of that thickness (bowl/cup)
//   yClipN  — 0 = no clip; in (-1, 1) clips above the plane y = yClipN * r
//             positive = clip top, negative = clip bottom
//
// At blend=0: distance to a sphere of radius r.
// At blend=1: distance to a box of half-extent r.
// Intermediate: smooth morph (lerp(distance_sphere, distance_box, blend)
// is bounded but not strictly Lipschitz; safe for raymarch step sizes
// at sprite res).
//
// Shell: subtract from inside via abs(distance) - shellHalf — produces a
// hollow body. Y-clip: max with a half-plane SDF — caps the volume above
// or below a horizontal plane.
fn sdSUP(p: vec3f, r: f32, blend: f32, shell: f32, yClipN: f32) -> f32 {
  // Sphere component: |p| - r
  let dSphere = length(p) - r;
  // Box component: rounded-box-ish with corner radius proportional to r.
  let q = abs(p) - vec3f(r);
  let dBox = length(max(q, vec3f(0.0))) + min(max(q.x, max(q.y, q.z)), 0.0);
  // Linear blend.
  var d = mix(dSphere, dBox, clamp(blend, 0.0, 1.0));
  // Shell — hollow it out.
  if (shell > 0.0) {
    d = abs(d) - shell * 0.5;
  }
  // Y-clip — half-space cull above (yClipN > 0) or below (yClipN < 0).
  if (yClipN > 0.0) {
    d = max(d, p.y - yClipN * r);
  } else if (yClipN < 0.0) {
    d = max(d, -p.y + yClipN * r);
  }
  return d;
}

// Integer-bit-pattern hash. Deterministic per-cell-corner hash for sdBase
// sphere-radius randomization. Pure bit ops → no precision drift at large
// world coords.
fn intHash3(p: vec3f) -> u32 {
  let i = vec3i(p);
  var h: u32 = u32(i.x * 1597) + u32(i.y * 2143) + u32(i.z * 3083) + 7919u;
  h = (h ^ (h >> 13u)) * 2654435769u;
  h = h ^ (h >> 16u);
  return h;
}

// FBM-SDF base function (Inigo Quilez technique). Sphere grid: at every
// integer cell corner there's a sphere with a randomized radius in
// [0, 0.5). SDF to the nearest of the 8 surrounding cell corners.
// CRITICAL CONSTRAINT (per IQ): radius < 0.5 × edge length, so each
// sphere is fully contained within its cell. That guarantees the 8
// corners of the cell containing p are sufficient — no need to check
// neighbor cells. Violating this (radius ≥ 0.5) means spheres in
// unchecked cells could be closer than any of the 8 we sampled, so
// the SDF would lie about distance and finite-difference normals
// would show that as fur/jitter. Strictly Lipschitz when the rule
// is honored. Reference: https://iquilezles.org/articles/fbmsdf/
fn sdBase(p: vec3f) -> f32 {
  let pi = floor(p);
  let pf = p - pi;
  var d = 1e6;
  for (var dz: i32 = 0; dz <= 1; dz = dz + 1) {
    for (var dy: i32 = 0; dy <= 1; dy = dy + 1) {
      for (var dx: i32 = 0; dx <= 1; dx = dx + 1) {
        let off = vec3f(f32(dx), f32(dy), f32(dz));
        let cell = pi + off;
        let h = f32(intHash3(cell) & 0xFFFFFFu) * (1.0 / 16777215.0);
        // r ∈ [0, 0.5). IQ canonical: 0.5 × hash. Strict half-edge
        // bound is what makes the 8-corner-only probe correct.
        let r = 0.5 * h;
        d = min(d, length(pf - off) - r);
      }
    }
  }
  return d;
}

// Smooth variant of sdBase. Replaces hard min with polynomial smin
// over the 8 cell-corner spheres. Breaks Lipschitz (so do NOT use for
// SDF surgery in the marcher), but produces a C-infinity-smooth scalar
// field across the whole domain — no C0 ridge corners between adjacent
// spheres. Use for any procedural-noise role: tonal variation, water
// displacement, cloud density, anywhere the value is consumed as a
// number rather than a distance. Output range approximately [-0.5, 0.7].
fn sdBaseSmooth(p: vec3f) -> f32 {
  let pi = floor(p);
  let pf = p - pi;
  var d = 1.0;
  for (var dz: i32 = 0; dz <= 1; dz = dz + 1) {
    for (var dy: i32 = 0; dy <= 1; dy = dy + 1) {
      for (var dx: i32 = 0; dx <= 1; dx = dx + 1) {
        let off = vec3f(f32(dx), f32(dy), f32(dz));
        let cell = pi + off;
        let h = f32(intHash3(cell) & 0xFFFFFFu) * (1.0 / 16777215.0);
        let r = 0.5 * h;
        d = smin_k(d, length(pf - off) - r, 0.15);
      }
    }
  }
  return d;
}

// Voronoi cell-edge distance using the same sphere-grid lattice as sdBase.
// Returns F2 - F1 where F1 = distance to nearest sphere SURFACE, F2 = 2nd
// nearest. Where this is small, the point is equidistant from two spheres
// = on a Voronoi cell boundary. For crack/cell-network deformers — the
// |sdBase| < band approach gives concentric-ring CRATERS instead, since
// sdBase=0 is the sphere surface not the cell boundary.
fn voronoiEdge(p: vec3f) -> f32 {
  let pi = floor(p);
  let pf = p - pi;
  var f1 = 1e6;
  var f2 = 1e6;
  for (var dz: i32 = 0; dz <= 1; dz = dz + 1) {
    for (var dy: i32 = 0; dy <= 1; dy = dy + 1) {
      for (var dx: i32 = 0; dx <= 1; dx = dx + 1) {
        let off = vec3f(f32(dx), f32(dy), f32(dz));
        let cell = pi + off;
        let h = f32(intHash3(cell) & 0xFFFFFFu) * (1.0 / 16777215.0);
        let r = 0.5 * h;
        let dToSurf = length(pf - off) - r;
        if (dToSurf < f1) { f2 = f1; f1 = dToSurf; }
        else if (dToSurf < f2) { f2 = dToSurf; }
      }
    }
  }
  return f2 - f1;
}

// FBM-SDF noise scalar in [0, 1]. Single-octave by default; Lipschitz
// is broken intentionally (sdBaseSmooth) so the result has no creases.
// freq is cycles per world unit (default world unit is 1m in this
// renderer, so freq=10 gives 100mm features, freq=30 gives 33mm).
fn fbmSdfNoise(p: vec3f, freq: f32) -> f32 {
  let v = sdBaseSmooth(p * freq);
  return clamp(v * 1.4 + 0.4, 0.0, 1.0);
}

// Iterated domain warping with billow noise — the "displace in a loop"
// cumulus-cloud trick. Per-axis warp uses 3 INDEPENDENT FBM samples (one
// per axis) so the displacement is unbiased; previous version used
// vec3(n, n, n) which biased every iteration toward the (1,1,1)
// diagonal and produced facet/cluster artifacts. fbm3 (centered around 0)
// is used for the warp; billow3 still supplies the final density so the
// surface stays cumulus-puffy.
fn cloudDensity(p: vec3f) -> f32 {
  // Two-octave billow-folded FBM-SDF density. Macro octave gives big
  // cumulus lobes; fine octave adds cauliflower texture on top of them.
  let warpX = fbmSdfNoise(p,                             1.0) - 0.5;
  let warpY = fbmSdfNoise(p + vec3f(31.7, 11.3,  5.9),   1.0) - 0.5;
  let warpZ = fbmSdfNoise(p + vec3f( 7.1, 53.7, 19.4),   1.0) - 0.5;
  let q = p + vec3f(warpX, warpY, warpZ) * 0.7;
  let n0 = fbmSdfNoise(q, 2.3);
  let macroPuff = 1.0 - 2.0 * abs(n0 - 0.5);
  let n1 = fbmSdfNoise(q * 2.6 + vec3f(7.1, 13.3, 19.7), 1.0);
  let finePuff = (1.0 - 2.0 * abs(n1 - 0.5)) * 0.35;
  return clamp(macroPuff + finePuff - 0.15, 0.0, 1.0);
}

// Sword swipe arc — intersecting oblate spheroids clipped to an angular
// sector. The "ring" is the shell between an outer ellipsoid (flat in Y)
// and a slightly-smaller inner ellipsoid; the sector clip restricts the
// visible arc to 0..arcAngleRad in the XZ plane's atan2(z, x). Animate
// by sweeping arcAngleRad from 0 to π via CPU-side time per VFX instance.
fn sdSwipeArc(p: vec3f, majorR: f32, halfThick: f32, arcRad: f32, innerRatio: f32) -> f32 {
  let outer = sdEllipsoid(p, vec3f(majorR, halfThick, majorR));
  let innerR = majorR * innerRatio;
  let inner = sdEllipsoid(p, vec3f(innerR, halfThick * 1.6, innerR));
  let shell = max(outer, -inner);
  // Angular-sector clip. Sector spans CCW from +X axis through arcRad.
  // Two half-plane constraints: p.z >= 0 (or equivalently sin(θ) >= 0)
  // AND p on the near side of the ray at angle arcRad.
  let ca = cos(arcRad);
  let sa = sin(arcRad);
  let violateA = -p.z;                    // behind the start boundary
  let violateB = p.z * ca - p.x * sa;     // past the end boundary
  let sectorOut = max(violateA, violateB);
  return max(shell, sectorOut);
}

// Slash trail — the curve r(θ) = A·sin(ω·θ)·exp(-k·θ) in the primitive's
// YZ plane, given tube thickness in X. Approximate SDF: distance from
// point to the curve's (y,z) locus plus X-thickness. Ignores curve
// tangent so isn't a strict SDF, but the approximation holds at sprite
// resolution where thickness >> the error.
fn sdLogPolarSineTrail(p: vec3f, amp: f32, freq: f32, decay: f32, thickness: f32) -> f32 {
  let theta = atan2(p.z, p.y);
  // Only the positive-theta half produces the trail — negative theta is
  // "before the swing started." Treat as a flat cap there.
  let t = max(theta, 0.0);
  let expectedR = abs(amp * sin(freq * t)) * exp(-decay * t);
  let actualR = length(vec2f(p.y, p.z));
  let radialDist = abs(actualR - expectedR);
  return length(vec2f(radialDist, p.x)) - thickness;
}

// Lightning bolt — zigzag line along Y with multi-octave sine displacement
// in X and Z, re-seeded every frame via the time uniform so the bolt
// crackles. Caps terminate at ±halfLen so the bolt has a clean start and
// end. Thickness controls the outer radius. Approximate distance (ignores
// the curve's tangent) but good enough at sprite resolution where the
// bolt's a few pixels wide.
fn sdLightning(p: vec3f, halfLen: f32, amplitude: f32, thickness: f32, t: f32) -> f32 {
  // Outside the vertical extent: distance is just the Y-excess.
  if (abs(p.y) > halfLen) {
    return abs(p.y) - halfLen + length(vec2f(p.x, p.z)) * 0.5;
  }
  // Three-octave sine displacement. Frequencies non-harmonic so the
  // pattern doesn't loop visibly within a bolt.
  let hx = amplitude * (
    sin(p.y * 30.0 + t * 35.0) +
    sin(p.y * 67.0 + t * 28.0) * 0.5 +
    sin(p.y * 143.0 + t * 47.0) * 0.25
  );
  let hz = amplitude * (
    sin(p.y * 41.0 + t * 31.0) +
    sin(p.y * 89.0 + t * 43.0) * 0.5
  );
  return length(vec2f(p.x - hx, p.z - hz)) - thickness;
}

// Cone SDF — Inigo Quilez's capped cone. Tip at origin, base at y=-h.
// 'sc' is (sin, cos) of the half-angle (precomputed on CPU to skip trig).
// Reference: iquilezles.org/articles/distfunctions.
fn sdCone(p: vec3f, sc: vec2f, h: f32) -> f32 {
  // Parameterize as the 2D base-point in (radial, y) space.
  let q = vec2f(h * sc.x / sc.y, -h);
  let w = vec2f(length(vec2f(p.x, p.z)), p.y);
  let a = w - q * clamp(dot(w, q) / dot(q, q), 0.0, 1.0);
  let b = w - q * vec2f(clamp(w.x / q.x, 0.0, 1.0), 1.0);
  let k = sign(q.y);
  let d = min(dot(a, a), dot(b, b));
  let s = max(k * (w.x * q.y - w.y * q.x), k * (w.y - q.y));
  return sqrt(d) * sign(s);
}

// Flame SDF: capsule core whose radius is modulated by advecting 3D noise.
// Noise scrolls upward with time — gives the "licking flames" animation
// for free. Narrows toward the top via the 'taper' factor so the plume
// reads as fire rather than a fuzzy cylinder.
fn sdFlame(p: vec3f, r: f32, h: f32, noiseAmp: f32, noiseFreq: f32, t: f32) -> f32 {
  // Vertical progression [0 at bottom, 1 at top].
  let v = clamp((p.y + h) / (h * 2.0), 0.0, 1.0);
  let taper = 1.0 - v * 0.6;   // top narrower than bottom
  // Sample FBM-SDF noise at (x,z) with Y offset for upward advection.
  let nP = vec3f(p.x, p.y - t * 1.2, p.z) * noiseFreq;
  let n = fbmSdfNoise(nP, 1.0) - 0.5;
  let n2 = fbmSdfNoise(nP, 2.3) - 0.5;
  let displacement = (n + n2 * 0.4) * noiseAmp;
  let effectiveR = max(r * taper + displacement, 0.001);
  return sdCapsule(p, effectiveR, h);
}

fn evalPrim(primIdx: u32, pWorld: vec3f) -> f32 {
  let base = primIdx * 6u;      // 6 vec4s per primitive (PRIM_STRIDE_FLOATS = 24)
  let slots = bitcast<vec4u>(prims[base + 0u]);
  let primType    = slots.x;    // 'type' is a WGSL reserved keyword
  let boneIdx     = slots.z;
  let params      = prims[base + 1u];
  let offset      = prims[base + 2u].xyz;

  // Type 15 (lineCapsule) — TWO-bone path. SDF is distance from pWorld
  // to the line segment between bone A's world translation (offset by
  // 'offset' in A's local frame) and bone B's world translation. boneB
  // index is bit-cast from params.z. No worldToLocal, no rotation slot
  // — limb length is implicit, only radius needs authoring.
  if (primType == 15u) {
    let boneAWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let jointBIdx  = bitcast<u32>(params.z);
    let boneBWorld = readMat4((u.frameIdx * u.numJoints + jointBIdx) * 4u);
    let aWorld = (boneAWorld * vec4f(offset, 1.0)).xyz;
    let bWorld = boneBWorld[3].xyz;
    return sdLineCapsule3D(pWorld, aWorld, bWorld, params.x, params.y);
  }
  // Type 16 (lineCapsuleOval) — TWO-bone path with OVAL cross-section.
  // Same joint topology as type 15 but cross-plane radii are per-axis:
  //   params.x = raX, params.y = rbX, params.z = jointBIdx (u32 bitcast),
  //   params.w = boneAxisLen (used by the decal layer).
  //   rotation slot: x=raZ, y=rbZ, z=_, w=_.
  // Used for torso segments where X (lateral) and Z (forward-back)
  // radii differ — flat chest / wide hips / oval ribcage.
  if (primType == 16u) {
    let boneAWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let jointBIdx  = bitcast<u32>(params.z);
    let boneBWorld = readMat4((u.frameIdx * u.numJoints + jointBIdx) * 4u);
    let pLocal = worldToLocal(boneAWorld, pWorld);
    let bWorld = boneBWorld[3].xyz;
    let bLocal = worldToLocal(boneAWorld, bWorld);
    let profile = prims[base + 4u];
    return sdLineCapsuleOval(pLocal, bLocal,
                              params.x, profile.x, params.y, profile.y);
  }
  // Type 18 — directional-Z oval segment. Same joint topology as type
  // 16 but with separate +Z / -Z radii at each end. Used for anatomy
  // bulges baked into the segment cross-section: chest (raZpos > raZneg
  // → forward swell), glute (raZneg > raZpos at hip → backward push).
  //   params.x = raX, params.y = rbX, params.z = jointBIdx (u32),
  //   params.w = boneAxisLen (decal-t normalisation)
  //   rotation: x=raZpos, y=raZneg, z=rbZpos, w=rbZneg
  if (primType == 18u) {
    let boneAWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let jointBIdx  = bitcast<u32>(params.z);
    let boneBWorld = readMat4((u.frameIdx * u.numJoints + jointBIdx) * 4u);
    let pLocal = worldToLocal(boneAWorld, pWorld);
    let bLocal = worldToLocal(boneAWorld, boneBWorld[3].xyz);
    let profile = prims[base + 4u];
    return sdLineCapsuleOvalDirZ(pLocal, bLocal,
                                  params.x, params.y,
                                  profile.x, profile.y, profile.z, profile.w);
  }
  // Type 17 (bezierProfileCapsule) — THREE-bone path. Quadratic Bezier
  // curve in 3D through joints A (boneIdx) → B (params.x bitcast u32) →
  // C (params.y bitcast u32). Cubic Bezier profile of radii r0..r3 in
  // the rotation slot (slot 4: x=r0, y=r1, z=r2, w=r3) sampled along
  // the same parameter t. Used for limbs (round elbow / knee bends)
  // and the future anatomy curves (bicep / glute / hip flare bulges).
  // Type 23 — ribbon chain. Polyline along count contiguous bones
  // starting at boneIdx, with rectangular cross-section (halfW × halfT).
  // Cape / tail / hair / wing chains are added to the rig in order so
  // bones are guaranteed contiguous — SDF walks them dynamically.
  //   boneIdx  = first chain bone
  //   params.x = chainCount (u32 bitcast)
  //   params.y = halfW (cross-section width)
  //   params.z = halfT (cross-section thickness)
  //   params.w = unused
  if (primType == 23u) {
    let count = bitcast<u32>(params.x);
    return sdRibbonChain(pWorld, boneIdx, count, params.y, params.z);
  }
  if (primType == 17u || primType == 20u) {
    let boneAWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let jointBIdx  = bitcast<u32>(params.x);
    let jointCIdx  = bitcast<u32>(params.y);
    let boneBWorld = readMat4((u.frameIdx * u.numJoints + jointBIdx) * 4u);
    let boneCWorld = readMat4((u.frameIdx * u.numJoints + jointCIdx) * 4u);
    let aWorld = (boneAWorld * vec4f(offset, 1.0)).xyz;
    let bWorld = boneBWorld[3].xyz;
    let cWorld = boneCWorld[3].xyz;
    let profile = prims[base + 4u];
    if (primType == 20u) {
      return sdBezierExactCapsule(pWorld, aWorld, bWorld, cWorld,
                                  profile.x, profile.y, profile.z, profile.w);
    }
    return sdBezierProfileCapsule(pWorld, aWorld, bWorld, cWorld,
                                  profile.x, profile.y, profile.z, profile.w);
  }

  // Transform world → bone_local → primitive_local.
  // Pixel-copy snap: project the primitive's world center into view space
  // and snap its XY to the pixel grid, then shift the bone matrix so the
  // primitive's silhouette lands on integer pixel boundaries. This makes
  // the same SDF pose rasterize byte-identically regardless of sub-pixel
  // world translation — the hallmark of "pixels copy, not rasterize"
  // that classic sprite engines give you for free.
  var boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
  if (u.pxPerM > 0.0) {
    let worldCtr = (boneWorld * vec4f(offset, 1.0)).xyz;
    let viewCtr = (u.view * vec4f(worldCtr, 1.0)).xyz;
    let snapX = round(viewCtr.x * u.pxPerM) / u.pxPerM;
    let snapY = round(viewCtr.y * u.pxPerM) / u.pxPerM;
    // Delta in view space. Convert to world via the view rotation's
    // inverse (transpose, since lookAt is orthonormal + scale by scales).
    let deltaV = vec3f(snapX - viewCtr.x, snapY - viewCtr.y, 0.0);
    let viewRot = mat3x3<f32>(u.view[0].xyz, u.view[1].xyz, u.view[2].xyz);
    let deltaW = transpose(viewRot) * deltaV;
    boneWorld[3] = boneWorld[3] + vec4f(deltaW, 0.0);
  }
  let pBone = worldToLocal(boneWorld, pWorld);
  // Slot 4 is overloaded: standard primitives read it as a rotation
  // quaternion (xyz/w); type 14 (bent capsule) reads xyz as tipDelta in
  // primitive-local space and ignores w. The branch costs one compare
  // per prim per march step.
  let slot4 = prims[base + 4u];
  var pPrim: vec3f;
  var tipDelta: vec3f = vec3f(0.0);
  if (primType == 14u) {
    pPrim = pBone - offset;
    tipDelta = slot4.xyz;
  } else {
    let qIsZero = slot4.w == 0.0 && all(slot4.xyz == vec3f(0.0));
    let q  = select(slot4, vec4f(0.0, 0.0, 0.0, 1.0), qIsZero);
    let qInv = vec4f(-q.x, -q.y, -q.z, q.w);
    pPrim = rotateByQuat(pBone - offset, qInv);
  }

  var d: f32 = 1e9;
  switch (primType) {
    case 0u:  { d = sdSphere(pPrim, params.x); }
    case 1u:  { d = sdBox(pPrim, params.xyz); }
    case 2u:  { d = sdRoundedBox(pPrim, params.xyz, params.w); }
    case 3u:  { d = sdEllipsoid(pPrim, params.xyz); }
    case 4u:  { d = sdCylinder(pPrim, params.x, params.y); }
    case 5u:  { d = sdCapsule(pPrim, params.x, params.y); }
    case 6u:  { d = sdTorus(pPrim, params.x, params.y); }
    case 7u:  { d = sdFlame(pPrim, params.x, params.y, params.z, params.w, u.time); }
    case 8u:  { d = sdSwipeArc(pPrim, params.x, params.y, params.z, params.w); }
    case 9u:  { d = sdLogPolarSineTrail(pPrim, params.x, params.y, params.z, params.w); }
    case 10u: { d = sdLightning(pPrim, params.x, params.y, params.z, u.time); }
    case 12u: { d = sdCone(pPrim, vec2f(params.x, params.y), params.z); }
    case 13u: { d = sdChibiHead(pPrim, params.x, params.y, params.z); }
    case 14u: { d = sdBentCapsule(pPrim, params.x, params.y, tipDelta); }
    case 18u: { d = sdSUP(pPrim, params.x, params.y, params.z, params.w); }
    case 19u: { d = sdEllipsoidExact(pPrim, params.xyz); }
    case 21u: { d = sdTrapezoidalBox(pPrim, params.x, params.y, params.z, params.w); }
    case 22u: { d = sdBand(pPrim, params.x, params.y, params.z); }
    default:  { d = 1e9; }
  }

  let colorFn = slots.w;
  if (colorFn == 9u) {
    // STONE CRACKS — Voronoi cell-edge band isolation, with domain warp
    // to break the integer-grid regularity that sdBase's lattice imposes.
    // voronoiEdge returns F2-F1 (small near cell boundaries); smoothstep
    // makes the carving taper smoothly so the surface stays Lipschitz.
    let crackDepth = prims[base + 2u].w;
    if (crackDepth > 0.0) {
      let crackDensity = prims[base + 3u].y;
      // Low-frequency warp + rotation breaks axis alignment of the lattice.
      let wx = sdBaseSmooth(pWorld * (crackDensity * 0.3));
      let wy = sdBaseSmooth(pWorld * (crackDensity * 0.3) + vec3f(31.7, 11.3, 5.9));
      let wz = sdBaseSmooth(pWorld * (crackDensity * 0.3) + vec3f(7.1, 53.7, 19.4));
      let warp = vec3f(wx, wy, wz) * 0.8;
      let m = mat3x3<f32>(
        vec3f( 0.36, 0.48, 0.80),
        vec3f(-0.80, 0.60, 0.00),
        vec3f(-0.48,-0.64, 0.60),
      );
      let q0 = m * ((pWorld + warp / crackDensity) * crackDensity);
      let edge0 = voronoiEdge(q0) / crackDensity;
      // Octave 1: hairline cracks branching off macro. Multiply (rather than
      // min) so hairlines only appear where the macro edge is ALSO near —
      // sparse intersection rather than dense grid coverage. Pixel-res
      // target so non-strict Lipschitz on this composite is acceptable.
      let q1 = q0 * 2.6 + vec3f(13.7, 5.3, 41.1);
      let edge1 = voronoiEdge(q1) / (crackDensity * 2.6);
      let bandW = max(crackDepth, 0.0005);
      let macroNear = 1.0 - smoothstep(0.0, bandW * 2.0, edge0);
      let edge1Effective = mix(1.0, edge1, macroNear);
      let edgeD = min(edge0, edge1Effective);
      let mask = smoothstep(0.0, bandW, edgeD);
      d = d + (1.0 - mask) * crackDepth;
    }
  } else if (colorFn == 14u) {
    // WOOD GRAIN — voronoi cells STRETCHED along Y so the cell network
    // becomes parallel-ish streaks running vertically. Two octaves: macro
    // grain at base density, fine detail at 2.4x (between-line texture).
    // FBM domain warp on X+Z (not Y) preserves grain direction.
    let grainDepth = prims[base + 2u].w;
    if (grainDepth > 0.0) {
      let grainDensity = prims[base + 3u].y;
      let stretch = vec3f(1.0, 0.12, 1.0);
      let wx = sdBaseSmooth(pWorld * (grainDensity * 0.2)) * 0.4;
      let wz = sdBaseSmooth(pWorld * (grainDensity * 0.2) + vec3f(13.7, 5.3, 41.1)) * 0.4;
      let warp = vec3f(wx, 0.0, wz);
      // Octave 0: macro grain
      let q0 = (pWorld + warp / grainDensity) * grainDensity * stretch;
      let edge0 = voronoiEdge(q0) / grainDensity;
      // Octave 1: fine detail at 2.4x freq, 0.4x amplitude
      let q1 = q0 * 2.4 + vec3f(7.1, 13.3, 19.7);
      let edge1 = (voronoiEdge(q1) / (grainDensity * 2.4)) * 0.4;
      let edgeD = min(edge0, edge1);
      let bandW = max(grainDepth, 0.0005);
      let mask = smoothstep(0.0, bandW, edgeD);
      d = d + (1.0 - mask) * grainDepth;
    }
  } else if (colorFn == 19u) {
    // VORONOI WEATHERING / FISSURES — IQ subtractive form (Variations
    // section of fbmsdf article). Each octave carves the volume of its
    // sphere lattice OUT of the host: smax(d, -n, k) makes d larger where
    // a noise sphere's interior used to be → surface pits where spheres
    // poked through. Three octaves with rotation + per-iter shift gives
    // fractal weathering character. Lipschitz-clean throughout.
    let weatherDepth = prims[base + 2u].w;
    if (weatherDepth > 0.0) {
      // IQ-natural: s = amplitude in world units, cell size = s. Both
      // halve per octave together. weatherDensity is informational only.
      // Amp budget: 3-octave sum 1+0.5+0.25 = 1.75. s_init = depth*0.57
      // keeps total carving ≤ user-asked depth.
      var s = weatherDepth * 0.57;
      var p_iter = pWorld / (weatherDepth * 0.57);
      let m = mat3x3<f32>(
        vec3f( 0.00, -1.60, -1.20),
        vec3f( 1.60,  0.72, -0.96),
        vec3f( 1.20, -0.96,  1.28),
      );
      for (var i: i32 = 0; i < 3; i = i + 1) {
        let n = s * sdBase(p_iter);
        d = smax_k(d, -n, 0.2 * s);
        p_iter = m * p_iter + vec3f(7.0, 11.0, 13.0);
        s = 0.5 * s;
      }
    }
  } else if (colorFn == 15u) {
    // RIDGED VORONOI — same band-isolation as cracks but RAISED instead
    // of carved. voronoiEdge=0 along cell boundaries; smoothstep mask is
    // 0 there → invert to 1 → SUBTRACT from d (raises surface outward).
    // Visual: sharp ridge lines along the voronoi cell network — cliff
    // edges, mountain ridges, dragon-scale crests.
    let ridgeDepth = prims[base + 2u].w;
    if (ridgeDepth > 0.0) {
      let ridgeDensity = prims[base + 3u].y;
      let wx = sdBaseSmooth(pWorld * (ridgeDensity * 0.3));
      let wy = sdBaseSmooth(pWorld * (ridgeDensity * 0.3) + vec3f(31.7, 11.3, 5.9));
      let wz = sdBaseSmooth(pWorld * (ridgeDensity * 0.3) + vec3f(7.1, 53.7, 19.4));
      let warp = vec3f(wx, wy, wz) * 0.8;
      let m = mat3x3<f32>(
        vec3f( 0.36, 0.48, 0.80),
        vec3f(-0.80, 0.60, 0.00),
        vec3f(-0.48,-0.64, 0.60),
      );
      let q0 = m * ((pWorld + warp / ridgeDensity) * ridgeDensity);
      let edge0 = voronoiEdge(q0) / ridgeDensity;
      // Octave 1: sub-ridges along main ridges via mask-multiply (same
      // pattern as cracks 2-octave) → fractal cliff character.
      let q1 = q0 * 2.6 + vec3f(13.7, 5.3, 41.1);
      let edge1 = voronoiEdge(q1) / (ridgeDensity * 2.6);
      let bandW = max(ridgeDepth, 0.0005);
      let macroNear = 1.0 - smoothstep(0.0, bandW * 2.0, edge0);
      let edge1Effective = mix(1.0, edge1, macroNear);
      let edgeD = min(edge0, edge1Effective);
      let mask = smoothstep(0.0, bandW, edgeD);
      d = d - (1.0 - mask) * ridgeDepth;
    }
  } else if (colorFn == 27u) {
    // REACTION-DIFFUSION (Gray-Scott) — sample baked V-channel field by
    // world-XY → tiled uv. High V = raised feature (coral spot, brain
    // ridge). Pattern is emergent (not analytical), F/k-tuned CPU-side
    // at spec ingest. density (slot 3.y) sets tiles-per-meter.
    let rdDepth = prims[base + 2u].w;
    if (rdDepth > 0.0) {
      let density = prims[base + 3u].y;
      let uv = fract(pWorld.xy * density);
      let gx = u32(uv.x * f32(RD_GRID)) % RD_GRID;
      let gy = u32(uv.y * f32(RD_GRID)) % RD_GRID;
      let v = rdField[gy * RD_GRID + gx];
      d = d - v * rdDepth;                                 // SUBTRACT = raised peak
    }
  } else if (colorFn == 28u) {
    // TERRAIN — pure FBM-SDF on the slab box. Heightmap gone (was the
    // remaining fur source: height field SDF is inherently non-Lipschitz
    // wherever the surface tilts, even with smooth noise input). Macro
    // shape now comes from the FBM-SDF construction itself: slab as host,
    // sphere-grid octaves smin'd into it via IQ technique. Single octave
    // for now to avoid octave-rotation looking like domain warp; tune
    // amplitude conservatively (0.05*s inflation, 0.15*s blend — half
    // the IQ defaults) to keep the surface gentle, not harsh-rocky.
    let terrainDepth = prims[base + 2u].w;
    if (terrainDepth > 0.0) {
      // IQ FBM-SDF, NO per-pixel gating. The recipe's
      //   smax(n, dHost - 0.1*s, 0.3*s)
      // is itself the bounding mechanism: outside the slab where dHost is
      // large-positive, smax forces noise to be large-positive too, and
      // the subsequent smin keeps dHost unchanged. Per-pixel if-gates
      // produce SDF discontinuities at their boundary that the eps probe
      // reads as kinked normals (iter 109 finding).
      var dHost = d;
      // Amplitude budget: geometric series sum 1+1/2+1/4+1/8 = 1.875 over
      // 4 octaves. To keep total terrain detail ≤ terrainDepth, set s_init
      // = terrainDepth/2 → total amp ≈ 0.94 * terrainDepth (under budget).
      let s_init = terrainDepth * 0.5;
      var s = s_init;
      var p_iter = pWorld / s_init;
      let m = mat3x3<f32>(
        vec3f( 0.00, -1.60, -1.20),
        vec3f( 1.60,  0.72, -0.96),
        vec3f( 1.20, -0.96,  1.28),
      );
      let N_OCTAVES: i32 = 4;
      for (var i: i32 = 0; i < N_OCTAVES; i = i + 1) {
        let n = s * sdBase(p_iter);
        let nClipped = smax_k(n, dHost - 0.1 * s, 0.3 * s);
        dHost = smin_k(nClipped, dHost, 0.3 * s);
        // Per-octave shift (IQ video trick): translates the lattice
        // between octaves so successive sphere grids don't share corners.
        // Creates more concavities → cliff-like character vs uniform bumps.
        p_iter = m * p_iter + vec3f(7.0, 11.0, 13.0);
        s = 0.5 * s;
      }
      d = dHost;
    }
  } else if (colorFn == 29u) {
    // CLOUD — fluffy cumulus via iterated-domain-warp billow noise applied
    // to whatever base SDF (sphere/ellipsoid recommended). The "alligator
    // billow + iterative same-noise displacement" trick: density(p) is
    // computed in cloudDensity() above; SDF subtract gives outward bulges.
    let cloudDepth = prims[base + 2u].w;
    if (cloudDepth > 0.0) {
      let density = prims[base + 3u].y;
      let dens = cloudDensity(pPrim * density);
      // Subtract scaled density from SDF so the cloud bulges outward.
      // Multiply by 0.5 (IQ-style safety) since the displacement isn't
      // strictly Lipschitz and we don't want the march to overshoot.
      d = (d - dens * cloudDepth) * 0.5;
      // Flat-base truncation — real cumulus has a flat bottom at the
      // condensation level. Intersect (max) with a half-space SDF that's
      // negative above pPrim.y = -cloudDepth*0.4 and positive below →
      // cloud only renders above that plane. Lipschitz preserved (max).
      let flatBase = -(pPrim.y + cloudDepth * 0.4);
      d = max(d, flatBase);
    }
  }
  return d;
}

// 2D ellipse SDF (Inigo Quilez approximation).
fn sdEllipse2D(p: vec2f, c: vec2f, r: vec2f) -> f32 {
  let q = p - c;
  let k0 = length(q / r);
  let k1 = length(q / (r * r));
  return k0 * (k0 - 1.0) / max(k1, 1e-8);
}

// 3-vertex polygon SDF (CCW). Inlined edge tests.
fn sdPoly3(p: vec2f, a: vec2f, b: vec2f, c: vec2f) -> f32 {
  let e0 = b - a; let e1 = c - b; let e2 = a - c;
  let v0 = p - a; let v1 = p - b; let v2 = p - c;
  let pq0 = v0 - e0 * clamp(dot(v0, e0) / dot(e0, e0), 0.0, 1.0);
  let pq1 = v1 - e1 * clamp(dot(v1, e1) / dot(e1, e1), 0.0, 1.0);
  let pq2 = v2 - e2 * clamp(dot(v2, e2) / dot(e2, e2), 0.0, 1.0);
  let s = sign(e0.x * e2.y - e0.y * e2.x);
  let dx = min(min(dot(pq0, pq0), dot(pq1, pq1)), dot(pq2, pq2));
  let dy = min(min(s * (v0.x * e0.y - v0.y * e0.x),
                   s * (v1.x * e1.y - v1.y * e1.x)),
                   s * (v2.x * e2.y - v2.y * e2.x));
  return -sqrt(dx) * sign(dy);
}

// Generic 5-vertex polygon SDF (works for any convex/concave 5-gon CCW).
// Trapezoid uses sdPoly5 with the 4th vert duplicated; could specialize but
// keeping one routine is simpler.
fn sdPoly5(p: vec2f, v0: vec2f, v1: vec2f, v2: vec2f, v3: vec2f, v4: vec2f) -> f32 {
  let vs = array<vec2f, 5>(v0, v1, v2, v3, v4);
  var d = dot(p - vs[0], p - vs[0]);
  var s = 1.0;
  for (var i = 0u; i < 5u; i = i + 1u) {
    let j = (i + 4u) % 5u;
    let e = vs[j] - vs[i];
    let w = p - vs[i];
    let t = clamp(dot(w, e) / max(dot(e, e), 1e-8), 0.0, 1.0);
    let b = w - e * t;
    d = min(d, dot(b, b));
    let c1 = p.y >= vs[i].y;
    let c2 = p.y <  vs[j].y;
    let c3 = (e.x * w.y) > (e.y * w.x);
    if ((c1 && c2 && c3) || (!c1 && !c2 && !c3)) { s = -s; }
  }
  return s * sqrt(d);
}

// 4-vertex polygon (trapezoid). Same machinery as sdPoly5 with one fewer edge.
fn sdPoly4(p: vec2f, v0: vec2f, v1: vec2f, v2: vec2f, v3: vec2f) -> f32 {
  let vs = array<vec2f, 4>(v0, v1, v2, v3);
  var d = dot(p - vs[0], p - vs[0]);
  var s = 1.0;
  for (var i = 0u; i < 4u; i = i + 1u) {
    let j = (i + 3u) % 4u;
    let e = vs[j] - vs[i];
    let w = p - vs[i];
    let t = clamp(dot(w, e) / max(dot(e, e), 1e-8), 0.0, 1.0);
    let b = w - e * t;
    d = min(d, dot(b, b));
    let c1 = p.y >= vs[i].y;
    let c2 = p.y <  vs[j].y;
    let c3 = (e.x * w.y) > (e.y * w.x);
    if ((c1 && c2 && c3) || (!c1 && !c2 && !c3)) { s = -s; }
  }
  return s * sqrt(d);
}

// Chibi head — pixel-fitted from anime reference (IoU 0.99 on side fit).
// 3D shape = max(side(p.zy), front(p.xy)) — intersection of two extruded
// 2D silhouettes. Each silhouette = min(ellipse, polygon(s)) for cranium +
// jaw / chin geometry.
//   R         = world-space scale (head spans ~R in each axis from centre)
//   chibi_t   = [0..1] compresses lower jaw toward cranium bottom
//   chin_tuck = [0..1] pulls chin tip back in z (less protrusion)
// Params from /tmp/sdf_research/head_3d_params.json.
fn sdChibiHead(p: vec3f, R: f32, chibi_t: f32, chin_tuck: f32) -> f32 {
  let np = p / max(R, 1e-6);

  // SIDE silhouette in (z, y) plane.
  let pzy = vec2f(np.z, np.y);
  let dSE = sdEllipse2D(pzy, vec2f(0.0, 0.0838), vec2f(0.4417, 0.4162));

  // Side polygon — 5 verts (jaw + chin region). Compress lower verts
  // toward cranium-bottom for chibi, pull chin tip back for tuck.
  let craniumBotY = 0.0838 - 0.4162;   // ellipse cy - ry
  let v0 = vec2f(0.4110, -0.0548);
  let v1 = vec2f(-0.2353, -0.0548);
  // v2, v3 are below craniumBotY → compress for chibi
  var v2y = -0.5049; var v3y = -0.5000;
  if (chibi_t > 0.0) {
    let f = chibi_t * 0.65;
    v2y = v2y * (1.0 - f) + craniumBotY * f;
    v3y = v3y * (1.0 - f) + craniumBotY * f;
  }
  // Chin tip (v3) z gets pulled back for tuck + chibi
  var v3z = 0.3681 - 0.15 * chin_tuck - 0.08 * chibi_t;
  let v2 = vec2f(-0.1946, v2y);
  let v3 = vec2f(v3z, v3y);
  let v4 = vec2f(0.4936, -0.2183);
  let dSP = sdPoly5(pzy, v0, v1, v2, v3, v4);
  let dSide = min(dSE, dSP);

  // FRONT silhouette in (x, y) plane.
  let pxy = vec2f(np.x, np.y);
  let dFE = sdEllipse2D(pxy, vec2f(0.0, 0.0858), vec2f(0.4142, 0.4142));

  // Trap (4 verts) — compresses for chibi (y_bot pulled up toward y_top).
  let trapYTop = -0.0656;
  let baseTrapYBot = -0.3788;
  let trapYBot = baseTrapYBot * (1.0 - chibi_t * 0.40) + trapYTop * (chibi_t * 0.40);
  let trapTopHw = 0.3856;
  let trapBotHw = 0.2745 * (1.0 - 0.10 * chibi_t);
  let dFT = sdPoly4(pxy,
    vec2f( trapTopHw, trapYTop),
    vec2f(-trapTopHw, trapYTop),
    vec2f(-trapBotHw, trapYBot),
    vec2f( trapBotHw, trapYBot));

  // Triangle (3 verts) — chin point. Pinned to trap bottom; height shrinks for chibi.
  let triYTop = trapYBot;
  let triHeight = (-0.5 - (-0.3788)) * (1.0 - 0.65 * chibi_t);   // negative
  let triYBot = triYTop + triHeight;
  let triTopHw = trapBotHw;
  let dFTri = sdPoly3(pxy,
    vec2f( triTopHw, triYTop),
    vec2f(-triTopHw, triYTop),
    vec2f(0.0, triYBot));

  let dFront = min(dFE, min(dFT, dFTri));

  // 3D intersection (max in SDF terms) — head is the volume that's inside
  // BOTH the side silhouette extrusion AND the front silhouette extrusion.
  // Multiply by R to convert normalized distance back to world units.
  return max(dSide, dFront) * max(R, 1e-6);
}

struct SceneHit {
  dist:    f32,
  primIdx: u32,
}

// Polynomial smooth-min from Inigo Quilez — C1 continuous, zero-cost on
// modern GPUs. k is the blend-band width; k=0.05 gives a ~5cm soft crease.
fn smin_k(a: f32, b: f32, k: f32) -> f32 {
  let kk = max(k, 1e-6);
  let h = clamp(0.5 + 0.5 * (b - a) / kk, 0.0, 1.0);
  return mix(b, a, h) - kk * h * (1.0 - h);
}
fn smax_k(a: f32, b: f32, k: f32) -> f32 {
  let kk = max(k, 1e-6);
  let h = clamp(0.5 - 0.5 * (b - a) / kk, 0.0, 1.0);
  return mix(b, a, h) + kk * h * (1.0 - h);
}
// CHAMFER blend operators — Mercury hg_sdf canonical formulas. Sharper
// than smin (smin produces fillets / soft creases; chamfer produces
// hard 45° bevels). Useful for armor, weapons, mecha — anything where
// edges should READ as edges, not as soft transitions. The constant
// 0.7071 is sin(45°) = cos(45°) = sqrt(0.5).
fn cmin_k(a: f32, b: f32, k: f32) -> f32 {
  let kk = max(k, 1e-6);
  return min(min(a, b), (a - kk + b) * 0.7071067811865476);
}
fn cmax_k(a: f32, b: f32, k: f32) -> f32 {
  let kk = max(k, 1e-6);
  return max(max(a, b), (a + kk + b) * 0.7071067811865476);
}
// Chamfer-subtract (carve b out of a with a beveled edge).
fn cdiff_k(a: f32, b: f32, k: f32) -> f32 {
  let kk = max(k, 1e-6);
  return max(max(a, -b), (a + kk - b) * 0.7071067811865476);
}

const MAX_GROUPS: u32 = 16u;

// Dual-map pattern (Inigo Quilez, WsSBzh):
//   wantDetail = 0  → smooth SDF for raymarch + shadow. No FBM displacement,
//                     no step-size collapse. Cheap steps, clean convergence.
//   wantDetail = 1  → same SDF plus per-primitive FBM displacement at the
//                     hit point. Called ONLY from sceneNormal so the 3-band
//                     cel lighting shades the detail surface (pores, grain,
//                     wood). Real 3D normal mapping — not a 2D texture.
fn sceneSDF(pWorld: vec3f, wantDetail: u32) -> SceneHit {
  var best = 1e9;
  var bestIdx = 0u;
  // Per-group accumulators. Groups are 1-indexed in the primitive record;
  // we store 0-indexed here. Attribution (groupIdx) picks argmin of the
  // RAW (pre-blend) distance among positive-contributing primitives in the
  // group — so the winning palette belongs to the closest member, which
  // is how "cheek-red near the cheek, skin elsewhere" falls out for free.
  var groupDist:    array<f32, 16>;
  var groupArgmin:  array<f32, 16>;
  var groupIdx:     array<u32, 16>;
  for (var g = 0u; g < MAX_GROUPS; g = g + 1u) {
    groupDist[g]   = 1e9;
    groupArgmin[g] = 1e9;
    groupIdx[g]    = 0u;
  }
  for (var i = 0u; i < u.numPrims; i = i + 1u) {
    let base = i * 6u;
    let cfg  = prims[base + 3u];
    let groupPacked = bitcast<u32>(cfg.z);
    let blendR = cfg.w;

    // Per-primitive occlusion — skip if the primitive's world bounding
    // sphere is farther than the current best. Multi-bone primitives
    // (line capsule, bezier limb) need their bounding to enclose ALL
    // joints, not just bone A — otherwise a ray pointing down the limb
    // axis skips the prim and you get holes at extreme camera angles.
    let slots0     = bitcast<vec4u>(prims[base + 0u]);
    let primType0  = slots0.x;
    let params0    = prims[base + 1u];
    let offset0    = prims[base + 2u].xyz;
    let bone0      = readMat4((u.frameIdx * u.numJoints + slots0.z) * 4u);
    let aWorld0    = (bone0 * vec4f(offset0, 1.0)).xyz;

    var worldCtr: vec3f;
    var radiusWorld: f32;
    if (primType0 == 17u || primType0 == 20u) {
      // Bezier through joints A / B / C. params.x, .y bitcast u32 = jointB, jointC.
      let jointBIdx0 = bitcast<u32>(params0.x);
      let jointCIdx0 = bitcast<u32>(params0.y);
      let boneB0 = readMat4((u.frameIdx * u.numJoints + jointBIdx0) * 4u);
      let boneC0 = readMat4((u.frameIdx * u.numJoints + jointCIdx0) * 4u);
      let bW0 = boneB0[3].xyz;
      let cW0 = boneC0[3].xyz;
      worldCtr = (aWorld0 + bW0 + cW0) / 3.0;
      let prof = prims[base + 4u];
      let maxR = max(max(prof.x, prof.y), max(prof.z, prof.w));
      let dA = distance(worldCtr, aWorld0);
      let dB = distance(worldCtr, bW0);
      let dC = distance(worldCtr, cW0);
      radiusWorld = max(max(dA, dB), dC) + maxR + abs(blendR) + 0.05;
    } else if (primType0 == 15u) {
      // Line capsule between joint A (this bone) and joint B (params.z u32).
      let jointBIdx0 = bitcast<u32>(params0.z);
      let boneB0 = readMat4((u.frameIdx * u.numJoints + jointBIdx0) * 4u);
      let bW0 = boneB0[3].xyz;
      worldCtr = (aWorld0 + bW0) * 0.5;
      let segHalf = distance(aWorld0, bW0) * 0.5;
      let maxR = max(abs(params0.x), abs(params0.y));
      radiusWorld = segHalf + maxR + abs(blendR) + 0.05;
    } else {
      // Single-bone primitive — local-radius bounded by sum of |params|.
      let c00 = bone0[0].xyz;
      let c10 = bone0[1].xyz;
      let c20 = bone0[2].xyz;
      let maxScaleSq = max(max(dot(c00, c00), dot(c10, c10)), dot(c20, c20));
      let radiusLocal = abs(params0.x) + abs(params0.y) + abs(params0.z) + abs(params0.w) + 0.05;
      worldCtr = aWorld0;
      radiusWorld = radiusLocal * sqrt(maxScaleSq) + abs(blendR);
    }
    let sphereDist = distance(pWorld, worldCtr) - radiusWorld;
    if (sphereDist >= best) { continue; }

    var d = evalPrim(i, pWorld);
    // Iter 109: dual-map detail displacement removed. It was a legacy
    // hack from the heightmap era — adding noise to the SDF only on the
    // normal pass to fake fine detail. fbmSdfNoise is non-Lipschitz, and
    // applying it asymmetrically (silhouette vs normal) is exactly the
    // pattern that produces kinked normals on an otherwise-clean surface.
    // FBM-SDF construction in evalPrim already provides Lipschitz detail.
    // Group ID is 1..15 in low 4 bits; bit 4 (0x10) flags CHAMFER blend
    // mode (Mercury hg_sdf canonical bevel) instead of polynomial smin
    // (default). Bit 4 set => sharp 45° bevel; bit 4 clear => smooth
    // fillet. The flag survives through groupPacked; we mask it out
    // for the group index lookup.
    let chamferFlag = (groupPacked & 0x10u) != 0u;
    let groupId     = groupPacked & 0x0Fu;
    if (groupId == 0u || groupId > MAX_GROUPS) {
      // Standalone — hard union into scene.
      if (d < best) { best = d; bestIdx = i; }
    } else {
      let g = groupId - 1u;
      // Additive primitives own the attribution; subtractors carve and
      // leave attribution to whoever was already there.
      if (blendR >= 0.0 && d < groupArgmin[g]) {
        groupArgmin[g] = d;
        groupIdx[g]    = i;
      }
      if (blendR > 0.0) {
        if (chamferFlag) {
          groupDist[g] = cmin_k(groupDist[g], d, blendR);
        } else {
          groupDist[g] = smin_k(groupDist[g], d, blendR);
        }
      } else if (blendR < 0.0) {
        if (chamferFlag) {
          groupDist[g] = cdiff_k(groupDist[g], d, -blendR);
        } else {
          groupDist[g] = smax_k(groupDist[g], -d, -blendR);
        }
      } else {
        groupDist[g] = min(groupDist[g], d);
      }
    }
  }
  // Fold groups — each group contributes one blended surface.
  for (var g = 0u; g < MAX_GROUPS; g = g + 1u) {
    if (groupDist[g] < best) {
      best    = groupDist[g];
      bestIdx = groupIdx[g];
    }
  }
  return SceneHit(best, bestIdx);
}

// Normals sample the DETAIL SDF (wantDetail=1), so the 3-band cel lighting
// shades the FBM-displaced surface rather than the smooth base geometry.
// This is the dual-map win: skin reads as porous, wood reads as grainy,
// even though the silhouette the march resolved is the smooth hull.
//
// Tetrahedral 4-sample gradient (Inigo Quilez, "Normals for an SDF"):
// 4 samples at the corners of a regular tetrahedron instead of 6 along
// the axes. ~33% cheaper than central differences, visually identical
// for the SDF surfaces we render. The k vector (1,-1) pattern ensures
// each axis gets two +eps and two -eps samples across the 4 corners,
// so the sum reconstructs the gradient correctly up to normalisation.
// True if the hit primitive is a terrain (colorFunc=28). Used to widen
// the normal-sampling epsilon so the normal picks up macro slope from
// the IQ heightmap SDF (which varies slowly across the X-Z plane).
fn isHitTerrain(primIdx: u32) -> bool {
  let base = primIdx * 6u;
  let cf = bitcast<vec4u>(prims[base + 0u]).w & 0x3Fu;
  return cf == 28u;
}
// True if hit is a cloud (colorFunc=29). Iterated billow noise has wild
// gradients at small scales — eps=2mm produces faceted normals; eps=6mm
// averages over multiple noise cells for smooth fluffy lighting.
fn isHitCloud(primIdx: u32) -> bool {
  let base = primIdx * 6u;
  let cf = bitcast<vec4u>(prims[base + 0u]).w & 0x3Fu;
  return cf == 29u;
}

fn sceneNormal(pWorld: vec3f, eps: f32) -> vec3f {
  let k = vec2f(1.0, -1.0);
  return normalize(
    k.xyy * sceneSDF(pWorld + k.xyy * eps, 1u).dist +
    k.yyx * sceneSDF(pWorld + k.yyx * eps, 1u).dist +
    k.yxy * sceneSDF(pWorld + k.yxy * eps, 1u).dist +
    k.xxx * sceneSDF(pWorld + k.xxx * eps, 1u).dist
  );
}

// Self-shadow was previously baked here via a 6-step softshadow march
// and packed into normal.a. That made lighting non-deferred (raymarch
// shading didn't respect the outline pass's configured light rig) and
// layered quantised shadow artefacts on top of clean cel lighting.
// Lighting is fully deferred now (see deferred_lighting_doctrine memory
// entry). If self-shadow returns, it goes in the post pass with the
// actual light directions, not here.

struct FsOut {
  @location(0) color:  vec4f,
  @location(1) normal: vec4f,
  @location(2) depth:  vec4f,
}

@fragment
fn fs_main(in: VsOut) -> FsOut {
  var out: FsOut;
  // DIAGNOSTIC: if we have no primitives at all, output magenta so the
  // problem surface visibly differs from "rays miss real geometry" (which
  // shows checker background downstream).
  if (u.numPrims == 0u) {
    out.color  = vec4f(1.0, 0.0, 1.0, 1.0);
    out.normal = vec4f(0.5, 0.5, 1.0, 1.0);
    out.depth  = vec4f(0.5, 0.0, 0.0, 1.0);
    return out;
  }

  // Reconstruct the ray from NDC. Near-plane point (ndc, 0) and far-plane
  // point (ndc, 1) both unprojected; ray goes from near → far.
  let nearPoint = u.invViewProj * vec4f(in.ndc, 0.0, 1.0);
  let farPoint  = u.invViewProj * vec4f(in.ndc, 1.0, 1.0);
  let ro = nearPoint.xyz / nearPoint.w;
  let rd = normalize((farPoint.xyz / farPoint.w) - ro);
  let totalDist = length((farPoint.xyz / farPoint.w) - ro);

  var t = 0.0;
  var hitPrim = 0u;
  var hit = false;
  // Adaptive SDF march with safety factor.
  let stepSafety = 0.85;
  for (var step = 0u; step < u.maxSteps; step = step + 1u) {
    let p = ro + rd * t;
    let s = sceneSDF(p, 0u);
    if (s.dist < 0.001) { hitPrim = s.primIdx; hit = true; break; }
    t = t + s.dist * stepSafety;
    if (t > totalDist) { break; }
  }

  if (!hit) {
    if (u.bgMode == 0u) {
      // Transparent miss — character/skeleton demos composite over checker
      // alpha. alpha=0 keeps the lit pass from drawing anything.
      out.color  = vec4f(0.0, 0.0, 0.0, 0.0);
      out.normal = vec4f(0.5, 0.5, 1.0, 0.0);
      out.depth  = vec4f(1.0, 0.0, 0.0, 1.0);
      return out;
    }
    // Atmospheric sky — terrain scenes only.
    let sunDirSky = normalize(vec3f(0.7, 0.5, 0.3));
    let cosTheta = dot(rd, sunDirSky);
    let rayleighPhase = 0.75 * (1.0 + cosTheta * cosTheta);
    let mieG = 0.76;
    let mieGG = mieG * mieG;
    let miePhase = (1.0 - mieGG)
                 / pow(max(1.0 + mieGG - 2.0 * mieG * cosTheta, 0.001), 1.5);
    let skyZenith   = vec3f(0.20, 0.42, 0.78);
    let skyHorizon  = vec3f(0.62, 0.74, 0.86);
    let sunGlow     = vec3f(1.00, 0.78, 0.45);
    let elev = max(rd.y, 0.0);
    let horizonMix = pow(1.0 - elev, 2.5);
    let baseSky = mix(skyZenith, skyHorizon, horizonMix);
    let skyCol = baseSky * (0.65 + 0.35 * rayleighPhase) + sunGlow * miePhase * 0.05;
    out.color  = vec4f(skyCol, 1.0);
    out.normal = vec4f(0.5, 0.5, 1.0, 0.0);
    out.depth  = vec4f(1.0, 1.0, 0.0, 1.0);   // unlit flag in .g
    return out;
  }

  let hitPos = ro + rd * t;
  // Normal sampling. Wider eps for noise-heavy deformers so high-frequency
  // gradient artifacts get averaged out (faceted-lighting fix):
  //   2mm  base prims (sphere, brick, etc.)
  //   4mm  terrain (IQ heightmap, slow X-Z gradient)
  //   6mm  clouds (iterated-DW billow noise has wild local gradients)
  var normalEps = 0.002;
  // Terrain eps widened 4→8mm. Detail FBM smallest octave wavelength is
  // ~14mm at density=4; finer eps was sampling within a quarter-wavelength
  // → gradient estimate captured every micro-fluctuation as normal jitter.
  // 8mm averages across more of the noise's local variation = smoother
  // physical-looking surface normals at the cost of some macro-detail
  // blurring (negligible since cell-feature size is well above 8mm).
  if (isHitCloud(hitPrim))   { normalEps = 0.006; }
  let n = sceneNormal(hitPos, normalEps);

  // Procedural color: pick between slotA and slotB based on colorFunc.
  // Crisp 2-3 band palette selection — no interpolated RGB, stays on
  // the discrete palette so the pixel-art contract holds.
  let base = hitPrim * 6u;   // 6 vec4s per primitive (PRIM_STRIDE_FLOATS = 24)
  let slots = bitcast<vec4u>(prims[base + 0u]);
  let colorCfg = prims[base + 3u];
  let slotsB = bitcast<vec4u>(prims[base + 3u]);
  let slotA = slots.y;
  // colorFunc stored in lower 6 bits; bit 6 (0x40) = unlit, bit 7 (0x80) = shiny.
  let cfPacked = slots.w;
  let colorFunc = cfPacked & 0x3Fu;
  let primUnlit = (cfPacked & 0x40u) != 0u;
  let primShiny = (cfPacked & 0x80u) != 0u;
  let slotB = slotsB.x;
  let colorExtent = colorCfg.y;

  var slot: u32 = slotA;
  if (colorFunc == 1u) {
    // gradientY: primitive-local Y from hit. Needs hit in primitive-local
    // space — reuse the bone inverse for the primitive's bone.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localY = worldToLocal(boneWorld, hitPos).y - offset.y;
    let normY = clamp((localY + colorExtent) / (2.0 * colorExtent), 0.0, 1.0);
    // 3 bands, crisp: [0, 0.33] → slotA, [0.33, 0.66] → midBand (slotA+1),
    // [0.66, 1] → slotB. This assumes slotA and slotB bracket a 3-slot
    // ramp in the palette — common pixel-art convention.
    if (normY > 0.66) { slot = slotB; }
    else if (normY > 0.33) { slot = slotA + 1u; }
    else { slot = slotA; }
  } else if (colorFunc == 2u) {
    // pulsate: toggle between A and B at frequency colorExtent (Hz).
    if (sin(u.time * colorExtent * 6.2831853) > 0.0) { slot = slotB; }
  } else if (colorFunc == 3u) {
    // radialFade: slot depends on radial distance from primitive origin.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localP = worldToLocal(boneWorld, hitPos) - offset;
    let r = length(localP);
    if (r > colorExtent) { slot = slotB; }
  } else if (colorFunc == 4u) {
    // STRIPES — alternating slotA/slotB bands along primitive-local Y.
    // colorExtent = stripes per metre. The +1024 offset keeps the floor()
    // arg positive across the [-1m, +1m] range we expect for sprite-tier
    // primitive-local coordinates, so u32 parity test is unambiguous.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localY = worldToLocal(boneWorld, hitPos).y - offset.y;
    let band = u32(floor(localY * colorExtent + 1024.0));
    if ((band & 1u) == 1u) { slot = slotB; }
  } else if (colorFunc == 5u) {
    // DOTS — circular spots tiled on the primitive-local XY plane.
    // colorExtent = cell size in metres; dot radius is 0.30 × cell.
    // Cells centre on (cell, cell) lattice; fract() wraps positions
    // into [0, 1) per cell so any sub-pixel sample finds its nearest dot.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localP = worldToLocal(boneWorld, hitPos) - offset;
    let cell = max(colorExtent, 0.001);
    let cellX = fract(localP.x / cell + 1024.5) - 0.5;
    let cellY = fract(localP.y / cell + 1024.5) - 0.5;
    if ((cellX * cellX + cellY * cellY) < 0.09) { slot = slotB; }
  } else if (colorFunc == 6u) {
    // CHECKER — 3D checkerboard in primitive-local space. colorExtent
    // = cell size in metres. Parity of (cx + cy + cz) selects A/B.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localP = worldToLocal(boneWorld, hitPos) - offset;
    let cell = max(colorExtent, 0.001);
    let cx = u32(floor(localP.x / cell + 1024.0));
    let cy = u32(floor(localP.y / cell + 1024.0));
    let cz = u32(floor(localP.z / cell + 1024.0));
    if (((cx + cy + cz) & 1u) == 1u) { slot = slotB; }
  } else if (colorFunc == 7u) {
    // CHEVRON — V-shaped bands in primitive-local space. Stripe parameter
    // is |x| + y, so a horizontal slice gives a /\\ shape pointing UP.
    // colorExtent = chevrons per metre. Used for heraldic capes.
    let boneIdx = slots.z;
    let boneWorld = readMat4((u.frameIdx * u.numJoints + boneIdx) * 4u);
    let offset = prims[base + 2u].xyz;
    let localP = worldToLocal(boneWorld, hitPos) - offset;
    let v = abs(localP.x) + localP.y;
    let band = u32(floor(v * colorExtent + 1024.0));
    if ((band & 1u) == 1u) { slot = slotB; }
  } else if (colorFunc == 8u) {
    // WORLD-Y STRIPES — same idea as colorFunc 4 but the band parameter
    // is the world-space Y of the hit, NOT primitive-local Y. Result: a
    // chain of cape segments shows ONE continuous striped pattern instead
    // of each segment showing its own self-centred stripes (which would
    // visibly jump at segment seams). Stripes-per-metre stays the same.
    let band = u32(floor(hitPos.y * colorExtent + 1024.0));
    if ((band & 1u) == 1u) { slot = slotB; }
  } else if (colorFunc == 27u) {
    // REACTION-DIFFUSION — peaks (high V) take slot B (the accent palette
    // entry, dark by default for sunken-feature deformers but raised here),
    // valleys keep slot A. Threshold at V=0.3 — Gray-Scott V settles in
    // [0, ~0.5] for typical F/k presets so 0.3 picks "established" peaks.
    let densityRD = colorExtent;
    let uvRD = fract(hitPos.xy * densityRD);
    let gxRD = u32(uvRD.x * f32(RD_GRID)) % RD_GRID;
    let gyRD = u32(uvRD.y * f32(RD_GRID)) % RD_GRID;
    let vRD = rdField[gyRD * RD_GRID + gxRD];
    if (vRD > 0.3) { slot = slotB; }
  } else if (colorFunc == 29u) {
    // CLOUD — single solid color (slot 0, white by default). All shading
    // comes from the deferred lit pass via surface normals. Avoids the
    // visible-dither/visible-grid issue from picking palette slots
    // based on noise output (which exposes value-noise grid artifacts).
    // Color variation can be added later via better noise (Perlin/
    // Simplex) — value noise's grid alignment shows through under
    // any threshold-based palette pick.
  } else if (colorFunc == 30u) {
    // BIND-COORD DECAL (T1) — sleeve / pant-leg / belly clothing layer.
    // World hit is transformed back to the primitive's bone-local frame
    // (the bind pose). Project to 1D t along local +Y. Layer alpha
    // drops out past colorExtent.
    //   slotA = base palette (skin / pants)
    //   slotB = layer palette (shirt / armor)
    //   colorExtent = cutoff t in [0, 1]: 0 = full base, 1 = full layer
    //   prims[base+1].z = bone-axis length in metres (T-pose chain
    //                    root→end distance). Used to normalise t.
    let decalBoneIdx = slots.z;
    let decalBoneWorld = readMat4((u.frameIdx * u.numJoints + decalBoneIdx) * 4u);
    let pBoneLocal = worldToLocal(decalBoneWorld, hitPos);
    // params.w holds the bone-axis length for type-15 segment prims
    // (params.z holds the jointBIdx as u32 for the segment SDF).
    let boneAxisLen = max(prims[base + 1u].w, 0.05);
    // Cutoff in METERS along bone-local +Y, not normalized t. When the
    // garment is full-length (colorExtent >= 1) we add a margin so the
    // hemispherical capsule cap at the bone tip — which extends past
    // boneAxisLen by the capsule radius — is still covered. Adjacent
    // segments' decals overlap the cap region from their own bone
    // frames, so the two overlap at the joint and there is no skin
    // crack at the elbow / knee.
    //
    // SCALE-AWARE: when proportion presets squash a bone's Y axis
    // (e.g. chibi legs at scale.y = 0.55), worldToLocal returns
    // pBoneLocal.y INFLATED by 1/scale.y because it normalizes by the
    // squared basis magnitude. The cap radius is fixed in WORLD meters
    // (it's a sphere in world space), so its projection into bone-local
    // Y is also inflated by 1/scale.y. Without compensation, the chibi
    // knee/elbow cap extends 0.085 / 0.55 ≈ 0.155 past boneAxisLen and
    // breaks through a 0.09 margin. Scale the margin by the same factor.
    let s1sq = dot(decalBoneWorld[1].xyz, decalBoneWorld[1].xyz);
    let invScaleY = 1.0 / max(sqrt(s1sq), 0.05);
    let capMargin = 0.09 * invScaleY;
    let coverFull = (colorExtent >= 1.0);
    let coverM = select(colorExtent * boneAxisLen, boneAxisLen + capMargin, coverFull);
    let alphaDecal = smoothstep(coverM + 0.02, coverM - 0.02, pBoneLocal.y);
    if (alphaDecal > 0.5) { slot = slotB; }
  }
  // Terrain auto-zoning (rock/snow split) intentionally disabled so we can
  // audit FBM-SDF geometry without color-pick noise. Slot stays slotA.

  // Face marks — surface-color overrides that live on a bone. Iterate
  // each mark; if it's attached to THIS primitive's bone, project the
  // world hit into bone-local space, test the mark's shape, override
  // the palette slot on an inside hit. Front-facing only (hit must be
  // on the same side as the mark's normal).
  let hitBoneIdx = slots.z;
  for (var m = 0u; m < u.numFaceMarks; m = m + 1u) {
    let mb = m * 4u;
    let mSlots = bitcast<vec4u>(faceMarks[mb + 0u]);
    let mShape  = mSlots.x;
    let mBone   = mSlots.y;
    let mPalette= mSlots.z;
    let mEnable = mSlots.w;
    if (mEnable == 0u) { continue; }
    if (mBone != hitBoneIdx) { continue; }

    let mCenter = faceMarks[mb + 1u].xyz;
    let mNormal = normalize(faceMarks[mb + 2u].xyz);
    let mSize   = faceMarks[mb + 3u].xy;

    // Hit in mark's bone-local space.
    let mBoneWorld = readMat4((u.frameIdx * u.numJoints + hitBoneIdx) * 4u);
    let localHit   = worldToLocal(mBoneWorld, hitPos);
    let d = localHit - mCenter;

    // Reject back side of tangent plane (behind the face for a front-
    // facing mark). Prevents eyes painting on the back of the head.
    if (dot(d, mNormal) < 0.0) { continue; }

    // Build a 2D tangent basis orthogonal to the mark's normal. Pick a
    // reference up vector that isn't parallel to the normal.
    let refUp = select(vec3f(0.0, 1.0, 0.0), vec3f(1.0, 0.0, 0.0), abs(mNormal.y) > 0.9);
    let tX    = normalize(cross(refUp, mNormal));
    let tY    = cross(mNormal, tX);
    let uC    = dot(d, tX);
    let vC    = dot(d, tY);

    var inside = false;
    if (mShape == 0u) {          // circle
      inside = (uC * uC + vC * vC) < (mSize.x * mSize.x);
    } else if (mShape == 1u) {   // rect
      inside = abs(uC) < mSize.x && abs(vC) < mSize.y;
    } else if (mShape == 2u) {   // line (thick horizontal: thickness = size.y)
      inside = abs(uC) < mSize.x && abs(vC) < mSize.y;
    }

    if (inside) {
      slot = mPalette;
      break;
    }
  }

  var tint = palette[slot].rgb;

  // Zone weights kept as zero — auto-zoning disabled (see slot-pick block
  // above). Downstream effects (rock/snow color blend, strata, snow tonal
  // variation, cloud shadow) become no-ops, leaving uniform tint.
  let landWeight: f32 = 0.0;
  let rockW: f32 = 0.0;
  let snowW: f32 = 0.0;

  // Smooth color blending across terrain zone boundaries. Eliminates
  // hard rock/grass and snow/rock seams. Slot remains the dominant zone
  // for downstream effects; only the visible COLOR smooths.
  if (colorFunc == 28u && slot != 3u && slot != 7u && slot != 6u) {
    let grassColor = palette[slotA].rgb;
    let rockColor  = palette[4].rgb;
    let snowColor  = palette[slotB].rgb;
    let landColor = mix(grassColor, rockColor, rockW);
    tint = mix(landColor, snowColor, snowW);
  }

  // Tonal variation — patch-scale brightness modulation, FBM-SDF sourced
  // (sdBaseSmooth, no C0 creases). Two scales summed for FBM-style detail.
  // Snow zones get 30% strength (fresh snow IS uniform), grass/rock full
  // strength, water/foam zero (handled by landWeight).
  if (colorFunc == 28u) {
    let coarse = fbmSdfNoise(hitPos, 8.0);
    let fine   = fbmSdfNoise(hitPos, 26.0);
    let toneM  = clamp(coarse * 0.7 + fine * 0.3, 0.0, 1.0);
    let toneStrength = (1.0 - 0.7 * snowW) * landWeight;
    tint = tint * mix(1.0, mix(0.78, 1.10, toneM), toneStrength);
  }
  // Sedimentary strata + snow texture — both weighted by their zone weight
  // multiplied by landWeight so neither effect leaks onto water (could
  // happen at high-altitude water for snowW, or detail noise edges for
  // rockW). Triple-gate is now a single mul, mathematically clean.
  if (colorFunc == 28u) {
    let yNoise = (fbmSdfNoise(hitPos, 35.0) - 0.5) * 0.008;
    let yPos = hitPos.y + yNoise;
    let strata = sin(yPos * 280.0) + sin(yPos * 460.0 + 1.7) * 0.5;
    let strataM = strata / 1.5 * 0.5 + 0.5;
    let strataMod = mix(0.78, 1.10, strataM);
    tint = tint * mix(1.0, strataMod, rockW * landWeight);
    let snowVar = fbmSdfNoise(hitPos, 60.0);
    let snowMod = mix(0.88, 1.02, snowVar);
    tint = tint * mix(1.0, snowMod, snowW * landWeight);
  }
  // Depth to NDC [0, 1] (near=0, far=1). Project hit to clip space then
  // normalize — but we can shortcut via the ray parametrization since
  // we already have totalDist (near→far world distance).
  let dNdc = clamp(t / totalDist, 0.0, 1.0);
  // Animated cloud shadows on terrain only. NOT baked into tint — packed
  // into depth.b as direct-light visibility (lit pass multiplies only the
  // KEY contribution by it). Real cloud shadows block sun, not ambient/
  // fill — baking into tint was wrong and made shadowed areas read as
  // dead-flat instead of "dimmer-but-still-skylit".
  var cloudShadowFactor: f32 = 1.0;
  if (colorFunc == 28u) {
    let cloudUV = hitPos.xz * 9.0 + vec2f(u.time * 0.03, u.time * 0.018);   // Y-up
    let cloud = fbmSdfNoise(vec3f(cloudUV.x, cloudUV.y, 0.0), 1.0);
    let cloudShadow = mix(0.84, 1.0, smoothstep(0.40, 0.62, cloud));
    cloudShadowFactor = mix(1.0, cloudShadow, landWeight);
  }

  // Pure G-buffer: tint + normal + depth. Lighting is fully deferred to
  // the outline pass, which combines ambient + key + fill light per
  // pixel using the surface normal. No per-material PBR for now —
  // metalness/roughness/AO removed pending need for them. Foundational
  // light wire-up (tinted ambient + dual-direction key/fill) is the
  // current priority; per-material specularity, point lights, and
  // contact shadows layer on top later.
  // G-buffer flags packed into spare channels:
  //   normal.a = shiny flag (1 = specular hot-spot on lit side, 0 = matte)
  //   depth.g  = unlit flag (1 = pass albedo through unmodified, 0 = lit)
  // Outline pass reads both to gate per-pixel shading decisions.
  // Per-pixel shiny override: water gets specular highlights, fading
  // SMOOTHLY out to matte across the shore band. Previously this was a
  // hard slot-identity gate (slot 3 or 7 → shiny=1, else baseline) which
  // produced a visible specular pop at the waterline. Now smoothed by
  // landWeight: full water = shiny=1, full land = baseline, narrow blend
  // through foam/wet-shore.
  let baselineShiny = select(0.0, 1.0, primShiny);
  var shinyOut = baselineShiny;
  if (colorFunc == 28u) {
    shinyOut = mix(1.0, baselineShiny, landWeight);
  }

  // Ambient occlusion + sun shadows on terrain — both packed into the
  // G-buffer, NOT baked into tint. Lit pass applies them per light:
  //   - directVis (depth.b): blocks KEY light only (sun shadow + cloud)
  //   - aoFactor  (depth.a): blocks AMBIENT + FILL (indirect light)
  // Real local geometric occlusion (AO) attenuates indirect/sky-bounce
  // light reaching a crevice, while letting direct sun illuminate the
  // open side. Tint*AO was darkening direct too, making crevices read
  // as dead-flat. New formulation = brighter, more dimensional shadows.
  var sunShadowFactor: f32 = 1.0;
  var aoFactor: f32 = 1.0;
  if (colorFunc == 28u) {
    if (landWeight > 0.01) {
      // AO probe — 4 samples along the surface normal.
      var occ = 0.0;
      let aoStep = 0.005;
      for (var ks = 1u; ks <= 4u; ks = ks + 1u) {
        let aoP = hitPos + n * (f32(ks) * aoStep);
        let sd = sceneSDF(aoP, hitPrim).dist;
        occ = occ + clamp(f32(ks) * aoStep - sd, 0.0, aoStep) * (1.0 / aoStep) * 0.25;
      }
      let ao = clamp(1.0 - occ * 0.7, 0.45, 1.0);
      aoFactor = mix(1.0, ao, landWeight);
      // Soft sun shadow (IQ trick).
      let sunDir = normalize(vec3f(0.7, 0.5, 0.3));
      var t = 0.002;
      var k = 1.0;
      let maxT = 0.10;
      let kSharp = 16.0;
      for (var ssi = 0u; ssi < 24u; ssi = ssi + 1u) {
        let sp = hitPos + sunDir * t;
        let sd = sceneSDF(sp, hitPrim).dist;
        if (sd < 0.0003) { k = 0.0; break; }
        k = min(k, sd * kSharp / t);
        t = t + sd * 0.7;
        if (t > maxT) { break; }
      }
      let shadow = clamp(k, 0.0, 1.0);
      let shadowMod = mix(0.40, 1.0, shadow);
      sunShadowFactor = mix(1.0, shadowMod, landWeight);
    }
  }
  let directVis = sunShadowFactor * cloudShadowFactor;

  out.color  = vec4f(tint, 1.0);
  out.normal = vec4f(n * 0.5 + 0.5, shinyOut);
  out.depth  = vec4f(dNdc, select(0.0, 1.0, primUnlit), directVis, aoFactor);
  return out;
}
`

export interface RaymarchRenderer {
  /** Draw the current primitive set into the active render pass's MRT
   *  targets. The caller supplies view + proj as Float32Array column-
   *  major mat4s — same shape the cube renderer expects. */
  draw(
    pass: GPURenderPassEncoder,
    view: Float32Array,
    proj: Float32Array,
    eye: [number, number, number],
    frameIdx: number,
  ): void
  setPrimitives(prims: RaymarchPrimitive[]): void
  setPaletteSlot(slot: number, r: number, g: number, b: number, a?: number): void
  rebind(vat: VATData): void
  /** Seconds since engine start. Drives flame/smoke/trail evolution. */
  setTime(t: number): void
  /** Pixels per world meter for the current render target. When >0, each
   *  primitive's center snaps to the view-space pixel grid before SDF
   *  evaluation — guarantees "pixels copy, not rasterize" as the
   *  character moves sub-pixel. Set to 0 to disable. */
  setPxPerM(pxPerM: number): void
  /** Upload a set of face marks — bone-attached color strokes. Each mark
   *  overrides the palette slot for any hit pixel whose primitive belongs
   *  to the mark's bone AND whose in-plane offset lies within the mark's
   *  shape. No SDF geometry change; pure color override. Max 16 marks. */
  setFaceMarks(marks: FaceMark[]): void
  /** Upload a CPU-baked Gray-Scott reaction-diffusion field. Expected
   *  length = 128² = 16384 floats (the V channel after N iterations).
   *  Sampled by colorFunc=27 deformer for raised coral/brain/zebra
   *  patterns. Always-bound; default-zero so RD is silent unless authored. */
  setRDField(data: Float32Array): void
  /** Scene-wide water level for the terrain deformer (colorFunc=28),
   *  expressed as fraction of terrainDepth in [0, 1]. Below this altitude
   *  the palette overrides to slot 3 (water blue). */
  setTerrainWaterLevel(level: number): void
  /** Scene background on raymarch miss. 'transparent' (default) writes
   *  alpha=0 so the demo's checker / page background shows through —
   *  required for character demos. 'sky' renders an atmospheric Rayleigh+
   *  Mie sky used by terrain scenes. */
  setBgMode(mode: 'transparent' | 'sky'): void

  // --- Static cache (for pass-based compositing) ---
  // Typical usage pattern from the caller:
  //
  //   if (cacheKeyChanged) {
  //     raymarch.marchIntoCache(encoder, view, proj, eye, frameIdx)
  //   }
  //   // ... inside the scene render pass ...
  //   raymarch.blitCacheToPass(scenePass)
  //
  // When the cache key is stable (camera parked, character in an idle
  // pose, palette unchanged), `marchIntoCache` is skipped and the frame
  // cost collapses to one fullscreen blit. For a truly static scene, the
  // raymarch runs once per camera change, not once per frame.

  /** Allocate or resize the cache framebuffer (color + normal + depth +
   *  depth-stencil) to match a render target resolution. Must be called
   *  before marchIntoCache / blitCacheToPass; safe to call repeatedly —
   *  no-op when already sized. */
  resizeCache(width: number, height: number): void
  /** Execute a full raymarch pass into the cache's own framebuffer.
   *  Creates its own render pass on the encoder. Call only when the
   *  cache-key fingerprint has changed. */
  marchIntoCache(
    encoder: GPUCommandEncoder,
    view: Float32Array,
    proj: Float32Array,
    eye: [number, number, number],
    frameIdx: number,
  ): void
  /** Fullscreen-blit the cache's color/normal/depth textures into the
   *  3 MRT outputs of the currently-active render pass. Cheap — one
   *  fullscreen triangle with three texture loads per pixel.
   *  `offsetPx` shifts where the cached content lands on screen — use
   *  this to let camera pan reuse cached pixels without re-marching.
   *  Out-of-range samples read as alpha=0 (background). */
  blitCacheToPass(pass: GPURenderPassEncoder, offsetPx?: [number, number]): void
}

export function createRaymarchRenderer(
  device: GPUDevice,
  format: GPUTextureFormat,
  initialPrims: RaymarchPrimitive[],
  palette: Float32Array,
  vat: VATData,
  options: { maxSteps?: number } = {},
): RaymarchRenderer {
  const maxSteps = options.maxSteps ?? 256

  const shader = device.createShaderModule({ code: RAYMARCH_SHADER, label: 'raymarch-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'raymarch-pipeline',
    layout: 'auto',
    vertex: { module: shader, entryPoint: 'vs_main' },
    fragment: {
      module: shader,
      entryPoint: 'fs_main',
      targets: [{ format }, { format }, { format }],
    },
    primitive: { topology: 'triangle-list' },
    // Fullscreen triangle — don't participate in depth testing. But the
    // render pass always binds a depth attachment (to share the scene
    // pass with the cube renderer), so the pipeline must declare a
    // matching format or validation fails.
    depthStencil: {
      format: 'depth24plus-stencil8',
      depthWriteEnabled: false,
      depthCompare: 'always',
    },
  })

  // Uniform layout (floats, zero-based indexing):
  //   [0..15]  invViewProj
  //   [16..31] view
  //   [32..35] eye + pad
  //   [36..39] u32 view: numPrims, numJoints, frameIdx, maxSteps
  //   [40..43] time, pxPerM, pad, pad
  // Total = 44 floats = 176 bytes. Round to 192 for alignment slack.
  const uniformBuffer = device.createBuffer({
    label: 'raymarch-uniforms',
    size: 192,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(48)
  let currentTime = 0
  let currentPxPerM = 0     // 0 disables per-primitive pixel snap
  let currentTerrainWaterLevel = 0  // 0 disables water cap (terrain renders bare)
  let currentBgMode: 0 | 1 = 0      // 0 = transparent miss; 1 = atmospheric sky

  // Primitives storage buffer — sized to grow a bit; reallocated if
  // setPrimitives() exceeds capacity.
  let primsBuffer: GPUBuffer | null = null
  let primsCapacity = 0

  const paletteBuffer = device.createBuffer({
    label: 'raymarch-palette',
    size: palette.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(paletteBuffer, 0, palette)

  // Face marks — small storage buffer of bone-attached color strokes
  // (eyes, mouths, tears, scars). 16 slots × 4 vec4f = 1 KB. Upload
  // once per character; not per frame.
  const MAX_FACE_MARKS = 16
  const faceMarksBuffer = device.createBuffer({
    label: 'raymarch-face-marks',
    size: MAX_FACE_MARKS * 16 * 4,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  // Upload a zeroed buffer so even with numFaceMarks=0 the storage
  // binding is valid.
  device.queue.writeBuffer(faceMarksBuffer, 0, new Float32Array(MAX_FACE_MARKS * 16))
  let numFaceMarks = 0

  // Reaction-diffusion field — 128² f32 storage buffer sampled by colorFunc=27
  // (Gray-Scott RD deformer). Default-zero so the binding is valid even when
  // no RD prim is in the scene. Caller invokes setRDField(data) with a
  // CPU-baked V-channel result.
  const RD_GRID_SIZE = 128
  const rdFieldBuffer = device.createBuffer({
    label: 'raymarch-rd-field',
    size: RD_GRID_SIZE * RD_GRID_SIZE * 4,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(rdFieldBuffer, 0, new Float32Array(RD_GRID_SIZE * RD_GRID_SIZE))

  let currentVat = vat
  let numPrims = 0
  let bindGroup: GPUBindGroup | null = null

  function uploadPrimitives(list: RaymarchPrimitive[]) {
    numPrims = list.length
    const needed = Math.max(1, list.length)
    if (!primsBuffer || needed > primsCapacity) {
      primsBuffer?.destroy()
      primsCapacity = Math.max(needed, primsCapacity * 2)
      primsBuffer = device.createBuffer({
        label: 'raymarch-primitives',
        size: primsCapacity * PRIM_STRIDE_FLOATS * 4,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      })
    }
    const data = new ArrayBuffer(needed * PRIM_STRIDE_FLOATS * 4)
    const f32 = new Float32Array(data)
    const u32 = new Uint32Array(data)
    for (let i = 0; i < list.length; i++) {
      const p = list[i]
      const base = i * PRIM_STRIDE_FLOATS
      // vec4<u32> in slot 0: type, slotA, boneIdx, colorFunc.
      // colorFunc lower 6 bits = function ID; bit 6 (0x40) packs the
      // unlit flag; bit 7 (0x80) packs the shiny flag. Both saved as
      // overflow bits so we don't grow per-prim storage.
      const cfPacked =
        ((p.colorFunc ?? 0) & 0x3F) |
        (p.unlit ? 0x40 : 0) |
        (p.shiny ? 0x80 : 0)
      u32[base + 0] = p.type
      u32[base + 1] = p.paletteSlot
      u32[base + 2] = p.boneIdx
      u32[base + 3] = cfPacked
      // vec4<f32> in slot 1: params. Some types overload params slots
      // as u32 bone indices — write those through the u32 view so the
      // shader's bitcast<u32>(...) reads the right bits.
      //   type 15 (lineCapsule):           params.z = jointBIdx
      //   type 17 (bezierProfileCapsule):  params.x = jointBIdx,
      //                                    params.y = jointCIdx
      if (p.type === 17 || p.type === 20) {
        u32[base + 4] = p.params[0]
        u32[base + 5] = p.params[1]
      } else if (p.type === 23) {
        // Ribbon chain: params[0] = chainCount (u32). params[1..3] are
        // halfW/halfT/_, kept as floats.
        u32[base + 4] = p.params[0]
        f32[base + 5] = p.params[1]
      } else {
        f32[base + 4] = p.params[0]
        f32[base + 5] = p.params[1]
      }
      if (p.type === 15 || p.type === 16 || p.type === 18) {
        // Types 15, 16, 18 all encode jointBIdx in params.z (= base+6).
        // Pack as u32 so the shader's `bitcast<u32>(params.z)` reads
        // the actual integer index, not the bit pattern of a float.
        u32[base + 6] = p.params[2]
      } else {
        f32[base + 6] = p.params[2]
      }
      if (p.type === 23) {
        // Ribbon chain: params.w = bone-1 index (u32 bitcast), so pack
        // through the u32 view.
        u32[base + 7] = p.params[3]
      } else {
        f32[base + 7] = p.params[3]
      }
      // vec4<f32> in slot 2: offset in bone (xyz) + detailAmplitude (w)
      f32[base + 8] = p.offsetInBone[0]
      f32[base + 9] = p.offsetInBone[1]
      f32[base + 10] = p.offsetInBone[2]
      f32[base + 11] = p.detailAmplitude ?? 0
      // vec4 in slot 3: slotB (u32), colorExtent (f32), blendGroup (u32 — bit 4 = chamfer flag), blendRadius (f32 signed)
      u32[base + 12] = p.paletteSlotB ?? p.paletteSlot
      f32[base + 13] = p.colorExtent ?? 0.1
      u32[base + 14] = (p.blendGroup ?? 0) | (p.chamfer ? 0x10 : 0)
      f32[base + 15] = p.blendRadius ?? 0
      // vec4 in slot 4: rotation quaternion (x, y, z, w). Identity if absent.
      // Type 23 (ribbon chain) overloads this slot to store bone indices
      // 2..5 — pack through the u32 view in that case.
      const rot = p.rotation ?? [0, 0, 0, 1]
      if (p.type === 23) {
        u32[base + 16] = rot[0]
        u32[base + 17] = rot[1]
        u32[base + 18] = rot[2]
        u32[base + 19] = rot[3]
      } else {
        f32[base + 16] = rot[0]
        f32[base + 17] = rot[1]
        f32[base + 18] = rot[2]
        f32[base + 19] = rot[3]
      }
      // vec4 in slot 5: wearFn (u32), wearDepth (f32), wearDensity (f32),
      // terrainFlowDepth (f32). wearFn=0 → secondary deformer off.
      // terrainFlowDepth used only by colorFunc=28; coexists with wear
      // because terrain prims rarely also have wear and slot is wasted
      // otherwise.
      u32[base + 20] = p.wearFn ?? 0
      f32[base + 21] = p.wearDepth ?? 0
      f32[base + 22] = p.wearDensity ?? 0
      f32[base + 23] = p.terrainFlowDepth ?? 0
    }
    device.queue.writeBuffer(primsBuffer!, 0, data)
    rebuildBindGroup()
  }

  function rebuildBindGroup() {
    if (!primsBuffer) return
    bindGroup = device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: uniformBuffer } },
        { binding: 1, resource: { buffer: primsBuffer } },
        { binding: 2, resource: { buffer: currentVat.buffer } },
        { binding: 3, resource: { buffer: paletteBuffer } },
        { binding: 4, resource: { buffer: faceMarksBuffer } },
        { binding: 5, resource: { buffer: rdFieldBuffer } },
      ],
    })
  }

  uploadPrimitives(initialPrims)

  // --- CPU mat4 helpers (minimal; avoid pulling in vec.ts here) ---
  function mulMat4(out: Float32Array, a: Float32Array, b: Float32Array) {
    for (let col = 0; col < 4; col++) {
      for (let row = 0; row < 4; row++) {
        out[col * 4 + row] =
          a[row]      * b[col * 4]     +
          a[row + 4]  * b[col * 4 + 1] +
          a[row + 8]  * b[col * 4 + 2] +
          a[row + 12] * b[col * 4 + 3]
      }
    }
  }
  function invertMat4(out: Float32Array, m: Float32Array): boolean {
    const a00 = m[0],  a01 = m[1],  a02 = m[2],  a03 = m[3]
    const a10 = m[4],  a11 = m[5],  a12 = m[6],  a13 = m[7]
    const a20 = m[8],  a21 = m[9],  a22 = m[10], a23 = m[11]
    const a30 = m[12], a31 = m[13], a32 = m[14], a33 = m[15]
    const b00 = a00 * a11 - a01 * a10, b01 = a00 * a12 - a02 * a10
    const b02 = a00 * a13 - a03 * a10, b03 = a01 * a12 - a02 * a11
    const b04 = a01 * a13 - a03 * a11, b05 = a02 * a13 - a03 * a12
    const b06 = a20 * a31 - a21 * a30, b07 = a20 * a32 - a22 * a30
    const b08 = a20 * a33 - a23 * a30, b09 = a21 * a32 - a22 * a31
    const b10 = a21 * a33 - a23 * a31, b11 = a22 * a33 - a23 * a32
    let det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06
    if (!det) return false
    det = 1.0 / det
    out[0]  = (a11 * b11 - a12 * b10 + a13 * b09) * det
    out[1]  = (a02 * b10 - a01 * b11 - a03 * b09) * det
    out[2]  = (a31 * b05 - a32 * b04 + a33 * b03) * det
    out[3]  = (a22 * b04 - a21 * b05 - a23 * b03) * det
    out[4]  = (a12 * b08 - a10 * b11 - a13 * b07) * det
    out[5]  = (a00 * b11 - a02 * b08 + a03 * b07) * det
    out[6]  = (a32 * b02 - a30 * b05 - a33 * b01) * det
    out[7]  = (a20 * b05 - a22 * b02 + a23 * b01) * det
    out[8]  = (a10 * b10 - a11 * b08 + a13 * b06) * det
    out[9]  = (a01 * b08 - a00 * b10 - a03 * b06) * det
    out[10] = (a30 * b04 - a31 * b02 + a33 * b00) * det
    out[11] = (a21 * b02 - a20 * b04 - a23 * b00) * det
    out[12] = (a11 * b07 - a10 * b09 - a12 * b06) * det
    out[13] = (a00 * b09 - a01 * b07 + a02 * b06) * det
    out[14] = (a31 * b01 - a30 * b03 - a32 * b00) * det
    out[15] = (a20 * b03 - a21 * b01 + a22 * b00) * det
    return true
  }

  const viewProj = new Float32Array(16)
  const invViewProj = new Float32Array(16)

  function writeUniforms(view: Float32Array, proj: Float32Array, eye: [number, number, number], frameIdx: number) {
    mulMat4(viewProj, proj, view)
    invertMat4(invViewProj, viewProj)
    // Match the WGSL Uniforms layout in the shader:
    //   [0..15]  invViewProj
    //   [16..31] view
    //   [32..35] eye.xyz + pad
    //   [36..39] u32: numPrims, numJoints, frameIdx, maxSteps
    //   [40..43] time, pxPerM, _pad, _pad
    uniformData.set(invViewProj, 0)
    uniformData.set(view, 16)
    uniformData[32] = eye[0]
    uniformData[33] = eye[1]
    uniformData[34] = eye[2]
    uniformData[35] = 0
    const u32 = new Uint32Array(uniformData.buffer, 36 * 4, 4)
    u32[0] = numPrims
    u32[1] = currentVat.numInstances
    u32[2] = frameIdx
    u32[3] = maxSteps
    uniformData[40] = currentTime
    uniformData[41] = currentPxPerM
    const uNum = new Uint32Array(uniformData.buffer, 42 * 4, 1)
    uNum[0] = numFaceMarks
    uniformData[43] = currentTerrainWaterLevel
    const uBg = new Uint32Array(uniformData.buffer, 44 * 4, 1)
    uBg[0] = currentBgMode
    device.queue.writeBuffer(uniformBuffer, 0, uniformData)
  }

  // --- Static cache infrastructure ----------------------------------------
  // The cache owns its own framebuffer (color + normal + depth + depth-stencil)
  // at the target render resolution. When the caller's "cache key" (camera,
  // pose, palette) is stable across frames, `marchIntoCache` is skipped and
  // the frame reduces to one fullscreen blit from cache into the scene pass.
  // That's the win: a parked camera on a static scene costs one blit per
  // frame, not N march iterations × M primitives.

  const BLIT_SHADER = /* wgsl */ `
struct BlitU {
  offsetPx: vec2i,    // pixel shift: output (X,Y) samples cache at (X-offsetPx.x, Y-offsetPx.y)
  _pad:     vec2i,
}
@group(0) @binding(0) var colorTex:  texture_2d<f32>;
@group(0) @binding(1) var normalTex: texture_2d<f32>;
@group(0) @binding(2) var depthTex:  texture_2d<f32>;
@group(0) @binding(3) var<uniform> u: BlitU;

struct VsOut { @builtin(position) clip: vec4f }

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  let corners = array<vec2f, 3>(
    vec2f(-1.0, -1.0),
    vec2f( 3.0, -1.0),
    vec2f(-1.0,  3.0),
  );
  var out: VsOut;
  out.clip = vec4f(corners[vid], 0.0, 1.0);
  return out;
}

struct FsOut {
  @location(0) color:  vec4f,
  @location(1) normal: vec4f,
  @location(2) depth:  vec4f,
}

@fragment
fn fs_main(in: VsOut) -> FsOut {
  let outPx = vec2i(in.clip.xy);
  let srcPx = outPx - u.offsetPx;
  let dim = vec2i(textureDimensions(colorTex, 0));
  var out: FsOut;
  // Out-of-range sample → background (alpha=0). WGSL textureLoad at
  // OOB coords returns zero, so the default color/normal/depth get
  // interpreted as "miss" downstream. This is how camera pan reveals
  // fresh background on one edge and hides pixels on the other.
  if (srcPx.x < 0 || srcPx.y < 0 || srcPx.x >= dim.x || srcPx.y >= dim.y) {
    out.color  = vec4f(0.0, 0.0, 0.0, 0.0);
    out.normal = vec4f(0.5, 0.5, 1.0, 0.0);
    out.depth  = vec4f(1.0, 0.0, 0.0, 0.0);
    return out;
  }
  out.color  = textureLoad(colorTex,  srcPx, 0);
  out.normal = textureLoad(normalTex, srcPx, 0);
  out.depth  = textureLoad(depthTex,  srcPx, 0);
  return out;
}
`

  const blitShader = device.createShaderModule({ code: BLIT_SHADER, label: 'raymarch-cache-blit' })
  const blitPipeline = device.createRenderPipeline({
    label: 'raymarch-cache-blit-pipeline',
    layout: 'auto',
    vertex: { module: blitShader, entryPoint: 'vs_main' },
    fragment: {
      module: blitShader,
      entryPoint: 'fs_main',
      targets: [{ format }, { format }, { format }],
    },
    primitive: { topology: 'triangle-list' },
    depthStencil: {
      format: 'depth24plus-stencil8',
      depthWriteEnabled: false,
      depthCompare: 'always',
    },
  })

  let cacheW = 0
  let cacheH = 0
  let cacheColor:  GPUTexture | null = null
  let cacheNormal: GPUTexture | null = null
  let cacheDepth:  GPUTexture | null = null
  let cacheDepthStencil: GPUTexture | null = null
  let cacheColorView:  GPUTextureView | null = null
  let cacheNormalView: GPUTextureView | null = null
  let cacheDepthView:  GPUTextureView | null = null
  let cacheDepthStencilView: GPUTextureView | null = null
  let cacheBlitBindGroup: GPUBindGroup | null = null

  // Blit offset uniform — 2 i32 (pixel dx, dy) + 2 i32 pad = 16 bytes.
  // Updated on every blit via writeBuffer. Enables camera-pan reuse of
  // cached pixels without re-marching.
  const blitOffsetBuffer = device.createBuffer({
    label: 'raymarch-cache-blit-offset',
    size: 16,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const blitOffsetData = new Int32Array(4)

  function resizeCache(w: number, h: number) {
    if (cacheW === w && cacheH === h && cacheColor) return
    cacheColor?.destroy()
    cacheNormal?.destroy()
    cacheDepth?.destroy()
    cacheDepthStencil?.destroy()
    const usage = GPUTextureUsage.RENDER_ATTACHMENT | GPUTextureUsage.TEXTURE_BINDING
    cacheColor  = device.createTexture({ label: 'raymarch-cache-color',  size: [w, h], format, usage })
    cacheNormal = device.createTexture({ label: 'raymarch-cache-normal', size: [w, h], format, usage })
    cacheDepth  = device.createTexture({ label: 'raymarch-cache-depth',  size: [w, h], format, usage })
    cacheDepthStencil = device.createTexture({
      label: 'raymarch-cache-depthstencil',
      size: [w, h],
      format: 'depth24plus-stencil8',
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
    })
    cacheColorView  = cacheColor.createView()
    cacheNormalView = cacheNormal.createView()
    cacheDepthView  = cacheDepth.createView()
    cacheDepthStencilView = cacheDepthStencil.createView()
    cacheBlitBindGroup = device.createBindGroup({
      layout: blitPipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: cacheColorView },
        { binding: 1, resource: cacheNormalView },
        { binding: 2, resource: cacheDepthView },
        { binding: 3, resource: { buffer: blitOffsetBuffer } },
      ],
    })
    cacheW = w
    cacheH = h
  }

  return {
    draw(pass, view, proj, eye, frameIdx) {
      if (!bindGroup) return
      writeUniforms(view, proj, eye, frameIdx)
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.draw(3)
    },
    setPrimitives(list) {
      uploadPrimitives(list)
    },
    setPaletteSlot(slot, r, g, b, a = 1) {
      const tmp = new Float32Array([r, g, b, a])
      device.queue.writeBuffer(paletteBuffer, slot * 16, tmp)
    },
    rebind(newVat) {
      currentVat = newVat
      rebuildBindGroup()
    },
    setTime(t) {
      currentTime = t
    },
    setFaceMarks(marks) {
      const n = Math.min(marks.length, MAX_FACE_MARKS)
      const data = new ArrayBuffer(MAX_FACE_MARKS * 16 * 4)
      const f32 = new Float32Array(data)
      const u32 = new Uint32Array(data)
      for (let i = 0; i < n; i++) {
        const m = marks[i]
        const b = i * 16
        const shapeId = m.shape === 'circle' ? 0 : m.shape === 'rect' ? 1 : 2
        u32[b + 0] = shapeId
        u32[b + 1] = m.boneIdx
        u32[b + 2] = m.paletteSlot
        u32[b + 3] = 1                              // enable
        f32[b + 4] = m.localCenter[0]
        f32[b + 5] = m.localCenter[1]
        f32[b + 6] = m.localCenter[2]
        f32[b + 7] = 0
        f32[b + 8] = m.localNormal[0]
        f32[b + 9] = m.localNormal[1]
        f32[b + 10] = m.localNormal[2]
        f32[b + 11] = 0
        f32[b + 12] = m.size[0]
        f32[b + 13] = m.size[1]
        f32[b + 14] = 0
        f32[b + 15] = 0
      }
      device.queue.writeBuffer(faceMarksBuffer, 0, data)
      numFaceMarks = n
    },
    setPxPerM(v) {
      currentPxPerM = v
    },
    setRDField(data) {
      // Upload a CPU-baked Gray-Scott V-channel field. Expected length =
      // RD_GRID_SIZE² (128² = 16384). Shorter inputs zero-pad, longer
      // inputs clip — both keep the binding valid for any caller.
      const need = RD_GRID_SIZE * RD_GRID_SIZE
      const out = data.length === need ? data
        : (() => { const f = new Float32Array(need); f.set(data.subarray(0, Math.min(data.length, need))); return f })()
      device.queue.writeBuffer(rdFieldBuffer, 0, out)
    },
    setTerrainWaterLevel(level) {
      // Scene-wide water level as fraction of terrainDepth [0, 1]. Below
      // this altitude, terrain palette switches to water slot 3.
      currentTerrainWaterLevel = Math.max(0, Math.min(1, level))
    },
    setBgMode(mode) {
      currentBgMode = mode === 'sky' ? 1 : 0
    },
    resizeCache(w, h) {
      resizeCache(w, h)
    },
    marchIntoCache(encoder, view, proj, eye, frameIdx) {
      if (!bindGroup || !cacheColorView || !cacheNormalView || !cacheDepthView || !cacheDepthStencilView) return
      writeUniforms(view, proj, eye, frameIdx)
      const pass = encoder.beginRenderPass({
        label: 'raymarch-cache-march',
        colorAttachments: [
          { view: cacheColorView,  loadOp: 'clear', storeOp: 'store', clearValue: { r: 0, g: 0, b: 0, a: 0 } },
          { view: cacheNormalView, loadOp: 'clear', storeOp: 'store', clearValue: { r: 0.5, g: 0.5, b: 1, a: 0 } },
          { view: cacheDepthView,  loadOp: 'clear', storeOp: 'store', clearValue: { r: 1, g: 0, b: 0, a: 0 } },
        ],
        depthStencilAttachment: {
          view: cacheDepthStencilView,
          depthLoadOp: 'clear',
          depthStoreOp: 'store',
          depthClearValue: 1.0,
          stencilLoadOp: 'clear',
          stencilStoreOp: 'store',
          stencilClearValue: 0,
        },
      })
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.draw(3)
      pass.end()
    },
    blitCacheToPass(pass, offsetPx) {
      if (!cacheBlitBindGroup) return
      const dx = Math.round(offsetPx?.[0] ?? 0)
      const dy = Math.round(offsetPx?.[1] ?? 0)
      blitOffsetData[0] = dx
      blitOffsetData[1] = dy
      device.queue.writeBuffer(blitOffsetBuffer, 0, blitOffsetData)
      pass.setPipeline(blitPipeline)
      pass.setBindGroup(0, cacheBlitBindGroup)
      pass.draw(3)
    },
  }
}
