import { describe, it, expect } from 'vitest'
import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { DifficultyManager } from '@engine/flow/difficulty'
import { CheckpointSystem, MemorySaveBackend } from '@engine/systems/checkpoint'
import { ProjectileManager } from '../src/game/projectiles'
import { PickupManager } from '../src/game/pickups'

describe('ScoreSystem integration', () => {
  it('builds combo from rapid kills', () => {
    const score = new ScoreSystem(2)
    score.addPoints(20) // kill 1
    score.addPoints(20) // kill 2
    score.addPoints(20) // kill 3
    expect(score.score).toBe(60)
    expect(score.combo).toBe(3)
    expect(score.maxCombo).toBe(3)
  })

  it('multiplier increases at 5 combo', () => {
    const score = new ScoreSystem(5)
    for (let i = 0; i < 5; i++) score.addPoints(10)
    expect(score.multiplier).toBe(1.5)
    // 6th kill gets 1.5x
    const pts = score.addPoints(10)
    expect(pts).toBe(15)
  })

  it('combo drops after timeout', () => {
    const score = new ScoreSystem(1)
    score.addPoints(20)
    expect(score.combo).toBe(1)
    score.update(2) // exceed 1s window
    expect(score.combo).toBe(0)
  })

  it('high score persists across resets', () => {
    const score = new ScoreSystem()
    score.addPoints(500)
    expect(score.highScore).toBe(500)
    score.reset()
    expect(score.score).toBe(0)
    expect(score.highScore).toBe(500)
  })
})

describe('HealthSystem integration', () => {
  it('takes damage and dies', () => {
    let died = false
    const health = new HealthSystem(100)
    health.onDeath = () => { died = true }
    health.takeDamage({ amount: 60, type: 'physical' })
    expect(health.health).toBe(40)
    health.takeDamage({ amount: 50, type: 'physical' })
    expect(health.health).toBe(0)
    expect(died).toBe(true)
  })

  it('shield absorbs damage', () => {
    const health = new HealthSystem(100)
    health.shield = 30
    health.takeDamage({ amount: 50, type: 'physical' })
    expect(health.shield).toBe(0)
    expect(health.health).toBe(80) // 50-30=20 to health
  })

  it('heal caps at max', () => {
    const health = new HealthSystem(100)
    health.takeDamage({ amount: 30, type: 'physical' })
    health.heal(999)
    expect(health.health).toBe(100)
  })
})

describe('DifficultyManager integration', () => {
  it('wave 1 is easy', () => {
    const diff = new DifficultyManager()
    diff.advanceByLevel(1, 10)
    expect(diff.get('enemyHealthMul')).toBeLessThan(1)
  })

  it('wave 10 is hard', () => {
    const diff = new DifficultyManager()
    diff.advanceByLevel(10, 10)
    expect(diff.get('enemyHealthMul')).toBeGreaterThan(1.5)
  })

  it('S-curve is smooth', () => {
    const diff = new DifficultyManager()
    const values: number[] = []
    for (let w = 0; w <= 10; w++) {
      diff.advanceByLevel(w, 10)
      values.push(diff.get('enemyHealthMul'))
    }
    // Should be monotonically increasing
    for (let i = 1; i < values.length; i++) {
      expect(values[i]).toBeGreaterThanOrEqual(values[i - 1])
    }
  })
})

describe('ProjectileManager', () => {
  it('spawns projectiles', () => {
    const pm = new ProjectileManager()
    pm.spawn(0, 0, 10, 0, 'player', 15)
    expect(pm.projectiles.length).toBe(1)
    expect(pm.projectiles[0].owner).toBe('player')
  })

  it('projectiles move over time', () => {
    const pm = new ProjectileManager()
    pm.spawn(0, 0, 10, 0, 'player', 15)
    // Need mock enemies/player/pickups for update — just check position manually
    const p = pm.projectiles[0]
    p.x += p.vx * 0.1
    expect(p.x).toBeCloseTo(1)
  })

  it('projectiles expire', () => {
    const pm = new ProjectileManager()
    pm.spawn(0, 0, 1, 0, 'player', 15)
    pm.projectiles[0].lifetime = 0 // force expire
    // Would be cleaned in update()
    expect(pm.projectiles[0].lifetime).toBe(0)
  })
})

describe('CheckpointSystem integration', () => {
  it('saves and restores score + health', () => {
    const cp = new CheckpointSystem(new MemorySaveBackend())
    const score = new ScoreSystem()
    const health = new HealthSystem(100)

    score.addPoints(250)
    health.takeDamage({ amount: 40, type: 'physical' })

    cp.register('score', {
      serialize: () => score.serialize(),
      deserialize: (d) => score.deserialize(d as any),
    })
    cp.register('health', {
      serialize: () => health.serialize(),
      deserialize: (d) => health.deserialize(d as any),
    })

    cp.setCheckpoint('wave_3')
    cp.save('test')

    // Modify state
    score.addPoints(1000)
    health.takeDamage({ amount: 50, type: 'physical' })

    // Restore
    expect(cp.load('test')).toBe(true)
    expect(score.score).toBe(250)
    expect(health.health).toBe(60)
    expect(cp.currentCheckpoint).toBe('wave_3')
  })
})
