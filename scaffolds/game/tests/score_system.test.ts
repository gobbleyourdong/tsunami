/**
 * ScoreSystem drone-API fixture. Locks the surface gamedev drones reach
 * for in main.ts: `score.addPoints(N)`, `score.score`, `score.combo`,
 * `score.multiplier`, `score.update(dt)` to drop combos, callbacks,
 * `reset()`, `serialize()`/`deserialize()`.
 *
 * The class exposes `score` directly (not `score.value`) — confirms the
 * fix from a782331 holds. Drones who write `score.value` should fail
 * tsc, not silently misbehave at runtime.
 */

import { describe, it, expect } from 'vitest'
import { ScoreSystem } from '@engine/systems/score'

describe('ScoreSystem — drone-natural surface', () => {
  it('starts at zero', () => {
    const s = new ScoreSystem()
    expect(s.score).toBe(0)
    expect(s.combo).toBe(0)
    expect(s.maxCombo).toBe(0)
    expect(s.multiplier).toBe(1)
    expect(s.highScore).toBe(0)
  })

  it('addPoints returns actual points scored', () => {
    const s = new ScoreSystem()
    expect(s.addPoints(10)).toBe(10)
    expect(s.score).toBe(10)
  })

  it('combo increments per addPoints', () => {
    const s = new ScoreSystem()
    s.addPoints(10)
    s.addPoints(10)
    s.addPoints(10)
    expect(s.combo).toBe(3)
  })

  it('multiplier kicks in at combo 5 (+0.5x per 5)', () => {
    const s = new ScoreSystem()
    for (let i = 0; i < 4; i++) s.addPoints(10)
    expect(s.multiplier).toBe(1)
    s.addPoints(10)  // combo 5 → 1 + floor(5/5)*0.5 = 1.5x
    expect(s.multiplier).toBe(1.5)
  })

  it('multiplier scales the next addPoints (Math.floor)', () => {
    const s = new ScoreSystem()
    for (let i = 0; i < 5; i++) s.addPoints(10)  // combo 5 → 1.5x
    const before = s.score
    const actual = s.addPoints(10)
    expect(actual).toBe(15)        // floor(10 * 1.5)
    expect(s.score).toBe(before + 15)
  })

  it('maxCombo records the highest combo reached', () => {
    const s = new ScoreSystem()
    for (let i = 0; i < 7; i++) s.addPoints(10)
    expect(s.combo).toBe(7)
    s.dropCombo()
    expect(s.combo).toBe(0)
    expect(s.maxCombo).toBe(7)  // preserved across drop
  })

  it('combo drops automatically after the combo window', () => {
    const s = new ScoreSystem(0.5)  // 0.5s window
    s.addPoints(10)
    expect(s.combo).toBe(1)
    s.update(0.3)
    expect(s.combo).toBe(1)  // still inside window
    s.update(0.3)            // total 0.6s > 0.5s
    expect(s.combo).toBe(0)
    expect(s.multiplier).toBe(1)
  })

  it('addPoints resets the combo timer', () => {
    const s = new ScoreSystem(0.5)
    s.addPoints(10)
    s.update(0.4)
    s.addPoints(10)   // resets timer
    s.update(0.4)
    expect(s.combo).toBe(2)  // would have dropped if timer didn't reset
  })

  it('onScoreChange fires with new total + delta', () => {
    const s = new ScoreSystem()
    const events: Array<{ score: number; delta: number }> = []
    s.onScoreChange = (score, delta) => events.push({ score, delta })
    s.addPoints(10)
    s.addPoints(20)
    expect(events).toEqual([
      { score: 10, delta: 10 },
      { score: 30, delta: 20 },
    ])
  })

  it('onComboChange fires with new combo + multiplier', () => {
    const s = new ScoreSystem()
    const seen: Array<[number, number]> = []
    s.onComboChange = (c, m) => seen.push([c, m])
    for (let i = 0; i < 5; i++) s.addPoints(10)
    expect(seen[seen.length - 1]).toEqual([5, 1.5])
  })

  it('onHighScore fires only when crossing the previous best', () => {
    const s = new ScoreSystem()
    let highs = 0
    s.onHighScore = () => { highs++ }
    s.addPoints(10)        // first point — sets new high (0 → 10)
    s.addPoints(10)        // 20 — new high
    s.addPoints(10)        // 30 — new high
    expect(highs).toBe(3)
  })

  it('reset() clears score/combo/multiplier but NOT highScore', () => {
    const s = new ScoreSystem()
    for (let i = 0; i < 7; i++) s.addPoints(10)
    const high = s.highScore
    s.reset()
    expect(s.score).toBe(0)
    expect(s.combo).toBe(0)
    expect(s.maxCombo).toBe(0)
    expect(s.multiplier).toBe(1)
    expect(s.highScore).toBe(high)  // persists across reset
  })

  it('serialize/deserialize roundtrip', () => {
    const a = new ScoreSystem()
    for (let i = 0; i < 6; i++) a.addPoints(10)
    const data = a.serialize()
    const b = new ScoreSystem()
    b.deserialize(data)
    expect(b.score).toBe(a.score)
    expect(b.highScore).toBe(a.highScore)
    expect(b.maxCombo).toBe(a.maxCombo)
  })
})
