import { describe, it, expect } from 'vitest'
import { HealthSystem } from '../src/systems/health'
import { Inventory } from '../src/systems/inventory'
import { CheckpointSystem, MemorySaveBackend } from '../src/systems/checkpoint'
import { ScoreSystem } from '../src/systems/score'
import type { ItemDef } from '../src/systems/inventory'

describe('HealthSystem', () => {
  it('starts at full health', () => {
    const h = new HealthSystem(100)
    expect(h.health).toBe(100)
    expect(h.healthPercent).toBe(1)
    expect(h.isDead).toBe(false)
  })

  it('takes damage', () => {
    const h = new HealthSystem(100)
    const actual = h.takeDamage({ amount: 30, type: 'physical' })
    expect(actual).toBe(30)
    expect(h.health).toBe(70)
  })

  it('applies resistance', () => {
    const h = new HealthSystem(100)
    h.resistances.fire = 0.5
    const actual = h.takeDamage({ amount: 40, type: 'fire' })
    expect(actual).toBe(20)
    expect(h.health).toBe(80)
  })

  it('shield absorbs damage first', () => {
    const h = new HealthSystem(100)
    h.shield = 20
    h.takeDamage({ amount: 30, type: 'physical' })
    expect(h.shield).toBe(0)
    expect(h.health).toBe(90) // 30-20=10 goes to health
  })

  it('dies at 0 HP', () => {
    let died = false
    const h = new HealthSystem(50)
    h.onDeath = () => { died = true }
    h.takeDamage({ amount: 100, type: 'physical' })
    expect(h.isDead).toBe(true)
    expect(h.health).toBe(0)
    expect(died).toBe(true)
  })

  it('heals up to max', () => {
    const h = new HealthSystem(100)
    h.takeDamage({ amount: 60, type: 'physical' })
    h.heal(999)
    expect(h.health).toBe(100)
  })

  it('revives from death', () => {
    const h = new HealthSystem(100)
    h.takeDamage({ amount: 200, type: 'physical' })
    expect(h.isDead).toBe(true)
    h.revive(0.5)
    expect(h.isDead).toBe(false)
    expect(h.health).toBe(50)
  })

  it('serializes and deserializes', () => {
    const h = new HealthSystem(100)
    h.takeDamage({ amount: 30, type: 'physical' })
    h.shield = 10
    const data = h.serialize()

    const h2 = new HealthSystem(100)
    h2.deserialize(data)
    expect(h2.health).toBe(70)
    expect(h2.shield).toBe(10)
  })
})

describe('Inventory', () => {
  const potion: ItemDef = { id: 'potion', name: 'Health Potion', maxStack: 10, category: 'consumable' }
  const sword: ItemDef = { id: 'sword', name: 'Iron Sword', maxStack: 1, category: 'weapon' }

  it('adds items', () => {
    const inv = new Inventory(5)
    inv.add(potion, 3)
    expect(inv.count('potion')).toBe(3)
    expect(inv.usedSlots).toBe(1)
  })

  it('stacks items', () => {
    const inv = new Inventory(5)
    inv.add(potion, 5)
    inv.add(potion, 3)
    expect(inv.count('potion')).toBe(8)
    expect(inv.usedSlots).toBe(1)
  })

  it('splits into multiple slots at max stack', () => {
    const inv = new Inventory(5)
    inv.add(potion, 15)
    expect(inv.count('potion')).toBe(15)
    expect(inv.usedSlots).toBe(2) // 10 + 5
  })

  it('returns leftover when full', () => {
    const inv = new Inventory(1)
    const leftover = inv.add(potion, 15)
    expect(leftover).toBe(5) // only 10 fit in 1 slot
  })

  it('removes items', () => {
    const inv = new Inventory(5)
    inv.add(potion, 5)
    const removed = inv.remove('potion', 3)
    expect(removed).toBe(3)
    expect(inv.count('potion')).toBe(2)
  })

  it('has() checks quantity', () => {
    const inv = new Inventory(5)
    inv.add(potion, 5)
    expect(inv.has('potion', 5)).toBe(true)
    expect(inv.has('potion', 6)).toBe(false)
    expect(inv.has('sword')).toBe(false)
  })

  it('non-stackable items use separate slots', () => {
    const inv = new Inventory(5)
    inv.add(sword)
    inv.add(sword)
    expect(inv.count('sword')).toBe(2)
    expect(inv.usedSlots).toBe(2)
  })

  it('clear empties all', () => {
    const inv = new Inventory(5)
    inv.add(potion, 5)
    inv.add(sword)
    inv.clear()
    expect(inv.usedSlots).toBe(0)
  })
})

describe('CheckpointSystem', () => {
  it('saves and loads game state', () => {
    const checkpoint = new CheckpointSystem()
    let value = 42
    checkpoint.register('myValue', {
      serialize: () => value,
      deserialize: (v) => { value = v as number },
    })

    checkpoint.setCheckpoint('town')
    checkpoint.save('slot1')

    value = 999
    expect(checkpoint.load('slot1')).toBe(true)
    expect(value).toBe(42)
    expect(checkpoint.currentCheckpoint).toBe('town')
  })

  it('returns false for missing slot', () => {
    const checkpoint = new CheckpointSystem()
    expect(checkpoint.load('nonexistent')).toBe(false)
  })

  it('lists saves', () => {
    const checkpoint = new CheckpointSystem()
    checkpoint.save('a')
    checkpoint.save('b')
    expect(checkpoint.listSaves()).toContain('a')
    expect(checkpoint.listSaves()).toContain('b')
  })

  it('deletes saves', () => {
    const checkpoint = new CheckpointSystem()
    checkpoint.save('del')
    expect(checkpoint.hasSave('del')).toBe(true)
    checkpoint.deleteSave('del')
    expect(checkpoint.hasSave('del')).toBe(false)
  })

  it('integrates with health + inventory', () => {
    const checkpoint = new CheckpointSystem()
    const health = new HealthSystem(100)
    const inv = new Inventory(5)
    const potion: ItemDef = { id: 'potion', name: 'Potion', maxStack: 10, category: 'item' }

    checkpoint.register('health', health)
    checkpoint.register('inventory', inv)

    health.takeDamage({ amount: 40, type: 'physical' })
    inv.add(potion, 5)
    checkpoint.save('mid')

    // Change state
    health.takeDamage({ amount: 50, type: 'physical' })
    inv.remove('potion', 5)

    // Restore
    checkpoint.load('mid')
    expect(health.health).toBe(60)
    expect(inv.count('potion')).toBe(5)
  })
})

describe('ScoreSystem', () => {
  it('adds points with multiplier', () => {
    const score = new ScoreSystem()
    const actual = score.addPoints(100)
    expect(actual).toBe(100) // 1x multiplier initially
    expect(score.score).toBe(100)
    expect(score.combo).toBe(1)
  })

  it('combo builds multiplier', () => {
    const score = new ScoreSystem()
    for (let i = 0; i < 5; i++) score.addPoints(10)
    // After 5 combo: multiplier = 1 + floor(5/5)*0.5 = 1.5
    expect(score.multiplier).toBe(1.5)
  })

  it('combo drops after timeout', () => {
    const score = new ScoreSystem(1) // 1 second window
    score.addPoints(100)
    expect(score.combo).toBe(1)

    score.update(1.5) // exceed window
    expect(score.combo).toBe(0)
    expect(score.multiplier).toBe(1)
  })

  it('tracks high score', () => {
    const score = new ScoreSystem()
    score.addPoints(500)
    expect(score.highScore).toBe(500)
    score.reset()
    expect(score.highScore).toBe(500) // persists
    expect(score.score).toBe(0)
  })

  it('serializes and deserializes', () => {
    const score = new ScoreSystem()
    score.addPoints(200)
    const data = score.serialize()

    const score2 = new ScoreSystem()
    score2.deserialize(data)
    expect(score2.score).toBe(200)
    expect(score2.highScore).toBe(200)
  })
})
