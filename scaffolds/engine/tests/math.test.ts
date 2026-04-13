import { describe, it, expect } from 'vitest'
import { vec3, mat4 } from '../src/math/vec'

describe('vec3', () => {
  it('creates zero vector', () => {
    const v = vec3.create()
    expect(v).toEqual([0, 0, 0])
  })

  it('adds vectors', () => {
    const out = vec3.create()
    vec3.add(out, [1, 2, 3], [4, 5, 6])
    expect(out).toEqual([5, 7, 9])
  })

  it('subtracts vectors', () => {
    const out = vec3.create()
    vec3.sub(out, [5, 7, 9], [4, 5, 6])
    expect(out).toEqual([1, 2, 3])
  })

  it('computes dot product', () => {
    expect(vec3.dot([1, 0, 0], [0, 1, 0])).toBe(0)
    expect(vec3.dot([1, 0, 0], [1, 0, 0])).toBe(1)
  })

  it('computes cross product', () => {
    const out = vec3.create()
    vec3.cross(out, [1, 0, 0], [0, 1, 0])
    expect(out).toEqual([0, 0, 1])
  })

  it('normalizes vectors', () => {
    const out = vec3.create()
    vec3.normalize(out, [3, 0, 0])
    expect(out[0]).toBeCloseTo(1)
    expect(out[1]).toBeCloseTo(0)
    expect(out[2]).toBeCloseTo(0)
  })

  it('computes length', () => {
    expect(vec3.length([3, 4, 0])).toBeCloseTo(5)
  })

  it('computes distance', () => {
    expect(vec3.distance([0, 0, 0], [3, 4, 0])).toBeCloseTo(5)
  })

  it('lerps between vectors', () => {
    const out = vec3.create()
    vec3.lerp(out, [0, 0, 0], [10, 20, 30], 0.5)
    expect(out).toEqual([5, 10, 15])
  })
})

describe('mat4', () => {
  it('creates identity matrix', () => {
    const m = mat4.create()
    expect(m[0]).toBe(1)
    expect(m[5]).toBe(1)
    expect(m[10]).toBe(1)
    expect(m[15]).toBe(1)
    expect(m[1]).toBe(0)
    expect(m[4]).toBe(0)
  })

  it('multiplies identity by identity', () => {
    const a = mat4.create()
    const b = mat4.create()
    const out = mat4.create()
    mat4.multiply(out, a, b)
    for (let i = 0; i < 16; i++) {
      expect(out[i]).toBeCloseTo(a[i])
    }
  })

  it('translation matrix moves points', () => {
    const m = mat4.create()
    mat4.translate(m, m, [10, 20, 30])
    expect(m[12]).toBe(10)
    expect(m[13]).toBe(20)
    expect(m[14]).toBe(30)
  })

  it('invert produces inverse', () => {
    const m = mat4.create()
    mat4.translate(m, m, [5, 3, -2])
    const inv = mat4.create()
    mat4.invert(inv, m)
    const result = mat4.create()
    mat4.multiply(result, m, inv)
    // Should be identity
    for (let i = 0; i < 4; i++) {
      for (let j = 0; j < 4; j++) {
        const expected = i === j ? 1 : 0
        expect(result[j * 4 + i]).toBeCloseTo(expected, 5)
      }
    }
  })

  it('perspective creates valid projection', () => {
    const m = mat4.create()
    mat4.perspective(m, Math.PI / 4, 16 / 9, 0.1, 100)
    // m[11] should be -1 for perspective divide
    expect(m[11]).toBe(-1)
    // Near plane should be reasonable
    expect(m[0]).toBeGreaterThan(0)
    expect(m[5]).toBeGreaterThan(0)
  })

  it('ortho creates valid projection', () => {
    const m = mat4.create()
    mat4.ortho(m, -10, 10, -10, 10, 0.1, 100)
    expect(m[0]).toBeGreaterThan(0)
    expect(m[5]).toBeGreaterThan(0)
    // No perspective divide
    expect(m[11]).toBe(0)
    expect(m[15]).toBe(1)
  })

  it('lookAt creates view matrix', () => {
    const m = mat4.create()
    mat4.lookAt(m, [0, 0, 5], [0, 0, 0], [0, 1, 0])
    // Transform origin should be at -5 on the z axis relative to eye
    const p = vec3.create()
    vec3.transformMat4(p, [0, 0, 0], m)
    expect(p[2]).toBeCloseTo(-5, 3)
  })

  it('rotateY rotates around Y axis', () => {
    const m = mat4.create()
    mat4.rotateY(m, m, Math.PI / 2)
    // X axis should now point to -Z
    expect(m[0]).toBeCloseTo(0, 5)
    expect(m[8]).toBeCloseTo(1, 5)
  })

  it('scale scales axes', () => {
    const m = mat4.create()
    mat4.scale(m, m, [2, 3, 4])
    expect(m[0]).toBe(2)
    expect(m[5]).toBe(3)
    expect(m[10]).toBe(4)
  })

  it('transpose works', () => {
    const m = mat4.create()
    m[1] = 5; m[4] = 0
    const out = mat4.create()
    mat4.transpose(out, m)
    expect(out[4]).toBe(5)
    expect(out[1]).toBe(0)
  })
})
