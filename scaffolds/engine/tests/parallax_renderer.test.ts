/**
 * parallax_renderer.ts — tests the Canvas2D blit logic.
 *
 * Uses a mock 2D context to verify drawImage call patterns + layer
 * ordering. No real canvas needed.
 */

import { describe, it, expect, vi } from 'vitest'
import {
  drawParallaxLayers,
  layerTileCount,
  type LayerOffset,
  type LoadedSprite,
  type SpriteResolver,
} from '../src/sprites/parallax_renderer'

function makeMockCtx(width = 800, height = 600) {
  const drawCalls: Array<{ id?: string; x: number; y: number; w: number; h: number }> = []
  const ctx = {
    canvas: { width, height },
    drawImage: vi.fn((img: any, x: number, y: number, w: number, h: number) => {
      drawCalls.push({ id: img.__id, x, y, w, h })
    }),
  } as any
  return { ctx, drawCalls }
}

function makeSprite(id: string, w: number, h: number): LoadedSprite {
  const image = { __id: id } as any
  return { image, width: w, height: h }
}

function makeResolver(map: Record<string, LoadedSprite>): SpriteResolver {
  return (id: string) => map[id] ?? null
}

describe('parallax_renderer', () => {
  it('draws one tile when offset is zero + loops=true', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprite = makeSprite('far', 3200, 224)
    const resolve = makeResolver({ far: sprite })
    const layers: LayerOffset[] = [
      { sprite_id: 'far', offset_x: 0, offset_y: 0, layer_z: -10, loops_horizontally: true },
    ]
    const drawn = drawParallaxLayers(ctx, layers, resolve)
    expect(drawn).toBe(1)
    // 3200 >> 800 so 1 tile suffices
    expect(drawCalls).toHaveLength(1)
    expect(drawCalls[0].id).toBe('far')
    expect(drawCalls[0].x).toBe(0)
  })

  it('wraps horizontal tiles when sprite is narrower than viewport', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprite = makeSprite('tiled', 300, 224)  // needs to wrap
    const resolve = makeResolver({ tiled: sprite })
    const layers: LayerOffset[] = [
      { sprite_id: 'tiled', offset_x: 0, offset_y: 0, layer_z: 0, loops_horizontally: true },
    ]
    const drawn = drawParallaxLayers(ctx, layers, resolve)
    expect(drawn).toBe(1)
    // 800 / 300 = 2.67, so 3 tiles covering positions 0, 300, 600
    expect(drawCalls.length).toBeGreaterThanOrEqual(3)
    expect(drawCalls[0].x).toBe(0)
    expect(drawCalls[1].x).toBe(300)
  })

  it('applies negative screen_x when scrolled right', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprite = makeSprite('far', 400, 224)
    const resolve = makeResolver({ far: sprite })
    const layers: LayerOffset[] = [
      { sprite_id: 'far', offset_x: 100, offset_y: 0, layer_z: -10, loops_horizontally: true },
    ]
    drawParallaxLayers(ctx, layers, resolve)
    // offset=100 means content moved LEFT by 100px. screen_x = -100.
    // But wrap moves into [-400, 0): -100 is already in that range.
    expect(drawCalls[0].x).toBe(-100)
    expect(drawCalls[1].x).toBe(300)
  })

  it('no-loops sprites draw once at negative-offset location', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprite = makeSprite('skybox', 800, 600)
    const resolve = makeResolver({ skybox: sprite })
    const layers: LayerOffset[] = [
      { sprite_id: 'skybox', offset_x: 50, offset_y: 10, layer_z: -100, loops_horizontally: false },
    ]
    drawParallaxLayers(ctx, layers, resolve)
    expect(drawCalls).toHaveLength(1)
    expect(drawCalls[0].x).toBe(-50)
    expect(drawCalls[0].y).toBe(-10)
  })

  it('sorts layers by z ascending (far drawn first)', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprites = {
      near: makeSprite('near', 3200, 224),
      mid:  makeSprite('mid',  3200, 224),
      far:  makeSprite('far',  3200, 224),
    }
    const resolve = makeResolver(sprites)
    // Deliberately out of z-order in input
    const layers: LayerOffset[] = [
      { sprite_id: 'near', offset_x: 0, offset_y: 0, layer_z: 0, loops_horizontally: true },
      { sprite_id: 'far',  offset_x: 0, offset_y: 0, layer_z: -10, loops_horizontally: true },
      { sprite_id: 'mid',  offset_x: 0, offset_y: 0, layer_z: -5, loops_horizontally: true },
    ]
    drawParallaxLayers(ctx, layers, resolve)
    // First call should be 'far' (lowest z), last should be 'near'
    expect(drawCalls[0].id).toBe('far')
    expect(drawCalls[drawCalls.length - 1].id).toBe('near')
  })

  it('preserves call order when sort_by_z is false', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const sprites = {
      a: makeSprite('a', 3200, 224),
      b: makeSprite('b', 3200, 224),
    }
    const resolve = makeResolver(sprites)
    const layers: LayerOffset[] = [
      { sprite_id: 'a', offset_x: 0, offset_y: 0, layer_z: 5, loops_horizontally: true },
      { sprite_id: 'b', offset_x: 0, offset_y: 0, layer_z: -5, loops_horizontally: true },
    ]
    drawParallaxLayers(ctx, layers, resolve, { sort_by_z: false })
    // Preserves input order
    expect(drawCalls[0].id).toBe('a')
    expect(drawCalls[1].id).toBe('b')
  })

  it('skips unresolved sprites silently', () => {
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const resolve = makeResolver({ 'exists': makeSprite('exists', 800, 600) })
    const layers: LayerOffset[] = [
      { sprite_id: 'missing', offset_x: 0, offset_y: 0, layer_z: 0, loops_horizontally: false },
      { sprite_id: 'exists',  offset_x: 0, offset_y: 0, layer_z: 0, loops_horizontally: false },
    ]
    const drawn = drawParallaxLayers(ctx, layers, resolve)
    expect(drawn).toBe(1)
    expect(drawCalls).toHaveLength(1)
    expect(drawCalls[0].id).toBe('exists')
  })

  it('layerTileCount computes wrap count correctly', () => {
    expect(layerTileCount(800, 800)).toBe(2)     // exactly fits + 1 safety
    expect(layerTileCount(400, 800)).toBe(3)     // 2 tiles + 1 safety
    expect(layerTileCount(3200, 800)).toBe(2)    // ceil(800/3200) + 1 = 1 + 1 = 2 (safety tile)
    expect(layerTileCount(0, 800)).toBe(1)       // degenerate guard
  })
})
