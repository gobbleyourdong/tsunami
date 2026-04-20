/**
 * Phase 4 — asset pool smoke tests.
 *
 * Verifies manifest loads, all listed paths exist on disk, query
 * helpers behave (AND semantics), and categorization matches the
 * plan (characters, enemies, items, weapons, tiles, ui).
 */

import { describe, it, expect } from 'vitest'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import {
  getAsset,
  queryByTag,
  findByTag,
  listAllTags,
  listCategories,
  categoryCounts,
  totalSpriteCount,
} from '../src/assets'

const ASSETS_ROOT = join(__dirname, '..', 'assets')

describe('Phase 4 — asset pool', () => {
  it('manifest loads with at least 30 sprite entries', () => {
    expect(totalSpriteCount()).toBeGreaterThanOrEqual(30)
  })

  it('exposes all 6 primary categories', () => {
    const cats = listCategories().sort()
    expect(cats).toEqual(['characters', 'enemies', 'items', 'tiles', 'ui', 'weapons'])
  })

  it('category counts match expected thresholds from JOB-C', () => {
    const counts = categoryCounts()
    // Must-have minima per ASSET_INVENTORY.md
    expect(counts.characters).toBeGreaterThanOrEqual(4)
    expect(counts.enemies).toBeGreaterThanOrEqual(5)
    expect(counts.items).toBeGreaterThanOrEqual(6)
    expect(counts.weapons).toBeGreaterThanOrEqual(6)
    expect(counts.tiles).toBeGreaterThanOrEqual(6)
    expect(counts.ui).toBeGreaterThanOrEqual(5)
  })

  it('every manifest path exists on disk', () => {
    const missing: string[] = []
    const counts = categoryCounts()
    for (const category of Object.keys(counts)) {
      const entries = queryByTag(category === 'characters' ? 'character' : category.slice(0, -1))
      for (const e of entries) {
        if (!existsSync(join(ASSETS_ROOT, e.path))) missing.push(e.path)
      }
    }
    expect(missing).toEqual([])
  })

  it('getAsset finds a known id', () => {
    const heart = getAsset('items/heart')
    expect(heart).toBeDefined()
    expect(heart?.tags).toContain('hp')
    expect(heart?.path).toBe('sprites/items/heart.svg')
  })

  it('getAsset returns undefined for unknown id', () => {
    expect(getAsset('not/a/real/asset')).toBeUndefined()
  })

  it('queryByTag applies AND semantics', () => {
    const all_enemies = queryByTag('enemy')
    const enemy_melee = queryByTag('enemy', 'melee')
    expect(enemy_melee.length).toBeGreaterThanOrEqual(2)
    expect(enemy_melee.length).toBeLessThanOrEqual(all_enemies.length)
    // Every result must have both tags
    for (const e of enemy_melee) {
      expect(e.tags).toContain('enemy')
      expect(e.tags).toContain('melee')
    }
  })

  it('queryByTag with no args returns everything', () => {
    expect(queryByTag().length).toBe(totalSpriteCount())
  })

  it('queryByTag with nonsense returns empty', () => {
    expect(queryByTag('not_a_real_tag')).toEqual([])
  })

  it('findByTag returns first match', () => {
    const first_weapon = findByTag('weapon')
    expect(first_weapon).toBeDefined()
    expect(first_weapon?.tags).toContain('weapon')
  })

  it('listAllTags surfaces all primary roles', () => {
    const tags = listAllTags()
    for (const required of ['character', 'enemy', 'weapon', 'item', 'tile', 'ui', 'pickup', 'ranged', 'melee']) {
      expect(tags).toContain(required)
    }
  })

  it('health-family tags cover bar + heart for HUD composition', () => {
    const bars = queryByTag('bar', 'health')
    const hearts = queryByTag('hp')
    expect(bars.length).toBeGreaterThanOrEqual(1)
    expect(hearts.length).toBeGreaterThanOrEqual(1)
  })

  it('each sprite has valid w/h dimensions', () => {
    for (const entry of queryByTag()) {
      expect(entry.w).toBeGreaterThan(0)
      expect(entry.h).toBeGreaterThan(0)
    }
  })
})
