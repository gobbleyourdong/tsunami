// Weapon-class registry + canonical 7-class taxonomy.
//
// From SotN's ItemCategory enum (after stripping consumables): 7 combat
// classes that bind weapon-instances to shared body animations + step
// machines. The ALttP rod-pose pattern scaled up.
//
// A scaffold typically picks 3-5 classes from this set. Platform-fighter
// scaffolds use {sword, fist, throw} mostly; metroidvania-shinobi uses
// {sword, throw, fist}; JRPG uses {sword, rod, bow}.

import type { StepMachine } from './attack_entity'
import type { BoxTimeline } from './box_types'

/**
 * The 7 canonical weapon classes (SotN-derived). Each class binds:
 * - A body animation on the owner (swing vs thrust vs shoot vs cast)
 * - A step-machine for the attack entity
 * - A frame-indexed box timeline (hitbox refs per anim frame)
 */
export const WeaponCategory = {
  SHORT_SWORD: 'short_sword',   // daggers, shortswords — fast, short reach
  SWORD:       'sword',          // standard sword — balanced
  TWO_HAND:    'two_hand',       // great-sword, battle-axe — slow, heavy
  FIST:        'fist',           // gauntlets, claws — very fast, very short
  CLUB:        'club',            // maces, hammers, rods — strike damage type
  THROW:       'throw',           // thrown projectiles (knife, shuriken, axe)
  SHIELD:      'shield',          // blocking primary, shield-bash secondary
  // Non-SotN but useful:
  BOW:         'bow',             // ranged physical (Zelda lineage)
  STAFF:       'staff',           // caster-weapons (JRPG lineage)
  SPEAR:       'spear',           // long-reach thrust (FF Dragoon lineage)
} as const

export type WeaponCategoryKey = typeof WeaponCategory[keyof typeof WeaponCategory]

/**
 * Class-level data. Heavy to define (animation + frame table + step
 * machine) — typically 7-10 per scaffold.
 */
export interface WeaponClass {
  /** Class identifier (e.g. 'sword', 'rod', 'bow'). */
  readonly id: string
  /** Category bucket — maps to owner body animation. */
  readonly category: WeaponCategoryKey
  /** Body animation the OWNER plays while this weapon is active.
   *  Rod-pose example: fire_rod/ice_rod/somaria/byrna all reference
   *  `rod_point` here. */
  readonly owner_body_animation_id: string
  /** The attack entity's own animation + frame-indexed box refs. */
  readonly frame_table: BoxTimeline
  /** The step-machine function advancing attack entities of this class. */
  readonly step_machine: StepMachine
  /** Default lifetime frames for this class's entities. -1 = follow
   *  anim-complete, N = hard deadline. */
  readonly default_lifetime_frames: number
}

/**
 * Per-instance data. Light — typically 50-200 per scaffold.
 * Instance differs from class by stats + sprite tile + palette.
 * Tier upgrades (wooden/master/tempered/golden sword) are sibling
 * instances of the same class.
 */
import type { AttackStats } from './equipment'

export interface WeaponInstance {
  readonly id: string             // 'wooden_sword' | 'master_sword'
  readonly class_id: string       // 'sword' — foreign-key into WeaponClass registry
  readonly display_name: string
  readonly stats: AttackStats
  /** Sprite tile ID in the owner's weapon-tile atlas. */
  readonly sprite_tile_id: number
  /** CGRAM palette slot (ALttP tier mechanic). Master Sword vs Golden
   *  Sword differ ONLY in this field + stats. */
  readonly palette_id: number
  /** Optional icon sprite for inventory UI. */
  readonly icon_id?: number
}

/**
 * Registry of weapon classes + instances. Scaffolds declare their
 * registry at startup; runtime looks up by id.
 */
export class WeaponRegistry {
  private classes = new Map<string, WeaponClass>()
  private instances = new Map<string, WeaponInstance>()

  registerClass(cls: WeaponClass): void {
    if (this.classes.has(cls.id)) {
      throw new Error(`Duplicate weapon class: ${cls.id}`)
    }
    this.classes.set(cls.id, cls)
  }

  registerInstance(inst: WeaponInstance): void {
    if (!this.classes.has(inst.class_id)) {
      throw new Error(`Weapon instance "${inst.id}" references unknown class "${inst.class_id}"`)
    }
    if (this.instances.has(inst.id)) {
      throw new Error(`Duplicate weapon instance: ${inst.id}`)
    }
    this.instances.set(inst.id, inst)
  }

  getClass(id: string): WeaponClass | undefined {
    return this.classes.get(id)
  }

  getInstance(id: string): WeaponInstance | undefined {
    return this.instances.get(id)
  }

  /** List all instances of a given class — useful for shop UIs + debug. */
  instancesOfClass(class_id: string): WeaponInstance[] {
    return [...this.instances.values()].filter(i => i.class_id === class_id)
  }

  /** Full class list — useful for scaffold content audits. */
  allClasses(): WeaponClass[] {
    return [...this.classes.values()]
  }
}
