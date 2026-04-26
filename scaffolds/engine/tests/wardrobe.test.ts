import { describe, it, expect } from 'vitest'
import {
  WARDROBE,
  WARDROBE_KNIGHT,
  WARDROBE_MAGE,
  WARDROBE_LIGHT,
  WARDROBE_BARBARIAN,
  WARDROBE_NINJA,
  outfitToBodyParts,
} from '../src/character3d/wardrobe'

describe('wardrobe registry', () => {
  it('exposes all 5 named outfits', () => {
    expect(Object.keys(WARDROBE).sort()).toEqual(
      ['barbarian', 'knight', 'light', 'mage', 'ninja'],
    )
  })

  it('outfitToBodyParts flattens pieces into one BodyPart array', () => {
    const knightParts = outfitToBodyParts(WARDROBE_KNIGHT)
    // Knight has 14 pieces: helmet, 2 pauldrons, chest, back, belt,
    // 2 vambraces, 2 gauntlets, 2 greaves, 2 boots.
    expect(knightParts.length).toBe(14)
    // Every part has the WP_ prefix that the rig emitter routes on.
    for (const p of knightParts) {
      expect(p.name).toMatch(/^WP_/)
      expect(p.parentName.length).toBeGreaterThan(0)
      expect(p.offset.length).toBe(3)
      expect(p.displaySize.length).toBe(3)
    }
  })

  it('all outfits use unique bone names across the registry', () => {
    const names: string[] = []
    for (const outfit of Object.values(WARDROBE)) {
      for (const part of outfitToBodyParts(outfit)) names.push(part.name)
    }
    const dupes = names.filter((n, i) => names.indexOf(n) !== i)
    expect(dupes).toEqual([])
  })

  it('routes piece prefixes correctly per outfit', () => {
    expect(outfitToBodyParts(WARDROBE_MAGE).every((p) => p.name.startsWith('WP_Mage_'))).toBe(true)
    expect(outfitToBodyParts(WARDROBE_LIGHT).every((p) => p.name.startsWith('WP_Light_'))).toBe(true)
    expect(outfitToBodyParts(WARDROBE_BARBARIAN).every((p) => p.name.startsWith('WP_Barb_'))).toBe(true)
    expect(outfitToBodyParts(WARDROBE_NINJA).every((p) => p.name.startsWith('WP_Ninja_'))).toBe(true)
    // Knight is the legacy outfit — uses bare WP_<role> names (no
    // outfit prefix). Verify that to lock the convention down.
    expect(outfitToBodyParts(WARDROBE_KNIGHT).every((p) => p.name.startsWith('WP_'))).toBe(true)
  })

  it('shape override defaults to undefined except where authored', () => {
    // Mage hood needs `shape: 'round'` because its name doesn't match
    // the default Helmet/Pauldron/Gauntlet round-detect regex.
    const mageHood = outfitToBodyParts(WARDROBE_MAGE).find((p) => p.name === 'WP_Mage_Hood')
    expect(mageHood?.shape).toBe('round')
    // Knight chest plate stays box-shaped (no override).
    const chest = outfitToBodyParts(WARDROBE_KNIGHT).find((p) => p.name === 'WP_ChestPlate')
    expect(chest?.shape).toBeUndefined()
  })
})
