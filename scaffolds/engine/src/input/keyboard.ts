/**
 * Keyboard input — key state map with down/justPressed/justReleased per frame.
 */

export class KeyboardInput {
  private currentKeys = new Set<string>()
  private previousKeys = new Set<string>()
  private cleanup: (() => void) | null = null

  /** Start listening to keyboard events. */
  bind(): void {
    const onDown = (e: KeyboardEvent) => {
      this.currentKeys.add(e.code)
    }
    const onUp = (e: KeyboardEvent) => {
      this.currentKeys.delete(e.code)
    }
    window.addEventListener('keydown', onDown)
    window.addEventListener('keyup', onUp)
    this.cleanup = () => {
      window.removeEventListener('keydown', onDown)
      window.removeEventListener('keyup', onUp)
    }
  }

  /** Call at end of each frame to snapshot previous state. */
  update(): void {
    this.previousKeys = new Set(this.currentKeys)
  }

  /** Key is currently held down. */
  isDown(code: string): boolean {
    return this.currentKeys.has(code)
  }

  /** Key was pressed this frame (not held from previous). */
  justPressed(code: string): boolean {
    return this.currentKeys.has(code) && !this.previousKeys.has(code)
  }

  /** Key was released this frame. */
  justReleased(code: string): boolean {
    return !this.currentKeys.has(code) && this.previousKeys.has(code)
  }

  /** Get all currently held keys. */
  getHeldKeys(): string[] {
    return Array.from(this.currentKeys)
  }

  unbind(): void {
    this.cleanup?.()
    this.cleanup = null
  }
}
