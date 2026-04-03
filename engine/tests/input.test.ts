import { describe, it, expect } from 'vitest'
import { KeyboardInput } from '../src/input/keyboard'
import { GamepadInput, GAMEPAD_BUTTONS } from '../src/input/gamepad'
import { ActionMap, createFPSActionMap, createPlatformerActionMap } from '../src/input/action_map'
import { ComboSystem } from '../src/input/combo'

describe('KeyboardInput', () => {
  it('tracks key state', () => {
    const kb = new KeyboardInput()
    // Simulate internal state directly (no DOM in Node)
    const current = (kb as any).currentKeys as Set<string>
    const previous = (kb as any).previousKeys as Set<string>

    current.add('KeyW')
    expect(kb.isDown('KeyW')).toBe(true)
    expect(kb.justPressed('KeyW')).toBe(true)  // not in previous

    kb.update()
    expect(kb.justPressed('KeyW')).toBe(false) // now in previous too
    expect(kb.isDown('KeyW')).toBe(true)

    current.delete('KeyW')
    expect(kb.justReleased('KeyW')).toBe(true)
    kb.update()
    expect(kb.justReleased('KeyW')).toBe(false)
  })

  it('getHeldKeys returns active keys', () => {
    const kb = new KeyboardInput()
    const current = (kb as any).currentKeys as Set<string>
    current.add('KeyA')
    current.add('Space')
    expect(kb.getHeldKeys()).toContain('KeyA')
    expect(kb.getHeldKeys()).toContain('Space')
  })
})

describe('GamepadInput', () => {
  it('applies dead zone', () => {
    const gp = new GamepadInput()
    gp.deadZone = 0.2
    const applyDZ = (gp as any).applyDeadZone.bind(gp) as (v: number) => number
    expect(applyDZ(0.1)).toBe(0)
    expect(applyDZ(0.5)).toBeGreaterThan(0)
    expect(applyDZ(-0.1)).toBe(0)
    expect(applyDZ(-0.5)).toBeLessThan(0)
  })

  it('has standard button constants', () => {
    expect(GAMEPAD_BUTTONS.A).toBe(0)
    expect(GAMEPAD_BUTTONS.START).toBe(9)
    expect(GAMEPAD_BUTTONS.DPAD_UP).toBe(12)
  })
})

describe('ActionMap', () => {
  it('defines and checks actions', () => {
    const map = new ActionMap()
    map.define('jump', { type: 'key', code: 'Space' })

    const keys = new Set(['Space'])
    expect(map.isActionDown('jump', keys)).toBe(true)
    expect(map.isActionDown('jump', new Set())).toBe(false)
  })

  it('supports multiple bindings per action', () => {
    const map = new ActionMap()
    map.define('jump', { type: 'key', code: 'Space' }, { type: 'key', code: 'KeyW' })

    expect(map.isActionDown('jump', new Set(['Space']))).toBe(true)
    expect(map.isActionDown('jump', new Set(['KeyW']))).toBe(true)
    expect(map.isActionDown('jump', new Set(['KeyA']))).toBe(false)
  })

  it('rebind replaces sources', () => {
    const map = new ActionMap()
    map.define('jump', { type: 'key', code: 'Space' })
    map.rebind('jump', { type: 'key', code: 'KeyJ' })

    expect(map.isActionDown('jump', new Set(['Space']))).toBe(false)
    expect(map.isActionDown('jump', new Set(['KeyJ']))).toBe(true)
  })

  it('addBinding appends to existing', () => {
    const map = new ActionMap()
    map.define('jump', { type: 'key', code: 'Space' })
    map.addBinding('jump', { type: 'key', code: 'ArrowUp' })

    expect(map.getSources('jump').length).toBe(2)
  })

  it('checks gamepad buttons', () => {
    const map = new ActionMap()
    map.define('fire', { type: 'gamepadButton', index: 7 })

    const buttons = new Array(16).fill(false)
    buttons[7] = true
    expect(map.isActionDown('fire', new Set(), buttons)).toBe(true)
  })

  it('serializes and deserializes', () => {
    const map = new ActionMap()
    map.define('jump', { type: 'key', code: 'Space' })
    map.define('fire', { type: 'key', code: 'KeyJ' })

    const json = map.serialize()

    const map2 = new ActionMap()
    map2.deserialize(json)
    expect(map2.isActionDown('jump', new Set(['Space']))).toBe(true)
    expect(map2.isActionDown('fire', new Set(['KeyJ']))).toBe(true)
  })

  it('getActions lists all defined', () => {
    const map = createFPSActionMap()
    const actions = map.getActions()
    expect(actions).toContain('moveForward')
    expect(actions).toContain('jump')
    expect(actions).toContain('attack')
    expect(actions).toContain('pause')
  })

  it('FPS preset has standard bindings', () => {
    const map = createFPSActionMap()
    expect(map.isActionDown('moveForward', new Set(['KeyW']))).toBe(true)
    expect(map.isActionDown('jump', new Set(['Space']))).toBe(true)
  })

  it('platformer preset has standard bindings', () => {
    const map = createPlatformerActionMap()
    expect(map.isActionDown('left', new Set(['KeyA']))).toBe(true)
    expect(map.isActionDown('left', new Set(['ArrowLeft']))).toBe(true)
    expect(map.isActionDown('jump', new Set(['Space']))).toBe(true)
  })
})

describe('ComboSystem', () => {
  it('detects simple combo', () => {
    const combo = new ComboSystem(10)
    let fired = false

    combo.addPattern({
      name: 'hadouken',
      sequence: ['down', 'downRight', 'right', 'punch'],
      windowMs: 500,
      onMatch: () => { fired = true },
    })

    combo.push('down', 0.0)
    combo.push('downRight', 0.1)
    combo.push('right', 0.2)
    expect(fired).toBe(false)
    combo.push('punch', 0.3)
    expect(fired).toBe(true)
  })

  it('fails if window exceeded', () => {
    const combo = new ComboSystem(10)
    let fired = false

    combo.addPattern({
      name: 'quick',
      sequence: ['a', 'b'],
      windowMs: 100,
      onMatch: () => { fired = true },
    })

    combo.push('a', 0.0)
    combo.push('b', 1.0)  // 1000ms apart > 100ms window
    expect(fired).toBe(false)
  })

  it('clears buffer after match', () => {
    const combo = new ComboSystem(10)
    let count = 0

    combo.addPattern({
      name: 'tap',
      sequence: ['a', 'b'],
      windowMs: 500,
      onMatch: () => { count++ },
    })

    combo.push('a', 0); combo.push('b', 0.1)
    expect(count).toBe(1)
    expect(combo.getBuffer().length).toBe(0) // cleared

    // Second attempt needs fresh inputs
    combo.push('a', 0.2); combo.push('b', 0.3)
    expect(count).toBe(2)
  })

  it('ignores noise between combo inputs', () => {
    const combo = new ComboSystem(10)
    let fired = false

    combo.addPattern({
      name: 'abc',
      sequence: ['a', 'b', 'c'],
      windowMs: 1000,
      onMatch: () => { fired = true },
    })

    combo.push('a', 0)
    combo.push('x', 0.05)  // noise
    combo.push('b', 0.1)
    combo.push('y', 0.15)  // noise
    combo.push('c', 0.2)
    expect(fired).toBe(true)
  })
})
