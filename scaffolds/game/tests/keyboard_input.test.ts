/**
 * KeyboardInput drone-API fixture. Drone pattern in main.ts:
 *
 *   const kb = new KeyboardInput()
 *   kb.bind()
 *   loop.onUpdate = () => {
 *     if (kb.justPressed('Space')) jump()
 *     if (kb.isDown('ArrowLeft')) move(-1)
 *     kb.update()  // snapshot at end of frame
 *   }
 *
 * Tests cover both (a) the bind() lifecycle against real DOM events
 * (jsdom) and (b) the per-frame transition pattern.
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { KeyboardInput } from '@engine/input/keyboard'

let kb: KeyboardInput

beforeEach(() => {
  kb = new KeyboardInput()
})

afterEach(() => {
  kb.unbind()
})

function press(code: string): void {
  window.dispatchEvent(new KeyboardEvent('keydown', { code }))
}
function release(code: string): void {
  window.dispatchEvent(new KeyboardEvent('keyup', { code }))
}

describe('KeyboardInput — drone-natural surface', () => {
  it('bind() listens to window keydown/keyup events', () => {
    kb.bind()
    press('KeyW')
    expect(kb.isDown('KeyW')).toBe(true)
    release('KeyW')
    expect(kb.isDown('KeyW')).toBe(false)
  })

  it('justPressed is true on the first frame a key goes down', () => {
    kb.bind()
    press('Space')
    expect(kb.justPressed('Space')).toBe(true)
    expect(kb.isDown('Space')).toBe(true)
  })

  it('justPressed becomes false after update() snapshots the frame', () => {
    kb.bind()
    press('Space')
    expect(kb.justPressed('Space')).toBe(true)
    kb.update()
    expect(kb.justPressed('Space')).toBe(false)
    expect(kb.isDown('Space')).toBe(true)  // still held
  })

  it('justReleased is true on the frame a key goes up', () => {
    kb.bind()
    press('KeyA')
    kb.update()  // sync previousKeys
    release('KeyA')
    expect(kb.justReleased('KeyA')).toBe(true)
    kb.update()
    expect(kb.justReleased('KeyA')).toBe(false)
  })

  it('getHeldKeys returns all currently-down codes', () => {
    kb.bind()
    press('KeyA')
    press('KeyD')
    press('Space')
    const held = kb.getHeldKeys()
    expect(held).toContain('KeyA')
    expect(held).toContain('KeyD')
    expect(held).toContain('Space')
    release('KeyD')
    expect(kb.getHeldKeys()).not.toContain('KeyD')
  })

  it('unbind() removes the listeners — events stop registering', () => {
    kb.bind()
    press('KeyW')
    expect(kb.isDown('KeyW')).toBe(true)
    kb.unbind()
    release('KeyW')              // event still fires…
    press('KeyS')                // …and another, but listener is gone
    expect(kb.isDown('KeyW')).toBe(true)   // state frozen
    expect(kb.isDown('KeyS')).toBe(false)  // never recorded
  })

  it('multiple keys held simultaneously all read as down', () => {
    kb.bind()
    press('KeyW')
    press('KeyA')
    expect(kb.isDown('KeyW')).toBe(true)
    expect(kb.isDown('KeyA')).toBe(true)
    expect(kb.isDown('KeyS')).toBe(false)
  })

  it('justPressed without prior bind never fires (state stays empty)', () => {
    // Drone forgets to call bind() — should be a soft no-op, not a crash
    expect(kb.justPressed('Space')).toBe(false)
    expect(kb.isDown('Space')).toBe(false)
    expect(kb.getHeldKeys()).toEqual([])
  })

  it('update() with no held keys is a no-op', () => {
    expect(() => kb.update()).not.toThrow()
  })
})
