/**
 * Asset pool query helper — Layer 0.5 of the gamedev framework.
 *
 * Exposes a tag-based lookup over the shared placeholder asset pool
 * at `scaffolds/engine/assets/`. Genre scaffolds use this instead of
 * hardcoding paths — `queryByTag('enemy', 'melee')` returns every
 * enemy-melee sprite regardless of which file the artist shipped.
 *
 * The manifest lives at `scaffolds/engine/assets/manifest.json`.
 * In a Vite build, JSON is imported directly; no fetch needed.
 */

import manifest from '../../assets/manifest.json'

export interface AssetEntry {
  /** Full id — category/name (e.g. "items/heart", "enemies/grunt"). */
  id: string
  /** Relative path from assets/ root — load via /engine-assets/<path> at runtime. */
  path: string
  /** Tags for queryByTag lookup. */
  tags: string[]
  /** Sprite dimensions in px (or 0 for non-sprite assets). */
  w: number
  h: number
}

// Flatten the manifest into a typed array at load time.
const SPRITE_ENTRIES: AssetEntry[] = Object.entries(manifest.sprites).map(
  ([id, raw]) => {
    const r = raw as { path: string; tags: string[]; w: number; h: number }
    return { id, path: r.path, tags: r.tags, w: r.w, h: r.h }
  },
)

/**
 * Get an asset by its full id (e.g. "enemies/grunt").
 * Returns undefined if not found — callers should provide a fallback.
 */
export function getAsset(id: string): AssetEntry | undefined {
  return SPRITE_ENTRIES.find((e) => e.id === id)
}

/**
 * Query assets matching ALL given tags (AND semantics).
 *
 *   queryByTag('enemy')             // every enemy sprite
 *   queryByTag('enemy', 'melee')    // enemy AND melee (grunt + zombie)
 *   queryByTag('weapon', 'ranged')  // bow + pistol + rifle + shotgun + plasma
 */
export function queryByTag(...tags: string[]): AssetEntry[] {
  if (tags.length === 0) return [...SPRITE_ENTRIES]
  return SPRITE_ENTRIES.filter((e) => tags.every((t) => e.tags.includes(t)))
}

/** Get the first asset matching all tags, or undefined. */
export function findByTag(...tags: string[]): AssetEntry | undefined {
  return queryByTag(...tags)[0]
}

/** List every distinct tag in the manifest (useful for debug / tooling). */
export function listAllTags(): string[] {
  const set = new Set<string>()
  for (const entry of SPRITE_ENTRIES) {
    for (const t of entry.tags) set.add(t)
  }
  return [...set].sort()
}

/** List every sprite category (prefix before /). */
export function listCategories(): string[] {
  const set = new Set<string>()
  for (const entry of SPRITE_ENTRIES) {
    set.add(entry.id.split('/')[0])
  }
  return [...set].sort()
}

/** Count of entries per category. */
export function categoryCounts(): Record<string, number> {
  const out: Record<string, number> = {}
  for (const entry of SPRITE_ENTRIES) {
    const cat = entry.id.split('/')[0]
    out[cat] = (out[cat] ?? 0) + 1
  }
  return out
}

/** Total sprite count in the manifest. */
export function totalSpriteCount(): number {
  return SPRITE_ENTRIES.length
}
