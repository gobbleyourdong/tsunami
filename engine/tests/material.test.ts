import { describe, it, expect } from 'vitest'
import { createDefaultMaterial, packMaterialUniforms } from '../src/scene/material'

describe('Material', () => {
  it('creates default material with sensible values', () => {
    const mat = createDefaultMaterial()
    expect(mat.roughness).toBe(0.5)
    expect(mat.metallic).toBe(0.0)
    expect(mat.albedo).toEqual([0.8, 0.8, 0.8, 1.0])
    expect(mat.alphaMode).toBe('opaque')
  })

  it('packs to 64 bytes (16 floats)', () => {
    const mat = createDefaultMaterial()
    mat.albedo = [1.0, 0.5, 0.2, 1.0]
    mat.roughness = 0.8
    mat.metallic = 0.3
    mat.emissive = [0.1, 0.0, 0.0]
    mat.alphaCutoff = 0.4

    const data = packMaterialUniforms(mat)
    expect(data.length).toBe(16)
    expect(data[0]).toBeCloseTo(1.0)  // albedo.r
    expect(data[1]).toBeCloseTo(0.5)  // albedo.g
    expect(data[4]).toBeCloseTo(0.8)  // roughness
    expect(data[5]).toBeCloseTo(0.3)  // metallic
    expect(data[8]).toBeCloseTo(0.1)  // emissive.r
    expect(data[11]).toBeCloseTo(0.4) // alphaCutoff
  })
})
