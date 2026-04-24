/**
 * Scaffold-author ergonomic helpers for projectile-sprite lookup.
 *
 * Parallel to `parallax_setup.ts` but for the `projectile` kind. Without
 * these helpers a scaffold author would have to:
 *   1. loadExtractionIndex([essence])
 *   2. getProjectilesByOwner(actor)
 *   3. filter to desired sub_kind
 *   4. hand-wire sprite_id + frame_count + cell_size into a weapon config
 *
 * This module collapses 2-3 into typed queries and 4 into a well-shaped
 * result object the caller can hand to `BulletPattern` or
 * `AttackFrames` mechanics.
 *
 * Note: unlike parallax_setup, projectile configs typically become
 * DATA (weapon tables) rather than MechanicInstances directly. These
 * helpers return a resolved config object, not a mechanic; the
 * scaffold's BulletPattern mechanic consumes the config.
 */

import {
  getAnimationsBySubKind,
  getAnimationsByActor,
  type TaggedAnimation,
  type ProjectileSubKind,
} from './kind_index'

/** Resolved projectile — all the fields a weapon/attack mechanic needs. */
export interface ResolvedProjectile {
  sprite_id: string
  sub_kind: ProjectileSubKind
  cell_size_px: [number, number]
  frame_count: number
  source_essence: string
  /** The extraction entry's actor field (owner of this projectile), if tagged. */
  owner?: string
  /** Fallback flag — true when background_params-like defaults were used
   *  because the extraction data lacked explicit metadata. */
  uses_defaults: boolean
}

/**
 * Find all projectiles owned by a given actor (e.g., `samus`,
 * `simon_belmont`). Returns empty array if actor not found or
 * extraction index not loaded.
 */
export function findProjectilesByOwner(ownerActor: string): ResolvedProjectile[] {
  const entries = getAnimationsByActor(ownerActor).filter(
    (t) => t.anim.kind === 'projectile',
  )
  return entries.map(resolveProjectile)
}

/**
 * Find all projectiles of a given sub_kind across all loaded essences.
 * Useful for building a generic weapon roster (e.g., all `gun_proj`
 * across the corpus when no specific actor is targeted).
 */
export function findProjectilesBySubKind(
  subKind: ProjectileSubKind,
): ResolvedProjectile[] {
  const entries = getAnimationsBySubKind('projectile', subKind)
  return entries.map(resolveProjectile)
}

/**
 * Find the canonical/default projectile for a given actor+sub_kind
 * pair. Returns null if no match. Used when a scaffold wants "samus's
 * special_attack_proj" without caring which one — picks the first by
 * extraction order.
 */
export function pickCanonicalProjectile(
  ownerActor: string,
  subKind: ProjectileSubKind,
): ResolvedProjectile | null {
  const matches = findProjectilesByOwner(ownerActor).filter(
    (p) => p.sub_kind === subKind,
  )
  return matches.length > 0 ? matches[0] : null
}

// ──────────────────────────── internal ────────────────────────────

function resolveProjectile(t: TaggedAnimation): ResolvedProjectile {
  const sub_kind = t.anim.sub_kind as ProjectileSubKind | undefined
  const px = t.anim.pixel_resolution_per_frame_px
  const cell_size_px: [number, number] = px
    ? [px[0], px[1]]
    : defaultCellSize(sub_kind)
  return {
    sprite_id: t.anim.name,
    sub_kind: sub_kind ?? 'gun_proj',  // reasonable default for untagged
    cell_size_px,
    frame_count: t.anim.frame_count ?? 1,
    source_essence: t.essence,
    owner: t.anim.actor ?? undefined,
    uses_defaults: !px || !sub_kind,
  }
}

/** Canonical cell sizes per projectile sub_kind, used when extraction
 *  data is missing `pixel_resolution_per_frame_px` (shouldn't happen
 *  after INT-15 tagging but defensive). */
function defaultCellSize(sk?: string): [number, number] {
  switch (sk) {
    case 'gun_proj':              return [8, 8]
    case 'special_attack_proj':   return [16, 16]
    case 'missile':               return [16, 16]
    case 'melee_thrown':          return [16, 16]
    case 'explosive':             return [16, 16]
    default:                      return [16, 16]
  }
}
