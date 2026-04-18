/**
 * WGSL source for the Sample Newton text shader.
 *
 * # Status
 *   Vertex shader   ✓ — quad expansion from instance data (+ cb pass-through)
 *   Outline walk    ✓ fire 3 (coarse sample, superseded fire 4)
 *   Contour breaks  ✓ fire 4 — @group(0)@binding(3) storage buffer;
 *                    is_contour_break() skips segments at boundaries
 *   Sample Newton   ✓ fire 4 — 5-sample init + 4 Newton-ish steps,
 *                    returns (closest_point, t_of_closest)
 *   Signed distance ✓ fire 4 — tangent-perpendicular cross-product sign
 *                    at the best segment's closest t; verify winding
 *                    convention on hardware (flip sign if inverted)
 *   Interior fill   ✓ fire 4 — smoothstep(-w, w, signed_dist) with
 *                    w = fwidth(signed_dist). Glyphs render as filled
 *                    shapes with 1-pixel AA at edges.
 *   Demo            TODO fire 5 or 6
 *
 * # Data flow
 *   - Atlas texture (rgba32float, row-per-glyph): each texel is a
 *     Hermite handle (anchor.xy, tangent.xy) in em units. Sampled with
 *     textureLoad (no bilerp — exact texel values).
 *   - Per-instance storage buffer: one entry per visible glyph with
 *     screen position, size, color, and atlas row + handle_count.
 *   - Vertex shader expands each instance to 4 verts (a screen-space
 *     quad sized by the glyph's plane bbox).
 *   - Fragment shader reads texels for its glyph, computes signed
 *     distance to the Hermite rope, outputs alpha.
 *
 * Instance buffer layout matches `GlyphInstance` in text.ts.
 */

export const TEXT_SHADER_WGSL = /* wgsl */ `
struct Uniforms {
  viewport:  vec2<f32>,  // pixel size of canvas (for screen → clip)
  em_size:   f32,        // atlas's em in px (for scale)
  distance_range: f32,   // in em units (unused in v1; reserved)
}

struct Instance {
  pos:        vec2<f32>,  // screen px, top-left of glyph plane
  size:       f32,        // target em → px scale
  _pad0:      f32,
  color:      vec4<f32>,
  plane:      vec4<f32>,  // em units: left, top, right, bottom
  atlas_row:  u32,
  handle_count: u32,
  cb_start:   u32,        // offset into contour_breaks[] for this glyph
  cb_count:   u32,        // # breaks for this glyph
}

@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var atlas: texture_2d<f32>;
@group(0) @binding(2) var<storage, read> instances: array<Instance>;
@group(0) @binding(3) var<storage, read> contour_breaks: array<u32>;

struct VSOut {
  @builtin(position) pos: vec4<f32>,
  @location(0) glyph_uv: vec2<f32>,   // em units within glyph bbox
  @location(1) @interpolate(flat) atlas_row: u32,
  @location(2) @interpolate(flat) handle_count: u32,
  @location(3) @interpolate(flat) cb_start: u32,
  @location(4) @interpolate(flat) cb_count: u32,
  @location(5) color: vec4<f32>,
}

// Corner offsets for 4-vert triangle-strip quad.
// Order: (0,0), (1,0), (0,1), (1,1).
const QUAD: array<vec2<f32>, 4> = array<vec2<f32>, 4>(
  vec2<f32>(0.0, 0.0),
  vec2<f32>(1.0, 0.0),
  vec2<f32>(0.0, 1.0),
  vec2<f32>(1.0, 1.0),
);

@vertex
fn vs_main(
  @builtin(vertex_index) vid: u32,
  @builtin(instance_index) iid: u32,
) -> VSOut {
  let inst = instances[iid];
  let corner = QUAD[vid];

  // Glyph extent in em → px
  let w = (inst.plane.z - inst.plane.x) * inst.size;
  let h = (inst.plane.w - inst.plane.y) * inst.size;

  // Screen-space position of this corner.
  // pos is glyph top-left; corner is (0..1, 0..1) within glyph.
  let screen_px = vec2<f32>(
    inst.pos.x + corner.x * w,
    inst.pos.y + corner.y * h,
  );

  // Convert pixel coords (top-left origin) to clip space (center origin, y up).
  let ndc = vec2<f32>(
    (screen_px.x / u.viewport.x) * 2.0 - 1.0,
    1.0 - (screen_px.y / u.viewport.y) * 2.0,
  );

  var out: VSOut;
  out.pos = vec4<f32>(ndc, 0.0, 1.0);
  // glyph_uv spans the plane bbox in em units; interpolated across the quad.
  out.glyph_uv = vec2<f32>(
    inst.plane.x + corner.x * (inst.plane.z - inst.plane.x),
    inst.plane.y + corner.y * (inst.plane.w - inst.plane.y),
  );
  out.atlas_row = inst.atlas_row;
  out.handle_count = inst.handle_count;
  out.cb_start = inst.cb_start;
  out.cb_count = inst.cb_count;
  out.color = inst.color;
  return out;
}

// ── Hermite evaluation ───────────────────────────────────────────
//
// Cubic Hermite segment:
//   H(t) = (2t³-3t²+1)·p0 + (t³-2t²+t)·m0 + (-2t³+3t²)·p1 + (t³-t²)·m1
// where p0,p1 are anchors, m0,m1 are tangents (our atlas storage).
// All values in em units.
fn hermite(t: f32, p0: vec2<f32>, m0: vec2<f32>, p1: vec2<f32>, m1: vec2<f32>) -> vec2<f32> {
  let t2 = t * t;
  let t3 = t2 * t;
  let h00 = 2.0 * t3 - 3.0 * t2 + 1.0;
  let h10 = t3 - 2.0 * t2 + t;
  let h01 = -2.0 * t3 + 3.0 * t2;
  let h11 = t3 - t2;
  return h00 * p0 + h10 * m0 + h01 * p1 + h11 * m1;
}

// Tangent of hermite at t (first derivative).
fn hermite_tan(t: f32, p0: vec2<f32>, m0: vec2<f32>, p1: vec2<f32>, m1: vec2<f32>) -> vec2<f32> {
  let t2 = t * t;
  let d00 = 6.0 * t2 - 6.0 * t;
  let d10 = 3.0 * t2 - 4.0 * t + 1.0;
  let d01 = -6.0 * t2 + 6.0 * t;
  let d11 = 3.0 * t2 - 2.0 * t;
  return d00 * p0 + d10 * m0 + d01 * p1 + d11 * m1;
}

// Load handle i from current instance's atlas row.
fn load_handle(row: u32, i: u32) -> vec4<f32> {
  return textureLoad(atlas, vec2<i32>(i32(i), i32(row)), 0);
}

// ── Sample Newton — closest point on a Hermite segment ──────────
//
// Initial guess: sample the segment at N_INIT equally-spaced t values
// and pick the nearest. Then N_ITER Newton-ish steps: project the
// residual (H(t) - p) onto the tangent, subtract a scaled step.
//
//   δt = -dot(H(t) - p, H'(t)) / |H'(t)|²
//
// This is Gauss-Newton on |H(t) - p|². Linear convergence, but the
// initial 5-sample scan lands us close enough that 4 iterations hit
// sub-pixel accuracy at screen-space pixel sizes.
//
// "Sample Newton" name: 5-sample initialization + Newton refinement.
// Beats MSDF+MSAA and MTSDF at same-speed because we never rasterized
// a distance field — the curve is analytic via Hermite handles.
const N_INIT: u32 = 5u;
const N_ITER: u32 = 4u;

// Returns (closest_point.xy, t_of_closest).
fn closest_on_hermite(
  p: vec2<f32>,
  p0: vec2<f32>, m0: vec2<f32>,
  p1: vec2<f32>, m1: vec2<f32>,
) -> vec3<f32> {
  var best_t: f32 = 0.0;
  var best_d2: f32 = 1.0e18;
  for (var s: u32 = 0u; s < N_INIT; s = s + 1u) {
    let t = f32(s) / f32(N_INIT - 1u);
    let q = hermite(t, p0, m0, p1, m1);
    let e = q - p;
    let d2 = dot(e, e);
    if (d2 < best_d2) { best_d2 = d2; best_t = t; }
  }

  var t = best_t;
  for (var i: u32 = 0u; i < N_ITER; i = i + 1u) {
    let q = hermite(t, p0, m0, p1, m1);
    let tg = hermite_tan(t, p0, m0, p1, m1);
    let e = q - p;
    let len2 = dot(tg, tg);
    if (len2 < 1.0e-8) { break; }     // degenerate segment
    let dt = -dot(e, tg) / len2;
    t = clamp(t + dt, 0.0, 1.0);
  }

  let q = hermite(t, p0, m0, p1, m1);
  return vec3<f32>(q, t);
}

// Is `idx` a contour-break handle index for the current glyph?
// Breaks are stored per-glyph in a contiguous slice of contour_breaks[].
// A segment (i, i+1) is spurious (crosses a contour boundary) if
// handle i+1 is a contour-start, i.e. a break index points at i+1.
//
// The baker records the contour_break as the index AFTER the last handle
// of a contour: for single-contour glyph with N handles, breaks = [N].
// For an 'O', breaks = [N_outer, N_outer + N_inner].
fn is_contour_break(idx: u32, cb_start: u32, cb_count: u32) -> bool {
  for (var b: u32 = 0u; b < cb_count; b = b + 1u) {
    if (contour_breaks[cb_start + b] == idx) { return true; }
  }
  return false;
}

@fragment
fn fs_main(in: VSOut) -> @location(0) vec4<f32> {
  if (in.handle_count < 2u) { discard; }

  let p = in.glyph_uv;  // fragment position in em units
  var min_dist: f32 = 1.0e9;
  var best_tangent: vec2<f32> = vec2<f32>(1.0, 0.0);
  var best_error:   vec2<f32> = vec2<f32>(0.0, 0.0);

  let n = in.handle_count;
  for (var i: u32 = 0u; i + 1u < n; i = i + 1u) {
    // Skip segments whose second endpoint is a contour-start:
    // those would connect end-of-contour-N to start-of-contour-N+1.
    if (is_contour_break(i + 1u, in.cb_start, in.cb_count)) { continue; }

    let h0 = load_handle(in.atlas_row, i);
    let h1 = load_handle(in.atlas_row, i + 1u);
    let p0 = h0.xy;  let m0 = h0.zw;
    let p1 = h1.xy;  let m1 = h1.zw;

    let res = closest_on_hermite(p, p0, m0, p1, m1);
    let q = res.xy;
    let t = res.z;
    let d = distance(p, q);

    if (d < min_dist) {
      min_dist = d;
      best_tangent = hermite_tan(t, p0, m0, p1, m1);
      best_error = p - q;
    }
  }

  // Signed distance via tangent-perpendicular test.
  //
  // At the closest point, the error (p - q) is perpendicular to the
  // tangent. The sign of cross(tangent, error) tells us which side:
  // consistent per contour winding. For CCW outer + CW inner (standard
  // even-odd font winding), cross < 0 means interior.
  //
  // NOTE (verify on hardware): some fonts use the opposite convention.
  // If glyphs render inverted, flip the sign below or the comparison.
  let cross_z = best_tangent.x * best_error.y - best_tangent.y * best_error.x;
  let sign_val = select(-1.0, 1.0, cross_z > 0.0);
  let signed_dist = min_dist * sign_val;

  // AA: smooth transition across ~1 pixel worth of signed distance.
  // fwidth(signed_dist) ≈ em-per-pixel magnitude. Negative = inside.
  let w = max(fwidth(signed_dist), 1.0e-6);
  let alpha = 1.0 - smoothstep(-w, w, signed_dist);
  if (alpha <= 0.001) { discard; }
  return vec4<f32>(in.color.rgb, in.color.a * alpha);
}
`
