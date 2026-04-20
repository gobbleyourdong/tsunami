/**
 * FrameLoop drone-API fixture. Locks the surface a gamedev drone touches
 * in main.ts: import { FrameLoop } from '@engine/renderer/frame', wire
 * onUpdate / onFixedUpdate / onRender, call start()/stop().
 *
 * Drives the loop with a synthetic rAF + performance.now so the test is
 * deterministic and hermetic — no real animation frames, no flaky timing.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { FrameLoop } from '@engine/renderer/frame'

let now = 0
let pending: ((t: number) => void) | null = null

// Step the loop one frame by `dtMs` milliseconds. The FrameLoop
// schedules a new rAF on every tick(); we capture it here, advance the
// clock, then invoke it. dt becomes (now - lastTime) / 1000.
function step(dtMs: number): void {
  now += dtMs
  const cb = pending
  pending = null
  if (cb) cb(now)
}

beforeEach(() => {
  now = 0
  pending = null
  vi.stubGlobal('requestAnimationFrame', (cb: (t: number) => void) => {
    pending = cb
    return 1
  })
  vi.stubGlobal('cancelAnimationFrame', () => {
    pending = null
  })
  // performance is read-only on real browsers but assignable in node;
  // use a getter spy so FrameLoop's `performance.now()` returns our clock.
  vi.spyOn(performance, 'now').mockImplementation(() => now)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('FrameLoop — drone-natural surface', () => {
  it('start/stop without onUpdate does not throw', () => {
    const loop = new FrameLoop()
    expect(() => loop.start()).not.toThrow()
    step(16)
    expect(() => loop.stop()).not.toThrow()
  })

  it('onUpdate fires every frame with FrameStats', () => {
    const loop = new FrameLoop()
    const samples: number[] = []
    loop.onUpdate = (stats) => {
      samples.push(stats.dt)
      expect(typeof stats.fps).toBe('number')
      expect(typeof stats.frameTime).toBe('number')
      expect(typeof stats.frameCount).toBe('number')
      expect(typeof stats.elapsed).toBe('number')
    }
    loop.start()                 // tick 0 (dt=0)
    step(16)                     // tick 1 (dt≈0.016)
    step(16)                     // tick 2
    expect(samples.length).toBe(3)
    expect(samples[0]).toBe(0)
    expect(samples[1]).toBeCloseTo(0.016, 3)
    expect(samples[2]).toBeCloseTo(0.016, 3)
    loop.stop()
  })

  it('caps dt at 0.1s to avoid spiral of death', () => {
    const loop = new FrameLoop()
    const seen: number[] = []
    loop.onUpdate = (stats) => seen.push(stats.dt)
    loop.start()
    step(2000)  // 2 seconds in one frame
    expect(seen[1]).toBe(0.1)   // capped, NOT 2.0
    loop.stop()
  })

  it('onFixedUpdate runs at fixed 1/60 timestep regardless of frame dt', () => {
    const loop = new FrameLoop()
    let fixedTicks = 0
    loop.onFixedUpdate = () => { fixedTicks++ }
    loop.start()
    // 100ms variable frame → cap kicks in at 0.1s; accumulator = 0.1
    // → exactly 6 fixed steps of 1/60 (~16.66ms) consumed
    step(100)
    expect(fixedTicks).toBe(6)
    loop.stop()
  })

  it('onRender fires after onUpdate (renderTime is populated)', () => {
    const loop = new FrameLoop()
    const order: string[] = []
    loop.onUpdate = () => order.push('update')
    loop.onRender = (stats) => {
      order.push('render')
      expect(stats.renderTime).toBeGreaterThanOrEqual(0)
    }
    loop.start()
    step(16)
    expect(order).toEqual(['update', 'render', 'update', 'render'])
    loop.stop()
  })

  it('stop() halts further callbacks', () => {
    const loop = new FrameLoop()
    let count = 0
    loop.onUpdate = () => { count++ }
    loop.start()
    step(16)
    loop.stop()
    step(16)  // would queue another rAF if running
    expect(count).toBe(2)  // only the start tick + one step
  })

  it('start() is idempotent (does not re-enter)', () => {
    const loop = new FrameLoop()
    let count = 0
    loop.onUpdate = () => { count++ }
    loop.start()
    loop.start()  // should be a no-op
    step(16)
    expect(count).toBe(2)  // not 3+
    loop.stop()
  })

  it('frameCount monotonically increases', () => {
    const loop = new FrameLoop()
    const counts: number[] = []
    loop.onUpdate = (s) => counts.push(s.frameCount)
    loop.start()
    step(16)
    step(16)
    step(16)
    expect(counts).toEqual([1, 2, 3, 4])
    loop.stop()
  })
})
