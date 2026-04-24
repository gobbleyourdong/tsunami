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

/** Color function enum — evaluated at raymarch hit time, picks between
 *  paletteSlot and paletteSlotB based on a per-function rule. All results
 *  palette-quantized so pixel-art consistency holds. */
export type ColorFunc =
  | 0  // flat: always paletteSlot
  | 1  // gradientY: hitPos.y / colorExtent → slotA (bottom) ↔ slotB (top), 3 crisp bands
  | 2  // pulsate: time-oscillating swap between A and B
  | 3  // radialFade: radial distance from primitive origin → A (center) ↔ B (edge)

export interface RaymarchPrimitive {
  type: number             // 0..9, see header comment
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
}

/** Same VATData interface used by skeleton_renderer + chunk_renderer. */
export interface VATData {
  buffer: GPUBuffer
  numInstances: number
  numFrames: number
}

// Storage-buffer layout per primitive (20 floats = 80 bytes):
//   [0..3]    typeAndSlots as u32 cast: type, paletteSlot, boneIdx, colorFunc
//   [4..7]    params x/y/z/w
//   [8..11]   offsetInBone x/y/z/detailAmplitude (normal-pass FBM, 0 = off)
//   [12..15]  slotB (u32) | colorExtent (f32) | blendGroup (u32) | blendRadius (f32, signed)
//   [16..19]  rotation quat (x, y, z, w) — identity (0,0,0,1) if axis-aligned
const PRIM_STRIDE_FLOATS = 20

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
  _pad1:       f32,
  _pad2:       f32,
}

@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var<storage, read> prims: array<vec4f>;     // PRIM_STRIDE_FLOATS per primitive
@group(0) @binding(2) var<storage, read> vatMats: array<vec4f>;   // forward bone matrices
@group(0) @binding(3) var<storage, read> palette: array<vec4f>;

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
fn sdEllipsoid(p: vec3f, r: vec3f) -> f32 {
  let k0 = length(p / r);
  let k1 = length(p / (r * r));
  return (k0 * (k0 - 1.0)) / k1;
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
fn sdTorus(p: vec3f, R: f32, r: f32) -> f32 {
  let qx = length(vec2f(p.x, p.z)) - R;
  return length(vec2f(qx, p.y)) - r;
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
  let base = primIdx * 5u;      // 5 vec4s per primitive (see PRIM_STRIDE_FLOATS)
  let slots = bitcast<vec4u>(prims[base + 0u]);
  let primType    = slots.x;    // 'type' is a WGSL reserved keyword
  let boneIdx     = slots.z;
  let params      = prims[base + 1u];
  let offset      = prims[base + 2u].xyz;

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
  // Primitive-local orientation: read quat from slot 4 and apply its inverse
  // to the march point. Identity (0,0,0,1) is a no-op (the default).
  // Defensive: a zero-init record (w=0, xyz=0) gets swapped to identity.
  let q0 = prims[base + 4u];
  let qIsZero = q0.w == 0.0 && all(q0.xyz == vec3f(0.0));
  let q  = select(q0, vec4f(0.0, 0.0, 0.0, 1.0), qIsZero);
  let qInv = vec4f(-q.x, -q.y, -q.z, q.w);
  let pPrim = rotateByQuat(pBone - offset, qInv);

  switch (primType) {
    case 0u: { return sdSphere(pPrim, params.x); }
    case 1u: { return sdBox(pPrim, params.xyz); }
    case 2u: { return sdRoundedBox(pPrim, params.xyz, params.w); }
    case 3u: { return sdEllipsoid(pPrim, params.xyz); }
    case 4u: { return sdCylinder(pPrim, params.x, params.y); }
    case 5u: { return sdCapsule(pPrim, params.x, params.y); }
    case 6u: { return sdTorus(pPrim, params.x, params.y); }
    case 7u: { return sdFlame(pPrim, params.x, params.y, params.z, params.w, u.time); }
    case 8u: { return sdSwipeArc(pPrim, params.x, params.y, params.z, params.w); }
    case 9u: { return sdLogPolarSineTrail(pPrim, params.x, params.y, params.z, params.w); }
    case 10u: { return sdLightning(pPrim, params.x, params.y, params.z, u.time); }
    case 11u: { return sdNoiseCloud(pPrim, params.x, params.y, params.z, params.w, u.time); }
    case 12u: { return sdCone(pPrim, vec2f(params.x, params.y), params.z); }
    default: { return 1e9; }
  }
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
    let base = i * 5u;
    let cfg  = prims[base + 3u];
    let groupPacked = bitcast<u32>(cfg.z);
    let blendR = cfg.w;

    // Per-primitive occlusion — skip if the primitive's world bounding
    // sphere is farther than the current best. Each primitive self-declares
    // its "can I possibly win" range; evalPrim is expensive, this test is
    // a vec sub + dot + sqrt + compare. On march steps outside the
    // character region 'best' collapses fast once one prim lands, and all
    // far prims short-circuit. "Layer was dumb, occlusion is smart."
    let slots0     = bitcast<vec4u>(prims[base + 0u]);
    let params0    = prims[base + 1u];
    let offset0    = prims[base + 2u].xyz;
    let bone0      = readMat4((u.frameIdx * u.numJoints + slots0.z) * 4u);
    let c00 = bone0[0].xyz;
    let c10 = bone0[1].xyz;
    let c20 = bone0[2].xyz;
    let maxScaleSq = max(max(dot(c00, c00), dot(c10, c10)), dot(c20, c20));
    let worldCtr   = (bone0 * vec4f(offset0, 1.0)).xyz;
    // Conservative upper bound on primitive extent in local space. Sum of
    // absolute params catches sphere radius, capsule r+h, torus R+r, cone
    // tip→base, etc. in one formula — never under-estimates. The 0.05m
    // margin covers smin blend softening, rotation re-orientation, and
    // VFX noise displacement.
    let radiusLocal = abs(params0.x) + abs(params0.y) + abs(params0.z) + abs(params0.w) + 0.05;
    let radiusWorld = radiusLocal * sqrt(maxScaleSq) + abs(blendR);
    let sphereDist  = distance(pWorld, worldCtr) - radiusWorld;
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
    if (groupPacked == 0u || groupPacked > MAX_GROUPS) {
      // Standalone — hard union into scene.
      if (d < best) { best = d; bestIdx = i; }
    } else {
      let g = groupPacked - 1u;
      // Additive primitives own the attribution; subtractors carve and
      // leave attribution to whoever was already there.
      if (blendR >= 0.0 && d < groupArgmin[g]) {
        groupArgmin[g] = d;
        groupIdx[g]    = i;
      }
      if (blendR > 0.0) {
        groupDist[g] = smin_k(groupDist[g], d, blendR);
      } else if (blendR < 0.0) {
        groupDist[g] = smax_k(groupDist[g], -d, -blendR);
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
fn sceneNormal(pWorld: vec3f, eps: f32) -> vec3f {
  let dx = sceneSDF(pWorld + vec3f(eps, 0.0, 0.0), 1u).dist - sceneSDF(pWorld - vec3f(eps, 0.0, 0.0), 1u).dist;
  let dy = sceneSDF(pWorld + vec3f(0.0, eps, 0.0), 1u).dist - sceneSDF(pWorld - vec3f(0.0, eps, 0.0), 1u).dist;
  let dz = sceneSDF(pWorld + vec3f(0.0, 0.0, eps), 1u).dist - sceneSDF(pWorld - vec3f(0.0, 0.0, eps), 1u).dist;
  return normalize(vec3f(dx, dy, dz));
}

// Soft-shadow ray — starts just above the primary hit point, marches
// toward the light. Penumbra estimator from Inigo Quilez's softshadow
// trick: track the min-ratio of (SDF distance / traveled distance), which
// captures how close the ray gets to the surface in angular terms.
// Output: 0 (fully occluded) → 1 (fully lit), quantized at the caller.
// Cost: up to 16 SDF evals per primary hit at sprite resolution — still
// cheaper than one 1080p pixel's worth of raymarch.
fn shadowRay(origin: vec3f, dir: vec3f, minT: f32, maxT: f32) -> f32 {
  var res = 1.0;
  var t = minT;
  for (var i = 0u; i < 16u; i = i + 1u) {
    let h = sceneSDF(origin + dir * t, 0u).dist;
    if (h < 0.0005) { return 0.0; }
    // Penumbra softness: smaller constant → harder shadow.
    res = min(res, 6.0 * h / t);
    t = t + clamp(h, 0.005, 0.1);
    if (t > maxT) { break; }
  }
  return clamp(res, 0.0, 1.0);
}

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
  let base = hitPrim * 5u;   // 5 vec4s per primitive
  let slots = bitcast<vec4u>(prims[base + 0u]);
  let colorCfg = prims[base + 3u];
  let slotsB = bitcast<vec4u>(prims[base + 3u]);
  let slotA = slots.y;
  let colorFunc = slots.w;
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
  }
  let tint = palette[slot].rgb;

  // Depth to NDC [0, 1] (near=0, far=1). Project hit to clip space then
  // normalize — but we can shortcut via the ray parametrization since
  // we already have totalDist (near→far world distance).
  let dNdc = clamp(t / totalDist, 0.0, 1.0);

  // Soft shadow toward the first key light (tunable later via uniform).
  // Quantize to 3 bands so the shadow edge reads like a crisp cel step
  // rather than a smooth gradient — matches the rest of the polish.
  let lightDir = normalize(vec3f(0.6, 0.7, 0.3));
  let shadowRaw = shadowRay(hitPos + n * 0.01, lightDir, 0.01, 2.5);
  var shadowFactor = 0.45;
  if (shadowRaw > 0.66) { shadowFactor = 1.00; }
  else if (shadowRaw > 0.30) { shadowFactor = 0.75; }

  out.color  = vec4f(tint, 1.0);
  // Pack the shadow factor into normal.a so the deferred cel pass can
  // read it alongside the normal and dim the light contribution where
  // occluded. Cube/chunk renderers write normal.a = 1.0 which means
  // "no shadow" — their output passes through unaffected.
  out.normal = vec4f(n * 0.5 + 0.5, shadowFactor);
  out.depth  = vec4f(dNdc, 0.0, 0.0, 1.0);
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
   *  fullscreen triangle with three texture loads per pixel. */
  blitCacheToPass(pass: GPURenderPassEncoder): void
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
      // vec4<u32> in slot 0: type, slotA, boneIdx, colorFunc
      u32[base + 0] = p.type
      u32[base + 1] = p.paletteSlot
      u32[base + 2] = p.boneIdx
      u32[base + 3] = p.colorFunc ?? 0
      // vec4<f32> in slot 1: params
      f32[base + 4] = p.params[0]
      f32[base + 5] = p.params[1]
      f32[base + 6] = p.params[2]
      f32[base + 7] = p.params[3]
      // vec4<f32> in slot 2: offset in bone (xyz) + detailAmplitude (w)
      f32[base + 8] = p.offsetInBone[0]
      f32[base + 9] = p.offsetInBone[1]
      f32[base + 10] = p.offsetInBone[2]
      f32[base + 11] = p.detailAmplitude ?? 0
      // vec4 in slot 3: slotB (u32), colorExtent (f32), blendGroup (u32), blendRadius (f32 signed)
      u32[base + 12] = p.paletteSlotB ?? p.paletteSlot
      f32[base + 13] = p.colorExtent ?? 0.1
      u32[base + 14] = p.blendGroup ?? 0
      f32[base + 15] = p.blendRadius ?? 0
      // vec4 in slot 4: rotation quaternion (x, y, z, w). Identity if absent.
      const rot = p.rotation ?? [0, 0, 0, 1]
      f32[base + 16] = rot[0]
      f32[base + 17] = rot[1]
      f32[base + 18] = rot[2]
      f32[base + 19] = rot[3]
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
@group(0) @binding(0) var colorTex:  texture_2d<f32>;
@group(0) @binding(1) var normalTex: texture_2d<f32>;
@group(0) @binding(2) var depthTex:  texture_2d<f32>;

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
  let px = vec2i(in.clip.xy);
  var out: FsOut;
  out.color  = textureLoad(colorTex,  px, 0);
  out.normal = textureLoad(normalTex, px, 0);
  out.depth  = textureLoad(depthTex,  px, 0);
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
    blitCacheToPass(pass) {
      if (!cacheBlitBindGroup) return
      pass.setPipeline(blitPipeline)
      pass.setBindGroup(0, cacheBlitBindGroup)
      pass.draw(3)
    },
  }
}
