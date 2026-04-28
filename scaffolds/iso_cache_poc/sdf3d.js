// sdf3d.js — 3D Signed Distance Field primitives + compose ops, JS port.
//
// Adapted from engine/src/character3d/sdf.ts (READ-ONLY reference). All
// math is inlined; no dependency on the engine's vec module. Vectors are
// plain `[x, y, z]` arrays.
//
// Primitives are centered at origin; use translate() to position. Signed
// distance is negative inside the surface, positive outside.

// ─────────── helpers ───────────

const vlen = (x, y, z) => Math.hypot(x, y, z);
const vmax = (a, b) => (a > b ? a : b);
const vmin = (a, b) => (a < b ? a : b);
const clamp = (x, lo, hi) => (x < lo ? lo : x > hi ? hi : x);
const mix = (a, b, t) => a + (b - a) * t;

// ─────────── PRIMITIVES ───────────

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

// Cone (vertical, tip at origin, opens downward to base at y=-height).
// halfAngle in radians.
export function cone(halfAngle, height) {
  const sa = Math.sin(halfAngle);
  const ca = Math.cos(halfAngle);
  return (p) => {
    const q = [vlen(p[0], 0, p[2]), p[1], 0];
    const k = vmax(-q[0] * sa - q[1] * ca, q[1]);
    if (q[1] > 0) return Math.hypot(q[0], q[1]);
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

// ─────────── EXAMPLE ASSETS ───────────

export function swordSDF() {
  const blade = cylinder(0.013, 0.30);
  const guard = translate([0, -0.04, 0], box([0.04, 0.01, 0.015]));
  const grip = translate([0, -0.09, 0], cylinder(0.012, 0.08));
  return smoothUnion(smoothUnion(blade, guard, 0.005), grip, 0.01);
}

export function rockSDF(seed = 0) {
  const rng = (n) => {
    const x = Math.sin(seed * 127.1 + n * 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  const bHalf = [0.30 + rng(1) * 0.2, 0.15 + rng(2) * 0.1, 0.25 + rng(3) * 0.15];
  const sR = 0.15 + rng(4) * 0.15;
  const sP = [rng(5) * 0.3 - 0.15, rng(6) * 0.1, rng(7) * 0.2 - 0.1];
  return smoothUnion(box(bHalf), translate(sP, sphere(sR)), 0.15);
}

export function chibiHeadSDF() {
  const skull = ellipsoid([0.19, 0.21, 0.19]);
  const jawSlit = translate([0, -0.16, 0.10], roundedBox([0.08, 0.02, 0.08], 0.015));
  return smoothSubtract(skull, jawSlit, 0.02);
}
