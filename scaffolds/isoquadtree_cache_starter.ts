/**
 * IsoQuadtreeCache — 2D iso-aligned spatial cache for raymarched static
 * scene content. Companion to PoseCache (which keys on archetype-pose).
 *
 * STARTER SKELETON. Per operator's "guiding principles, not strict canon"
 * (2026-04-27 directive), this is a sketch for review. Architecture
 * lives in scaffolds/ISO_QUADTREE_CACHE.md.
 *
 * Two cache stores collaborate:
 *   IsoQuadtreeCache  — static spatial regions per layer (bg, mid, ...)
 *   PoseCache         — dynamic per-archetype pose tiles (fg entities)
 *
 * Both feed the compositor's per-frame layer blit.
 *
 * Why iso-quadtree (2D) instead of octree (3D):
 *   - Iso camera is fixed, so world XZ bijects to screen-space parallelogram
 *   - Static geometry only needs caching at the projected resolution
 *   - Vertical extent is bounded per region (max building height) → bake tile = 2D
 *   - Layer separation lets FG moves not invalidate BG cache
 *
 * Cosmetic-animation strategy:
 *   - Cached tile holds palette indices, not RGB
 *   - Palette LUT cycled at blit time → animated water/grass without re-march
 *   - Vertex-deform shader pass for sway → cached tile stays static
 *   - Pixel-grid stamps for sparkles/particles → never cached, always per-frame
 *
 * Hard cases that DO trigger re-raymarch:
 *   - Building destroyed → invalidateRegion covering its footprint
 *   - World content edited → per-affected-node invalidation
 */

import type { SdfPrimitive } from '../design/schema'
import type { SdfProducer } from './posecache_starter'  // adjust import path when integrated

// ───────────────────────────────────────────────────────────────────
// Layer model
// ───────────────────────────────────────────────────────────────────

/** Named layer — operator-defined; canonical set is bg / mid / fg / particle / ui. */
export type LayerName = 'bg' | 'mid' | string

export interface LayerConfig {
  name: LayerName
  zOrder: number          // smaller = drawn first (further back)
  cosmetic?: {
    /** Palette cycling — multiple LUTs picked by frame index at blit time */
    paletteCycle?: { lutCount: number; framesPerLut: number }
    /** Sway/displacement shader applied at blit time */
    sway?: { amplitudePixels: number; frequencyHz: number }
  }
}

// ───────────────────────────────────────────────────────────────────
// Quadtree node + cache key
// ───────────────────────────────────────────────────────────────────

export interface QuadtreeNodeId {
  depth: number          // 0 = root, +1 per subdivision
  xIdx: number           // grid index at this depth
  zIdx: number
}

export interface QuadtreeBounds {
  xMin: number; xMax: number
  zMin: number; zMax: number
  yMaxObserved?: number  // tracked from contained primitives for vertical extent
}

export interface IsoCacheKey {
  layer: LayerName
  nodeId: QuadtreeNodeId
  paletteVariant?: string   // default 'default'
}

function keyHash(k: IsoCacheKey): string {
  const n = k.nodeId
  return `${k.layer}|${n.depth}:${n.xIdx},${n.zIdx}|${k.paletteVariant ?? 'default'}`
}

// ───────────────────────────────────────────────────────────────────
// Cached spatial tile
// ───────────────────────────────────────────────────────────────────

export interface SpatialTile {
  texture: GPUTexture
  view: GPUTextureView
  pixelWidth: number
  pixelHeight: number
  bytesUsed: number
  lastAccess: number

  /** Cosmetic flags — picked up by the compositor's blit shader */
  paletteDirty?: boolean    // re-look-up palette LUT next blit
  swayActive?: boolean

  /** Bounds + screen projection for the compositor */
  worldBounds: QuadtreeBounds
  screenOriginX: number
  screenOriginY: number
}

// ───────────────────────────────────────────────────────────────────
// IsoQuadtreeCache
// ───────────────────────────────────────────────────────────────────

export interface IsoQuadtreeCacheOptions {
  /** Total VRAM budget across all layers + nodes (default 256MB). */
  maxSizeMB?: number

  /** Pixel size per world-tile-unit at iso projection (default 64). */
  isoTilePixelSize?: number

  /** Max depth before we stop subdividing (default 5 = up to 1024 leaves). */
  maxQuadtreeDepth?: number

  /**
   * Producer for region-bounded raymarches. The chibi raymarcher
   * (engine/src/character3d/raymarch_renderer.ts) needs a `renderRegion`
   * method added; for now we extend SdfProducer.
   */
  producer: SdfProducerWithRegion
}

/** Extended SdfProducer with region-bounded render for spatial caching. */
export interface SdfProducerWithRegion extends SdfProducer {
  renderRegion(args: {
    sdfPrimitives: SdfPrimitive[]
    bounds: QuadtreeBounds
    palette: Record<string, string>
    targetWidth: number
    targetHeight: number
  }): Promise<GPUTexture>
}

const DEFAULTS = {
  maxSizeMB: 256,
  isoTilePixelSize: 64,
  maxQuadtreeDepth: 5,
}

export class IsoQuadtreeCache {
  private device: GPUDevice
  private opts: IsoQuadtreeCacheOptions & typeof DEFAULTS
  private store = new Map<string, SpatialTile>()
  private bytesUsed = 0
  private accessTick = 0

  /** Layer registry — render-order + cosmetic config */
  private layers = new Map<LayerName, LayerConfig>()

  /** All SDF primitives in the world, indexed for region queries */
  private worldPrimitives = new Map<LayerName, SdfPrimitive[]>()

  constructor(device: GPUDevice, opts: IsoQuadtreeCacheOptions) {
    this.device = device
    this.opts = { ...DEFAULTS, ...opts }
  }

  registerLayer(cfg: LayerConfig): void {
    this.layers.set(cfg.name, cfg)
    this.worldPrimitives.set(cfg.name, [])
  }

  /** Add static SDF primitives to a layer (e.g. baking a town). */
  addPrimitives(layer: LayerName, primitives: SdfPrimitive[]): void {
    const list = this.worldPrimitives.get(layer)
    if (!list) throw new Error(`Layer "${layer}" not registered`)
    list.push(...primitives)
    // Caller can call invalidateRegion afterward to drop affected cached nodes
  }

  /**
   * Resolve a tile for a quadtree node — bake on cache miss.
   */
  async resolve(key: IsoCacheKey, palette: Record<string, string>): Promise<SpatialTile> {
    const hash = keyHash(key)
    const cached = this.store.get(hash)
    if (cached) {
      cached.lastAccess = ++this.accessTick
      return cached
    }

    const bounds = this.boundsForNode(key.nodeId)
    const primitives = this.queryPrimitivesInBounds(key.layer, bounds)
    const tileDims = this.computeTileDims(bounds)

    const texture = await this.opts.producer.renderRegion({
      sdfPrimitives: primitives,
      bounds,
      palette,
      targetWidth: tileDims.width,
      targetHeight: tileDims.height,
    })

    const view = texture.createView()
    const bytes = tileDims.width * tileDims.height * 4
    const tile: SpatialTile = {
      texture, view,
      pixelWidth: tileDims.width,
      pixelHeight: tileDims.height,
      bytesUsed: bytes,
      lastAccess: ++this.accessTick,
      worldBounds: bounds,
      screenOriginX: this.worldXZToScreenX(bounds.xMin, bounds.zMin),
      screenOriginY: this.worldXZToScreenY(bounds.xMin, bounds.zMin),
    }
    this.store.set(hash, tile)
    this.bytesUsed += bytes
    this.evictIfOverBudget()
    return tile
  }

  /** Drop cached tiles for nodes whose bounds intersect a region. */
  invalidateRegion(args: { layer: LayerName; bounds: QuadtreeBounds }): void {
    const toDelete: string[] = []
    for (const [hash, tile] of this.store.entries()) {
      if (!hash.startsWith(`${args.layer}|`)) continue
      if (this.boundsOverlap(tile.worldBounds, args.bounds)) {
        toDelete.push(hash)
      }
    }
    for (const hash of toDelete) {
      const tile = this.store.get(hash)!
      tile.texture.destroy()
      this.bytesUsed -= tile.bytesUsed
      this.store.delete(hash)
    }
  }

  /** Mark tiles palette-dirty (no re-march, just LUT swap at next blit). */
  markPaletteDirty(args: { layer: LayerName; paletteVariant?: string }): void {
    const variant = args.paletteVariant ?? 'default'
    for (const [hash, tile] of this.store.entries()) {
      if (hash.startsWith(`${args.layer}|`) && hash.endsWith(`|${variant}`)) {
        tile.paletteDirty = true
      }
    }
  }

  /** Set sway-active flag for tiles (used by compositor's blit shader). */
  setSway(args: { layer: LayerName; active: boolean }): void {
    for (const [hash, tile] of this.store.entries()) {
      if (hash.startsWith(`${args.layer}|`)) {
        tile.swayActive = args.active
      }
    }
  }

  /** Visibility query — which nodes need to be drawn for this camera frustum? */
  queryVisible(viewBounds: QuadtreeBounds, layer: LayerName): QuadtreeNodeId[] {
    // Simple version: enumerate nodes at maxDepth whose bounds overlap viewBounds
    // Real impl: walk quadtree top-down, descending only into overlapping subtrees
    const visible: QuadtreeNodeId[] = []
    const depth = this.opts.maxQuadtreeDepth
    const cellsPerSide = 1 << depth
    const worldXSize = this.opts.isoTilePixelSize * 64  // arbitrary world size; should come from scene config
    const cellSize = worldXSize / cellsPerSide
    // Iterate over candidate cells
    const xMinIdx = Math.max(0, Math.floor(viewBounds.xMin / cellSize))
    const xMaxIdx = Math.min(cellsPerSide - 1, Math.ceil(viewBounds.xMax / cellSize))
    const zMinIdx = Math.max(0, Math.floor(viewBounds.zMin / cellSize))
    const zMaxIdx = Math.min(cellsPerSide - 1, Math.ceil(viewBounds.zMax / cellSize))
    for (let x = xMinIdx; x <= xMaxIdx; x++) {
      for (let z = zMinIdx; z <= zMaxIdx; z++) {
        visible.push({ depth, xIdx: x, zIdx: z })
      }
    }
    return visible
  }

  // Diagnostics
  stats(): { tiles: number; bytesUsed: number; budgetBytes: number; layers: number } {
    return {
      tiles: this.store.size,
      bytesUsed: this.bytesUsed,
      budgetBytes: this.opts.maxSizeMB * 1024 * 1024,
      layers: this.layers.size,
    }
  }

  // ─────────────────────────────────────────────────────────────────
  // Internals
  // ─────────────────────────────────────────────────────────────────

  private boundsForNode(nodeId: QuadtreeNodeId): QuadtreeBounds {
    const cellsPerSide = 1 << nodeId.depth
    const worldXSize = this.opts.isoTilePixelSize * 64  // see queryVisible note
    const cellSize = worldXSize / cellsPerSide
    return {
      xMin: nodeId.xIdx * cellSize,
      xMax: (nodeId.xIdx + 1) * cellSize,
      zMin: nodeId.zIdx * cellSize,
      zMax: (nodeId.zIdx + 1) * cellSize,
    }
  }

  private queryPrimitivesInBounds(layer: LayerName, bounds: QuadtreeBounds): SdfPrimitive[] {
    // Simple AABB filter; for high-density scenes wrap with a 2D index
    const all = this.worldPrimitives.get(layer) ?? []
    return all.filter(p => {
      const x = p.offset[0]
      const z = p.offset[2]
      // Conservative inclusion: any primitive whose origin is in the region OR within ~radius outside
      const r = (p.radius ?? 0.5) + 0.5
      return x + r >= bounds.xMin && x - r <= bounds.xMax
          && z + r >= bounds.zMin && z - r <= bounds.zMax
    })
  }

  private computeTileDims(bounds: QuadtreeBounds): { width: number; height: number } {
    // 2:1 dimetric: x and z both contribute to screen x and y
    const isoTile = this.opts.isoTilePixelSize
    const wWorld = bounds.xMax - bounds.xMin
    const hWorld = bounds.zMax - bounds.zMin
    const yExtent = (bounds.yMaxObserved ?? 4)  // default reserve for ~4 world-units of vertical content
    return {
      width: Math.ceil((wWorld + hWorld) * isoTile * 0.866),  // cos(30°) ≈ 0.866
      height: Math.ceil((wWorld + hWorld) * isoTile * 0.5 + yExtent * isoTile),  // sin(30°) = 0.5
    }
  }

  private worldXZToScreenX(x: number, z: number): number {
    return (x - z) * this.opts.isoTilePixelSize * 0.866
  }

  private worldXZToScreenY(x: number, z: number): number {
    return (x + z) * this.opts.isoTilePixelSize * 0.5
  }

  private boundsOverlap(a: QuadtreeBounds, b: QuadtreeBounds): boolean {
    return a.xMax > b.xMin && a.xMin < b.xMax
        && a.zMax > b.zMin && a.zMin < b.zMax
  }

  private evictIfOverBudget(): void {
    const budgetBytes = this.opts.maxSizeMB * 1024 * 1024
    if (this.bytesUsed <= budgetBytes) return
    const entries = Array.from(this.store.entries()).sort(
      (a, b) => a[1].lastAccess - b[1].lastAccess
    )
    while (this.bytesUsed > budgetBytes && entries.length > 0) {
      const [hash, tile] = entries.shift()!
      tile.texture.destroy()
      this.bytesUsed -= tile.bytesUsed
      this.store.delete(hash)
    }
  }
}

// ───────────────────────────────────────────────────────────────────
// Compositor sketch (read-only — actual impl is in render loop)
// ───────────────────────────────────────────────────────────────────
//
// Per-frame composition combines IsoQuadtreeCache and PoseCache outputs:
//
//   const visibleViewBounds = camera.xzBoundsFromFrustum()
//
//   for layer of [bg, mid] sorted by zOrder:                  // IsoQuadtreeCache layers
//     for nodeId of isoCache.queryVisible(visibleViewBounds, layer):
//       const tile = await isoCache.resolve({ layer, nodeId }, currentPalette)
//       blitWithCosmeticShader(tile, /* picks palette LUT and sway based on cfg */)
//
//   for entity of fgEntities sorted by Y-grid:                // PoseCache layer
//     const tile = await poseCache.resolve(entity.poseKey())
//     blit(tile, entity.screenPos())
//     stampPixelGrid(entity.face_pixels, entity.faceAnchor)
//     if (entity.alertState) stampPixelGrid(entity.overhead_pixels, entity.aboveHeadAnchor)
//
//   for particle of activeParticles:                          // particle layer
//     const stamp = particleLib[particle.preset][particle.frame]
//     stampPixelGrid(stamp, [floor(p.screenX), floor(p.screenY)])
//
//   drawUI()                                                  // top-most layer
//
// Total per-frame cost (after warmup): O(visible nodes × layers + visible entities + active particles).
// All blits, no raymarching.
