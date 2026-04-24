/**
 * motion_aliases.ts — canonicalization of motion-verb synonyms.
 * See scaffolds/.claude/sprite_sheets/MOTION_ESSENCE_MAP.md JOB-M4.
 */

import { describe, it, expect } from 'vitest'
import {
  canonicalize,
  canonicalizeVerbs,
  aliasesOf,
  isAlias,
  MOTION_ALIAS_GROUPS,
} from '../src/design/motion_aliases'

describe('motion_aliases — canonicalize()', () => {
  it('returns unchanged verb when not a known alias', () => {
    expect(canonicalize('walk')).toBe('walk')
    expect(canonicalize('run')).toBe('run')
    expect(canonicalize('idle')).toBe('idle')
    expect(canonicalize('totally_unknown_verb')).toBe('totally_unknown_verb')
  })

  it('maps magic-cast family to cast', () => {
    expect(canonicalize('magic_cast')).toBe('cast')
    expect(canonicalize('spell_cast')).toBe('cast')
    expect(canonicalize('casting')).toBe('cast')
    expect(canonicalize('cast_spell')).toBe('cast')
  })

  it('maps duck/squat/kneel to crouch', () => {
    expect(canonicalize('duck')).toBe('crouch')
    expect(canonicalize('squat')).toBe('crouch')
    expect(canonicalize('kneel')).toBe('crouch')
  })

  it('maps charge_attack/power_up to charge', () => {
    expect(canonicalize('charge_attack')).toBe('charge')
    expect(canonicalize('power_up')).toBe('charge')
  })

  it('maps whip_swing and sword_swing to slash', () => {
    expect(canonicalize('whip_swing')).toBe('slash')
    expect(canonicalize('sword_swing')).toBe('slash')
    expect(canonicalize('chop')).toBe('slash')
  })

  it('maps hurt-family to hurt', () => {
    expect(canonicalize('flinch')).toBe('hurt')
    expect(canonicalize('stagger')).toBe('hurt')
    expect(canonicalize('knockback')).toBe('hurt')
  })

  it('maps shoot-family to shoot', () => {
    expect(canonicalize('fire')).toBe('shoot')
    expect(canonicalize('discharge')).toBe('shoot')
    expect(canonicalize('launch')).toBe('shoot')
  })

  it('maps leap/hop/bound to jump', () => {
    expect(canonicalize('leap')).toBe('jump')
    expect(canonicalize('hop')).toBe('jump')
    expect(canonicalize('bound')).toBe('jump')
  })

  it('does NOT collapse parry to block (different semantics)', () => {
    // RoA parry has a 6-frame window + reflects; Smash-block is tanking.
    // See MOTION_ESSENCE_MAP.md commentary.
    expect(canonicalize('parry')).toBe('parry')
    expect(canonicalize('block')).toBe('block')
  })

  it('does NOT collapse fly to float (state vs locomotion distinction)', () => {
    expect(canonicalize('fly')).toBe('fly')
    expect(canonicalize('float')).toBe('float')
  })

  it('does NOT collapse grapple_throw to grapple (different playback_mode)', () => {
    expect(canonicalize('grapple_throw')).toBe('grapple_throw')
    expect(canonicalize('grapple')).toBe('grapple')
  })
})

describe('motion_aliases — canonicalizeVerbs()', () => {
  it('dedups when aliases collapse to the same canonical', () => {
    expect(canonicalizeVerbs(['magic_cast', 'spell_cast', 'cast'])).toEqual(['cast'])
  })

  it('preserves non-alias verbs alongside canonicalized ones', () => {
    expect(canonicalizeVerbs(['walk', 'duck', 'run'])).toEqual(['crouch', 'run', 'walk'])
  })

  it('returns sorted output for stable dispatch keys', () => {
    const result = canonicalizeVerbs(['slash', 'idle', 'crouch'])
    expect(result).toEqual([...result].sort())
  })

  it('empty input returns empty output', () => {
    expect(canonicalizeVerbs([])).toEqual([])
  })
})

describe('motion_aliases — aliasesOf()', () => {
  it('returns canonical + aliases for cast', () => {
    const all = aliasesOf('cast')
    expect(all).toContain('cast')
    expect(all).toContain('magic_cast')
    expect(all).toContain('spell_cast')
    expect(all.length).toBeGreaterThanOrEqual(5)
  })

  it('returns canonical + aliases for crouch', () => {
    const all = aliasesOf('crouch')
    expect(all).toContain('crouch')
    expect(all).toContain('duck')
  })

  it('returns just the verb itself when canonical has no known aliases', () => {
    expect(aliasesOf('idle')).toEqual(['idle'])
  })
})

describe('motion_aliases — isAlias()', () => {
  it('identifies known aliases', () => {
    expect(isAlias('magic_cast')).toBe(true)
    expect(isAlias('duck')).toBe(true)
    expect(isAlias('charge_attack')).toBe(true)
    expect(isAlias('whip_swing')).toBe(true)
  })

  it('canonical forms themselves are NOT aliases', () => {
    expect(isAlias('cast')).toBe(false)
    expect(isAlias('crouch')).toBe(false)
    expect(isAlias('jump')).toBe(false)
  })

  it('unknown verbs are not aliases', () => {
    expect(isAlias('walk')).toBe(false)
    expect(isAlias('random_xyz')).toBe(false)
  })
})

describe('motion_aliases — group-integrity', () => {
  it('no alias appears in more than one group', () => {
    const seen = new Set<string>()
    for (const g of MOTION_ALIAS_GROUPS) {
      for (const a of g.aliases) {
        expect(seen.has(a), `alias "${a}" in multiple groups`).toBe(false)
        seen.add(a)
      }
    }
  })

  it('no canonical is also declared as alias', () => {
    const canonicals = new Set(MOTION_ALIAS_GROUPS.map(g => g.canonical))
    for (const g of MOTION_ALIAS_GROUPS) {
      for (const a of g.aliases) {
        expect(canonicals.has(a), `alias "${a}" is also a canonical`).toBe(false)
      }
    }
  })

  it('every group has a non-empty rationale', () => {
    for (const g of MOTION_ALIAS_GROUPS) {
      expect(g.rationale.length).toBeGreaterThan(20)
    }
  })

  it('has at least 7 groups covering Tier 1/2/3 verbs', () => {
    expect(MOTION_ALIAS_GROUPS.length).toBeGreaterThanOrEqual(7)
  })
})
