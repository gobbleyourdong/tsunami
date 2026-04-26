import { describe, it, expect } from 'vitest'
import {
  sphere, box, roundedBox, ellipsoid, cylinder, capsule, torus, plane,
  union, smoothUnion, intersect, subtract,
  translate, scale, rotateY, rotateX, rotateZ, mirrorX,
} from '../src/character3d/sdf'

describe('SDF primitives', () => {
  it('sphere distance is |p| - r', () => {
    const s = sphere(1)
    expect(s([0, 0, 0])).toBeCloseTo(-1)        // center is inside by r
    expect(s([1, 0, 0])).toBeCloseTo(0)         // surface
    expect(s([2, 0, 0])).toBeCloseTo(1)         // 1m outside surface
    expect(s([0, 3, 0])).toBeCloseTo(2)
  })

  it('box returns 0 at corners, negative inside, positive outside', () => {
    const b = box([1, 1, 1])
    expect(b([0, 0, 0])).toBeCloseTo(-1)        // center is 1m from each face
    expect(b([1, 1, 1])).toBeCloseTo(0)         // corner = surface
    expect(b([2, 0, 0])).toBeCloseTo(1)         // 1m beyond face
    expect(b([2, 2, 2])).toBeCloseTo(Math.sqrt(3))   // 1,1,1 outside the corner
  })

  it('roundedBox subtracts cornerRadius and adds it back', () => {
    const r = roundedBox([1, 1, 1], 0.2)
    expect(r([0, 0, 0])).toBeCloseTo(-1)        // center same as box
    // Surface is at half + cornerRadius along an axis.
    expect(r([1, 0, 0])).toBeCloseTo(0)
  })

  it('cylinder along +Y', () => {
    const c = cylinder(1, 2)                     // r=1, h=2 → halfH=1
    expect(c([0, 0, 0])).toBeCloseTo(-1)        // center 1m from cylindrical wall
    expect(c([1, 0, 0])).toBeCloseTo(0)         // touches side
    expect(c([0, 1, 0])).toBeCloseTo(0)         // touches top cap
    expect(c([2, 0, 0])).toBeCloseTo(1)         // 1m outside side
    expect(c([0, 2, 0])).toBeCloseTo(1)         // 1m above top
  })

  it('capsule along +Y with hemisphere caps', () => {
    const c = capsule(0.5, 1)                    // r=0.5, length=1 → halfL=0.5
    expect(c([0, 0, 0])).toBeCloseTo(-0.5)      // center
    expect(c([0.5, 0, 0])).toBeCloseTo(0)       // side surface
    // Top hemisphere center at (0, 0.5, 0); surface 0.5 above that.
    expect(c([0, 1.0, 0])).toBeCloseTo(0)       // top of hemisphere
  })

  it('torus in XZ plane, ring at radius R, tube radius r', () => {
    const t = torus(2, 0.5)
    expect(t([2, 0, 0])).toBeCloseTo(-0.5)      // on the ring centerline = max-inside
    expect(t([2.5, 0, 0])).toBeCloseTo(0)       // outer surface
    expect(t([1.5, 0, 0])).toBeCloseTo(0)       // inner surface
    expect(t([0, 0, 0])).toBeCloseTo(1.5)       // center is 2 - 0.5 = 1.5m from inner surface
  })

  it('plane with unit normal, offset 0 = signed distance to that plane', () => {
    const p = plane([0, 1, 0])                    // y=0 plane, normal +Y
    expect(p([0, 0, 0])).toBe(0)
    expect(p([0, 1, 0])).toBe(1)
    expect(p([5, -3, 7])).toBe(-3)
  })
})

describe('SDF compose operators', () => {
  it('union takes the min of inputs', () => {
    const u = union(sphere(1), translate([3, 0, 0], sphere(1)))
    expect(u([0, 0, 0])).toBeCloseTo(-1)        // inside sphere A
    expect(u([3, 0, 0])).toBeCloseTo(-1)        // inside sphere B
    expect(u([1.5, 0, 0])).toBeCloseTo(0.5)     // between A and B, outside both
  })

  it('intersect takes the max of inputs', () => {
    const i = intersect(box([2, 2, 2]), sphere(1.5))
    // (0,0,0) inside both → -min(2, 1.5) = -1.5 from sphere
    expect(i([0, 0, 0])).toBeCloseTo(-1.5)
    // (1.5, 0, 0) on sphere edge but inside box → 0
    expect(i([1.5, 0, 0])).toBeCloseTo(0)
  })

  it('subtract carves second SDF out of first', () => {
    const s = subtract(sphere(2), sphere(1))
    // Origin: A=-2 (inside), B=-1 (inside) → max(A, -B) = max(-2, 1) = 1 (outside cavity)
    expect(s([0, 0, 0])).toBeCloseTo(1)
    // (1.5, 0, 0): A=-0.5 (inside outer), B=0.5 (outside inner) → max(-0.5, -0.5) = -0.5
    expect(s([1.5, 0, 0])).toBeCloseTo(-0.5)
  })

  it('smoothUnion blends seams between two SDFs', () => {
    const sharp = union(sphere(1), translate([1.5, 0, 0], sphere(1)))
    const smooth = smoothUnion(sphere(1), translate([1.5, 0, 0], sphere(1)), 0.3)
    // At the join point (0.75, 0, 0) the smooth blend dips deeper.
    expect(smooth([0.75, 0, 0])).toBeLessThan(sharp([0.75, 0, 0]))
  })
})

describe('SDF transforms', () => {
  it('translate shifts the field', () => {
    const t = translate([5, 0, 0], sphere(1))
    expect(t([5, 0, 0])).toBeCloseTo(-1)
    expect(t([6, 0, 0])).toBeCloseTo(0)
  })

  it('scale multiplies distance proportionally', () => {
    const s2 = scale(2, sphere(1))
    expect(s2([2, 0, 0])).toBeCloseTo(0)        // surface at 2x radius
    expect(s2([0, 0, 0])).toBeCloseTo(-2)
  })

  it('rotateY rotates around the Y axis', () => {
    // Box at the +X face. After 90° CCW (looking down -Y), face moves to +Z.
    const orig = translate([1, 0, 0], sphere(0.5))
    const rotated = rotateY(Math.PI / 2, orig)
    // The original sphere's center is at (1, 0, 0). After CCW rotation
    // around Y, the +Z direction in world should be the original +X.
    // So (0, 0, 1) world should hit the sphere surface (was at +X).
    expect(rotated([0, 0, 1])).toBeCloseTo(-0.5, 1)
  })

  it('rotateX rotates so original +Y appears at -Z in the new frame', () => {
    // Sphere originally at (0, 1, 0). After rotateX(+90°), eval point
    // (0, 0, -1) hits the sphere centre (the rotation maps eval (0,0,-1)
    // back to (0, 1, 0) in the original frame).
    const off = translate([0, 1, 0], sphere(0.3))
    const rx = rotateX(Math.PI / 2, off)
    expect(rx([0, 0, -1])).toBeCloseTo(-0.3)
  })

  it('rotateZ moves a +X object to -Y (forward eval-transform convention)', () => {
    // The transform applies Rz(+angle) to the EVAL POINT, which means
    // the visible object rotates by -angle. Sphere originally at +X
    // ends up findable at world (0, -1, 0) after rotateZ(+90°).
    const orig = translate([1, 0, 0], sphere(0.3))
    const rz = rotateZ(Math.PI / 2, orig)
    expect(rz([0, -1, 0])).toBeCloseTo(-0.3)
  })

  it('mirrorX reflects field across X=0', () => {
    const arm = translate([1.5, 0, 0], sphere(0.4))
    const armPair = mirrorX(arm)
    expect(armPair([1.5, 0, 0])).toBeCloseTo(-0.4)
    expect(armPair([-1.5, 0, 0])).toBeCloseTo(-0.4)   // mirror reflects the +X arm
  })
})
