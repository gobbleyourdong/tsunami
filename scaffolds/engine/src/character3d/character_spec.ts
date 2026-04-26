/**
 * CharacterSpec V2 — the complete data description of a character.
 *
 * Doctrine: characters are DATA. Anything that distinguishes one character
 * from another (proportions, palette, face layout, accessories, archetype
 * base sizes) belongs in a JSON file; anything that draws pixels belongs
 * in the engine. This type is the contract between those sides.
 *
 * A CharacterSpec fully round-trips: load → runtime mutation (slider drag,
 * palette pick) → save → load reproduces identical renders. The engine
 * should never need to dip into hardcoded constants to complete the
 * picture — if it does, that's a missing spec field.
 *
 * Versioning:
 *  - V1 (legacy): proportions + palette only. Face/hair/body/accessories
 *    came from in-code defaults. Loader upgrades forward, never drops data.
 *  - V2 (current): adds archetype, face, hair, body, accessories arrays.
 *
 * The spec does NOT include the animation VAT or the rig topology — those
 * are shared across characters that use the same skeleton (Mixamo base).
 * One spec, many animations. Separate entities.
 */
import type { FaceFeature, HairPart, BodyPart, Accessory } from './mixamo_loader'

/** Rig archetype geometry — the base sizes that a character's proportion
 *  multipliers are applied against. "Chibi" is one archetype; future
 *  "realistic" or "toddler" archetypes share this shape with different
 *  numbers. Extracting these here lets a spec override them without
 *  touching the engine code. */
export interface CharacterArchetype {
  /** Named body-part half-extents for centered parts (head, torso, hips,
   *  neck). Keys match joint names. */
  centeredSizes: Record<string, [number, number, number]>
  /** Local offsets applied to centered parts (e.g. head sits above the
   *  joint origin to clear the shoulders). */
  centeredOffsets: Record<string, [number, number, number]>
  /** Limb thickness per joint, [x, y] half-extents (z is symmetric). */
  limbThickness: Record<string, [number, number]>
}

/** Palette entry — RGB in [0, 1]. Slot names are the material's namedSlots
 *  keys (skin, hair, shirt, pants, etc.) so the map survives slot-index
 *  renumbering across engine versions. */
export type PaletteEntry = [number, number, number]

/** V2 complete spec. Every field is load-bearing; none are optional except
 *  license (marketplace metadata, no engine effect). */
export interface CharacterSpecV2 {
  version: 2
  name: string
  archetype: CharacterArchetype
  /** Per-group proportion multiplier (head/torso/arms/legs/etc).
   *  1.0 = archetype default; >1 scales up, <1 scales down. */
  proportions: Record<string, number>
  /** Slot name → RGB. Example: { skin: [0.95, 0.80, 0.68], hair: [0.2, 0.1, 0.05] }. */
  palette: Record<string, PaletteEntry>
  face:        FaceFeature[]
  hair:        HairPart[]
  bodyParts:   BodyPart[]
  accessories: Accessory[]
  /** Optional marketplace metadata. No engine effect. */
  license?: {
    commercial?:     boolean
    redistribution?: boolean
    author?:         string
  }
  /** Optional loadout / preset selections — what the demo's UI panel
   *  has selected. Round-trips so a saved character restores its outfit
   *  and expression. Strings are treated as opaque tokens by this module
   *  — the demo validates them against its own enums on load. */
  loadout?: {
    armor?:       string
    hair?:        string
    cape?:        boolean
    capePattern?: string
    grenades?:    boolean
    expression?:  string
    proportion?:  string
    hands?:       string
    feet?:        string
    helm?:        string
  }
  /** Optional anatomy profile overrides — each entry is a 4-control-point
   *  cubic Bezier of radii along the corresponding curve (limb beziers in
   *  `limbs` keyed by limb name; anatomy curves in `anatomy` keyed by
   *  AnatomyCurve.name). The demo's emission resolves these against the
   *  active rig + DEFAULT_ANATOMY at load time. Missing entries fall
   *  back to engine defaults — partial overrides are valid. The
   *  combination of these knobs is the character's "muscularity / sex
   *  characteristics" surface. */
  profiles?: {
    limbs?:   Record<string, [number, number, number, number]>
    anatomy?: Record<string, [number, number, number, number]>
  }
}

/** V1 legacy shape — kept for backward-compat load. */
export interface CharacterSpecV1 {
  version: 1
  name: string
  proportions: Record<string, number>
  palette: Record<string, PaletteEntry>
  license?: CharacterSpecV2['license']
}

export type AnyCharacterSpec = CharacterSpecV1 | CharacterSpecV2

/** Inputs to a serialize call — the runtime's current state. Pass what
 *  you have; missing pieces fall back to empty arrays (still valid). */
export interface SerializeInput {
  name:         string
  archetype:    CharacterArchetype
  proportions:  Record<string, number>
  palette:      Record<string, PaletteEntry>
  face:         FaceFeature[]
  hair:         HairPart[]
  bodyParts:    BodyPart[]
  accessories:  Accessory[]
  license?:     CharacterSpecV2['license']
  loadout?:     CharacterSpecV2['loadout']
  profiles?:    CharacterSpecV2['profiles']
}

export function serializeCharacterSpec(input: SerializeInput): CharacterSpecV2 {
  return {
    version:     2,
    name:        input.name,
    archetype:   cloneArchetype(input.archetype),
    proportions: { ...input.proportions },
    palette:     clonePalette(input.palette),
    face:        input.face.map(cloneAttached),
    hair:        input.hair.map(cloneAttached),
    bodyParts:   input.bodyParts.map(cloneAttached),
    accessories: input.accessories.map(cloneAttached),
    ...(input.license ? { license: { ...input.license } } : {}),
    ...(input.loadout ? { loadout: { ...input.loadout } } : {}),
    ...(input.profiles ? {
      profiles: {
        ...(input.profiles.limbs   ? { limbs:   { ...input.profiles.limbs   } } : {}),
        ...(input.profiles.anatomy ? { anatomy: { ...input.profiles.anatomy } } : {}),
      },
    } : {}),
  }
}

/** Migrate any supported version to V2. V1 inputs get empty face/hair/body/
 *  accessory arrays and an empty archetype; callers should merge defaults
 *  on top if those are load-bearing for rendering. */
export function upgradeSpec(spec: AnyCharacterSpec, defaults: CharacterArchetype): CharacterSpecV2 {
  if (spec.version === 2) return spec
  // V1 → V2: promote known fields, fill archetype from defaults, face/hair/
  // body/accessories stay empty (caller merges in engine defaults).
  return {
    version:     2,
    name:        spec.name ?? 'unnamed',
    archetype:   cloneArchetype(defaults),
    proportions: { ...spec.proportions },
    palette:     clonePalette(spec.palette ?? {}),
    face:        [],
    hair:        [],
    bodyParts:   [],
    accessories: [],
    ...(spec.license ? { license: { ...spec.license } } : {}),
  }
}

/** Parse + migrate. Throws if the JSON is structurally invalid. */
export function parseCharacterSpec(json: string, defaults: CharacterArchetype): CharacterSpecV2 {
  const raw = JSON.parse(json) as AnyCharacterSpec
  if (raw?.version !== 1 && raw?.version !== 2) {
    throw new Error(`unknown character spec version: ${(raw as { version?: unknown })?.version}`)
  }
  return upgradeSpec(raw, defaults)
}

/** Pretty-print for on-disk storage. Stable key order via JSON.stringify's
 *  default enumeration — good enough for diffability. */
export function stringifyCharacterSpec(spec: CharacterSpecV2, indent = 2): string {
  return JSON.stringify(spec, null, indent)
}

// --- internals ---------------------------------------------------------

function cloneArchetype(a: CharacterArchetype): CharacterArchetype {
  return {
    centeredSizes:   cloneTripleRecord(a.centeredSizes),
    centeredOffsets: cloneTripleRecord(a.centeredOffsets),
    limbThickness:   clonePairRecord(a.limbThickness),
  }
}

function clonePalette(p: Record<string, PaletteEntry>): Record<string, PaletteEntry> {
  const out: Record<string, PaletteEntry> = {}
  for (const k of Object.keys(p)) out[k] = [p[k][0], p[k][1], p[k][2]]
  return out
}

function cloneTripleRecord(r: Record<string, [number, number, number]>): Record<string, [number, number, number]> {
  const out: Record<string, [number, number, number]> = {}
  for (const k of Object.keys(r)) out[k] = [r[k][0], r[k][1], r[k][2]]
  return out
}

function clonePairRecord(r: Record<string, [number, number]>): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {}
  for (const k of Object.keys(r)) out[k] = [r[k][0], r[k][1]]
  return out
}

/** FaceFeature / HairPart / BodyPart / Accessory all share the same field
 *  shape (name, parentName, offset, displaySize, optional rotationDeg). */
function cloneAttached<T extends {
  name: string
  parentName: string
  offset: [number, number, number]
  displaySize: [number, number, number]
  rotationDeg?: [number, number, number]
}>(item: T): T {
  const copy: T = {
    ...item,
    offset:      [item.offset[0], item.offset[1], item.offset[2]],
    displaySize: [item.displaySize[0], item.displaySize[1], item.displaySize[2]],
  }
  if (item.rotationDeg) {
    copy.rotationDeg = [item.rotationDeg[0], item.rotationDeg[1], item.rotationDeg[2]]
  }
  return copy
}
