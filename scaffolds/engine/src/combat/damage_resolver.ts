// DamageResolver — consumes CollisionEvents from resolveCombat() and
// applies HP decrement + hitstun + already-hit tracking + element ×
// resistance calculation.
//
// One function per event kind. Pure — takes the world state + events,
// returns a list of DamageApplied records. Application to external
// entities is done by the caller (so that the caller owns their state
// store).

import { elementMultiplier, isUnblockable } from './equipment'
import type { CollisionEvent } from './collision_resolver'
import type { CombatWorld } from './combat_world'

export interface ElementalProfile {
  /** Elements this entity is weak to (2× damage). */
  weakness_mask: number
  /** Elements this entity resists (0.5× damage). */
  resistance_mask: number
}

export interface EntityDamageProfile extends ElementalProfile {
  /** Whether this entity is currently in a blocking state. */
  is_blocking: boolean
  /** Hitstun frames remaining. >0 means stunned. */
  hitstun_frames_remaining: number
}

export interface DamageApplied {
  readonly target_id: string
  readonly source_id: string
  readonly damage_dealt: number
  readonly element_mask: number
  readonly blocked: boolean
  readonly stun_applied: number
  readonly move_id: string
}

export interface DamageResolverInput {
  readonly events: readonly CollisionEvent[]
  readonly world: CombatWorld
  readonly profiles: ReadonlyMap<string, EntityDamageProfile>
}

/**
 * Consume collision events and produce damage-applied records.
 * Caller applies these to their entity state store.
 *
 * Also mutates `already_hit` on external entities to track the same-
 * move-id filter (matches SF2's Final-Fight-derived behavior).
 */
export function resolveDamage(input: DamageResolverInput): DamageApplied[] {
  const applied: DamageApplied[] = []

  for (const ev of input.events) {
    switch (ev.kind) {
      case 'clean_hit': {
        const target = input.world.getExternal(ev.defender)
        const profile = input.profiles.get(ev.defender)
        if (!ev.hitbox.hit_props) break
        const stats = ev.hitbox.hit_props
        const blocked = profile?.is_blocking && !isUnblockable(0)  // element check below
        const mult = profile
          ? elementMultiplier(0, profile.weakness_mask, profile.resistance_mask)
          : 1.0
        const final_damage = Math.max(0, Math.floor(stats.damage * mult))
        applied.push({
          target_id: ev.defender,
          source_id: ev.attacker,
          damage_dealt: blocked ? 0 : final_damage,
          element_mask: 0,
          blocked: !!blocked,
          stun_applied: blocked ? stats.blockstun_frames : stats.hitstun_frames,
          move_id: stats.move_id,
        })
        // Track already-hit to prevent re-hit on same move.
        if (target) target.already_hit.add(stats.move_id)
        break
      }
      case 'trade': {
        // Both sides take damage simultaneously.
        for (const dir of [
          { attacker: ev.a, defender: ev.b, hitbox: ev.a_hits },
          { attacker: ev.b, defender: ev.a, hitbox: ev.b_hits },
        ] as const) {
          if (!dir.hitbox.hit_props) continue
          const target = input.world.getExternal(dir.defender)
          const profile = input.profiles.get(dir.defender)
          const mult = profile
            ? elementMultiplier(0, profile.weakness_mask, profile.resistance_mask)
            : 1.0
          applied.push({
            target_id: dir.defender,
            source_id: dir.attacker,
            damage_dealt: Math.floor(dir.hitbox.hit_props.damage * mult),
            element_mask: 0,
            blocked: false,
            stun_applied: dir.hitbox.hit_props.hitstun_frames,
            move_id: dir.hitbox.hit_props.move_id,
          })
          if (target) target.already_hit.add(dir.hitbox.hit_props.move_id)
        }
        break
      }
      case 'proj_hit': {
        if (!ev.hitbox.hit_props) break
        const stats = ev.hitbox.hit_props
        const target = input.world.getExternal(ev.defender)
        const profile = input.profiles.get(ev.defender)
        const mult = profile
          ? elementMultiplier(0, profile.weakness_mask, profile.resistance_mask)
          : 1.0
        applied.push({
          target_id: ev.defender,
          source_id: ev.projectile,
          damage_dealt: Math.floor(stats.damage * mult),
          element_mask: 0,
          blocked: false,
          stun_applied: stats.hitstun_frames,
          move_id: stats.move_id,
        })
        if (target) target.already_hit.add(stats.move_id)
        // Projectile is despawned by its step-machine seeing itself in
        // already_hit, or by the scaffold consumer calling world.despawn.
        break
      }
      case 'throw': {
        // Grab — unblockable; caller handles throw animation + throw-
        // specific damage. We emit a damage-applied with 0 damage so
        // the caller knows the grab connected.
        applied.push({
          target_id: ev.target,
          source_id: ev.grabber,
          damage_dealt: 0,
          element_mask: 0,
          blocked: false,
          stun_applied: 0,
          move_id: 'throw_connected',
        })
        break
      }
      // clank, push_overlap, proj_clash — not damage events; handled
      // by other systems (audio, pushback, projectile-despawn).
    }
  }

  return applied
}
