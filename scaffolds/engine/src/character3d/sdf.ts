/**
 * Signed Distance Field primitives and compose operators.
 *
 * WHAT AN SDF IS
 * ==============
 * A function `f(p: vec3) → number` that returns the signed distance from
 * point p to the nearest surface: negative inside, positive outside,
 * zero at the surface. Primitives have exact formulas; compose ops
 * combine multiple SDFs into one.
 *
 * WHY SDF-AS-BAKE-FORMAT FOR PIXEL-PERFECT 3D
 * -------------------------------------------
 *   1. Assets are code, not data — "rock" is 200 bytes of parameters,
 *      not 5KB of mesh.
 *   2. Variation is free: one primitive + seeded params → N variants,
 *      no duplicate storage.
 *   3. Edits propagate — change the primitive, every instance re-bakes.
 *   4. No UV hell — normals come from gradient, colors from palette
 *      slot bindings. The pixelizer + palette LUT handle everything.
 *   5. Compose ops do what meshes can't cheaply: smoothUnion → organic
 *      blend with no mesh surgery; subtract → clean boolean hole.
 *
 * THE PIPELINE
 * ------------
 *    SDF tree ──(marching cubes @ target cell size)──▶ polygonal mesh
 *                                                       │
 *    optional: + bone weights per vertex                │
 *    optional: + palette slot per face                  │
 *                                                       ▼
 *                                              live 3D render
 *                                              → pose cache
 *                                              → pixel-perfect output
 *
 * We stay polygonal at runtime because skinned deformation is cheap on
 * meshes and expensive on SDFs. SDF is an AUTHORING + BAKE substrate.
 *
 * Primitive formulas follow Inigo Quilez's canonical catalog.
 */

import type { Vec3 } from '../math/vec'

/** An SDF is a function: point → distance. */
export type SDF = (p: Vec3) => number

// --- Vector helpers (internal; we don't want vec.ts import bloat here) ---

function vlen(x: number, y: number, z: number): number {
  return Math.hypot(x, y, z)
}

function vmax(a: number, b: number): number {
  return a > b ? a : b
}

function vmin(a: number, b: number): number {
  return a < b ? a : b
}

function clamp(x: number, lo: number, hi: number): number {
  return x < lo ? lo : x > hi ? hi : x
}

function mix(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

// --- PRIMITIVES ---
// All primitives are centered at origin. Use translate() to position.

/** Solid sphere of the given radius. */
export function sphere(radius: number): SDF {
  return (p) => vlen(p[0], p[1], p[2]) - radius
}

/** Axis-aligned box with half-extents [hx, hy, hz]. */
export function box(half: [number, number, number]): SDF {
  return (p) => {
    const dx = Math.abs(p[0]) - half[0]
    const dy = Math.abs(p[1]) - half[1]
    const dz = Math.abs(p[2]) - half[2]
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), vmax(dz, 0))
    const inside = vmin(vmax(dx, vmax(dy, dz)), 0)
    return outside + inside
  }
}

/** Box with rounded corners — radius is subtracted from each half-extent
 *  and added back as a smooth edge. Nice for hand-grip handles, pauldrons. */
export function roundedBox(half: [number, number, number], cornerRadius: number): SDF {
  const inner: [number, number, number] = [
    vmax(half[0] - cornerRadius, 0),
    vmax(half[1] - cornerRadius, 0),
    vmax(half[2] - cornerRadius, 0),
  ]
  const base = box(inner)
  return (p) => base(p) - cornerRadius
}

/** Axis-aligned ellipsoid with radii [rx, ry, rz]. Inigo's "inexact"
 *  variant (Lipschitz-bounded, good for MC). */
export function ellipsoid(radii: [number, number, number]): SDF {
  return (p) => {
    const k0 = vlen(p[0] / radii[0], p[1] / radii[1], p[2] / radii[2])
    const k1 = vlen(
      p[0] / (radii[0] * radii[0]),
      p[1] / (radii[1] * radii[1]),
      p[2] / (radii[2] * radii[2]),
    )
    return (k0 * (k0 - 1)) / k1
  }
}

/** Vertical cylinder along +Y, with radius and total height.
 *  Height is the full length, not half. */
export function cylinder(radius: number, height: number): SDF {
  const h = height / 2
  return (p) => {
    const dx = vlen(p[0], 0, p[2]) - radius
    const dy = Math.abs(p[1]) - h
    const outside = vlen(vmax(dx, 0), vmax(dy, 0), 0)
    const inside = vmin(vmax(dx, dy), 0)
    return outside + inside
  }
}

/** Capsule: cylinder with hemisphere caps. Oriented along +Y. `length`
 *  is the cylinder length (straight part); total height = length + 2*r. */
export function capsule(radius: number, length: number): SDF {
  const h = length / 2
  return (p) => {
    const y = clamp(p[1], -h, h)
    return vlen(p[0], p[1] - y, p[2]) - radius
  }
}

/** Torus lying in the XZ plane: major radius R (ring size), minor radius r
 *  (tube thickness). Good for rings, wheels, eye sockets. */
export function torus(majorRadius: number, minorRadius: number): SDF {
  return (p) => {
    const qx = vlen(p[0], 0, p[2]) - majorRadius
    return vlen(qx, p[1], 0) - minorRadius
  }
}

/** Infinite plane with a given outward normal (must be unit length) and
 *  an offset. Useful as a half-space for CSG. */
export function plane(normal: Vec3, offset = 0): SDF {
  return (p) => p[0] * normal[0] + p[1] * normal[1] + p[2] * normal[2] + offset
}

// --- COMPOSE OPERATORS ---
// Each takes N SDFs and returns a new SDF.

/** Set union — points inside either SDF. Sharp seam at intersection. */
export function union(...fs: SDF[]): SDF {
  return (p) => {
    let d = fs[0](p)
    for (let i = 1; i < fs.length; i++) d = vmin(d, fs[i](p))
    return d
  }
}

/** Smooth union — soft blend across a radius k. Organic-looking merger,
 *  what polygonal CSG can't cheaply produce. */
export function smoothUnion(a: SDF, b: SDF, k: number): SDF {
  return (p) => {
    const da = a(p), db = b(p)
    const h = clamp(0.5 + 0.5 * (db - da) / k, 0, 1)
    return mix(db, da, h) - k * h * (1 - h)
  }
}

/** Intersection — points inside BOTH SDFs. */
export function intersect(a: SDF, b: SDF): SDF {
  return (p) => vmax(a(p), b(p))
}

/** Subtraction — a minus b. Carves b out of a. */
export function subtract(a: SDF, b: SDF): SDF {
  return (p) => vmax(a(p), -b(p))
}

/** Smooth subtraction — like subtract but with a soft edge. */
export function smoothSubtract(a: SDF, b: SDF, k: number): SDF {
  return (p) => {
    const da = a(p), db = b(p)
    const h = clamp(0.5 - 0.5 * (db + da) / k, 0, 1)
    return mix(da, -db, h) + k * h * (1 - h)
  }
}

// --- TRANSFORM OPERATORS ---
// Wrap an SDF with a coordinate transform. Rotations use radians.

/** Translate: evaluate the SDF as if the space were shifted. */
export function translate(offset: Vec3, f: SDF): SDF {
  return (p) => f([p[0] - offset[0], p[1] - offset[1], p[2] - offset[2]])
}

/** Uniform scale. For non-uniform scale, Lipschitz bound is tricky —
 *  the returned distance underestimates slightly, OK for MC. */
export function scale(s: number, f: SDF): SDF {
  return (p) => f([p[0] / s, p[1] / s, p[2] / s]) * s
}

/** Rotate around Y by `angle` radians (positive = CCW looking down -Y). */
export function rotateY(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle)
  return (p) => f([c * p[0] + s * p[2], p[1], -s * p[0] + c * p[2]])
}

/** Rotate around X by `angle` radians. */
export function rotateX(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle)
  return (p) => f([p[0], c * p[1] - s * p[2], s * p[1] + c * p[2]])
}

/** Rotate around Z by `angle` radians. */
export function rotateZ(angle: number, f: SDF): SDF {
  const c = Math.cos(angle), s = Math.sin(angle)
  return (p) => f([c * p[0] - s * p[1], s * p[0] + c * p[1], p[2]])
}

/** Mirror across X=0 (character symmetry — bake one arm, mirror for the other). */
export function mirrorX(f: SDF): SDF {
  return (p) => f([Math.abs(p[0]), p[1], p[2]])
}

// --- EVALUATION HELPERS ---

/** Gradient via finite differences. Normal = normalize(gradient). Used
 *  by MC for per-vertex normals — faster than analytic gradient and
 *  good enough for pixel-art output. */
export function gradient(f: SDF, p: Vec3, eps = 1e-3): Vec3 {
  const px: Vec3 = [p[0] + eps, p[1], p[2]]
  const py: Vec3 = [p[0] - eps, p[1], p[2]]
  const qx: Vec3 = [p[0], p[1] + eps, p[2]]
  const qy: Vec3 = [p[0], p[1] - eps, p[2]]
  const rx: Vec3 = [p[0], p[1], p[2] + eps]
  const ry: Vec3 = [p[0], p[1], p[2] - eps]
  return [f(px) - f(py), f(qx) - f(qy), f(rx) - f(ry)]
}

/** Normalize a vector in-place. Returns [0,1,0] if length is zero. */
export function normalize(v: Vec3): Vec3 {
  const l = vlen(v[0], v[1], v[2])
  if (l < 1e-12) return [0, 1, 0]
  return [v[0] / l, v[1] / l, v[2] / l]
}

// --- EXAMPLE ASSETS ---
// Enough to exercise the primitives + operators. Each returns a unit SDF
// positioned relative to its own origin. Use translate() to place.

/** Basic sword: cylinder blade + box crossguard + short grip. Tuned to
 *  match the current DEFAULT_ACCESSORIES RightWeapon cube (half-ext
 *  [0.015, 0.22, 0.015]). */
export function swordSDF(): SDF {
  const blade = cylinder(0.013, 0.30)                          // tall thin vertical
  const guard = translate([0, -0.04, 0], box([0.04, 0.01, 0.015]))
  const grip  = translate([0, -0.09, 0], cylinder(0.012, 0.08))
  return smoothUnion(smoothUnion(blade, guard, 0.005), grip, 0.01)
}

/** Rock: smooth-unioned box + sphere with seedable variance. */
export function rockSDF(seed = 0): SDF {
  const rng = (n: number) => {
    // Tiny deterministic hash so seed=0 and seed=1 produce visibly different rocks.
    const x = Math.sin(seed * 127.1 + n * 311.7) * 43758.5453
    return x - Math.floor(x)
  }
  const bHalf: [number, number, number] = [0.30 + rng(1) * 0.2, 0.15 + rng(2) * 0.1, 0.25 + rng(3) * 0.15]
  const sR = 0.15 + rng(4) * 0.15
  const sP: [number, number, number] = [rng(5) * 0.3 - 0.15, rng(6) * 0.1, rng(7) * 0.2 - 0.1]
  return smoothUnion(box(bHalf), translate(sP, sphere(sR)), 0.15)
}

/** Head stand-in: ellipsoid with a subtracted jaw slit. Not actually
 *  human — just a placeholder to validate SDF → MC → chunk skinning. */
export function chibiHeadSDF(): SDF {
  const skull = ellipsoid([0.19, 0.21, 0.19])
  const jawSlit = translate([0, -0.16, 0.10], roundedBox([0.08, 0.02, 0.08], 0.015))
  return smoothSubtract(skull, jawSlit, 0.02)
}
