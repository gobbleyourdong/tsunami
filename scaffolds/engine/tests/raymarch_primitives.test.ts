import { describe, it, expect } from 'vitest'
import {
  chibiMaterial,
  chibiRaymarchPrimitives,
  extendRigWithBodyParts,
  extendRigWithHair,
  DEFAULT_BOB_HAIR,
  DEFAULT_LONG_HAIR,
  DEFAULT_HAIR_STRANDS,
  DEFAULT_CAPE_PARTS,
  DEFAULT_GRENADE_BELT,
  type BodyPart,
} from '../src/character3d/mixamo_loader'
import { outfitToBodyParts, WARDROBE } from '../src/character3d/wardrobe'
import type { Joint } from '../src/character3d/skeleton'

const RIG: Joint[] = [
  { name: 'Hips',          parent: -1, offset: [0, 1, 0] },
  { name: 'Spine',         parent: 0,  offset: [0, 0.1, 0] },
  { name: 'Spine1',        parent: 1,  offset: [0, 0.1, 0] },
  { name: 'Spine2',        parent: 2,  offset: [0, 0.1, 0] },
  { name: 'Neck',          parent: 3,  offset: [0, 0.1, 0] },
  { name: 'Head',          parent: 4,  offset: [0, 0.05, 0] },
  { name: 'LeftShoulder',  parent: 3,  offset: [0.1, 0, 0] },
  { name: 'RightShoulder', parent: 3,  offset: [-0.1, 0, 0] },
  { name: 'LeftArm',       parent: 6,  offset: [0.05, -0.1, 0] },
  { name: 'LeftForeArm',   parent: 8,  offset: [0, -0.2, 0] },
  { name: 'LeftHand',      parent: 9,  offset: [0, -0.2, 0] },
  { name: 'RightArm',      parent: 7,  offset: [-0.05, -0.1, 0] },
  { name: 'RightForeArm',  parent: 11, offset: [0, -0.2, 0] },
  { name: 'RightHand',     parent: 12, offset: [0, -0.2, 0] },
  { name: 'LeftUpLeg',     parent: 0,  offset: [0.05, -0.05, 0] },
  { name: 'LeftLeg',       parent: 14, offset: [0, -0.4, 0] },
  { name: 'LeftFoot',      parent: 15, offset: [0, -0.4, 0] },
  { name: 'RightUpLeg',    parent: 0,  offset: [-0.05, -0.05, 0] },
  { name: 'RightLeg',      parent: 17, offset: [0, -0.4, 0] },
  { name: 'RightFoot',     parent: 18, offset: [0, -0.4, 0] },
]

describe('chibiRaymarchPrimitives — base body emission', () => {
  it('emits an ellipsoid for Head and the spine sack', () => {
    const m = chibiMaterial(RIG)
    const prims = chibiRaymarchPrimitives(RIG, m)
    const head = prims.find((p) => p.boneIdx === RIG.findIndex((j) => j.name === 'Head'))
    expect(head?.type).toBe(3)              // 3 = ellipsoid (was sphere; upgrade)
    expect(head?.blendGroup).toBe(1)        // head's own group
    const spine2Idx = RIG.findIndex((j) => j.name === 'Spine2')
    const spine2 = prims.find((p) => p.boneIdx === spine2Idx)
    expect(spine2?.type).toBe(3)            // 3 = ellipsoid
    expect(spine2?.blendGroup).toBe(6)      // group 6 = potato sack
  })

  it('emits a cone-jaw alongside the head ellipsoid', () => {
    const m = chibiMaterial(RIG)
    const prims = chibiRaymarchPrimitives(RIG, m)
    const headIdx = RIG.findIndex((j) => j.name === 'Head')
    const headPrims = prims.filter((p) => p.boneIdx === headIdx)
    // Head emits an ellipsoid + a cone (type 12) for the chin.
    expect(headPrims.some((p) => p.type === 3)).toBe(true)
    expect(headPrims.some((p) => p.type === 12)).toBe(true)
  })
})

describe('chibiRaymarchPrimitives — hair emission', () => {
  it('emits an ellipsoid for HairBob (round, single shell)', () => {
    const ext = extendRigWithHair(RIG, DEFAULT_BOB_HAIR)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, DEFAULT_BOB_HAIR)
    const bobIdx = ext.findIndex((j) => j.name === 'HairBob')
    const bob = prims.find((p) => p.boneIdx === bobIdx)
    expect(bob?.type).toBe(3)               // ellipsoid
  })

  it('emits roundedBox + blend group 12 for HairLong segments', () => {
    const ext = extendRigWithHair(RIG, DEFAULT_LONG_HAIR)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, DEFAULT_LONG_HAIR)
    const longPrims = prims.filter((p) => /^HairLong/.test(ext[p.boneIdx]?.name ?? ''))
    expect(longPrims.length).toBe(DEFAULT_LONG_HAIR.length)
    for (const p of longPrims) {
      expect(p.type).toBe(2)                // roundedBox
      expect(p.blendGroup).toBe(12)         // long hair group
    }
  })

  it('emits bent_capsule (type 14) + blend group 13 for HairStrand chunks', () => {
    const ext = extendRigWithHair(RIG, DEFAULT_HAIR_STRANDS)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, DEFAULT_HAIR_STRANDS)
    const strandPrims = prims.filter((p) => /^HairStrand/.test(ext[p.boneIdx]?.name ?? ''))
    expect(strandPrims.length).toBe(DEFAULT_HAIR_STRANDS.length)
    for (const p of strandPrims) {
      expect(p.type).toBe(14)               // bent capsule
      expect(p.blendGroup).toBe(13)         // strand group
      // Slot 4 sentinel: the demo overrides per frame, but at boot
      // emission, rotation is [0,0,0,0] — meaning tipDelta = 0.
      expect(p.rotation).toEqual([0, 0, 0, 0])
    }
  })
})

describe('chibiRaymarchPrimitives — body extras + wardrobe', () => {
  it('emits roundedBox cape segments with worldStripes (colorFunc 8) by default', () => {
    const ext = extendRigWithBodyParts(RIG, DEFAULT_CAPE_PARTS)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, undefined, DEFAULT_CAPE_PARTS)
    const capePrims = prims.filter((p) => /^Cape/.test(ext[p.boneIdx]?.name ?? ''))
    expect(capePrims.length).toBeGreaterThan(0)
    for (const p of capePrims) {
      expect(p.type).toBe(2)                // roundedBox
      expect(p.colorFunc).toBe(8)           // worldStripes
      expect(p.blendGroup).toBe(9)          // cape group
    }
  })

  it('emits sphere primitives for grenades, no blend group', () => {
    const ext = extendRigWithBodyParts(RIG, DEFAULT_GRENADE_BELT)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, undefined, DEFAULT_GRENADE_BELT)
    const grenades = prims.filter((p) => /^Grenade/.test(ext[p.boneIdx]?.name ?? ''))
    for (const g of grenades) {
      expect(g.type).toBe(0)                // sphere
      // No blendGroup means it falls through to default (undefined / 0).
      expect(g.blendGroup ?? 0).toBe(0)
    }
  })

  it('emits ellipsoid for WP_Helmet (round routing) + box for WP_ChestPlate', () => {
    const knightParts = outfitToBodyParts(WARDROBE.knight)
    const ext = extendRigWithBodyParts(RIG, knightParts)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, undefined, knightParts)
    const helmet = prims.find((p) => ext[p.boneIdx]?.name === 'WP_Helmet')
    const chest  = prims.find((p) => ext[p.boneIdx]?.name === 'WP_ChestPlate')
    expect(helmet?.type).toBe(3)            // ellipsoid (round routing)
    expect(chest?.type).toBe(2)             // roundedBox (box routing)
    // Both share blend group 11 (armor).
    expect(helmet?.blendGroup).toBe(11)
    expect(chest?.blendGroup).toBe(11)
  })

  it('honours BodyPart.shape override (round vs box)', () => {
    const items: BodyPart[] = [
      { name: 'WP_Mage_Hood', parentName: 'Head', offset: [0, 0, 0], displaySize: [0.22, 0.22, 0.22], shape: 'round' },
      { name: 'WP_Mage_Belt', parentName: 'Hips', offset: [0, 0, 0], displaySize: [0.18, 0.04, 0.16] },
    ]
    const ext = extendRigWithBodyParts(RIG, items)
    const m = chibiMaterial(ext)
    const prims = chibiRaymarchPrimitives(ext, m, undefined, undefined, undefined, items)
    const hood = prims.find((p) => ext[p.boneIdx]?.name === 'WP_Mage_Hood')
    const belt = prims.find((p) => ext[p.boneIdx]?.name === 'WP_Mage_Belt')
    expect(hood?.type).toBe(3)              // round override → ellipsoid
    expect(belt?.type).toBe(2)              // default → roundedBox
  })
})
