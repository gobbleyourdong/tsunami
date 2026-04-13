import { describe, it, expect } from 'vitest'
import { quat } from '../src/math/quat'

describe('quat', () => {
  it('creates identity quaternion', () => {
    const q = quat.create()
    expect(q).toEqual([0, 0, 0, 1])
  })

  it('identity multiply is identity', () => {
    const a = quat.create()
    const b = quat.create()
    const out = quat.create()
    quat.multiply(out, a, b)
    expect(out[3]).toBeCloseTo(1)
    expect(out[0]).toBeCloseTo(0)
  })

  it('slerp at 0 returns a', () => {
    const a: [number, number, number, number] = [0, 0, 0, 1]
    const b: [number, number, number, number] = [0, 0.7071, 0, 0.7071]
    const out = quat.create()
    quat.slerp(out, a, b, 0)
    expect(out[0]).toBeCloseTo(0)
    expect(out[3]).toBeCloseTo(1)
  })

  it('slerp at 1 returns b', () => {
    const a: [number, number, number, number] = [0, 0, 0, 1]
    const b: [number, number, number, number] = [0, 0.7071, 0, 0.7071]
    const out = quat.create()
    quat.slerp(out, a, b, 1)
    expect(out[1]).toBeCloseTo(0.7071, 3)
    expect(out[3]).toBeCloseTo(0.7071, 3)
  })

  it('slerp at 0.5 is halfway', () => {
    const a: [number, number, number, number] = [0, 0, 0, 1]
    const b: [number, number, number, number] = [0, 0.7071, 0, 0.7071]
    const out = quat.create()
    quat.slerp(out, a, b, 0.5)
    const len = quat.length(out)
    expect(len).toBeCloseTo(1, 3)
  })

  it('normalize produces unit quaternion', () => {
    const q: [number, number, number, number] = [1, 2, 3, 4]
    const out = quat.create()
    quat.normalize(out, q)
    expect(quat.length(out)).toBeCloseTo(1, 5)
  })

  it('invert produces inverse', () => {
    const q: [number, number, number, number] = [0, 0.7071, 0, 0.7071]
    const inv = quat.create()
    quat.invert(inv, q)
    const result = quat.create()
    quat.multiply(result, q, inv)
    // Should be near identity
    expect(result[3]).toBeCloseTo(1, 3)
    expect(Math.abs(result[0])).toBeLessThan(0.01)
    expect(Math.abs(result[1])).toBeLessThan(0.01)
    expect(Math.abs(result[2])).toBeLessThan(0.01)
  })

  it('fromEuler produces unit quaternion', () => {
    const out = quat.create()
    quat.fromEuler(out, Math.PI / 4, Math.PI / 3, 0)
    expect(quat.length(out)).toBeCloseTo(1, 5)
  })

  it('toMat4 produces valid rotation matrix', () => {
    const q: [number, number, number, number] = [0, 0, 0, 1]
    const m = new Float32Array(16)
    quat.toMat4(m, q)
    // Identity rotation → identity matrix
    expect(m[0]).toBeCloseTo(1)
    expect(m[5]).toBeCloseTo(1)
    expect(m[10]).toBeCloseTo(1)
    expect(m[15]).toBeCloseTo(1)
  })

  it('90° Y rotation via toMat4', () => {
    const q = quat.create()
    quat.fromEuler(q, 0, Math.PI / 2, 0)
    const m = new Float32Array(16)
    quat.toMat4(m, q)
    // X axis should map to ~Z
    expect(m[0]).toBeCloseTo(0, 3)
    expect(m[8]).toBeCloseTo(1, 3)
  })
})
