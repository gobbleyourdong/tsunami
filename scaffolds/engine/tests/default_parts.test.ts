import { describe, it, expect } from 'vitest'
import {
  DEFAULT_BODY_PARTS,
  DEFAULT_CAPE_PARTS,
  DEFAULT_GRENADE_BELT,
  DEFAULT_BOB_HAIR,
  DEFAULT_LONG_HAIR,
  DEFAULT_HAIR_STRANDS,
  DEFAULT_FACE,
  DEFAULT_HAIR,
  DEFAULT_ACCESSORIES,
  CHIBI_CENTERED_SIZE,
  CHIBI_CENTERED_OFFSET,
  CHIBI_LIMB_THICKNESS,
} from '../src/character3d/mixamo_loader'

function isPositiveSize3(size: [number, number, number]): boolean {
  return size.every((s) => s > 0 && Number.isFinite(s))
}

describe('Default body part registries', () => {
  it('DEFAULT_BODY_PARTS — secondary-sex pads with valid shape', () => {
    expect(DEFAULT_BODY_PARTS.length).toBe(4)
    for (const p of DEFAULT_BODY_PARTS) {
      expect(p.name).toMatch(/Breast|HipPad/)
      expect(['Spine2', 'Hips']).toContain(p.parentName)
      expect(isPositiveSize3(p.displaySize)).toBe(true)
    }
  })

  it('DEFAULT_CAPE_PARTS — chain with sequential naming', () => {
    expect(DEFAULT_CAPE_PARTS.length).toBeGreaterThanOrEqual(3)
    for (let i = 0; i < DEFAULT_CAPE_PARTS.length; i++) {
      expect(DEFAULT_CAPE_PARTS[i].name).toBe(`Cape${i}`)
      expect(isPositiveSize3(DEFAULT_CAPE_PARTS[i].displaySize)).toBe(true)
    }
  })

  it('DEFAULT_GRENADE_BELT — left + right grenades parented to Hips', () => {
    expect(DEFAULT_GRENADE_BELT.length).toBe(2)
    const names = DEFAULT_GRENADE_BELT.map((g) => g.name).sort()
    expect(names).toEqual(['GrenadeL', 'GrenadeR'])
    for (const g of DEFAULT_GRENADE_BELT) {
      expect(g.parentName).toBe('Hips')
      expect(isPositiveSize3(g.displaySize)).toBe(true)
    }
    // Mirror symmetry across X.
    const l = DEFAULT_GRENADE_BELT.find((g) => g.name === 'GrenadeL')!
    const r = DEFAULT_GRENADE_BELT.find((g) => g.name === 'GrenadeR')!
    expect(l.offset[0]).toBeCloseTo(-r.offset[0])
  })

  it('DEFAULT_BOB_HAIR — single shell on Head', () => {
    expect(DEFAULT_BOB_HAIR.length).toBe(1)
    expect(DEFAULT_BOB_HAIR[0].name).toBe('HairBob')
    expect(DEFAULT_BOB_HAIR[0].parentName).toBe('Head')
    expect(isPositiveSize3(DEFAULT_BOB_HAIR[0].displaySize)).toBe(true)
  })

  it('DEFAULT_LONG_HAIR — 5-segment chain anchored at back of head', () => {
    expect(DEFAULT_LONG_HAIR.length).toBe(5)
    expect(DEFAULT_LONG_HAIR[0].name).toBe('HairLong0')
    expect(DEFAULT_LONG_HAIR[0].parentName).toBe('Head')
    // Segments 1..4 chain off the previous segment.
    for (let i = 1; i < 5; i++) {
      expect(DEFAULT_LONG_HAIR[i].name).toBe(`HairLong${i}`)
      expect(DEFAULT_LONG_HAIR[i].parentName).toBe(`HairLong${i - 1}`)
      // Each subsequent segment drops down by ~0.13m.
      expect(DEFAULT_LONG_HAIR[i].offset[1]).toBeLessThan(0)
    }
    // Anchor offset is BACK of cranium (negative Z).
    expect(DEFAULT_LONG_HAIR[0].offset[2]).toBeLessThan(0)
  })

  it('DEFAULT_HAIR_STRANDS — 6 named tufts on Head with baked rotations', () => {
    expect(DEFAULT_HAIR_STRANDS.length).toBe(6)
    const names = DEFAULT_HAIR_STRANDS.map((s) => s.name).sort()
    expect(names).toEqual(['HairStrand0', 'HairStrand1', 'HairStrand2', 'HairStrand3', 'HairStrand4', 'HairStrand5'])
    for (const s of DEFAULT_HAIR_STRANDS) {
      expect(s.parentName).toBe('Head')
      expect(isPositiveSize3(s.displaySize)).toBe(true)
    }
    // Strands 0/1 are top tufts (positive Y). Strands 4/5 are sideburns
    // (large +/- X, low Y). Pin those defaults.
    const top0 = DEFAULT_HAIR_STRANDS[0]
    expect(top0.offset[1]).toBeGreaterThan(0.10)
    const sidebL = DEFAULT_HAIR_STRANDS[4]
    expect(Math.abs(sidebL.offset[0])).toBeGreaterThan(0.10)
  })

  it('DEFAULT_FACE / DEFAULT_HAIR / DEFAULT_ACCESSORIES — known starting shapes', () => {
    // Face is empty — face features are paste-on overlays in the outline pass.
    expect(DEFAULT_FACE).toEqual([])
    // Hair default is empty — characters opt-in via DEFAULT_BOB_HAIR etc.
    expect(DEFAULT_HAIR).toEqual([])
    // Accessories default is the right-hand weapon attachment point.
    expect(DEFAULT_ACCESSORIES.length).toBe(1)
    expect(DEFAULT_ACCESSORIES[0].name).toBe('RightWeapon')
    expect(DEFAULT_ACCESSORIES[0].parentName).toBe('RightHand')
  })

  it('CHIBI_CENTERED_SIZE / OFFSET cover head + spine + hips + neck', () => {
    expect(CHIBI_CENTERED_SIZE.Head).toBeDefined()
    expect(CHIBI_CENTERED_SIZE.Spine).toBeDefined()
    expect(CHIBI_CENTERED_SIZE.Spine1).toBeDefined()
    expect(CHIBI_CENTERED_SIZE.Spine2).toBeDefined()
    expect(CHIBI_CENTERED_SIZE.Hips).toBeDefined()
    expect(CHIBI_CENTERED_SIZE.Neck).toBeDefined()
    // Each entry is a positive 3-vec.
    for (const v of Object.values(CHIBI_CENTERED_SIZE)) {
      expect(isPositiveSize3(v as [number, number, number])).toBe(true)
    }
    // Only Head has a non-zero offset — its primitive sits above the
    // joint (cranium clears the shoulders). Other centered parts use
    // the default (0,0,0) fallback in the emitter.
    expect(CHIBI_CENTERED_OFFSET.Head).toBeDefined()
    expect(CHIBI_CENTERED_OFFSET.Head[1]).toBeGreaterThan(0)
  })

  it('CHIBI_LIMB_THICKNESS values are positive, 2-vec', () => {
    expect(CHIBI_LIMB_THICKNESS.LeftArm).toBeDefined()
    expect(CHIBI_LIMB_THICKNESS.LeftLeg).toBeDefined()
    for (const v of Object.values(CHIBI_LIMB_THICKNESS)) {
      const [x, y] = v as [number, number]
      expect(x).toBeGreaterThan(0)
      expect(y).toBeGreaterThan(0)
    }
  })
})
