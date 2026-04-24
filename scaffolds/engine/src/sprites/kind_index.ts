// Kind-aware index over the sprite-sheet extraction corpus.
//
// TypeScript mirror of:
//   - scaffolds/.claude/SPRITE_KIND_SCHEMA.json (runtime shape)
//   - scaffolds/.claude/SPRITE_KIND_REGISTRY.md (per-kind / sub_kind contracts)
//
// Loads `sprite_sheets/<essence>/sheet_*.json` extraction manifests and
// builds typed indices for fast lookup. Complements loader.ts — that
// module loads the runtime sprite-asset manifest (which frames go where),
// this module loads the EXTRACTION catalog (which animations exist per
// essence + kind + sub_kind).
//
// Two-layer design:
//   - `loadExtractionIndex(essenceIds)` fetches per-essence sheet JSONs
//     and builds an in-memory kind × sub_kind index.
//   - `get*` functions query that index with full TypeScript typing
//     via discriminated unions on (kind, sub_kind).

// ──────────────────────────── Type taxonomy ────────────────────────────
//
// The 7 registered sprite kinds. MUST stay in sync with
// SPRITE_KIND_SCHEMA.json::$defs.sprite_kind_enum.
export type SpriteKind =
  | 'character'
  | 'tile'
  | 'ui'
  | 'pickup_item'
  | 'effect_layer'
  | 'projectile'
  | 'background_layer'

// Per-kind sub_kind enums (narrowed unions).
// MUST stay in sync with SPRITE_KIND_SCHEMA.json kind-branched sub_kind enums.
export type CharacterSubKind =
  | 'playable' | 'boss' | 'minion' | 'final_boss'
  | 'npc' | 'mount_or_vehicle' | 'enemy_group'

export type TileSubKind =
  | 'level_layout' | 'background' | 'tile_atlas' | 'overworld_map'

export type UISubKind =
  | 'menu_screen' | 'hud_readout' | 'cutscene'
  | 'logo' | 'typography' | 'dialog' | 'portrait'

export type PickupItemSubKind =
  | 'health_pickup' | 'power_item' | 'currency' | 'weapon_pickup'

export type EffectLayerSubKind =
  | 'explosion_vfx' | 'spell_vfx' | 'aura_vfx'
  | 'atmospheric_vfx' | 'summon_vfx'

export type ProjectileSubKind =
  | 'special_attack_proj' | 'gun_proj' | 'melee_thrown'
  | 'missile' | 'explosive'

export type BackgroundLayerSubKind =
  | 'parallax_far' | 'parallax_mid' | 'parallax_near' | 'parallax_single'
  | 'mode7_horizon' | 'mode7_floor' | 'skybox_static'

// Generic lookup — given a kind, the narrowed sub_kind type
export type SubKindFor<K extends SpriteKind> =
  K extends 'character'        ? CharacterSubKind :
  K extends 'tile'             ? TileSubKind :
  K extends 'ui'               ? UISubKind :
  K extends 'pickup_item'      ? PickupItemSubKind :
  K extends 'effect_layer'     ? EffectLayerSubKind :
  K extends 'projectile'       ? ProjectileSubKind :
  K extends 'background_layer' ? BackgroundLayerSubKind :
  never

// Background-layer specific metadata (populated for kind=background_layer)
export interface BackgroundParams {
  layer_position?: 'far' | 'mid' | 'near' | 'single'
  scroll_speed_ratio?: number
  tile_width_px?: number
  loops_horizontally?: boolean
  source_essence?: string
  biome?: string
  time_of_day?: string
}

// A single animation entry as it appears in a sheet manifest.
export interface AnimationEntry {
  name: string
  kind: SpriteKind
  sub_kind?: string  // string-typed at entry level; narrowed via guards
  actor?: string | null
  pixel_resolution_per_frame_px: [number, number] | null
  frame_count: number | null
  grid_layout: string
  grid_position_on_sheet_px?: [number, number]
  progression_description: string
  inferred: boolean
  confidence: number
  notes?: string
  form?: string | null
  asset_id?: string | number | null
  asset_id_secondary?: string | number | null
  background_params?: BackgroundParams
  // Migration fields (preserved from INT-16 and INT-18 migrations)
  grid_layout_original?: string
  kind_original?: string
  sub_kind_original?: string
}

// A whole sheet manifest (one JSON file).
export interface SpriteSheetManifest {
  game_stem: string
  source_url?: string | null
  sheet_title: string
  sheet_image_url?: string | null
  local_image_path?: string | null
  platform?: string | null
  animations: AnimationEntry[]
  signature?: string | null
  extraction_ts?: string | null
}

// Tagged entry — an animation plus the essence + sheet it came from.
// Most lookups return these (you usually want to know the provenance).
export interface TaggedAnimation {
  essence: string
  sheet_title: string
  anim: AnimationEntry
}

// ──────────────────────────── Index shape ────────────────────────────

interface KindIndex {
  // Flat list of all animations, tagged with provenance
  all: TaggedAnimation[]
  // kind → entries
  byKind: Map<SpriteKind, TaggedAnimation[]>
  // (kind, sub_kind) → entries
  byKindSub: Map<string, TaggedAnimation[]>  // key = `${kind}::${sub_kind}`
  // actor → entries (for cross-essence character lookup)
  byActor: Map<string, TaggedAnimation[]>
  // essence → entries
  byEssence: Map<string, TaggedAnimation[]>
}

let _index: KindIndex | null = null
let _pending: Promise<KindIndex> | null = null

function emptyIndex(): KindIndex {
  return {
    all: [],
    byKind: new Map(),
    byKindSub: new Map(),
    byActor: new Map(),
    byEssence: new Map(),
  }
}

function pushToMap<T>(m: Map<string, T[]>, key: string, v: T): void {
  const arr = m.get(key)
  if (arr) arr.push(v)
  else m.set(key, [v])
}

function pushToKindMap(m: Map<SpriteKind, TaggedAnimation[]>, kind: SpriteKind, v: TaggedAnimation): void {
  const arr = m.get(kind)
  if (arr) arr.push(v)
  else m.set(kind, [v])
}

// ──────────────────────────── Loading ────────────────────────────

/** Fetch per-essence sheet manifests and build the kind index. `base`
 *  defaults to `/sprite_sheets/` — override when the scaffold serves
 *  extraction data from a different path. */
export async function loadExtractionIndex(
  essenceIds: string[],
  base = '/sprite_sheets/',
): Promise<KindIndex> {
  if (_index) return _index
  if (_pending) return _pending
  _pending = (async () => {
    const idx = emptyIndex()
    for (const essence of essenceIds) {
      const manifestListUrl = `${base.replace(/\/$/, '')}/${essence}/_index.json`
      let sheetFiles: string[]
      try {
        const res = await fetch(manifestListUrl)
        if (!res.ok) continue
        sheetFiles = (await res.json()) as string[]
      } catch {
        continue
      }
      for (const sheetPath of sheetFiles) {
        let sheet: SpriteSheetManifest
        try {
          const res = await fetch(`${base.replace(/\/$/, '')}/${essence}/${sheetPath}`)
          if (!res.ok) continue
          sheet = (await res.json()) as SpriteSheetManifest
        } catch {
          continue
        }
        for (const anim of sheet.animations) {
          const tagged: TaggedAnimation = { essence, sheet_title: sheet.sheet_title, anim }
          idx.all.push(tagged)
          pushToKindMap(idx.byKind, anim.kind, tagged)
          if (anim.sub_kind) {
            pushToMap(idx.byKindSub, `${anim.kind}::${anim.sub_kind}`, tagged)
          }
          if (anim.actor) {
            pushToMap(idx.byActor, anim.actor, tagged)
          }
          pushToMap(idx.byEssence, essence, tagged)
        }
      }
    }
    _index = idx
    _pending = null
    return idx
  })()
  return _pending
}

/** Synchronous access — only valid after `loadExtractionIndex` resolves. */
export function getExtractionIndex(): KindIndex | null {
  return _index
}

export function isExtractionIndexLoaded(): boolean {
  return _index !== null
}

/** Reset — for tests / hot reload. */
export function resetExtractionIndex(): void {
  _index = null
  _pending = null
}

// ──────────────────────────── Typed queries ────────────────────────────

/** All animations of a given kind across all loaded essences. */
export function getAnimationsByKind(kind: SpriteKind): TaggedAnimation[] {
  return _index?.byKind.get(kind) ?? []
}

/** All animations matching (kind, sub_kind). TypeScript narrows sub_kind
 *  to the kind-appropriate union. */
export function getAnimationsBySubKind<K extends SpriteKind>(
  kind: K,
  subKind: SubKindFor<K>,
): TaggedAnimation[] {
  return _index?.byKindSub.get(`${kind}::${subKind}`) ?? []
}

/** All animations tagged with a specific actor. Cross-essence —
 *  useful for Mario (5 essences), Samus (2), Link (2), etc. */
export function getAnimationsByActor(actor: string): TaggedAnimation[] {
  return _index?.byActor.get(actor) ?? []
}

/** All animations from a specific essence. */
export function getAnimationsByEssence(essence: string): TaggedAnimation[] {
  return _index?.byEssence.get(essence) ?? []
}

// ──────────────────────────── Convenience queries ────────────────────────────
//
// Kind-specific helpers that narrow return types for the common cases.

/** Find a playable character by actor name, any essence. Useful for
 *  looking up a character mentioned in a scaffold config. */
export function getPlayableByActor(actor: string): TaggedAnimation[] {
  return getAnimationsByActor(actor).filter(
    (t) => t.anim.kind === 'character' && t.anim.sub_kind === 'playable',
  )
}

/** All bosses across the corpus, sorted by essence (useful for deep boss
 *  atlas lookup). */
export function getAllBosses(): TaggedAnimation[] {
  const regular = getAnimationsBySubKind('character', 'boss')
  const final_ = getAnimationsBySubKind('character', 'final_boss')
  return [...regular, ...final_]
}

/** Background-layer entries for a specific essence (if it has parallax
 *  backdrops extracted). */
export function getBackgroundLayersForEssence(
  essence: string,
): TaggedAnimation[] {
  return getAnimationsByEssence(essence).filter(
    (t) => t.anim.kind === 'background_layer',
  )
}

/** 3-layer parallax set for a specific essence — returns {far, mid, near}
 *  if all three are present, else null. Lookup-by-essence because
 *  parallax layers are essence-coupled (biome + time_of_day match). */
export function getParallax3LayerForEssence(
  essence: string,
): { far: TaggedAnimation; mid: TaggedAnimation; near: TaggedAnimation } | null {
  const bgs = getBackgroundLayersForEssence(essence)
  const far = bgs.find((t) => t.anim.sub_kind === 'parallax_far')
  const mid = bgs.find((t) => t.anim.sub_kind === 'parallax_mid')
  const near = bgs.find((t) => t.anim.sub_kind === 'parallax_near')
  if (far && mid && near) return { far, mid, near }
  return null
}

/** Projectile entries binding to a specific owner actor. `samus` returns
 *  samus-wave-beam and variants; empty array if actor unknown. */
export function getProjectilesByOwner(ownerActor: string): TaggedAnimation[] {
  return getAnimationsByActor(ownerActor).filter(
    (t) => t.anim.kind === 'projectile',
  )
}

/** Type guard: is this entry a character of a specific sub_kind? */
export function isCharacter<K extends CharacterSubKind>(
  t: TaggedAnimation,
  subKind?: K,
): boolean {
  if (t.anim.kind !== 'character') return false
  if (subKind && t.anim.sub_kind !== subKind) return false
  return true
}

/** Type guard: is this entry a background layer of a specific sub_kind? */
export function isBackgroundLayer<K extends BackgroundLayerSubKind>(
  t: TaggedAnimation,
  subKind?: K,
): boolean {
  if (t.anim.kind !== 'background_layer') return false
  if (subKind && t.anim.sub_kind !== subKind) return false
  return true
}

// ──────────────────────────── Stats ────────────────────────────

export interface KindStats {
  totalAnims: number
  byKind: Record<SpriteKind, number>
  taggedWithSubKind: number
  essenceCount: number
}

export function getExtractionStats(): KindStats | null {
  if (!_index) return null
  const byKind = {
    character: 0, tile: 0, ui: 0, pickup_item: 0,
    effect_layer: 0, projectile: 0, background_layer: 0,
  } as Record<SpriteKind, number>
  let tagged = 0
  for (const t of _index.all) {
    byKind[t.anim.kind] = (byKind[t.anim.kind] ?? 0) + 1
    if (t.anim.sub_kind) tagged++
  }
  return {
    totalAnims: _index.all.length,
    byKind,
    taggedWithSubKind: tagged,
    essenceCount: _index.byEssence.size,
  }
}
