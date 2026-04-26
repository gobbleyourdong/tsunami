import { describe, it, expect } from 'vitest'
import {
  EYE_STYLES,
  MOUTH_STYLES,
  resolveSlot,
  FACE_EYE_MARIO,
  FACE_EYE_GLOWING,
  FACE_MOUTH_OFF,
  type FacePixelSlot,
} from '../src/character3d/face_pixels'

describe('face pixel registries', () => {
  it('exposes 7 eye styles aligned with shader IDs', () => {
    expect(EYE_STYLES.length).toBe(7)
    // Style index 0 must be 'mario' (matches the demo's expression
    // table default + the bake's slot ordering).
    expect(EYE_STYLES[0].name).toBe('mario')
    expect(EYE_STYLES[0]).toBe(FACE_EYE_MARIO)
  })

  it('exposes 6 mouth styles, index 0 = "off"', () => {
    expect(MOUTH_STYLES.length).toBe(6)
    expect(MOUTH_STYLES[0].name).toBe('off')
    expect(MOUTH_STYLES[0]).toBe(FACE_MOUTH_OFF)
    expect(FACE_MOUTH_OFF.pixels).toEqual([])
  })

  it('every authored eye style has at least one pixel', () => {
    for (const eye of EYE_STYLES) {
      if (eye.name === 'closed') continue   // closed = empty by intent
      expect(eye.pixels.length).toBeGreaterThan(0)
    }
  })

  it('eye pixels stay in the 5x5 paint grid (dx/dy ∈ [-2, 2])', () => {
    for (const eye of EYE_STYLES) {
      for (const px of eye.pixels) {
        expect(px.dx).toBeGreaterThanOrEqual(-2)
        expect(px.dx).toBeLessThanOrEqual(2)
        expect(px.dy).toBeGreaterThanOrEqual(-2)
        expect(px.dy).toBeLessThanOrEqual(2)
      }
    }
  })

  it('mouth pixels stay in the 5x3 paint grid (dx ∈ [-2, 2], dy ∈ [-1, 1])', () => {
    for (const mouth of MOUTH_STYLES) {
      for (const px of mouth.pixels) {
        expect(px.dx).toBeGreaterThanOrEqual(-2)
        expect(px.dx).toBeLessThanOrEqual(2)
        expect(px.dy).toBeGreaterThanOrEqual(-1)
        expect(px.dy).toBeLessThanOrEqual(1)
      }
    }
  })

  it('glowing style declares a glowSlot for shader pulsing', () => {
    expect(FACE_EYE_GLOWING.glowSlot).toBeDefined()
  })

  it('resolveSlot maps named slots and uses sentinels for tear/glow_core', () => {
    const named = { pupil: 7, eyewhite: 6, accent: 11, mouth: 8 }
    expect(resolveSlot('pupil', named)).toBe(7)
    expect(resolveSlot('eyewhite', named)).toBe(6)
    expect(resolveSlot('accent', named)).toBe(11)
    expect(resolveSlot('mouth', named)).toBe(8)
    // Sentinels: tear = 28, glow_core = 29 (shader-internal constants).
    expect(resolveSlot('tear', named)).toBe(28)
    expect(resolveSlot('glow_core', named)).toBe(29)
  })

  it('resolveSlot falls back to defaults when slot missing from named map', () => {
    expect(resolveSlot('pupil', {})).toBe(7)
    expect(resolveSlot('eyewhite', {})).toBe(6)
    expect(resolveSlot('mouth', {})).toBe(8)
  })

  it('every pixel uses a valid FacePixelSlot string', () => {
    const valid: FacePixelSlot[] = ['pupil', 'eyewhite', 'accent', 'tear', 'mouth', 'glow_core']
    const all = [...EYE_STYLES, ...MOUTH_STYLES]
    for (const grid of all) {
      for (const px of grid.pixels) {
        expect(valid).toContain(px.slot)
      }
    }
  })
})
