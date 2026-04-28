/**
 * Wing rig — one mirrored pair of ribbon-chain wings, with a per-frame
 * flap animation that composes onto whatever body animation is playing.
 *
 * Architecture: every "limb component" lives in its own module
 * (wing_rig.ts here, leg_rig.ts / head_rig.ts / etc later). Each
 * exports:
 *
 *   1. A spec type (dimensions + appearance knobs)
 *   2. buildBones() — returns Joint[] suitable for splicing into a
 *      creature rig array. Parents are RELATIVE indices within the
 *      returned array; the caller offsets them when splicing.
 *   3. buildPrim() — returns the SDF primitive emitted at the chain
 *      root (ribbon for wings, capsule chain for legs, etc).
 *   4. Animation generators — pure functions of phase ∈ [0, 1]
 *      returning local-rotation deltas keyed by bone NAME (so the
 *      bake pipeline doesn't need to track joint indices). These are
 *      authored independent of the creature; "wing flap" composes
 *      onto bird, dragon, bat, whatever as long as the bone names
 *      match the convention this module emits.
 *
 * The same VAT bake format used for Mixamo animations consumes the
 * output: build the rig once, walk frames, apply animation overrides,
 * compose world matrices, write VAT1 binary.
 */

import type { Joint } from './skeleton'
import type { RaymarchPrimitive } from './raymarch_renderer'
import type { Vec3 } from '../math/vec'

// ============================================================================
// Spec
// ============================================================================

export interface WingSpec {
  /** Number of visible chain segments. 0 = single straight ribbon
   *  segment between Anchor and the tip; N = N+1 ribbon segments
   *  with N intermediate joints. Bend control: more segments = more
   *  joints to drive in fold / glide / flap variants. */
  segmentCount: number
  /** Length of each ribbon segment in meters. Total wing span =
   *  segmentLength × (segmentCount + 1). */
  segmentLength: number
  /** Cross-section half-extents. halfW is the broad direction (held
   *  perpendicular to the camera by the bind rotation), halfThick is
   *  the narrow (membrane thickness). Set halfW >> halfThick for the
   *  classic flat-wing silhouette — same trick the back-hair ponytail
   *  uses. */
  halfW: number
  halfThick: number
  /** Cross-section scale at the wing tip. 0.4 = noticeable taper to a
   *  feather-tip shape. 1.0 = no taper. */
  tipTaper: number
  paletteSlot: number
  /** Bind-pose angle from body's local +Y (vertical) to wing chain
   *  direction, applied in the X-Y plane. π/2 = wings held straight
   *  out horizontally. < π/2 = wings tilted up at rest (folded);
   *  > π/2 = wings drooping. */
  spreadAngle: number
}

export const DEFAULT_WING_SPEC: WingSpec = {
  segmentCount: 2,
  segmentLength: 0.10,
  halfW: 0.060,
  halfThick: 0.012,
  tipTaper: 0.4,
  paletteSlot: 9,    // creature_demo's FEATHER_SLOT
  spreadAngle: Math.PI * 0.50,
}

// ============================================================================
// Bones
// ============================================================================

/** Build bones for a single wing side. Returns Anchor (index 0) +
 *  Seg0..SegN (indices 1..N+1) — segmentCount+2 bones total. Parent
 *  indices are RELATIVE to the returned array: Anchor's parent is
 *  -1 (placeholder; caller sets to the attach-socket bone), Seg0's
 *  parent is 0, Seg1's parent is 1, etc. The caller offsets all
 *  parents by the splice position when inserting into the rig.
 *
 *  Bone names: Wing${side}${suffix} where suffix is _Anchor or
 *  _Seg{i}. The animation generators key on these names.
 *
 *  attachSidewaysOffset: sideways offset (signed, in attach socket's
 *  local frame) from socket center to anchor position. Caller picks
 *  this based on the socket's local geometry — e.g. ~70% of body
 *  halfW for a body-mounted wing. */
export function buildWingBones(
  spec: WingSpec,
  side: 'L' | 'R',
  attachSidewaysOffset: number,
): Joint[] {
  const sign = side === 'L' ? -1 : 1
  const bones: Joint[] = [
    {
      name: `Wing${side}_Anchor`,
      parent: -1,    // placeholder; caller assigns to socket bone
      offset: [sign * Math.abs(attachSidewaysOffset), 0, 0],
      // Single Z rotation puts local +Y at the desired sideways angle.
      // Same convention as creature_rig.ts limbAnchorRotation: rotating
      // +Y by -sign × spreadAngle around Z lands it at the L/R side.
      preRotation: [0, 0, -sign * spec.spreadAngle],
    },
  ]
  for (let i = 0; i <= spec.segmentCount; i++) {
    bones.push({
      name: `Wing${side}_Seg${i}`,
      parent: i,    // relative to this array (0 = Anchor)
      offset: i === 0 ? [0, 0, 0] : [0, spec.segmentLength, 0],
    })
  }
  return bones
}

/** Ribbon-chain primitive emitted at the first chain bone (Seg0).
 *  The chain walks count bones consecutively in the rig array, so
 *  the caller MUST keep wing bones in the order returned by
 *  buildWingBones — Anchor first, Seg0 immediately after, then
 *  Seg1..SegN consecutively. firstSegBoneIdx is Seg0's final rig
 *  index after splicing.
 *
 *  count = segmentCount + 1 = number of chain bones (Seg0 through
 *  SegN). The Anchor is NOT part of the ribbon walk — it's the
 *  attachment frame whose preRotation orients the chain. */
export function buildWingPrim(spec: WingSpec, firstSegBoneIdx: number): RaymarchPrimitive {
  return {
    type: 23,
    paletteSlot: spec.paletteSlot,
    boneIdx: firstSegBoneIdx,
    params: [spec.segmentCount + 1, spec.halfW, spec.halfThick, spec.tipTaper],
    offsetInBone: [0, 0, 0],
  }
}

// ============================================================================
// Animations
// ============================================================================

/** Per-bone local-rotation delta, keyed by bone name. Values are
 *  Euler XYZ in radians, applied ON TOP of the bone's bind-pose
 *  rotation by the bake pipeline. null entries (or missing bones)
 *  inherit the bind pose unchanged.
 *
 *  Same shape every limb-component animation returns, so the bake
 *  pipeline composes them generically — it just walks animation
 *  outputs by bone name and accumulates rotation deltas. */
export type AnimationOverrides = Record<string, Vec3>

/** Wing flap. Wings rotate around the body's forward axis (Z) to
 *  rock the chain up and down. Both sides flap symmetrically — the
 *  sign flip on each side keeps them mirrored across the X axis so
 *  they meet at the top of the upstroke and fully extended at the
 *  bottom of the downstroke.
 *
 *  - phase: 0..1 fraction of one full flap cycle (sin(2π × phase))
 *  - amplitude: peak rotation in radians (e.g. π/4 = ±45° flap)
 *
 *  Returns an AnimationOverrides keyed on the Anchor bone names
 *  (`WingL_Anchor`, `WingR_Anchor`) — the anchor's bind preRotation
 *  already handles spread; this delta adds the flap on top. */
export function flapAnimation(phase: number, amplitude: number): AnimationOverrides {
  const flap = Math.sin(phase * 2 * Math.PI) * amplitude
  // Both anchors rotate around bone-local Z by the SAME signed delta.
  // Anchor's bind +Y points outward (sideways), so a +Z rotation lifts
  // BOTH wings up/down symmetrically — not mirrored, because L and R
  // anchors have opposite bind frames already (the sign flip in
  // buildWingBones), and the local-Z rotation composes onto each.
  return {
    WingL_Anchor: [0, 0,  flap],
    WingR_Anchor: [0, 0, -flap],
  }
}

/** Wing fold — anchors rotate inward so wings tuck against the body.
 *  Static (no phase). Composable: a fold partial (0..1) lets you
 *  blend between extended and folded for transitions. */
export function foldAnimation(amount: number): AnimationOverrides {
  // Tuck angle pivots the anchor +Y from horizontal-out toward up-and-in.
  // Symmetric like flap: each side rotates Z by amount × π/3 in the
  // direction that brings the wing tip toward the spine.
  const tuck = amount * Math.PI / 3
  return {
    WingL_Anchor: [0, 0, -tuck],
    WingR_Anchor: [0, 0,  tuck],
  }
}
