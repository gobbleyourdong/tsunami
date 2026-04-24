/**
 * kind_index.ts — tests the typed extraction-index API.
 *
 * Uses a stubbed fetch to feed synthetic sheet manifests to the loader.
 * Validates:
 *   - byKind + byKindSub + byActor + byEssence index construction
 *   - discriminated-union narrowing on getAnimationsBySubKind
 *   - convenience query helpers (bosses, parallax, projectiles-by-owner)
 *   - stats rollup
 *   - reset semantics
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  loadExtractionIndex,
  resetExtractionIndex,
  isExtractionIndexLoaded,
  getAnimationsByKind,
  getAnimationsBySubKind,
  getAnimationsByActor,
  getAnimationsByEssence,
  getAllBosses,
  getBackgroundLayersForEssence,
  getParallax3LayerForEssence,
  getProjectilesByOwner,
  getPlayableByActor,
  getExtractionStats,
  isCharacter,
  isBackgroundLayer,
  type SpriteSheetManifest,
} from '../src/sprites/kind_index'

function makeSheet(game_stem: string, title: string, anims: any[]): SpriteSheetManifest {
  return {
    game_stem,
    sheet_title: title,
    animations: anims,
  }
}

// Canned fixtures: 2 essences with representative animations covering
// all 7 kinds + a handful of sub_kinds.
const FIXTURES: Record<string, Record<string, any>> = {
  '1986_metroid': {
    '_index.json': ['sheet_001.json', 'sheet_002.json'],
    'sheet_001.json': makeSheet('1986_metroid', 'Samus sprites', [
      { name: 'samus_walk', kind: 'character', sub_kind: 'playable', actor: 'samus',
        pixel_resolution_per_frame_px: [16, 24], frame_count: 3, grid_layout: 'horizontal_strip',
        progression_description: 'walk cycle', inferred: false, confidence: 0.95 },
      { name: 'mother_brain_idle', kind: 'character', sub_kind: 'final_boss', actor: 'mother_brain',
        pixel_resolution_per_frame_px: [128, 64], frame_count: 4, grid_layout: 'atlas_grid',
        progression_description: 'multi-phase boss', inferred: false, confidence: 0.9 },
      { name: 'samus_wave_beam', kind: 'projectile', sub_kind: 'special_attack_proj', actor: 'samus',
        pixel_resolution_per_frame_px: [16, 16], frame_count: 4, grid_layout: 'horizontal_strip',
        progression_description: 'wave beam projectile', inferred: false, confidence: 0.92 },
      { name: 'morphball_pickup', kind: 'pickup_item', sub_kind: 'power_item',
        pixel_resolution_per_frame_px: [16, 16], frame_count: 1, grid_layout: 'single_cell',
        progression_description: 'morph ball', inferred: false, confidence: 0.95 },
    ]),
    'sheet_002.json': makeSheet('1986_metroid', 'Zebes tiles', [
      { name: 'zebes_ground', kind: 'tile', sub_kind: 'level_layout',
        pixel_resolution_per_frame_px: [16, 16], frame_count: 1, grid_layout: 'single_cell',
        progression_description: 'collidable ground', inferred: false, confidence: 0.9 },
    ]),
  },
  '1991_sonic_the_hedgehog': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1991_sonic_the_hedgehog', 'Green Hill parallax', [
      { name: 'green_hill_far', kind: 'background_layer', sub_kind: 'parallax_far',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'far parallax layer', inferred: false, confidence: 0.88,
        background_params: { layer_position: 'far', scroll_speed_ratio: 0.25, biome: 'green_hill', time_of_day: 'day' } },
      { name: 'green_hill_mid', kind: 'background_layer', sub_kind: 'parallax_mid',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'mid parallax layer', inferred: false, confidence: 0.88,
        background_params: { layer_position: 'mid', scroll_speed_ratio: 0.5, biome: 'green_hill', time_of_day: 'day' } },
      { name: 'green_hill_near', kind: 'background_layer', sub_kind: 'parallax_near',
        pixel_resolution_per_frame_px: [3200, 224], frame_count: 1, grid_layout: 'horizontal_strip',
        progression_description: 'near parallax layer', inferred: false, confidence: 0.88,
        background_params: { layer_position: 'near', scroll_speed_ratio: 0.75, biome: 'green_hill', time_of_day: 'day' } },
      { name: 'sonic_run', kind: 'character', sub_kind: 'playable', actor: 'sonic',
        pixel_resolution_per_frame_px: [32, 32], frame_count: 8, grid_layout: 'horizontal_strip',
        progression_description: 'run cycle', inferred: false, confidence: 0.95 },
    ]),
  },
}

// Stub fetch with the fixtures. URL format: /sprite_sheets/<essence>/<file>
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

describe('kind_index — loading', () => {
  it('builds an index from two essences', async () => {
    await loadExtractionIndex(['1986_metroid', '1991_sonic_the_hedgehog'])
    expect(isExtractionIndexLoaded()).toBe(true)
    const stats = getExtractionStats()!
    expect(stats.totalAnims).toBe(9)
    expect(stats.essenceCount).toBe(2)
    expect(stats.byKind.character).toBe(3)
    expect(stats.byKind.projectile).toBe(1)
    expect(stats.byKind.background_layer).toBe(3)
  })

  it('caches the index on subsequent calls', async () => {
    const idx1 = await loadExtractionIndex(['1986_metroid', '1991_sonic_the_hedgehog'])
    const idx2 = await loadExtractionIndex(['1986_metroid', '1991_sonic_the_hedgehog'])
    expect(idx1).toBe(idx2)
  })

  it('reset clears the cache', async () => {
    await loadExtractionIndex(['1986_metroid'])
    expect(isExtractionIndexLoaded()).toBe(true)
    resetExtractionIndex()
    expect(isExtractionIndexLoaded()).toBe(false)
  })
})

describe('kind_index — kind queries', () => {
  beforeEach(async () => {
    await loadExtractionIndex(['1986_metroid', '1991_sonic_the_hedgehog'])
  })

  it('getAnimationsByKind returns all of a kind', () => {
    expect(getAnimationsByKind('character')).toHaveLength(3)
    expect(getAnimationsByKind('projectile')).toHaveLength(1)
    expect(getAnimationsByKind('background_layer')).toHaveLength(3)
    expect(getAnimationsByKind('effect_layer')).toHaveLength(0)
  })

  it('getAnimationsBySubKind narrows correctly', () => {
    const playables = getAnimationsBySubKind('character', 'playable')
    expect(playables).toHaveLength(2)  // samus + sonic
    expect(playables.map((t) => t.anim.actor).sort()).toEqual(['samus', 'sonic'])

    const bosses = getAnimationsBySubKind('character', 'final_boss')
    expect(bosses).toHaveLength(1)
    expect(bosses[0].anim.actor).toBe('mother_brain')
  })

  it('getAnimationsByActor returns cross-essence hits', () => {
    const samus = getAnimationsByActor('samus')
    expect(samus).toHaveLength(2)  // walk + wave_beam
    const kinds = samus.map((t) => t.anim.kind).sort()
    expect(kinds).toEqual(['character', 'projectile'])
  })

  it('getAnimationsByEssence scopes to one essence', () => {
    const metroid = getAnimationsByEssence('1986_metroid')
    expect(metroid).toHaveLength(5)
    const sonic = getAnimationsByEssence('1991_sonic_the_hedgehog')
    expect(sonic).toHaveLength(4)
  })
})

describe('kind_index — convenience queries', () => {
  beforeEach(async () => {
    await loadExtractionIndex(['1986_metroid', '1991_sonic_the_hedgehog'])
  })

  it('getAllBosses merges boss + final_boss', () => {
    const bosses = getAllBosses()
    expect(bosses).toHaveLength(1)  // only mother_brain as final_boss
    expect(bosses[0].anim.sub_kind).toBe('final_boss')
  })

  it('getBackgroundLayersForEssence filters to one essence', () => {
    const sonic = getBackgroundLayersForEssence('1991_sonic_the_hedgehog')
    expect(sonic).toHaveLength(3)
    const metroid = getBackgroundLayersForEssence('1986_metroid')
    expect(metroid).toHaveLength(0)
  })

  it('getParallax3LayerForEssence returns the far/mid/near triple', () => {
    const trio = getParallax3LayerForEssence('1991_sonic_the_hedgehog')
    expect(trio).not.toBeNull()
    expect(trio!.far.anim.sub_kind).toBe('parallax_far')
    expect(trio!.mid.anim.sub_kind).toBe('parallax_mid')
    expect(trio!.near.anim.sub_kind).toBe('parallax_near')
    expect(trio!.far.anim.background_params?.scroll_speed_ratio).toBe(0.25)
  })

  it('getParallax3LayerForEssence returns null when incomplete', () => {
    expect(getParallax3LayerForEssence('1986_metroid')).toBeNull()
  })

  it('getProjectilesByOwner matches by actor', () => {
    const samusProj = getProjectilesByOwner('samus')
    expect(samusProj).toHaveLength(1)
    expect(samusProj[0].anim.name).toBe('samus_wave_beam')
  })

  it('getPlayableByActor returns only playable characters', () => {
    const samus = getPlayableByActor('samus')
    expect(samus).toHaveLength(1)
    expect(samus[0].anim.sub_kind).toBe('playable')
  })
})

describe('kind_index — type guards', () => {
  it('isCharacter narrows correctly', async () => {
    await loadExtractionIndex(['1986_metroid'])
    const all = getAnimationsByEssence('1986_metroid')
    const chars = all.filter((t) => isCharacter(t))
    expect(chars).toHaveLength(2)  // samus + mother_brain
    const playableOnly = all.filter((t) => isCharacter(t, 'playable'))
    expect(playableOnly).toHaveLength(1)
    expect(playableOnly[0].anim.actor).toBe('samus')
  })

  it('isBackgroundLayer narrows correctly', async () => {
    await loadExtractionIndex(['1991_sonic_the_hedgehog'])
    const all = getAnimationsByEssence('1991_sonic_the_hedgehog')
    const bgs = all.filter((t) => isBackgroundLayer(t))
    expect(bgs).toHaveLength(3)
    const farOnly = all.filter((t) => isBackgroundLayer(t, 'parallax_far'))
    expect(farOnly).toHaveLength(1)
  })
})
