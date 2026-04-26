import { describe, it, expect } from 'vitest'
import {
  chibiMaterial,
  defaultRainbowMaterial,
  extendRigWithBodyParts,
  extendRigWithHair,
  type BodyPart,
  type HairPart,
} from '../src/character3d/mixamo_loader'
import type { Joint } from '../src/character3d/skeleton'

const RIG: Joint[] = [
  { name: 'Hips',          parent: -1, offset: [0, 1, 0] },
  { name: 'Spine',         parent: 0,  offset: [0, 0.1, 0] },
  { name: 'Spine2',        parent: 1,  offset: [0, 0.2, 0] },
  { name: 'Head',          parent: 2,  offset: [0, 0.15, 0] },
  { name: 'LeftShoulder',  parent: 2,  offset: [0.1, 0, 0] },
  { name: 'LeftArm',       parent: 4,  offset: [0.1, -0.1, 0] },
  { name: 'LeftHand',      parent: 5,  offset: [0.1, -0.1, 0] },
  { name: 'RightShoulder', parent: 2,  offset: [-0.1, 0, 0] },
  { name: 'LeftFoot',      parent: 0,  offset: [0.1, -1, 0] },
  { name: 'LeftEye',       parent: 3,  offset: [0.05, 0.1, 0.1] },
  { name: 'Mouth',         parent: 3,  offset: [0, 0, 0.15] },
]

describe('chibiMaterial', () => {
  it('returns palette + paletteIndices + namedSlots; sized to rig length', () => {
    const m = chibiMaterial(RIG)
    expect(m.paletteIndices.length).toBe(RIG.length)
    // 32 slots × 4 floats per slot.
    expect(m.palette.length).toBe(32 * 4)
    // Some essential slot names present.
    expect(m.namedSlots).toMatchObject({
      skin: expect.any(Number),
      hair: expect.any(Number),
      shirt: expect.any(Number),
      armor: expect.any(Number),
      cloth: expect.any(Number),
      leather: expect.any(Number),
    })
  })

  it('routes named body parts to expected slots', () => {
    const m = chibiMaterial(RIG)
    const slotOf = (name: string) => m.paletteIndices[RIG.findIndex((j) => j.name === name)]
    expect(slotOf('Head')).toBe(m.namedSlots.skin)
    expect(slotOf('Spine2')).toBe(m.namedSlots.shirt)
    expect(slotOf('Hips')).toBe(m.namedSlots.pants)
    expect(slotOf('LeftFoot')).toBe(m.namedSlots.shoes)
    expect(slotOf('LeftEye')).toBe(m.namedSlots.eyewhite)
    expect(slotOf('Mouth')).toBe(m.namedSlots.mouth)
  })

  it('routes WP_Mage_* and WP_Ninja_* to cloth slot', () => {
    const items: BodyPart[] = [
      { name: 'WP_Mage_Hood',  parentName: 'Head',   offset: [0, 0, 0], displaySize: [0.2, 0.2, 0.2] },
      { name: 'WP_Mage_Belt',  parentName: 'Hips',   offset: [0, 0, 0], displaySize: [0.18, 0.04, 0.16] },
      { name: 'WP_Ninja_Mask', parentName: 'Head',   offset: [0, 0, 0], displaySize: [0.1, 0.06, 0.04] },
    ]
    const extended = extendRigWithBodyParts(RIG, items)
    const m = chibiMaterial(extended)
    const slotOf = (name: string) => m.paletteIndices[extended.findIndex((j) => j.name === name)]
    expect(slotOf('WP_Mage_Hood')).toBe(m.namedSlots.cloth)
    expect(slotOf('WP_Mage_Belt')).toBe(m.namedSlots.accent)   // belt → accent
    expect(slotOf('WP_Ninja_Mask')).toBe(m.namedSlots.cloth)
  })

  it('routes WP_Light_Chest to armor; other WP_Light_ to leather', () => {
    const items: BodyPart[] = [
      { name: 'WP_Light_ChestPlate', parentName: 'Spine2',  offset: [0, 0, 0], displaySize: [0.2, 0.2, 0.2] },
      { name: 'WP_Light_BootL',      parentName: 'LeftFoot', offset: [0, 0, 0], displaySize: [0.06, 0.08, 0.11] },
    ]
    const extended = extendRigWithBodyParts(RIG, items)
    const m = chibiMaterial(extended)
    const slotOf = (name: string) => m.paletteIndices[extended.findIndex((j) => j.name === name)]
    expect(slotOf('WP_Light_ChestPlate')).toBe(m.namedSlots.armor)
    expect(slotOf('WP_Light_BootL')).toBe(m.namedSlots.leather)
  })

  it('routes WP_Barb_* to leather slot', () => {
    const items: BodyPart[] = [
      { name: 'WP_Barb_PauldronL', parentName: 'LeftShoulder', offset: [0, 0, 0], displaySize: [0.1, 0.1, 0.1] },
    ]
    const extended = extendRigWithBodyParts(RIG, items)
    const m = chibiMaterial(extended)
    const slotOf = (name: string) => m.paletteIndices[extended.findIndex((j) => j.name === name)]
    expect(slotOf('WP_Barb_PauldronL')).toBe(m.namedSlots.leather)
  })

  it('legacy WP_<role> (knight) routes to armor', () => {
    const items: BodyPart[] = [
      { name: 'WP_Helmet',     parentName: 'Head',   offset: [0, 0, 0], displaySize: [0.22, 0.22, 0.22] },
      { name: 'WP_ChestPlate', parentName: 'Spine2', offset: [0, 0, 0], displaySize: [0.2, 0.18, 0.14] },
      { name: 'WP_Belt',       parentName: 'Hips',   offset: [0, 0, 0], displaySize: [0.18, 0.04, 0.16] },
    ]
    const extended = extendRigWithBodyParts(RIG, items)
    const m = chibiMaterial(extended)
    const slotOf = (name: string) => m.paletteIndices[extended.findIndex((j) => j.name === name)]
    expect(slotOf('WP_Helmet')).toBe(m.namedSlots.armor)
    expect(slotOf('WP_ChestPlate')).toBe(m.namedSlots.armor)
    expect(slotOf('WP_Belt')).toBe(m.namedSlots.accent)
  })

  it('routes Hair* / Cape* / Grenade* to their dedicated slots', () => {
    const hair: HairPart[] = [
      { name: 'HairBob', parentName: 'Head', offset: [0, 0.16, 0], displaySize: [0.22, 0.16, 0.22] },
    ]
    const extras: BodyPart[] = [
      { name: 'Cape0',     parentName: 'Spine2', offset: [0, 0, -0.1], displaySize: [0.1, 0.05, 0.02] },
      { name: 'GrenadeL',  parentName: 'Hips',   offset: [-0.1, 0, 0], displaySize: [0.04, 0.04, 0.04] },
    ]
    let extended = extendRigWithHair(RIG, hair)
    extended = extendRigWithBodyParts(extended, extras)
    const m = chibiMaterial(extended)
    const slotOf = (name: string) => m.paletteIndices[extended.findIndex((j) => j.name === name)]
    expect(slotOf('HairBob')).toBe(m.namedSlots.hair)
    expect(slotOf('Cape0')).toBe(m.namedSlots.cape)
    expect(slotOf('GrenadeL')).toBe(m.namedSlots.weapon)
  })
})

describe('defaultRainbowMaterial', () => {
  it('cycles through 16 hue slots based on joint index', () => {
    const m = defaultRainbowMaterial(20)
    expect(m.paletteIndices.length).toBe(20)
    // Values cycle through 0..15 then wrap.
    expect(m.paletteIndices[0]).toBe(0)
    expect(m.paletteIndices[15]).toBe(15)
    expect(m.paletteIndices[16]).toBe(0)
    // namedSlots is empty (no semantic slots in rainbow mode).
    expect(m.namedSlots).toEqual({})
  })
})
