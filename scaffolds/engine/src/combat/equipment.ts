// Attack stats + element bitmask.
//
// Modeled on SotN's `Equipment` struct (include/game.h, size=0x32):
// flat row-per-item, one shape serving weapons / projectiles / spells /
// familiar-attacks. The bitmask trick — physical damage types (CUT/STRIKE/
// PIERCE) share the same u16 field with elemental types (FIRE/ICE/HOLY/
// CURSE) — collapses "damage type" and "element" into one resistance lookup.
//
// See scaffolds/.claude/combat/UNIFIED_DAMAGE_SYSTEM.md for design rationale.

/**
 * Element bitmask. 16-bit field where each bit identifies a damage type
 * or element. An attack carries a bitmask (`CUT | FIRE` = flaming sword);
 * a defender has a resistance-and-weakness bitmask; damage multiplier is
 * computed per-bit.
 */
export const Element = {
  // Physical damage types (bits 0-3)
  CUT:     1 << 0,   // slashing — swords, claws
  STRIKE:  1 << 1,   // blunt — maces, fists, hammers
  PIERCE:  1 << 2,   // thrusting — spears, arrows
  EXPLOSIVE: 1 << 3, // bombs, grenades — AOE physical

  // Elemental types (bits 4-11)
  FIRE:    1 << 4,
  ICE:     1 << 5,
  THUNDER: 1 << 6,
  HOLY:    1 << 7,
  DARK:    1 << 8,
  CURSE:   1 << 9,
  POISON:  1 << 10,
  WATER:   1 << 11,

  // Special flags (bits 12-15)
  UNBLOCKABLE: 1 << 12,  // grabs, certain bosses' supers
  LIFESTEAL:   1 << 13,  // heal on hit (Soul Steal, Dark Metamorphosis)
  KNOCKDOWN:   1 << 14,
  STAGGER:     1 << 15,  // break defender's shield/block
} as const

export type ElementMask = number

/** Physical damage types (subset for lookup-speed convenience). */
export const PhysicalElements: ElementMask = Element.CUT | Element.STRIKE | Element.PIERCE

/**
 * Flat stats row. Attack entities carry one of these. Matches SotN's
 * `Equipment` layout at semantic level (field names differ to stay
 * TypeScript-idiomatic). Per `UNIFIED_DAMAGE_SYSTEM.md` §stat-row-layer.
 *
 * Shared by weapons, projectiles, spells, familiar attacks — one shape
 * for all. New-attack-type = new stats-row instance.
 */
export interface AttackStats {
  /** Base damage before resistance calculation. */
  readonly attack: number
  /** Element + damage-type bitmask. See Element constants. */
  readonly element: ElementMask
  /** Frames of victim hitstun. Matches SF2's hitstun_frames. */
  readonly stun_frames: number
  /** Frames of blockstun when blocked. */
  readonly block_stun_frames: number
  /** MP cost for spell-attacks. 0 for physical. */
  readonly mp_cost: number
  /** Frames the owner is locked during the attack. SotN `lockDuration`. */
  readonly lock_duration: number
  /** Max chains this move participates in. SotN `chainLimit`. */
  readonly chain_limit: number
  /** Critical-hit probability [0, 1]. */
  readonly critical_rate: number
  /** Optional hit-pause (screen freeze) frames on clean connect. */
  readonly hit_pause_frames?: number
  /** Optional launch velocity on-hit. Lets hitbox publisher drive knockback.
   *  `null` = default knockback from owner's facing + defender's weight. */
  readonly launch?: { x: number; y: number } | null
}

/**
 * Default stats — used for un-stat-rowed attacks (shouldn't happen in
 * production, but lets tests omit when irrelevant).
 */
export const DEFAULT_ATTACK_STATS: AttackStats = {
  attack: 10,
  element: Element.CUT,
  stun_frames: 16,
  block_stun_frames: 10,
  mp_cost: 0,
  lock_duration: 30,
  chain_limit: 1,
  critical_rate: 0,
}

/**
 * Compute damage multiplier for attacker's element bitmask against
 * defender's weakness + resistance masks. Weakness >> Resistance >>
 * Neutral (1.0). Multiple overlapping bits multiply (fire-weakness AND
 * curse-weakness attacker hits for 4x on a fire+curse enemy).
 *
 * Matches SotN behavior per research § elemental.
 */
export function elementMultiplier(
  attack_mask: ElementMask,
  weakness_mask: ElementMask,
  resistance_mask: ElementMask,
): number {
  let mult = 1.0
  for (let bit = 0; bit < 16; bit++) {
    const b = 1 << bit
    if ((attack_mask & b) === 0) continue
    if ((weakness_mask & b) !== 0) mult *= 2.0
    if ((resistance_mask & b) !== 0) mult *= 0.5
  }
  return mult
}

/** Convenience: does this attack have ANY physical damage type? */
export function isPhysical(mask: ElementMask): boolean {
  return (mask & PhysicalElements) !== 0
}

/** Convenience: is this an unblockable (grab)? */
export function isUnblockable(mask: ElementMask): boolean {
  return (mask & Element.UNBLOCKABLE) !== 0
}
