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
}

/** Default chibi material: 6-slot palette, each visible body part bound
 *  to a semantic slot. Color swatches live entirely in `palette` — change
 *  palette[slot] and every bone using that slot recolors instantly. */
export function chibiMaterial(rig: Joint[]): SpriteMaterial {
  const PART_TO_SLOT: Record<string, number> = {
    Head:         CHIBI_SLOTS.skin,   // head reads as skin (face); hair layers later
    Spine1:       CHIBI_SLOTS.shirt,
    Hips:         CHIBI_SLOTS.pants,
    LeftArm:      CHIBI_SLOTS.skin,
    LeftForeArm:  CHIBI_SLOTS.skin,
    RightArm:     CHIBI_SLOTS.skin,
    RightForeArm: CHIBI_SLOTS.skin,
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
    if (/^Weapon/i.test(name) || /Sword|Shield|Staff|Bow|Gun/.test(name)) return CHIBI_SLOTS.weapon
    if (/^Accent/i.test(name) || /Pauldron|Belt|Strap/.test(name)) return CHIBI_SLOTS.accent
    return undefined
  }

  const paletteIndices = new Uint32Array(rig.length)
  for (let j = 0; j < rig.length; j++) {
    const name = rig[j].name
    paletteIndices[j] = PART_TO_SLOT[name] ?? accessorySlot(name) ?? CHIBI_SLOTS.bg
  }

  const palette = new Float32Array(16 * 4)
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

  return { paletteIndices, palette, namedSlots: { ...CHIBI_SLOTS } }
}

/** Procedural per-joint palette (rainbow) for non-chibi rigs. Preserves
 *  the old "each joint a different color" look using the LUT system. */
export function defaultRainbowMaterial(numJoints: number): SpriteMaterial {
  const paletteIndices = new Uint32Array(numJoints)
  for (let j = 0; j < numJoints; j++) paletteIndices[j] = j % 16
  const palette = new Float32Array(16 * 4)
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
}

export const DEFAULT_BODY_PARTS: BodyPart[] = [
  { name: 'LeftBreast',  parentName: 'Spine2', offset: [ 0.045, 0.035, 0.10], displaySize: [0.050, 0.045, 0.055] },
  { name: 'RightBreast', parentName: 'Spine2', offset: [-0.045, 0.035, 0.10], displaySize: [0.050, 0.045, 0.055] },
  { name: 'LeftHipPad',  parentName: 'Hips',   offset: [ 0.095, 0.010, 0.00], displaySize: [0.040, 0.055, 0.070] },
  { name: 'RightHipPad', parentName: 'Hips',   offset: [-0.095, 0.010, 0.00], displaySize: [0.040, 0.055, 0.070] },
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

export const DEFAULT_HAIR: HairPart[] = [
  // Broad dome sitting on top of the head cube. Head cube spans y ±0.21
  // and z ±0.19 centered on the Head joint, so hair sits at y=+0.18 to
  // read as "crown" without floating.
  { name: 'HairTop',       parentName: 'Head', offset: [0, 0.18, -0.02], displaySize: [0.17, 0.08, 0.16] },
  // Flat back-of-head hair — thin slab hugging the back of the skull.
  { name: 'HairBack',      parentName: 'Head', offset: [0, 0.02, -0.19], displaySize: [0.16, 0.17, 0.04] },
  // Side bangs extending the silhouette beyond the head cube's X extent.
  { name: 'HairLeftSide',  parentName: 'Head', offset: [ 0.17, 0.05, 0.02], displaySize: [0.04, 0.11, 0.11] },
  { name: 'HairRightSide', parentName: 'Head', offset: [-0.17, 0.05, 0.02], displaySize: [0.04, 0.11, 0.11] },
  // Front fringe above the eyes — narrow slab just in front of the
  // forehead. Thin Z so the eye whites (z=+0.195) sit slightly in front.
  { name: 'HairFringe',    parentName: 'Head', offset: [0, 0.13, 0.185],  displaySize: [0.14, 0.05, 0.01] },
]

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

export const DEFAULT_FACE: FaceFeature[] = [
  { name: 'LeftEye',    parentName: 'Head',     offset: [ 0.055, 0.035, 0.195], displaySize: [0.028, 0.022, 0.008] },
  { name: 'RightEye',   parentName: 'Head',     offset: [-0.055, 0.035, 0.195], displaySize: [0.028, 0.022, 0.008] },
  // Pupils parented to eyes so eye scale + eye-direction changes bring
  // pupils along for free. Offsets are in the eye's local frame (just a
  // small +Z pushes the pupil onto the eye's front surface).
  { name: 'LeftPupil',  parentName: 'LeftEye',  offset: [0, 0, 0.006], displaySize: [0.012, 0.014, 0.004] },
  { name: 'RightPupil', parentName: 'RightEye', offset: [0, 0, 0.006], displaySize: [0.012, 0.014, 0.004] },
  { name: 'Mouth',      parentName: 'Head',     offset: [0,    -0.065, 0.195], displaySize: [0.030, 0.012, 0.008] },
  { name: 'Nose',       parentName: 'Head',     offset: [0,    -0.015, 0.205], displaySize: [0.013, 0.020, 0.018] },
]

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
  Head:    [0.19, 0.21, 0.19],
  Neck:    [0.045, 0.06, 0.045],
  Spine1:  [0.17, 0.15, 0.12],
  Hips:    [0.15, 0.07, 0.12],
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
}

export function chibiRaymarchPrimitives(
  rig: Joint[],
  material: SpriteMaterial,
  face: FaceFeature[] = DEFAULT_FACE,
  accessories: Accessory[] = DEFAULT_ACCESSORIES,
  hair: HairPart[] = DEFAULT_HAIR,
  bodyParts: BodyPart[] = DEFAULT_BODY_PARTS,
): RaymarchPrimDesc[] {
  const prims: RaymarchPrimDesc[] = []
  const faceByName = new Map(face.map((f) => [f.name, f]))
  const accByName = new Map(accessories.map((a) => [a.name, a]))
  const hairByName = new Map(hair.map((h) => [h.name, h]))
  const bodyByName = new Map(bodyParts.map((b) => [b.name, b]))

  for (let j = 0; j < rig.length; j++) {
    const name = rig[j].name
    const slot = material.paletteIndices[j]

    // 1) Core centered body parts — head is an ellipsoid, others are boxes.
    const core = CHIBI_CENTERED_SIZE[name]
    if (core) {
      const off = CHIBI_CENTERED_OFFSET[name] ?? [0, 0, 0]
      const type = name === 'Head' ? 3 : 1   // 3=ellipsoid, 1=box
      // Head gets a blend group so the jaw/chin ellipsoid (below) melds into
      // it as a single skin surface rather than showing a crease at the seam.
      // 0.03m blend radius → soft under-chin transition, hard enough that
      // the overall silhouette still reads as the chibi round head.
      const headBlend = name === 'Head' ? { blendGroup: 1, blendRadius: 0.03 } : {}
      prims.push({
        type, paletteSlot: slot, boneIdx: j,
        params: [core[0], core[1], core[2], 0],
        offsetInBone: [off[0], off[1], off[2]],
        ...headBlend,
      })
      // Add the jaw/chin ellipsoid — a smaller ellipsoid offset down and
      // forward. Smooth-unions with the head ellipsoid via blend group 1
      // to give a subtle jawline without a crease. Pure RENDERING addition
      // (no rig change); turn off by removing this block.
      if (name === 'Head') {
        prims.push({
          type: 3, paletteSlot: slot, boneIdx: j,
          params: [core[0] * 0.80, core[1] * 0.55, core[2] * 0.90, 0],
          offsetInBone: [off[0], off[1] - core[1] * 0.55, off[2] + core[2] * 0.12],
          blendGroup: 1, blendRadius: 0.03,
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

    // 3) Hair — rounded boxes (soft edges read better than boxes for hair).
    const hp = hairByName.get(name)
    if (hp) {
      prims.push({
        type: 2, paletteSlot: slot, boneIdx: j,
        params: [hp.displaySize[0], hp.displaySize[1], hp.displaySize[2], 0.015],
        offsetInBone: [0, 0, 0],
      })
      continue
    }

    // 4) Body parts — breasts as ellipsoids (natural shape), hip pads as boxes.
    const bp = bodyByName.get(name)
    if (bp) {
      if (/Breast/.test(name)) {
        prims.push({
          type: 3, paletteSlot: slot, boneIdx: j,
          params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0],
          offsetInBone: [0, 0, 0],
        })
      } else {
        prims.push({
          type: 2, paletteSlot: slot, boneIdx: j,
          params: [bp.displaySize[0], bp.displaySize[1], bp.displaySize[2], 0.02],
          offsetInBone: [0, 0, 0],
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

    // 6) Limbs — capsule along bone +Y. Mixamo bones orient child at +Y in
    // parent-local frame so no primitive rotation is needed.
    const thickness = CHIBI_LIMB_THICKNESS[name]
    if (!thickness) continue

    let length = 0
    for (let k = 0; k < rig.length; k++) {
      if (rig[k].parent !== j) continue
      const o = rig[k].offset
      const lo = Math.sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2])
      if (lo > 1e-6) { length = lo; break }
    }
    if (length < 1e-6) continue

    const halfLen = length / 2
    // Capsule radius = average of the two thickness axes (they're symmetric
    // for arms/legs anyway). Center along bone by offsetting +Y halfLen.
    const radius = (thickness[0] + thickness[1]) * 0.5
    // halfLength param is the STRAIGHT section (not including hemisphere caps),
    // so subtract radius to hit the bone length exactly.
    prims.push({
      type: 5, paletteSlot: slot, boneIdx: j,
      params: [radius, Math.max(0.001, halfLen - radius), 0, 0],
      offsetInBone: [0, halfLen, 0],
    })
  }
  return prims
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
    Neck:    [0.045, 0.06, 0.045],  // small pillar so the head doesn't merge with the torso
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
