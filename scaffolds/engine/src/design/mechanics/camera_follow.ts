// CameraFollow — Phase 3 action-core mechanic.
//
// Lerps the game camera toward the target archetype each frame. Modes
// describe offset intent:
//   topdown      — camera above target (y+ offset), looking down
//   sidescroll   — fixed y + z offset, tracks x
//   chase_3d     — offset behind target along its forward axis
//   locked_axis  — lock one axis, follow others (platformer)
//
// ease 0 = rigid snap, 1 = fully smoothed. bounds clamp camera target.

import type { Game } from '../../game/game'
import type { CameraFollowParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class CameraFollowRuntime implements MechanicRuntime {
  private params: CameraFollowParams
  private game!: Game
  private currentTarget: [number, number, number] = [0, 0, 0]

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as CameraFollowParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    const pos = this.findTargetPos()
    if (!pos) return
    const goal = this.applyOffset(pos)
    const ease = this.params.ease ?? 0.3
    // Lerp with per-frame step — approximate under 60fps; not framerate-
    // independent but good enough for v1.
    this.currentTarget = [
      lerp(this.currentTarget[0], goal[0], ease),
      lerp(this.currentTarget[1], goal[1], ease),
      lerp(this.currentTarget[2], goal[2], ease),
    ]
    if (this.params.bounds) {
      const b = this.params.bounds
      this.currentTarget[0] = clamp(this.currentTarget[0], b.min[0], b.max[0])
      this.currentTarget[1] = clamp(this.currentTarget[1], b.min[1], b.max[1])
      this.currentTarget[2] = clamp(this.currentTarget[2], b.min[2], b.max[2])
    }
    this.applyToCamera(this.currentTarget)
  }

  dispose(): void { /* no state */ }

  expose(): Record<string, unknown> {
    return {
      mode: this.params.mode,
      cameraTarget: [...this.currentTarget],
    }
  }

  private findTargetPos(): [number, number, number] | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.target_archetype as unknown as string
    const target = entities.find(e => e.type === aid)
    if (!target) return null
    return (target.position as [number, number, number] | undefined) ?? null
  }

  private applyOffset(pos: [number, number, number]): [number, number, number] {
    const off = this.params.offset ?? this.defaultOffset()
    return [pos[0] + off[0], pos[1] + off[1], pos[2] + off[2]]
  }

  private defaultOffset(): [number, number, number] {
    switch (this.params.mode) {
      case 'topdown':     return [0, 12, 0]
      case 'sidescroll':  return [0, 0, 8]
      case 'chase_3d':    return [0, 3, -8]
      case 'locked_axis': return [0, 0, 10]
    }
  }

  private applyToCamera(target: [number, number, number]): void {
    // Game.camera is a typed Camera instance. We update its target via
    // the low-level setter that most cameras expose. Guard if the camera
    // API differs in the host game class.
    const cam = (this.game as unknown as Record<string, unknown>).camera as
      Record<string, unknown> | undefined
    if (!cam) return
    if (typeof (cam as Record<string, (t: [number, number, number]) => void>).setTarget === 'function') {
      try { (cam as Record<string, (t: [number, number, number]) => void>).setTarget(target) }
      catch { /* camera busy */ }
    } else {
      // Fallback: write `target` directly — compatible with our Camera
      // class's public field name.
      ;(cam as Record<string, unknown>).target = target
    }
  }
}

function lerp(a: number, b: number, t: number): number { return a + (b - a) * t }
function clamp(v: number, lo: number, hi: number): number { return Math.max(lo, Math.min(hi, v)) }

mechanicRegistry.register('CameraFollow', (instance, game) => {
  const rt = new CameraFollowRuntime(instance)
  rt.init(game)
  return rt
})
