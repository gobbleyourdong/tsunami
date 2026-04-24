// AttackEntity + step-machine runner.
//
// SotN's architectural core: every damage event is an Entity with a
// position, stepped lifetime, AABB, and stats-row. Sword swings,
// projectiles, spells, familiar attacks — all the same shape.
//
// See UNIFIED_DAMAGE_SYSTEM.md §the-core-recipe.

import type { CombatEntityState } from './box_types'
import type { AttackStats } from './equipment'

/**
 * The unified attack abstraction. Extends `CombatEntityState` (which
 * already carries entity_id, character_id, animation_id, frame_index,
 * position, facing, hp, already_hit) with step-machine state + stats.
 *
 * An AttackEntity IS a CombatEntityState — the collision resolver
 * already handles it via the existing channel loops. No new channel
 * needed.
 */
export interface AttackEntity extends CombatEntityState {
  /** Step index within the owner's step-machine. init=0, active=1,
   *  recovery=2, despawn=3 by convention but each machine defines its
   *  own sequence. */
  step: number
  /** Frame counter within the current step. Reset on step transition. */
  step_timer: number
  /** Owning entity — who spawned this. Used to look up owner position
   *  for owner-locked entities (sword swings track player). */
  readonly owner_id: string
  /** Weapon/spell class identifier — dispatches into step_machine
   *  registry. */
  readonly class_id: string
  /** Weapon instance identifier — picks stats row and sprite. */
  readonly weapon_instance_id?: string
  /** Stats row. Damage / element / stun / mp / etc. */
  readonly stats: AttackStats
  /** For free-flying entities (projectiles), independent velocity. For
   *  owner-locked entities (sword swings), velocity is unused — position
   *  is copied from owner each tick. */
  velocity: { x: number; y: number }
  /** True if this entity's position should track its owner each tick.
   *  Set by step-machine init for sword-swing-style attacks. False for
   *  projectiles once they leave the owner's hand. */
  owner_locked: boolean
  /** Lifetime frames remaining before forced despawn. -1 = unlimited. */
  lifetime_frames: number
  /** Set to true by step-machine when ready to be garbage-collected.
   *  CombatWorld.tick will despawn on next pass. */
  dead: boolean
  /** Per-machine scratch state. Step-machines store their own locals
   *  here when they need to persist across ticks. */
  scratch: Record<string, unknown>
}

/**
 * A step-machine is a function that advances one AttackEntity by one
 * tick. Reads/mutates the entity's step/step_timer/position/velocity/
 * dead fields. May call world.spawnAttack() to spawn child entities
 * (Hellfire spawning 3 fireballs). Must not mutate other entities
 * directly — emit collision events instead via the resolver.
 */
export type StepMachine = (ent: AttackEntity, world: CombatWorldHandle) => void

/**
 * Minimal world handle given to step-machines. Keeps the machine
 * decoupled from the full CombatWorld class (which depends on more).
 */
export interface CombatWorldHandle {
  /** Current tick number (monotonic). */
  readonly tick_count: number
  /** Look up an entity's position — used for owner-tracking. */
  getPosition(entity_id: string): { x: number; y: number } | null
  /** Look up an entity's facing direction. */
  getFacing(entity_id: string): 1 | -1
  /** Spawn a child attack-entity (e.g. Hellfire spawns 3 fireballs). */
  spawnAttack(class_id: string, owner_id: string, params: SpawnAttackParams): AttackEntity | null
  /** Despawn an entity by id. Idempotent. */
  despawn(entity_id: string): void
}

/**
 * Parameters for `spawnAttack`. Most fields optional; defaults come
 * from the class registry.
 */
export interface SpawnAttackParams {
  /** Weapon/attack instance ID — picks stats row. If omitted, class
   *  default stats are used. */
  readonly weapon_instance_id?: string
  /** Starting position. Default = owner's position. */
  readonly position?: { x: number; y: number }
  /** Starting velocity. Default = {0,0} (owner-locked). */
  readonly velocity?: { x: number; y: number }
  /** Override owner_locked flag. Default: true unless velocity provided. */
  readonly owner_locked?: boolean
  /** Lifetime frames. Default: class-provided. */
  readonly lifetime_frames?: number
  /** Free-form angle or other params the step-machine reads from
   *  scratch on init. */
  readonly extra?: Record<string, unknown>
}

/**
 * Advance one AttackEntity by one tick. Calls the class's step-machine,
 * increments step_timer, applies lifetime-countdown, handles
 * owner-tracking.
 */
export function tickAttackEntity(
  ent: AttackEntity,
  step_machine: StepMachine,
  world: CombatWorldHandle,
): void {
  if (ent.dead) return

  // Owner-tracking: copy owner's position each tick for swing-style.
  if (ent.owner_locked) {
    const ownerPos = world.getPosition(ent.owner_id)
    if (ownerPos) {
      (ent as unknown as { world_position: { x: number; y: number } })
        .world_position = { x: ownerPos.x, y: ownerPos.y }
      const ownerFacing = world.getFacing(ent.owner_id)
      ;(ent as unknown as { facing: 1 | -1 }).facing = ownerFacing
    }
  } else {
    // Free-flying: integrate velocity.
    (ent as unknown as { world_position: { x: number; y: number } })
      .world_position = {
        x: ent.world_position.x + ent.velocity.x,
        y: ent.world_position.y + ent.velocity.y,
      }
  }

  // Lifetime countdown.
  if (ent.lifetime_frames > 0) {
    ent.lifetime_frames -= 1
    if (ent.lifetime_frames === 0) {
      ent.dead = true
      return
    }
  }

  // Run the class's step-machine.
  step_machine(ent, world)

  // Advance step timer (step-machine may reset it on transition).
  ent.step_timer += 1
}

/**
 * Build an AttackEntity. Called by CombatWorld.spawnAttack. Step
 * machines then initialize it in step 0.
 */
export function makeAttackEntity(
  entity_id: string,
  class_id: string,
  owner_id: string,
  position: { x: number; y: number },
  facing: 1 | -1,
  stats: AttackStats,
  opts: Partial<SpawnAttackParams> = {},
): AttackEntity {
  const velocity = opts.velocity ?? { x: 0, y: 0 }
  const owner_locked = opts.owner_locked ?? (velocity.x === 0 && velocity.y === 0)
  return {
    entity_id,
    character_id: class_id,       // attack-entity character is its class for palette lookup
    animation_id: 'default',
    frame_index: 0,
    world_position: position,
    facing,
    hp: 1,                         // attacks have 1 HP so they despawn on proj-swat
    already_hit: new Set(),
    step: 0,
    step_timer: 0,
    owner_id,
    class_id,
    weapon_instance_id: opts.weapon_instance_id,
    stats,
    velocity,
    owner_locked,
    lifetime_frames: opts.lifetime_frames ?? -1,
    dead: false,
    scratch: { ...opts.extra },
  }
}
