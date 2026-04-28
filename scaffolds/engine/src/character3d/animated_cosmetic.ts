/**
 * Animated cosmetic — standardized format for ANY rigged accessory
 * with its own bones + animations that drops onto a host character.
 *
 * Use cases this format covers (in priority order):
 *   - Wings (flap / idle / fold)
 *   - Tails (sway / wag / curl)
 *   - Capes & cloaks (drift / wind)
 *   - Ears (twitch / perk)
 *   - Floating familiars / pets / aura ribbons
 *   - Mustache / beard wiggle
 *   - Hair tufts that bounce on motion
 *
 * KEY DESIGN PRINCIPLES
 *
 * 1. ATTACH TO A SOCKET. Every cosmetic declares ONE host-rig bone
 *    name as its parent socket. The cosmetic's own bone hierarchy
 *    sprouts from that socket; runtime splices the cosmetic bones
 *    into the host rig at composition time.
 *
 * 2. SELF-CONTAINED ANIMATIONS. Animations drive the COSMETIC'S
 *    bones only (they don't know or care about the host). The bones
 *    are keyed by name (`WingL_Anchor`, `Tail_Seg2`, etc.) so the
 *    same animation source applies to any cosmetic that uses the
 *    same bone naming convention.
 *
 * 3. ADDITIVE EULER DELTAS. Animations store per-frame Euler XYZ
 *    deltas applied ON TOP of the bone's bind preRotation. This
 *    means a cosmetic's BIND POSE comes from its own bone defs;
 *    animations just nudge from there. Cheaper to author, cheaper
 *    to overlay (don't have to know the bind orientation to drive
 *    the animation).
 *
 * 4. PRIM EMISSION DECLARATIVE. The cosmetic ships its SDF prims
 *    inline — the host doesn't need to know what shape the cosmetic
 *    renders, it just splices bones + emits prims at composition.
 *
 * 5. ONE FILE PER COSMETIC. `<name>.cos.json` packages bones +
 *    prims + animations together. Authoring tool (TS module) writes
 *    these via a bake script; runtime fetches + parses.
 *
 * COMPOSITION AT RUNTIME (not yet implemented — design target)
 *
 *   1. Host character rig loads as usual (Mixamo VAT or creature_rig).
 *   2. For each equipped cosmetic:
 *      a. Look up the socket bone in the host rig.
 *      b. Splice cosmetic bones into the host rig array, with
 *         socket bone as the parent of any cosmetic bone with
 *         parent === -1.
 *      c. Add prims to the host's prim list.
 *   3. Composer extension: for each frame, BEFORE world-mat compose:
 *      a. Read host body anim's local matrices.
 *      b. For each cosmetic, read its current animation's deltas
 *         for this frame and apply on top of the bind preRotation.
 *   4. World matrices propagate normally through the host's compose.
 *
 * FILE EXTENSION: `.cos.json` (cosmetic source).
 * MANIFEST: `cosmetic_manifest.json` lists cosmetics with file refs.
 */

import type { Vec3 } from '../math/vec'

/** One bone in the cosmetic's local hierarchy. parent indices
 *  reference earlier entries in the same `bones` array. parent = -1
 *  means "attach to the host's socket bone" (resolved at composition
 *  time). preRotation is Euler XYZ in radians, applied to the
 *  bone's local frame at bind. */
export interface CosmeticBone {
  name: string
  parent: number           // index into bones[] OR -1 for socket-attach
  offset: Vec3             // local translation in parent's frame
  preRotation?: Vec3       // local Euler XYZ at bind, optional
}

/** SDF primitive emitted at composition. Same shape as RaymarchPrimitive
 *  but with bone REFERENCED BY NAME instead of index — runtime resolves
 *  to the index after splicing into the host rig. paletteSlot is also
 *  a string key (resolved against host material's namedSlots). */
export interface CosmeticPrim {
  type: number             // matches RaymarchPrimitive.type IDs
  bone: string             // cosmetic bone name OR host bone name
  paletteSlot: string      // semantic slot key (e.g. 'feather')
  params: [number, number, number, number]
  offsetInBone: Vec3
  rotation?: [number, number, number, number]   // optional quat
  blendGroup?: number
  blendRadius?: number
}

/** Per-frame additive Euler XYZ delta keyed by bone name. Frame
 *  count and fps live on the parent CosmeticAnimation. Missing bones
 *  inherit bind pose; extra bones in the dict (not present in the
 *  cosmetic's own bones[]) are silently ignored. */
export type AnimationFrame = Record<string, Vec3>

/** Single named animation (idle, flap, fold, sway, wag, ...). */
export interface CosmeticAnimation {
  tag: string
  fps: number
  numFrames: number
  durationSec: number
  /** Length === numFrames. Each entry is the bone-deltas for that
   *  frame; the runtime interpolates between adjacent frames if the
   *  playback time falls between. */
  frames: AnimationFrame[]
}

/** Complete cosmetic — what ships as a `.cos.json` file. */
export interface AnimatedCosmetic {
  /** Schema version — bump when the format changes. */
  schema: 1
  /** Stable identifier for save files / equip slots. */
  name: string
  /** Coarse category for UI grouping. */
  category: 'wings' | 'tail' | 'cape' | 'ears' | 'hair' | 'aura' | 'familiar' | 'other'
  /** Default socket — bone name on the host rig where this cosmetic
   *  attaches. The host can override at equip time (e.g. wings
   *  socketed on Spine2 vs upper-back midpoint vs Hips). */
  defaultSocket: string
  /** Local bone hierarchy. Splice into host rig at composition. */
  bones: CosmeticBone[]
  /** SDF primitives. boneIdx resolves against the cosmetic's own
   *  bones[] by name, NOT the host rig (runtime handles the splice). */
  prims: CosmeticPrim[]
  /** Animations keyed by tag. The cosmetic ships with a default
   *  resting animation (usually 'idle') that plays when no specific
   *  state is set. */
  animations: Record<string, CosmeticAnimation>
  /** Default animation tag to play when equipped, before any state
   *  override. */
  defaultAnim: string
}

/** Manifest listing — same role as anim_manifest.json for human anims.
 *  Shipped as cosmetic_manifest.json. */
export interface CosmeticManifestEntry {
  /** Stable name used to fetch the .cos.json. */
  name: string
  /** Category (mirrors AnimatedCosmetic.category). */
  category: AnimatedCosmetic['category']
  /** Path to the .cos.json file (relative to public/). */
  url: string
}

export interface CosmeticManifest {
  version: 1
  cosmetics: CosmeticManifestEntry[]
}
