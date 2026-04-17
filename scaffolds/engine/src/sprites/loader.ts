// Runtime sprite manifest loader.
//
// build_sprites.py emits `public/sprites/manifest.json` as a flat
// `{ id → SpriteEntry }` map. `loadSpriteManifest(base?)` fetches it
// once, caches in module scope, and `resolveSpriteRef(id)` returns
// the entry for an archetype's sprite_ref. All sprite paths in the
// entry are relative to the site root (or whatever `base` resolves
// to in the hosting scaffold).
//
// Why a flat map: compile-time archetype.sprite_ref is a string;
// no walker needs to traverse categories at runtime. The category
// stays on the entry only as metadata for the renderer (e.g. to
// decide atlas lookup vs single-image blit).

export interface SpriteManifest {
  schema_version: string
  assets: Record<string, SpriteEntry>
}

export interface SpriteEntry {
  id: string
  /** Path relative to the site root, e.g. `sprites/player_knight.png`. */
  path: string
  category: string
  /** Merged metadata: author-supplied + post-process side effects.
   *  For tilesets this contains `atlas` (path to the .atlas.json
   *  sidecar), for effects it may contain `composite_mode`, etc. */
  metadata: Record<string, unknown>
}

let _manifest: SpriteManifest | null = null
let _pending: Promise<SpriteManifest> | null = null

/** Fetch + cache the runtime manifest. Subsequent calls return the
 *  cached copy. `base` defaults to `/` — override when the scaffold
 *  serves from a sub-path. */
export async function loadSpriteManifest(base = '/'): Promise<SpriteManifest> {
  if (_manifest) return _manifest
  if (_pending) return _pending
  const url = `${base.replace(/\/$/, '')}/sprites/manifest.json`
  _pending = fetch(url).then(async (res) => {
    if (!res.ok) {
      throw new Error(`loadSpriteManifest: ${res.status} ${res.statusText} @ ${url}`)
    }
    const m = (await res.json()) as SpriteManifest
    _manifest = m
    _pending = null
    return m
  }).catch((e) => {
    _pending = null
    throw e
  })
  return _pending
}

/** Return the manifest synchronously — only usable after
 *  `loadSpriteManifest` has resolved once. Callers that need to
 *  check whether load has happened use `isManifestLoaded()`. */
export function getSpriteManifest(): SpriteManifest | null {
  return _manifest
}

export function isManifestLoaded(): boolean {
  return _manifest !== null
}

/** Lookup a sprite by id. Returns null when the manifest hasn't
 *  loaded yet or the id isn't in it; compile-time validator is the
 *  source of truth that rejects bad refs, so a null here means
 *  something went wrong between compile and runtime load (e.g. the
 *  build step didn't write the manifest, or the manifest is stale). */
export function resolveSpriteRef(ref: string): SpriteEntry | null {
  return _manifest?.assets[ref] ?? null
}

/** Reset — mostly for hot-reload / test scaffolds. */
export function resetSpriteManifest(): void {
  _manifest = null
  _pending = null
}
