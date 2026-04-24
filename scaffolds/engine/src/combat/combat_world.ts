// CombatWorld — spawn / despawn / tick loop for AttackEntities.
//
// Wraps the existing `resolveCombat` box-level resolver with an entity-
// lifecycle layer. Per-tick order:
//   1. Tick step-machines for all AttackEntities → mutate positions +
//      spawn children + mark dead.
//   2. Garbage-collect dead entities.
//   3. Call resolveCombat with surviving entities → emit CollisionEvent[].
//   4. (Consumer) damage_resolver + pushback_solver read the events.

import { type AttackEntity, type CombatWorldHandle, type SpawnAttackParams,
         makeAttackEntity, tickAttackEntity } from './attack_entity'
import type { BoxPalette, BoxTimeline } from './box_types'
import { type CollisionEvent, resolveCombat } from './collision_resolver'
import { DEFAULT_ATTACK_STATS } from './equipment'
import type { WeaponRegistry } from './weapon_class'

export interface CombatWorldConfig {
  readonly registry: WeaponRegistry
  /** Character-palette lookup by character_id — used by resolveCombat. */
  readonly palettes: ReadonlyMap<string, BoxPalette>
  /** External-entity timelines keyed by `${character_id}::${animation_id}`.
   *  For non-attack entities (players, enemies, NPCs). Attack-entity
   *  timelines come from the weapon-class registry automatically. */
  readonly timelines?: ReadonlyMap<string, BoxTimeline>
}

/**
 * Non-attack combat entities (player, enemies, familiars). Scaffold
 * code pushes these in + updates their state each frame. CombatWorld's
 * tick loop combines them with attack-entities before box-resolution.
 */
export interface ExternalEntity {
  readonly entity_id: string
  readonly character_id: string
  readonly animation_id: string
  frame_index: number
  world_position: { x: number; y: number }
  facing: 1 | -1
  hp: number
  /** Mutable — damage-resolver clears this after applying hits. */
  already_hit: Set<string>
}

export class CombatWorld implements CombatWorldHandle {
  tick_count = 0
  private readonly attack_entities = new Map<string, AttackEntity>()
  private readonly external_entities = new Map<string, ExternalEntity>()
  private next_entity_id = 1
  private readonly pending_despawn = new Set<string>()

  constructor(private readonly config: CombatWorldConfig) {}

  // ─── CombatWorldHandle interface ───

  getPosition(entity_id: string): { x: number; y: number } | null {
    const a = this.attack_entities.get(entity_id)
    if (a) return a.world_position
    const e = this.external_entities.get(entity_id)
    if (e) return e.world_position
    return null
  }

  getFacing(entity_id: string): 1 | -1 {
    const a = this.attack_entities.get(entity_id)
    if (a) return a.facing
    const e = this.external_entities.get(entity_id)
    if (e) return e.facing
    return 1
  }

  spawnAttack(class_id: string, owner_id: string, params: SpawnAttackParams = {}): AttackEntity | null {
    const cls = this.config.registry.getClass(class_id)
    if (!cls) return null

    const owner_pos = this.getPosition(owner_id) ?? { x: 0, y: 0 }
    const owner_facing = this.getFacing(owner_id)

    // Resolve stats: per-instance override, else default.
    let stats = DEFAULT_ATTACK_STATS
    if (params.weapon_instance_id) {
      const inst = this.config.registry.getInstance(params.weapon_instance_id)
      if (inst) stats = inst.stats
    }

    const id = `attack_${this.next_entity_id++}`
    const ent = makeAttackEntity(
      id, class_id, owner_id,
      params.position ?? { ...owner_pos },
      owner_facing,
      stats,
      params,
    )
    if (params.lifetime_frames === undefined) {
      ent.lifetime_frames = cls.default_lifetime_frames
    }
    this.attack_entities.set(id, ent)
    return ent
  }

  despawn(entity_id: string): void {
    this.pending_despawn.add(entity_id)
  }

  // ─── external-entity management ───

  addExternal(e: ExternalEntity): void {
    this.external_entities.set(e.entity_id, e)
  }

  removeExternal(entity_id: string): void {
    this.external_entities.delete(entity_id)
  }

  getExternal(entity_id: string): ExternalEntity | undefined {
    return this.external_entities.get(entity_id)
  }

  // ─── tick loop ───

  tick(): CollisionEvent[] {
    this.tick_count += 1

    // 1. Advance step-machines for all attack entities.
    for (const ent of this.attack_entities.values()) {
      if (ent.dead) continue
      const cls = this.config.registry.getClass(ent.class_id)
      if (!cls) { ent.dead = true; continue }
      tickAttackEntity(ent, cls.step_machine, this)
    }

    // 2. Garbage-collect dead or pending-despawn.
    for (const id of this.pending_despawn) this.attack_entities.delete(id)
    this.pending_despawn.clear()
    for (const [id, ent] of this.attack_entities) {
      if (ent.dead) this.attack_entities.delete(id)
    }

    // 3. Resolve collisions.
    const all_entities = [
      ...this.attack_entities.values(),
      ...this.external_entities.values(),
    ]

    // Timeline map — each weapon-class registers its frame_table + any
    // external-entity timelines from config.
    const timelines = new Map<string, BoxTimeline>()
    for (const cls of this.config.registry.allClasses()) {
      timelines.set(`${cls.id}::default`, cls.frame_table)
      timelines.set(`${cls.id}::${cls.frame_table.animation_id}`, cls.frame_table)
    }
    if (this.config.timelines) {
      for (const [k, v] of this.config.timelines) timelines.set(k, v)
    }

    return resolveCombat({
      entities: all_entities,
      palettes: this.config.palettes,
      timelines,
    })
  }

  // ─── diagnostics ───

  attackEntityCount(): number {
    return this.attack_entities.size
  }

  externalEntityCount(): number {
    return this.external_entities.size
  }

  listAttackEntities(): ReadonlyArray<AttackEntity> {
    return [...this.attack_entities.values()]
  }
}
