/**
 * Node particles — the chain mechanic for capes, long hair, tentacles,
 * ribbons, trails. Sibling to secondary.ts (springs); both ship in the
 * same engine and are the two primitives for character secondary motion.
 *
 * Use this when you have a CHAIN where each link should trail the
 * previous with progressive lag. Use a spring (secondary.ts) when you
 * have a single mass that should oscillate around an anchor (jiggle).
 *
 *   chain mechanism      → node_particle.ts (this file)
 *   single-mass jiggle   → secondary.ts
 *
 * THE TRICK: ONE-FRAME-STALE PARENT READ
 * --------------------------------------
 * Each particle has exactly one parent (a rig bone, or another node
 * particle further up the chain). Each frame, the particle reads its
 * parent's PREVIOUS frame world position — not the current frame —
 * and uses it as a target. The result is a one-frame lag at every
 * link in the chain. A 4-segment cape's tip lags 4 frames behind the
 * body. Free chain flow, no springs, no integration, no instability
 * under variable dt.
 *
 * Pattern as shipped on Returnal — node particles for the alien
 * tentacles, ribbons, and homing-bullet trails. Their public tech
 * blog details the same parent-child / one-frame-stale design we
 * implement here.
 *
 * THE CONSTRAINT: DISTANCE CLAMP
 * ------------------------------
 * After picking a target, clamp the particle's distance from its
 * CURRENT-frame parent to [minLength, maxLength]. Tight bounds
 * (0.95-1.05) → taut cloth read. Loose bounds (0.7-1.3) → floppy
 * read. No springs needed; the constraint alone gives the rigid-
 * with-give feel of cloth/rope.
 */

import type { Vec3 } from '../math/vec'

/** A single node in a chain. Resides at a world position; reads its
 *  parent's previous-frame position to derive the next target. */
export interface NodeParticle {
  /** Rig-bone index this node follows, OR an index into the SAME
   *  particles array (chain link). The kind is disambiguated by
   *  `parentKind`. */
  parentRef: number
  parentKind: 'bone' | 'particle'
  /** Rest offset from the parent, in the parent's local frame. The
   *  particle wants to sit here when there's no motion. For cape:
   *  CapeRoot's restOffset = (0, -0.05, -0.10) — slightly below and
   *  behind Spine2's local origin. */
  restOffset: Vec3
  /** Distance bounds from the parent's current-frame position. The
   *  rigid-with-give clamp. min ≤ rest length ≤ max; equal values
   *  give a fully rigid link. */
  minLength: number
  maxLength: number
  /** Current world position of this particle. Updated each tick. */
  position: Vec3
  /** Cached parent's world position from the LAST frame. Read every
   *  tick to compute target; written every tick (after target eval)
   *  so next frame's children read this frame's value. The crucial
   *  one-frame-stale data. */
  prevParentPos: Vec3
  /** Whether the particle's `position` has been initialised. First
   *  tick on a freshly-spawned chain seeds prevParentPos = current
   *  parent pos to avoid a "snap from origin" on frame 0. */
  initialised: boolean
}

/**
 * Allocate a fresh particle. After this, call `tickNodeParticle(...)`
 * each frame.
 *
 *   parentRef + parentKind: where this node hangs from. For cape root:
 *   parent is the Spine2 bone (kind 'bone'). For cape mid: parent is
 *   the cape root particle (kind 'particle'). For cape tip: parent
 *   is the cape mid particle.
 *
 *   restOffset: in the parent's local frame. For a cape, you typically
 *   want offsets that drape down + slightly back: (0, -segLen, -0.02).
 *
 *   restLength: the natural distance between this node and its parent.
 *   minLength / maxLength default to ±5% of restLength (taut cloth feel).
 */
export function createNodeParticle(opts: {
  parentRef: number
  parentKind: 'bone' | 'particle'
  restOffset: Vec3
  restLength: number
  minLength?: number
  maxLength?: number
}): NodeParticle {
  return {
    parentRef:    opts.parentRef,
    parentKind:   opts.parentKind,
    restOffset:   [opts.restOffset[0], opts.restOffset[1], opts.restOffset[2]],
    minLength:    opts.minLength ?? opts.restLength * 0.95,
    maxLength:    opts.maxLength ?? opts.restLength * 1.05,
    position:     [0, 0, 0],
    prevParentPos: [0, 0, 0],
    initialised:  false,
  }
}

/**
 * Tick one particle. Order matters: process root-to-tip so each
 * child reads its parent's STALE position (set in the previous
 * frame's tick, before the parent updates its own prevParentPos).
 *
 *   getBoneWorldPos:   bone-index → world position. Provided by the
 *                      caller from the rig's current world matrices.
 *   particles:         the full chain array, used when parentKind is
 *                      'particle' (chain-internal parent reference).
 *
 *   restOffsetWorld:   pre-rotated restOffset in world space, computed
 *                      from the parent's current frame rotation. Caller
 *                      computes this so we don't drag a quaternion-math
 *                      dep into this file.
 */
export function tickNodeParticle(
  p: NodeParticle,
  particles: readonly NodeParticle[],
  getBoneWorldPos: (boneIdx: number) => Vec3,
  restOffsetWorld: Vec3,
): void {
  // Resolve current-frame parent world position.
  const parentNow: Vec3 = p.parentKind === 'bone'
    ? getBoneWorldPos(p.parentRef)
    : particles[p.parentRef].position

  // Seed on first tick so we don't snap from the origin.
  if (!p.initialised) {
    p.position = [
      parentNow[0] + restOffsetWorld[0],
      parentNow[1] + restOffsetWorld[1],
      parentNow[2] + restOffsetWorld[2],
    ]
    p.prevParentPos = [parentNow[0], parentNow[1], parentNow[2]]
    p.initialised = true
    return
  }

  // Target = STALE parent position + rest offset (rotated to world by caller).
  // The one-frame stale read is what creates the chain-flow feel.
  const targetX = p.prevParentPos[0] + restOffsetWorld[0]
  const targetY = p.prevParentPos[1] + restOffsetWorld[1]
  const targetZ = p.prevParentPos[2] + restOffsetWorld[2]

  // Move particle TOWARD target, then clamp distance from parent's
  // CURRENT position. We snap directly to the target — the lag comes
  // from the staleness of `prevParentPos`, not from a smoothing factor.
  // Then the clamp keeps the link rigid.
  let px = targetX
  let py = targetY
  let pz = targetZ

  const dx = px - parentNow[0]
  const dy = py - parentNow[1]
  const dz = pz - parentNow[2]
  const dist = Math.hypot(dx, dy, dz)
  if (dist > 1e-6) {
    let clampedDist = dist
    if (dist < p.minLength) clampedDist = p.minLength
    else if (dist > p.maxLength) clampedDist = p.maxLength
    if (clampedDist !== dist) {
      const k = clampedDist / dist
      px = parentNow[0] + dx * k
      py = parentNow[1] + dy * k
      pz = parentNow[2] + dz * k
    }
  }
  p.position[0] = px
  p.position[1] = py
  p.position[2] = pz

  // CRUCIAL: cache parent's CURRENT position for next frame's read by
  // OUR children. This must happen at the END of the tick, after the
  // target has been computed using the OLD value.
  p.prevParentPos[0] = parentNow[0]
  p.prevParentPos[1] = parentNow[1]
  p.prevParentPos[2] = parentNow[2]
}

/**
 * Tick a whole chain in root-to-tip order. Convenience wrapper for
 * the common case where you have one chain and want it stepped.
 *
 *   restOffsetsWorld: per-particle, pre-rotated rest offsets. Caller
 *   computes these from each particle's parent rotation each frame.
 */
export function tickChain(
  particles: NodeParticle[],
  getBoneWorldPos: (boneIdx: number) => Vec3,
  restOffsetsWorld: Vec3[],
): void {
  for (let i = 0; i < particles.length; i++) {
    tickNodeParticle(particles[i], particles, getBoneWorldPos, restOffsetsWorld[i])
  }
}

/**
 * Helper: derive a bone's local rotation that orients its X axis from
 * the bone position TOWARD a particle position. Useful for setting a
 * cape segment's rotation each frame so its primitive points along
 * the chain.
 *
 * Returns the rotation as Euler XYZ (radians). Caller composes this
 * into the bone's display matrix.
 *
 *   For a cape segment whose rest pose hangs along -Y:
 *   - Compute direction from segment-bone-pos to next-segment particle pos
 *   - Pass to this function; returns the angles needed to rotate -Y toward
 *     that direction.
 */
export function lookAtEuler(from: Vec3, to: Vec3): Vec3 {
  const dx = to[0] - from[0]
  const dy = to[1] - from[1]
  const dz = to[2] - from[2]
  const len = Math.hypot(dx, dy, dz) || 1
  // Spherical angles for direction = (dx, dy, dz) / len.
  // pitch (X-axis) brings -Y toward the desired Y component.
  // yaw   (Y-axis) rotates around vertical to land on (dx, dz) plane.
  const yaw   = Math.atan2(dx, dz)
  const pitch = Math.asin(-dy / len)
  return [pitch, yaw, 0]
}
