// Motion-verb canonicalization — JOB-M4 (see scaffolds/.claude/sprite_sheets/MOTION_ESSENCE_MAP.md)
//
// The 41-verb MOTION_PROGRESSION_CATALOG enumerates canonical names, but
// scaffold-extracted animations + LLM-generated names use variant forms
// ("duck" vs "crouch", "magic_cast" vs "cast", "charge_attack" vs
// "charge"). Resolve at dispatch time so per-verb lookup tables use a
// single canonical form.
//
// Parallel to tag_aliases.ts (JOB-T4). Same runtime contract:
// canonicalize(), canonicalizeVerbs(), aliasesOf(), isAlias().

export type CanonicalVerb = string
export type AliasVerb = string

interface AliasGroup {
  readonly canonical: CanonicalVerb
  readonly aliases: readonly AliasVerb[]
  readonly rationale: string
}

export const MOTION_ALIAS_GROUPS: readonly AliasGroup[] = [
  {
    canonical: 'cast',
    aliases: ['magic_cast', 'spell_cast', 'casting', 'cast_spell', 'incant'],
    rationale:
      'Spell-casting motion is a single animation-family regardless of spell-type (fire/ice/heal). ' +
      'The 8-frame progression is identical — hands raise → glow → release. ' +
      'Corpus has 45 `cast` hits which already subsume `magic_cast` via name-match.',
  },
  {
    canonical: 'crouch',
    aliases: ['duck', 'squat', 'kneel', 'stoop'],
    rationale:
      'Crouch is the MOTION_PROGRESSION canonical; Castlevania-lineage (1986/1987) uses "duck" specifically ' +
      'for the whip-low variant but the base motion is identical to Mario-lineage "crouch". ' +
      'Kneel/squat cover posture-variants (spell-kneel, rest-squat) that play the same frames.',
  },
  {
    canonical: 'charge',
    aliases: ['charge_attack', 'power_up', 'hold_to_release', 'focus'],
    rationale:
      'Charge is the hold-then-release motion primitive (R-Type wave-cannon, SF2 charge-motions, SM Super-Missile). ' +
      'The charge-attack variant is just charge + strike — the charge portion is shared.',
  },
  {
    canonical: 'slash',
    aliases: ['sword_swing', 'whip_swing', 'blade_swing', 'strike_sword', 'chop'],
    rationale:
      'Slash is the weapon-horizontal-swing motion. Whip (Castlevania) shares the same 4-frame-active-hitbox ' +
      'structure as sword-slash (Zelda/SotN). Treat as one verb for animation generation; differentiate via ' +
      'weapon-sprite overlay.',
  },
  {
    canonical: 'jump',
    aliases: ['leap', 'hop', 'bound'],
    rationale:
      'Jump is the canonical vertical-launch. Leap/hop/bound are context-variants (leap = longer horizontal, ' +
      'hop = shorter, bound = multi-jump-chain) but share the F1-F8 MOTION_PROGRESSION structure.',
  },
  {
    canonical: 'hurt',
    aliases: ['flinch', 'stagger', 'recoil', 'knockback'],
    rationale:
      'Hurt is the damage-reaction motion. Knockback is the extended variant (hurt + airborne displacement) ' +
      'but the initial 2-3 frames are identical. Stagger = hurt-with-no-flinch-recovery.',
  },
  {
    canonical: 'shoot',
    aliases: ['fire', 'discharge', 'release_projectile', 'launch'],
    rationale:
      'Shoot is the projectile-release motion. Fire/discharge/launch are semantic-synonyms across genres ' +
      '(Mega-Man "shoot", Shmup "fire", Metroid "launch" for missiles — same animation primitive).',
  },
  // Deliberately NOT merged:
  // - `block` vs `parry`: 6-frame window and timing-gate make parry distinct (RoA-divergence from Smash-block).
  //   See TAG_ESSENCE_MAP.md Tier-4 block_parry. Different verb, different gameplay.
  // - `fly` vs `float`: fly is locomotion (active wing-flap), float is state (passive hover). Different base_state.
  // - `grapple` vs `grapple_throw`: grapple is grab-hold, grapple_throw is grab-hold-then-release-with-velocity.
  //   Different playback_mode (held vs one_off).
]

const ALIAS_TO_CANONICAL: ReadonlyMap<AliasVerb, CanonicalVerb> = (() => {
  const m = new Map<AliasVerb, CanonicalVerb>()
  for (const g of MOTION_ALIAS_GROUPS) {
    for (const a of g.aliases) {
      if (m.has(a)) {
        // eslint-disable-next-line no-console
        console.warn(
          `motion_aliases: "${a}" declared in multiple groups ` +
          `(existing=${m.get(a)}, new=${g.canonical}). Using existing.`,
        )
        continue
      }
      m.set(a, g.canonical)
    }
  }
  return m
})()

/**
 * If `verb` is a known alias, return its canonical form. Otherwise pass
 * through unchanged.
 */
export function canonicalize(verb: string): string {
  return ALIAS_TO_CANONICAL.get(verb) ?? verb
}

/**
 * Canonicalize + dedup + sort — stable dispatch keys for per-verb maps.
 */
export function canonicalizeVerbs(verbs: readonly string[]): string[] {
  const seen = new Set<string>()
  for (const v of verbs) seen.add(canonicalize(v))
  return [...seen].sort()
}

/**
 * For a canonical verb, enumerate all aliases (inclusive of itself).
 */
export function aliasesOf(canonical: CanonicalVerb): readonly string[] {
  const g = MOTION_ALIAS_GROUPS.find(x => x.canonical === canonical)
  return g ? [canonical, ...g.aliases] : [canonical]
}

/**
 * Diagnostic: is this verb a known alias that canonicalize() would remap?
 */
export function isAlias(verb: string): boolean {
  return ALIAS_TO_CANONICAL.has(verb)
}
