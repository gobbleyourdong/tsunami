import { describe, it, expect } from 'vitest'
import { createCubeGeometry, createPlaneGeometry, createSphereGeometry } from '../src/renderer/geometry'

describe('createCubeGeometry', () => {
  it('has 24 vertices and 36 indices', () => {
    const cube = createCubeGeometry()
    expect(cube.vertexCount).toBe(24)
    expect(cube.indexCount).toBe(36)
  })

  it('has correct stride (8 floats per vertex)', () => {
    const cube = createCubeGeometry()
    expect(cube.vertices.length).toBe(24 * 8)
  })

  it('indices are within vertex range', () => {
    const cube = createCubeGeometry()
    for (let i = 0; i < cube.indexCount; i++) {
      expect(cube.indices[i]).toBeLessThan(cube.vertexCount)
      expect(cube.indices[i]).toBeGreaterThanOrEqual(0)
    }
  })

  it('normals are unit length', () => {
    const cube = createCubeGeometry()
    for (let v = 0; v < cube.vertexCount; v++) {
      const offset = v * 8 + 3
      const nx = cube.vertices[offset]
      const ny = cube.vertices[offset + 1]
      const nz = cube.vertices[offset + 2]
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz)
      expect(len).toBeCloseTo(1, 4)
    }
  })

  it('respects size parameter', () => {
    const cube = createCubeGeometry(4)
    // First vertex position x should be -2 (half of size=4)
    expect(Math.abs(cube.vertices[0])).toBeCloseTo(2)
  })
})

describe('createPlaneGeometry', () => {
  it('has correct vertex count for 1 segment', () => {
    const plane = createPlaneGeometry(10, 1)
    expect(plane.vertexCount).toBe(4)
    expect(plane.indexCount).toBe(6)
  })

  it('has correct vertex count for multiple segments', () => {
    const plane = createPlaneGeometry(10, 4)
    expect(plane.vertexCount).toBe(25)
    expect(plane.indexCount).toBe(4 * 4 * 6)
  })

  it('normals point up', () => {
    const plane = createPlaneGeometry()
    for (let v = 0; v < plane.vertexCount; v++) {
      const offset = v * 8 + 3
      expect(plane.vertices[offset]).toBe(0)     // nx
      expect(plane.vertices[offset + 1]).toBe(1)  // ny (up)
      expect(plane.vertices[offset + 2]).toBe(0)  // nz
    }
  })
})

describe('createSphereGeometry', () => {
  it('has valid indices', () => {
    const sphere = createSphereGeometry(1, 16, 8)
    for (let i = 0; i < sphere.indexCount; i++) {
      expect(sphere.indices[i]).toBeLessThan(sphere.vertexCount)
      expect(sphere.indices[i]).toBeGreaterThanOrEqual(0)
    }
  })

  it('normals are approximately unit length', () => {
    const sphere = createSphereGeometry()
    for (let v = 0; v < sphere.vertexCount; v++) {
      const offset = v * 8 + 3
      const nx = sphere.vertices[offset]
      const ny = sphere.vertices[offset + 1]
      const nz = sphere.vertices[offset + 2]
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz)
      expect(len).toBeCloseTo(1, 3)
    }
  })

  it('positions are on sphere surface', () => {
    const r = 2.5
    const sphere = createSphereGeometry(r, 16, 8)
    for (let v = 0; v < sphere.vertexCount; v++) {
      const offset = v * 8
      const x = sphere.vertices[offset]
      const y = sphere.vertices[offset + 1]
      const z = sphere.vertices[offset + 2]
      const dist = Math.sqrt(x * x + y * y + z * z)
      expect(dist).toBeCloseTo(r, 3)
    }
  })
})
