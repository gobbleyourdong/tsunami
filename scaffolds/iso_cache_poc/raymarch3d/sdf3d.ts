// sdf3d.ts — 3D Signed Distance Field primitives + compose ops.
// TypeScript port of engine/src/character3d/sdf.ts (READ-ONLY upstream).
// Vec3 = [x, y, z] tuple; SDFs are functions Vec3 → number.
//
// All math inlined; no engine deps. Used for CPU-side asset previewing
// and for generating the flat primitive list that the WGSL shader consumes.

export type Vec3 = readonly [number, number, number];
export type SDF = (p: Vec3) => number;

const vlen = (x: number, y: number, z: number): number => Math.hypot(x, y, z);
const vmax = (a: number, b: number): number => (a > b ? a : b);
const vmin = (a: number, b: number): number => (a < b ? a : b);
const clamp = (x: number, lo: number, hi: number): number =>
  x < lo ? lo : x > hi ? hi : x;
const mix = (a: number, b: number, t: number): number => a + (b - a) * t;

// ─────────── PRIMITIVES (centered at origin) ───────────

export function sphere(radius: number): SDF {
  return (p) => vlen(p[0], p[1], p[2]) - radius;
}

export function box(half: Vec3): SDF {
  return (p) => {
    const dx = Math.abs(p[0]) - half[0];
    const dy = Math.abs(p[1]) - half[1];
    const dz = Math.abs(p[2]) - half[2];
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), vmax(dz, 0));
    const inside = vmin(vmax(dx, vmax(dy, dz)), 0);
    return outside + inside;
  };
}

export function roundedBox(half: Vec3, cornerRadius: number): SDF {
  const inner: Vec3 = [
    vmax(half[0] - cornerRadius, 0),
    vmax(half[1] - cornerRadius, 0),
    vmax(half[2] - cornerRadius, 0),
  ];
  const base = box(inner);
  return (p) => base(p) - cornerRadius;
}

export function ellipsoid(radii: Vec3): SDF {
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

export function cylinder(radius: number, height: number): SDF {
  const h = height / 2;
  return (p) => {
    const dx = vlen(p[0], 0, p[2]) - radius;
    const dy = Math.abs(p[1]) - h;
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), 0);
    const inside = vmin(vmax(dx, dy), 0);
    return outside + inside;
  };
}

export function capsule(radius: number, length: number): SDF {
  const h = length / 2;
  return (p) => {
    const y = clamp(p[1], -h, h);
    return vlen(p[0], p[1] - y, p[2]) - radius;
  };
}

export function torus(majorRadius: number, minorRadius: number): SDF {
  return (p) => {
    const qx = vlen(p[0], 0, p[2]) - majorRadius;
    return vlen(qx, p[1], 0) - minorRadius;
  };
}

export function plane(normal: Vec3, offset = 0): SDF {
  return (p) => p[0] * normal[0] + p[1] * normal[1] + p[2] * normal[2] + offset;
}

// ─────────── COMPOSE ───────────

export function union(...fs: SDF[]): SDF {
  return (p) => {
    let d = fs[0](p);
    for (let i = 1; i < fs.length; i++) d = vmin(d, fs[i](p));
    return d;
  };
}

export function smoothUnion(a: SDF, b: SDF, k: number): SDF {
  return (p) => {
    const da = a(p), db = b(p);
    const h = clamp(0.5 + (0.5 * (db - da)) / k, 0, 1);
    return mix(db, da, h) - k * h * (1 - h);
  };
}

export function intersect(a: SDF, b: SDF): SDF {
  return (p) => vmax(a(p), b(p));
}

export function subtract(a: SDF, b: SDF): SDF {
  return (p) => vmax(a(p), -b(p));
}

export function smoothSubtract(a: SDF, b: SDF, k: number): SDF {
  return (p) => {
    const da = a(p), db = b(p);
    const h = clamp(0.5 - (0.5 * (db + da)) / k, 0, 1);
    return mix(da, -db, h) + k * h * (1 - h);
  };
}

// ─────────── TRANSFORMS ───────────

export function translate(offset: Vec3, f: SDF): SDF {
  return (p) => f([p[0] - offset[0], p[1] - offset[1], p[2] - offset[2]]);
}

export function scale(s: number, f: SDF): SDF {
  return (p) => f([p[0] / s, p[1] / s, p[2] / s]) * s;
}

export function rotateY(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([c * p[0] + s * p[2], p[1], -s * p[0] + c * p[2]]);
}

export function rotateX(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([p[0], c * p[1] - s * p[2], s * p[1] + c * p[2]]);
}

export function rotateZ(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle);
  return (p) => f([c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]]);
}

export function mirrorX(f: SDF): SDF {
  return (p) => f([Math.abs(p[0]), p[1], p[2]]);
}

// ─────────── EVAL HELPERS ───────────

export function gradient(f: SDF, p: Vec3, eps = 1e-3): Vec3 {
  const px: Vec3 = [p[0] + eps, p[1], p[2]];
  const py: Vec3 = [p[0] - eps, p[1], p[2]];
  const qx: Vec3 = [p[0], p[1] + eps, p[2]];
  const qy: Vec3 = [p[0], p[1] - eps, p[2]];
  const rx: Vec3 = [p[0], p[1], p[2] + eps];
  const ry: Vec3 = [p[0], p[1], p[2] - eps];
  return [f(px) - f(py), f(qx) - f(qy), f(rx) - f(ry)];
}

export function normalize(v: Vec3): Vec3 {
  const l = vlen(v[0], v[1], v[2]);
  if (l < 1e-12) return [0, 1, 0];
  return [v[0] / l, v[1] / l, v[2] / l];
}

// ─────────── EXAMPLE ASSETS ───────────

export function swordSDF(): SDF {
  const blade = cylinder(0.013, 0.30);
  const guard = translate([0, -0.04, 0], box([0.04, 0.01, 0.015]));
  const grip = translate([0, -0.09, 0], cylinder(0.012, 0.08));
  return smoothUnion(smoothUnion(blade, guard, 0.005), grip, 0.01);
}

export function rockSDF(seed = 0): SDF {
  const rng = (n: number): number => {
    const x = Math.sin(seed * 127.1 + n * 311.7) * 43758.5453;
    return x - Math.floor(x);
  };
  const bHalf: Vec3 = [
    0.30 + rng(1) * 0.2,
    0.15 + rng(2) * 0.1,
    0.25 + rng(3) * 0.15,
  ];
  const sR = 0.15 + rng(4) * 0.15;
  const sP: Vec3 = [rng(5) * 0.3 - 0.15, rng(6) * 0.1, rng(7) * 0.2 - 0.1];
  return smoothUnion(box(bHalf), translate(sP, sphere(sR)), 0.15);
}

export function chibiHeadSDF(): SDF {
  const skull = ellipsoid([0.19, 0.21, 0.19]);
  const jawSlit = translate(
    [0, -0.16, 0.10],
    roundedBox([0.08, 0.02, 0.08], 0.015),
  );
  return smoothSubtract(skull, jawSlit, 0.02);
}
