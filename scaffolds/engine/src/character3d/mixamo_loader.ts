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
  bg:    0,    // invisible / zero-size bones
  hair:  1,
  skin:  2,
  shirt: 3,
  pants: 4,
  shoes: 5,
}

/** Default chibi material: 6-slot palette, each visible body part bound
 *  to a semantic slot. Color swatches live entirely in `palette` — change
 *  palette[slot] and every bone using that slot recolors instantly. */
export function chibiMaterial(rig: Joint[]): SpriteMaterial {
  const PART_TO_SLOT: Record<string, number> = {
    Head:         CHIBI_SLOTS.hair,
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
  }

  const paletteIndices = new Uint32Array(rig.length)
  for (let j = 0; j < rig.length; j++) {
    paletteIndices[j] = PART_TO_SLOT[rig[j].name] ?? CHIBI_SLOTS.bg
  }

  const palette = new Float32Array(16 * 4)
  const setC = (slot: number, r: number, g: number, b: number) => {
    palette[slot * 4 + 0] = r
    palette[slot * 4 + 1] = g
    palette[slot * 4 + 2] = b
    palette[slot * 4 + 3] = 1
  }
  setC(CHIBI_SLOTS.bg,    0.0,  0.0,  0.0)
  setC(CHIBI_SLOTS.hair,  0.35, 0.2,  0.1 )    // dark brown hair
  setC(CHIBI_SLOTS.skin,  0.95, 0.75, 0.6 )    // peach skin
  setC(CHIBI_SLOTS.shirt, 0.75, 0.25, 0.25)    // red shirt
  setC(CHIBI_SLOTS.pants, 0.15, 0.2,  0.45)    // dark-blue pants
  setC(CHIBI_SLOTS.shoes, 0.35, 0.2,  0.12)    // brown shoes
  // Slots 6..15 available for extras (eyes, accent, gear, glow, etc.)

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

/** Chibi character display: only a handful of Mixamo bones render as chunky
 *  body parts; the rest collapse to zero-size (invisible). Head/torso/hips
 *  are centered cubes on their joints; limbs orient along their bone
 *  direction toward the first child. Gives the classic chibi silhouette:
 *  giant head, short cube body, stubby limbs.
 *
 *  All half-extents in meters. Sizing chosen to read clearly at SNES scale
 *  (256×224 internal) with an orthoSize ~1.3.
 */
export function chibiBoneDisplayMats(rig: Joint[]): Float32Array {
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
    Spine1:  [0.17, 0.15, 0.12],    // torso
    Hips:    [0.15, 0.07, 0.12],    // hips
  }

  const out = new Float32Array(rig.length * 16)

  for (let j = 0; j < rig.length; j++) {
    const base = j * 16
    const name = rig[j].name

    // Centered body parts (head/torso/hips): identity-rotated, centered on joint.
    const centered = CENTERED_SIZE[name]
    if (centered) {
      const [hx, hy, hz] = centered
      out[base + 0]  = hx
      out[base + 5]  = hy
      out[base + 10] = hz
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
