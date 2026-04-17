// Phase 8 — sprite loader + sprite_ref validator tests.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  loadSpriteManifest,
  getSpriteManifest,
  isManifestLoaded,
  resolveSpriteRef,
  resetSpriteManifest,
} from '../src/sprites/loader'
import { validate } from '../src/design/validate'
import type { DesignScript } from '../src/design/schema'


const SAMPLE_MANIFEST = {
  schema_version: '1',
  assets: {
    hero: {
      id: 'hero',
      path: 'sprites/hero.png',
      category: 'character',
      metadata: { class: 'knight', facing: 'side' },
    },
    coin: {
      id: 'coin',
      path: 'sprites/coin.png',
      category: 'item',
      metadata: { rarity: 'common' },
    },
  },
}


describe('loader: manifest fetch + cache', () => {
  beforeEach(() => resetSpriteManifest())

  it('reports unloaded before first fetch', () => {
    expect(isManifestLoaded()).toBe(false)
    expect(getSpriteManifest()).toBeNull()
  })

  it('fetches manifest + caches in module scope', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200, statusText: 'OK',
      json: async () => SAMPLE_MANIFEST,
    } as unknown as Response))
    vi.stubGlobal('fetch', fetchMock)

    const m = await loadSpriteManifest('/')
    expect(m.schema_version).toBe('1')
    expect(Object.keys(m.assets)).toEqual(['hero', 'coin'])
    expect(isManifestLoaded()).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    // Second call must hit cache — no second fetch.
    await loadSpriteManifest('/')
    expect(fetchMock).toHaveBeenCalledTimes(1)

    vi.unstubAllGlobals()
  })

  it('resolveSpriteRef returns entry after load, null for unknown id', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true, status: 200, statusText: 'OK',
      json: async () => SAMPLE_MANIFEST,
    } as unknown as Response)))
    await loadSpriteManifest('/')
    const hero = resolveSpriteRef('hero')
    expect(hero).not.toBeNull()
    expect(hero!.path).toBe('sprites/hero.png')
    expect(hero!.category).toBe('character')
    expect(resolveSpriteRef('does_not_exist')).toBeNull()
    vi.unstubAllGlobals()
  })

  it('propagates fetch failures', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false, status: 404, statusText: 'Not Found',
      json: async () => ({}),
    } as unknown as Response)))
    await expect(loadSpriteManifest('/')).rejects.toThrow(/404/)
    vi.unstubAllGlobals()
  })
})


describe('validate: sprite_ref_not_in_manifest', () => {
  function baseDesign(): DesignScript {
    return {
      meta: { title: 'Sprite Test', shape: 'action', vibe: [] },
      config: {
        mode: '2d', camera: 'orthographic',
        gravity: [0, 0, 0],
        playfield: { kind: 'continuous', arena: { shape: 'rect', size: 16 } },
      },
      singletons: {},
      archetypes: {},
      mechanics: [],
      flow: { kind: 'scene', name: 'main' as unknown as never },
    } as DesignScript
  }

  it('accepts sprite_ref that exists in sprite_manifest', () => {
    const d = baseDesign()
    d.archetypes.player = {
      controller: 'topdown', components: [], tags: ['player'],
      sprite_ref: 'hero',
    } as unknown as never
    ;(d as unknown as Record<string, unknown>).sprite_manifest = {
      schema_version: '1',
      assets: { hero: { id: 'hero', category: 'character',
                        path: 'sprites/hero.png', metadata: {} } },
    }
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('rejects sprite_ref not declared in sprite_manifest', () => {
    const d = baseDesign()
    d.archetypes.player = {
      controller: 'topdown', components: [], tags: ['player'],
      sprite_ref: 'ghost',
    } as unknown as never
    ;(d as unknown as Record<string, unknown>).sprite_manifest = {
      schema_version: '1',
      assets: { hero: { id: 'hero', category: 'character',
                        path: 'sprites/hero.png', metadata: {} } },
    }
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('sprite_ref_not_in_manifest')
  })

  it('skips the check when no sprite_manifest is supplied (build-step surfaces it)', () => {
    const d = baseDesign()
    d.archetypes.player = {
      controller: 'topdown', components: [], tags: ['player'],
      sprite_ref: 'anything',
    } as unknown as never
    const r = validate(d)
    expect(r.ok).toBe(true)  // validator is quiet; build_sprites enforces.
  })
})
