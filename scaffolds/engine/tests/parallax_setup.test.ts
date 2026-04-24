/**
 * parallax_setup.ts — tests the scaffold-ergonomics helpers.
 *
 * Reuses the kind_index fetch-stub pattern from kind_index.test.ts to
 * feed fixture essences, then verifies the setup helpers build valid
 * MechanicInstances from them.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  configureParallax3LayerFromEssence,
  configureParallaxSingleLayerFromEssence,
  configureParallaxFromEssence,
} from '../src/sprites/parallax_setup'
import {
  loadExtractionIndex,
  resetExtractionIndex,
  type SpriteSheetManifest,
} from '../src/sprites/kind_index'

function makeSheet(game_stem: string, title: string, anims: any[]): SpriteSheetManifest {
  return { game_stem, sheet_title: title, animations: anims }
}

const FIXTURES: Record<string, Record<string, any>> = {
  '1991_sonic_the_hedgehog': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1991_sonic_the_hedgehog', 'Green Hill parallax', [
      {
        name: 'green_hill_far', kind: 'background_layer', sub_kind: 'parallax_far',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'far', inferred: false, confidence: 0.9,
        background_params: { layer_position: 'far', scroll_speed_ratio: 0.25, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
      },
      {
        name: 'green_hill_mid', kind: 'background_layer', sub_kind: 'parallax_mid',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'mid', inferred: false, confidence: 0.9,
        background_params: { layer_position: 'mid', scroll_speed_ratio: 0.5, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
      },
      {
        name: 'green_hill_near', kind: 'background_layer', sub_kind: 'parallax_near',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'near', inferred: false, confidence: 0.9,
        background_params: { layer_position: 'near', scroll_speed_ratio: 0.75, biome: 'green_hill', time_of_day: 'day', loops_horizontally: true },
      },
    ]),
  },
  '1990_raiden': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1990_raiden', 'Single backdrop', [
      {
        name: 'raiden_urban_military', kind: 'background_layer', sub_kind: 'parallax_single',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'single', inferred: false, confidence: 0.9,
        background_params: { layer_position: 'single', scroll_speed_ratio: 1.0, biome: 'urban_night', time_of_day: 'night', loops_horizontally: true },
      },
    ]),
  },
  '1992_super_mario_kart': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1992_super_mario_kart', 'Mode 7 track', [
      {
        name: 'smk_horizon', kind: 'background_layer', sub_kind: 'mode7_horizon',
        pixel_resolution_per_frame_px: [3200, 112], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'horizon', inferred: false, confidence: 0.9,
      },
      {
        name: 'smk_floor', kind: 'background_layer', sub_kind: 'mode7_floor',
        pixel_resolution_per_frame_px: [1024, 1024], frame_count: 1, grid_layout: 'atlas_grid',
        progression_description: 'floor', inferred: false, confidence: 0.9,
      },
    ]),
  },
  '1985_super_mario_bros': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1985_super_mario_bros', 'Mario no-parallax', [
      {
        name: 'mario_small_walk', kind: 'character', sub_kind: 'playable', actor: 'mario',
        pixel_resolution_per_frame_px: [16, 16], frame_count: 3, grid_layout: 'horizontal_strip',
        progression_description: 'walk', inferred: false, confidence: 0.95,
      },
    ]),
  },
}

const URL_RE = /\/sprite_sheets\/([^/]+)\/(.+)$/

beforeEach(() => {
  resetExtractionIndex()
  ;(globalThis as any).fetch = vi.fn(async (url: string) => {
    const m = URL_RE.test(url) ? url.match(URL_RE) : null
    if (!m) return { ok: false, status: 404, statusText: 'not matched', json: async () => ({}) }
    const essence = m[1], file = m[2]
    const data = FIXTURES[essence]?.[file]
    if (data === undefined) return { ok: false, status: 404, statusText: 'not found', json: async () => ({}) }
    return { ok: true, status: 200, statusText: 'ok', json: async () => data }
  })
})

describe('parallax_setup — 3-layer', () => {
  it('builds a MechanicInstance with 3 layers + correct ratios + z', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const inst = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)
    expect(inst).not.toBeNull()
    expect(inst!.type).toBe('ParallaxScroll')
    const params = inst!.params as any
    expect(params.follow_archetype).toBe('player')
    expect(params.axes).toBe('horizontal')
    expect(params.layers).toHaveLength(3)
    const [far, mid, near] = params.layers
    expect(far.sprite_id).toBe('green_hill_far')
    expect(far.scroll_speed_ratio).toBe(0.25)
    expect(far.layer_z).toBe(-10)
    expect(mid.scroll_speed_ratio).toBe(0.5)
    expect(mid.layer_z).toBe(-5)
    expect(near.scroll_speed_ratio).toBe(0.75)
    expect(near.layer_z).toBe(0)
  })

  it('returns null for essence without 3-layer triple', async () => {
    await loadExtractionIndex(['1990_raiden'])
    const inst = configureParallax3LayerFromEssence('1990_raiden', 'player' as any)
    expect(inst).toBeNull()
  })

  it('custom instance_id + axes override', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const inst = configureParallax3LayerFromEssence('1991_sonic_the_hedgehog', 'player' as any, {
      instance_id: 'my_custom_id' as any,
      axes: 'both',
    })
    expect(inst!.id).toBe('my_custom_id')
    expect((inst!.params as any).axes).toBe('both')
  })
})

describe('parallax_setup — single-layer', () => {
  it('builds a 1-layer MechanicInstance', async () => {
    await loadExtractionIndex(['1990_raiden'])
    const inst = configureParallaxSingleLayerFromEssence('1990_raiden', 'player' as any)
    expect(inst).not.toBeNull()
    const params = inst!.params as any
    expect(params.layers).toHaveLength(1)
    expect(params.layers[0].sprite_id).toBe('raiden_urban_military')
    expect(params.layers[0].scroll_speed_ratio).toBe(1.0)
  })

  it('returns null for non-single essences', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const inst = configureParallaxSingleLayerFromEssence('1991_sonic_the_hedgehog', 'player' as any)
    expect(inst).toBeNull()
  })
})

describe('parallax_setup — generic configureParallaxFromEssence', () => {
  it('returns null when essence has no background_layer entries', async () => {
    await loadExtractionIndex(['1985_super_mario_bros'])
    const inst = configureParallaxFromEssence('1985_super_mario_bros', 'player' as any)
    expect(inst).toBeNull()
  })

  it('builds 3-layer from full parallax essence', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const inst = configureParallaxFromEssence('1991_sonic_the_hedgehog', 'player' as any)
    expect(inst).not.toBeNull()
    const params = inst!.params as any
    expect(params.layers).toHaveLength(3)
  })

  it('handles mode7 essence with horizon + floor', async () => {
    await loadExtractionIndex(['1992_super_mario_kart'])
    const inst = configureParallaxFromEssence('1992_super_mario_kart', 'kart' as any)
    expect(inst).not.toBeNull()
    const params = inst!.params as any
    expect(params.layers).toHaveLength(2)
    // mode7_horizon should have lock_y=true
    const horizon = params.layers.find((l: any) => l.sprite_id === 'smk_horizon')
    const floor = params.layers.find((l: any) => l.sprite_id === 'smk_floor')
    expect(horizon.lock_y).toBe(true)
    expect(horizon.scroll_speed_ratio).toBe(0.0)
    expect(floor.scroll_speed_ratio).toBe(1.0)
    expect(floor.lock_y).toBe(false)
  })

  it('sorts layers by z ascending (painter\'s order)', async () => {
    await loadExtractionIndex(['1992_super_mario_kart'])
    const inst = configureParallaxFromEssence('1992_super_mario_kart', 'kart' as any)
    const layers = (inst!.params as any).layers
    // horizon (-8) should come before floor (0)
    expect(layers[0].layer_z).toBeLessThan(layers[1].layer_z)
  })
})
