// HotspotMechanic — Phase 4 extension mechanic.
//
// Monkey-Island-style click regions on a scene. handlePointer(x, y) hit-tests
// against screen-space rectangles; on hit, fires the matching on_examine /
// on_use / on_pickup ActionRef subject to unlock_condition gating.

import type { Game } from '../../game/game'
import type { ActionRef, HotspotMechanicParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { flagTruthy } from './world_flags'

type Hotspot = HotspotMechanicParams['hotspots'][number]

class HotspotMechanicRuntime implements MechanicRuntime {
  private params: HotspotMechanicParams
  private game!: Game

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as HotspotMechanicParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* pointer-driven */ }

  dispose(): void { /* no state */ }

  /** External: pointer click at screen coords (x, y). kind optionally
   *  narrows the interaction (examine / use / pickup). Returns true if
   *  a hotspot handled the click. */
  handlePointer(x: number, y: number, kind: 'examine' | 'use' | 'pickup' = 'examine'): boolean {
    // Scene gate — only fire for hotspots belonging to this mechanic's
    // scene (HotspotMechanic scopes hotspots per scene in schema).
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const activeName = (active?.name as string | undefined) ?? ''
    if (activeName && activeName !== this.params.scene as unknown as string) return false

    for (const h of this.params.hotspots ?? []) {
      if (h.unlock_condition
          && !flagTruthy(this.game, h.unlock_condition as unknown as string)) continue
      if (!this.pointInRegion(x, y, h.region)) continue
      const action = this.actionFor(h, kind)
      if (action) this.fire(action)
      return true
    }
    return false
  }

  expose(): Record<string, unknown> {
    return {
      scene: this.params.scene,
      hotspots: (this.params.hotspots ?? []).map(h => ({
        name: h.name,
        available: !h.unlock_condition
          || flagTruthy(this.game, h.unlock_condition as unknown as string),
      })),
    }
  }

  private pointInRegion(x: number, y: number, r: Hotspot['region']): boolean {
    return x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h
  }

  private actionFor(h: Hotspot, kind: 'examine' | 'use' | 'pickup'): ActionRef | undefined {
    if (kind === 'examine') return h.on_examine
    if (kind === 'use') return h.on_use ?? h.on_examine
    if (kind === 'pickup') return h.on_pickup
    return h.on_examine
  }

  private fire(action: ActionRef): void {
    const dispatch = (this.game as unknown as Record<string, unknown>).dispatchAction as
      ((a: ActionRef) => void) | undefined
    if (typeof dispatch === 'function') {
      try { dispatch(action) } catch { /* fire-and-forget */ }
    }
  }
}

mechanicRegistry.register('HotspotMechanic', (instance, game) => {
  const rt = new HotspotMechanicRuntime(instance)
  rt.init(game)
  return rt
})
