// Archetype tag canonicalization — JOB-T4 (see scaffolds/.claude/TAG_PROPOSALS.md)
//
// Scaffold data declares synonymous tags across projects (e.g. ninja_garden
// uses `shielded`, action_rpg_atb uses `shield`, action_rpg_atb uses
// `heavy_armored` — all three mean the same concept). Rather than force
// cross-scaffold data edits, resolve at dispatch time: the validator + the
// mechanic-param reader call `canonicalize(tag)` before comparison.
//
// Adding a new alias group: pick the canonical (the form cataloged in
// TAG_ESSENCE_MAP.md Tier 2/5), list the aliases, and write a one-line
// note on why the synonymy exists (scaffold context, concept-overlap).

export type CanonicalTag = string
export type AliasTag = string

interface AliasGroup {
  readonly canonical: CanonicalTag
  readonly aliases: readonly AliasTag[]
  /** why these tags collapse — for code-review + audit-log */
  readonly rationale: string
}

export const TAG_ALIAS_GROUPS: readonly AliasGroup[] = [
  {
    canonical: 'shielded',
    aliases: ['heavy_armored', 'shield', 'armored_pack', 'armored'],
    rationale:
      'Shield/armor are a single behavior: attack must break guard before damage applies. ' +
      'ninja_garden uses "shielded"; action_rpg_atb uses "heavy_armored" (+"shield" on knight class + "armored_pack" on spawner). ' +
      'Collapses 4 declarations into one.',
  },
  {
    canonical: 'shrine_main_locked',
    aliases: [
      'locked_boss',
      'boss_door_locked',
      'locked_small',
      'boss_arena_volcanic_door',
      'lock_key_substitute',
    ],
    rationale:
      'All five tag LockAndKey doors/arenas — difference is narrative (shrine vs boss vs volcanic) not mechanical. ' +
      'The locks_resolver reads archetype data to pick the key_item; the tag only needs to say "locked".',
  },
  {
    canonical: 'ranged_attacker',
    aliases: ['ranged_thrower', 'archer', 'projectile_enemy'],
    rationale:
      'Thrower/archer/projectile-enemy all branch to the same AI path (maintain-range + fire-projectile). ' +
      'ninja_garden declares both `ranged_thrower` (shadow_ninja) and `ranged_attacker` (tengu_archer) — unify.',
  },
  {
    canonical: 'melee_attacker',
    aliases: ['melee_swinger', 'close_combat', 'slasher'],
    rationale:
      'All branch to the same AI path (close-to-range + swing). Reserved for future scaffold adoption; ' +
      'no current duplication in cross-scaffolds but anticipated when more scaffolds land.',
  },
  {
    canonical: 'mage',
    aliases: ['wizard', 'sorcerer', 'black_mage'],
    rationale:
      'JRPG T8 class-tag: mage is the canonical for offensive-magic-caster. action_rpg_atb uses "mage"; ' +
      'rhythm_fighter uses "wizard" for the same concept. sorcerer/black_mage reserved for future scaffolds.',
  },
  {
    canonical: 'healer',
    aliases: ['white_mage', 'priest', 'cleric'],
    rationale:
      'JRPG T8 class-tag: healer is the canonical for restorative-caster. ' +
      'FF-lineage uses "white_mage"; DQ-lineage uses "priest"; D&D-lineage uses "cleric". Equivalent gameplay slot.',
  },
  // Deliberately NOT merged — "heavy" in rhythm_fighter means rushdown-archetype-weight-class,
  // "heavy_armored" means shielded-tank. Different concepts. See TAG_PROPOSALS.md § T7 vs T2.
]

/**
 * Reverse index: alias → canonical. Built once at module-load.
 */
const ALIAS_TO_CANONICAL: ReadonlyMap<AliasTag, CanonicalTag> = (() => {
  const m = new Map<AliasTag, CanonicalTag>()
  for (const g of TAG_ALIAS_GROUPS) {
    for (const a of g.aliases) {
      if (m.has(a)) {
        // eslint-disable-next-line no-console
        console.warn(
          `tag_aliases: "${a}" is declared as alias in multiple groups ` +
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
 * If `tag` is a known alias, return its canonical form. Otherwise return
 * `tag` unchanged. Case-sensitive — scaffold data uses snake_case
 * consistently.
 */
export function canonicalize(tag: string): string {
  return ALIAS_TO_CANONICAL.get(tag) ?? tag
}

/**
 * Canonicalize every tag in a list, dedup, return sorted. Stable ordering
 * for hash-keyed dispatch tables.
 */
export function canonicalizeTags(tags: readonly string[]): string[] {
  const seen = new Set<string>()
  for (const t of tags) seen.add(canonicalize(t))
  return [...seen].sort()
}

/**
 * For a canonical tag, enumerate all aliases (inclusive of itself). Used
 * by the validator when checking `requires_tags: ['enemy']` — it should
 * accept any alias of `enemy` too, if any are ever declared.
 */
export function aliasesOf(canonical: CanonicalTag): readonly string[] {
  const g = TAG_ALIAS_GROUPS.find(x => x.canonical === canonical)
  return g ? [canonical, ...g.aliases] : [canonical]
}

/**
 * Diagnostic: is this tag a known alias (i.e. canonicalize() would
 * substitute it)? Used by the scaffold-linter to warn authors who are
 * declaring a non-canonical form.
 */
export function isAlias(tag: string): boolean {
  return ALIAS_TO_CANONICAL.has(tag)
}
