/**
 * Action map — rebindable action → key/button mappings.
 * Serializes to localStorage for persistence.
 */

export type InputSource =
  | { type: 'key'; code: string }
  | { type: 'gamepadButton'; index: number }
  | { type: 'gamepadAxis'; index: number; direction: 1 | -1; threshold?: number }
  | { type: 'mouseButton'; button: number }

export interface ActionBinding {
  action: string
  sources: InputSource[]
}

export class ActionMap {
  private bindings = new Map<string, InputSource[]>()

  /** Define an action with default bindings. */
  define(action: string, ...sources: InputSource[]): this {
    this.bindings.set(action, sources)
    return this
  }

  /** Rebind an action to new sources (replaces existing). */
  rebind(action: string, ...sources: InputSource[]): this {
    this.bindings.set(action, sources)
    return this
  }

  /** Add a binding to an existing action. */
  addBinding(action: string, source: InputSource): this {
    const existing = this.bindings.get(action) ?? []
    existing.push(source)
    this.bindings.set(action, existing)
    return this
  }

  /** Get all sources for an action. */
  getSources(action: string): InputSource[] {
    return this.bindings.get(action) ?? []
  }

  /** Get all defined action names. */
  getActions(): string[] {
    return Array.from(this.bindings.keys())
  }

  /** Check if action is triggered by given key state. */
  isActionDown(action: string, keyState: Set<string>, gamepadButtons?: boolean[]): boolean {
    const sources = this.bindings.get(action)
    if (!sources) return false

    for (const src of sources) {
      if (src.type === 'key' && keyState.has(src.code)) return true
      if (src.type === 'gamepadButton' && gamepadButtons?.[src.index]) return true
    }
    return false
  }

  /** Get axis value for an action from gamepad axes. */
  getActionAxis(action: string, gamepadAxes?: number[]): number {
    const sources = this.bindings.get(action)
    if (!sources) return 0

    for (const src of sources) {
      if (src.type === 'gamepadAxis' && gamepadAxes) {
        const raw = gamepadAxes[src.index] ?? 0
        const threshold = src.threshold ?? 0.1
        if (Math.abs(raw) > threshold) return raw * src.direction
      }
    }
    return 0
  }

  /** Serialize to JSON string for localStorage. */
  serialize(): string {
    const data: ActionBinding[] = []
    for (const [action, sources] of this.bindings) {
      data.push({ action, sources })
    }
    return JSON.stringify(data)
  }

  /** Deserialize from JSON string. */
  deserialize(json: string): void {
    const data: ActionBinding[] = JSON.parse(json)
    this.bindings.clear()
    for (const { action, sources } of data) {
      this.bindings.set(action, sources)
    }
  }

  /** Save to localStorage. */
  save(key = 'tsunami_keybinds'): void {
    try { localStorage.setItem(key, this.serialize()) } catch {}
  }

  /** Load from localStorage. Returns false if no saved data. */
  load(key = 'tsunami_keybinds'): boolean {
    try {
      const data = localStorage.getItem(key)
      if (!data) return false
      this.deserialize(data)
      return true
    } catch { return false }
  }
}

/** Create a standard FPS action map with defaults. */
export function createFPSActionMap(): ActionMap {
  return new ActionMap()
    .define('moveForward', { type: 'key', code: 'KeyW' }, { type: 'gamepadAxis', index: 1, direction: -1 })
    .define('moveBackward', { type: 'key', code: 'KeyS' }, { type: 'gamepadAxis', index: 1, direction: 1 })
    .define('moveLeft', { type: 'key', code: 'KeyA' }, { type: 'gamepadAxis', index: 0, direction: -1 })
    .define('moveRight', { type: 'key', code: 'KeyD' }, { type: 'gamepadAxis', index: 0, direction: 1 })
    .define('jump', { type: 'key', code: 'Space' }, { type: 'gamepadButton', index: 0 })
    .define('sprint', { type: 'key', code: 'ShiftLeft' }, { type: 'gamepadButton', index: 10 })
    .define('interact', { type: 'key', code: 'KeyE' }, { type: 'gamepadButton', index: 2 })
    .define('attack', { type: 'mouseButton', button: 0 }, { type: 'gamepadButton', index: 7 })
    .define('aim', { type: 'mouseButton', button: 2 }, { type: 'gamepadButton', index: 6 })
    .define('pause', { type: 'key', code: 'Escape' }, { type: 'gamepadButton', index: 9 })
}

/** Create a standard platformer action map with defaults. */
export function createPlatformerActionMap(): ActionMap {
  return new ActionMap()
    .define('left', { type: 'key', code: 'KeyA' }, { type: 'key', code: 'ArrowLeft' })
    .define('right', { type: 'key', code: 'KeyD' }, { type: 'key', code: 'ArrowRight' })
    .define('jump', { type: 'key', code: 'Space' }, { type: 'key', code: 'ArrowUp' })
    .define('duck', { type: 'key', code: 'KeyS' }, { type: 'key', code: 'ArrowDown' })
    .define('attack', { type: 'key', code: 'KeyJ' }, { type: 'gamepadButton', index: 0 })
    .define('special', { type: 'key', code: 'KeyK' }, { type: 'gamepadButton', index: 2 })
    .define('pause', { type: 'key', code: 'Escape' }, { type: 'gamepadButton', index: 9 })
}
