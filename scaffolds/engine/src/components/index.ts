/**
 * Component vocabulary — Layer 1 of the gamedev framework.
 *
 * Canonical set of game-object components. Genre scaffolds attach
 * these to EntityDef.properties and mechanics subscribe via the
 * existing system classes.
 *
 * Design choices:
 * - Existing Health/Inventory/Score/Checkpoint SYSTEMS stay — this module
 *   adds the TYPE-level component shape + thin re-export.
 * - Missing components (Tags, Stats, Team, Faction, Mana, Hitbox/Hurtbox,
 *   Spellbook, Cooldown, Controller) get full definitions here.
 * - No breaking changes to the existing Game/SceneBuilder flow. Attach
 *   components via properties: { Health: {...}, Mana: {...}, ... }.
 */

// Re-export existing system-level components (Health, Inventory, Score, Checkpoint).
// Callers can import from @engine/components OR @engine/systems — both work.
export {
  HealthSystem,
  type DamageType,
  type DamageEvent,
  Inventory,
  type ItemDef,
  type InventorySlot,
  CheckpointSystem,
  MemorySaveBackend,
  localStorageBackend,
  type SaveData,
  type SaveBackend,
  ScoreSystem,
} from '../systems'

// ─── Component shapes (data-only; attach to EntityDef.properties) ───

/** Health state for an entity. Attaches to properties.Health. */
export interface HealthComponent {
  current: number
  max: number
  /** Invulnerability frames remaining after the last hit. */
  invuln_frames?: number
  /** Subscribable damage types (filters for resistance/weakness). */
  resistances?: Record<string, number>  // damage_type → multiplier (0 = immune, 2 = double)
}

/** Mana/energy pool. Resources like MP, stamina, ammo share this shape. */
export interface ManaComponent {
  current: number
  max: number
  regen_rate?: number  // units per second
}

/** RPG-style stats. Open map — genres pick which keys matter. */
export interface StatsComponent {
  /** e.g. {str: 10, dex: 8, int: 14} — genre-dependent keys. */
  [stat: string]: number
}

/** Queryable string set. Mechanics filter by tags (e.g. tag_requirement). */
export type TagsComponent = string[]

/** Team / faction affiliation. */
export interface TeamComponent {
  team_id: number
  faction?: string
}

/** Combat hitbox (active = can deal damage this frame). */
export interface HitboxComponent {
  /** AABB offset from entity position. */
  offset_x: number
  offset_y: number
  offset_z?: number
  width: number
  height: number
  depth?: number
  active: boolean
  /** Damage this hitbox inflicts on overlap. */
  damage?: number
  /** Damage type (for resistance lookup in HealthComponent.resistances). */
  damage_type?: string
  /** Entity id of the owner — HitboxSystem won't self-damage. */
  owner_id?: string
}

/** Combat hurtbox (what CAN be damaged). Inverse of hitbox. */
export interface HurtboxComponent {
  offset_x: number
  offset_y: number
  offset_z?: number
  width: number
  height: number
  depth?: number
  active: boolean
}

/** Spell/ability loadout. References SpellCasting mechanic instances. */
export interface SpellbookComponent {
  /** List of spell ids the entity can cast. */
  spells: string[]
  /** Currently-selected spell (for hotkey cycling). */
  active_spell?: string
}

/** Cooldown state for an action. */
export interface CooldownComponent {
  /** Map of action_id → seconds remaining. */
  [action_id: string]: number
}

/** Input binding. Which "channel" this entity listens to. */
export interface ControllerComponent {
  /** 'player1' | 'player2' | 'ai' | 'network' | <custom channel> */
  channel: string
  /** Optional input-map profile name. */
  profile?: string
}

/** Position component — wraps Vec3 as attachable data. */
export interface PositionComponent {
  x: number
  y: number
  z?: number
  facing?: number  // radians, 0 = +X
}

/** Velocity component. */
export interface VelocityComponent {
  vx: number
  vy: number
  vz?: number
  max_speed?: number
}

/** Sprite reference — lookup into public/sprites/<id>. */
export interface SpriteComponent {
  id: string
  anchor?: 'center' | 'top-left' | 'bottom-center'
  flip_x?: boolean
  flip_y?: boolean
  layer?: number  // draw-order tiebreaker
}

/** Animation state. */
export interface AnimatorComponent {
  current_animation: string
  frame: number
  timer: number
  loop: boolean
}

/** Score state — individual contribution. */
export interface ScoreComponent {
  current: number
  multiplier?: number
  /** Team id if the score contributes to a team total. */
  team_id?: number
}

// ─── Helpers ───────────────────────────────────────────────────────

/** Component-bag shape — what gets attached to EntityDef.properties. */
export interface ComponentBag {
  Health?: HealthComponent
  Mana?: ManaComponent
  Stats?: StatsComponent
  Tags?: TagsComponent
  Team?: TeamComponent
  Hitbox?: HitboxComponent
  Hurtbox?: HurtboxComponent
  Spellbook?: SpellbookComponent
  Cooldown?: CooldownComponent
  Controller?: ControllerComponent
  Position?: PositionComponent
  Velocity?: VelocityComponent
  Sprite?: SpriteComponent
  Animator?: AnimatorComponent
  Score?: ScoreComponent
  // Open-ended: unknown component kinds pass through.
  [custom: string]: unknown
}

/** Get a typed component from an EntityDef's properties bag. */
export function getComponent<K extends keyof ComponentBag>(
  entity: { properties?: Record<string, unknown> },
  kind: K,
): ComponentBag[K] | undefined {
  return entity.properties?.[kind as string] as ComponentBag[K] | undefined
}

/** Set/update a component on an EntityDef. */
export function setComponent<K extends keyof ComponentBag>(
  entity: { properties?: Record<string, unknown> },
  kind: K,
  value: ComponentBag[K],
): void {
  if (!entity.properties) entity.properties = {}
  entity.properties[kind as string] = value
}

/** Check if an entity has a component. */
export function hasComponent(
  entity: { properties?: Record<string, unknown> },
  kind: keyof ComponentBag,
): boolean {
  return entity.properties?.[kind as string] !== undefined
}

/** List all component kinds present on an entity. */
export function listComponents(
  entity: { properties?: Record<string, unknown> },
): string[] {
  return Object.keys(entity.properties ?? {})
}
