/**
 * Procedural creature rig — spec → bone hierarchy + raymarch primitives.
 *
 * Architecture per the design discussion: every creature is a central
 * segmented ribbon (the spine) with a head at one end and N mirrored
 * limb pairs along its length. Segment count drives the silhouette:
 *   0 segments  → bird (head + body capsule, no spine articulation)
 *   2 segments  → spider (head + 2-segment body = cephalothorax + abdomen)
 *   N segments  → snake / centipede
 *
 * Bone convention:
 *   - HeadAnchor is the rig root, at the FRONT of the creature (world Z+).
 *   - Body bones extend BACKWARD from HeadAnchor along its local -Y axis
 *     (Mixamo convention: bone +Y points to first child along the chain).
 *     We use -Y so HeadAnchor's first child sits behind the head.
 *     Wait — that breaks the "bone +Y is chain direction" rule. Use +Y
 *     and just place HeadAnchor with a bind-pose rotation that points
 *     its +Y backward in world space.
 *   - Limb anchors hang off each body bone with a sideways+downward
 *     bind-pose rotation. Each limb is its own chain with bones along
 *     its own +Y. Mirrored pairs share the same chain shape with
 *     X-flipped offset on the anchor.
 *
 * Output:
 *   - rig: Joint[] suitable for the existing skeleton.ts pipeline
 *   - worldMats: Float32Array (numJoints × 16, column-major) — single
 *     frame T-pose. Caller writes this to a GPUBuffer with numFrames=1.
 *   - prims: RaymarchPrimitive[] keyed by joint index.
 */

import type { Joint } from './skeleton'
import type { RaymarchPrimitive } from './raymarch_renderer'
import { mat4, type Vec3 } from '../math/vec'

// ============================================================================
// Spec
// ============================================================================

export interface CreatureSpec {
  /** Display name for debug + UI. */
  name: string
  body: BodySpec
  head: HeadSpec
  /** 0..N mirrored limb pairs along the body. attachT 0 = head end,
   *  1 = tail end. Each pair generates 2 limbs (L + R) with the same
   *  segments, X-flipped at the anchor. */
  limbPairs: LimbPairSpec[]
}

export interface BodySpec {
  /** Number of articulation joints in the spine BETWEEN head and tail.
   *  0 = single capsule (bird). N = N+1 capsules (snake/centipede). */
  segments: number
  /** Total length head-to-tail in meters. Distributed evenly across
   *  segments, so each capsule = totalLength / (segments + 1). */
  totalLength: number
  /** Cross-section radius in meters. Future: per-segment taper. */
  radius: number
  paletteSlot: number
}

export interface HeadSpec {
  /** Half-extents of the head ellipsoid in meters [x, y, z]. */
  size: [number, number, number]
  paletteSlot: number
}

export interface LimbPairSpec {
  /** 0 = at head end of body, 1 = at tail end. Snapped to the nearest
   *  body joint at rig-build time. */
  attachT: number
  /** Each entry is one capsule segment; chained head→tip. Empty array
   *  means no limb (skip the pair entirely). */
  segments: LimbSegmentSpec[]
  /** Sideways spread from body axis, radians. PI/2 = perpendicular,
   *  0 = parallel forward. */
  spreadAngle: number
  /** Vertical droop, radians. Positive = down. PI/2 = straight down. */
  downAngle: number
  paletteSlot: number
}

export interface LimbSegmentSpec {
  length: number
  radiusStart: number
  radiusEnd: number
}

// ============================================================================
// Build
// ============================================================================

export interface BuiltCreature {
  rig: Joint[]
  /** Single-frame world matrices in column-major layout. Length = rig.length × 16. */
  worldMats: Float32Array
  prims: RaymarchPrimitive[]
}

/** Builds the full bone hierarchy + bind-pose world matrices + raymarch
 *  primitives for a creature spec. Single-frame static rig — no
 *  animation yet. The caller uploads worldMats to a GPUBuffer with
 *  numFrames=1 and the existing raymarch renderer reads from it
 *  exactly the same way it reads VAT animations. */
export function buildCreature(spec: CreatureSpec): BuiltCreature {
  const rig: Joint[] = []
  const prims: RaymarchPrimitive[] = []

  // -------------------- Body chain --------------------
  // HeadAnchor at world origin. Body extends along world -Z (so the
  // creature faces +Z). HeadAnchor itself has no display geometry; it's
  // a logical attachment point for the head ellipsoid + the body chain.
  const segCount = Math.max(0, spec.body.segments)
  const segLen   = spec.body.totalLength / (segCount + 1)

  rig.push({ name: 'HeadAnchor', parent: -1, offset: [0, 0, 0] })
  const headAnchorIdx = rig.length - 1

  // Body bones BodySeg0..BodySegN, each offset by -segLen along world Z.
  // Bone +Y axis convention: each bone's +Y should point toward its
  // first child along the chain. HeadAnchor → BodySeg0 → BodySeg1 → ...
  // We achieve this by setting the bone offsets along -Z (world) AND
  // applying a preRotation that rotates local +Y to point along world -Z
  // for every body bone. World-mat construction below handles this.
  const bodyBoneIdxs: number[] = []
  for (let i = 0; i < segCount + 1; i++) {
    const parent = i === 0 ? headAnchorIdx : rig.length - 1
    rig.push({
      name: `BodySeg${i}`,
      parent,
      // Local offset is in PARENT'S local frame. Parent's +Y axis points
      // backward (world -Z) by our bind-pose convention, so an offset of
      // [0, segLen, 0] places this bone segLen behind the parent.
      offset: i === 0 ? [0, 0, 0] : [0, segLen, 0],
    })
    bodyBoneIdxs.push(rig.length - 1)
  }

  // -------------------- Head primitive --------------------
  // Ellipsoid at HeadAnchor, offset slightly forward (world +Z, which is
  // HeadAnchor's local -Y given our backward-pointing convention).
  prims.push({
    type: 3, // sdEllipsoid
    paletteSlot: spec.head.paletteSlot,
    boneIdx: headAnchorIdx,
    params: [spec.head.size[0], spec.head.size[1], spec.head.size[2], 0],
    offsetInBone: [0, -spec.head.size[1] * 0.6, 0],
  })

  // -------------------- Body capsules --------------------
  // One type-15 capsule per body segment, from BodySeg(i) to BodySeg(i+1).
  // Tail bone has no successor → no capsule (segCount+1 bones → segCount+0
  // capsules wait that's wrong). With segCount segments and segCount+1
  // bones, we have segCount capsules between bones plus one capsule from
  // HeadAnchor to BodySeg0. Actually let me recount:
  //   bird (segCount=0): 1 body bone, capsule HeadAnchor → BodySeg0
  //   spider (segCount=2): 3 body bones, capsules HeadAnchor→Seg0,
  //                        Seg0→Seg1, Seg1→Seg2 = 3 capsules
  //   snake (segCount=10): 11 body bones, 11 capsules
  // Per-capsule: type-15, boneA = parent (HeadAnchor or BodySeg(i-1)),
  // boneB = current body bone. params.x/y = radii, params.z = boneB index.
  const allBodyBones = [headAnchorIdx, ...bodyBoneIdxs]
  for (let i = 0; i + 1 < allBodyBones.length; i++) {
    const aIdx = allBodyBones[i]
    const bIdx = allBodyBones[i + 1]
    prims.push({
      type: 15,
      paletteSlot: spec.body.paletteSlot,
      boneIdx: aIdx,
      params: [spec.body.radius, spec.body.radius, bIdx, segLen],
      offsetInBone: [0, 0, 0],
    })
  }

  // -------------------- Limb pairs --------------------
  for (let p = 0; p < spec.limbPairs.length; p++) {
    const pair = spec.limbPairs[p]
    if (pair.segments.length === 0) continue
    // Snap attachT to nearest body bone. attachT=0 → first body bone
    // (BodySeg0, which is at HeadAnchor's position); attachT=1 → last.
    const tClamped = Math.max(0, Math.min(1, pair.attachT))
    const idxF = tClamped * segCount
    const attachBoneIdx = bodyBoneIdxs[Math.round(idxF)]

    // Each side (L/R): an anchor bone offset sideways from the body
    // bone, then a chain of segment bones along the anchor's +Y.
    for (const side of ['L', 'R'] as const) {
      const sign = side === 'L' ? 1 : -1
      // LimbAnchor sits at the body bone with a small sideways offset.
      // Its bind-pose rotation aligns +Y outward (sideways + down per
      // spreadAngle and downAngle). We bake the rotation into the
      // anchor's preRotation; the offset is along PARENT's frame so we
      // use a small lateral X to push the anchor off the body surface.
      const anchorIdx = rig.length
      rig.push({
        name: `LimbP${p}${side}_Anchor`,
        parent: attachBoneIdx,
        offset: [sign * spec.body.radius * 0.8, 0, 0],
        preRotation: limbAnchorRotation(pair.spreadAngle, pair.downAngle, sign),
      })

      let parentIdx = anchorIdx
      for (let s = 0; s < pair.segments.length; s++) {
        const segSpec = pair.segments[s]
        const childIdx = rig.length
        rig.push({
          name: `LimbP${p}${side}_Seg${s}`,
          parent: parentIdx,
          // Each limb segment offsets along PARENT's +Y (limb axis).
          offset: s === 0 ? [0, 0, 0] : [0, pair.segments[s - 1].length, 0],
        })
        parentIdx = childIdx
      }
      // Tip bone — places the end of the last segment, no display.
      const lastSeg = pair.segments[pair.segments.length - 1]
      const tipIdx = rig.length
      rig.push({
        name: `LimbP${p}${side}_Tip`,
        parent: parentIdx,
        offset: [0, lastSeg.length, 0],
      })

      // Capsule per limb segment: from segment bone to the next
      // segment-or-tip bone. Same type-15 pattern as body.
      const limbBones = []
      // Walk the chain we just built — anchor → seg0 → seg1 → ... → tip
      for (let s = 0; s < pair.segments.length; s++) {
        // Find the bone index of LimbP{p}{side}_Seg{s}
        const segName = `LimbP${p}${side}_Seg${s}`
        const idx = rig.findIndex((j) => j.name === segName)
        if (idx >= 0) limbBones.push(idx)
      }
      limbBones.push(tipIdx)
      for (let i = 0; i + 1 < limbBones.length; i++) {
        const segSpec = pair.segments[i]
        prims.push({
          type: 15,
          paletteSlot: pair.paletteSlot,
          boneIdx: limbBones[i],
          params: [segSpec.radiusStart, segSpec.radiusEnd, limbBones[i + 1], segSpec.length],
          offsetInBone: [0, 0, 0],
        })
      }
    }
  }

  // -------------------- World matrices (T-pose, single frame) --------------------
  const worldMats = computeBindPoseWorldMats(rig)

  return { rig, worldMats, prims }
}

// ============================================================================
// Bind-pose world-matrix bake
// ============================================================================

/** Given a rig with optional preRotation per joint, compute one frame
 *  of world matrices (column-major, 16 floats per joint). Walks the
 *  hierarchy parent-first, composing local = T(offset) × R(preRotation)
 *  and world = parent.world × local. Roots get identity for parent.
 *
 *  Important: the body chain bones use a backward-pointing convention.
 *  HeadAnchor's bind rotation flips +Y to point along world -Z so that
 *  child offsets [0, segLen, 0] place children backward, which matches
 *  the cape/hair convention where bone +Y is the chain direction. */
function computeBindPoseWorldMats(rig: Joint[]): Float32Array {
  const out = new Float32Array(rig.length * 16)
  const localMat = new Float32Array(16)

  for (let j = 0; j < rig.length; j++) {
    const joint = rig[j]
    // Local = R(preRotation) × T(offset) — apply rotation first so the
    // offset is in the rotated parent frame's terms, then translate.
    // Wait — Mixamo convention: T(offset) × R(preRotation). The offset
    // is in PARENT'S local frame. preRotation rotates THIS bone's own
    // axes. So the local matrix is: position-this-bone, then orient-it.
    mat4Identity(localMat)
    if (joint.preRotation) {
      const [rx, ry, rz] = joint.preRotation
      mat4FromEulerXYZ(localMat, rx, ry, rz)
    }
    localMat[12] = joint.offset[0]
    localMat[13] = joint.offset[1]
    localMat[14] = joint.offset[2]

    // HeadAnchor specifically: rotate +Y to point along world -Z so the
    // body chain extends backward. Identified by parent === -1.
    if (joint.parent < 0 && joint.name === 'HeadAnchor') {
      // Rotation that maps local +Y → world -Z (and +Z → +Y so the
      // creature is "standing" with Z up still). 90° around X axis.
      mat4FromEulerXYZ(localMat, Math.PI * 0.5, 0, 0)
      localMat[12] = joint.offset[0]
      localMat[13] = joint.offset[1]
      localMat[14] = joint.offset[2]
    }

    if (joint.parent < 0) {
      // Root → world = local
      for (let i = 0; i < 16; i++) out[j * 16 + i] = localMat[i]
    } else {
      // world = parent.world × local
      const parentBase = joint.parent * 16
      mat4MulInto(out, j * 16, out, parentBase, localMat, 0)
    }
  }

  return out
}

// ============================================================================
// Helpers
// ============================================================================

function limbAnchorRotation(spread: number, down: number, sign: number): Vec3 {
  // Limb anchor bind-pose: rotate so the limb's +Y points sideways and
  // down. Body bone +Y points backward (world -Z), so the anchor frame
  // is parented in that. We want anchor's +Y in world to be:
  //   side = sign * sin(spread) along X
  //   down = -sin(down) along Y (world Y is up)
  //   forward/backward = small Z component (mostly perpendicular)
  //
  // Encoding as Euler XYZ: rotate around Z to spread sideways, then
  // around X to droop down. Sign flips on the X rotation for the
  // mirrored side so both legs droop the same way relative to the body.
  // In the parent (body) frame, X axis points sideways (world X for a
  // forward-facing creature). So Z rotation in local frame swings the
  // anchor in the XY plane (sideways), and X rotation drops it.
  return [down, 0, sign * spread]
}

function mat4Identity(out: Float32Array) {
  for (let i = 0; i < 16; i++) out[i] = 0
  out[0] = 1; out[5] = 1; out[10] = 1; out[15] = 1
}

function mat4FromEulerXYZ(out: Float32Array, rx: number, ry: number, rz: number) {
  // Composed rotation Rx × Ry × Rz, column-major. Applied as v' = R × v
  // where v is a column vector — standard transform of a basis vector.
  const cx = Math.cos(rx), sx = Math.sin(rx)
  const cy = Math.cos(ry), sy = Math.sin(ry)
  const cz = Math.cos(rz), sz = Math.sin(rz)
  // Standard XYZ: M = Rx * Ry * Rz (extrinsic), see mat4 reference.
  out[0] = cy * cz
  out[1] = sx * sy * cz + cx * sz
  out[2] = -cx * sy * cz + sx * sz
  out[3] = 0
  out[4] = -cy * sz
  out[5] = -sx * sy * sz + cx * cz
  out[6] = cx * sy * sz + sx * cz
  out[7] = 0
  out[8] = sy
  out[9] = -sx * cy
  out[10] = cx * cy
  out[11] = 0
  out[12] = 0; out[13] = 0; out[14] = 0; out[15] = 1
}

function mat4MulInto(
  dst: Float32Array, dstOff: number,
  a: Float32Array, aOff: number,
  b: Float32Array, bOff: number,
) {
  // dst = a × b, all column-major 4×4. dstOff/aOff/bOff are starting
  // float offsets within their respective arrays.
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      dst[dstOff + col * 4 + row] =
        a[aOff + row]      * b[bOff + col * 4]     +
        a[aOff + row + 4]  * b[bOff + col * 4 + 1] +
        a[aOff + row + 8]  * b[bOff + col * 4 + 2] +
        a[aOff + row + 12] * b[bOff + col * 4 + 3]
    }
  }
}

// ============================================================================
// Presets
// ============================================================================

const SKIN_SLOT     = 2
const FUR_SLOT      = 8   // cape-ish brown for body
const FEATHER_SLOT  = 9   // accent
const LEATHER_SLOT  = 10

export const CREATURE_PRESETS: Record<string, CreatureSpec> = {
  bird: {
    name: 'bird',
    body:    { segments: 0, totalLength: 0.30, radius: 0.10, paletteSlot: FEATHER_SLOT },
    head:    { size: [0.07, 0.07, 0.08], paletteSlot: FEATHER_SLOT },
    limbPairs: [
      // 1 wing pair attached at the front body bone, swept sideways.
      {
        attachT: 0.2,
        spreadAngle: Math.PI * 0.45,
        downAngle: 0.1,
        paletteSlot: FEATHER_SLOT,
        segments: [
          { length: 0.12, radiusStart: 0.04, radiusEnd: 0.025 },
          { length: 0.14, radiusStart: 0.025, radiusEnd: 0.005 },
        ],
      },
      // 1 leg pair (small, drooping under the body)
      {
        attachT: 0.7,
        spreadAngle: 0.15,
        downAngle: Math.PI * 0.45,
        paletteSlot: LEATHER_SLOT,
        segments: [
          { length: 0.08, radiusStart: 0.012, radiusEnd: 0.010 },
          { length: 0.06, radiusStart: 0.010, radiusEnd: 0.008 },
        ],
      },
    ],
  },
  spider: {
    name: 'spider',
    body:    { segments: 1, totalLength: 0.20, radius: 0.075, paletteSlot: FUR_SLOT },
    head:    { size: [0.05, 0.05, 0.05], paletteSlot: FUR_SLOT },
    limbPairs: spiderLegs(),
  },
  snake: {
    name: 'snake',
    body:    { segments: 14, totalLength: 1.20, radius: 0.045, paletteSlot: SKIN_SLOT },
    head:    { size: [0.05, 0.04, 0.04], paletteSlot: SKIN_SLOT },
    limbPairs: [],
  },
  centipede: {
    name: 'centipede',
    body:    { segments: 20, totalLength: 0.80, radius: 0.030, paletteSlot: SKIN_SLOT },
    head:    { size: [0.04, 0.03, 0.03], paletteSlot: SKIN_SLOT },
    limbPairs: centipedeLegs(),
  },
}

function spiderLegs(): LimbPairSpec[] {
  // 4 evenly-spaced pairs along the 2-segment body. Long thin legs.
  const pairs: LimbPairSpec[] = []
  const positions = [0.0, 0.33, 0.66, 1.0]   // 4 attach points
  for (let i = 0; i < 4; i++) {
    pairs.push({
      attachT: positions[i],
      spreadAngle: Math.PI * 0.35,
      // Legs angle outward and down. Front-back lean spreads them out
      // along the body (front legs lean forward, back legs lean backward).
      downAngle: Math.PI * 0.10,
      paletteSlot: FUR_SLOT,
      segments: [
        { length: 0.18, radiusStart: 0.015, radiusEnd: 0.010 },
        { length: 0.18, radiusStart: 0.010, radiusEnd: 0.005 },
      ],
    })
  }
  return pairs
}

function centipedeLegs(): LimbPairSpec[] {
  // Many pairs, one per body segment.
  const pairs: LimbPairSpec[] = []
  for (let i = 0; i < 18; i++) {
    pairs.push({
      attachT: i / 18,
      spreadAngle: Math.PI * 0.45,
      downAngle: Math.PI * 0.15,
      paletteSlot: LEATHER_SLOT,
      segments: [
        { length: 0.06, radiusStart: 0.006, radiusEnd: 0.003 },
      ],
    })
  }
  return pairs
}
