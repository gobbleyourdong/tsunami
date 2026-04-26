import { describe, it, expect } from 'vitest'
import {
  DEFAULT_ANATOMY,
  FACE_ANCHORS,
  BUILD_PRESETS,
  type AnatomyCurve,
  type AnatomyAnchor,
} from '../src/character3d/anatomy'

function isFiniteProfile(p: unknown): boolean {
  return Array.isArray(p) && p.length === 4 && p.every((n) => typeof n === 'number' && Number.isFinite(n) && n > 0)
}

describe('DEFAULT_ANATOMY', () => {
  it('exposes the full plan list (8+ curves: pec/glute/hipFlare L+R, jawline, brow, cheekbones)', () => {
    const names = DEFAULT_ANATOMY.map((c) => c.name).sort()
    expect(names).toContain('pecL')
    expect(names).toContain('pecR')
    expect(names).toContain('gluteL')
    expect(names).toContain('gluteR')
    expect(names).toContain('hipFlareL')
    expect(names).toContain('hipFlareR')
    expect(names).toContain('jawline')
    expect(names).toContain('brow')
    expect(names).toContain('cheekboneL')
    expect(names).toContain('cheekboneR')
  })

  it('every curve has 3 joint names + a 4-control-point profile + a positive blend group', () => {
    for (const c of DEFAULT_ANATOMY) {
      expect(typeof c.jointA).toBe('string')
      expect(typeof c.jointB).toBe('string')
      expect(typeof c.jointC).toBe('string')
      expect(c.jointA.length).toBeGreaterThan(0)
      expect(isFiniteProfile(c.profile)).toBe(true)
      expect(c.blendGroup).toBeGreaterThanOrEqual(1)
      expect(c.blendGroup).toBeLessThanOrEqual(15)
      expect(c.blendRadius).toBeGreaterThanOrEqual(0)
    }
  })

  it('L/R paired curves are mirror-symmetric in offsetA.x and route to mirror blend groups', () => {
    const pairs: [string, string][] = [
      ['pecL', 'pecR'],
      ['gluteL', 'gluteR'],
      ['hipFlareL', 'hipFlareR'],
      ['cheekboneL', 'cheekboneR'],
    ]
    for (const [lName, rName] of pairs) {
      const l = DEFAULT_ANATOMY.find((c) => c.name === lName)!
      const r = DEFAULT_ANATOMY.find((c) => c.name === rName)!
      expect(l).toBeDefined()
      expect(r).toBeDefined()
      const lx = l.offsetA?.[0] ?? 0
      const rx = r.offsetA?.[0] ?? 0
      expect(lx).toBeCloseTo(-rx)
    }
  })

  it('face curves all live in blend group 1 (head)', () => {
    for (const name of ['jawline', 'brow', 'cheekboneL', 'cheekboneR']) {
      const c = DEFAULT_ANATOMY.find((x) => x.name === name)!
      expect(c.blendGroup).toBe(1)
    }
  })

  it('face curves reference Anchor_* joints (not body bones)', () => {
    const faceCurves = ['jawline', 'brow', 'cheekboneL', 'cheekboneR']
    for (const name of faceCurves) {
      const c = DEFAULT_ANATOMY.find((x) => x.name === name)!
      expect(c.jointA.startsWith('Anchor_')).toBe(true)
      expect(c.jointB.startsWith('Anchor_')).toBe(true)
      expect(c.jointC.startsWith('Anchor_')).toBe(true)
    }
  })
})

describe('FACE_ANCHORS', () => {
  it('exposes 8 anchors all parented to Head', () => {
    expect(FACE_ANCHORS.length).toBe(8)
    for (const a of FACE_ANCHORS) {
      expect(a.parentName).toBe('Head')
      expect(a.name.startsWith('Anchor_')).toBe(true)
      expect(a.offset.length).toBe(3)
      for (const v of a.offset) expect(Number.isFinite(v)).toBe(true)
    }
  })

  it('L/R anchor pairs are X-mirrored', () => {
    const pairs: [string, string][] = [
      ['Anchor_JawL', 'Anchor_JawR'],
      ['Anchor_BrowL', 'Anchor_BrowR'],
      ['Anchor_CheekL', 'Anchor_CheekR'],
    ]
    for (const [lName, rName] of pairs) {
      const l = FACE_ANCHORS.find((a) => a.name === lName)!
      const r = FACE_ANCHORS.find((a) => a.name === rName)!
      expect(l.offset[0]).toBeCloseTo(-r.offset[0])
      expect(l.offset[1]).toBeCloseTo(r.offset[1])
      expect(l.offset[2]).toBeCloseTo(r.offset[2])
    }
  })

  it('Chin anchor has negative Y offset (sits below head joint)', () => {
    const chin = FACE_ANCHORS.find((a) => a.name === 'Anchor_Chin')!
    expect(chin.offset[1]).toBeLessThan(0)
  })

  it('Brow + Cheek anchors have positive Z offset (face-forward)', () => {
    for (const name of ['Anchor_BrowL', 'Anchor_BrowR', 'Anchor_BrowMid', 'Anchor_CheekL', 'Anchor_CheekR']) {
      const a = FACE_ANCHORS.find((x) => x.name === name)!
      expect(a.offset[2]).toBeGreaterThan(0)
    }
  })

  it('all anchor names are unique', () => {
    const names = FACE_ANCHORS.map((a) => a.name)
    const unique = new Set(names)
    expect(unique.size).toBe(names.length)
  })
})

describe('BUILD_PRESETS', () => {
  it('exposes the 4 named builds', () => {
    expect(Object.keys(BUILD_PRESETS).sort()).toEqual(
      ['hourglass', 'skinny', 'standard', 'strong'],
    )
  })

  it('standard is empty (engine defaults)', () => {
    expect(BUILD_PRESETS.standard).toEqual({})
  })

  it('every non-default preset has finite, positive profiles', () => {
    for (const [name, preset] of Object.entries(BUILD_PRESETS)) {
      if (name === 'standard') continue
      if (preset.limbs) {
        for (const v of Object.values(preset.limbs)) {
          expect(isFiniteProfile(v)).toBe(true)
        }
      }
      if (preset.anatomy) {
        for (const v of Object.values(preset.anatomy)) {
          expect(isFiniteProfile(v)).toBe(true)
        }
      }
    }
  })

  it('hourglass hip flare is wider at start than strong (anatomical signal)', () => {
    const h = BUILD_PRESETS.hourglass.anatomy?.hipFlareL!
    const s = BUILD_PRESETS.strong.anatomy?.hipFlareL!
    expect(h[0]).toBeGreaterThan(s[0])   // first profile point = hip start
  })

  it('strong limbs are bigger than skinny limbs at the bicep peak', () => {
    const strong = BUILD_PRESETS.strong.limbs?.LeftArm!
    const skinny = BUILD_PRESETS.skinny.limbs?.LeftArm!
    expect(strong[1]).toBeGreaterThan(skinny[1])   // r1 = mid-bone = bicep peak
  })
})
