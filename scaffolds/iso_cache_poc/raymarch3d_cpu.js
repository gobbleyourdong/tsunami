// raymarch3d_cpu.js — JS 3D SDF primitives + compose ops + transforms.
// Pure browser-friendly module, no deps. Used by object_buffer_cache.html
// to evaluate 3D SDFs per pixel inside the existing GameObject.bake().
//
// Vec3 = [x, y, z] arrays. SDFs are functions Vec3 → number (signed
// distance: negative inside, positive outside, zero at the surface).
//
// Adapted from engine/src/character3d/sdf.ts (READ-ONLY upstream).
// The TS sibling lives at raymarch3d/sdf3d.ts; this is a parallel JS
// version so the no-build 2D demo can `import` it directly.

// ─────────── helpers ───────────

const vlen = (x, y, z) => Math.hypot(x, y, z);
const vmax = (a, b) => (a > b ? a : b);
const vmin = (a, b) => (a < b ? a : b);
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const mix = (a, b, t) => a + (b - a) * t;

// ─────────── PRIMITIVES (centered at origin) ───────────

export function sphere(radius) {
  return (p) => vlen(p[0], p[1], p[2]) - radius;
}

export function box(half) {
  return (p) => {
    const dx = Math.abs(p[0]) - half[0];
    const dy = Math.abs(p[1]) - half[1];
    const dz = Math.abs(p[2]) - half[2];
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), vmax(dz, 0));
    const inside = vmin(vmax(dx, vmax(dy, dz)), 0);
    return outside + inside;
  };
}

export function roundedBox(half, cornerRadius) {
  const inner = [
    vmax(half[0] - cornerRadius, 0),
    vmax(half[1] - cornerRadius, 0),
    vmax(half[2] - cornerRadius, 0),
  ];
  const base = box(inner);
  return (p) => base(p) - cornerRadius;
}

export function ellipsoid(radii) {
  return (p) => {
    const k0 = vlen(p[0] / radii[0], p[1] / radii[1], p[2] / radii[2]);
    const k1 = vlen(
      p[0] / (radii[0] * radii[0]),
      p[1] / (radii[1] * radii[1]),
      p[2] / (radii[2] * radii[2]),
    );
    if (k1 < 1e-12) return -Math.min(radii[0], radii[1], radii[2]);
    return (k0 * (k0 - 1)) / k1;
  };
}

export function cylinder(radius, height) {
  const h = height / 2;
  return (p) => {
    const dx = vlen(p[0], 0, p[2]) - radius;
    const dy = Math.abs(p[1]) - h;
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), 0);
    const inside = vmin(vmax(dx, dy), 0);
    return outside + inside;
  };
}

export function capsule(radius, length) {
  const h = length / 2;
  return (p) => {
    const y = clamp(p[1], -h, h);
    return vlen(p[0], p[1] - y, p[2]) - radius;
  };
}

export function torus(majorRadius, minorRadius) {
  return (p) => {
    const qx = vlen(p[0], 0, p[2]) - majorRadius;
    return vlen(qx, p[1], 0) - minorRadius;
  };
}

export function plane(normal, offset = 0) {
  return (p) => p[0] * normal[0] + p[1] * normal[1] + p[2] * normal[2] + offset;
}

// Cone (vertical, tip at origin, opens DOWNWARD; base at y = -height).
// halfAngle in radians.
export function cone(halfAngle, height) {
  const sa = Math.sin(halfAngle);
  const ca = Math.cos(halfAngle);
  return (p) => {
    // Distance to lateral surface
    const r = vlen(p[0], 0, p[2]);
    // Plane orthogonal to slope, opening downward
    const k = vmax(-r * sa - p[1] * ca, p[1]);
    if (p[1] > 0) return Math.hypot(r, p[1]); // above tip
    if (p[1] < -height) return Math.hypot(Math.max(r - height * Math.tan(halfAngle), 0), p[1] + height);
    return k;
  };
}

// ─────────── COMPOSE ───────────

export function union(...fs) {
  return (p) => {
    let d = fs[0](p);
    for (let i = 1; i < fs.length; i++) d = vmin(d, fs[i](p));
    return d;
  };
}

export function smoothUnion(a, b, k) {
  return (p) => {
    const da = a(p), db = b(p);
    if (k <= 0) return vmin(da, db);
    const h = clamp(0.5 + 0.5 * (db - da) / k, 0, 1);
    return mix(db, da, h) - k * h * (1 - h);
  };
}

export function intersect(a, b) {
  return (p) => vmax(a(p), b(p));
}

export function subtract(a, b) {
  return (p) => vmax(a(p), -b(p));
}

export function smoothSubtract(a, b, k) {
  return (p) => {
    const da = a(p), db = b(p);
    if (k <= 0) return vmax(da, -db);
    const h = clamp(0.5 - 0.5 * (db + da) / k, 0, 1);
    return mix(da, -db, h) + k * h * (1 - h);
  };
}

// ─────────── TRANSFORMS ───────────

export function translate(offset, f) {
  return (p) => f([p[0] - offset[0], p[1] - offset[1], p[2] - offset[2]]);
}

export function scale(s, f) {
  return (p) => f([p[0] / s, p[1] / s, p[2] / s]) * s;
}

export function rotateY(angle, f) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([c * p[0] + s * p[2], p[1], -s * p[0] + c * p[2]]);
}

export function rotateX(angle, f) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([p[0], c * p[1] - s * p[2], s * p[1] + c * p[2]]);
}

export function rotateZ(angle, f) {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]]);
}

export function mirrorX(f) {
  return (p) => f([Math.abs(p[0]), p[1], p[2]]);
}

// ─────────── EVAL HELPERS ───────────

export function gradient(f, p, eps = 1e-3) {
  const px = [p[0] + eps, p[1], p[2]];
  const py = [p[0] - eps, p[1], p[2]];
  const qx = [p[0], p[1] + eps, p[2]];
  const qy = [p[0], p[1] - eps, p[2]];
  const rx = [p[0], p[1], p[2] + eps];
  const ry = [p[0], p[1], p[2] - eps];
  return [f(px) - f(py), f(qx) - f(qy), f(rx) - f(ry)];
}

export function normalize(v) {
  const l = vlen(v[0], v[1], v[2]);
  if (l < 1e-12) return [0, 1, 0];
  return [v[0] / l, v[1] / l, v[2] / l];
}
