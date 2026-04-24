/**
 * End-to-end integration test — exercises the FULL parallax pipeline
 * across all 5 sprite modules + the ParallaxScroll mechanic + the
 * mechanic registry. Proves scaffold-author code like this works:
 *
 *   await loadExtractionIndex(['1991_sonic_the_hedgehog'])
 *   const inst = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player')
 *   const rt = mechanicRegistry.create(inst!, game)
 *   // ... each frame:
 *   rt.update(dt)
 *   drawParallaxLayers(ctx, rt.expose().layer_offsets, spriteResolver)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mechanicRegistry } from '../src/design/mechanics/index'
import '../src/design/mechanics/parallax_scroll'
import {
  loadExtractionIndex,
  resetExtractionIndex,
  type SpriteSheetManifest,
} from '../src/sprites/kind_index'
import { configureParallax3LayerFromEssence } from '../src/sprites/parallax_setup'
import { drawParallaxLayers, type LoadedSprite } from '../src/sprites/parallax_renderer'

const SHEET: SpriteSheetManifest = {
  game_stem: '1991_sonic_the_hedgehog',
  sheet_title: 'green hill',
  animations: [
    {
      name: 'gh_far', kind: 'background_layer', sub_kind: 'parallax_far',
      pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
      progression_description: 'far', inferred: false, confidence: 0.9,
      background_params: { layer_position: 'far', scroll_speed_ratio: 0.25, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
    } as any,
    {
      name: 'gh_mid', kind: 'background_layer', sub_kind: 'parallax_mid',
      pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
      progression_description: 'mid', inferred: false, confidence: 0.9,
      background_params: { layer_position: 'mid', scroll_speed_ratio: 0.5, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
    } as any,
    {
      name: 'gh_near', kind: 'background_layer', sub_kind: 'parallax_near',
      pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
      progression_description: 'near', inferred: false, confidence: 0.9,
      background_params: { layer_position: 'near', scroll_speed_ratio: 0.75, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
    } as any,
  ],
}

const URL_RE = /\/sprite_sheets\/([^/]+)\/(.+)$/

beforeEach(() => {
  resetExtractionIndex()
  ;(globalThis as any).fetch = vi.fn(async (url: string) => {
    const m = URL_RE.test(url) ? url.match(URL_RE) : null
    if (!m) return { ok: false, status: 404, statusText: 'nm', json: async () => ({}) }
    const essence = m[1], file = m[2]
    if (essence !== '1991_sonic_the_hedgehog') return { ok: false, status: 404, statusText: 'nf', json: async () => ({}) }
    if (file === '_index.json') return { ok: true, status: 200, statusText: 'ok', json: async () => ['sheet_001.json'] }
    if (file === 'sheet_001.json') return { ok: true, status: 200, statusText: 'ok', json: async () => SHEET }
    return { ok: false, status: 404, statusText: 'nf', json: async () => ({}) }
  })
})

function makeMockCtx(w = 800, h = 600) {
  const drawCalls: Array<{ id: string; x: number; y: number }> = []
  const ctx = {
    canvas: { width: w, height: h },
    drawImage: vi.fn((img: any, x: number, y: number) => {
      drawCalls.push({ id: img.__id, x, y })
    }),
  } as any
  return { ctx, drawCalls }
}

function makeGame(playerX: number, playerY: number) {
  const scene = {
    entities: [{ archetype: 'player', position: { x: playerX, y: playerY } }],
  }
  return {
    scene,
    sceneManager: { activeScene: () => scene },
  }
}

function makeResolver(): (id: string) => LoadedSprite | null {
  return (id: string) => ({
    image: { __id: id } as any,
    width: 3200,
    height: 224,
  })
}

describe('parallax_e2e — full pipeline', () => {
  it('scaffold-author 4-step flow produces scrolled draw calls', async () => {
    // Step 1: load the extraction index (stubbed fetch feeds the fixture)
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])

    // Step 2: configure the mechanic from the loaded data
    const instance = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)
    expect(instance).not.toBeNull()

    // Step 3: register it with a game context
    const game = makeGame(0, 0)
    const rt = mechanicRegistry.create(instance!, game as any)
    expect(rt).not.toBeNull()

    // Step 4: simulate a frame — move the player + update + render
    game.scene.entities[0].position.x = 1000
    rt!.update(1 / 60)

    const exposed = rt!.expose!() as any
    expect(exposed.layer_offsets).toHaveLength(3)
    // far: 1000 * 0.25 = 250, mid: 500, near: 750
    expect(exposed.layer_offsets[0].offset_x).toBeCloseTo(250)
    expect(exposed.layer_offsets[1].offset_x).toBeCloseTo(500)
    expect(exposed.layer_offsets[2].offset_x).toBeCloseTo(750)

    // Step 5: render to Canvas2D
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    const drawn = drawParallaxLayers(ctx, exposed.layer_offsets, makeResolver())
    expect(drawn).toBe(3)
    // Each 3200-wide sprite covers the 800-wide viewport with 1 tile
    // (sprite wider than viewport → 1 draw per layer = 3 total)
    expect(drawCalls).toHaveLength(3)
    // Draw order: far first (lowest z), then mid, then near
    expect(drawCalls.map((c) => c.id)).toEqual(['gh_far', 'gh_mid', 'gh_near'])
    // Scrolled positions: -250, -500, -750 (content shifted left)
    expect(drawCalls[0].x).toBe(-250)
    expect(drawCalls[1].x).toBe(-500)
    expect(drawCalls[2].x).toBe(-750)

    rt!.dispose()
  })

  it('multi-frame accumulation produces consistent draw pattern', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const instance = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)!
    const game = makeGame(0, 0)
    const rt = mechanicRegistry.create(instance, game as any)!

    // Simulate 5 frames, each moving the player 200 units right
    for (let frame = 1; frame <= 5; frame++) {
      game.scene.entities[0].position.x = frame * 200
      rt.update(1 / 60)
    }

    const exposed = rt.expose!() as any
    // Cumulative offset after 5 × 200 = 1000 world-units
    // far: 1000 * 0.25 = 250
    // mid: 500
    // near: 750
    expect(exposed.layer_offsets[0].offset_x).toBeCloseTo(250)
    expect(exposed.layer_offsets[1].offset_x).toBeCloseTo(500)
    expect(exposed.layer_offsets[2].offset_x).toBeCloseTo(750)

    // Render one more time and verify draw positions
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    drawParallaxLayers(ctx, exposed.layer_offsets, makeResolver())
    expect(drawCalls[0].x).toBe(-250)
    expect(drawCalls[2].x).toBe(-750)
    rt.dispose()
  })

  it('player backing up (negative delta) reverses scroll', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const instance = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)!
    const game = makeGame(0, 0)
    const rt = mechanicRegistry.create(instance, game as any)!

    game.scene.entities[0].position.x = 500
    rt.update(1 / 60)
    game.scene.entities[0].position.x = 300  // back 200 units
    rt.update(1 / 60)

    const exposed = rt.expose!() as any
    // Cumulative: +500*0.25 - 200*0.25 = +75 for far
    expect(exposed.layer_offsets[0].offset_x).toBeCloseTo(75)
    rt.dispose()
  })

  it('wrap tiling kicks in when sprite narrower than viewport', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const instance = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)!
    const game = makeGame(0, 0)
    const rt = mechanicRegistry.create(instance, game as any)!
    game.scene.entities[0].position.x = 500
    rt.update(1 / 60)

    // Use a NARROW sprite resolver — 400px wide in a 800px viewport
    const narrowResolver = (id: string) => ({
      image: { __id: id } as any, width: 400, height: 224,
    })
    const { ctx, drawCalls } = makeMockCtx(800, 600)
    drawParallaxLayers(ctx, rt.expose!().layer_offsets as any, narrowResolver)

    // 400-wide sprite in 800-wide viewport = at least 2 tiles per layer × 3 layers = 6+
    expect(drawCalls.length).toBeGreaterThanOrEqual(6)
    rt.dispose()
  })
})
