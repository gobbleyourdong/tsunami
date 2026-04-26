import { describe, it, expect } from 'vitest'
import {
  DEFAULT_HANDS,
  DEFAULT_FEET,
  DEFAULT_ATTACHMENTS,
  HAND_LIBRARY,
  FOOT_LIBRARY,
  type AttachmentPart,
} from '../src/character3d/attachments'

const VALID_PALETTE_KEYS = new Set(['skin', 'shirt', 'pants', 'shoes', 'armor', 'leather', 'cloth'])

function isValidAttachment(a: AttachmentPart): boolean {
  if (typeof a.name !== 'string' || a.name.length === 0) return false
  if (typeof a.jointName !== 'string' || a.jointName.length === 0) return false
  if (typeof a.type !== 'number' || !Number.isInteger(a.type) || a.type < 0) return false
  if (!Array.isArray(a.params) || a.params.length !== 4) return false
  if (!a.params.every((n) => typeof n === 'number' && Number.isFinite(n))) return false
  if (!Array.isArray(a.offsetInBone) || a.offsetInBone.length !== 3) return false
  if (a.paletteSlot !== undefined && !VALID_PALETTE_KEYS.has(a.paletteSlot)) return false
  return true
}

describe('DEFAULT_HANDS / DEFAULT_FEET / DEFAULT_ATTACHMENTS', () => {
  it('DEFAULT_HANDS = 2 entries, L on LeftHand and R on RightHand', () => {
    expect(DEFAULT_HANDS.length).toBe(2)
    const joints = DEFAULT_HANDS.map((a) => a.jointName).sort()
    expect(joints).toEqual(['LeftHand', 'RightHand'])
  })

  it('DEFAULT_FEET = 2 entries, L on LeftFoot and R on RightFoot', () => {
    expect(DEFAULT_FEET.length).toBe(2)
    const joints = DEFAULT_FEET.map((a) => a.jointName).sort()
    expect(joints).toEqual(['LeftFoot', 'RightFoot'])
  })

  it('DEFAULT_ATTACHMENTS = hands ∪ feet', () => {
    expect(DEFAULT_ATTACHMENTS.length).toBe(DEFAULT_HANDS.length + DEFAULT_FEET.length)
    const wantNames = [...DEFAULT_HANDS, ...DEFAULT_FEET].map((a) => a.name)
    const gotNames  = DEFAULT_ATTACHMENTS.map((a) => a.name)
    expect(gotNames).toEqual(wantNames)
  })

  it('every default attachment has a valid structure + skin/shoes palette', () => {
    for (const a of DEFAULT_ATTACHMENTS) {
      expect(isValidAttachment(a)).toBe(true)
      expect(['skin', 'shoes']).toContain(a.paletteSlot)
    }
  })

  it('left-side attachments use blend group 2 / 4, right-side use 3 / 5', () => {
    const expectGroup = (joint: string): number => {
      if (joint === 'LeftHand')  return 2
      if (joint === 'RightHand') return 3
      if (joint === 'LeftFoot')  return 4
      if (joint === 'RightFoot') return 5
      return -1
    }
    for (const a of DEFAULT_ATTACHMENTS) {
      expect(a.blendGroup).toBe(expectGroup(a.jointName))
    }
  })
})

describe('HAND_LIBRARY', () => {
  it('exposes named variants including the default skin entry', () => {
    expect(Object.keys(HAND_LIBRARY)).toContain('skin')
    expect(Object.keys(HAND_LIBRARY).length).toBeGreaterThanOrEqual(2)
  })

  it('every variant is a 2-element [L, R] list with mirrored joints', () => {
    for (const [variant, list] of Object.entries(HAND_LIBRARY)) {
      expect(list.length).toBe(2)
      const joints = list.map((a) => a.jointName).sort()
      expect(joints).toEqual(['LeftHand', 'RightHand'])
      for (const a of list) {
        expect(isValidAttachment(a)).toBe(true)
      }
      // L attaches to group 2, R to group 3.
      const lEntry = list.find((a) => a.jointName === 'LeftHand')!
      const rEntry = list.find((a) => a.jointName === 'RightHand')!
      expect(lEntry.blendGroup).toBe(2)
      expect(rEntry.blendGroup).toBe(3)
      // Quick sanity: variant name appears somewhere in the entry name.
      expect(lEntry.name.toLowerCase()).toContain(variant.toLowerCase())
    }
  })

  it('skin variant aliases DEFAULT_HANDS exactly', () => {
    expect(HAND_LIBRARY.skin).toBe(DEFAULT_HANDS)
  })
})

describe('FOOT_LIBRARY', () => {
  it('exposes named variants including the default shoe entry', () => {
    expect(Object.keys(FOOT_LIBRARY)).toContain('shoe')
    expect(Object.keys(FOOT_LIBRARY).length).toBeGreaterThanOrEqual(2)
  })

  it('every variant is a 2-element [L, R] list with mirrored joints', () => {
    for (const [variant, list] of Object.entries(FOOT_LIBRARY)) {
      expect(list.length).toBe(2)
      const joints = list.map((a) => a.jointName).sort()
      expect(joints).toEqual(['LeftFoot', 'RightFoot'])
      for (const a of list) {
        expect(isValidAttachment(a)).toBe(true)
      }
      const lEntry = list.find((a) => a.jointName === 'LeftFoot')!
      const rEntry = list.find((a) => a.jointName === 'RightFoot')!
      expect(lEntry.blendGroup).toBe(4)
      expect(rEntry.blendGroup).toBe(5)
      // Variant-name-in-entry-name is the convention for new entries
      // (foot_bare_*, foot_boot_*) but NOT 'shoe' which aliases the
      // historical foot_skin_* default — skip that check there.
      if (variant !== 'shoe') {
        expect(lEntry.name.toLowerCase()).toContain(variant.toLowerCase())
      }
    }
  })

  it('shoe variant aliases DEFAULT_FEET exactly', () => {
    expect(FOOT_LIBRARY.shoe).toBe(DEFAULT_FEET)
  })
})
