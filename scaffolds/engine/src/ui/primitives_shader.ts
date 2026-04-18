/**
 * WGSL for UI primitives — rect, rounded-rect, border.
 *
 * # Status
 *   Vertex                 ✓ scaffold (quad expansion, screen → clip)
 *   Rounded-rect SDF        ✓ scaffold (standard formula)
 *   Border stroke via SDF   ✓ scaffold (|sd| band, AA via fwidth)
 *   Drop shadow             TODO v1.2 (2nd pass with blurred outer SDF)
 *   Gradient fill           TODO v1.2
 *
 * Instance layout matches `QuadInstance` in primitives.ts (64 bytes):
 *   pos.xy (8) | size.xy (8) | color.rgba (16) | border_color.rgba (16)
 *   | radius (4) | border_width (4) | _pad (8)
 */

export const PRIMITIVES_SHADER_WGSL = /* wgsl */ `
struct Uniforms {
  viewport: vec2<f32>,
  _pad: vec2<f32>,
}

struct Instance {
  pos:          vec2<f32>,  // top-left pixel coords
  size:         vec2<f32>,  // width, height in pixels
  color:        vec4<f32>,  // fill RGBA
  border_color: vec4<f32>,  // border RGBA
  radius:       f32,        // corner radius in pixels
  border_width: f32,        // 0 = no border; otherwise px inward
  _pad:         vec2<f32>,
}

@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var<storage, read> instances: array<Instance>;

struct VSOut {
  @builtin(position) clip: vec4<f32>,
  @location(0)                         local: vec2<f32>,  // centered, in pixels
  @location(1) @interpolate(flat)      half_size: vec2<f32>,
  @location(2) @interpolate(flat)      color: vec4<f32>,
  @location(3) @interpolate(flat)      border_color: vec4<f32>,
  @location(4) @interpolate(flat)      radius: f32,
  @location(5) @interpolate(flat)      border_width: f32,
}

const QUAD: array<vec2<f32>, 4> = array<vec2<f32>, 4>(
  vec2<f32>(0.0, 0.0), vec2<f32>(1.0, 0.0),
  vec2<f32>(0.0, 1.0), vec2<f32>(1.0, 1.0),
);

@vertex
fn vs_main(
  @builtin(vertex_index) vid: u32,
  @builtin(instance_index) iid: u32,
) -> VSOut {
  let inst = instances[iid];
  let corner = QUAD[vid];

  let screen_px = inst.pos + corner * inst.size;
  let ndc = vec2<f32>(
    (screen_px.x / u.viewport.x) * 2.0 - 1.0,
    1.0 - (screen_px.y / u.viewport.y) * 2.0,
  );

  var out: VSOut;
  out.clip = vec4<f32>(ndc, 0.0, 1.0);
  // Local coord centered on the rect, in pixels.
  out.local = (corner - vec2<f32>(0.5, 0.5)) * inst.size;
  out.half_size    = inst.size * 0.5;
  out.color        = inst.color;
  out.border_color = inst.border_color;
  out.radius       = inst.radius;
  out.border_width = inst.border_width;
  return out;
}

// Signed distance to an axis-aligned rounded box centered at origin.
// Inside is negative. Classic Quilez formula.
fn sd_rounded_box(p: vec2<f32>, half_size: vec2<f32>, r: f32) -> f32 {
  let q = abs(p) - half_size + vec2<f32>(r, r);
  return min(max(q.x, q.y), 0.0) + length(max(q, vec2<f32>(0.0, 0.0))) - r;
}

@fragment
fn fs_main(in: VSOut) -> @location(0) vec4<f32> {
  let sd = sd_rounded_box(in.local, in.half_size, in.radius);

  // Outside the rounded rect → discard (with AA band handled below).
  let w = max(fwidth(sd), 1.0e-6);

  // Outer alpha: 1 inside, 0 outside, AA over 1 fwidth band.
  let fill_a = 1.0 - smoothstep(-w, w, sd);
  if (fill_a <= 0.001) { discard; }

  if (in.border_width > 0.0) {
    // Border band: |sd + border_width/2| < border_width/2 from the edge.
    // Equivalent: sd in [-border_width, 0].
    let bw = in.border_width;
    let band = smoothstep(-bw - w, -bw + w, sd) * (1.0 - smoothstep(-w, w, sd));
    // Result = fill × (1 - band) + border × band, premultiplied by fill_a.
    let rgb = mix(in.color.rgb, in.border_color.rgb, band);
    let a   = mix(in.color.a,   in.border_color.a,   band) * fill_a;
    return vec4<f32>(rgb, a);
  }

  return vec4<f32>(in.color.rgb, in.color.a * fill_a);
}
`
