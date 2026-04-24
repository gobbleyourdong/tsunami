// ParallaxScroll — multi-layer backdrop scroll positioning.
//
// Each frame, reads the follow_archetype's world position, computes per-
// layer scroll offsets via scroll_speed_ratio, and exposes the offsets
// via .expose() for the renderer to consume. No rendering happens here —
// the mechanic produces scroll offsets; downstream renderer applies them
// when blitting background_layer sprites.
//
// Pairs with:
//   - sprite kind `background_layer` (extraction data)
//   - asset_workflows/parallax_backdrop/ (asset generation)
//   - engine/src/sprites/kind_index.ts (typed sprite lookup)

import type { Game } from '../../game/game'
import type { MechanicInstance, ParallaxScrollParams, ParallaxScrollLayer } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

class ParallaxScrollRuntime implements MechanicRuntime {
  private params: ParallaxScrollParams
  private game!: Game
  private followArchetype = ''
  /** Per-layer scroll offset (world-px relative to foreground 0). Index
   *  matches `params.layers[]`. */
  private offsets: Array<{ x: number; y: number }> = []
  /** Last-frame follow position — used to compute delta scroll. */
  private lastFollowPos: { x: number; y: number } = { x: 0, y: 0 }

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ParallaxScrollParams
    this.followArchetype = this.params.follow_archetype
    this.offsets = this.params.layers.map(() => ({ x: 0, y: 0 }))
  }

  init(game: Game): void {
    this.game = game
    // Initial follow-position snapshot.
    const pos = this.findFollowPos()
    if (pos) this.lastFollowPos = { x: pos.x, y: pos.y }
  }

  update(_dt: number): void {
    const pos = this.findFollowPos()
    if (!pos) return
    const dx = pos.x - this.lastFollowPos.x
    const dy = pos.y - this.lastFollowPos.y
    // Apply per-layer scroll. scroll_speed_ratio=0 → layer stays fixed
    // (skybox), scroll_speed_ratio=1 → layer moves 1:1 with camera
    // (foreground-pinned), fractions produce depth-parallax.
    for (let i = 0; i < this.params.layers.length; i++) {
      const layer = this.params.layers[i]
      const ratio = layer.scroll_speed_ratio
      const off = this.offsets[i]
      if (this.params.axes === 'horizontal' || this.params.axes === 'both') {
        off.x += dx * ratio
      }
      if ((this.params.axes === 'vertical' || this.params.axes === 'both') && !layer.lock_y) {
        off.y += dy * ratio
      }
    }
    // Clamp to bounds if configured.
    if (this.params.bounds) {
      const b = this.params.bounds
      for (const off of this.offsets) {
        if (b.min_x !== undefined) off.x = Math.max(off.x, b.min_x)
        if (b.max_x !== undefined) off.x = Math.min(off.x, b.max_x)
        if (b.min_y !== undefined) off.y = Math.max(off.y, b.min_y)
        if (b.max_y !== undefined) off.y = Math.min(off.y, b.max_y)
      }
    }
    this.lastFollowPos = { x: pos.x, y: pos.y }
  }

  dispose(): void {
    /* no state */
  }

  expose(): Record<string, unknown> {
    // Per-layer offset + resolved z — renderer iterates this to position
    // background sprites. Returned shape is deliberately flat so a
    // WebGL/Canvas renderer can map 1-to-1 to draw calls.
    return {
      layer_offsets: this.params.layers.map((layer, i) => ({
        sprite_id: layer.sprite_id,
        offset_x: this.offsets[i].x,
        offset_y: this.offsets[i].y,
        layer_z: layer.layer_z ?? _defaultZ(i, this.params.layers.length),
        loops_horizontally: layer.loops_horizontally ?? true,
      })),
      follow_pos: { ...this.lastFollowPos },
    }
  }

  /** Walk active scene for the follow-archetype entity. Returns null
   *  when not present (scene not loaded, entity not spawned). */
  private findFollowPos(): { x: number; y: number } | null {
    const scene = this.game?.sceneManager?.activeScene?.()
    if (!scene) return null
    const entities = (scene as { entities?: Array<{ archetype?: string; position?: { x?: number; y?: number } }> }).entities
    if (!entities) return null
    for (const e of entities) {
      if (e.archetype === this.followArchetype && e.position) {
        return { x: e.position.x ?? 0, y: e.position.y ?? 0 }
      }
    }
    return null
  }
}

/** Default z-ordering: far = -10, through near = 0 (interpolated for
 *  mid layers). Single-layer → z = -5 (behind foreground, visually
 *  midrange). */
function _defaultZ(index: number, count: number): number {
  if (count === 1) return -5
  if (count === 2) return index === 0 ? -10 : 0
  // 3+ layers: linear-space -10 to 0
  return -10 + (10 * index) / (count - 1)
}

mechanicRegistry.register('ParallaxScroll', (instance, game) => {
  const rt = new ParallaxScrollRuntime(instance)
  rt.init(game)
  return rt
})
