/**
 * PoseCache — runtime cached SDF pose tile store.
 *
 * STARTER SKELETON. Per operator's "guiding principles, not strict canon"
 * (2026-04-27 directive), this is a sketch for review — not a final impl.
 * The chibi character pipeline at engine/src/character3d/raymarch_renderer.ts
 * is the existing SDF-render producer; PoseCache wraps it for the runtime
 * cached-iso-render architecture.
 *
 * Usage shape (tentative):
 *
 *   const cache = new PoseCache(device, { maxSizeMB: 100 })
 *   const tile = await cache.resolve({
 *     archetype: 'cecil',
 *     contextName: 'overworld',
 *     anim: 'walk_n',
 *     frame: 2,
 *     paletteVariant: 'default',
 *   })
 *   tile.blit(commandEncoder, screenX, screenY)
 *
 * Cache key composition: (archetype × contextName × anim × frame × paletteVariant)
 * Cache miss: invokes the SDF producer, renders to off-screen target, stores
 * Cache hit: returns existing GPUTexture handle
 * Eviction: LRU when budget exceeded
 *
 * Open questions (see PHASE2_BUNDLE_README.md for full list):
 *   - LRU budget per scaffold or global?
 *   - Pre-warm on scene load or pure lazy?
 *   - How does palette swap interact with cache (full evict vs per-tile flag)?
 *   - Where does the schema's render_contexts.scale apply (target dim or post-blit)?
 */

import type { Archetype, RenderContext, SdfSpec } from '../design/schema'

// ───────────────────────────────────────────────────────────────────
// Cache key
// ───────────────────────────────────────────────────────────────────

export interface PoseCacheKey {
  archetype: string         // archetype id
  contextName: string       // key into Archetype.render_contexts
  anim: string              // anim name from RenderContext.anims
  frame: number             // frame index in the anim sequence
  paletteVariant?: string   // optional alt palette (default: archetype's own palette)
  stance?: string           // optional, for stealth-style stance variants
}

function keyHash(k: PoseCacheKey): string {
  // Stable string key for Map lookup; cheap to compute, deterministic
  return `${k.archetype}|${k.contextName}|${k.stance ?? ''}|${k.anim}|${k.frame}|${k.paletteVariant ?? 'default'}`
}

// ───────────────────────────────────────────────────────────────────
// Tile (cached render output)
// ───────────────────────────────────────────────────────────────────

export interface CachedTile {
  texture: GPUTexture
  view: GPUTextureView
  width: number             // pixels
  height: number            // pixels
  bytesUsed: number         // for LRU accounting
  lastAccess: number        // monotonic ticks for LRU
}

// ───────────────────────────────────────────────────────────────────
// SDF producer interface (the operator's chibi raymarcher conforms)
// ───────────────────────────────────────────────────────────────────

export interface SdfProducer {
  /**
   * Render an SDF spec at a given camera + anim frame to a GPU texture.
   * Implementer: wrap engine/src/character3d/raymarch_renderer.ts here.
   */
  render(args: {
    sdf: SdfSpec
    context: RenderContext
    direction: number       // 0..directions-1 (e.g. 0=N, 1=E, 2=S, 3=W for 4-dir)
    anim: string
    frame: number
    targetWidth: number
    targetHeight: number
    palette?: Record<string, string>  // overrides archetype palette if set
  }): Promise<GPUTexture>
}

// ───────────────────────────────────────────────────────────────────
// PoseCache
// ───────────────────────────────────────────────────────────────────

export interface PoseCacheOptions {
  maxSizeMB?: number        // default 256 (~10K 64x96 tiles)
  defaultTileSize?: { width: number; height: number }
  // Hooks called from the runtime — operator can override
  onCacheMiss?: (key: PoseCacheKey) => void
  onEvict?: (key: PoseCacheKey, tile: CachedTile) => void
}

const DEFAULT_OPTS: Required<Pick<PoseCacheOptions, 'maxSizeMB' | 'defaultTileSize'>> = {
  maxSizeMB: 256,
  defaultTileSize: { width: 64, height: 96 },
}

export class PoseCache {
  private device: GPUDevice
  private producer: SdfProducer
  private opts: PoseCacheOptions & typeof DEFAULT_OPTS
  private store = new Map<string, CachedTile>()
  private bytesUsed = 0
  private accessTick = 0
  private archetypeRegistry = new Map<string, Archetype>()

  constructor(device: GPUDevice, producer: SdfProducer, opts: PoseCacheOptions = {}) {
    this.device = device
    this.producer = producer
    this.opts = { ...DEFAULT_OPTS, ...opts }
  }

  // Register archetype JSON so resolve() can look up sdf + render_contexts
  register(archetypeId: string, archetype: Archetype): void {
    this.archetypeRegistry.set(archetypeId, archetype)
  }

  /**
   * Resolve a pose tile — cache hit returns immediately, miss invokes
   * producer.render() and stores the result.
   */
  async resolve(key: PoseCacheKey): Promise<CachedTile> {
    const hash = keyHash(key)
    const cached = this.store.get(hash)
    if (cached) {
      cached.lastAccess = ++this.accessTick
      return cached
    }
    this.opts.onCacheMiss?.(key)

    const archetype = this.archetypeRegistry.get(key.archetype)
    if (!archetype || !archetype.sdf) {
      throw new Error(`PoseCache: archetype "${key.archetype}" missing or has no sdf spec`)
    }
    const context = archetype.render_contexts?.[key.contextName]
    if (!context) {
      throw new Error(`PoseCache: archetype "${key.archetype}" has no render_context "${key.contextName}"`)
    }

    // Compute target dimensions from default tile size × context.scale
    const scale = context.scale ?? 1.0
    const targetWidth = Math.round(this.opts.defaultTileSize.width * scale)
    const targetHeight = Math.round(this.opts.defaultTileSize.height * scale)

    // Direction is computed from anim name conventionally (e.g. "walk_n" → 0)
    // OR could be an explicit param; for now derive from anim suffix
    const direction = deriveDirectionFromAnim(key.anim, context.directions)

    const texture = await this.producer.render({
      sdf: archetype.sdf,
      context,
      direction,
      anim: key.anim,
      frame: key.frame,
      targetWidth,
      targetHeight,
      palette: undefined,  // for paletteVariant: extend later
    })

    const view = texture.createView()
    const bytes = targetWidth * targetHeight * 4  // RGBA8
    const tile: CachedTile = {
      texture, view, width: targetWidth, height: targetHeight,
      bytesUsed: bytes, lastAccess: ++this.accessTick,
    }

    this.store.set(hash, tile)
    this.bytesUsed += bytes
    this.evictIfOverBudget()
    return tile
  }

  /**
   * Drop tiles for an archetype (e.g. on archetype data change or on
   * scene unload).
   */
  invalidateArchetype(archetypeId: string): void {
    for (const [hash, tile] of this.store.entries()) {
      if (hash.startsWith(`${archetypeId}|`)) {
        this.store.delete(hash)
        this.bytesUsed -= tile.bytesUsed
        tile.texture.destroy()
        // Note: structural cache key parse — could use a parsed key form for safety
      }
    }
  }

  private evictIfOverBudget(): void {
    const budgetBytes = this.opts.maxSizeMB * 1024 * 1024
    if (this.bytesUsed <= budgetBytes) return

    // Sort by lastAccess (LRU first), evict until under budget
    const entries = Array.from(this.store.entries()).sort(
      (a, b) => a[1].lastAccess - b[1].lastAccess
    )
    while (this.bytesUsed > budgetBytes && entries.length > 0) {
      const [hash, tile] = entries.shift()!
      this.store.delete(hash)
      this.bytesUsed -= tile.bytesUsed
      tile.texture.destroy()
      // Optional: emit onEvict via parsed key
    }
  }

  // Diagnostics
  stats(): { tiles: number; bytesUsed: number; budgetBytes: number } {
    return {
      tiles: this.store.size,
      bytesUsed: this.bytesUsed,
      budgetBytes: this.opts.maxSizeMB * 1024 * 1024,
    }
  }
}

// ───────────────────────────────────────────────────────────────────
// Helpers
// ───────────────────────────────────────────────────────────────────

function deriveDirectionFromAnim(anim: string, directionCount: 1 | 2 | 4 | 8): number {
  // Convention: "walk_n" / "walk_ne" / "walk_e" suffix → direction index
  // 4-dir: n=0, e=1, s=2, w=3
  // 8-dir: n=0, ne=1, e=2, se=3, s=4, sw=5, w=6, nw=7
  // 1-dir: always 0 (no direction encoding needed in anim name)
  // 2-dir: l=0, r=1 (face-left vs face-right)
  if (directionCount === 1) return 0
  const suffix = anim.split('_').pop()?.toLowerCase()
  if (directionCount === 2) {
    return suffix === 'l' ? 0 : 1
  }
  if (directionCount === 4) {
    return { n: 0, e: 1, s: 2, w: 3 }[suffix ?? ''] ?? 0
  }
  if (directionCount === 8) {
    return { n: 0, ne: 1, e: 2, se: 3, s: 4, sw: 5, w: 6, nw: 7 }[suffix ?? ''] ?? 0
  }
  return 0
}

// ───────────────────────────────────────────────────────────────────
// Sketch of the per-frame compositor (for context only — not impl)
// ───────────────────────────────────────────────────────────────────
//
// The render loop becomes (after PoseCache lands):
//
//   await Promise.all(visibleEntities.map(e =>
//     cache.resolve({ archetype: e.archetype, contextName: scene.context, anim: e.anim, frame: e.frame })
//   ))
//
//   for entity of visibleEntities sorted by yGrid:
//     pass.draw(entity.tile, screenX, screenY)
//     stamp entity.face_pixels at projected face anchor
//     stamp entity.shirt_pixels at projected chest anchor
//     stamp entity.overhead_pixels if alert state set
//
//   for particle of activeParticles:
//     screenX = floor(world_to_screen_x(particle.pos.x))
//     screenY = floor(world_to_screen_y(particle.pos.y))
//     stamp particle.preset[particle.frame] at (screenX, screenY)
//
// The compositor lives outside PoseCache. It's the operator's render-loop
// integration point.
