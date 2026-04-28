// raymarch.wgsl — fullscreen-triangle vertex + fragment raymarcher.
//
// Encodes the scene as a flat array of typed primitives; each pixel marches
// a ray through the scene SDF and shades on hit. Inspired by the engine's
// raymarch_renderer.ts WGSL (READ-ONLY upstream); rewritten minimally for
// the POC scope.

struct Uniforms {
  // World-space camera. cameraDir is the orthographic look direction
  // (pixels are columns parallel to this). cameraUp/Right span the
  // projection plane. orthoExtent.x is the half-width in world units;
  // orthoExtent.y is half-height.
  cameraPos: vec4<f32>,       // .xyz = origin, .w unused
  cameraDir: vec4<f32>,       // .xyz unit dir into scene
  cameraRight: vec4<f32>,
  cameraUp: vec4<f32>,
  orthoExtent: vec4<f32>,     // .xy = half (W,H), .zw = canvas (W,H)
  numPrims: u32,
  maxSteps: u32,
  time: f32,
  _pad: f32,
};

struct Primitive {
  type_: u32,         // 0 sphere, 1 box, 2 capsule, 3 cylinder, 4 ellipsoid, 5 torus, 6 roundedBox
  blendGroup: u32,
  blendRadius: f32,
  paletteSlot: u32,
  params: vec4<f32>,  // shape-specific (radius, half-extents, etc.)
  offset: vec4<f32>,  // .xyz local position
  rotation: vec4<f32>, // quaternion (xyzw)
};

@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var<storage, read> prims: array<Primitive>;
@group(0) @binding(2) var<storage, read> palette: array<vec4<f32>>;

// ─────────── Quaternion → vector rotation (q⁻¹ * v * q for inverse) ───────────
fn quatRot(q: vec4<f32>, v: vec3<f32>) -> vec3<f32> {
  // v' = v + 2 * cross(q.xyz, cross(q.xyz, v) + q.w * v)
  let qv = q.xyz;
  let t = cross(qv, v) + q.w * v;
  return v + 2.0 * cross(qv, t);
}

fn quatInv(q: vec4<f32>) -> vec4<f32> {
  return vec4<f32>(-q.x, -q.y, -q.z, q.w);
}

// ─────────── Primitive SDFs (in primitive-local space) ───────────

fn sdSphere(p: vec3<f32>, r: f32) -> f32 {
  return length(p) - r;
}

fn sdBox(p: vec3<f32>, half: vec3<f32>) -> f32 {
  let q = abs(p) - half;
  return length(max(q, vec3<f32>(0.0))) + min(max(q.x, max(q.y, q.z)), 0.0);
}

fn sdRoundedBox(p: vec3<f32>, half: vec3<f32>, r: f32) -> f32 {
  let inner = max(half - vec3<f32>(r), vec3<f32>(0.0));
  return sdBox(p, inner) - r;
}

fn sdCapsule(p: vec3<f32>, r: f32, hLen: f32) -> f32 {
  let y = clamp(p.y, -hLen, hLen);
  return length(vec3<f32>(p.x, p.y - y, p.z)) - r;
}

fn sdCylinder(p: vec3<f32>, r: f32, hHeight: f32) -> f32 {
  let dx = length(vec3<f32>(p.x, 0.0, p.z)) - r;
  let dy = abs(p.y) - hHeight;
  let outside = length(vec2<f32>(max(dx, 0.0), max(dy, 0.0)));
  let inside = min(max(dx, dy), 0.0);
  return outside + inside;
}

fn sdEllipsoid(p: vec3<f32>, r: vec3<f32>) -> f32 {
  let k0 = length(p / r);
  let k1 = length(p / (r * r));
  if (k1 < 1e-6) { return -min(r.x, min(r.y, r.z)); }
  return k0 * (k0 - 1.0) / k1;
}

fn sdTorus(p: vec3<f32>, R: f32, r: f32) -> f32 {
  let qx = length(vec2<f32>(p.x, p.z)) - R;
  return length(vec2<f32>(qx, p.y)) - r;
}

// Smooth union (polynomial) — Inigo Quilez canonical form.
fn smin(a: f32, b: f32, k: f32) -> f32 {
  if (k <= 0.0) { return min(a, b); }
  let h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
  return mix(b, a, h) - k * h * (1.0 - h);
}

// ─────────── Per-primitive SDF dispatch (in world space) ───────────

fn primSDF(prim: Primitive, p: vec3<f32>) -> f32 {
  // World → primitive-local: subtract offset, rotate by inverse quaternion.
  let local = quatRot(quatInv(prim.rotation), p - prim.offset.xyz);
  switch prim.type_ {
    case 0u: { return sdSphere(local, prim.params.x); }
    case 1u: { return sdBox(local, prim.params.xyz); }
    case 2u: { return sdCapsule(local, prim.params.x, prim.params.y); }
    case 3u: { return sdCylinder(local, prim.params.x, prim.params.y); }
    case 4u: { return sdEllipsoid(local, prim.params.xyz); }
    case 5u: { return sdTorus(local, prim.params.x, prim.params.y); }
    case 6u: { return sdRoundedBox(local, prim.params.xyz, prim.params.w); }
    default: { return 1e10; }
  }
}

// ─────────── Scene SDF: blend within group, hard min across groups ───────────
//
// Pass 1: per-group min/smin accumulator; Pass 2: hard-min across groups.
// Up to 8 blend groups; group 0 == standalone (no smoothing).

const MAX_GROUPS: u32 = 8u;

fn sceneSDF(p: vec3<f32>) -> f32 {
  var groupD: array<f32, MAX_GROUPS>;
  var groupK: array<f32, MAX_GROUPS>;
  var groupSeen: array<bool, MAX_GROUPS>;
  for (var g = 0u; g < MAX_GROUPS; g++) {
    groupD[g] = 1e10;
    groupK[g] = 0.0;
    groupSeen[g] = false;
  }
  var standalone = 1e10;
  let n = u.numPrims;
  for (var i = 0u; i < n; i++) {
    let pr = prims[i];
    let dp = primSDF(pr, p);
    let g = pr.blendGroup;
    if (g == 0u || g >= MAX_GROUPS) {
      standalone = min(standalone, dp);
    } else {
      if (!groupSeen[g]) {
        groupD[g] = dp;
        groupK[g] = pr.blendRadius;
        groupSeen[g] = true;
      } else {
        let k = max(groupK[g], pr.blendRadius);
        groupD[g] = smin(groupD[g], dp, k);
      }
    }
  }
  var best = standalone;
  for (var g = 1u; g < MAX_GROUPS; g++) {
    if (groupSeen[g]) { best = min(best, groupD[g]); }
  }
  return best;
}

fn sceneNormal(p: vec3<f32>) -> vec3<f32> {
  let e = vec2<f32>(0.001, 0.0);
  return normalize(vec3<f32>(
    sceneSDF(p + e.xyy) - sceneSDF(p - e.xyy),
    sceneSDF(p + e.yxy) - sceneSDF(p - e.yxy),
    sceneSDF(p + e.yyx) - sceneSDF(p - e.yyx),
  ));
}

// ─────────── Vertex: full-screen triangle ───────────

struct VOut {
  @builtin(position) pos: vec4<f32>,
  @location(0) ndc: vec2<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VOut {
  // Three vertices that cover the screen with a single triangle:
  //   (-1,-1) (3,-1) (-1,3)
  var positions = array<vec2<f32>, 3>(
    vec2<f32>(-1.0, -1.0),
    vec2<f32>( 3.0, -1.0),
    vec2<f32>(-1.0,  3.0),
  );
  let p = positions[vi];
  var out: VOut;
  out.pos = vec4<f32>(p, 0.0, 1.0);
  out.ndc = p;
  return out;
}

// ─────────── Fragment: raymarch ───────────

@fragment
fn fs_main(in: VOut) -> @location(0) vec4<f32> {
  // NDC ∈ [-1, 1]² → world-space ortho ray origin on the camera plane.
  let halfW = u.orthoExtent.x;
  let halfH = u.orthoExtent.y;
  let dir = normalize(u.cameraDir.xyz);
  let right = normalize(u.cameraRight.xyz);
  let up = normalize(u.cameraUp.xyz);

  let originPlane = u.cameraPos.xyz
    + right * (in.ndc.x * halfW)
    + up * (in.ndc.y * halfH);

  // March along +dir from the camera plane.
  var t = 0.0;
  let maxT = 8.0;
  let eps = 0.001;
  let maxSteps = u.maxSteps;
  var hit = false;
  var hitPos = vec3<f32>(0.0);
  for (var i = 0u; i < maxSteps; i++) {
    let p = originPlane + dir * t;
    let d = sceneSDF(p);
    if (d < eps) {
      hit = true;
      hitPos = p;
      break;
    }
    if (d > maxT - t) { break; }
    t = t + max(d, eps * 0.5);
    if (t > maxT) { break; }
  }
  if (!hit) {
    return vec4<f32>(0.05, 0.06, 0.08, 1.0);
  }

  // Per-prim color: re-evaluate which primitive was nearest at hit; use its
  // palette slot. (Cheap re-scan — fine for POC primitive counts.)
  var bestI = 0u;
  var bestD = 1e10;
  for (var i = 0u; i < u.numPrims; i++) {
    let dp = primSDF(prims[i], hitPos);
    if (dp < bestD) { bestD = dp; bestI = i; }
  }
  let slot = prims[bestI].paletteSlot;
  let baseColor = palette[slot].rgb;

  // Lambert + ambient + soft rim.
  let n = sceneNormal(hitPos);
  let lightDir = normalize(vec3<f32>(0.4, 0.7, 0.6));
  let diffuse = max(0.0, dot(n, lightDir));
  let rim = pow(1.0 - max(0.0, dot(n, -dir)), 2.0) * 0.25;
  let shade = 0.30 + 0.60 * diffuse + rim;
  let col = baseColor * shade;

  return vec4<f32>(col, 1.0);
}
