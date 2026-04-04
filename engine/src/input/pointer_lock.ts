/**
 * Pointer lock — FPS-style mouse capture for 3D games.
 * Request on canvas click, unlock on Escape, delta-based rotation.
 */

export class PointerLockInput {
  isLocked = false
  deltaX = 0
  deltaY = 0
  sensitivity = 1

  private cleanup: (() => void) | null = null

  bind(canvas: HTMLCanvasElement): void {
    const onClick = () => {
      if (!this.isLocked) {
        canvas.requestPointerLock()
      }
    }

    const onLockChange = () => {
      this.isLocked = document.pointerLockElement === canvas
    }

    const onMouseMove = (e: MouseEvent) => {
      if (this.isLocked) {
        this.deltaX += e.movementX * this.sensitivity
        this.deltaY += e.movementY * this.sensitivity
      }
    }

    canvas.addEventListener('click', onClick)
    document.addEventListener('pointerlockchange', onLockChange)
    document.addEventListener('mousemove', onMouseMove)

    this.cleanup = () => {
      canvas.removeEventListener('click', onClick)
      document.removeEventListener('pointerlockchange', onLockChange)
      document.removeEventListener('mousemove', onMouseMove)
    }
  }

  /** Consume delta (call once per frame, then delta resets). */
  consumeDelta(): { x: number; y: number } {
    const d = { x: this.deltaX, y: this.deltaY }
    this.deltaX = 0
    this.deltaY = 0
    return d
  }

  unlock(): void {
    if (this.isLocked) document.exitPointerLock()
  }

  unbind(): void {
    this.unlock()
    this.cleanup?.()
    this.cleanup = null
  }
}
