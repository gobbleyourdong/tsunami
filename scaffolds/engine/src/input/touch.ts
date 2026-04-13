/**
 * Touch input — virtual joystick + tap-to-action for mobile.
 */

export interface VirtualJoystick {
  active: boolean
  x: number  // -1 to 1
  y: number  // -1 to 1
  magnitude: number  // 0 to 1
}

export interface TouchButton {
  id: string
  x: number      // CSS percent from left
  y: number      // CSS percent from top
  radius: number // CSS pixels
  pressed: boolean
  justPressed: boolean
}

export class TouchInput {
  joystick: VirtualJoystick = { active: false, x: 0, y: 0, magnitude: 0 }
  private buttons: TouchButton[] = []
  private joystickTouchId = -1
  private joystickOrigin = { x: 0, y: 0 }
  private joystickRadius = 60
  private cleanup: (() => void) | null = null
  private prevButtonState = new Map<string, boolean>()

  /** Register a virtual button on screen. */
  addButton(id: string, x: number, y: number, radius = 40): void {
    this.buttons.push({ id, x, y, radius, pressed: false, justPressed: false })
  }

  /** Start listening to touch events on a canvas. */
  bind(canvas: HTMLCanvasElement): void {
    const onStart = (e: TouchEvent) => {
      e.preventDefault()
      for (const touch of Array.from(e.changedTouches)) {
        const rect = canvas.getBoundingClientRect()
        const tx = touch.clientX - rect.left
        const ty = touch.clientY - rect.top

        // Check buttons first
        let hitButton = false
        for (const btn of this.buttons) {
          const bx = (btn.x / 100) * rect.width
          const by = (btn.y / 100) * rect.height
          const dist = Math.sqrt((tx - bx) ** 2 + (ty - by) ** 2)
          if (dist < btn.radius) {
            btn.pressed = true
            hitButton = true
          }
        }

        // Left half of screen = joystick
        if (!hitButton && tx < rect.width * 0.5 && this.joystickTouchId < 0) {
          this.joystickTouchId = touch.identifier
          this.joystickOrigin = { x: tx, y: ty }
          this.joystick.active = true
        }
      }
    }

    const onMove = (e: TouchEvent) => {
      for (const touch of Array.from(e.changedTouches)) {
        if (touch.identifier === this.joystickTouchId) {
          const rect = canvas.getBoundingClientRect()
          const dx = (touch.clientX - rect.left) - this.joystickOrigin.x
          const dy = (touch.clientY - rect.top) - this.joystickOrigin.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          const clamped = Math.min(dist, this.joystickRadius)
          const magnitude = clamped / this.joystickRadius

          if (dist > 0) {
            this.joystick.x = (dx / dist) * magnitude
            this.joystick.y = (dy / dist) * magnitude
          }
          this.joystick.magnitude = magnitude
        }
      }
    }

    const onEnd = (e: TouchEvent) => {
      for (const touch of Array.from(e.changedTouches)) {
        if (touch.identifier === this.joystickTouchId) {
          this.joystickTouchId = -1
          this.joystick = { active: false, x: 0, y: 0, magnitude: 0 }
        }
        // Release buttons
        for (const btn of this.buttons) btn.pressed = false
      }
    }

    canvas.addEventListener('touchstart', onStart, { passive: false })
    canvas.addEventListener('touchmove', onMove, { passive: false })
    canvas.addEventListener('touchend', onEnd)
    canvas.addEventListener('touchcancel', onEnd)

    this.cleanup = () => {
      canvas.removeEventListener('touchstart', onStart)
      canvas.removeEventListener('touchmove', onMove)
      canvas.removeEventListener('touchend', onEnd)
      canvas.removeEventListener('touchcancel', onEnd)
    }
  }

  /** Call per frame to compute justPressed. */
  update(): void {
    for (const btn of this.buttons) {
      const prev = this.prevButtonState.get(btn.id) ?? false
      btn.justPressed = btn.pressed && !prev
      this.prevButtonState.set(btn.id, btn.pressed)
    }
  }

  getButton(id: string): TouchButton | undefined {
    return this.buttons.find(b => b.id === id)
  }

  unbind(): void {
    this.cleanup?.()
    this.cleanup = null
  }
}
