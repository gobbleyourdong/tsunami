/**
 * tag_aliases.ts — canonicalization of archetype-tag synonyms.
 * See scaffolds/.claude/TAG_PROPOSALS.md JOB-T4.
 */

import { describe, it, expect } from 'vitest'
import {
  canonicalize,
  canonicalizeTags,
  aliasesOf,
  isAlias,
  TAG_ALIAS_GROUPS,
} from '../src/design/tag_aliases'

describe('tag_aliases — canonicalize()', () => {
  it('returns unchanged tag when not a known alias', () => {
    expect(canonicalize('player')).toBe('player')
    expect(canonicalize('enemy')).toBe('enemy')
    expect(canonicalize('totally_unknown_tag_xyz')).toBe('totally_unknown_tag_xyz')
  })

  it('maps shielded-family aliases to shielded', () => {
    expect(canonicalize('heavy_armored')).toBe('shielded')
    expect(canonicalize('shield')).toBe('shielded')
    expect(canonicalize('armored_pack')).toBe('shielded')
    expect(canonicalize('armored')).toBe('shielded')
  })

  it('maps lock-family aliases to shrine_main_locked', () => {
    expect(canonicalize('locked_boss')).toBe('shrine_main_locked')
    expect(canonicalize('boss_door_locked')).toBe('shrine_main_locked')
    expect(canonicalize('locked_small')).toBe('shrine_main_locked')
    expect(canonicalize('boss_arena_volcanic_door')).toBe('shrine_main_locked')
  })

  it('maps ranged_thrower to ranged_attacker', () => {
    expect(canonicalize('ranged_thrower')).toBe('ranged_attacker')
  })

  it('does NOT collapse "heavy" (rhythm_fighter weight-class) to shielded', () => {
    // TAG_PROPOSALS.md deliberately keeps "heavy" separate from "heavy_armored"
    expect(canonicalize('heavy')).toBe('heavy')
  })
})

describe('tag_aliases — canonicalizeTags()', () => {
  it('dedups when aliases collapse to the same canonical', () => {
    expect(canonicalizeTags(['heavy_armored', 'shield', 'shielded'])).toEqual(['shielded'])
  })

  it('preserves non-alias tags alongside canonicalized ones', () => {
    expect(canonicalizeTags(['player', 'shield', 'damageable'])).toEqual([
      'damageable', 'player', 'shielded',
    ])
  })

  it('returns sorted output for stable dispatch keys', () => {
    const result = canonicalizeTags(['shielded', 'damageable', 'player'])
    expect(result).toEqual([...result].sort())
  })

  it('empty input returns empty output', () => {
    expect(canonicalizeTags([])).toEqual([])
  })
})

describe('tag_aliases — aliasesOf()', () => {
  it('returns canonical + its aliases', () => {
    const all = aliasesOf('shielded')
    expect(all).toContain('shielded')
    expect(all).toContain('heavy_armored')
    expect(all).toContain('shield')
    expect(all.length).toBeGreaterThanOrEqual(4)
  })

  it('returns just the tag itself when canonical has no known aliases', () => {
    expect(aliasesOf('player')).toEqual(['player'])
  })
})

describe('tag_aliases — isAlias()', () => {
  it('identifies known aliases', () => {
    expect(isAlias('heavy_armored')).toBe(true)
    expect(isAlias('ranged_thrower')).toBe(true)
    expect(isAlias('locked_boss')).toBe(true)
  })

  it('canonical forms themselves are NOT aliases (they are the target)', () => {
    expect(isAlias('shielded')).toBe(false)
    expect(isAlias('ranged_attacker')).toBe(false)
    expect(isAlias('shrine_main_locked')).toBe(false)
  })

  it('unknown tags are not aliases', () => {
    expect(isAlias('player')).toBe(false)
    expect(isAlias('random_xyz')).toBe(false)
  })
})

describe('tag_aliases — group-integrity', () => {
  it('no alias appears in more than one group', () => {
    const seen = new Set<string>()
    for (const g of TAG_ALIAS_GROUPS) {
      for (const a of g.aliases) {
        expect(seen.has(a), `alias "${a}" declared in multiple groups`).toBe(false)
        seen.add(a)
      }
    }
  })

  it('no canonical is also declared as an alias elsewhere', () => {
    const canonicals = new Set(TAG_ALIAS_GROUPS.map(g => g.canonical))
    for (const g of TAG_ALIAS_GROUPS) {
      for (const a of g.aliases) {
        expect(canonicals.has(a), `alias "${a}" is also a canonical — would chain`).toBe(false)
      }
    }
  })

  it('every group has a non-empty rationale', () => {
    for (const g of TAG_ALIAS_GROUPS) {
      expect(g.rationale.length).toBeGreaterThan(20)
    }
  })
})
