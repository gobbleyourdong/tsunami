/**
 * Runtime loader for a baked-Mixamo JSON (produced offline by
 * scripts/bake_mixamo.mjs). Converts the generic pose-frames format into
 * the shape bakeSkeletonVAT expects: a Joint[] rig + a RotationSampler.
 *
 * The JSON is source-agnostic — same loader would work for any per-frame
 * euler-rotation tracks keyed by the same joint hierarchy.
 */

import type { Vec3 } from '../math/vec'
import type { Joint, RotationSampler } from './skeleton'
import { DEFAULT_ANATOMY, FACE_ANCHORS, type AnatomyCurve, type AnatomyAnchor } from './anatomy'
import { DEFAULT_ATTACHMENTS, type AttachmentPart } from './attachments'

export interface MixamoBake {
  source: string
  fps: number
  numFrames: number
  durationSec: number
  joints: { name: string; parent: number; offset: Vec3; preRotation?: Vec3 }[]
  poses: { r: Vec3; t: Vec3 }[][]
}

export interface LoadedMixamo {
  rig: Joint[]
  sampler: RotationSampler
  boneDisplayMats: Float32Array   // per-joint mat4 (16 floats) column-major
  fps: number
  numFrames: number
  durationSec: number
}

/** Per-bone DISPLAY matrix: transforms a unit cube (±1 in each axis) into
 *  a bone-shaped box that extends FROM the joint origin TOWARD the first
 *  child's rest position. Result: each bone actually looks like a limb
 *  pointing down the skeleton instead of a floating elongated block.
 *
 *  Composition (applied right-to-left to vertex positions):
 *    rotate(+Y → boneDir) · translate(0, length/2, 0) · scale(thick, length/2, thick)
 *
 *  vPos = (0, -1, 0) → (0, 0, 0)           joint origin
 *  vPos = (0,  1, 0) → (length * boneDir)  where the child sits
 *
 *  Packed as column-major mat4 to match the VAT convention (4 vec4f per bone).
 */
function computeBoneDisplayMats(rig: Joint[]): Float32Array {
  const THICK = 0.04
  const LEAF_SIZE = 0.04
  const out = new Float32Array(rig.length * 16)

  for (let j = 0; j < rig.length; j++) {
    // Find first child whose parent is this bone, pick its offset as direction.
    let childOffset: [number, number, number] | null = null
    for (let k = 0; k < rig.length; k++) {
      if (rig[k].parent !== j) continue
      const o = rig[k].offset
      const len = Math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
      if (len > 1e-6) { childOffset = [o[0], o[1], o[2]]; break }
    }

    let dir: [number, number, number]
    let length: number
    if (childOffset) {
      length = Math.sqrt(
        childOffset[0] * childOffset[0] +
        childOffset[1] * childOffset[1] +
        childOffset[2] * childOffset[2]
      )
      dir = [childOffset[0] / length, childOffset[1] / length, childOffset[2] / length]
    } else {
      length = LEAF_SIZE
      dir = [0, 1, 0]          // leaf: default to +Y
    }

    // Build orthonormal frame with Y = bone direction. Pick a perpendicular
    // X axis (world-X unless too aligned with dir, else world-Z).
    let px: [number, number, number] = Math.abs(dir[0]) < 0.9 ? [1, 0, 0] : [0, 0, 1]
    // Z = dir × px (normalized)
    let zx = dir[1] * px[2] - dir[2] * px[1]
    let zy = dir[2] * px[0] - dir[0] * px[2]
    let zz = dir[0] * px[1] - dir[1] * px[0]
    const zLen = Math.sqrt(zx * zx + zy * zy + zz * zz)
    zx /= zLen; zy /= zLen; zz /= zLen
    // X = Y × Z  →  re-derive an in-plane X axis
    const xx = dir[1] * zz - dir[2] * zy
    const xy = dir[2] * zx - dir[0] * zz
    const xz = dir[0] * zy - dir[1] * zx

    // Column-major mat4 = [col0(X*thick), col1(Y*length/2), col2(Z*thick), col3(translation)]
    // Translation = (dir * length/2) so cube base sits at joint origin.
    const half = length / 2
    const base = j * 16

    out[base + 0]  = xx * THICK
    out[base + 1]  = xy * THICK
    out[base + 2]  = xz * THICK
    out[base + 3]  = 0

    out[base + 4]  = dir[0] * half
    out[base + 5]  = dir[1] * half
    out[base + 6]  = dir[2] * half
    out[base + 7]  = 0

    out[base + 8]  = zx * THICK
    out[base + 9]  = zy * THICK
    out[base + 10] = zz * THICK
    out[base + 11] = 0

    out[base + 12] = dir[0] * half
    out[base + 13] = dir[1] * half
    out[base + 14] = dir[2] * half
    out[base + 15] = 1
  }
  return out
}

/** Mixamo ships at cm scale (~100 units ~= 1m). Our demo scene uses meters.
 *  Scale all offsets by this factor when constructing the rig. */
const UNIT_SCALE = 0.01

export async function loadMixamoBake(url: string): Promise<LoadedMixamo> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`Mixamo bake fetch failed: ${url} (${resp.status})`)
  const data: MixamoBake = await resp.json()

  const rig: Joint[] = data.joints.map((j) => ({
    name: j.name,
    parent: j.parent,
    offset: [j.offset[0] * UNIT_SCALE, j.offset[1] * UNIT_SCALE, j.offset[2] * UNIT_SCALE],
    // preRotation already stored in radians by the baker; pass through as-is.
    preRotation: j.preRotation ? [j.preRotation[0], j.preRotation[1], j.preRotation[2]] : [0, 0, 0],
  }))

  // Pre-scale per-frame translation tracks from cm → m so they match the
  // already-scaled rest offsets. Done once up front to avoid per-frame
  // allocation in the hot sampler.
  const scaledT: Vec3[][] = data.poses.map((framePoses) =>
    framePoses.map((p) => [p.t[0] * UNIT_SCALE, p.t[1] * UNIT_SCALE, p.t[2] * UNIT_SCALE])
  )

  // Phase convention (matches procedural samplers): `phase` ∈ [0, 2π) spans
  // one full loop. Map to a continuous frame index, then linearly interpolate
  // rotation + translation between the two adjacent keyframes. Wraps around
  // so frame N-1 interpolates toward frame 0 (cycle-closure).
  const TAU = Math.PI * 2
  const sampler: RotationSampler = (phase, jointIdx) => {
    const t01 = ((phase / TAU) % 1 + 1) % 1                 // [0, 1), wrap-safe
    const continuousFrame = t01 * data.numFrames
    const f0 = Math.floor(continuousFrame) % data.numFrames
    const f1 = (f0 + 1) % data.numFrames
    const a = continuousFrame - Math.floor(continuousFrame) // [0, 1) blend

    const r0 = data.poses[f0][jointIdx].r
    const r1 = data.poses[f1][jointIdx].r
    const t0 = scaledT[f0][jointIdx]
    const t1 = scaledT[f1][jointIdx]
    const inv = 1 - a

    return {
      r: [r0[0] * inv + r1[0] * a, r0[1] * inv + r1[1] * a, r0[2] * inv + r1[2] * a],
      t: [t0[0] * inv + t1[0] * a, t0[1] * inv + t1[1] * a, t0[2] * inv + t1[2] * a],
    }
  }

  return {
    rig,
    sampler,
    boneDisplayMats: computeBoneDisplayMats(rig),
    fps: data.fps,
    numFrames: data.numFrames,
    durationSec: data.durationSec,
  }
}

/** Default display matrices for procedural rigs: plain scaled identity
 *  (each bone is a centered cube, no direction alignment). */
export function uniformBoneDisplayMats(numJoints: number, size = 0.06): Float32Array {
  const out = new Float32Array(numJoints * 16)
  for (let j = 0; j < numJoints; j++) {
    const base = j * 16
    out[base + 0]  = size        // col0.x
    out[base + 5]  = size        // col1.y
    out[base + 10] = size        // col2.z
    out[base + 15] = 1           // col3.w
  }
  return out
}

/** Sprite material = per-joint palette-slot index + the palette itself.
 *  Per user doctrine: sprite bake outputs palette indices, not colors; the
 *  material hosts the (semantic → slot) mapping so runtime edits to the
 *  palette texture recolor every affected joint without re-baking anything. */
export interface SpriteMaterial {
  paletteIndices: Uint32Array      // length = numJoints; value = palette slot 0..N
  palette: Float32Array             // length = numSlots × 4 (RGBA per slot)
  namedSlots: Record<string, number>    // semantic → slot (hair, skin, shirt, ...)
}

const CHIBI_SLOTS = {
  bg:        0,    // invisible / zero-size bones
  hair:      1,
  skin:      2,
  shirt:     3,
  pants:     4,
  shoes:     5,
  eyewhite:  6,
  pupil:     7,
  mouth:     8,
  nose:      9,
  weapon:    10,   // held accessories (sword, shield, staff, etc)
  accent:    11,   // pauldrons, belts, straps
  fire_base: 12,   // VFX ramp: deep red (bottom of flame)
  fire_mid:  13,   //           orange (mid)
  fire_tip:  14,   //           yellow (top)
  cape:      15,   // capes / robes / cloth chains driven by node particles
  armor:     16,   // wardrobe armor pieces (helmet, plates, gauntlets)
  cloth:     17,   // mage robe, hood — soft fabric look (cooler/duller)
  leather:   18,   // light armor straps, barbarian pads — warm tan/brown
}

/** Default chibi material: 6-slot palette, each visible body part bound
 *  to a semantic slot. Color swatches live entirely in `palette` — change
 *  palette[slot] and every bone using that slot recolors instantly. */
export function chibiMaterial(rig: Joint[]): SpriteMaterial {
  const PART_TO_SLOT: Record<string, number> = {
    Head:         CHIBI_SLOTS.skin,   // head reads as skin (face); hair layers later
    Neck:         CHIBI_SLOTS.skin,   // exposed neck reads as skin, not bg
    LeftShoulder: CHIBI_SLOTS.shirt,  // shoulder ball under the shirt
    RightShoulder:CHIBI_SLOTS.shirt,
    Spine:        CHIBI_SLOTS.shirt,  // mid-spine ellipsoid (potato sack)
    Spine1:       CHIBI_SLOTS.shirt,
    Spine2:       CHIBI_SLOTS.shirt,  // upper chest ellipsoid
    Hips:         CHIBI_SLOTS.pants,
    LeftArm:      CHIBI_SLOTS.skin,
    LeftForeArm:  CHIBI_SLOTS.skin,
    LeftHand:     CHIBI_SLOTS.skin,
    RightArm:     CHIBI_SLOTS.skin,
    RightForeArm: CHIBI_SLOTS.skin,
    RightHand:    CHIBI_SLOTS.skin,
    LeftUpLeg:    CHIBI_SLOTS.pants,
    LeftLeg:      CHIBI_SLOTS.pants,
    LeftFoot:     CHIBI_SLOTS.shoes,
    RightUpLeg:   CHIBI_SLOTS.pants,
    RightLeg:     CHIBI_SLOTS.pants,
    RightFoot:    CHIBI_SLOTS.shoes,
    // Face features (appended as virtual joints — see DEFAULT_FACE below).
    LeftEye:      CHIBI_SLOTS.eyewhite,
    RightEye:     CHIBI_SLOTS.eyewhite,
    LeftPupil:    CHIBI_SLOTS.pupil,
    RightPupil:   CHIBI_SLOTS.pupil,
    Mouth:        CHIBI_SLOTS.mouth,
    Nose:         CHIBI_SLOTS.nose,
    // Accessories (appended as virtual joints — see Accessory below).
    // Anything whose name starts with "Weapon" picks up the weapon slot;
    // "Accent" picks up accent. Per-accessory names live in the config.
  }
  function accessorySlot(name: string): number | undefined {
    if (/^Hair/.test(name)) return CHIBI_SLOTS.hair
    if (/Breast/.test(name)) return CHIBI_SLOTS.shirt
    if (/HipPad/.test(name)) return CHIBI_SLOTS.pants
    if (/^Cape/.test(name)) return CHIBI_SLOTS.cape
    if (/^Grenade/.test(name)) return CHIBI_SLOTS.weapon
    // Wardrobe armor pieces — route by outfit prefix so each outfit can
    // pick its own palette family without rewriting paletteIndices at
    // runtime. WP_Mage_* → cloth, WP_Light_* / WP_Barb_* → leather (with
    // chest plate exception), legacy WP_<role> (knight) → armor.
    if (/^WP_Belt$/.test(name) || /^WP_[A-Za-z]+_Belt$/.test(name)) return CHIBI_SLOTS.accent
    if (/^WP_Mage_/.test(name)) return CHIBI_SLOTS.cloth
    if (/^WP_Ninja_/.test(name)) return CHIBI_SLOTS.cloth
    if (/^WP_Light_(Chest|Plate)/.test(name)) return CHIBI_SLOTS.armor
    if (/^WP_Light_/.test(name)) return CHIBI_SLOTS.leather
    if (/^WP_Barb_/.test(name)) return CHIBI_SLOTS.leather
    if (/^WP_/.test(name)) return CHIBI_SLOTS.armor
    if (/^Weapon/i.test(name) || /Sword|Shield|Staff|Bow|Gun/.test(name)) return CHIBI_SLOTS.weapon
    if (/^Accent/i.test(name) || /Pauldron|Belt|Strap/.test(name)) return CHIBI_SLOTS.accent
    return undefined
  }

  const paletteIndices = new Uint32Array(rig.length)
  for (let j = 0; j < rig.length; j++) {
    const name = rig[j].name
    paletteIndices[j] = PART_TO_SLOT[name] ?? accessorySlot(name) ?? CHIBI_SLOTS.bg
  }

  const palette = new Float32Array(32 * 4)   // 32 slots — room for wardrobe / future expansion
  const setC = (slot: number, r: number, g: number, b: number) => {
    palette[slot * 4 + 0] = r
    palette[slot * 4 + 1] = g
    palette[slot * 4 + 2] = b
    palette[slot * 4 + 3] = 1
  }
  setC(CHIBI_SLOTS.bg,       0.0,  0.0,  0.0)
  setC(CHIBI_SLOTS.hair,     0.35, 0.2,  0.1 )    // dark brown hair (reserved)
  setC(CHIBI_SLOTS.skin,     0.95, 0.75, 0.6 )    // peach skin
  setC(CHIBI_SLOTS.shirt,    0.75, 0.25, 0.25)    // red shirt
  setC(CHIBI_SLOTS.pants,    0.15, 0.2,  0.45)    // dark-blue pants
  setC(CHIBI_SLOTS.shoes,    0.35, 0.2,  0.12)    // brown shoes
  setC(CHIBI_SLOTS.eyewhite, 0.95, 0.92, 0.88)    // warm off-white
  setC(CHIBI_SLOTS.pupil,    0.10, 0.08, 0.20)    // near-NAVY pupil
  setC(CHIBI_SLOTS.mouth,    0.55, 0.20, 0.25)    // desaturated red mouth
  setC(CHIBI_SLOTS.nose,     0.88, 0.65, 0.52)    // slightly-darker skin nose
  setC(CHIBI_SLOTS.weapon,    0.72, 0.72, 0.78)    // cool steel
  setC(CHIBI_SLOTS.accent,    0.40, 0.30, 0.18)    // dark leather
  setC(CHIBI_SLOTS.fire_base, 0.60, 0.10, 0.08)    // deep red (flame base)
  setC(CHIBI_SLOTS.fire_mid,  0.95, 0.45, 0.10)    // orange    (flame mid)
  setC(CHIBI_SLOTS.fire_tip,  1.00, 0.90, 0.30)    // yellow    (flame tip)
  setC(CHIBI_SLOTS.cape,      0.55, 0.10, 0.12)    // crimson cape
  setC(CHIBI_SLOTS.armor,     0.55, 0.58, 0.65)    // steel grey, faint cool tint
  setC(CHIBI_SLOTS.cloth,     0.30, 0.20, 0.45)    // mage robe — cool indigo
  setC(CHIBI_SLOTS.leather,   0.45, 0.28, 0.16)    // saddle leather — warm tan

  return { paletteIndices, palette, namedSlots: { ...CHIBI_SLOTS } }
}

/** Procedural per-joint palette (rainbow) for non-chibi rigs. Preserves
 *  the old "each joint a different color" look using the LUT system. */
export function defaultRainbowMaterial(numJoints: number): SpriteMaterial {
  const paletteIndices = new Uint32Array(numJoints)
  for (let j = 0; j < numJoints; j++) paletteIndices[j] = j % 16
  const palette = new Float32Array(32 * 4)   // 32 slots — room for wardrobe / future expansion
  for (let s = 0; s < 16; s++) {
    const h = s * 0.1373
    palette[s * 4 + 0] = 0.55 + 0.4 * Math.sin(h * 6.28)
    palette[s * 4 + 1] = 0.55 + 0.4 * Math.sin(h * 6.28 + 2.094)
    palette[s * 4 + 2] = 0.55 + 0.4 * Math.sin(h * 6.28 + 4.188)
    palette[s * 4 + 3] = 1
  }
  return { paletteIndices, palette, namedSlots: {} }
}

/** Face features as "virtual joints" — they don't exist in Mixamo's rig
 *  but we append them to the rig and localMats arrays so the same
 *  retargeting composer that drives the body also drives the face, and
 *  they inherit the head's proportion scale automatically. Each feature
 *  is parented to another joint by NAME (resolved to index at extend
 *  time) with an identity-rotation + offset local transform.
 *
 *  Offsets are in the parent's rest local frame. For features parented to
 *  Head: +Z is face-forward, +Y is up, ±X is character's left/right.
 *  Mixamo's Head joint has some PreRotation but in chibi display it reads
 *  as face-front, so these offsets tune visually against the giant head
 *  cube's front face at z ≈ +0.19.
 */
export interface FaceFeature {
  name: string
  parentName: string
  offset: [number, number, number]
  /** Centered cube half-extents (applied in chibiBoneDisplayMats). */
  displaySize: [number, number, number]
}

/** Accessory = a virtual joint attached to an existing rig bone with a
 *  static local transform. Same machinery as FaceFeature but with an
 *  optional rotation so a sword can extend perpendicular to the forearm
 *  without forcing the hand-joint's Y-axis to point wherever. The
 *  accessory's local transform composes as T × Rx*Ry*Rz in the parent
 *  bone's frame; display cube size is in the accessory's local frame.
 *
 *  This is how "weapon sockets" work: each accessory IS a socket. A
 *  character doc records `{parentName, offset, rotationDeg, displaySize}`
 *  per accessory — drop a different accessory in the same slot to swap
 *  the sprite, no animation rebake. */
export interface Accessory {
  name: string                                // must be unique across rig + face + accessories
  parentName: string                          // existing joint name
  offset: [number, number, number]            // translation in parent's local frame
  rotationDeg?: [number, number, number]      // XYZ Euler degrees, applied R=Rz*Ry*Rx
  displaySize: [number, number, number]       // cube half-extents
}

/** Hair part = same mechanism as face/accessories but semantically its
 *  own bucket so a character doc can swap hair without touching weapons.
 *  All hair pieces collect under the `hair` palette slot so a single
 *  color picker recolors the whole coif. */
export interface HairPart {
  name: string
  parentName: string
  offset: [number, number, number]
  rotationDeg?: [number, number, number]
  displaySize: [number, number, number]
}

/** Body-shape parts — secondary-sex-characteristic virtual joints.
 *  Defaults to zero scale so the character reads neutral unless a preset
 *  or slider enables them. Parented to existing rig bones (Spine2 for
 *  chest, Hips for pelvis). Same machinery as face/hair/accessories —
 *  they are AttachedParts living on the body. */
export interface BodyPart {
  name: string
  parentName: string
  offset: [number, number, number]
  rotationDeg?: [number, number, number]
  displaySize: [number, number, number]
  /** Optional shape override for /^WP_/ wardrobe pieces. If unset, the
   *  emitter falls back to a regex on the name (Helmet/Pauldron/Gauntlet
   *  → round, everything else → box). Lets new outfits use semantic
   *  names like WP_Mage_Hood while still picking the round primitive. */
  shape?: 'round' | 'box'
}

export const DEFAULT_BODY_PARTS: BodyPart[] = [
  // Secondary characteristics (breasts / hipPads) retired for now.
  // Re-introduce when the archetype system is rebuilt — they should
  // ride on a per-character body-shape spec, not on a baseline default.
]

/** Long hair — 5-segment chain hanging down from the back of the head.
 *  Chain physics in the demo (cape pattern reused): root locked to a
 *  back-of-head anchor that rotates with Head bone; mid/tip use one-frame-
 *  stale parent reads with distance clamp; body collision pushes
 *  particles out of head + shoulder bounding spheres. */
export const DEFAULT_LONG_HAIR: HairPart[] = [
  // Ponytail-style: 6 bones, narrow rectangular cross-section. Same
  // ribbon-chain primitive as the cape (type 23), just smaller and
  // anchored to Head. Cross-section halfW = 0.045 (9cm wide), halfT =
  // 0.030 (6cm thick) reads as a thick braid; for "flat hair flowing
  // back" make halfW > halfT (e.g., 0.10 × 0.025).
  { name: 'HairLong0', parentName: 'Head',      offset: [0,  0.10, -0.13], displaySize: [0.10, 0.10, 0.018] },
  { name: 'HairLong1', parentName: 'HairLong0', offset: [0, -0.10,  0.00], displaySize: [0.10, 0.10, 0.018] },
  { name: 'HairLong2', parentName: 'HairLong1', offset: [0, -0.10,  0.00], displaySize: [0.10, 0.10, 0.018] },
  { name: 'HairLong3', parentName: 'HairLong2', offset: [0, -0.10,  0.00], displaySize: [0.10, 0.10, 0.018] },
  { name: 'HairLong4', parentName: 'HairLong3', offset: [0, -0.10,  0.00], displaySize: [0.10, 0.10, 0.018] },
  // HairLong5 — positional-only endpoint joint for last segment's B side.
  { name: 'HairLong5', parentName: 'HairLong4', offset: [0, -0.10,  0.00], displaySize: [0.0, 0.0, 0.0] },
]

/** Bob hair — ellipsoid sitting on top of the cranium. Centred above
 *  the head sphere (head sphere center is at (0, 0.12, 0)) so the
 *  hair reads as a clear shell over the upper skull. Spring-driven on
 *  the Head bone for jiggle on quick head moves. Wider than the head
 *  in X/Z, slightly shorter in Y so the lower face stays exposed. */
export const DEFAULT_BOB_HAIR: HairPart[] = [
  // Forward-tilted hemisphere covering crown + forehead-front. Diagonal
  // hairline silhouette in profile (yarmulke pulled forward 25°).
  { name: 'HairBob',     parentName: 'Head', offset: [0, 0.23, -0.02], rotationDeg: [-25, 0, 0], displaySize: [0.19, 0.12, 0.19] },
  // Back-of-head dome.
  { name: 'HairBobBack', parentName: 'Head', offset: [0, 0.10, -0.05],                          displaySize: [0.18, 0.18, 0.16] },
  // Temple panels — drape the bob down at the FRONT-sides where the
  // back dome doesn't reach (HairBobBack at offset Z=-0.05 doesn't
  // extend to Z=+0.10, the temple region). Centered at temple-line:
  // X=±0.15 (just outside head halfX=0.165), Y=0.08 (ear-top), Z=+0.02
  // (slightly forward to wrap the temples). Bigger halfX/halfZ than
  // before so the panel is actually OUTBOARD of HairBobBack rather
  // than nested inside it. halfY=0.10 covers ear-top (Y=-0.02) up to
  // mid-head (Y=+0.18).
  { name: 'HairBobSideL', parentName: 'Head', offset: [-0.15, 0.16, -0.02],                       displaySize: [0.05, 0.10, 0.16] },
  { name: 'HairBobSideR', parentName: 'Head', offset: [ 0.15, 0.16, -0.02],                       displaySize: [0.05, 0.10, 0.16] },
]

/** Hair strands — face-framing side bangs. Two 3-segment ribbon chains,
 *  one per side, anchored to Spine2 (upper torso) at chest-front-shoulder
 *  height. Drapes straight DOWN with chain physics, framing the face
 *  from the sides. Anchored to torso rather than head so head rotation
 *  doesn't fling the bangs around — they hang relative to the body.
 *
 *  Was: six independent type-14 bent capsules (top tufts, front fringe,
 *  sideburns) with per-strand springs. Replaced with this chain layout
 *  because the bent-capsule version never read as actual hair — the
 *  capsules clipped the head and the spring jiggle was too local. Same
 *  emit slot (HairStrand* names) so loadout entries / saved-character
 *  files keep working.
 *
 *  Anchor: X = ±0.10 (ear-line), Y = +0.10 (toward neck), Z = +0.13
 *  (forward of body surface). 30cm total drape (3 segments × 0.10m).
 */
export const DEFAULT_HAIR_STRAND_L: HairPart[] = [
  // Left side strand — 3 visible segments + tip endpoint. Head-anchored
  // (same socket as HairLong ponytail) so bangs follow head rotation.
  // Anchor at temple-line: X just past head halfX (0.165), Y ear-level
  // (above head bone origin which sits near the jaw), Z just behind face.
  { name: 'HairStrandL0', parentName: 'Head',         offset: [-0.16,  0.15,  0.05], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandL1', parentName: 'HairStrandL0', offset: [ 0.00, -0.13,  0.00], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandL2', parentName: 'HairStrandL1', offset: [ 0.00, -0.13,  0.00], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandL3', parentName: 'HairStrandL2', offset: [ 0.00, -0.13,  0.00], displaySize: [0.000, 0.00, 0.000] },
]
export const DEFAULT_HAIR_STRAND_R: HairPart[] = [
  { name: 'HairStrandR0', parentName: 'Head',         offset: [ 0.16,  0.15,  0.05], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandR1', parentName: 'HairStrandR0', offset: [ 0.00, -0.13,  0.00], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandR2', parentName: 'HairStrandR1', offset: [ 0.00, -0.13,  0.00], displaySize: [0.045, 0.13, 0.032] },
  { name: 'HairStrandR3', parentName: 'HairStrandR2', offset: [ 0.00, -0.13,  0.00], displaySize: [0.000, 0.00, 0.000] },
]
/** Combined L+R strand set — used for rig extension (all bones present)
 *  and as legacy fallback when both bangs toggle on together. */
export const DEFAULT_HAIR_STRANDS: HairPart[] = [...DEFAULT_HAIR_STRAND_L, ...DEFAULT_HAIR_STRAND_R]

/** Spike-hair sets — Crono / DBZ-style cone clusters. Four independent
 *  groups so each axis (top, sides, back) can toggle on its own and
 *  combine for asymmetric silhouettes. Type-12 cone SDF where
 *  displaySize.x = base radius and displaySize.y = spike length.
 *  Permaslots: all bones live in the rig at init; loadout flags toggle
 *  emission. */

/** Compute the rotationDeg that aims a spike's bone +Y axis radially
 *  outward from the cranium center. Without this, hand-authored Euler
 *  values made every spike look like it pointed straight up in T-pose
 *  regardless of where it was anchored.
 *
 *  Math: target_dir = normalize(offset - head_center). Build a Z-then-X
 *  rotation that takes (0,1,0) to target_dir:
 *    γ (Z roll)   = -asin(dx)   — tilts +Y in the XY plane
 *    α (X pitch)  =  atan2(dz, dy) — tilts +Y in the YZ plane
 *  Y angle stays 0 (no twist around the spike's own axis). */
const HEAD_CENTER_LOCAL: [number, number, number] = [0, 0.12, 0]
function radialSpikeRot(offset: [number, number, number]): [number, number, number] {
  const dx = offset[0] - HEAD_CENTER_LOCAL[0]
  const dy = offset[1] - HEAD_CENTER_LOCAL[1]
  const dz = offset[2] - HEAD_CENTER_LOCAL[2]
  const mag = Math.hypot(dx, dy, dz) || 1
  const Dx = dx / mag, Dy = dy / mag, Dz = dz / mag
  const gamma = -Math.asin(Math.max(-1, Math.min(1, Dx))) * 180 / Math.PI
  const alpha =  Math.atan2(Dz, Dy) * 180 / Math.PI
  return [alpha, 0, gamma]
}

export const DEFAULT_SPIKE_TOP: HairPart[] = [
  // Anchors sunk into the cranium (Y values lower than the surface so the
  // cone base sits inside the bob ellipsoid; only the upper portion of
  // each cone emerges through the bob — the spike "grows through" rather
  // than perching on top). rotationDeg computed radially outward.
  { name: 'HairSpike0', parentName: 'Head', offset: [ 0.00, 0.20, -0.04], rotationDeg: radialSpikeRot([ 0.00, 0.20, -0.04]), displaySize: [0.050, 0.26, 0] },
  { name: 'HairSpike1', parentName: 'Head', offset: [-0.07, 0.20, -0.04], rotationDeg: radialSpikeRot([-0.07, 0.20, -0.04]), displaySize: [0.045, 0.24, 0] },
  { name: 'HairSpike2', parentName: 'Head', offset: [ 0.07, 0.20, -0.04], rotationDeg: radialSpikeRot([ 0.07, 0.20, -0.04]), displaySize: [0.045, 0.24, 0] },
  { name: 'HairSpike3', parentName: 'Head', offset: [-0.09, 0.16, -0.10], rotationDeg: radialSpikeRot([-0.09, 0.16, -0.10]), displaySize: [0.040, 0.22, 0] },
  { name: 'HairSpike4', parentName: 'Head', offset: [ 0.09, 0.16, -0.10], rotationDeg: radialSpikeRot([ 0.09, 0.16, -0.10]), displaySize: [0.040, 0.22, 0] },
]
/** Side spikes — 3 cones per side stacked vertically along the temple,
 *  pointing radially outward. */
export const DEFAULT_SPIKE_SIDE_L: HairPart[] = [
  { name: 'HairSpikeSideL0', parentName: 'Head', offset: [-0.10, 0.20, -0.02], rotationDeg: radialSpikeRot([-0.10, 0.20, -0.02]), displaySize: [0.035, 0.16, 0] },
  { name: 'HairSpikeSideL1', parentName: 'Head', offset: [-0.10, 0.13, -0.02], rotationDeg: radialSpikeRot([-0.10, 0.13, -0.02]), displaySize: [0.035, 0.16, 0] },
  { name: 'HairSpikeSideL2', parentName: 'Head', offset: [-0.10, 0.06, -0.04], rotationDeg: radialSpikeRot([-0.10, 0.06, -0.04]), displaySize: [0.032, 0.14, 0] },
]
export const DEFAULT_SPIKE_SIDE_R: HairPart[] = [
  { name: 'HairSpikeSideR0', parentName: 'Head', offset: [ 0.10, 0.20, -0.02], rotationDeg: radialSpikeRot([ 0.10, 0.20, -0.02]), displaySize: [0.035, 0.16, 0] },
  { name: 'HairSpikeSideR1', parentName: 'Head', offset: [ 0.10, 0.13, -0.02], rotationDeg: radialSpikeRot([ 0.10, 0.13, -0.02]), displaySize: [0.035, 0.16, 0] },
  { name: 'HairSpikeSideR2', parentName: 'Head', offset: [ 0.10, 0.06, -0.04], rotationDeg: radialSpikeRot([ 0.10, 0.06, -0.04]), displaySize: [0.032, 0.14, 0] },
]
/** Back spikes — 5 cones across the rear of the cranium (1 top center,
 *  2 upper L+R, 2 lower L+R), pointing radially outward. */
export const DEFAULT_SPIKE_BACK: HairPart[] = [
  { name: 'HairSpikeBack0', parentName: 'Head', offset: [ 0.00, 0.20, -0.10], rotationDeg: radialSpikeRot([ 0.00, 0.20, -0.10]), displaySize: [0.045, 0.22, 0] },
  { name: 'HairSpikeBack1', parentName: 'Head', offset: [-0.07, 0.18, -0.10], rotationDeg: radialSpikeRot([-0.07, 0.18, -0.10]), displaySize: [0.040, 0.20, 0] },
  { name: 'HairSpikeBack2', parentName: 'Head', offset: [ 0.07, 0.18, -0.10], rotationDeg: radialSpikeRot([ 0.07, 0.18, -0.10]), displaySize: [0.040, 0.20, 0] },
  { name: 'HairSpikeBack3', parentName: 'Head', offset: [-0.05, 0.08, -0.10], rotationDeg: radialSpikeRot([-0.05, 0.08, -0.10]), displaySize: [0.038, 0.20, 0] },
  { name: 'HairSpikeBack4', parentName: 'Head', offset: [ 0.05, 0.08, -0.10], rotationDeg: radialSpikeRot([ 0.05, 0.08, -0.10]), displaySize: [0.038, 0.20, 0] },
]

/** Nose-bridge attachment socket — single bone parented to Head,
 *  positioned where the bridge of the nose sits. Used as the anchor
 *  for SDF face accessories (nose itself, moustache, glasses, etc.)
 *  via NOSE_LIBRARY in attachments.ts. Anchor only; emits no geometry
 *  itself — the loadout's nose entry pushes the actual prims onto
 *  this bone (same pattern as HAND_LIBRARY / FOOT_LIBRARY).
 *
 *  Offset is in Head-local meters: forward (+Z, face direction), small
 *  upward bias (+Y) so the bridge sits between the eyes rather than
 *  at chin height. Not under any chibi/realistic scale group — the
 *  Head-group scale stretches it to match cranium size. */
export const DEFAULT_NOSE_BRIDGE: BodyPart[] = [
  // Offset matches the head ellipsoid's front-center (CHIBI_CENTERED_OFFSET
  // Head [0, 0.12, 0] + halfZ 0.17 = front of face in head-local meters).
  // NoseBridge is in the head scale group via the GROUP_PATTERNS regex,
  // so this bind offset multiplies by the head's chibi/stylized scale —
  // a 1.7× chibi head pushes NoseBridge to z=0.289, on the chibi face.
  { name: 'NoseBridge', parentName: 'Head', offset: [0, 0.12, 0.17], displaySize: [0, 0, 0] },
]

/** Grenade belt — two small spheres on the Hips, driven by per-grenade
 *  springs (jiggle on running). Use weapon palette slot. */
export const DEFAULT_GRENADE_BELT: BodyPart[] = [
  // Round grenade — sphere-shaped, classic baseball form.
  { name: 'GrenadeL', parentName: 'Hips', offset: [ 0.115, -0.025, 0.095], displaySize: [0.060, 0.060, 0.060] },
  // Can grenade — elongated cylinder/pill (smoke-bomb style). Same SDF
  // type (ellipsoid via primitive emission) but elongated in Y.
  { name: 'GrenadeR', parentName: 'Hips', offset: [-0.115, -0.025, 0.095], displaySize: [0.050, 0.085, 0.050] },
]

/** Cape — three-segment chain hanging behind Spine2. Each segment is a
 *  thin roundedBox in palette slot `cape` and blend group 9, so the
 *  three segments smin together as one cloth volume but stay visually
 *  distinct from the body. Bone hierarchy chains through CapeRoot →
 *  CapeMid → CapeTip so node particles can drive each segment to lag
 *  the previous in the chain.
 *
 *  Empty by default — characters opt in by passing this (or a custom
 *  cape config) to extendRigWithBodyParts. */
export const DEFAULT_CAPE_PARTS: BodyPart[] = [
  // 5-segment cape: Cape0 (root, locked to shoulders) → Cape4 (tip).
  // Each subsequent segment hangs 0.18m below its parent → ~0.72m
  // total drape from shoulders to mid-thigh. Width flares slightly
  // toward the bottom for a heroic-cape silhouette. Cape0's offset
  // attaches at shoulder height (Y +0.10 above Spine2 centre) and
  // clear of the torso back (Z -0.20 vs Spine2 back at ~-0.12).
  // halfY 0.13 (was 0.10): primitive extends 0.13m each side of segment
  // centre, segments are 0.18m apart → 0.08m overlap with neighbour
  // (each side). Blend group 9 with radius 0.08 fuses them into one cloth
  // volume. Without enough overlap, smin can't bridge the seam and the
  // cape reads as discrete stacked blocks.
  // 5-segment cape (Cape0..Cape5). halfW = 0.20 (40cm wide),
  // halfT = 0.032 (6.4cm thick), spacing 0.1854m per segment (+3%).
  // Anchor at Spine2 local (0, 0.05, -0.13) — slightly higher toward
  // the neck and a touch closer to the body's back surface.
  { name: 'Cape0', parentName: 'Spine2', offset: [0,  0.05, -0.13], displaySize: [0.200, 0.13, 0.032] },
  { name: 'Cape1', parentName: 'Cape0',  offset: [0, -0.1854, 0.00], displaySize: [0.200, 0.13, 0.032] },
  { name: 'Cape2', parentName: 'Cape1',  offset: [0, -0.1854, 0.00], displaySize: [0.200, 0.13, 0.032] },
  { name: 'Cape3', parentName: 'Cape2',  offset: [0, -0.1854, 0.00], displaySize: [0.200, 0.13, 0.032] },
  { name: 'Cape4', parentName: 'Cape3',  offset: [0, -0.1854, 0.00], displaySize: [0.200, 0.13, 0.032] },
  { name: 'Cape5', parentName: 'Cape4',  offset: [0, -0.1854, 0.00], displaySize: [0.0, 0.0, 0.0] },
]

export function extendRigWithBodyParts(rig: Joint[], items: BodyPart[] = DEFAULT_BODY_PARTS): Joint[] {
  const out: Joint[] = rig.map((j) => ({ ...j }))
  const nameToIdx = new Map<string, number>()
  for (let j = 0; j < out.length; j++) nameToIdx.set(out[j].name, j)
  for (const b of items) {
    const parentIdx = nameToIdx.get(b.parentName)
    if (parentIdx === undefined) {
      console.warn(`body part ${b.name}: parent "${b.parentName}" not found; skipping`)
      continue
    }
    const idx = out.length
    out.push({ name: b.name, parent: parentIdx, offset: [...b.offset] })
    nameToIdx.set(b.name, idx)
  }
  return out
}

export function extendLocalMatsWithBodyParts(
  localMats: Float32Array,
  numFrames: number,
  origNumJoints: number,
  items: BodyPart[] = DEFAULT_BODY_PARTS,
): Float32Array {
  const newNumJoints = origNumJoints + items.length
  const out = new Float32Array(numFrames * newNumJoints * 16)
  const staticLocals = items.map((b) => {
    const m = new Float32Array(16)
    if (b.rotationDeg) {
      eulerXYZToMat4Cols(b.rotationDeg[0], b.rotationDeg[1], b.rotationDeg[2], m)
    } else {
      m[0] = 1; m[5] = 1; m[10] = 1; m[15] = 1
    }
    m[12] = b.offset[0]
    m[13] = b.offset[1]
    m[14] = b.offset[2]
    return m
  })
  for (let f = 0; f < numFrames; f++) {
    const srcOff = f * origNumJoints * 16
    const dstOff = f * newNumJoints * 16
    out.set(localMats.subarray(srcOff, srcOff + origNumJoints * 16), dstOff)
    for (let k = 0; k < items.length; k++) {
      out.set(staticLocals[k], dstOff + (origNumJoints + k) * 16)
    }
  }
  return out
}

/** Hair removed for now — focused face treatment is just eyes + mouth
 *  as pixel-paint-on overlays, skin underneath. Hair comes back as
 *  either another overlay or a dedicated SDF primitive once the face
 *  glyph library stabilizes. */
export const DEFAULT_HAIR: HairPart[] = []

export function extendRigWithHair(rig: Joint[], items: HairPart[] = DEFAULT_HAIR): Joint[] {
  const out: Joint[] = rig.map((j) => ({ ...j }))
  const nameToIdx = new Map<string, number>()
  for (let j = 0; j < out.length; j++) nameToIdx.set(out[j].name, j)
  for (const h of items) {
    const parentIdx = nameToIdx.get(h.parentName)
    if (parentIdx === undefined) {
      console.warn(`hair ${h.name}: parent "${h.parentName}" not found; skipping`)
      continue
    }
    const idx = out.length
    out.push({ name: h.name, parent: parentIdx, offset: [...h.offset] })
    nameToIdx.set(h.name, idx)
  }
  return out
}

export function extendLocalMatsWithHair(
  localMats: Float32Array,
  numFrames: number,
  origNumJoints: number,
  items: HairPart[] = DEFAULT_HAIR,
): Float32Array {
  const newNumJoints = origNumJoints + items.length
  const out = new Float32Array(numFrames * newNumJoints * 16)
  const staticLocals = items.map((h) => {
    const m = new Float32Array(16)
    if (h.rotationDeg) {
      eulerXYZToMat4Cols(h.rotationDeg[0], h.rotationDeg[1], h.rotationDeg[2], m)
    } else {
      m[0] = 1; m[5] = 1; m[10] = 1; m[15] = 1
    }
    m[12] = h.offset[0]
    m[13] = h.offset[1]
    m[14] = h.offset[2]
    return m
  })
  for (let f = 0; f < numFrames; f++) {
    const srcOff = f * origNumJoints * 16
    const dstOff = f * newNumJoints * 16
    out.set(localMats.subarray(srcOff, srcOff + origNumJoints * 16), dstOff)
    for (let k = 0; k < items.length; k++) {
      out.set(staticLocals[k], dstOff + (origNumJoints + k) * 16)
    }
  }
  return out
}

/** DEFAULT_ACCESSORIES are ATTACHMENT POINTS — virtual joints that mark
 *  where items can mount on the rig (right-hand-weapon, left-hand-shield,
 *  back-scabbard, etc). The `displaySize` here is a PREVIEW size used
 *  when no item is equipped in the demo; in production this socket is
 *  invisible and the equipped item's own mesh/sprite renders at the
 *  socket's world transform.
 *
 *  The weapon itself is a SEPARATE ASSET (see equipped-item system in
 *  skeleton_demo.ts): character bakes once, weapons ship as their own
 *  files and are swapped at runtime without rebaking anything. Real
 *  weapons will ship with a per-angle atlas (4 cardinal for top-down,
 *  8 for iso, 2 mirrored for sidescrollers) and the renderer picks the
 *  closest angle from the socket's world rotation. */
export const DEFAULT_ACCESSORIES: Accessory[] = [
  {
    name: 'RightWeapon',
    parentName: 'RightHand',
    offset: [0.0, 0.25, 0.0],
    rotationDeg: [0, 0, 15],
    displaySize: [0.015, 0.22, 0.015],   // preview cube; overridden by equipped item
  },
]

/** Face features are PASTE-ON overlays now, not SDF primitives. Eyes,
 *  mouth, nose, etc. get stamped onto the rendered sprite in a post
 *  pass, indexed by expression — classic pixel-art face treatment.
 *  The face SDF is just the skin surface (skull + jaw + cheeks, all
 *  bound to the Head joint) so there's nothing muddy to fight with
 *  at sprite-tier resolution.
 *
 *  Kept as an empty export so the extendRigWithFace plumbing doesn't
 *  need to change; the overlay pass reads the Head joint's screen
 *  position directly. */
export const DEFAULT_FACE: FaceFeature[] = []

/** Append face features to a rig. Returns a new rig array; does not
 *  mutate the input. The order in `face` matters — parents must precede
 *  their children, and parentName must resolve against either the base
 *  rig or an already-appended face feature. */
export function extendRigWithFace(rig: Joint[], face: FaceFeature[] = DEFAULT_FACE): Joint[] {
  const out: Joint[] = rig.map((j) => ({ ...j }))
  const nameToIdx = new Map<string, number>()
  for (let j = 0; j < out.length; j++) nameToIdx.set(out[j].name, j)
  for (const f of face) {
    const parentIdx = nameToIdx.get(f.parentName)
    if (parentIdx === undefined) {
      console.warn(`face feature ${f.name}: parent "${f.parentName}" not found in rig; skipping`)
      continue
    }
    const idx = out.length
    out.push({ name: f.name, parent: parentIdx, offset: [...f.offset] })
    nameToIdx.set(f.name, idx)
  }
  return out
}

/** Append accessories to a rig. Behaves identically to extendRigWithFace
 *  but for the Accessory type. */
export function extendRigWithAccessories(rig: Joint[], items: Accessory[] = DEFAULT_ACCESSORIES): Joint[] {
  const out: Joint[] = rig.map((j) => ({ ...j }))
  const nameToIdx = new Map<string, number>()
  for (let j = 0; j < out.length; j++) nameToIdx.set(out[j].name, j)
  for (const a of items) {
    const parentIdx = nameToIdx.get(a.parentName)
    if (parentIdx === undefined) {
      console.warn(`accessory ${a.name}: parent "${a.parentName}" not found; skipping`)
      continue
    }
    const idx = out.length
    out.push({ name: a.name, parent: parentIdx, offset: [...a.offset] })
    nameToIdx.set(a.name, idx)
  }
  return out
}

/** Euler XYZ (degrees) → column-major mat4 rotation. Matches the
 *  convention used by the FBX baker (R = Rz * Ry * Rx).
 *  Inlined here so the loader doesn't drag in a math dep. */
function eulerXYZToMat4Cols(xDeg: number, yDeg: number, zDeg: number, out16: Float32Array) {
  const x = xDeg * Math.PI / 180, y = yDeg * Math.PI / 180, z = zDeg * Math.PI / 180
  const cx = Math.cos(x), sx = Math.sin(x), cy = Math.cos(y), sy = Math.sin(y), cz = Math.cos(z), sz = Math.sin(z)
  const m00 =  cy * cz,            m01 =  sx * sy * cz - cx * sz, m02 =  cx * sy * cz + sx * sz
  const m10 =  cy * sz,            m11 =  sx * sy * sz + cx * cz, m12 =  cx * sy * sz - sx * cz
  const m20 = -sy,                 m21 =  sx * cy,                m22 =  cx * cy
  // Column-major packing
  out16[0]  = m00; out16[1]  = m10; out16[2]  = m20; out16[3]  = 0
  out16[4]  = m01; out16[5]  = m11; out16[6]  = m21; out16[7]  = 0
  out16[8]  = m02; out16[9]  = m12; out16[10] = m22; out16[11] = 0
  out16[12] = 0;   out16[13] = 0;   out16[14] = 0;   out16[15] = 1
}

/** Append accessory local matrices to a localMats buffer. Each accessory
 *  gets a rotation (Euler XYZ) + translation, applied every frame so
 *  only the parent's animation drives the accessory's world transform. */
export function extendLocalMatsWithAccessories(
  localMats: Float32Array,
  numFrames: number,
  origNumJoints: number,
  items: Accessory[] = DEFAULT_ACCESSORIES,
): Float32Array {
  const newNumJoints = origNumJoints + items.length
  const out = new Float32Array(numFrames * newNumJoints * 16)
  // Pre-compute one rotation+translation mat4 per accessory (frame-invariant).
  const staticLocals = items.map((a) => {
    const m = new Float32Array(16)
    if (a.rotationDeg) {
      eulerXYZToMat4Cols(a.rotationDeg[0], a.rotationDeg[1], a.rotationDeg[2], m)
    } else {
      m[0] = 1; m[5] = 1; m[10] = 1; m[15] = 1
    }
    m[12] = a.offset[0]
    m[13] = a.offset[1]
    m[14] = a.offset[2]
    return m
  })
  for (let f = 0; f < numFrames; f++) {
    const srcOff = f * origNumJoints * 16
    const dstOff = f * newNumJoints * 16
    out.set(localMats.subarray(srcOff, srcOff + origNumJoints * 16), dstOff)
    for (let k = 0; k < items.length; k++) {
      out.set(staticLocals[k], dstOff + (origNumJoints + k) * 16)
    }
  }
  return out
}

/** Extend localMats (flat, frame-major) with identity-rotation + offset
 *  matrices for each face joint, repeated every frame. Face joints
 *  "animate" only through their parents (head rotation) — their own
 *  local matrix is static. */
/** Append anatomy anchor virtual joints to the rig. Anchors are
 *  POSITION-ONLY references — they emit no primitive but provide world
 *  positions that anatomy curves (jawline / brow / cheekbones) sample
 *  as bezier control points. Same shape as extendRigWithFace; the bone
 *  loop in chibiRaymarchPrimitives ignores them naturally because they
 *  match no emission map. */
export function extendRigWithAnchors(rig: Joint[], anchors: AnatomyAnchor[] = FACE_ANCHORS): Joint[] {
  const out: Joint[] = rig.map((j) => ({ ...j }))
  const nameToIdx = new Map<string, number>()
  for (let j = 0; j < out.length; j++) nameToIdx.set(out[j].name, j)
  for (const a of anchors) {
    const parentIdx = nameToIdx.get(a.parentName)
    if (parentIdx === undefined) {
      console.warn(`anatomy anchor ${a.name}: parent "${a.parentName}" not found in rig; skipping`)
      continue
    }
    const idx = out.length
    out.push({ name: a.name, parent: parentIdx, offset: [...a.offset] })
    nameToIdx.set(a.name, idx)
  }
  return out
}

export function extendLocalMatsWithAnchors(
  localMats: Float32Array,
  numFrames: number,
  origNumJoints: number,
  anchors: AnatomyAnchor[] = FACE_ANCHORS,
): Float32Array {
  const newNumJoints = origNumJoints + anchors.length
  const out = new Float32Array(numFrames * newNumJoints * 16)
  for (let f = 0; f < numFrames; f++) {
    const srcOff = f * origNumJoints * 16
    const dstOff = f * newNumJoints * 16
    out.set(localMats.subarray(srcOff, srcOff + origNumJoints * 16), dstOff)
    for (let k = 0; k < anchors.length; k++) {
      const base = dstOff + (origNumJoints + k) * 16
      out[base + 0]  = 1; out[base + 5]  = 1; out[base + 10] = 1; out[base + 15] = 1
      out[base + 12] = anchors[k].offset[0]
      out[base + 13] = anchors[k].offset[1]
      out[base + 14] = anchors[k].offset[2]
    }
  }
  return out
}

export function extendLocalMatsWithFace(
  localMats: Float32Array,
  numFrames: number,
  origNumJoints: number,
  face: FaceFeature[] = DEFAULT_FACE,
): Float32Array {
  const newNumJoints = origNumJoints + face.length
  const out = new Float32Array(numFrames * newNumJoints * 16)
  for (let f = 0; f < numFrames; f++) {
    const srcOff = f * origNumJoints * 16
    const dstOff = f * newNumJoints * 16
    // Copy existing body joints untouched.
    out.set(localMats.subarray(srcOff, srcOff + origNumJoints * 16), dstOff)
    // Append face joint locals: identity rotation, col3 = offset.
    for (let k = 0; k < face.length; k++) {
      const base = dstOff + (origNumJoints + k) * 16
      out[base + 0]  = 1; out[base + 5]  = 1; out[base + 10] = 1; out[base + 15] = 1
      out[base + 12] = face[k].offset[0]
      out[base + 13] = face[k].offset[1]
      out[base + 14] = face[k].offset[2]
    }
  }
  return out
}

// Shared chibi dimension tables — used by both the cube-renderer display
// mats (chibiBoneDisplayMats) and the raymarch-primitive enumeration
// (chibiRaymarchPrimitives). Keeping them module-level so tuning is a
// one-place edit.
export const CHIBI_LIMB_THICKNESS: Record<string, [number, number]> = {
  LeftArm:      [0.055, 0.055],
  LeftForeArm:  [0.05,  0.05 ],
  RightArm:     [0.055, 0.055],
  RightForeArm: [0.05,  0.05 ],
  LeftUpLeg:    [0.075, 0.075],
  LeftLeg:      [0.065, 0.065],
  LeftFoot:     [0.065, 0.09],
  RightUpLeg:   [0.075, 0.075],
  RightLeg:     [0.065, 0.065],
  RightFoot:    [0.065, 0.09],
}
export const CHIBI_CENTERED_SIZE: Record<string, [number, number, number]> = {
  // Head is an ellipsoid (anime-egg: slightly taller than wide, slight
  // depth bias for the face-forward dimension). Cone-jaw smin'd onto
  // the lower hemisphere + a small forehead bulge ellipsoid up front
  // give the silhouette real character vs. a plain ball + cone. The
  // shape is IDENTICAL across realistic/stylized/chibi — only the head
  // group's uniform scale changes between presets.
  //   X = ear-to-ear half-width
  //   Y = top-to-bottom half-height (taller for elongated face)
  //   Z = face-forward half-depth (slightly forward of X)
  Head:    [0.165, 0.20, 0.17],
  Neck:    [0.022, 0.06, 0.022],
  // Spine column. Both procedural (Hips → Spine1 → Spine2 → Head) and
  // Mixamo (Hips → Spine → Spine1 → Spine2 → Neck → Head) rigs emit
  // intermediate spine joints with ~0.3m offsets — if we only rendered
  // Spine1, the torso read as two disconnected oblate disks. We now
  // stamp an ellipsoid on every spine bone so blend group 6 has a
  // continuous column to smin across.
  // Skinny uniform column — torso is treated as one more "limb" for now,
  // not a sculpted barrel. All four sack-core bones share roughly the
  // same X/Z so smin produces a smooth tapered cylinder rather than a
  // staircase of barrels. Archetype-specific torso shaping is queued
  // for the rebuild; this is the baseline silhouette in the meantime.
  // Lozenge: narrow at hips (taper into upper-leg roots, no saddle
  // bags), narrow waist, wide mid, wide upper (taper out to meet the
  // shoulder spheres so they smin into the torso instead of sitting
  // off to the side as separate blobs). Y unchanged.
  Hips:    [0.135, 0.08, 0.110],   // wide enough to MEET the upper-leg cylinders
                                   // at their inner side — no smin across groups,
                                   // just visual contact at the groin seam
  Spine:   [0.137, 0.10, 0.117],   // waist
  Spine1:  [0.186, 0.15, 0.156],   // mid-torso bulge
  Spine2:  [0.176, 0.10, 0.137],   // upper — reaches shoulder balls
}
export const CHIBI_CENTERED_OFFSET: Record<string, [number, number, number]> = {
  Head: [0, 0.12, 0],
}

/** Raymarch equivalent of chibiBoneDisplayMats — enumerates the character
 *  rig (with face/hair/accessories/body parts already appended) into a
 *  flat RaymarchPrimitive-shaped descriptor list. Caller imports the
 *  type from raymarch_renderer.ts; we keep this module free of that
 *  dependency by returning a structural match.
 *
 *  Mixamo rig convention: bone +Y points toward the first child. So
 *  limbs render as axis-aligned cylinders/capsules in bone-local Y —
 *  no rotation needed per primitive. Centered parts (head/torso/hips/
 *  face features) use axis-aligned primitives at bone origin.  */
export interface RaymarchPrimDesc {
  type: number
  paletteSlot: number
  boneIdx: number
  params: [number, number, number, number]
  offsetInBone: [number, number, number]
  colorFunc?: number
  paletteSlotB?: number
  colorExtent?: number
  blendGroup?: number
  blendRadius?: number
  rotation?: [number, number, number, number]
  detailAmplitude?: number
  shiny?: boolean
  /** Tier-1 extraction from Unbound — sharp 45° bevel via Mercury hg_sdf
   *  formula instead of polynomial smin. Set per primitive. */
  chamfer?: boolean
  /** Tier-1 extraction — at upload time, expandMirrors() duplicates the
   *  prim with X-flipped offsetInBone. Halves authoring for symmetric
   *  features (horns, paired armor pieces). */
  mirrorYZ?: boolean
}

export function chibiRaymarchPrimitives(
  rig: Joint[],
  material: SpriteMaterial,
  face: FaceFeature[] = DEFAULT_FACE,
  accessories: Accessory[] = DEFAULT_ACCESSORIES,
  hair: HairPart[] = DEFAULT_HAIR,
  bodyParts: BodyPart[] = DEFAULT_BODY_PARTS,
  anatomy: AnatomyCurve[] = DEFAULT_ANATOMY,
  attachments: AttachmentPart[] = DEFAULT_ATTACHMENTS,
  helmStyle: 'none' | 'kettle' | 'horned' | 'pickelhaube' | 'greathelm' | 'sallet' | 'crested' | 'plumed' = 'none',
): RaymarchPrimDesc[] {
  const prims: RaymarchPrimDesc[] = []
  const faceByName = new Map(face.map((f) => [f.name, f]))
  const accByName = new Map(accessories.map((a) => [a.name, a]))
  const hairByName = new Map(hair.map((h) => [h.name, h]))
  const bodyByName = new Map(bodyParts.map((b) => [b.name, b]))

  for (let j = 0; j < rig.length; j++) {
    const name = rig[j].name
    const slot = material.paletteIndices[j]

    // 1) Core centered body parts — head is a SPHERE (perfect primitive,
    // shape stable across proportions), torso/hips are ellipsoids
    // (rounded mass for the potato-sack), neck stays a small box.
    const core = CHIBI_CENTERED_SIZE[name]
    if (core) {
      const off = CHIBI_CENTERED_OFFSET[name] ?? [0, 0, 0]
      const isSackCore = name === 'Spine' || name === 'Spine1' || name === 'Spine2' || name === 'Hips'
      // PHASE B — torso segment migration. Replace the 4 sack-core
      // ellipsoids (Hips, Spine, Spine1, Spine2) with 3 oval segments
      // between consecutive joints, using the existing per-bone X/Z
      // half-extents as cross-section radii. Same blendGroup=6, same
      // smin → torso reads as one continuous oval column instead of a
      // stack of disjoint ellipsoids.
      // Torso segments DISABLED — per-bone segment SDFs in bone-A-local
      // frames don't compose well under heavy animation (backflip etc).
      // Adjacent segments' cross-section ellipses live in different
      // bone-local orientations and the smin between them produces
      // joint kinks / explosions. Reverted to the ellipsoid stack which
      // is small-per-bone and bends gracefully under animation.
      // Kept the segment infrastructure (type 16/18 SDFs, decal layer)
      // for future use when bone-aware multi-segment skinning lands.
      const TORSO_SEGMENTS_ENABLED = false
      if (TORSO_SEGMENTS_ENABLED && (name === 'Spine' || name === 'Spine1' || name === 'Spine2' || name === 'Neck')) continue
      if (TORSO_SEGMENTS_ENABLED && name === 'Hips') {
        // Explicit per-segment cross-section profiles. Decoupled from
        // CHIBI_CENTERED_SIZE so the silhouette can express anatomy
        // (hips → narrow waist → broad chest) rather than just inherit
        // each bone's bounding ellipsoid. (raX, raZ) at A end + (rbX, rbZ)
        // at B end. Linear interp along t.
        // Each segment carries (raX, rbX) X radii + (rZpos, rZneg) per
        // end. raZpos = front-Z radius (chest/belly side), raZneg = back-Z
        // radius (spine side). Symmetric segments set rZpos = rZneg.
        // Anatomy migrates here: pec swell on Spine1→Spine2 (raZpos >
        // raZneg), glute on Hips→Spine (raZneg > raZpos at A end =
        // backward bulk at the hips).
        type TorsoSeg = {
          a: string; b: string;
          aRX: number; aZpos: number; aZneg: number;
          bRX: number; bZpos: number; bZneg: number;
          slot: number;
        }
        // Asymmetry tuned down — at strong spine bends (backflip mid-arc)
        // adjacent segments' directional-Z cross-sections don't align,
        // and smin between them produces visible bulge artifacts at the
        // joint. Keeping subtle Zpos/Zneg differences only at SEGMENT
        // INTERIORS, with symmetric ends for stable smin transitions.
        // Wider blendRadius (0.07 → 0.11) further softens joint kinks
        // under heavy animation.
        const torsoSegments: TorsoSeg[] = [
          { a: 'Hips',   b: 'Spine',
            aRX: 0.125, aZpos: 0.095, aZneg: 0.105,
            bRX: 0.095, bZpos: 0.078, bZneg: 0.078,
            slot: CHIBI_SLOTS.pants },
          { a: 'Spine',  b: 'Spine1',
            aRX: 0.095, aZpos: 0.078, aZneg: 0.078,
            bRX: 0.115, bZpos: 0.090, bZneg: 0.090,
            slot: CHIBI_SLOTS.shirt },
          { a: 'Spine1', b: 'Spine2',
            aRX: 0.115, aZpos: 0.090, aZneg: 0.090,
            bRX: 0.140, bZpos: 0.115, bZneg: 0.100,
            slot: CHIBI_SLOTS.shirt },
          { a: 'Spine2', b: 'Neck',
            aRX: 0.135, aZpos: 0.105, aZneg: 0.100,
            bRX: 0.050, bZpos: 0.050, bZneg: 0.050,
            slot: CHIBI_SLOTS.shirt },
          { a: 'Neck',   b: 'Head',
            aRX: 0.045, aZpos: 0.045, aZneg: 0.045,
            bRX: 0.050, bZpos: 0.050, bZneg: 0.050,
            slot: CHIBI_SLOTS.skin },
        ]
        for (const seg of torsoSegments) {
          const aIdx = rig.findIndex((rj) => rj.name === seg.a)
          const bIdx = rig.findIndex((rj) => rj.name === seg.b)
          if (aIdx < 0 || bIdx < 0) continue
          const bOff = rig[bIdx].offset
          const segLen = Math.hypot(bOff[0], bOff[1], bOff[2])
          prims.push({
            type: 18, paletteSlot: seg.slot, boneIdx: aIdx,
            params: [seg.aRX, seg.bRX, bIdx, segLen],
            offsetInBone: [0, 0, 0],
            blendGroup: 6, blendRadius: 0.11,
            rotation: [seg.aZpos, seg.aZneg, seg.bZpos, seg.bZneg],
          })
        }
        continue
      }
      // Head is now an ELLIPSOID (taller than wide). Earlier the head
      // was a uniform sphere, which made every face read identical
      // across characters and across proportions. The ellipsoid lets
      // the front-profile (Y) and ear-to-ear (X) dimensions vary
      // independently — anime-egg shape, then scaled uniformly per
      // proportion preset for chibi/stylized/realistic.
      const type = name === 'Head' ? 3 : isSackCore ? 3 : 1   // 3=ellipsoid, 1=box
      // Head gets a blend group so the jaw/chin ellipsoid (below) melds into
      // it as a single skin surface rather than showing a crease at the seam.
      // 0.03m blend radius → soft under-chin transition, hard enough that
      // the overall silhouette still reads as the chibi round head.
      // Skin detail: 2mm FBM displacement read only by the normal pass.
      // Too small to shift the silhouette; big enough to break up the
      // flat ellipsoid lighting into organic 3-band cel shading.
      //
      // "Potato sack" — upper/lower body fuse as one volume. Group 6
      // holds Spine1 + Hips + Neck + both Shoulders (shoulder sphere
      // reassigned below from its arm group to here). Arms stay in
      // their own chains (groups 2/3); where arm meets body there's
      // still a subtle cross-group seam, which we want — lets arms
      // articulate visually even though the torso itself is soft.
      // Palette slots stay per-primitive, so shirt→pants colour
      // boundaries are crisp inside one fused geometry.
      const centerExtras: Partial<RaymarchPrimDesc> =
        name === 'Head'
          ? { blendGroup: 1, blendRadius: 0.10, detailAmplitude: 0.002 }
        : (isSackCore || name === 'Neck')
          ? { blendGroup: 6, blendRadius: 0.07 }
        : {}
      // All centered parts now use the 3-axis ellipsoid — head reads as
      // anime-egg, spine/hips as oblate ellipsoids. The pixel-fit
      // chibi_head SDF (type 13) is shipped in the shader but parked
      // — its max-of-extrusions combine produces square-from-top
      // cross-sections; needs an elliptical-cross-section rebuild
      // before re-enabling.
      const corePrimParams: [number, number, number, number] = [core[0], core[1], core[2], 0]
      prims.push({
        type, paletteSlot: slot, boneIdx: j,
        params: corePrimParams,
        offsetInBone: [off[0], off[1], off[2]],
        ...centerExtras,
      })
      // Blank-face head build-out — just a tapered cone jaw for the chin
      // line. Cheeks, eye sockets, nose all removed: every face feature
      // (eyes, mouth, blush, tears) is drawn by the screen-space pixel
      // stamp in the outline shader, no SDF cost. Pure flat-skin head.
      if (name === 'Head') {
        // Cone jaw — tapered chin extending below the head ellipsoid.
        // Cone primitive (type 12) is "tip at origin, base at y=-h" by
        // default; rotation quat (1,0,0,0) flips it 180° around X so
        // the tip (chin point) faces DOWN.
        //
        // Half-angle 38° (was 45°) — narrower taper, the chin reads as
        // a chin instead of a triangular wedge under the head. Height
        // tied to the head's Y radius (was X) so the chin extends below
        // the elongated face shape, not the sphere-equator distance.
        // Big blend radius (0.10) so the cone-ellipsoid seam dissolves
        // into a continuous taper.
        const HEAD_HEIGHT_Y = core[1]
        const JAW_HALF_ANGLE_DEG = 38
        const JAW_HALF_ANGLE_SIN = Math.sin(JAW_HALF_ANGLE_DEG * Math.PI / 180)
        const JAW_HALF_ANGLE_COS = Math.cos(JAW_HALF_ANGLE_DEG * Math.PI / 180)
        const JAW_HEIGHT = HEAD_HEIGHT_Y * 0.95
        const jawTipY = off[1] - HEAD_HEIGHT_Y * 1.10
        prims.push({
          type: 12, paletteSlot: slot, boneIdx: j,
          params: [JAW_HALF_ANGLE_SIN, JAW_HALF_ANGLE_COS, JAW_HEIGHT, 0],
          offsetInBone: [off[0], jawTipY, off[2]],
          rotation: [1, 0, 0, 0],
          blendGroup: 1, blendRadius: 0.10,
          detailAmplitude: 0.002,
        })
      }
      continue
    }

    // 2) Face features — sphere/torus/roundedBox based on name.
    const ff = faceByName.get(name)
    if (ff) {
      let type = 1                             // default box
      let params: [number, number, number, number] = [ff.displaySize[0], ff.displaySize[1], ff.displaySize[2], 0]
      if (/Eye$|Pupil$/.test(name)) {
        type = 0                               // sphere
        params = [ff.displaySize[0], 0, 0, 0]
      } else if (name === 'Mouth') {
        type = 6                               // torus
        params = [ff.displaySize[0], ff.displaySize[2], 0, 0]
      } else if (name === 'Nose') {
        // Cone (type 12) — native orientation is tip at origin, base at -Y,
        // which reads as a chin spike. Rotate +90° about +X so local +Y
        // maps to world +Z (face-forward), and offset the primitive forward
        // by the cone height so the base sits at the face surface while
        // the tip extends out. (sin, cos) = (0.30, 0.954) ≈ 17° half-angle.
        type = 12
        const halfAngle = 0.30
        const height = ff.displaySize[1] * 2.0
        params = [Math.sin(halfAngle), Math.cos(halfAngle), height, 0]
        // quat for +90° about +X → takes local +Y to +Z
        const s = Math.SQRT1_2   // sin(π/4) = cos(π/4) = 0.7071...
        prims.push({
          type, paletteSlot: slot, boneIdx: j, params,
          offsetInBone: [0, 0, height],
          rotation: [s, 0, 0, s],
        })
        continue
      }
      prims.push({ type, paletteSlot: slot, boneIdx: j, params, offsetInBone: [0, 0, 0] })
      continue
    }

    // 3) Hair — rounded boxes (soft edges) by default, ellipsoid for
    // HairBob (single shell wrapping the cranium needs round, not boxy).
    // Long hair segments smin into one continuous strand via blend
    // group 12 (own group — keeps hair distinct from body / armor).
    const hp = hairByName.get(name)
    if (hp) {
      if (/^HairBob/.test(name)) {
        // Group 16 = bob ensemble (HairBob cap + HairBobBack panel).
        // 4cm blend radius so the two pieces fuse into one continuous
        // hair surface across the cranium, with the trapezoidal-taper
        // silhouette emerging from their union.
        prims.push({
          type: 3, paletteSlot: slot, boneIdx: j,
          params: [hp.displaySize[0], hp.displaySize[1], hp.displaySize[2], 0],
          offsetInBone: [0, 0, 0],
          blendGroup: 16, blendRadius: 0.07,
        })
      } else if (/^HairLong/.test(name)) {
        // Long hair — single type-23 ribbon-chain primitive walks
        // HairLong0..HairLong5 as a polyline. Same architecture as
        // cape, just anchored to Head with narrower cross-section.
        // Emit only for HairLong0; other bones contribute as chain
        // points but don't host their own primitive. Skip HairLong5
        // (positional-only endpoint joint).
        if (name !== 'HairLong0') continue
        const halfW     = hp.displaySize[0]
        const halfThick = hp.displaySize[2]
        const hairIndices: number[] = [j]
        for (let k = 1; k < 6; k++) {
          const idx = rig.findIndex((joint) => joint.name === `HairLong${k}`)
          if (idx >= 0) hairIndices.push(idx)
        }
        if (hairIndices.length < 2) continue
        const chainCount = hairIndices.length
        prims.push({
          type: 23, paletteSlot: slot, boneIdx: j,
          params: [chainCount, halfW, halfThick, 0],
          offsetInBone: [0, 0, 0],
          blendGroup: 12, blendRadius: 0,
        })
      } else if (/^HairSpike/.test(name)) {
        // Spike — type-12 cone primitive. Default cone is tip-at-origin
        // extending in -Y direction; offsetInBone shifts up by `height`
        // so the BASE sits at the bone origin (scalp anchor) and the
        // TIP extends up along the bone's +Y axis (rotated outward by
        // rotationDeg). Per-spike rotation does the radial flare.
        // displaySize.x = base radius, displaySize.y = spike length.
        const baseR  = hp.displaySize[0]
        const height = hp.displaySize[1]
        const len    = Math.hypot(baseR, height) || 1
        prims.push({
          type: 12, paletteSlot: slot, boneIdx: j,
          params: [baseR / len, height / len, height, 0],
          offsetInBone: [0, height, 0],
          // Own blend group, no smin — each spike stays distinctly pointy.
          blendGroup: 18, blendRadius: 0,
        })
      } else if (/^HairStrand(L|R)0$/.test(name)) {
        // Side strands (face-framing bangs) — type-23 ribbon-chain. Own
        // blend group (17) so the bangs layer ADDITIVELY over the bob
        // shell + ponytail rather than smin'ing into them. params.w =
        // tipScale (0.3 = bangs taper to 30% width at the tip). Other
        // ribbon callers pass 0 → no taper.
        const sideKey = /HairStrandL/.test(name) ? 'L' : 'R'
        const halfW     = hp.displaySize[0]
        const halfThick = hp.displaySize[2]
        const sideIndices: number[] = [j]
        for (let k = 1; k < 4; k++) {
          const idx = rig.findIndex((joint) => joint.name === `HairStrand${sideKey}${k}`)
          if (idx >= 0) sideIndices.push(idx)
        }
        if (sideIndices.length < 2) continue
        prims.push({
          type: 23, paletteSlot: slot, boneIdx: j,
          params: [sideIndices.length, halfW, halfThick, 0.3],
          offsetInBone: [0, 0, 0],
          blendGroup: 17, blendRadius: 0,
        })
      } else if (/^HairStrand/.test(name)) {
        // Non-root strand segments contribute via the chain primitive
        // emitted at HairStrandL0/R0 — skip standalone primitive.
        continue
      } else {
        prims.push({
          type: 2, paletteSlot: slot, boneIdx: j,
          params: [hp.displaySize[0], hp.displaySize[1], hp.displaySize[2], 0.015],
          offsetInBone: [0, 0, 0],
        })
      }
      continue
    }

    // 4) Body parts — breasts as ellipsoids (natural shape), capes as
    // chained roundedBoxes in their own blend group, hip pads as plain
    // roundedBoxes.
    const bp = bodyByName.get(name)
    if (bp) {
      if (/Breast/.test(name)) {
        // Group 6 (torso) so the breast ellipsoid smin's with Spine2 +
        // shoulder spheres into ONE continuous chest surface — no seam
        // where breast meets ribcage. Same blend radius as the other
        // torso ellipsoids.
        prims.push({
          type: 3, paletteSlot: slot, boneIdx: j,
          params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0],
          offsetInBone: [0, 0, 0],
          blendGroup: 6, blendRadius: 0.05,
        })
      } else if (/^Cape/.test(name)) {
        // Boxy lizard tail — type-23 ribbon-chain primitive. SDF is now
        // a proper 3D box per segment (not infinite tube) so endpoints
        // cap correctly and adjacent segments fuse at vertices instead
        // of exploding outward along their tangents.
        if (name !== 'Cape0') continue
        const slotB = (material.namedSlots.accent ?? 11)
        const halfW     = bp.displaySize[0]
        const halfThick = bp.displaySize[2]
        const capeIndices: number[] = [j]
        for (let k = 1; k < 6; k++) {
          const idx = rig.findIndex((joint) => joint.name === `Cape${k}`)
          if (idx >= 0) capeIndices.push(idx)
        }
        if (capeIndices.length < 2) continue
        const chainCount = capeIndices.length
        const b1 = capeIndices[1] ?? 0
        const b2 = capeIndices[2] ?? capeIndices[capeIndices.length - 1]
        const b3 = capeIndices[3] ?? capeIndices[capeIndices.length - 1]
        const b4 = capeIndices[4] ?? capeIndices[capeIndices.length - 1]
        const b5 = capeIndices[5] ?? capeIndices[capeIndices.length - 1]
        prims.push({
          type: 23, paletteSlot: slot, boneIdx: j,
          params: [chainCount, halfW, halfThick, b1],
          rotation: [b2, b3, b4, b5],
          offsetInBone: [0, 0, 0],
          blendGroup: 9, blendRadius: 0,
          colorFunc: 8,
          paletteSlotB: slotB,
          colorExtent: 5,
        })
      } else if (name === 'NoseBridge') {
        // Anchor bone — emits no geometry. The NOSE_LIBRARY entries
        // attach prims here via the same path as HAND_LIBRARY /
        // FOOT_LIBRARY (passed as `attachments` to chibiRaymarchPrimitives).
      } else if (/^Grenade/.test(name)) {
        // Grenade — ellipsoid primitive so the same emission path covers
        // round (uniform halfX/Y/Z) AND can-shaped (elongated halfY)
        // grenades. displaySize[0..2] are the three half-extents. No
        // blend group: each grenade is a discrete prop.
        prims.push({
          type: 3, paletteSlot: slot, boneIdx: j,
          params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0],
          offsetInBone: [0, 0, 0],
        })
      } else if (/^WP_/.test(name)) {
        // Wardrobe armor piece. Helmet/gauntlet/pauldron get ellipsoid
        // (rounded silhouette); belt + plates use roundedBox. Blend
        // group 11 — armor pieces fuse with adjacent armor (chest+
        // pauldron seam) but cross-group min vs body keeps the armor
        // distinct from skin underneath.
        const isRound = bp.shape !== undefined
          ? bp.shape === 'round'
          : /(Helmet|Pauldron|Gauntlet|Hood|Cap)/.test(name)
        if (isRound) {
          prims.push({
            type: 3, paletteSlot: slot, boneIdx: j,
            params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0],
            offsetInBone: bp.offset,
            blendGroup: 11, blendRadius: 0.025,
          })
        } else {
          prims.push({
            type: 2, paletteSlot: slot, boneIdx: j,
            params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0.012],
            offsetInBone: bp.offset,
            blendGroup: 11, blendRadius: 0.025,
          })
        }
      } else {
        // Generic body-part fallback — e.g., HipPads. Lands in torso
        // group 6 so it merges into the body surface (Hips ellipsoid)
        // rather than appearing as a stuck-on cube.
        prims.push({
          type: 2, paletteSlot: slot, boneIdx: j,
          params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0.02],
          offsetInBone: [0, 0, 0],
          blendGroup: 6, blendRadius: 0.05,
        })
      }
      continue
    }

    // 5) Accessories — rounded boxes by default (weapon rod, etc.).
    const acc = accByName.get(name)
    if (acc) {
      prims.push({
        type: 2, paletteSlot: slot, boneIdx: j,
        params: [acc.displaySize[0], acc.displaySize[1], acc.displaySize[2], acc.displaySize[0] * 0.3],
        offsetInBone: [0, 0, 0],
      })
      continue
    }

    // 5.5) Shoulder joints — small spheres filling the gap between torso
    // and arm chain start. Now part of the torso "potato sack" (group 6)
    // instead of the arm chain: the shoulders fuse into the body mass,
    // the arm then emerges from the fused surface. This is the key to
    // the sack silhouette — shoulders read as body volume, not as arm
    // sockets. Arm's upper capsule still overlaps the shoulder sphere,
    // so the arm-to-body join remains connected (hard min at the seam).
    if (name === 'LeftShoulder' || name === 'RightShoulder') {
      // Shoulder ball is the bridge between Spine2 and the upper-arm
      // capsule. Arm and torso live in different blend groups (limb
      // swappability), so the only thing that can smin into Spine2
      // is THIS sphere — it has to reach far enough out that the arm
      // capsule's hard-min seam lands inside it visually. 7.5cm radius
      // covers the gap from LeftShoulder joint to LeftArm joint.
      prims.push({
        type: 0, paletteSlot: slot, boneIdx: j,
        params: [0.075, 0, 0, 0],
        offsetInBone: [0, 0, 0],
        blendGroup: 6,
        blendRadius: 0.050,
      })
      continue
    }

    // 5.6) Hands — sphere at the Hand joint, treated as an ATTACHMENT
    // (hard-min into scene, not part of the arm blend chain). This keeps
    // arm-flex bends clean (forearm bezier doesn't smear into the hand
    // when the arm crosses the torso) and lets the hand be swapped out
    // freely (skin/mitt/fist/claw/robot/etc.) the same way feet and
    // helmets work.
    if (name === 'LeftHand' || name === 'RightHand') {
      prims.push({
        type: 0, paletteSlot: CHIBI_SLOTS.skin, boneIdx: j,
        params: [0.045, 0, 0, 0],     // 4.5cm sphere — the fist
        offsetInBone: [0, 0, 0],
        blendGroup: 0,    // 0 = standalone, hard-min into scene
        blendRadius: 0,
      })
      continue
    }

    // 6) Limbs — Bezier-profile capsules per chain ROOT (LeftArm,
    // RightArm, LeftUpLeg, RightUpLeg). One curve per limb, three
    // joints define the shape:
    //   A = chain root   (this bone:    Arm or UpLeg)
    //   B = bend control (first child:  ForeArm or Leg = elbow / knee)
    //   C = end          (grandchild:   Hand or Foot = wrist / ankle)
    // Mid bones (ForeArm, Leg) skip emission — they're folded into the
    // parent's Bezier. End bones (Hand) skip naturally (no children),
    // foot keeps its wedge-roundedBox special case.
    //
    // Profile control points r0..r3 (cubic Bezier of radii along the
    // curve) live in the rotation slot. CONSTANT radius today —
    // anatomy library lands next tick once the curve is verified.
    const thickness = CHIBI_LIMB_THICKNESS[name]
    if (!thickness) continue

    // First child bone index (= jointB for the bezier).
    let jointBIdx = -1
    for (let k = 0; k < rig.length; k++) {
      if (rig[k].parent !== j) continue
      const o = rig[k].offset
      const lo = Math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
      if (lo > 1e-6) { jointBIdx = k; break }
    }
    if (jointBIdx < 0) continue   // end bone — no segment

    // Mid-chain bones (ForeArm, Leg) are part of their parent's bezier.
    // Skip emission here so we don't double-render.
    const isChainMid = /^(LeftForeArm|RightForeArm|LeftLeg|RightLeg)$/.test(name)
    if (isChainMid) continue

    // Foot — emission moved to attachments.ts (DEFAULT_FEET). The
    // foot bone here in the limb loop is a chain end, no children, so
    // it would be skipped naturally by the jointBIdx < 0 check below.
    if (name === 'LeftFoot' || name === 'RightFoot') continue

    // Chain root (Arm / UpLeg) — emit a bezier covering A→B→C.
    const isChainRoot = /^(LeftArm|RightArm|LeftUpLeg|RightUpLeg)$/.test(name)
    if (!isChainRoot) continue

    let jointCIdx = -1
    for (let k = 0; k < rig.length; k++) {
      if (rig[k].parent !== jointBIdx) continue
      const o = rig[k].offset
      const lo = Math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
      if (lo > 1e-6) { jointCIdx = k; break }
    }
    if (jointCIdx < 0) continue

    const radius = (thickness[0] + thickness[1]) * 0.5
    // Per-bone segments. Arms = type-15 round (no anatomy asymmetry
    // needed for biceps; future). Legs = type-18 directional-Z so the
    // upper segment can express glute mass on -Z (back) and a thicker
    // X for hipFlare. Lower segment = symmetric.
    const isArm = name === 'LeftArm' || name === 'RightArm'
    const isLeg = name === 'LeftUpLeg' || name === 'RightUpLeg'
    const groupId = CHIBI_LIMB_BLEND_GROUP[name] ?? 0
    // Blend radius dissolves the elbow/knee crease where the upper and
    // lower segments bend. Sized to ~60-70% of the SMALLER segment
    // radius at the joint so smin produces a tight fillet, not a
    // swelling meniscus. Earlier 0.085 across the board inflated arm
    // joints (1.8× arm radius → visible bulge); per-limb tuning lets
    // legs keep more rounding (knees) while arms stay slim.
    //   arm forearm radius ≈ 0.046 → 0.030 fillet
    //   leg shin radius   ≈ 0.060 → 0.040 fillet
    const blendR = groupId ? (isArm ? 0.030 : 0.040) : 0
    const decalSlotB = isArm ? CHIBI_SLOTS.shirt : (isLeg ? CHIBI_SLOTS.pants : CHIBI_SLOTS.bg)
    const decalCutoff = isArm ? 1.0 : (isLeg ? 1.0 : 0.0)
    const useDecal = isArm || isLeg
    const baseSlot = useDecal ? CHIBI_SLOTS.skin : slot
    const decalExtras = useDecal ? {
      colorFunc: 30 as const,
      paletteSlotB: decalSlotB,
      colorExtent: decalCutoff,
    } : {}
    const elbowOff = rig[jointBIdx].offset
    const wristOff = rig[jointCIdx].offset
    const upperLen = Math.hypot(elbowOff[0], elbowOff[1], elbowOff[2])
    const lowerLen = Math.hypot(wristOff[0], wristOff[1], wristOff[2])

    // Round-only (type 15) for both arms and legs. Directional-Z (type
    // 18) was unstable under animation — bone-local Z orientation
    // doesn't ride with the bone correctly when chained segments bend
    // sharply. Round capsules are rotation-invariant and bend cleanly.
    //
    // Lower-leg foot-end (segLowerR1 for legs) tapers to a near-point
    // (0.015) instead of the wrist-equivalent ~0.055. The forearm tip
    // is hidden under the DEFAULT_HANDS sphere (5.5cm) at the wrist;
    // the leg has no equivalent occluder at the ankle, so a 5.5cm ball
    // poked out above the small DEFAULT_FEET wedge ("a wedge AND a
    // foot ball" report). Tapering to 1.5cm lets the shoe wedge sit
    // at the foot bone with no visible ankle ball.
    const segUpperR0 = isArm ? 0.062 : 0.085
    const segUpperR1 = isArm ? 0.046 : 0.060
    const segLowerR0 = isArm ? 0.046 : 0.060
    const segLowerR1 = isArm ? 0.040 : 0.015
    prims.push({
      type: 15, paletteSlot: baseSlot, boneIdx: j,
      params: [segUpperR0, segUpperR1, jointBIdx, upperLen],
      offsetInBone: [0, 0, 0],
      blendGroup: groupId, blendRadius: blendR,
      ...decalExtras,
    })
    prims.push({
      type: 15, paletteSlot: baseSlot, boneIdx: jointBIdx,
      params: [segLowerR0, segLowerR1, jointCIdx, lowerLen],
      offsetInBone: [0, 0, 0],
      blendGroup: groupId, blendRadius: blendR,
      ...decalExtras,
    })
    void radius
  }
  // 6b) Attachments — hand / foot meshes that plug into the limb's
  // terminal joint. Default = skin spheres on wrists; replaceable
  // (gauntlets, cartoon mitts, claws) via wardrobe equips on later
  // ticks. Each AttachmentPart is a (name, joint, prim) triple — same
  // shape as a single wardrobe piece but specifically for terminal
  // limb slots.
  for (const att of attachments) {
    const aIdx = rig.findIndex((j) => j.name === att.jointName)
    if (aIdx < 0) {
      console.warn(`attachment ${att.name}: joint "${att.jointName}" not found in rig; skipping`)
      continue
    }
    const slotKey = att.paletteSlot ?? 'skin'
    const slotIdx = material.namedSlots[slotKey] ?? material.paletteIndices[aIdx]
    prims.push({
      type: att.type,
      paletteSlot: slotIdx,
      boneIdx: aIdx,
      params: [att.params[0], att.params[1], att.params[2], att.params[3]],
      offsetInBone: [att.offsetInBone[0], att.offsetInBone[1], att.offsetInBone[2]],
      ...(att.rotation ? { rotation: [...att.rotation] as [number, number, number, number] } : {}),
      blendGroup: att.blendGroup ?? 0,
      blendRadius: att.blendRadius ?? 0,
    })
  }

  // 7) Anatomy curves — type-17 bezier-profile capsules that smin onto
  // the matching limb / torso group, layering muscle / fat masses onto
  // the base body. Each entry resolves three joint NAMES to indices
  // and emits one primitive. Skin palette by default; spec lets a
  // character override per-curve.
  const skinSlot = material.namedSlots.skin ?? 2
  const slotForAnatomy: Record<string, number> = {
    skin:  skinSlot,
    shirt: material.namedSlots.shirt ?? 3,
    pants: material.namedSlots.pants ?? 4,
  }
  for (const a of anatomy) {
    const aIdx = rig.findIndex((j) => j.name === a.jointA)
    const bIdx = rig.findIndex((j) => j.name === a.jointB)
    const cIdx = rig.findIndex((j) => j.name === a.jointC)
    if (aIdx < 0 || bIdx < 0 || cIdx < 0) {
      console.warn(`anatomy ${a.name}: missing joint(s) ${a.jointA}/${a.jointB}/${a.jointC} — skipping`)
      continue
    }
    prims.push({
      type: 17,
      paletteSlot: slotForAnatomy[a.paletteSlot ?? 'skin'] ?? skinSlot,
      boneIdx: aIdx,
      params: [bIdx, cIdx, 0, 0],
      offsetInBone: a.offsetA ?? [0, 0, 0],
      blendGroup: a.blendGroup,
      blendRadius: a.blendRadius,
      rotation: [a.profile[0], a.profile[1], a.profile[2], a.profile[3]],
    })
  }

  // 8) Helmet — built from the new Tier-1 primitives:
  //   * SUP (type 18) for the crown — sphere-leaning blend with Y-clip
  //     below the brow line for the open-bottom helmet shape.
  //   * SUP (type 18) again for the brim ring (box-leaning, tight Y-clip)
  //     CHAMFER-blended onto the crown for sharp rim edge.
  //   * SUP horns with mirrorYZ — one entry produces L+R via expandMirrors.
  // All in blend group 14 (helmet armor) so smin'd into one continuous
  // surface. Palette: armor slot.
  if (helmStyle !== 'none') {
    const headIdx = rig.findIndex((j) => j.name === 'Head')
    if (headIdx >= 0) {
      const armorSlot = material.namedSlots.armor ?? 16
      const headOffsetY = 0.12   // matches CHIBI_CENTERED_OFFSET.Head
      const isGreathelm = helmStyle === 'greathelm'
      const isSallet    = helmStyle === 'sallet'
      if (isSallet) {
        // SALLET — showcase variant exercising all three Tier-1 prims:
        //   * SUP crown — box-leaning, slightly Y-elongated (sphere blend
        //     0.55, no clip) for the rounded-back-with-tail silhouette.
        //   * CHAMFER-subtract eye slit — wide horizontal cut at brow line.
        //   * mirrorYZ ear-flap — single SUP entry expanded to L+R covers
        //     the temple/cheek area.
        // Crown.
        prims.push({
          type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.21, 0.55, 0, 0.10],   // slight Y-clip on top for the back-tail look
          offsetInBone: [0, headOffsetY + 0.02, 0],
          blendGroup: 14, blendRadius: 0.025,
        })
        // Eye slit — chamfer-subtract a thin horizontal box across the
        // front. Narrower than greathelm's full visor; just enough to
        // see through.
        prims.push({
          type: 1, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.15, 0.010, 0.18, 0],
          offsetInBone: [0, headOffsetY + 0.06, 0.07],
          blendGroup: 14, blendRadius: -0.012,
          chamfer: true,
        })
        // Ear-flap — small SUP plate on the side of the head, mirrorYZ
        // produces the matching pair. blend=0.7 (box-leaning so it's
        // distinctly an armor plate, not a soft bulge).
        prims.push({
          type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.05, 0.70, 0, 0],
          offsetInBone: [0.14, headOffsetY - 0.03, 0.02],
          blendGroup: 14, blendRadius: 0.02,
          chamfer: true,
          mirrorYZ: true,
        })
      } else if (isGreathelm) {
        // GREATHELM — full-face box-leaning crown (no Y-clip), then
        // CHAMFER-subtract a thin horizontal box for the visor slit.
        // Demonstrates cdiff_k (chamfer-subtract): negative blendRadius
        // + chamfer:true routes to the bevel-edge subtract path in the
        // group blender. Result: sharp-edged slot cut clean across the
        // front of the helmet, no soft fillet.
        prims.push({
          type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.20, 0.75, 0, 0],   // box-leaning, no Y-clip
          offsetInBone: [0, headOffsetY, 0],
          blendGroup: 14, blendRadius: 0.025,
        })
        // Visor slit — type 1 box, chamfer-subtracted from the crown.
        // Wide X (ear-to-ear), thin Y (slot height ~2 cm), deep Z so the
        // box penetrates fully. Offset Z forward so the slit appears at
        // the FRONT face of the helm, not centered on the head joint.
        prims.push({
          type: 1, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.16, 0.012, 0.18, 0],
          offsetInBone: [0, headOffsetY + 0.04, 0.07],
          blendGroup: 14, blendRadius: -0.015,
          chamfer: true,
        })
      } else {
        // Crown — SUP dome. blend=0.15 (mostly sphere, slight box for
        // structured silhouette), shell=0 (solid), yClipN = +0.15 r so
        // the top is rounded but the lower half is open under the brim.
        prims.push({
          type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.21, 0.15, 0, -0.15],
          offsetInBone: [0, headOffsetY + 0.04, 0],
          blendGroup: 14, blendRadius: 0.02,
        })
        // Brim — SUP flat ring. blend=0.85 (mostly box / squared),
        // smaller radius, big chamfered fuse with crown for the rim ridge.
        prims.push({
          type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
          params: [0.23, 0.85, 0, 0],
          offsetInBone: [0, headOffsetY - 0.06, 0],
          blendGroup: 14, blendRadius: 0.03,
          chamfer: true,
        })
        // Horned variant — pair of horns mirrored across YZ.
        if (helmStyle === 'horned') {
          prims.push({
            type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
            params: [0.04, 0.30, 0, 0],
            offsetInBone: [0.13, headOffsetY + 0.18, 0.02],
            blendGroup: 14, blendRadius: 0.015,
            mirrorYZ: true,
          })
        }
        // Plumed variant — kettle base + a fan of 3 SUP "feathers"
        // sweeping backward and outward from the crown's top-rear. Each
        // feather is a narrow elongated SUP plate. mirrorYZ on each
        // doubles them to a 6-feather array (one entry → L+R pair via
        // expandMirrors). The center feather (X=0) doesn't mirror.
        // Demonstrates SUP authoring with multiple per-character pieces
        // and reuse of mirrorYZ for radial-symmetric decorations.
        if (helmStyle === 'plumed') {
          // Side feathers — three pairs swept back at increasing angles.
          const feathers: { x: number; y: number; z: number }[] = [
            { x: 0.04, y: headOffsetY + 0.20, z: -0.06 },   // near-center
            { x: 0.07, y: headOffsetY + 0.16, z: -0.10 },   // mid
            { x: 0.09, y: headOffsetY + 0.10, z: -0.14 },   // outer (lower, further back)
          ]
          for (const f of feathers) {
            prims.push({
              type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
              params: [0.025, 0.20, 0, 0],   // narrow long SUP, sphere-leaning
              offsetInBone: [f.x, f.y, f.z],
              blendGroup: 14, blendRadius: 0.02,
              chamfer: true,
              mirrorYZ: true,
            })
          }
        }
        // Crested variant — Greek/Roman style ridge along the centerline
        // of the crown. Uses TYPE 19 (exact ellipsoid) rather than type 3
        // because the crest is highly anisotropic (very narrow X, tall Y,
        // medium Z) — the inexact bound on type 3 over-estimates distance
        // for such elongated shapes, causing the marcher to over-step
        // and miss the surface at extreme angles. Exact solve via
        // quadratic_roots fixes that.
        if (helmStyle === 'crested') {
          prims.push({
            type: 19, paletteSlot: armorSlot, boneIdx: headIdx,
            params: [0.018, 0.085, 0.13, 0],   // anisotropic: thin X, tall Y, medium Z
            offsetInBone: [0, headOffsetY + 0.18, 0],
            blendGroup: 14, blendRadius: 0.02,
            chamfer: true,
          })
        }
        // Pickelhaube variant — spiked top, no horns. SUP with deep
        // negative Y-clip (elongated upward) + tight radius gives a clean
        // cone-style spike that smin's into the crown for the Prussian-
        // helm silhouette. Single primitive, no mirror needed.
        if (helmStyle === 'pickelhaube') {
          prims.push({
            type: 18, paletteSlot: armorSlot, boneIdx: headIdx,
            params: [0.045, 0.10, 0, -0.30],
            offsetInBone: [0, headOffsetY + 0.20, 0],
            blendGroup: 14, blendRadius: 0.025,
            chamfer: true,
          })
        }
      }
    }
  }

  // Shininess sweep is disabled — full roughness on every body surface
  // until we revisit the spec / highlight authoring story. The per-prim
  // shiny flag, raymarch packing, and outline highlight band all
  // remain in place; turning a character (or a specific primitive) shiny
  // is a one-line p.shiny = true away when needed.
  return prims
}

/** Each limb chain smooth-unions into one primitive group so joints
 *  read as continuous flesh, not three pipes taped together.
 *  Group 1 is reserved for Head+Jaw (see CENTERED_SIZE branch).
 *  Shoulder joins the arm chain so the arm smoothly meets a ball at
 *  the shoulder, closing the gap between torso box and arm start. */
const CHIBI_LIMB_BLEND_GROUP: Record<string, number> = {
  // Hands and feet are ATTACHMENTS (blendGroup=0, hard-min) — swappable
  // independent of the arm/leg primitive. Shoulders are reassigned to
  // the torso group inside the centered-bone emission path so they fuse
  // into the body mass rather than starting the arm chain.
  LeftArm: 2,  LeftForeArm: 2,
  RightArm: 3, RightForeArm: 3,
  LeftUpLeg: 4,  LeftLeg: 4,
  RightUpLeg: 5, RightLeg: 5,
}

/** Chibi character display: only a handful of Mixamo bones render as chunky
 *  body parts; the rest collapse to zero-size (invisible). Head/torso/hips
 *  are centered cubes on their joints; limbs orient along their bone
 *  direction toward the first child. Gives the classic chibi silhouette:
 *  giant head, short cube body, stubby limbs.
 *
 *  All half-extents in meters. Sizing chosen to read clearly at SNES scale
 *  (256×224 internal) with an orthoSize ~1.3.
 */
export function chibiBoneDisplayMats(
  rig: Joint[],
  face: FaceFeature[] = DEFAULT_FACE,
  accessories: Accessory[] = DEFAULT_ACCESSORIES,
  hair: HairPart[] = DEFAULT_HAIR,
  bodyParts: BodyPart[] = DEFAULT_BODY_PARTS,
): Float32Array {
  // name → [halfX, halfZ]. halfY is the actual bone length so cubes reach
  // their child joint (no gap between upper arm and forearm).
  // For CENTERED parts (head/torso/hips), all three half-extents are explicit.
  const LIMB_THICKNESS: Record<string, [number, number]> = {
    LeftArm:      [0.055, 0.055],
    LeftForeArm:  [0.05,  0.05 ],
    RightArm:     [0.055, 0.055],
    RightForeArm: [0.05,  0.05 ],
    LeftUpLeg:    [0.075, 0.075],
    LeftLeg:      [0.065, 0.065],
    LeftFoot:     [0.065, 0.09],
    RightUpLeg:   [0.075, 0.075],
    RightLeg:     [0.065, 0.065],
    RightFoot:    [0.065, 0.09],
  }
  const CENTERED_SIZE: Record<string, [number, number, number]> = {
    Head:    [0.19, 0.21, 0.19],    // GIANT head
    Neck:    [0.022, 0.06, 0.022],  // small pillar so the head doesn't merge with the torso
    Spine1:  [0.17, 0.15, 0.12],    // torso
    Hips:    [0.15, 0.07, 0.12],    // hips
  }
  // Per-centered-part local-space offset from the joint origin. Without
  // this the Head cube (half-extent Y 0.21) extends down to the shoulder
  // line — head reads as having no neck. Lifting it by +0.12 along the
  // Head joint's local Y clears the shoulder region and makes room for
  // the Neck cube defined above.
  const CENTERED_OFFSET: Record<string, [number, number, number]> = {
    Head: [0, 0.12, 0],
  }
  // Face features: centered cubes with the sizes specified in the face
  // feature config. Pulled in here (rather than a hard-coded map) so
  // adding a new face feature only requires editing DEFAULT_FACE.
  for (const f of face) CENTERED_SIZE[f.name] = [...f.displaySize]
  // Accessories: same pattern. The accessory's own rotation is already
  // baked into its local matrix via extendLocalMatsWithAccessories, so
  // here we only need the cube half-extents.
  for (const a of accessories) CENTERED_SIZE[a.name] = [...a.displaySize]
  for (const h of hair) CENTERED_SIZE[h.name] = [...h.displaySize]
  for (const b of bodyParts) CENTERED_SIZE[b.name] = [...b.displaySize]

  const out = new Float32Array(rig.length * 16)

  for (let j = 0; j < rig.length; j++) {
    const base = j * 16
    const name = rig[j].name

    // Centered body parts (head/torso/hips): identity-rotated cube, with
    // optional local-space translation so e.g. the Head cube can sit
    // above the neck line instead of sunk into the shoulders.
    const centered = CENTERED_SIZE[name]
    if (centered) {
      const [hx, hy, hz] = centered
      const off = CENTERED_OFFSET[name] ?? [0, 0, 0]
      out[base + 0]  = hx
      out[base + 5]  = hy
      out[base + 10] = hz
      out[base + 12] = off[0]
      out[base + 13] = off[1]
      out[base + 14] = off[2]
      out[base + 15] = 1
      continue
    }

    // Oriented limb: Y axis along bone direction, Y length = actual bone length.
    const thickness = LIMB_THICKNESS[name]
    if (!thickness) continue   // invisible bone (all zeros)

    const [hx, hz] = thickness

    // Find first child to determine bone direction + length.
    let dir: [number, number, number] = [0, 1, 0]
    let length = 0
    for (let k = 0; k < rig.length; k++) {
      if (rig[k].parent !== j) continue
      const o = rig[k].offset
      const lo = Math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
      if (lo > 1e-6) {
        dir = [o[0] / lo, o[1] / lo, o[2] / lo]
        length = lo
        break
      }
    }
    if (length < 1e-6) continue   // leaf with no measurable bone; skip
    const hy = length / 2

    // Orthonormal frame with Y = dir.
    const px: [number, number, number] = Math.abs(dir[0]) < 0.9 ? [1, 0, 0] : [0, 0, 1]
    let zx = dir[1] * px[2] - dir[2] * px[1]
    let zy = dir[2] * px[0] - dir[0] * px[2]
    let zz = dir[0] * px[1] - dir[1] * px[0]
    const zLen = Math.sqrt(zx * zx + zy * zy + zz * zz)
    zx /= zLen; zy /= zLen; zz /= zLen
    const xx = dir[1] * zz - dir[2] * zy
    const xy = dir[2] * zx - dir[0] * zz
    const xz = dir[0] * zy - dir[1] * zx

    out[base + 0]  = xx * hx
    out[base + 1]  = xy * hx
    out[base + 2]  = xz * hx
    out[base + 4]  = dir[0] * hy
    out[base + 5]  = dir[1] * hy
    out[base + 6]  = dir[2] * hy
    out[base + 8]  = zx * hz
    out[base + 9]  = zy * hz
    out[base + 10] = zz * hz
    out[base + 12] = dir[0] * hy
    out[base + 13] = dir[1] * hy
    out[base + 14] = dir[2] * hy
    out[base + 15] = 1
  }
  return out
}
