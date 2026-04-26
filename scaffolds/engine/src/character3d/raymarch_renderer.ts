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
  _pad2:       f32,
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

// --- 3D value noise --------------------------------------------------
// Minimal hash + trilinear-interpolated value noise for VFX displacement.
// Cheap (~15 ops per sample) and deterministic; good enough for flame /
// smoke / fog at sprite resolution. Not Perlin or simplex — we can swap
// to something with smoother gradients if a specific effect demands it.

fn hash3(p: vec3f) -> f32 {
  let h = dot(p, vec3f(127.1, 311.7, 74.7));
  return fract(sin(h) * 43758.5453123);
}

fn noise3(p: vec3f) -> f32 {
  let i = floor(p);
  let f = fract(p);
  let u = f * f * (vec3f(3.0) - 2.0 * f);   // smoothstep interpolation
  let n000 = hash3(i + vec3f(0.0, 0.0, 0.0));
  let n100 = hash3(i + vec3f(1.0, 0.0, 0.0));
  let n010 = hash3(i + vec3f(0.0, 1.0, 0.0));
  let n110 = hash3(i + vec3f(1.0, 1.0, 0.0));
  let n001 = hash3(i + vec3f(0.0, 0.0, 1.0));
  let n101 = hash3(i + vec3f(1.0, 0.0, 1.0));
  let n011 = hash3(i + vec3f(0.0, 1.0, 1.0));
  let n111 = hash3(i + vec3f(1.0, 1.0, 1.0));
  let x00 = mix(n000, n100, u.x);
  let x10 = mix(n010, n110, u.x);
  let x01 = mix(n001, n101, u.x);
  let x11 = mix(n011, n111, u.x);
  let y0 = mix(x00, x10, u.y);
  let y1 = mix(x01, x11, u.y);
  return mix(y0, y1, u.z);
}

// 3-octave FBM — centered roughly on zero, bounded roughly in [-0.5, 0.5].
// Used by the dual-map pattern (sceneSDF_detail) for per-surface micro
// displacement that drives correct 3D normal shading. Frequencies chosen
// non-harmonic so the pattern doesn't feel grid-locked.
fn fbm3(p: vec3f) -> f32 {
  var acc = 0.0;
  var amp = 0.5;
  var q = p;
  acc = acc + amp * (noise3(q) - 0.5);
  amp = amp * 0.5;
  q = q * 2.07;
  acc = acc + amp * (noise3(q) - 0.5);
  amp = amp * 0.5;
  q = q * 2.11;
  acc = acc + amp * (noise3(q) - 0.5);
  return acc;
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

// NoiseCloud SDF — 3D value-noise field thresholded into a surface, clipped
// to a bounding box. Advected slowly with time so it drifts. Not a true SDF
// (the noise doesn't have a Lipschitz bound) but at sprite resolution with
// small step sizes the artifacts are invisible. Good for fog/smoke/dust.
fn sdNoiseCloud(p: vec3f, hx: f32, hy: f32, hz: f32, threshold: f32, t: f32) -> f32 {
  // Box distance (clipping volume).
  let boxD = sdBox(p, vec3f(hx, hy, hz));
  // Noise sampled with time-based drift. Negate & offset so "inside" the
  // threshold is negative and the surface is at noise = threshold.
  let nP = vec3f(p.x + t * 0.15, p.y - t * 0.08, p.z) * 2.0;
  let n = noise3(nP) + 0.5 * noise3(nP * 2.13);
  let cloudD = threshold - n * 0.67;       // normalize second-octave scale
  // Box-clamped intersection. Treat cloud as a soft field; scale down so
  // it doesn't over-dominate the march-step size.
  return max(boxD, cloudD * 0.35);
}

// Flame SDF: capsule core whose radius is modulated by advecting 3D noise.
// Noise scrolls upward with time — gives the "licking flames" animation
// for free. Narrows toward the top via the 'taper' factor so the plume
// reads as fire rather than a fuzzy cylinder.
fn sdFlame(p: vec3f, r: f32, h: f32, noiseAmp: f32, noiseFreq: f32, t: f32) -> f32 {
  // Vertical progression [0 at bottom, 1 at top].
  let v = clamp((p.y + h) / (h * 2.0), 0.0, 1.0);
  let taper = 1.0 - v * 0.6;   // top narrower than bottom
  // Sample noise at (x,z) with Y offset for upward advection.
  let nP = vec3f(p.x, p.y - t * 1.2, p.z) * noiseFreq;
  let n = noise3(nP) - 0.5;
  // Add a second octave at double frequency for finer licks.
  let n2 = noise3(nP * 2.3) - 0.5;
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
  // Type 17 (bezierProfileCapsule) — THREE-bone path. Quadratic Bezier
  // curve in 3D through joints A (boneIdx) → B (params.x bitcast u32) →
  // C (params.y bitcast u32). Cubic Bezier profile of radii r0..r3 in
  // the rotation slot (slot 4: x=r0, y=r1, z=r2, w=r3) sampled along
  // the same parameter t. Used for limbs (round elbow / knee bends)
  // and the future anatomy curves (bicep / glute / hip flare bulges).
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
    case 11u: { d = sdNoiseCloud(pPrim, params.x, params.y, params.z, params.w, u.time); }
    case 12u: { d = sdCone(pPrim, vec2f(params.x, params.y), params.z); }
    case 13u: { d = sdChibiHead(pPrim, params.x, params.y, params.z); }
    case 14u: { d = sdBentCapsule(pPrim, params.x, params.y, tipDelta); }
    case 18u: { d = sdSUP(pPrim, params.x, params.y, params.z, params.w); }
    case 19u: { d = sdEllipsoidExact(pPrim, params.xyz); }
    case 21u: { d = sdTrapezoidalBox(pPrim, params.x, params.y, params.z, params.w); }
    case 22u: { d = sdBand(pPrim, params.x, params.y, params.z); }
    default:  { d = 1e9; }
  }

  // GEOMETRIC CRACK DISPLACEMENT — when colorFunc=9 is set on this prim,
  // and the slot 2.w (detailAmplitude) is repurposed as crack DEPTH,
  // displace the SDF surface OUTWARD near voronoi cell edges. This makes
  // the cracks become real silhouette gaps rather than just dark color
  // bands. World-space evaluation so cracks wrap the geometry consistently.
  let colorFn = slots.w;
  if (colorFn == 9u) {
    // CRACKS — domain-warped FBM noise band, smoothstep falloff. Warping the
    // input coordinate by an independent FBM field breaks the regular signature
    // of plain FBM contours so cracks read as natural fracture lines instead of
    // a uniform ripple. INWARD displacement: d = d + delta pushes surface away
    // from the outside query → sunken into the model.
    let crackDepth = prims[base + 2u].w;
    if (crackDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp = vec3f(
        fbm3(pWorld * (density * 0.5)),
        fbm3(pWorld * (density * 0.5) + vec3f(31.0, 17.0, 53.0)),
        fbm3(pWorld * (density * 0.5) + vec3f(7.0, 41.0, 23.0)),
      );
      let pw = pWorld * density + warp * 1.4;
      let n = fbm3(pw);
      let ridgeDist = abs(n);
      let thresh = 0.06;
      let t = 1.0 - smoothstep(0.0, thresh, ridgeDist);
      d = d + t * crackDepth;                          // ADD = sunken (inward)
    }
  } else if (colorFn == 10u) {
    // PITS — Worley distance to nearest cell point. Where distance is
    // small (close to a random "impact" point), displace the surface
    // INWARD by pitDepth → creates round craters. Domain-warped input
    // so pits are irregularly distributed, not on a grid.
    let pitDepth = prims[base + 2u].w;
    if (pitDepth > 0.0) {
      let density = prims[base + 3u].y;
      // Domain warp via FBM at higher freq, like the crack code.
      let warp = vec3f(
        fbm3(pWorld * 8.0),
        fbm3(pWorld * 8.0 + vec3f(31.0, 17.0, 53.0)),
        fbm3(pWorld * 8.0 + vec3f(7.0, 41.0, 23.0)),
      ) - vec3f(0.5);
      let pp = (pWorld + warp * 0.15) * density;
      let pi = floor(pp);
      var dmin = 1e9;
      for (var z = -1; z <= 1; z = z + 1) {
        for (var y = -1; y <= 1; y = y + 1) {
          for (var x = -1; x <= 1; x = x + 1) {
            let cell = pi + vec3f(f32(x), f32(y), f32(z));
            var h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
            let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
            let dd = length(pp - pt);
            if (dd < dmin) { dmin = dd; }
          }
        }
      }
      // Pit radius — 0.30 cell-units = round pits ~30% of cell size.
      let pitRadius = 0.30;
      if (dmin < pitRadius) {
        let t = 1.0 - dmin / pitRadius;             // 1 at center, 0 at rim
        d = d + pow(t, 2.0) * pitDepth;             // smooth crater
      }
    }
  } else if (colorFn == 11u) {
    // BUMPS — smooth outward FBM displacement. fbm3 is already centered
    // on 0 (range ~±0.5), no shift needed.
    let bumpDepth = prims[base + 2u].w;
    if (bumpDepth > 0.0) {
      let density = prims[base + 3u].y;
      let n = fbm3(pWorld * density);
      d = d - n * bumpDepth * 2.0;                     // subtract → outward bumps
    }
  } else if (colorFn == 12u) {
    // SCALES — raised RIDGES along Worley cell EDGES. Each tile is a
    // cell with raised borders separating it from neighbors. The
    // cell-center version reads as just "lumpy" not "scaled" — the EDGE
    // RIDGES are what visually communicate tile boundaries. Smoothstep
    // falloff (not pow) to keep SDF Lipschitz / no march overshoot.
    let scaleDepth = prims[base + 2u].w;
    if (scaleDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp = vec3f(
        fbm3(pWorld * 6.0),
        fbm3(pWorld * 6.0 + vec3f(31.0, 17.0, 53.0)),
        fbm3(pWorld * 6.0 + vec3f(7.0, 41.0, 23.0)),
      ) - vec3f(0.5);
      let pp = (pWorld + warp * 0.10) * density;
      let pi = floor(pp);
      var d1 = vec3f(0.0); var d1m = 1e9;
      for (var z = -1; z <= 1; z = z + 1) {
        for (var y = -1; y <= 1; y = y + 1) {
          for (var x = -1; x <= 1; x = x + 1) {
            let cell = pi + vec3f(f32(x), f32(y), f32(z));
            var h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
            let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
            let dd = length(pp - pt);
            if (dd < d1m) { d1m = dd; d1 = pt; }
          }
        }
      }
      var d2m = 1e9;
      for (var z = -1; z <= 1; z = z + 1) {
        for (var y = -1; y <= 1; y = y + 1) {
          for (var x = -1; x <= 1; x = x + 1) {
            let cell = pi + vec3f(f32(x), f32(y), f32(z));
            var h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
            let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
            if (length(pt - d1) < 0.001) { continue; }
            let dd = length(pp - pt);
            if (dd < d2m) { d2m = dd; }
          }
        }
      }
      let edge = d2m - d1m;
      let thresh = 0.10;
      let t = 1.0 - smoothstep(0.0, thresh, edge);
      d = d - t * scaleDepth;
    }
  } else if (colorFn == 13u) {
    // VEINS — same FBM noise-band as cracks but RAISED. Smoothstep falloff,
    // 0-centered noise (corrected from earlier abs(n-0.5) bug).
    let veinDepth = prims[base + 2u].w;
    if (veinDepth > 0.0) {
      let density = prims[base + 3u].y;
      let n = fbm3(pWorld * density);
      let ridgeDist = abs(n);
      let thresh = 0.04;
      let t = 1.0 - smoothstep(0.0, thresh, ridgeDist);
      d = d - t * veinDepth;          // SUBTRACT → raised
    }
  } else if (colorFn == 14u) {
    // WOOD GRAIN — directional sinusoidal stripes along Y axis, distorted
    // by FBM warp for natural irregularity. Cheap and effective for wood
    // planks, tree bark, muscle striation, rope strands.
    let grainDepth = prims[base + 2u].w;
    if (grainDepth > 0.0) {
      let density = prims[base + 3u].y;
      // FBM warp shifts the stripe phase locally → wavy not perfectly
      // straight grain. Higher amplitude = wavier; 0 = ruler-straight.
      let warp = fbm3(pWorld * 5.0) * 1.5;
      let s = sin(pWorld.y * density * 6.283 + warp * 4.0);
      // |s| ∈ [0, 1]; thin band where it crosses zero = grain line.
      let thresh = 0.30;
      let t = 1.0 - smoothstep(0.0, thresh, abs(s));
      d = d + t * grainDepth;          // ADD = sunken grain line
    }
  } else if (colorFn == 15u) {
    // RIDGED MULTIFRACTAL — classic Musgrave/Perlin "mountain" pattern. Each
    // octave is folded via 1-|n| then squared so peaks stay sharp while valleys
    // fill in smoothly. Domain-warped input so spines don't read as periodic.
    // Use cases: mountain ridges, sword-blade fullers, scaly ridges along a
    // creature's spine, wrinkled bark, knotted rope. Different look from
    // crack-band: ONE prominent ridge per noise period, not band-pair edges.
    let ridgeDepth = prims[base + 2u].w;
    if (ridgeDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp = vec3f(
        fbm3(pWorld * (density * 0.4)),
        fbm3(pWorld * (density * 0.4) + vec3f(31.0, 17.0, 53.0)),
        fbm3(pWorld * (density * 0.4) + vec3f(7.0, 41.0, 23.0)),
      );
      var p = pWorld * density + warp * 1.2;
      var amp = 0.5;
      var sum = 0.0;
      var prev = 1.0;
      // 4-octave ridged multifractal. fbm3 already loops octaves but we want
      // explicit folding per octave so we re-implement here.
      for (var i = 0; i < 4; i = i + 1) {
        let n = fbm3(p);                      // signed noise ~[-0.5, 0.5]
        var r = 1.0 - abs(n * 2.0);           // fold to peaks ~[0,1]
        r = r * r * prev;                      // sharpen + multiplicative warping
        sum = sum + r * amp;
        prev = r;
        p = p * 2.03;                          // non-integer lacunarity
        amp = amp * 0.5;
      }
      // sum ∈ ~[0, 1.0]. Subtract from d → raised ridges along peaks.
      d = d - sum * ridgeDepth;
    }
  } else if (colorFn == 16u) {
    // EROSION STREAKS — directional gradient × FBM, gives the look of vertical
    // drips, rust runs, water staining on stone. Streaks are aligned with the
    // local +Y axis (gravity direction). Higher up = no streak; lower = full
    // streak intensity, modulated by FBM so streaks are uneven and clustered.
    // Combine with bumps or grain for layered weathering.
    let streakDepth = prims[base + 2u].w;
    if (streakDepth > 0.0) {
      let density = prims[base + 3u].y;
      // High-freq horizontal noise picks WHICH columns drip; low-freq vertical
      // noise modulates intensity along the column. Together → patchy vertical
      // streaks (not uniform striping).
      let columnPick = fbm3(vec3f(pWorld.x * density, 0.0, pWorld.z * density));
      let columnT = smoothstep(0.45, 0.55, columnPick);
      // Vertical falloff: streaks start ~middle of bbox and intensify downward.
      // Use raw +Y so streaks are gravity-aligned in world space.
      let drip = clamp(0.5 - pWorld.y * 5.0, 0.0, 1.0);
      // Vertical jitter so streaks don't all end at the same line.
      let jitter = fbm3(vec3f(pWorld.x * density * 2.0, pWorld.y * density * 0.5, pWorld.z * density * 2.0));
      let intensity = columnT * drip * (0.5 + jitter);
      d = d + clamp(intensity, 0.0, 1.0) * streakDepth;     // ADD = sunken streak
    }
  } else if (colorFn == 17u) {
    // HEX TILES — periodic hexagonal lattice with raised cell faces and sunken
    // mortar grooves. Pointy-top hex orientation. Domain-warped to break the
    // perfectly-regular lattice into a "natural" but still hex-recognizable
    // pattern. Use cases: sci-fi armor plating, honeycomb, alien skin,
    // tessellated shields. Different from scaleDepth (Voronoi cells, irregular
    // sizes) — hex has uniform cell size, perfect tiling.
    let hexDepth = prims[base + 2u].w;
    if (hexDepth > 0.0) {
      let density = prims[base + 3u].y;
      // Light domain warp so panel boundaries aren't ruler-straight.
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.6)),
        fbm3(pWorld * (density * 0.6) + vec3f(31.0, 17.0, 53.0)),
      );
      let pp = pWorld.xy * density + warp2 * 0.3;
      // Hex tiling via two interlocking rectangular grids offset by half-cell;
      // pick whichever cell center is closer. s = (sqrt(3), 1) for pointy-top.
      let s = vec2f(1.7320508, 1.0);
      let h = s * 0.5;
      let a = pp - s * floor(pp / s + vec2f(0.5));
      let b = (pp - h) - s * floor((pp - h) / s + vec2f(0.5));
      let q = select(b, a, dot(a, a) < dot(b, b));
      // Distance to nearest hex EDGE for pointy-top hex centered at origin.
      // Standard formula: max(|qx|*sqrt(3)/2 + |qy|*0.5, |qy|).
      let aq = abs(q);
      let edgeDist = 0.5 - max(aq.x * 0.8660254 + aq.y * 0.5, aq.y);
      // edgeDist ∈ ~[0, 0.5]; small near edge, large near center.
      let groove = 0.04;            // mortar half-width in cell units
      let t = 1.0 - smoothstep(0.0, groove, edgeDist);
      d = d + t * hexDepth;          // ADD = sunken mortar groove between plates
    }
  } else if (colorFn == 18u) {
    // BRICK MASONRY — offset rectangular tiling with mortar grooves. Each row
    // shifted by half a brick (running-bond pattern). Domain-warped slightly
    // so individual bricks have natural irregularity. Use cases: stone walls,
    // chimneys, building facades, dungeon walls.
    let brickDepth = prims[base + 2u].w;
    if (brickDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.4)),
        fbm3(pWorld * (density * 0.4) + vec3f(31.0, 17.0, 53.0)),
      );
      // Brick aspect ratio 2:1 (twice as wide as tall). XY plane.
      let brickSize = vec2f(2.0, 1.0);
      var pp = pWorld.xy * density + warp2 * 0.2;
      // Row index → row offset by half a brick on alternate rows.
      let rowIdx = floor(pp.y / brickSize.y);
      let rowOffset = (rowIdx - 2.0 * floor(rowIdx * 0.5)) * brickSize.x * 0.5;
      pp.x = pp.x + rowOffset;
      // Local position within a brick.
      let local = pp - brickSize * (floor(pp / brickSize) + vec2f(0.5));
      // Distance to nearest brick edge (mortar joint).
      let edgeXY = brickSize * 0.5 - abs(local);
      let edgeDist = min(edgeXY.x, edgeXY.y);
      let groove = 0.06;
      let t = 1.0 - smoothstep(0.0, groove, edgeDist);
      d = d + t * brickDepth;        // ADD = sunken mortar between bricks
    }
  } else if (colorFn == 19u) {
    // VORONOI CRACKS — geometric cell-network fracture. Distinct from the
    // FBM-band cracks (mode 9): this finds F1 and F2 (1st & 2nd nearest
    // Voronoi cell points) and uses their bisector distance to draw thin
    // sunken lines exactly along cell boundaries. The result reads as
    // cracked dried mud, dragon-egg shell, broken tile, parched earth.
    // Cell SIZES are uniform (random jitter only), so the network feels
    // organic but not "noisy" — every line is a true cell boundary.
    let voronoiDepth = prims[base + 2u].w;
    if (voronoiDepth > 0.0) {
      let density = prims[base + 3u].y;
      // Mild domain warp so cell shapes aren't perfectly Voronoi-textbook.
      let warp = vec3f(
        fbm3(pWorld * (density * 0.5)),
        fbm3(pWorld * (density * 0.5) + vec3f(31.0, 17.0, 53.0)),
        fbm3(pWorld * (density * 0.5) + vec3f(7.0, 41.0, 23.0)),
      );
      let pp = (pWorld + warp * 0.06) * density;
      let pi = floor(pp);
      var d1m = 1e9;
      var d1p = vec3f(0.0);
      // Two-pass Voronoi: F1 first, then F2 excluding F1's cell.
      for (var z = -1; z <= 1; z = z + 1) {
        for (var y = -1; y <= 1; y = y + 1) {
          for (var x = -1; x <= 1; x = x + 1) {
            let cell = pi + vec3f(f32(x), f32(y), f32(z));
            let h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
            let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
            let dd = length(pp - pt);
            if (dd < d1m) { d1m = dd; d1p = pt; }
          }
        }
      }
      // F2: project query onto the F1↔F2 bisector for accurate edge distance.
      var bisDist = 1e9;
      for (var z = -1; z <= 1; z = z + 1) {
        for (var y = -1; y <= 1; y = y + 1) {
          for (var x = -1; x <= 1; x = x + 1) {
            let cell = pi + vec3f(f32(x), f32(y), f32(z));
            let h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
            let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
            let delta = pt - d1p;
            let dlen = length(delta);
            if (dlen < 1e-4) { continue; }              // skip F1 itself
            // Bisector distance = projection of (pp - midpoint) onto unit normal.
            let mid = (pt + d1p) * 0.5;
            let nrm = delta / dlen;
            let bd = abs(dot(pp - mid, nrm));
            if (bd < bisDist) { bisDist = bd; }
          }
        }
      }
      let crackHalfWidth = 0.04;                         // line half-thickness in cell units
      let t = 1.0 - smoothstep(0.0, crackHalfWidth, bisDist);
      d = d + t * voronoiDepth;          // ADD = sunken crack along cell edges
    }
  } else if (colorFn == 20u) {
    // SCRATCHES — sparse directional strokes. Each scratch is a line along
    // local +X (rotate the prim to redirect). Two FBM fields combine: a
    // high-freq selector that picks WHICH lines exist, and a low-freq jitter
    // that bends individual scratches slightly. Result: brushed-metal /
    // weapon-wear look. Different from grain mode (continuous parallel stripes)
    // — scratches are sparse, irregular, partial-length.
    let scratchDepth = prims[base + 2u].w;
    if (scratchDepth > 0.0) {
      let density = prims[base + 3u].y;
      // Low-freq vertical jitter bends each scratch's exact path slightly.
      let bend = fbm3(vec3f(pWorld.x * density * 0.3, 0.0, pWorld.z * density * 0.3));
      let yLine = pWorld.y * density + bend * 0.6;
      // Sin gives perfect parallel lines; floor identifies WHICH line we're near.
      let lineIdx = floor(yLine + 0.5);
      let distToLine = abs(yLine - lineIdx);
      // Selector: per-line random hash decides if THIS line exists (sparse).
      let exists = fract(sin(lineIdx * 12.9898 + 78.233) * 43758.5);
      let lineExists = step(0.7, exists);                // ~30% of lines exist
      // Length-along-X also masked: scratches are partial-length.
      let xMask = fbm3(vec3f(pWorld.x * density * 0.4, lineIdx * 0.1, 0.0));
      let lengthMask = smoothstep(0.4, 0.55, xMask);
      let lineWidth = 0.06;
      let t = (1.0 - smoothstep(0.0, lineWidth, distToLine)) * lineExists * lengthMask;
      d = d + t * scratchDepth;
    }
  } else if (colorFn == 21u) {
    // DIMPLES — regular grid of sunken sphere indents. The XY plane is
    // tiled with cell-centered hemispheres (radius = 0.35 cell-units, can
    // be tightened) that subtract from the surface. Domain-warped slightly
    // so the grid isn't ruler-perfect. Use cases: golf ball, hammered
    // metal, perforated panel, leather pebbling. Inverse of mode 22 (studs).
    let dimpleDepth = prims[base + 2u].w;
    if (dimpleDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.4)),
        fbm3(pWorld * (density * 0.4) + vec3f(31.0, 17.0, 53.0)),
      );
      let pp = pWorld.xy * density + warp2 * 0.15;
      let local = pp - floor(pp + vec2f(0.5));            // [-0.5, 0.5] per cell
      let r = length(local);
      let dimpleR = 0.35;                                 // cell-units
      // Smooth radial falloff: 1 at center, 0 at rim. Falls beyond rim → 0.
      let t = 1.0 - smoothstep(0.0, dimpleR, r);
      d = d + t * dimpleDepth;                            // ADD = sunken indent
    }
  } else if (colorFn == 22u) {
    // STUDS — regular grid of raised hemispheres. Inverse of dimples. Same
    // grid math, opposite sign on d. Use cases: rivets, tactile dot
    // patterns (control-pad / D-pad), studded leather, decorative dots.
    let studDepth = prims[base + 2u].w;
    if (studDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.4)),
        fbm3(pWorld * (density * 0.4) + vec3f(31.0, 17.0, 53.0)),
      );
      let pp = pWorld.xy * density + warp2 * 0.10;
      let local = pp - floor(pp + vec2f(0.5));
      let r = length(local);
      let studR = 0.30;
      let t = 1.0 - smoothstep(0.0, studR, r);
      d = d - t * studDepth;                              // SUBTRACT = raised
    }
  } else if (colorFn == 23u) {
    // CHEVRONS — V-shaped raised ridges along local +Y axis. Like grain but
    // V-pattern: at each Y-step, a chevron spans ±X width. Domain-warped to
    // break the perfectly-regular pattern. Use cases: arrow pavement,
    // textured rubber grip, military stencil chevrons, herringbone leather.
    let chevDepth = prims[base + 2u].w;
    if (chevDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp = fbm3(pWorld * (density * 0.5)) * 0.4;
      let yIdx = floor(pWorld.y * density + warp);
      // V-shape: y position relative to current chevron + |x| determines
      // distance to the V. Higher |x| = needs greater +y to be on V.
      let yLocal = (pWorld.y * density + warp) - yIdx;
      let xLocal = abs(pWorld.x * density) % 1.0;
      let vDist = abs(yLocal - 0.5 - xLocal * 0.5);       // V-shape distance
      let chevWidth = 0.08;
      let t = 1.0 - smoothstep(0.0, chevWidth, vDist);
      d = d - t * chevDepth;                              // SUBTRACT = raised V
    }
  } else if (colorFn == 24u) {
    // WHORL — concentric rings around the local origin (XY plane). The radius
    // is domain-warped by FBM so rings aren't perfect circles — they wave and
    // pinch like fingerprint or tree-growth rings. sin(radius * density)
    // crossings are the ring lines (sunken). Different from every existing
    // mode: pure radial, no Voronoi/lattice/band. Use cases: fingerprints,
    // tree-stump rings, sliced fruit, contour topo lines, target patterns,
    // wood end-grain.
    let whorlDepth = prims[base + 2u].w;
    if (whorlDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp = fbm3(pWorld * (density * 0.4)) * 0.6;
      let r = length(pWorld.xy) + warp * 0.012;
      let s = sin(r * density * 6.283);                    // ring oscillation
      let t = 1.0 - smoothstep(0.0, 0.30, abs(s));
      d = d + t * whorlDepth;                              // ADD = sunken ring
    }
  } else if (colorFn == 25u) {
    // FISHSCALE — offset arc-rows. Each cell shows a half-circle arc whose
    // visible bottom edge is the shadow line BETWEEN overlapping scales.
    // Adjacent rows shifted by half-cell so arcs interlock (offset bond
    // pattern, like brick but with curves). Different from scales mode 12,
    // Voronoi cells, irregular sizes) — fishscale is uniform, regular,
    // unmistakably "tile / scale / pinecone-bract". Domain-warped lightly
    // so the arc edges aren't ruler-perfect.
    let fsDepth = prims[base + 2u].w;
    if (fsDepth > 0.0) {
      let density = prims[base + 3u].y;
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.4)),
        fbm3(pWorld * (density * 0.4) + vec3f(31.0, 17.0, 53.0)),
      );
      let cellSize = vec2f(2.0, 1.0);
      var pp = pWorld.xy * density + warp2 * 0.10;
      let rowIdx = floor(pp.y / cellSize.y);
      let rowOffset = (rowIdx - 2.0 * floor(rowIdx * 0.5)) * cellSize.x * 0.5;
      pp.x = pp.x + rowOffset;
      let local = pp - cellSize * (floor(pp / cellSize) + vec2f(0.5));
      // Arc center sits at cell-top (local.y = +cellSize.y/2). Arc radius is
      // ~half cell width; the visible half-circle is the BOTTOM of this arc.
      let arcCenter = vec2f(0.0, cellSize.y * 0.5);
      let arcR = cellSize.x * 0.55;
      let r = length(local - arcCenter);
      let dArcLine = abs(r - arcR);
      // Smooth gate: only the bottom half of the arc circle (below arcCenter.y)
      // is the visible scale boundary. Above = inside the next-row scale.
      let visibleBottom = smoothstep(arcCenter.y + 0.05, arcCenter.y - 0.05, local.y);
      let lineW = 0.06;
      let t = visibleBottom * (1.0 - smoothstep(0.0, lineW, dArcLine));
      d = d + t * fsDepth;                                 // ADD = sunken groove
    }
  } else if (colorFn == 26u) {
    // WEAVE — two-axis over-under fabric pattern. Horizontal strands raise
    // along X; vertical strands raise along Y. In alternating large cells,
    // either H or V strand is dominant (on top), so the surface reads as
    // genuinely woven, not just cross-hatched. Different from grain (single
    // direction) and chevrons (V-pattern). Use cases: woven fabric, basket
    // weave, cane, mesh, chainmail, woven grass mat.
    let weaveDepth = prims[base + 2u].w;
    if (weaveDepth > 0.0) {
      let density = prims[base + 3u].y;
      // Light domain warp so strands wave gently, not ruler-straight.
      let warp2 = vec2f(
        fbm3(pWorld * (density * 0.3)),
        fbm3(pWorld * (density * 0.3) + vec3f(31.0, 17.0, 53.0)),
      );
      let pp = pWorld.xy * density + warp2 * 0.15;
      // Two perpendicular sin strands. Peak (sin == 1) = strand top.
      let strandH = sin(pp.x * 6.283);          // horizontal-running strand
      let strandV = sin(pp.y * 6.283);          // vertical-running strand
      // Over-under: parity of (cellX + cellY) at half the density picks which
      // strand is on top in each large cell. The factor 0.5 makes large cells
      // = 2x2 strand-cells so over-under flips visibly.
      let cellSum = floor(pp.x * 0.5) + floor(pp.y * 0.5);
      let parity = (i32(cellSum) % 2) == 0;
      let dominant = select(strandV, strandH, parity);
      // Raise where dominant strand peaks (top of sin wave).
      let t = max(0.0, dominant);
      d = d - t * weaveDepth;                              // SUBTRACT = raised strand
    }
  }
  // ──────────────── SECONDARY WEAR DEFORMER ────────────────
  // Runs AFTER the primary colorFunc deformer. Limited to FBM-based wear
  // modes so the wear block stays compact (the primary chain is 14-wide;
  // duplicating that for the wear slot is overkill — wear is realistically
  // always one of these four). Slot 5: x=wearFn (u32), y=wearDepth (f32),
  // z=wearDensity (f32), w=pad. wearFn=0 = off (early-out via the if).
  let slot5 = prims[base + 5u];
  let wearFn = bitcast<u32>(slot5.x);
  if (wearFn != 0u) {
    let wDepth = slot5.y;
    let wDens = slot5.z;
    if (wearFn == 1u) {
      // BUMPS overlay — smooth FBM outward displacement. Same math as primary mode 11.
      let n = fbm3(pWorld * wDens);
      d = d - n * wDepth * 2.0;
    } else if (wearFn == 2u) {
      // GRAIN overlay — directional sin stripes warped by FBM. Same as mode 14.
      let warp = fbm3(pWorld * 5.0) * 1.5;
      let s = sin(pWorld.y * wDens * 6.283 + warp * 4.0);
      let t = 1.0 - smoothstep(0.0, 0.30, abs(s));
      d = d + t * wDepth;
    } else if (wearFn == 3u) {
      // STREAKS overlay — gravity-aligned drips. Same as mode 16.
      let columnPick = fbm3(vec3f(pWorld.x * wDens, 0.0, pWorld.z * wDens));
      let columnT = smoothstep(0.45, 0.55, columnPick);
      let drip = clamp(0.5 - pWorld.y * 5.0, 0.0, 1.0);
      let jitter = fbm3(vec3f(pWorld.x * wDens * 2.0, pWorld.y * wDens * 0.5, pWorld.z * wDens * 2.0));
      let intensity = columnT * drip * (0.5 + jitter);
      d = d + clamp(intensity, 0.0, 1.0) * wDepth;
    } else if (wearFn == 4u) {
      // SCRATCHES overlay — sparse directional strokes. Same as mode 20.
      let bend = fbm3(vec3f(pWorld.x * wDens * 0.3, 0.0, pWorld.z * wDens * 0.3));
      let yLine = pWorld.y * wDens + bend * 0.6;
      let lineIdx = floor(yLine + 0.5);
      let distToLine = abs(yLine - lineIdx);
      let exists = fract(sin(lineIdx * 12.9898 + 78.233) * 43758.5);
      let lineExists = step(0.7, exists);
      let xMask = fbm3(vec3f(pWorld.x * wDens * 0.4, lineIdx * 0.1, 0.0));
      let lengthMask = smoothstep(0.4, 0.55, xMask);
      let t = (1.0 - smoothstep(0.0, 0.06, distToLine)) * lineExists * lengthMask;
      d = d + t * wDepth;
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
    // Dual-map detail displacement — per-primitive FBM, only active on
    // the normal pass. detailAmp lives in the offsetInBone.w pad slot.
    if (wantDetail == 1u) {
      let detailAmp = prims[base + 2u].w;
      if (detailAmp > 0.0) {
        d = d - detailAmp * fbm3(pWorld * 28.0);
      }
    }
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
  for (var step = 0u; step < u.maxSteps; step = step + 1u) {
    let p = ro + rd * t;
    let s = sceneSDF(p, 0u);
    if (s.dist < 0.001) { hitPrim = s.primIdx; hit = true; break; }
    t = t + s.dist;
    if (t > totalDist) { break; }
  }

  if (!hit) {
    out.color  = vec4f(0.0, 0.0, 0.0, 0.0);   // alpha=0 → outline pass treats as bg
    out.normal = vec4f(0.5, 0.5, 1.0, 0.0);
    out.depth  = vec4f(1.0, 0.0, 0.0, 0.0);
    return out;
  }

  let hitPos = ro + rd * t;
  let n = sceneNormal(hitPos, 0.002);

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
  } else if (colorFunc == 9u) {
    // VORONOI EDGE CRACKS — irregular branching dark lines suggesting
    // surface fractures. Cell-edge distance via 2-nearest-neighbour
    // search; pixels close to a Voronoi cell boundary read as cracks.
    // colorExtent = density (cells per metre). Higher = finer cracks.
    let pp = hitPos * colorExtent;
    let pi = floor(pp);
    var d1 = vec3f(0.0); var d1m = 1e9;
    for (var z = -1; z <= 1; z = z + 1) {
      for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
          let cell = pi + vec3f(f32(x), f32(y), f32(z));
          var h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
          let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
          let dd = length(pp - pt);
          if (dd < d1m) { d1m = dd; d1 = pt; }
        }
      }
    }
    var d2m = 1e9;
    for (var z = -1; z <= 1; z = z + 1) {
      for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
          let cell = pi + vec3f(f32(x), f32(y), f32(z));
          var h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
          let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
          if (length(pt - d1) < 0.001) { continue; }
          let dd = length(pp - pt);
          if (dd < d2m) { d2m = dd; }
        }
      }
    }
    if ((d2m - d1m) < 0.10) { slot = slotB; }   // edge band → crack
  } else if (colorFunc == 10u) {
    // PITS — round craters picked into slotB. Mirror the domain-warped Worley
    // F1 distance from evalPrim. Crater interior gets the dark accent.
    let warp = vec3f(
      fbm3(hitPos * (colorExtent * 0.8)),
      fbm3(hitPos * (colorExtent * 0.8) + vec3f(31.0, 17.0, 53.0)),
      fbm3(hitPos * (colorExtent * 0.8) + vec3f(7.0, 41.0, 23.0)),
    );
    let pp = (hitPos + warp * 0.15) * colorExtent;
    let pi = floor(pp);
    var dmin = 1e9;
    for (var z = -1; z <= 1; z = z + 1) {
      for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
          let cell = pi + vec3f(f32(x), f32(y), f32(z));
          let h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
          let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
          let dd = length(pp - pt);
          if (dd < dmin) { dmin = dd; }
        }
      }
    }
    if (dmin < 0.30) { slot = slotB; }                       // pit interior
  } else if (colorFunc == 13u) {
    // VEINS — same FBM-band ridge as cracks but raised. Picked into slotB
    // so the dark vein lines visibly trace the raised geometry.
    let n = fbm3(hitPos * colorExtent);
    if (abs(n) < 0.04) { slot = slotB; }                     // vein ridge band
  } else if (colorFunc == 15u) {
    // RIDGES — ridged-multifractal peaks picked into slotB. Approximation of
    // the 4-octave fold from evalPrim using a single-octave (1-|n|) — color
    // contrast doesn't need full multifractal precision, just "near a ridge".
    let warp = vec3f(
      fbm3(hitPos * (colorExtent * 0.4)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(31.0, 17.0, 53.0)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(7.0, 41.0, 23.0)),
    );
    let pp = hitPos * colorExtent + warp * 1.2;
    let n = fbm3(pp);
    let r = 1.0 - abs(n * 2.0);                              // [0, 1] peak proximity
    if (r > 0.65) { slot = slotB; }                          // near a ridge peak
  } else if (colorFunc == 16u) {
    // STREAKS — gravity-aligned drips picked into slotB. Same column-pick +
    // vertical falloff math from evalPrim. Streaks darken (rust runoff,
    // water staining).
    let columnPick = fbm3(vec3f(hitPos.x * colorExtent, 0.0, hitPos.z * colorExtent));
    let columnT = smoothstep(0.45, 0.55, columnPick);
    let drip = clamp(0.5 - hitPos.y * 5.0, 0.0, 1.0);
    let jitter = fbm3(vec3f(hitPos.x * colorExtent * 2.0, hitPos.y * colorExtent * 0.5, hitPos.z * colorExtent * 2.0));
    let intensity = clamp(columnT * drip * (0.5 + jitter), 0.0, 1.0);
    if (intensity > 0.25) { slot = slotB; }                  // streak band
  } else if (colorFunc == 12u) {
    // SCALES — Voronoi cell-edge ridges picked into slotB. Mirror the F1-F2
    // bisector math from evalPrim's geometric pass so the dark ridges line up
    // with the raised displacement. Same domain warp.
    let warp = vec3f(
      fbm3(hitPos * (colorExtent * 0.6)),
      fbm3(hitPos * (colorExtent * 0.6) + vec3f(31.0, 17.0, 53.0)),
      fbm3(hitPos * (colorExtent * 0.6) + vec3f(7.0, 41.0, 23.0)),
    );
    let pp = (hitPos + warp * 0.10) * colorExtent;
    let pi = floor(pp);
    var d1 = vec3f(0.0); var d1m = 1e9;
    for (var z = -1; z <= 1; z = z + 1) {
      for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
          let cell = pi + vec3f(f32(x), f32(y), f32(z));
          let h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
          let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
          let dd = length(pp - pt);
          if (dd < d1m) { d1m = dd; d1 = pt; }
        }
      }
    }
    var d2m = 1e9;
    for (var z = -1; z <= 1; z = z + 1) {
      for (var y = -1; y <= 1; y = y + 1) {
        for (var x = -1; x <= 1; x = x + 1) {
          let cell = pi + vec3f(f32(x), f32(y), f32(z));
          let h = fract(sin(dot(cell, vec3f(127.1, 311.7, 74.7))) * 43758.5);
          let pt = cell + vec3f(h, fract(h * 37.0), fract(h * 91.0));
          if (length(pt - d1) < 0.001) { continue; }
          let dd = length(pp - pt);
          if (dd < d2m) { d2m = dd; }
        }
      }
    }
    let edge = d2m - d1m;
    if (edge < 0.10) { slot = slotB; }                       // cell-edge ridge
  } else if (colorFunc == 17u) {
    // HEX TILES — mortar grooves between plates picked into slotB. Mirrors
    // the geometric evaluation in evalPrim so the dark mortar lines up with
    // the sunken displacement. Density read from colorExtent.
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.6)),
      fbm3(hitPos * (colorExtent * 0.6) + vec3f(31.0, 17.0, 53.0)),
    );
    let pp = hitPos.xy * colorExtent + warp2 * 0.3;
    let s = vec2f(1.7320508, 1.0);
    let h = s * 0.5;
    let a = pp - s * floor(pp / s + vec2f(0.5));
    let b = (pp - h) - s * floor((pp - h) / s + vec2f(0.5));
    let q = select(b, a, dot(a, a) < dot(b, b));
    let aq = abs(q);
    let edgeDist = 0.5 - max(aq.x * 0.8660254 + aq.y * 0.5, aq.y);
    if (edgeDist < 0.04) { slot = slotB; }                  // mortar line
  } else if (colorFunc == 18u) {
    // BRICK MASONRY — mortar joints picked into slotB. Same offset-row math
    // as the geometric pass.
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.4)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(31.0, 17.0, 53.0)),
    );
    let brickSize = vec2f(2.0, 1.0);
    var pp = hitPos.xy * colorExtent + warp2 * 0.2;
    let rowIdx = floor(pp.y / brickSize.y);
    let rowOffset = (rowIdx - 2.0 * floor(rowIdx * 0.5)) * brickSize.x * 0.5;
    pp.x = pp.x + rowOffset;
    let local = pp - brickSize * (floor(pp / brickSize) + vec2f(0.5));
    let edgeXY = brickSize * 0.5 - abs(local);
    let edgeDist = min(edgeXY.x, edgeXY.y);
    if (edgeDist < 0.06) { slot = slotB; }                  // mortar joint
  } else if (colorFunc == 21u) {
    // DIMPLES — center of each cell picked into slotB so dimples darken,
    // matching the sunken geometry.
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.4)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(31.0, 17.0, 53.0)),
    );
    let pp = hitPos.xy * colorExtent + warp2 * 0.15;
    let local = pp - floor(pp + vec2f(0.5));
    let r = length(local);
    if (r < 0.30) { slot = slotB; }                          // dimple interior
  } else if (colorFunc == 22u) {
    // STUDS — raised hemispheres picked into slotB so tops can highlight
    // (use a brighter slotB) OR darken (set slotB darker than slotA, e.g.
    // shadow ring around studs).
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.4)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(31.0, 17.0, 53.0)),
    );
    let pp = hitPos.xy * colorExtent + warp2 * 0.10;
    let local = pp - floor(pp + vec2f(0.5));
    let r = length(local);
    if (r < 0.25) { slot = slotB; }                          // stud face
  } else if (colorFunc == 23u) {
    // CHEVRONS — V-ridge band picked into slotB. Same V-distance math as
    // the geometric pass.
    let warp = fbm3(hitPos * (colorExtent * 0.5)) * 0.4;
    let yIdx = floor(hitPos.y * colorExtent + warp);
    let yLocal = (hitPos.y * colorExtent + warp) - yIdx;
    let xLocal = abs(hitPos.x * colorExtent) % 1.0;
    let vDist = abs(yLocal - 0.5 - xLocal * 0.5);
    if (vDist < 0.07) { slot = slotB; }                      // V-band
  } else if (colorFunc == 24u) {
    // WHORL — ring lines picked into slotB so concentric rings read as actual
    // dark lines (fingerprint / growth-ring look) over the base material.
    let warp = fbm3(hitPos * (colorExtent * 0.4)) * 0.6;
    let r = length(hitPos.xy) + warp * 0.012;
    let s = sin(r * colorExtent * 6.283);
    if (abs(s) < 0.20) { slot = slotB; }                     // ring line
  } else if (colorFunc == 25u) {
    // FISHSCALE — shadow line between overlapping scales picked into slotB.
    // Mirror the geometric pass's offset-row arc math.
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.4)),
      fbm3(hitPos * (colorExtent * 0.4) + vec3f(31.0, 17.0, 53.0)),
    );
    let cellSize = vec2f(2.0, 1.0);
    var pp = hitPos.xy * colorExtent + warp2 * 0.10;
    let rowIdx = floor(pp.y / cellSize.y);
    let rowOffset = (rowIdx - 2.0 * floor(rowIdx * 0.5)) * cellSize.x * 0.5;
    pp.x = pp.x + rowOffset;
    let local = pp - cellSize * (floor(pp / cellSize) + vec2f(0.5));
    let arcCenter = vec2f(0.0, cellSize.y * 0.5);
    let arcR = cellSize.x * 0.55;
    let r = length(local - arcCenter);
    let dArcLine = abs(r - arcR);
    if (dArcLine < 0.05 && local.y < arcCenter.y) { slot = slotB; }
  } else if (colorFunc == 26u) {
    // WEAVE — sunken (between-strand) regions picked into slotB so the
    // negative space (gaps between strands) reads as dark, putting the
    // raised strands in light slot A. Mirror the geometric pass's
    // alternating-cell over-under logic.
    let warp2 = vec2f(
      fbm3(hitPos * (colorExtent * 0.3)),
      fbm3(hitPos * (colorExtent * 0.3) + vec3f(31.0, 17.0, 53.0)),
    );
    let pp = hitPos.xy * colorExtent + warp2 * 0.15;
    let strandH = sin(pp.x * 6.283);
    let strandV = sin(pp.y * 6.283);
    let cellSum = floor(pp.x * 0.5) + floor(pp.y * 0.5);
    let parity = (i32(cellSum) % 2) == 0;
    let dominant = select(strandV, strandH, parity);
    if (dominant < 0.0) { slot = slotB; }                    // gap between strands
  }

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

  let tint = palette[slot].rgb;

  // Depth to NDC [0, 1] (near=0, far=1). Project hit to clip space then
  // normalize — but we can shortcut via the ray parametrization since
  // we already have totalDist (near→far world distance).
  let dNdc = clamp(t / totalDist, 0.0, 1.0);

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
  out.color  = vec4f(tint, 1.0);
  out.normal = vec4f(n * 0.5 + 0.5, select(0.0, 1.0, primShiny));
  out.depth  = vec4f(dNdc, select(0.0, 1.0, primUnlit), 0.0, 1.0);
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
  const maxSteps = options.maxSteps ?? 48

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
      } else {
        f32[base + 4] = p.params[0]
        f32[base + 5] = p.params[1]
      }
      if (p.type === 15) {
        u32[base + 6] = p.params[2]
      } else {
        f32[base + 6] = p.params[2]
      }
      f32[base + 7] = p.params[3]
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
      const rot = p.rotation ?? [0, 0, 0, 1]
      f32[base + 16] = rot[0]
      f32[base + 17] = rot[1]
      f32[base + 18] = rot[2]
      f32[base + 19] = rot[3]
      // vec4 in slot 5: wearFn (u32), wearDepth (f32), wearDensity (f32), pad.
      // wearFn=0 → secondary deformer is off (early-out in the shader).
      u32[base + 20] = p.wearFn ?? 0
      f32[base + 21] = p.wearDepth ?? 0
      f32[base + 22] = p.wearDensity ?? 0
      f32[base + 23] = 0
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
    const uNum = new Uint32Array(uniformData.buffer, 42 * 4, 2)
    uNum[0] = numFaceMarks
    uNum[1] = 0
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
