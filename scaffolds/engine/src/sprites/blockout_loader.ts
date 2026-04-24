import { canonicalize as canonicalizeMotion } from '../design/motion_aliases'

// TypeScript mirror of `asset_workflows/_common/blockout_loader.py`.
//
// Runtime loader for movement-loop blockout sheets produced by the
// top_down_character / iso_character workflows via the pipeline:
//   run_blockout.py → assemble_from_corpus → <name>_movement_blockout.*
//
// The pipeline emits 4 files per character into
// `./out/blockouts/<essence>/<animation_name>/`:
//   - <name>_movement_blockout.png              (the sheet)
//   - <name>_movement_blockout.manifest.json    (cell coordinates)
//   - <name>_movement_blockout.spec.json        (anim_frame_targets + projection)
//   - <name>_movement_blockout_preview.png      (labeled dev grid — ignore at runtime)
//
// This loader reads the sheet PNG + the two JSONs and gives scaffold
// code typed access to:
//   - per-direction frame rectangles (for blit)
//   - per-anim frame counts (for anim-state machine configuration)
//   - seed + source-essence provenance (for telemetry / attribution)

export interface CellRect {
  index: number
  label: string | null
  cell_x: number
  cell_y: number
  cell_w: number
  cell_h: number
  source: string | null
}

export interface BlockoutManifest {
  cols: number
  rows: number
  cell_w: number
  cell_h: number
  gutter_px: number
  sheet_w: number
  sheet_h: number
  frame_count: number
  cells: CellRect[]
}

export interface BlockoutSpec {
  directions: string[]
  projection: string
  anim_frame_targets: Record<string, number>
  rotation_angles: number
  per_frame_ms_default?: number
  blockout_note?: string
  source_essence?: string
  source_animation?: string
}

export interface LoadedBlockout {
  /** Path relative to the site root of the sheet PNG. */
  sheet_path: string
  /** The geometric manifest — cell_x, cell_y, cell_w, cell_h per direction. */
  manifest: BlockoutManifest
  /** The semantic spec — directions list, projection, anim_frame_targets. */
  spec: BlockoutSpec
  /** Quick-lookup: direction → its CellRect. */
  by_direction: Map<string, CellRect>
}

let _cache: Map<string, LoadedBlockout> = new Map()

/** Fetch + parse one blockout set. `base` defaults to `/blockouts/` —
 *  override if the scaffold serves from a subpath. Cached per
 *  (essence, animation_name). */
export async function loadBlockout(
  essence: string, animation_name: string,
  base = '/blockouts/',
): Promise<LoadedBlockout | null> {
  const cacheKey = `${essence}/${animation_name}`
  const cached = _cache.get(cacheKey)
  if (cached) return cached

  const root = `${base.replace(/\/$/, '')}/${essence}/${animation_name}`
  const manifestUrl = `${root}/${essence}_${animation_name}_movement_blockout.manifest.json`
  const specUrl = `${root}/${essence}_${animation_name}_movement_blockout.spec.json`
  const sheetUrl = `${root}/${essence}_${animation_name}_movement_blockout.png`

  let manifest: BlockoutManifest
  let spec: BlockoutSpec
  try {
    const [mRes, sRes] = await Promise.all([fetch(manifestUrl), fetch(specUrl)])
    if (!mRes.ok || !sRes.ok) return null
    manifest = (await mRes.json()) as BlockoutManifest
    spec = (await sRes.json()) as BlockoutSpec
  } catch {
    return null
  }

  const by_direction = new Map<string, CellRect>()
  for (const cell of manifest.cells) {
    if (cell.label) by_direction.set(cell.label, cell)
  }

  const loaded: LoadedBlockout = {
    sheet_path: sheetUrl,
    manifest,
    spec,
    by_direction,
  }
  _cache.set(cacheKey, loaded)
  return loaded
}

/** Reset the cache — for tests or hot-reload scaffolds. */
export function resetBlockoutCache(): void {
  _cache = new Map()
}

/** Iterator over every cached blockout. */
export function cachedBlockouts(): IterableIterator<LoadedBlockout> {
  return _cache.values()
}

/** Lookup a direction's CellRect after loadBlockout has resolved. */
export function getCellForDirection(
  loaded: LoadedBlockout, direction: string,
): CellRect | null {
  return loaded.by_direction.get(direction) ?? null
}

/** Frame count for a specific anim label (e.g. "walk") from the spec.
 *  Returns 0 when the anim isn't in anim_frame_targets.
 *
 *  Canonicalizes the lookup key via `motion_aliases.canonicalize()` first,
 *  so `getAnimFrameCount(blockout, 'duck')` finds the `crouch` entry,
 *  `getAnimFrameCount(blockout, 'magic_cast')` finds `cast`, etc.
 *  Falls back to the raw `anim` label if the canonical form is absent —
 *  scaffolds can opt into canonicalization without breaking existing
 *  spec files that declare raw verb names.
 */
export function getAnimFrameCount(
  loaded: LoadedBlockout, anim: string,
): number {
  const targets = loaded.spec.anim_frame_targets
  const canonical = canonicalizeMotion(anim)
  return targets[canonical] ?? targets[anim] ?? 0
}

/** True when the blockout covers all 4 cardinal directions (N/E/S/W). */
export function isTopDownComplete(loaded: LoadedBlockout): boolean {
  return ['N', 'E', 'S', 'W'].every(d => loaded.by_direction.has(d))
}

/** True when the blockout covers all 8 compass directions. */
export function isIsoComplete(loaded: LoadedBlockout): boolean {
  return ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'].every(d => loaded.by_direction.has(d))
}
