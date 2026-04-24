/**
 * projectile_setup.ts — tests the projectile lookup helpers.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  findProjectilesByOwner,
  findProjectilesBySubKind,
  pickCanonicalProjectile,
} from '../src/sprites/projectile_setup'
import {
  loadExtractionIndex,
  resetExtractionIndex,
  type SpriteSheetManifest,
} from '../src/sprites/kind_index'

function makeSheet(game_stem: string, title: string, anims: any[]): SpriteSheetManifest {
  return { game_stem, sheet_title: title, animations: anims }
}

const FIXTURES: Record<string, Record<string, any>> = {
  '1986_metroid': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1986_metroid', 'Samus weapons', [
      {
        name: 'samus_wave_beam', kind: 'projectile', sub_kind: 'special_attack_proj', actor: 'samus',
        pixel_resolution_per_frame_px: [16, 16], frame_count: 4, grid_layout: 'horizontal_strip',
        progression_description: 'wave beam', inferred: false, confidence: 0.92,
      },
      {
        name: 'samus_missile', kind: 'projectile', sub_kind: 'missile', actor: 'samus',
        pixel_resolution_per_frame_px: [16, 8], frame_count: 2, grid_layout: 'horizontal_strip',
        progression_description: 'missile', inferred: false, confidence: 0.9,
      },
    ]),
  },
  '1987_contra': {
    '_index.json': ['sheet_001.json'],
    'sheet_001.json': makeSheet('1987_contra', 'Contra weapons', [
      {
        name: 'contra_blaster', kind: 'projectile', sub_kind: 'gun_proj', actor: 'bill',
        pixel_resolution_per_frame_px: [8, 8], frame_count: 1, grid_layout: 'single_cell',
        progression_description: 'default shot', inferred: false, confidence: 0.95,
      },
      {
        name: 'contra_spread', kind: 'projectile', sub_kind: 'gun_proj', actor: 'bill',
        pixel_resolution_per_frame_px: [8, 8], frame_count: 1, grid_layout: 'single_cell',
        progression_description: 'spread shot', inferred: false, confidence: 0.9,
      },
    ]),
  },
}

const URL_RE = /\/sprite_sheets\/([^/]+)\/(.+)$/

beforeEach(() => {
  resetExtractionIndex()
  ;(globalThis as any).fetch = vi.fn(async (url: string) => {
    const m = URL_RE.test(url) ? url.match(URL_RE) : null
    if (!m) return { ok: false, status: 404, statusText: 'nm', json: async () => ({}) }
    const data = FIXTURES[m[1]]?.[m[2]]
    if (data === undefined) return { ok: false, status: 404, statusText: 'nf', json: async () => ({}) }
    return { ok: true, status: 200, statusText: 'ok', json: async () => data }
  })
})

describe('projectile_setup', () => {
  it('findProjectilesByOwner returns samus projectiles', async () => {
    await loadExtractionIndex(['1986_metroid'])
    const samus = findProjectilesByOwner('samus')
    expect(samus).toHaveLength(2)
    expect(samus.map((p) => p.sprite_id).sort()).toEqual(['samus_missile', 'samus_wave_beam'])
    expect(samus[0].owner).toBe('samus')
  })

  it('resolved config carries cell_size + frame_count from extraction', async () => {
    await loadExtractionIndex(['1986_metroid'])
    const [waveBeam] = findProjectilesByOwner('samus').filter((p) => p.sub_kind === 'special_attack_proj')
    expect(waveBeam.cell_size_px).toEqual([16, 16])
    expect(waveBeam.frame_count).toBe(4)
    expect(waveBeam.source_essence).toBe('1986_metroid')
    expect(waveBeam.uses_defaults).toBe(false)
  })

  it('findProjectilesBySubKind spans essences', async () => {
    await loadExtractionIndex(['1986_metroid', '1987_contra'])
    const guns = findProjectilesBySubKind('gun_proj')
    expect(guns).toHaveLength(2)  // both contra entries
    expect(guns.every((p) => p.sub_kind === 'gun_proj')).toBe(true)
  })

  it('pickCanonicalProjectile returns first match', async () => {
    await loadExtractionIndex(['1987_contra'])
    const bill = pickCanonicalProjectile('bill', 'gun_proj')
    expect(bill).not.toBeNull()
    expect(bill!.sprite_id).toBe('contra_blaster')  // first in extraction order
  })

  it('pickCanonicalProjectile returns null on no match', async () => {
    await loadExtractionIndex(['1987_contra'])
    expect(pickCanonicalProjectile('bill', 'missile')).toBeNull()
    expect(pickCanonicalProjectile('unknown_actor', 'gun_proj')).toBeNull()
  })

  it('empty return when index not loaded', () => {
    expect(findProjectilesByOwner('samus')).toEqual([])
    expect(findProjectilesBySubKind('gun_proj')).toEqual([])
  })
})
