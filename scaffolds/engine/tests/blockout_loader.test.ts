/**
 * blockout_loader.ts — runtime loader for movement-loop blockout sheets.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  loadBlockout,
  resetBlockoutCache,
  getCellForDirection,
  getAnimFrameCount,
  isTopDownComplete,
  isIsoComplete,
} from '../src/sprites/blockout_loader'

const FIXTURES: Record<string, any> = {
  '/blockouts/1986_dragon_quest/hero_plainclothes_walk/1986_dragon_quest_hero_plainclothes_walk_movement_blockout.manifest.json': {
    cols: 4, rows: 1, cell_w: 256, cell_h: 256, gutter_px: 0,
    sheet_w: 1024, sheet_h: 256, frame_count: 4,
    cells: [
      { index: 0, label: 'N', cell_x: 0, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_N.png' },
      { index: 1, label: 'E', cell_x: 256, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_E.png' },
      { index: 2, label: 'S', cell_x: 512, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_S.png' },
      { index: 3, label: 'W', cell_x: 768, cell_y: 0, cell_w: 256, cell_h: 256, source: 'frame_W.png' },
    ],
  },
  '/blockouts/1986_dragon_quest/hero_plainclothes_walk/1986_dragon_quest_hero_plainclothes_walk_movement_blockout.spec.json': {
    directions: ['N', 'E', 'S', 'W'],
    projection: 'orthographic_top_down',
    anim_frame_targets: { walk: 2 },
    rotation_angles: 4,
    per_frame_ms_default: 90,
  },
}

beforeEach(() => {
  resetBlockoutCache()
  ;(globalThis as any).fetch = vi.fn(async (url: string) => {
    const data = FIXTURES[url]
    if (!data) return { ok: false, status: 404, statusText: 'nf', json: async () => ({}) }
    return { ok: true, status: 200, statusText: 'ok', json: async () => data }
  })
})

describe('blockout_loader — loading', () => {
  it('loads a complete top-down 4-dir blockout', async () => {
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(b).not.toBeNull()
    expect(b!.spec.directions).toEqual(['N', 'E', 'S', 'W'])
    expect(b!.manifest.frame_count).toBe(4)
    expect(b!.by_direction.size).toBe(4)
  })

  it('caches after first load', async () => {
    const a = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(a).toBe(b)
  })

  it('returns null on missing essence', async () => {
    const b = await loadBlockout('9999_not_a_game', 'fake_anim')
    expect(b).toBeNull()
  })
})

describe('blockout_loader — queries', () => {
  it('getCellForDirection returns the right rect', async () => {
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    const e = getCellForDirection(b!, 'E')
    expect(e).not.toBeNull()
    expect(e!.cell_x).toBe(256)
    expect(e!.cell_y).toBe(0)
    expect(e!.cell_w).toBe(256)
  })

  it('getCellForDirection returns null for unknown direction', async () => {
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(getCellForDirection(b!, 'NW')).toBeNull()
  })

  it('getAnimFrameCount reads anim_frame_targets', async () => {
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(getAnimFrameCount(b!, 'walk')).toBe(2)
    expect(getAnimFrameCount(b!, 'cast')).toBe(0)
  })

  it('getAnimFrameCount canonicalizes via motion_aliases — JOB-M5', async () => {
    // The fixture declares only "walk" in anim_frame_targets. A scaffold
    // author asking for the leap/hop/bound aliases of "jump" should still
    // get back 0 without an error (no jump entry) — and when an entry
    // IS present under a canonical name, the alias lookup should hit it.
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(b).not.toBeNull()

    // Inject a canonical entry so we can test the alias resolves into it.
    b!.spec.anim_frame_targets['crouch'] = 3
    b!.spec.anim_frame_targets['cast'] = 5

    // duck → crouch (alias hit)
    expect(getAnimFrameCount(b!, 'duck')).toBe(3)
    // magic_cast → cast
    expect(getAnimFrameCount(b!, 'magic_cast')).toBe(5)
    // canonical name still works directly
    expect(getAnimFrameCount(b!, 'crouch')).toBe(3)
    // unknown + non-alias returns 0
    expect(getAnimFrameCount(b!, 'fatality')).toBe(0)
  })

  it('getAnimFrameCount prefers raw spec when both raw + canonical exist', async () => {
    // Back-compat: if a spec has historically used the non-canonical name
    // "duck" in anim_frame_targets (no canonical "crouch" entry), the
    // loader must still return that value — scaffolds need not migrate.
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    delete b!.spec.anim_frame_targets['crouch']
    b!.spec.anim_frame_targets['duck'] = 7
    // Asking for "duck" (raw) still resolves — fallback path.
    expect(getAnimFrameCount(b!, 'duck')).toBe(7)
  })

  it('isTopDownComplete correctly identifies 4-dir', async () => {
    const b = await loadBlockout('1986_dragon_quest', 'hero_plainclothes_walk')
    expect(isTopDownComplete(b!)).toBe(true)
    expect(isIsoComplete(b!)).toBe(false)
  })
})
