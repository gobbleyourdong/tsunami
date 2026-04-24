/**
 * Canvas2D renderer for parallax backdrop layers.
 *
 * Consumes the output of `ParallaxScroll.expose().layer_offsets` and
 * paints each layer into a Canvas2D context. Small, dependency-light,
 * testable — intended for scaffolds that want parallax without the full
 * WebGPU pipeline. WebGPU-based scaffolds use the same expose() output
 * with their own texture-quad renderer.
 *
 * Horizontal looping is done via repeat-tile: if the source image is
 * N pixels wide and the offset is negative, we paint enough copies
 * left + right to cover the viewport. Vertical handled identically when
 * the layer isn't `lock_y`.
 */

/** Shape of a single layer entry — matches `ParallaxScroll.expose()`. */
export interface LayerOffset {
  sprite_id: string
  offset_x: number
  offset_y: number
  layer_z: number
  loops_horizontally?: boolean
}

/** Shape of a loaded sprite — from the runtime manifest (loader.ts). */
export interface LoadedSprite {
  /** Rendered image. Canvas2D accepts `HTMLImageElement | ImageBitmap |
   *  HTMLCanvasElement | OffscreenCanvas` via `CanvasImageSource`. */
  image: CanvasImageSource
  /** Source-image width in CSS pixels. */
  width: number
  /** Source-image height in CSS pixels. */
  height: number
}

/** Sprite resolver — looks up a loaded sprite by id. Scaffolds wire
 *  this to their own image-cache (backed by loader.ts `SpriteManifest`
 *  entries + decoded `HTMLImageElement`). Returning `null` means the
 *  sprite isn't loaded yet; the renderer skips that layer for this frame. */
export type SpriteResolver = (sprite_id: string) => LoadedSprite | null

export interface ParallaxRenderOptions {
  /** Optional viewport size. If omitted, uses ctx.canvas dimensions. */
  viewport_w?: number
  viewport_h?: number
  /** Whether to sort layers by layer_z ascending before draw (back-to-front).
   *  Default true — Canvas2D draws in call-order, so this ensures far →
   *  near painter's algorithm. */
  sort_by_z?: boolean
}

/**
 * Draw the parallax layers. Call each frame after ParallaxScroll.update().
 *
 * The `offset_x/y` from ParallaxScroll represents the scroll DISTANCE
 * the layer has traveled. Canvas-side, that means the image shifts by
 * `-offset_x` (scrolling right = content moves left under the camera).
 *
 * @param ctx       destination Canvas2D context
 * @param layers    output of `mechanic.expose().layer_offsets`
 * @param resolve   sprite-id → loaded image (or null if not ready)
 * @param opts      viewport + sort config
 * @returns number of layers actually drawn
 */
export function drawParallaxLayers(
  ctx: CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D,
  layers: LayerOffset[],
  resolve: SpriteResolver,
  opts: ParallaxRenderOptions = {},
): number {
  const canvasW = opts.viewport_w ?? (ctx.canvas as HTMLCanvasElement).width
  const canvasH = opts.viewport_h ?? (ctx.canvas as HTMLCanvasElement).height

  const ordered = (opts.sort_by_z ?? true)
    ? [...layers].sort((a, b) => a.layer_z - b.layer_z)
    : layers

  let drawn = 0
  for (const layer of ordered) {
    const sprite = resolve(layer.sprite_id)
    if (!sprite) continue
    drawn++

    // Compute the screen-x of the layer's origin. Negative offset scrolls
    // the content LEFT (camera moved right). Modulo into [0, -width) so
    // tiling is well-defined regardless of total distance scrolled.
    let screen_x = -layer.offset_x
    let screen_y = -layer.offset_y
    const loops = layer.loops_horizontally ?? true

    if (loops && sprite.width > 0) {
      // Wrap screen_x into [-sprite.width, 0) so the first tile starts
      // at-or-left-of the viewport left edge. `| 0` coerces any -0 to +0.
      screen_x = (screen_x % sprite.width) | 0
      if (screen_x > 0) screen_x -= sprite.width
      screen_y = screen_y | 0
      // Paint tiles covering the viewport horizontally.
      for (let x = screen_x; x < canvasW; x += sprite.width) {
        ctx.drawImage(sprite.image, x, screen_y, sprite.width, sprite.height)
      }
    } else {
      ctx.drawImage(sprite.image, screen_x | 0, screen_y | 0, sprite.width, sprite.height)
    }
  }
  return drawn
}

/**
 * Convenience: compute the number of tile repeats needed to cover the
 * viewport width at the given scroll state. Used by tests + performance
 * instrumentation.
 */
export function layerTileCount(
  sprite_width: number, viewport_w: number,
): number {
  if (sprite_width <= 0) return 1
  return Math.ceil(viewport_w / sprite_width) + 1
}
