import { describe, it, expect } from 'vitest'
import { bakeIsosurface, type SDFPrimitive } from '../src/character3d/isosurface'
import { sphere, box, translate } from '../src/character3d/sdf'

describe('bakeIsosurface (Surface Nets)', () => {
  it('bakes a single sphere into vertices + indices', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.5), paletteSlot: 2, parentJoint: 'Hips' },
    ]
    const mesh = bakeIsosurface(
      { name: 'sphere', primitives: prims, bbox: [[-0.6, -0.6, -0.6], [0.6, 0.6, 0.6]] },
      0.1,                       // 12³ = 1728 cells
    )
    expect(mesh.vertices.length).toBeGreaterThan(0)
    expect(mesh.indices.length).toBeGreaterThan(0)
    // jointNames maps boneIdx → name. With one prim only, one entry.
    expect(mesh.jointNames).toEqual(['Hips'])
  })

  it('vertex stride is 8 floats (px py pz nx ny nz paletteSlot boneIdx)', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.4), paletteSlot: 5, parentJoint: 'Spine2' },
    ]
    const mesh = bakeIsosurface(
      { name: 's', primitives: prims, bbox: [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]] },
      0.1,
    )
    expect(mesh.vertices.length % 8).toBe(0)
    // Sample one vertex's palette slot — slot 5 is paletteSlot field
    // (index 6 within an 8-float stride).
    expect(mesh.vertices[6]).toBe(5)
    expect(mesh.vertices[7]).toBe(0)         // bone idx 0 (only prim)
  })

  it('multiple primitives produce per-vertex bone tags', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.3),                     paletteSlot: 2, parentJoint: 'A' },
      { sdf: translate([1, 0, 0], sphere(0.3)), paletteSlot: 4, parentJoint: 'B' },
    ]
    const mesh = bakeIsosurface(
      { name: 'pair', primitives: prims, bbox: [[-0.5, -0.5, -0.5], [1.5, 0.5, 0.5]] },
      0.1,
    )
    expect(mesh.jointNames).toEqual(['A', 'B'])
    // Look at every vertex's bone idx — must include both 0 and 1
    // (some vertices belong to A, some to B).
    const boneIdxs = new Set<number>()
    for (let i = 7; i < mesh.vertices.length; i += 8) boneIdxs.add(mesh.vertices[i])
    expect(boneIdxs.has(0)).toBe(true)
    expect(boneIdxs.has(1)).toBe(true)
  })

  it('empty bbox or all-positive SDF produces no vertices', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.1), paletteSlot: 0, parentJoint: 'X' },
    ]
    // Bbox far from the sphere — no surface crossings, no mesh.
    const mesh = bakeIsosurface(
      { name: 'far', primitives: prims, bbox: [[10, 10, 10], [11, 11, 11]] },
      0.5,
    )
    expect(mesh.vertices.length).toBe(0)
    expect(mesh.indices.length).toBe(0)
  })

  it('cell size affects vertex count — finer grid yields more vertices', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.5), paletteSlot: 1, parentJoint: 'V' },
    ]
    const coarse = bakeIsosurface(
      { name: 'c', primitives: prims, bbox: [[-0.6, -0.6, -0.6], [0.6, 0.6, 0.6]] },
      0.2,
    )
    const fine = bakeIsosurface(
      { name: 'f', primitives: prims, bbox: [[-0.6, -0.6, -0.6], [0.6, 0.6, 0.6]] },
      0.08,
    )
    expect(fine.vertices.length).toBeGreaterThan(coarse.vertices.length)
  })

  it('vertex normals are unit-length', () => {
    const prims: SDFPrimitive[] = [
      { sdf: sphere(0.5), paletteSlot: 0, parentJoint: 'V' },
    ]
    const mesh = bakeIsosurface(
      { name: 's', primitives: prims, bbox: [[-0.6, -0.6, -0.6], [0.6, 0.6, 0.6]] },
      0.15,
    )
    // Each vertex stride = 8 floats; offset 3..5 is the normal vec3.
    for (let i = 0; i < mesh.vertices.length; i += 8) {
      const nx = mesh.vertices[i + 3]
      const ny = mesh.vertices[i + 4]
      const nz = mesh.vertices[i + 5]
      const len = Math.hypot(nx, ny, nz)
      // Tolerate slight gradient inaccuracies near the sphere surface.
      expect(Math.abs(len - 1)).toBeLessThan(0.05)
    }
  })

  it('indices reference valid vertices', () => {
    const prims: SDFPrimitive[] = [
      { sdf: box([0.3, 0.3, 0.3]), paletteSlot: 0, parentJoint: 'B' },
    ]
    const mesh = bakeIsosurface(
      { name: 'b', primitives: prims, bbox: [[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]] },
      0.1,
    )
    const numVerts = mesh.vertices.length / 8
    for (let i = 0; i < mesh.indices.length; i++) {
      expect(mesh.indices[i]).toBeGreaterThanOrEqual(0)
      expect(mesh.indices[i]).toBeLessThan(numVerts)
    }
  })
})
