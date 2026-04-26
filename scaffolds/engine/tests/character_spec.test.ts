import { describe, it, expect } from 'vitest'
import {
  serializeCharacterSpec,
  parseCharacterSpec,
  stringifyCharacterSpec,
  upgradeSpec,
  type CharacterArchetype,
  type CharacterSpecV2,
  type CharacterSpecV1,
} from '../src/character3d/character_spec'

const EMPTY_ARCHETYPE: CharacterArchetype = {
  centeredSizes: {},
  centeredOffsets: {},
  limbThickness: {},
}

describe('CharacterSpecV2 round-trip', () => {
  it('round-trips loadout fields through stringify + parse', () => {
    const spec = serializeCharacterSpec({
      name: 'Test Hero',
      archetype: EMPTY_ARCHETYPE,
      proportions: { head: 1.0, torso: 1.1 },
      palette: { skin: [0.95, 0.75, 0.6] },
      face: [],
      hair: [],
      bodyParts: [],
      accessories: [],
      loadout: {
        armor: 'knight',
        hair: 'long+strands',
        cape: true,
        capePattern: 'chevron',
        grenades: false,
        expression: 'angry',
        proportion: 'chibi',
      },
    })
    const json = stringifyCharacterSpec(spec)
    const parsed = parseCharacterSpec(json, EMPTY_ARCHETYPE)
    expect(parsed.version).toBe(2)
    expect(parsed.name).toBe('Test Hero')
    expect(parsed.loadout).toEqual({
      armor: 'knight',
      hair: 'long+strands',
      cape: true,
      capePattern: 'chevron',
      grenades: false,
      expression: 'angry',
      proportion: 'chibi',
    })
  })

  it('omits loadout when not provided', () => {
    const spec = serializeCharacterSpec({
      name: 'Bare',
      archetype: EMPTY_ARCHETYPE,
      proportions: {},
      palette: {},
      face: [], hair: [], bodyParts: [], accessories: [],
    })
    expect(spec.loadout).toBeUndefined()
    // Round-trip preserves the absence — parsed shouldn't synthesize one.
    const parsed = parseCharacterSpec(stringifyCharacterSpec(spec), EMPTY_ARCHETYPE)
    expect(parsed.loadout).toBeUndefined()
  })

  it('upgrades V1 specs without inventing a loadout', () => {
    const v1: CharacterSpecV1 = {
      version: 1,
      name: 'Legacy',
      proportions: { head: 0.9 },
      palette: { skin: [1, 1, 1] },
    }
    const upgraded = upgradeSpec(v1, EMPTY_ARCHETYPE)
    expect(upgraded.version).toBe(2)
    expect(upgraded.name).toBe('Legacy')
    expect(upgraded.proportions.head).toBe(0.9)
    expect(upgraded.loadout).toBeUndefined()
    expect(upgraded.face).toEqual([])
    expect(upgraded.hair).toEqual([])
    expect(upgraded.bodyParts).toEqual([])
  })

  it('rejects unknown spec versions', () => {
    const garbage = JSON.stringify({ version: 99, name: 'oops' })
    expect(() => parseCharacterSpec(garbage, EMPTY_ARCHETYPE)).toThrow()
  })

  it('round-trips anatomy profile overrides', () => {
    const spec = serializeCharacterSpec({
      name: 'Muscle',
      archetype: EMPTY_ARCHETYPE,
      proportions: {},
      palette: {},
      face: [], hair: [], bodyParts: [], accessories: [],
      profiles: {
        limbs: {
          LeftArm:   [0.040, 0.075, 0.075, 0.040],
          RightArm:  [0.040, 0.075, 0.075, 0.040],
        },
        anatomy: {
          pecL:      [0.04, 0.13, 0.10, 0.04],
          gluteR:    [0.06, 0.11, 0.09, 0.05],
        },
      },
    })
    const json = stringifyCharacterSpec(spec)
    const parsed = parseCharacterSpec(json, EMPTY_ARCHETYPE)
    expect(parsed.profiles?.limbs?.LeftArm).toEqual([0.040, 0.075, 0.075, 0.040])
    expect(parsed.profiles?.limbs?.RightArm).toEqual([0.040, 0.075, 0.075, 0.040])
    expect(parsed.profiles?.anatomy?.pecL).toEqual([0.04, 0.13, 0.10, 0.04])
    expect(parsed.profiles?.anatomy?.gluteR).toEqual([0.06, 0.11, 0.09, 0.05])
  })

  it('omits profiles when not provided', () => {
    const spec = serializeCharacterSpec({
      name: 'Bare',
      archetype: EMPTY_ARCHETYPE,
      proportions: {}, palette: {},
      face: [], hair: [], bodyParts: [], accessories: [],
    })
    expect(spec.profiles).toBeUndefined()
  })

  it('partial profile overrides survive round-trip', () => {
    // Just one limb — others should fall back to defaults at apply time.
    const spec = serializeCharacterSpec({
      name: 'Asymmetric',
      archetype: EMPTY_ARCHETYPE,
      proportions: {}, palette: {},
      face: [], hair: [], bodyParts: [], accessories: [],
      profiles: {
        limbs: { LeftArm: [0.03, 0.06, 0.06, 0.03] },
      },
    })
    const parsed = parseCharacterSpec(stringifyCharacterSpec(spec), EMPTY_ARCHETYPE)
    expect(parsed.profiles?.limbs?.LeftArm).toEqual([0.03, 0.06, 0.06, 0.03])
    expect(parsed.profiles?.limbs?.RightArm).toBeUndefined()
    expect(parsed.profiles?.anatomy).toBeUndefined()
  })

  it('passes V2 specs through upgradeSpec unchanged', () => {
    const v2: CharacterSpecV2 = {
      version: 2,
      name: 'Already V2',
      archetype: EMPTY_ARCHETYPE,
      proportions: {},
      palette: {},
      face: [], hair: [], bodyParts: [], accessories: [],
      loadout: { armor: 'mage' },
    }
    const result = upgradeSpec(v2, EMPTY_ARCHETYPE)
    expect(result).toBe(v2)   // identity passthrough
  })
})
