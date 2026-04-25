/**
 * Secondary animation — single-spring driver for all dangly things on a
 * character (capes, hair, scarves, tassels, robe edges). One physics
 * integration per character; every dangly bit reads the same source and
 * applies its own scale + per-axis constraint.
 *
 * Why one spring drives many secondaries:
 *   - O(1) physics per character regardless of how much dangly stuff
 *     the character carries.
 *   - Coherent motion — everything sways together when the body pivots.
 *   - Authoring is "+1 reader" not "+N more spring couplings."
 *
 * Pattern as shipped on Jedi: Fallen Order — Cal's poncho was a
 * full-physics chain (lots of edge cases, would have shipped cleaner
 * as procedural). His other clothes + hair + every supporting
 * character's hair used the single-spring-on-hips driving secondary
 * approach we're building here. That pattern shipped clean and is
 * the right starting point for sprite-resolution dangly stuff.
 *
 * The master oscillator is a damped spring whose rest target is the
 * character's hip-anchored point. When the character moves, the spring's
 * `position` lags behind `restTarget`. The lag vector — `restTarget -
 * position` — is the "wind" that all secondaries respond to. Each
 * secondary multiplies the lag by a per-bone scale (root small, tip
 * large) and applies the result as a bone rotation, masked + clamped.
 *
 * Perceptual independence: hair feels lighter than cape because hair's
 * reader smooths the master signal less aggressively. Both read the
 * same source, but each filters at its own time constant. One vec3
 * lerp per reader buys you mass-difference for free.
 */

import type { Vec3 } from '../math/vec'

/** Master spring — one per character. Updated each tick. */
export interface SecondarySpring {
  /** Spring point in world space. Lags behind `restTarget` when the
   *  character moves. */
  position: Vec3
  /** Per-frame velocity of the spring point. */
  velocity: Vec3
  /** Stiffness — how fast the spring returns to rest. 12-25 typical
   *  for character-scale (1m). Higher = snappier. */
  stiffness: number
  /** Damping — exponential velocity decay per second. 0.85-0.95
   *  typical. Lower = more bounce. */
  damping: number
  /** Lazy-init: first tickSpring snaps position to the rest target
   *  instead of integrating from (0,0,0). Without this the spring
   *  spends ~1s sliding from world origin to the bone's actual
   *  position — visible as the dangly element flickering up from
   *  the floor at the start of every demo run. */
  initialised: boolean
}

/** Per-secondary configuration. One per dangly thing on the character. */
export interface SecondaryReader {
  /** Bone indices in chain order: root → tip. */
  bones: number[]
  /** Per-bone response magnitude. Length must match `bones`. Usually
   *  ramps from ~0 at the root to ~1 (or beyond) at the tip — a tip
   *  value of 1.5 produces a whip-crack effect. */
  scale: number[]
  /** Per-axis allowed motion. [pitch, yaw, roll] in 0/1. e.g. cape
   *  is [1,0,1] — no twist around its hanging axis. */
  axisMask: Vec3
  /** Hard-cap on rotation magnitude per bone (radians). Keeps cape
   *  from folding into the body, hair from wrapping the head, etc. */
  maxAngleRad: number
  /** Smoothing time constant (1 / lerp coefficient). Higher = lags
   *  more. Hair = 25, cape = 8, heavy robe = 4. Set to 0 to disable
   *  per-reader smoothing (reader uses raw master lag). */
  responsiveness: number
  /** Reader's filtered copy of the master lag vector. Don't set
   *  manually — the tick mutates this. Initial value [0,0,0]. */
  filteredLag: Vec3
}

/**
 * Allocate a fresh master spring at a rest position.
 *
 *   stiffness/damping defaults are tuned for chibi-scale (1m tall)
 *   characters. Larger characters want lower stiffness; tiny mascots
 *   want higher.
 */
export function createSecondarySpring(restPos: Vec3, opts?: {
  stiffness?: number
  damping?: number
}): SecondarySpring {
  return {
    position: [restPos[0], restPos[1], restPos[2]],
    velocity: [0, 0, 0],
    stiffness: opts?.stiffness ?? 18,
    damping:   opts?.damping   ?? 0.90,
    initialised: false,
  }
}

/**
 * Allocate a reader. `scale.length` must equal `bones.length`.
 * Throws on mismatch (caller mistake; better to fail loud).
 */
export function createSecondaryReader(opts: {
  bones: number[]
  scale: number[]
  axisMask?: Vec3
  maxAngleRad?: number
  responsiveness?: number
}): SecondaryReader {
  if (opts.scale.length !== opts.bones.length) {
    throw new Error(`SecondaryReader: scale.length (${opts.scale.length}) must equal bones.length (${opts.bones.length})`)
  }
  return {
    bones: opts.bones.slice(),
    scale: opts.scale.slice(),
    axisMask: opts.axisMask ? [opts.axisMask[0], opts.axisMask[1], opts.axisMask[2]] : [1, 1, 1],
    maxAngleRad: opts.maxAngleRad ?? 0.7,    // ~40°, generous default
    responsiveness: opts.responsiveness ?? 8,
    filteredLag: [0, 0, 0],
  }
}

/**
 * Integrate the master spring one step. Call once per frame, before
 * evaluating readers.
 *
 *   restTarget — usually the character's hip world position. Pass the
 *   updated value each frame (not a stale reference). The spring lags
 *   this; lag = restTarget - position.
 *
 *   dt — frame delta in seconds. Clamp upstream if your engine gives
 *   wild values (>1/30s); spring math destabilises with big dt.
 */
export function tickSpring(spring: SecondarySpring, restTarget: Vec3, dt: number): void {
  // First tick: snap to rest target so the dangly element appears
  // immediately at the bone position instead of accelerating toward it
  // from world origin.
  if (!spring.initialised) {
    spring.position[0] = restTarget[0]
    spring.position[1] = restTarget[1]
    spring.position[2] = restTarget[2]
    spring.velocity[0] = 0
    spring.velocity[1] = 0
    spring.velocity[2] = 0
    spring.initialised = true
    return
  }
  const dtClamped = Math.min(dt, 1 / 30)
  // Damped harmonic oscillator: F = -k * displacement - c * velocity
  // (Verlet-style for stability under chunky dt.)
  const dx = spring.position[0] - restTarget[0]
  const dy = spring.position[1] - restTarget[1]
  const dz = spring.position[2] - restTarget[2]
  const ax = -spring.stiffness * dx
  const ay = -spring.stiffness * dy
  const az = -spring.stiffness * dz
  // Exponential damping: v *= damping^dt
  const dampThisFrame = Math.pow(spring.damping, dtClamped * 60)
  spring.velocity[0] = spring.velocity[0] * dampThisFrame + ax * dtClamped
  spring.velocity[1] = spring.velocity[1] * dampThisFrame + ay * dtClamped
  spring.velocity[2] = spring.velocity[2] * dampThisFrame + az * dtClamped
  spring.position[0] += spring.velocity[0] * dtClamped
  spring.position[1] += spring.velocity[1] * dtClamped
  spring.position[2] += spring.velocity[2] * dtClamped
}

/**
 * Read the master spring's lag vector into a reader's filtered copy.
 * Apply this after `tickSpring`, before using the reader to drive bones.
 *
 *   The lag vector is `restTarget - position` — points from the spring
 *   back toward where it WANTS to be. Effectively the apparent "wind"
 *   the character is generating.
 */
export function tickReader(reader: SecondaryReader, spring: SecondarySpring, restTarget: Vec3, dt: number): void {
  const dtClamped = Math.min(dt, 1 / 30)
  const lagX = restTarget[0] - spring.position[0]
  const lagY = restTarget[1] - spring.position[1]
  const lagZ = restTarget[2] - spring.position[2]
  if (reader.responsiveness <= 0) {
    reader.filteredLag[0] = lagX
    reader.filteredLag[1] = lagY
    reader.filteredLag[2] = lagZ
    return
  }
  // One-pole low-pass: the smaller `responsiveness`, the slower the
  // reader catches up to the master. Different responsiveness per
  // reader gives the perceptual "different mass" feel.
  const k = Math.min(1, reader.responsiveness * dtClamped)
  reader.filteredLag[0] += (lagX - reader.filteredLag[0]) * k
  reader.filteredLag[1] += (lagY - reader.filteredLag[1]) * k
  reader.filteredLag[2] += (lagZ - reader.filteredLag[2]) * k
}

/**
 * Compute the per-bone Euler offset (in radians) that this reader
 * applies to a given bone. Returns [pitchX, yawY, rollZ] suitable for
 * adding to a bone's keyframe rotation before computing its local
 * matrix.
 *
 *   The interpretation: the reader's filtered lag vector — a 3D vector
 *   in world space — gets treated as small Euler angles, scaled by the
 *   per-bone factor, masked by `axisMask`, clamped by `maxAngleRad`.
 *   Cape's typical config (axisMask [1,0,1]) means lag.x drives pitch
 *   (forward swing) and lag.z drives roll (sideways swing); yaw is
 *   killed so the cape can't twist around its hanging axis.
 *
 *   Note: at small lag magnitudes the small-angle approximation
 *   (Euler ≈ axis-angle) is fine. For large lags the clamp kicks in.
 */
export function readerBoneEuler(reader: SecondaryReader, boneIndexInChain: number): Vec3 {
  const s = reader.scale[boneIndexInChain]
  const pitch = clamp(reader.filteredLag[0] * s * reader.axisMask[0], -reader.maxAngleRad, reader.maxAngleRad)
  const yaw   = clamp(reader.filteredLag[1] * s * reader.axisMask[1], -reader.maxAngleRad, reader.maxAngleRad)
  const roll  = clamp(reader.filteredLag[2] * s * reader.axisMask[2], -reader.maxAngleRad, reader.maxAngleRad)
  return [pitch, yaw, roll]
}

function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v
}

/**
 * Default cape config — three-segment chain, root small / tip large
 * scale, [1,0,1] axis mask (forward + sideways, no twist). Pass the
 * three cape bone indices.
 */
export function makeDefaultCapeReader(boneIndices: [number, number, number]): SecondaryReader {
  return createSecondaryReader({
    bones: boneIndices,
    scale: [0.30, 0.65, 1.10],
    axisMask: [1, 0, 1],
    maxAngleRad: 0.9,         // ~52°, generous so a sprint shows real flow
    responsiveness: 6,        // moderate lag — heavier than hair
  })
}

/**
 * Default hair config — three-segment chain, free axes, faster
 * response than cape. For longer hair (more segments) just extend
 * the scale ramp so the tip approaches ~1.2.
 */
export function makeDefaultHairReader(boneIndices: number[]): SecondaryReader {
  const n = boneIndices.length
  // Ramp scale linearly from 0.2 (root) to 1.2 (tip).
  const scale = boneIndices.map((_, i) => 0.2 + (1.0 * i) / Math.max(1, n - 1))
  return createSecondaryReader({
    bones: boneIndices,
    scale,
    axisMask: [1, 0, 1],
    maxAngleRad: 0.6,
    responsiveness: 18,       // light, snappy
  })
}
