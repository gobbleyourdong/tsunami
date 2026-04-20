/**
 * Phase 1 smoke tests — component vocabulary.
 *
 * Verifies:
 * - The barrel exports resolve (no circular-import / missing-export at load time).
 * - Component-bag helpers (getComponent/setComponent/hasComponent/listComponents) work.
 * - TypeScript shape of ComponentBag matches what genre scaffolds will produce.
 * - Existing systems (HealthSystem/Inventory) re-export through @engine/components.
 */

import { describe, it, expect } from 'vitest'
import {
  getComponent,
  setComponent,
  hasComponent,
  listComponents,
  HealthSystem,
  Inventory,
  type HealthComponent,
  type ManaComponent,
  type TagsComponent,
  type TeamComponent,
  type HitboxComponent,
  type LevelComponent,
  type CurrencyComponent,
  type StatusEffectComponent,
  type ComponentBag,
} from '../src/components'

describe('Phase 1 — components barrel', () => {
  it('re-exports HealthSystem from systems/', () => {
    expect(typeof HealthSystem).toBe('function')  // class constructor
  })

  it('re-exports Inventory from systems/', () => {
    expect(typeof Inventory).toBe('function')
  })

  it('setComponent attaches to properties', () => {
    const entity: { properties?: Record<string, unknown> } = {}
    const health: HealthComponent = { current: 100, max: 100 }
    setComponent(entity, 'Health', health)
    expect(entity.properties?.Health).toEqual(health)
  })

  it('getComponent retrieves typed component', () => {
    const entity = { properties: { Mana: { current: 50, max: 100 } as ManaComponent } }
    const mana = getComponent(entity, 'Mana')
    expect(mana?.current).toBe(50)
    expect(mana?.max).toBe(100)
  })

  it('getComponent returns undefined when component missing', () => {
    const entity = { properties: {} }
    expect(getComponent(entity, 'Health')).toBeUndefined()
  })

  it('hasComponent distinguishes present vs absent', () => {
    const tags: TagsComponent = ['player', 'invulnerable']
    const entity = { properties: { Tags: tags } }
    expect(hasComponent(entity, 'Tags')).toBe(true)
    expect(hasComponent(entity, 'Health')).toBe(false)
  })

  it('listComponents enumerates attached kinds', () => {
    const entity = {
      properties: {
        Health: { current: 100, max: 100 },
        Mana: { current: 50, max: 50 },
        Tags: ['enemy'],
      },
    }
    const kinds = listComponents(entity)
    expect(kinds.sort()).toEqual(['Health', 'Mana', 'Tags'])
  })

  it('handles entities without properties bag', () => {
    const entity: { properties?: Record<string, unknown> } = {}
    expect(getComponent(entity, 'Health')).toBeUndefined()
    expect(hasComponent(entity, 'Health')).toBe(false)
    expect(listComponents(entity)).toEqual([])
    // Setting should initialize
    setComponent(entity, 'Health', { current: 1, max: 1 })
    expect(entity.properties?.Health).toBeDefined()
  })

  it('ComponentBag accepts all canonical component shapes', () => {
    const bag: ComponentBag = {
      Health: { current: 100, max: 100, invuln_frames: 0 },
      Mana: { current: 50, max: 100, regen_rate: 5 },
      Stats: { str: 10, dex: 8, int: 14 },
      Tags: ['player', 'hero'],
      Team: { team_id: 1, faction: 'heroes' },
      Hitbox: {
        offset_x: 0, offset_y: 0, width: 32, height: 48,
        active: false, damage: 10, damage_type: 'slash',
      },
      Controller: { channel: 'player1' },
      Position: { x: 100, y: 200, facing: 0 },
      Velocity: { vx: 0, vy: 0, max_speed: 180 },
      Sprite: { id: 'link_front', anchor: 'center' },
      Spellbook: { spells: ['fireball', 'heal'] },
      Cooldown: { fireball: 0, heal: 3.5 },
      Score: { current: 0, multiplier: 1 },
    }
    // Just verify TypeScript accepts this shape (compile-time check).
    expect(bag.Health?.current).toBe(100)
    expect(bag.Stats?.str).toBe(10)
    expect(bag.Tags).toContain('player')
    expect(bag.Team?.team_id).toBe(1)
    expect(bag.Hitbox?.active).toBe(false)
  })

  it('custom component keys pass through', () => {
    const bag: ComponentBag = {
      Health: { current: 10, max: 10 },
      CustomGenreThing: { anything: 'goes here' },  // open-ended
    } as ComponentBag
    expect(bag.CustomGenreThing).toBeDefined()
  })
})

describe('Phase 1 — component shapes carry expected fields', () => {
  it('HealthComponent supports resistances map', () => {
    const h: HealthComponent = {
      current: 100, max: 100,
      resistances: { fire: 0.5, ice: 2.0 },  // half damage from fire, double from ice
    }
    expect(h.resistances?.fire).toBe(0.5)
  })

  it('HitboxComponent has active flag for frame-based combat', () => {
    const box: HitboxComponent = {
      offset_x: 16, offset_y: 0, width: 40, height: 30,
      active: true, damage: 25, damage_type: 'strike',
      owner_id: 'player',
    }
    expect(box.active).toBe(true)
    expect(box.owner_id).toBe('player')
  })

  it('TeamComponent with faction for PvE factions', () => {
    const t: TeamComponent = { team_id: 2, faction: 'moblins' }
    expect(t.faction).toBe('moblins')
  })

  it('LevelComponent — RPG progression (added via JOB-B)', () => {
    const l: LevelComponent = {
      current: 12, xp: 3400, xp_to_next: 4000, class: 'mage',
    }
    expect(l.current).toBe(12)
    expect(l.class).toBe('mage')
  })

  it('CurrencyComponent — multi-currency map (JRPG has gold + rupees)', () => {
    const c: CurrencyComponent = { gold: 150, rupees: 42 }
    expect(c.gold).toBe(150)
    expect(c.rupees).toBe(42)
  })

  it('StatusEffectComponent — stack of active buffs/debuffs', () => {
    const s: StatusEffectComponent = {
      active: [
        { id: 'poison', remaining: 4.5, magnitude: 10, source: 'boss_a' },
        { id: 'haste', remaining: 10.0, magnitude: 1.5 },
      ],
    }
    expect(s.active).toHaveLength(2)
    expect(s.active[0].id).toBe('poison')
    expect(s.active[1].magnitude).toBe(1.5)
  })
})
