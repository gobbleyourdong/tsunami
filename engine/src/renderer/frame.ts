/**
 * Frame graph — describes render passes, auto-barrier insertion.
 * Manages the main render loop with fixed-timestep physics and variable-rate rendering.
 */

export interface FrameStats {
  fps: number
  frameTime: number   // ms
  renderTime: number  // ms
  frameCount: number
  elapsed: number     // seconds since start
  dt: number          // delta time in seconds (capped)
}

export type FrameCallback = (stats: FrameStats) => void

export class FrameLoop {
  private running = false
  private animId = 0
  private lastTime = 0
  private frameCount = 0
  private startTime = 0

  // FPS tracking
  private fpsAccumulator = 0
  private fpsFrameCount = 0
  private currentFps = 0

  // Fixed timestep
  private fixedDt = 1 / 60
  private accumulator = 0

  onUpdate?: FrameCallback
  onFixedUpdate?: (dt: number) => void
  onRender?: FrameCallback

  start(): void {
    if (this.running) return
    this.running = true
    this.startTime = performance.now()
    this.lastTime = this.startTime
    this.tick(this.startTime)
  }

  stop(): void {
    this.running = false
    if (this.animId) cancelAnimationFrame(this.animId)
  }

  private tick = (now: number): void => {
    if (!this.running) return
    this.animId = requestAnimationFrame(this.tick)

    const rawDt = (now - this.lastTime) / 1000
    const dt = Math.min(rawDt, 0.1) // cap to avoid spiral of death
    this.lastTime = now
    this.frameCount++

    // FPS counter
    this.fpsAccumulator += rawDt
    this.fpsFrameCount++
    if (this.fpsAccumulator >= 1.0) {
      this.currentFps = this.fpsFrameCount / this.fpsAccumulator
      this.fpsAccumulator = 0
      this.fpsFrameCount = 0
    }

    const stats: FrameStats = {
      fps: this.currentFps,
      frameTime: rawDt * 1000,
      renderTime: 0, // filled after render
      frameCount: this.frameCount,
      elapsed: (now - this.startTime) / 1000,
      dt,
    }

    // Fixed timestep updates (physics)
    if (this.onFixedUpdate) {
      this.accumulator += dt
      while (this.accumulator >= this.fixedDt) {
        this.onFixedUpdate(this.fixedDt)
        this.accumulator -= this.fixedDt
      }
    }

    // Variable-rate update
    this.onUpdate?.(stats)

    // Render
    const renderStart = performance.now()
    this.onRender?.(stats)
    stats.renderTime = performance.now() - renderStart
  }
}

/**
 * Render pass descriptor builder for common patterns.
 */
export function colorPass(
  view: GPUTextureView,
  depthView?: GPUTextureView,
  clearColor?: [number, number, number, number]
): GPURenderPassDescriptor {
  const c = clearColor ?? [0.05, 0.05, 0.08, 1.0]
  return {
    colorAttachments: [
      {
        view,
        clearValue: { r: c[0], g: c[1], b: c[2], a: c[3] },
        loadOp: 'clear',
        storeOp: 'store',
      },
    ],
    depthStencilAttachment: depthView
      ? {
          view: depthView,
          depthClearValue: 1.0,
          depthLoadOp: 'clear',
          depthStoreOp: 'store',
          stencilClearValue: 0,
          stencilLoadOp: 'clear',
          stencilStoreOp: 'store',
        }
      : undefined,
  }
}
