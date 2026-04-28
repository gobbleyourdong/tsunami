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
  /** Optional per-preset camera framing — orthoSize (smaller = zoomed
   *  in) and look-at target. Demos read these on preset switch so a
   *  bird at 0.30m doesn't render at the same zoom as a 1.20m snake.
   *  Default if absent: orthoSize 0.6, target [0, 0.1, 0]. */
  camera?: { orthoSize: number; target: [number, number, number] }
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
  /** Optional ellipsoid override — when set AND segments === 0, the
   *  body emits as a single type-3 ellipsoid at BodySeg0 instead of a
   *  type-15 capsule chain. Half-extents in body-local frame:
   *  [X = side, Y = head-to-tail, Z = depth]. Use this for round /
   *  egg-shaped bodies (bird, spider) where a degenerate single
   *  capsule would render as a perfect sphere. */
  halfExtents?: [number, number, number]
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
  /** Sideways spread from body axis, radians. PI/2 = perpendicular,
   *  0 = parallel forward. */
  spreadAngle: number
  /** Vertical droop, radians. Positive = down. PI/2 = straight down. */
  downAngle: number
  paletteSlot: number
  /** Limb is a ribbon-chain (type 23) over segmentCount+1 bones; each
   *  segment is segmentLength along bone-Y, halfW × halfThick cross-
   *  section, tapering to halfW × tipTaper at the chain tip. Maps to
   *  the same SDF that drives the cape and hair-strands. Set 0 (or
   *  segmentCount=0) to skip the pair. */
  segmentCount: number
  segmentLength: number
  /** Half-width of the ribbon cross-section in the broad direction
   *  (looks like the back-hair chain when halfW >> halfThick). */
  halfW: number
  /** Half-thickness in the narrow direction. */
  halfThick: number
  /** Cross-section scale at the chain tip — 1 = no taper, 0 = sharp
   *  point. 0.3-0.5 reads as a tapered limb. */
  tipTaper: number
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

  // Body bones BodySeg0..BodySegN, each offset by segLen along its
  // parent's +Y. HeadAnchor's bind rotation puts +Y along world -Z so
  // the chain extends backward. Every body bone — including BodySeg0
  // — uses [0, segLen, 0]: BodySeg0 sits one segment-length behind
  // HeadAnchor (NOT at HeadAnchor's position, which would collapse
  // the head→body capsule into a sphere).
  const bodyBoneIdxs: number[] = []
  for (let i = 0; i < segCount + 1; i++) {
    const parent = i === 0 ? headAnchorIdx : rig.length - 1
    rig.push({
      name: `BodySeg${i}`,
      parent,
      offset: [0, segLen, 0],
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

  // -------------------- Body --------------------
  // Two emit modes:
  //   (a) ellipsoid override (BodySpec.halfExtents set, segments=0):
  //       single type-3 ellipsoid at BodySeg0, centered between
  //       HeadAnchor and BodySeg0 by an offset of -segLen/2 along
  //       bone-Y so the lump spans head → tail.
  //   (b) capsule chain: one type-15 round capsule per (i, i+1) bone
  //       pair walking HeadAnchor → BodySeg0 → ... → BodySegN.
  // Capsule chain is the right call for snake/centipede where
  // segments matter for animation; ellipsoid is the right call for
  // bird/spider where the body is a single rounded lump.
  if (spec.body.halfExtents && segCount === 0) {
    const [hx, hy, hz] = spec.body.halfExtents
    prims.push({
      type: 3,
      paletteSlot: spec.body.paletteSlot,
      boneIdx: bodyBoneIdxs[0],
      params: [hx, hy, hz, 0],
      offsetInBone: [0, -segLen * 0.5, 0],   // center between head & tail
    })
  } else {
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
  }

  // -------------------- Limb pairs (ribbon-chain) --------------------
  // Each limb is a single type-23 ribbon-chain primitive walking N+1
  // CONSECUTIVE bones (Seg0..SegN where SegN is the tip endpoint).
  // sdRibbonChain reads bone matrices at startBone..startBone+count-1
  // — they MUST be consecutive in the rig array, so we push them in
  // order without interleaving anything else. The Anchor bone holds
  // the bind-pose rotation that points the chain outward + down; its
  // own +Y axis is the chain root direction, and Seg0..N inherit
  // that frame through the hierarchy via offset [0, segLen, 0].
  for (let p = 0; p < spec.limbPairs.length; p++) {
    const pair = spec.limbPairs[p]
    if (pair.segmentCount <= 0) continue
    const tClamped = Math.max(0, Math.min(1, pair.attachT))
    const idxF = tClamped * segCount
    const attachBoneIdx = bodyBoneIdxs[Math.round(idxF)]

    for (const side of ['L', 'R'] as const) {
      const sign = side === 'L' ? 1 : -1
      // 1. Anchor bone — sideways offset off the body, with bind-pose
      //    rotation pointing limb +Y outward+down.
      const anchorIdx = rig.length
      rig.push({
        name: `LimbP${p}${side}_Anchor`,
        parent: attachBoneIdx,
        offset: [sign * spec.body.radius * 0.7, 0, 0],
        preRotation: limbAnchorRotation(pair.spreadAngle, pair.downAngle, sign),
      })

      // 2. Chain bones Seg0..SegN — Seg0 sits AT the anchor (offset 0),
      //    each subsequent seg offset by segmentLength along bone +Y.
      //    SegN is the tip endpoint (no segment hangs off it).
      const chainStart = rig.length
      let prev = anchorIdx
      for (let s = 0; s <= pair.segmentCount; s++) {
        const childIdx = rig.length
        rig.push({
          name: `LimbP${p}${side}_Seg${s}`,
          parent: prev,
          offset: s === 0 ? [0, 0, 0] : [0, pair.segmentLength, 0],
        })
        prev = childIdx
      }

      // 3. Single ribbon-chain prim at chain root, count = segmentCount+1.
      prims.push({
        type: 23,
        paletteSlot: pair.paletteSlot,
        boneIdx: chainStart,
        params: [pair.segmentCount + 1, pair.halfW, pair.halfThick, pair.tipTaper],
        offsetInBone: [0, 0, 0],
      })
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
    // Plump egg body, big head, FLAT membrane wings (halfW>>halfThick
    // ribbon — same look as the back-hair / ponytail chain).
    body: {
      segments: 0, totalLength: 0.18, radius: 0.10, paletteSlot: FEATHER_SLOT,
      halfExtents: [0.075, 0.10, 0.085],     // egg ellipsoid
    },
    head: { size: [0.08, 0.08, 0.09], paletteSlot: FEATHER_SLOT },
    limbPairs: [
      // Wings — flat 2-segment ribbon, wide × thin like a feather.
      {
        attachT: 0.2,
        spreadAngle: Math.PI * 0.45,
        downAngle: 0.05,
        paletteSlot: FEATHER_SLOT,
        segmentCount: 2, segmentLength: 0.07,
        halfW: 0.045, halfThick: 0.005,    // FLAT — like back hair
        tipTaper: 0.4,
      },
      // Legs — twig pair under the body. Thin chain.
      {
        attachT: 0.6,
        spreadAngle: 0.15,
        downAngle: Math.PI * 0.50,
        paletteSlot: LEATHER_SLOT,
        segmentCount: 1, segmentLength: 0.08,
        halfW: 0.012, halfThick: 0.012,
        tipTaper: 0.6,
      },
    ],
    camera: { orthoSize: 0.28, target: [0, 0.0, 0] },
  },
  spider: {
    name: 'spider',
    body: {
      segments: 0, totalLength: 0.13, radius: 0.085, paletteSlot: FUR_SLOT,
      halfExtents: [0.075, 0.085, 0.075],   // round-ish lump
    },
    head: { size: [0.045, 0.045, 0.045], paletteSlot: FUR_SLOT },
    limbPairs: spiderLegs(),
    camera: { orthoSize: 0.34, target: [0, -0.04, 0] },
  },
  snake: {
    name: 'snake',
    body:    { segments: 10, totalLength: 0.70, radius: 0.035, paletteSlot: SKIN_SLOT },
    head:    { size: [0.05, 0.04, 0.05], paletteSlot: SKIN_SLOT },
    limbPairs: [],
    camera: { orthoSize: 0.40, target: [0, 0.0, -0.20] },
  },
  centipede: {
    name: 'centipede',
    body:    { segments: 12, totalLength: 0.60, radius: 0.030, paletteSlot: SKIN_SLOT },
    head:    { size: [0.040, 0.035, 0.040], paletteSlot: SKIN_SLOT },
    limbPairs: centipedeLegs(),
    camera: { orthoSize: 0.38, target: [0, -0.02, -0.18] },
  },
}

function spiderLegs(): LimbPairSpec[] {
  // 4 evenly-spaced pairs = 8 legs. Each leg is a 2-segment ribbon
  // chain in the same shape as the bangs hair-strand: thin halfW,
  // slightly thinner halfThick, sharp taper to the tip.
  const pairs: LimbPairSpec[] = []
  const positions = [0.0, 0.33, 0.66, 1.0]
  for (let i = 0; i < 4; i++) {
    pairs.push({
      attachT: positions[i],
      spreadAngle: Math.PI * 0.40,
      downAngle: Math.PI * 0.15,
      paletteSlot: FUR_SLOT,
      segmentCount: 2, segmentLength: 0.10,
      halfW: 0.012, halfThick: 0.008,        // thin like bangs
      tipTaper: 0.3,
    })
  }
  return pairs
}

function centipedeLegs(): LimbPairSpec[] {
  const pairs: LimbPairSpec[] = []
  for (let i = 0; i < 18; i++) {
    pairs.push({
      attachT: i / 18,
      spreadAngle: Math.PI * 0.45,
      downAngle: Math.PI * 0.15,
      paletteSlot: LEATHER_SLOT,
      segmentCount: 1, segmentLength: 0.06,
      halfW: 0.006, halfThick: 0.005,
      tipTaper: 0.5,
    })
  }
  return pairs
}
