/**
 * Gamepad input — poll on rAF, normalize axes/buttons across vendors.
 * Supports Xbox, PlayStation, and generic controllers via Gamepad API.
 */

export interface GamepadState {
  connected: boolean
  id: string
  axes: number[]     // normalized -1 to 1
  buttons: boolean[] // pressed state
  leftStick: { x: number; y: number }
  rightStick: { x: number; y: number }
  leftTrigger: number   // 0-1
  rightTrigger: number  // 0-1
}

const EMPTY_STATE: GamepadState = {
  connected: false, id: '', axes: [], buttons: [],
  leftStick: { x: 0, y: 0 }, rightStick: { x: 0, y: 0 },
  leftTrigger: 0, rightTrigger: 0,
}

export class GamepadInput {
  deadZone = 0.15
  private previousButtons: boolean[] = []

  /** Poll current gamepad state (call every frame). */
  poll(index = 0): GamepadState {
    const gamepads = navigator.getGamepads?.() ?? []
    const gp = gamepads[index]
    if (!gp) return { ...EMPTY_STATE }

    const axes = gp.axes.map(a => this.applyDeadZone(a))
    const buttons = gp.buttons.map(b => b.pressed)

    const state: GamepadState = {
      connected: true,
      id: gp.id,
      axes,
      buttons,
      leftStick: { x: axes[0] ?? 0, y: axes[1] ?? 0 },
      rightStick: { x: axes[2] ?? 0, y: axes[3] ?? 0 },
      leftTrigger: gp.buttons[6]?.value ?? 0,
      rightTrigger: gp.buttons[7]?.value ?? 0,
    }

    return state
  }

  /** Check if button was just pressed this frame. */
  justPressed(state: GamepadState, buttonIndex: number): boolean {
    const current = state.buttons[buttonIndex] ?? false
    const previous = this.previousButtons[buttonIndex] ?? false
    return current && !previous
  }

  /** Snapshot button state for next-frame comparison. */
  update(state: GamepadState): void {
    this.previousButtons = [...state.buttons]
  }

  private applyDeadZone(value: number): number {
    if (Math.abs(value) < this.deadZone) return 0
    const sign = Math.sign(value)
    return sign * (Math.abs(value) - this.deadZone) / (1 - this.deadZone)
  }
}

// Standard button mapping (Xbox layout)
export const GAMEPAD_BUTTONS = {
  A: 0, B: 1, X: 2, Y: 3,
  LB: 4, RB: 5, LT: 6, RT: 7,
  BACK: 8, START: 9,
  L_STICK: 10, R_STICK: 11,
  DPAD_UP: 12, DPAD_DOWN: 13, DPAD_LEFT: 14, DPAD_RIGHT: 15,
  HOME: 16,
} as const
