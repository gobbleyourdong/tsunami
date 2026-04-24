/**
 * Unified damage system tests — SF2 × ALttP × SotN synthesis.
 *
 * Scenarios demonstrate that "every attack is an entity" scales across:
 *   - SotN Alucard sword swing (owner-locked entity)
 *   - SotN Hellfire spell (step-machine spawns 3 child entities)
 *   - SotN throwing knife (free-flying entity)
 *   - ALttP rod-pose shared body-animation (fire-rod vs ice-rod instances)
 *   - ALttP tier upgrades (wooden → master → golden sword: same class, different instance)
 *   - ALttP carry-to-projectile handoff (pot pickup → pot throw entity)
 *   - Damage resolver: element × resistance multiplier, already-hit filter
 *
 * See scaffolds/.claude/combat/UNIFIED_DAMAGE_SYSTEM.md
 */

import { describe, it, expect, beforeEach } from 'vitest'
import {
  type AttackEntity, type AttackStats, type BoxPalette, type BoxTimeline,
  type ExternalEntity, type StepMachine, type WeaponClass, type WeaponInstance,
  type EntityDamageProfile, type CollisionEvent,
  CombatWorld, WeaponRegistry, resolveDamage,
  DEFAULT_ATTACK_STATS, Element, elementMultiplier,
} from '../src/combat'

// ─────────────────────────────────────────────────────────────────────
//  helpers
// ─────────────────────────────────────────────────────────────────────

const box = (x: number, y: number, w: number, h: number) => ({ x, y, w, h })

function statsFor(overrides: Partial<AttackStats> = {}): AttackStats {
  return { ...DEFAULT_ATTACK_STATS, ...overrides }
}

function palette(char: string, data: Partial<BoxPalette> & { phit?: Record<number, any>; hit?: Record<number, any>; hit_props?: Record<number, any>; hurt?: Record<number, any> }): BoxPalette {
  const mk = (r: Record<number, any> | undefined) =>
    new Map(Object.entries(r ?? {}).map(([k, v]) => [Number(k), v]))
  return {
    character_id: char,
    hurtboxes:      mk(data.hurt as any),
    hitboxes:       mk(data.hit as any),
    pushboxes:      mk(undefined),
    throwboxes:     mk(undefined),
    throwables:     mk(undefined),
    proj_hitboxes:  mk(data.phit as any),
    proj_hurtboxes: mk(undefined),
    hit_properties: mk(data.hit_props as any),
  }
}

function timeline(anim: string, frames: any[]): BoxTimeline {
  return { animation_id: anim, frame_count: frames.length, frames }
}

// A minimal step-machine that spawns on init, publishes hitbox for N frames, despawns.
function simpleAttackMachine(active_frames: number): StepMachine {
  return (ent, world) => {
    switch (ent.step) {
      case 0:
        ent.step = 1
        ent.step_timer = 0
        break
      case 1:
        if (ent.step_timer >= active_frames) {
          ent.step = 2
          ent.step_timer = 0
        }
        break
      case 2:
        ent.dead = true
        break
    }
  }
}

// Hellfire-style machine: spawn 3 fireballs then self-despawn.
function hellfireMachine(): StepMachine {
  return (ent, world) => {
    switch (ent.step) {
      case 0:
        // Spawn 3 fireballs at angles -30, 0, +30.
        for (const angle of [-30, 0, 30]) {
          world.spawnAttack('hellfire_fireball', ent.owner_id, {
            position: { x: ent.world_position.x, y: ent.world_position.y },
            velocity: { x: Math.cos(angle * Math.PI / 180) * 5, y: 0 },
          })
        }
        ent.step = 1
        break
      case 1:
        ent.dead = true
        break
    }
  }
}

function external(
  id: string, char: string, anim: string, frame: number,
  x: number, y: number, facing: 1 | -1 = 1, hp = 100,
): ExternalEntity {
  return {
    entity_id: id, character_id: char, animation_id: anim, frame_index: frame,
    world_position: { x, y }, facing, hp, already_hit: new Set(),
  }
}

const baseHitProp = (move_id: string, damage = 10) => ({
  damage, hitstun_frames: 16, blockstun_frames: 10,
  hit_level: 'mid' as const, knockdown: false, tier: null, move_id,
})

// ─────────────────────────────────────────────────────────────────────
//  SotN Alucard sword swing — owner-locked attack entity
// ─────────────────────────────────────────────────────────────────────

describe('unified — SotN-style sword swing as owner-locked entity', () => {
  let world: CombatWorld

  beforeEach(() => {
    const registry = new WeaponRegistry()
    // Sword class — owner-locked hitbox published on proj_hitbox channel
    // for 4 frames. Using proj_hitbox channel since attack IS an entity.
    const swordClass: WeaponClass = {
      id: 'sword',
      category: 'sword' as any,
      owner_body_animation_id: 'sword_swing',
      frame_table: timeline('default', [
        { proj_hitboxes: [1] },   // active frames 1-4
        { proj_hitboxes: [1] },
        { proj_hitboxes: [1] },
        { proj_hitboxes: [1] },
      ]),
      step_machine: simpleAttackMachine(3),
      default_lifetime_frames: 10,
    }
    registry.registerClass(swordClass)

    // Master Sword instance — tier-palette-swap demo
    const masterSword: WeaponInstance = {
      id: 'master_sword',
      class_id: 'sword',
      display_name: 'Master Sword',
      stats: statsFor({ attack: 20, element: Element.CUT | Element.HOLY }),
      sprite_tile_id: 2,
      palette_id: 2,
    }
    registry.registerInstance(masterSword)

    // Palettes — sword's proj_hitbox is authored in sword's character palette
    const swordPalette = palette('sword', {
      phit: { 1: box(30, 40, 40, 30) },
      hit_props: { 1: baseHitProp('master_sword_slash', 20) },
    })
    const enemyPalette = palette('moblin', { hurt: { 1: box(0, 40, 40, 80) } })

    world = new CombatWorld({
      registry,
      palettes: new Map([['sword', swordPalette], ['moblin', enemyPalette], ['link_base', palette('link_base', {})]]),
      timelines: new Map([
        ['moblin::idle', timeline('idle', [{ hurtboxes: [1] }])],
        ['link_base::idle', timeline('idle', [{}])],
      ]),
    })
    // Link as external entity at origin
    world.addExternal(external('link', 'link_base', 'idle', 0, 0, 0))
    // Moblin at x=50
    world.addExternal(external('moblin1', 'moblin', 'idle', 0, 50, 0))
  })

  it('spawns a sword attack entity, it tracks owner, hits enemy, despawns', () => {
    const attack = world.spawnAttack('sword', 'link', {
      weapon_instance_id: 'master_sword',
    })
    expect(attack).not.toBeNull()
    expect(world.attackEntityCount()).toBe(1)

    // Tick a few frames — each tick the sword should be at link's
    // position (owner-locked) and publishing hitbox.
    const events: CollisionEvent[] = []
    for (let t = 0; t < 5; t++) {
      events.push(...world.tick())
    }

    // Expect at least one proj_hit during the active frames.
    expect(events.filter(e => e.kind === 'proj_hit').length).toBeGreaterThan(0)
    // After the machine's 3-frame active window + transition, sword
    // is despawned.
    expect(world.attackEntityCount()).toBe(0)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  SotN Hellfire — step-machine spawns 3 child entities
// ─────────────────────────────────────────────────────────────────────

describe('unified — SotN Hellfire spell as fleet-spawner step-machine', () => {
  it('Hellfire init spawns 3 fireball entities', () => {
    const registry = new WeaponRegistry()
    registry.registerClass({
      id: 'hellfire',
      category: 'staff' as any,
      owner_body_animation_id: 'cast_hellfire',
      frame_table: timeline('default', [{}]),
      step_machine: hellfireMachine(),
      default_lifetime_frames: 2,
    })
    registry.registerClass({
      id: 'hellfire_fireball',
      category: 'throw' as any,
      owner_body_animation_id: 'fireball_fly',
      frame_table: timeline('default', [{ proj_hitboxes: [1] }]),
      step_machine: simpleAttackMachine(60),
      default_lifetime_frames: 120,
    })

    const world = new CombatWorld({
      registry,
      palettes: new Map([
        ['hellfire', palette('hellfire', {})],
        ['hellfire_fireball', palette('hellfire_fireball', {
          phit: { 1: box(0, 0, 16, 16) },
          hit_props: { 1: baseHitProp('hellfire_fireball', 30) },
        })],
      ]),
    })
    world.addExternal(external('alucard', 'alucard', 'idle', 0, 0, 0))

    const hellfire = world.spawnAttack('hellfire', 'alucard')
    expect(hellfire).not.toBeNull()
    expect(world.attackEntityCount()).toBe(1)

    world.tick()
    // After first tick, hellfire has spawned 3 fireballs + transitioned
    // to step 1. Total attack entities: 1 (hellfire, dying) + 3 fireballs.
    expect(world.attackEntityCount()).toBe(4)

    world.tick()
    // Hellfire self-destructs on step 1 → step 2 transition.
    // 3 fireballs remain (they have 120-frame lifetime).
    expect(world.attackEntityCount()).toBe(3)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  SotN throwing knife — free-flying entity with velocity
// ─────────────────────────────────────────────────────────────────────

describe('unified — SotN throwing knife as free-flying entity', () => {
  it('knife has velocity, moves each tick, hits distant target', () => {
    const registry = new WeaponRegistry()
    registry.registerClass({
      id: 'knife',
      category: 'throw' as any,
      owner_body_animation_id: 'throw',
      frame_table: timeline('default', [{ proj_hitboxes: [1] }]),
      step_machine: simpleAttackMachine(60),
      default_lifetime_frames: 120,
    })
    const world = new CombatWorld({
      registry,
      palettes: new Map([
        ['knife', palette('knife', {
          phit: { 1: box(0, 0, 12, 4) },
          hit_props: { 1: baseHitProp('knife', 8) },
        })],
        ['target', palette('target', { hurt: { 1: box(0, 0, 20, 40) } })],
        ['alucard', palette('alucard', {})],
      ]),
      timelines: new Map([
        ['target::idle', timeline('idle', [{ hurtboxes: [1] }])],
        ['alucard::idle', timeline('idle', [{}])],
      ]),
    })
    world.addExternal(external('alucard', 'alucard', 'idle', 0, 0, 0))
    world.addExternal(external('enemy1', 'target', 'idle', 0, 50, 0))

    const knife = world.spawnAttack('knife', 'alucard', {
      velocity: { x: 10, y: 0 },    // flies right at 10 px/tick
      owner_locked: false,
    })
    expect(knife).not.toBeNull()
    const startX = knife!.world_position.x

    const eventsAcrossTicks: CollisionEvent[] = []
    for (let t = 0; t < 8; t++) {
      eventsAcrossTicks.push(...world.tick())
    }
    // Knife should have moved 80 px right (10 × 8 ticks), crossed
    // the target at x=50 around tick 5, and emitted a proj_hit.
    expect(eventsAcrossTicks.some(e => e.kind === 'proj_hit')).toBe(true)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  ALttP rod-pose — fire-rod vs ice-rod share class, differ in stats
// ─────────────────────────────────────────────────────────────────────

describe('unified — ALttP rod-pose shared class, different instances', () => {
  it('fire-rod and ice-rod both use `rod` class but have different element bitmasks', () => {
    const registry = new WeaponRegistry()
    registry.registerClass({
      id: 'rod',
      category: 'staff' as any,
      owner_body_animation_id: 'rod_point',
      frame_table: timeline('default', [{ proj_hitboxes: [1] }]),
      step_machine: simpleAttackMachine(30),
      default_lifetime_frames: 60,
    })
    registry.registerInstance({
      id: 'fire_rod',
      class_id: 'rod',
      display_name: 'Fire Rod',
      stats: statsFor({ attack: 16, element: Element.FIRE, mp_cost: 4 }),
      sprite_tile_id: 10,
      palette_id: 5,
    })
    registry.registerInstance({
      id: 'ice_rod',
      class_id: 'rod',
      display_name: 'Ice Rod',
      stats: statsFor({ attack: 20, element: Element.ICE, mp_cost: 4 }),
      sprite_tile_id: 11,
      palette_id: 6,
    })

    expect(registry.instancesOfClass('rod')).toHaveLength(2)
    expect(registry.getInstance('fire_rod')!.stats.element).toBe(Element.FIRE)
    expect(registry.getInstance('ice_rod')!.stats.element).toBe(Element.ICE)
    // Both share the class's body animation.
    const cls = registry.getClass('rod')!
    expect(cls.owner_body_animation_id).toBe('rod_point')
  })
})

// ─────────────────────────────────────────────────────────────────────
//  ALttP sword tier progression — wooden → master → golden
// ─────────────────────────────────────────────────────────────────────

describe('unified — ALttP sword tier palette-swap progression', () => {
  it('four sword tiers share class, differ only in palette + stats', () => {
    const registry = new WeaponRegistry()
    registry.registerClass({
      id: 'sword',
      category: 'sword' as any,
      owner_body_animation_id: 'sword_swing',
      frame_table: timeline('default', [{ proj_hitboxes: [1] }]),
      step_machine: simpleAttackMachine(4),
      default_lifetime_frames: 10,
    })

    const tiers = [
      { id: 'wooden_sword', attack: 5, palette_id: 1 },
      { id: 'master_sword', attack: 10, palette_id: 2 },
      { id: 'tempered_sword', attack: 20, palette_id: 3 },
      { id: 'golden_sword', attack: 40, palette_id: 4 },
    ]
    for (const t of tiers) {
      registry.registerInstance({
        id: t.id, class_id: 'sword', display_name: t.id,
        stats: statsFor({ attack: t.attack, element: Element.CUT }),
        sprite_tile_id: 1,     // same tile across tiers — palette differs
        palette_id: t.palette_id,
      })
    }
    expect(registry.instancesOfClass('sword')).toHaveLength(4)
    // Same tile ID everywhere — the ALttP palette-swap property.
    const all = registry.instancesOfClass('sword')
    for (const inst of all) expect(inst.sprite_tile_id).toBe(1)
    // Unique palette IDs per tier.
    const pids = all.map(i => i.palette_id)
    expect(new Set(pids).size).toBe(4)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  Damage resolver — element × resistance multiplier
// ─────────────────────────────────────────────────────────────────────

describe('unified — elemental resistance multiplier', () => {
  it('fire attack × fire resistance = 0.5× damage', () => {
    const mult = elementMultiplier(Element.FIRE, 0, Element.FIRE)
    expect(mult).toBe(0.5)
  })

  it('fire attack × fire weakness = 2× damage', () => {
    const mult = elementMultiplier(Element.FIRE, Element.FIRE, 0)
    expect(mult).toBe(2.0)
  })

  it('cut+fire attack × fire-weakness = 2× (only fire bit is weak)', () => {
    const mult = elementMultiplier(
      Element.CUT | Element.FIRE,
      Element.FIRE, 0,
    )
    expect(mult).toBe(2.0)  // only FIRE is weakness
  })

  it('fire+curse attack × fire-weakness+curse-weakness = 4×', () => {
    const mult = elementMultiplier(
      Element.FIRE | Element.CURSE,
      Element.FIRE | Element.CURSE, 0,
    )
    expect(mult).toBe(4.0)  // both bits hit weakness → multiply
  })

  it('neutral damage = 1.0×', () => {
    const mult = elementMultiplier(Element.CUT, 0, 0)
    expect(mult).toBe(1.0)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  Damage resolver — applied records from collision events
// ─────────────────────────────────────────────────────────────────────

describe('unified — damage resolver consuming clean_hit', () => {
  it('emits DamageApplied with stun frames on clean_hit', () => {
    const registry = new WeaponRegistry()
    const world = new CombatWorld({ registry, palettes: new Map() })
    world.addExternal(external('target', 'tgt', 'idle', 0, 100, 0, 1, 100))

    const events: CollisionEvent[] = [{
      kind: 'clean_hit',
      attacker: 'player',
      defender: 'target',
      hitbox: {
        owner: 'player', channel: 'hitbox' as any, palette_id: 1,
        x_min: 90, x_max: 110, y_min: 0, y_max: 20,
        hit_props: baseHitProp('test_slash', 25),
      },
    }]

    const profiles = new Map<string, EntityDamageProfile>([
      ['target', {
        weakness_mask: 0, resistance_mask: 0,
        is_blocking: false, hitstun_frames_remaining: 0,
      }],
    ])

    const damage = resolveDamage({ events, world, profiles })
    expect(damage).toHaveLength(1)
    expect(damage[0].damage_dealt).toBe(25)
    expect(damage[0].stun_applied).toBe(16)
    // already-hit tracker populated so subsequent re-hit is filtered.
    expect(world.getExternal('target')!.already_hit.has('test_slash')).toBe(true)
  })
})
