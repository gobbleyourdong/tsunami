/**
 * VFX lifetime manager — spawn/animate/despawn raymarch primitives over
 * time. Each VFX instance carries a spawn time and a duration; update()
 * prunes expired ones; getPrimitives() projects the live list to the
 * RaymarchPrimitive shape the renderer consumes, with per-type animators
 * driving params from age.
 *
 * This is the bridge between gameplay events ("player swung a sword") and
 * the render layer. Gameplay code calls spawnSwipe / spawnTrail / etc.;
 * the render layer pulls getPrimitives(now) each frame.
 *
 * Animator conventions:
 *   - t = age / duration, clamped [0, 1]
 *   - Intro/hold/outro shape encoded per-type below
 *   - Despawn is implicit once age > duration; no gradient cleanup needed
 *     because raymarch primitives are pure (no GPU state to tear down)
 */

import type { RaymarchPrimitive } from './raymarch_renderer'

export type VFXKind = 'swipe' | 'trail' | 'muzzleFlash' | 'impactStar' | 'orbitGlow' | 'lightning' | 'beam'

export interface VFXInstance {
  kind: VFXKind
  spawnTime: number
  duration: number
  boneIdx: number
  offsetInBone: [number, number, number]
  /** Primary palette slot. Most VFX use gradientY (slotA → slotA+1 → slotB) so
   *  pair it with a paletteSlotB for the ramp target. */
  paletteSlot: number
  paletteSlotB?: number
  /** Scale multiplier on the primitive's default params — so a big slash
   *  trail and a small one share one animator with a size knob. */
  size?: number
}

export class VFXSystem {
  private instances: VFXInstance[] = []

  /** Sword swipe arc — intersecting oblate spheroids sweeping 0 → π over
   *  the duration. Default 250ms lifetime reads as a crisp impact frame. */
  spawnSwipe(now: number, boneIdx: number, offset: [number, number, number],
             paletteA: number, paletteB: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'swipe',
      spawnTime: now,
      duration: opts.duration ?? 0.25,
      boneIdx, offsetInBone: offset,
      paletteSlot: paletteA, paletteSlotB: paletteB,
      size: opts.size ?? 1,
    })
  }

  /** Slash trail — the r = A·sin(ω·θ)·exp(-k·θ) ribbon. Amp decays over
   *  lifetime. Typically spawned adjacent to swipe for layered read. */
  spawnTrail(now: number, boneIdx: number, offset: [number, number, number],
             paletteSlot: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'trail',
      spawnTime: now,
      duration: opts.duration ?? 0.55,
      boneIdx, offsetInBone: offset,
      paletteSlot, size: opts.size ?? 1,
    })
  }

  /** Muzzle flash — quick radial pulse. 120ms lifetime. Cone shape via a
   *  capsule whose radius decays fast. */
  spawnMuzzleFlash(now: number, boneIdx: number, offset: [number, number, number],
                   paletteA: number, paletteB: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'muzzleFlash',
      spawnTime: now,
      duration: opts.duration ?? 0.12,
      boneIdx, offsetInBone: offset,
      paletteSlot: paletteA, paletteSlotB: paletteB,
      size: opts.size ?? 1,
    })
  }

  /** Impact star — brief expanding sphere. Spawn at hit location. */
  spawnImpactStar(now: number, boneIdx: number, offset: [number, number, number],
                  paletteSlot: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'impactStar',
      spawnTime: now,
      duration: opts.duration ?? 0.20,
      boneIdx, offsetInBone: offset,
      paletteSlot, size: opts.size ?? 1,
    })
  }

  /** Lightning bolt — crackling zigzag line emanating along bone +Y.
   *  Short life (~150ms) reads as a flash. Long-life variants could
   *  persist as a sustained channeled spell. */
  spawnLightning(now: number, boneIdx: number, offset: [number, number, number],
                 paletteA: number, paletteB: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'lightning',
      spawnTime: now,
      duration: opts.duration ?? 0.15,
      boneIdx, offsetInBone: offset,
      paletteSlot: paletteA, paletteSlotB: paletteB,
      size: opts.size ?? 1,
    })
  }

  /** Beam — cylinder along bone +Y with grow-in / hold / fade-out
   *  envelope. Default 800ms. Good for charged shots, laser sweeps. */
  spawnBeam(now: number, boneIdx: number, offset: [number, number, number],
            paletteA: number, paletteB: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'beam',
      spawnTime: now,
      duration: opts.duration ?? 0.80,
      boneIdx, offsetInBone: offset,
      paletteSlot: paletteA, paletteSlotB: paletteB,
      size: opts.size ?? 1,
    })
  }

  /** Glowing orb at a socket — pulsating, longer-lived (e.g. for held
   *  magic or charged-attack indicator). Caller sets duration for persist. */
  spawnOrbitGlow(now: number, boneIdx: number, offset: [number, number, number],
                 paletteA: number, paletteB: number, opts: { duration?: number; size?: number } = {}) {
    this.instances.push({
      kind: 'orbitGlow',
      spawnTime: now,
      duration: opts.duration ?? 2.0,
      boneIdx, offsetInBone: offset,
      paletteSlot: paletteA, paletteSlotB: paletteB,
      size: opts.size ?? 1,
    })
  }

  /** Prune expired VFX. Call once per frame before getPrimitives. */
  update(now: number) {
    this.instances = this.instances.filter((v) => now - v.spawnTime < v.duration)
  }

  /** Current active primitives ready to hand to raymarch.setPrimitives(). */
  getPrimitives(now: number): RaymarchPrimitive[] {
    const out: RaymarchPrimitive[] = []
    for (const v of this.instances) {
      const prim = this.instanceToPrim(v, now)
      if (prim) out.push(prim)
    }
    return out
  }

  count(): number { return this.instances.length }

  clear() { this.instances = [] }

  private instanceToPrim(v: VFXInstance, now: number): RaymarchPrimitive | null {
    const age = Math.max(0, now - v.spawnTime)
    const t = Math.min(1, age / v.duration)      // 0 spawn → 1 despawn
    const size = v.size ?? 1

    switch (v.kind) {
      case 'swipe': {
        // SwipeArc (type 8): params = [majorR, halfThick, arcRad, innerRatio].
        // Sweep arc from 0 to π over lifetime; keep fixed ring thickness.
        return {
          type: 8, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [0.30 * size, 0.02 * size, Math.PI * t, 0.78],
          offsetInBone: v.offsetInBone,
          colorFunc: 1,                            // gradientY ramp
          paletteSlotB: v.paletteSlotB ?? v.paletteSlot,
          colorExtent: 0.30 * size,
        }
      }
      case 'trail': {
        // LogPolarSineTrail (type 9): params = [amp, freq, decay, thick].
        // Amp decays with age so trail fades out spatially.
        const ampDecay = 1 - t
        return {
          type: 9, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [0.12 * size * ampDecay, 6.0, 1.4, 0.008 * size],
          offsetInBone: v.offsetInBone,
        }
      }
      case 'muzzleFlash': {
        // Capsule (type 5): params = [radius, halfLength]. Fast radial grow
        // then collapse — humps at t=0.3 for a sharp snap.
        const hump = Math.sin(t * Math.PI)        // 0→1→0
        return {
          type: 5, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [0.03 * size * hump, 0.06 * size * (1 + hump), 0, 0],
          offsetInBone: v.offsetInBone,
          colorFunc: 1,                            // yellow core → orange edge
          paletteSlotB: v.paletteSlotB ?? v.paletteSlot,
          colorExtent: 0.10 * size,
        }
      }
      case 'impactStar': {
        // Sphere (type 0) that rapidly grows then disappears. Size hump
        // early; fade via duration cutoff.
        const r = 0.08 * size * Math.sin(t * Math.PI * 0.7)   // grow for 70% of life
        if (r <= 0) return null
        return {
          type: 0, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [r, 0, 0, 0],
          offsetInBone: v.offsetInBone,
        }
      }
      case 'lightning': {
        // Lightning (type 10): params = [halfLen, amplitude, thickness].
        // Hold full intensity through life, brief fade on outro.
        const fade = t > 0.7 ? (1 - (t - 0.7) / 0.3) : 1
        return {
          type: 10, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [0.40 * size, 0.015 * size * fade, 0.008 * size * fade, 0],
          offsetInBone: [v.offsetInBone[0], v.offsetInBone[1] + 0.40 * size, v.offsetInBone[2]],
          colorFunc: 1,                            // gradient tip-to-base
          paletteSlotB: v.paletteSlotB ?? v.paletteSlot,
          colorExtent: 0.40 * size,
        }
      }
      case 'beam': {
        // Cylinder (type 4): params = [radius, halfHeight].
        // Grow-in for first 20% of life, hold, fade-out in last 20%.
        const growIn = Math.min(1, t * 5)
        const fadeOut = t > 0.8 ? (1 - (t - 0.8) / 0.2) : 1
        const half = 0.50 * size * growIn
        const thick = 0.025 * size * fadeOut
        return {
          type: 4, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [thick, half, 0, 0],
          // Offset puts the beam's base at the socket and extends out +Y.
          offsetInBone: [v.offsetInBone[0], v.offsetInBone[1] + half, v.offsetInBone[2]],
          colorFunc: 1,                            // fade along length
          paletteSlotB: v.paletteSlotB ?? v.paletteSlot,
          colorExtent: half,
        }
      }
      case 'orbitGlow': {
        // Sphere pulsating via sin(age). Long lived. Uses pulsate colorFunc
        // so it alternates between slotA and slotB at a frequency.
        const pulse = 0.05 + 0.01 * Math.sin(age * 8)
        return {
          type: 0, paletteSlot: v.paletteSlot, boneIdx: v.boneIdx,
          params: [pulse * size, 0, 0, 0],
          offsetInBone: v.offsetInBone,
          colorFunc: 2,                            // pulsate
          paletteSlotB: v.paletteSlotB ?? v.paletteSlot,
          colorExtent: 2.5,                        // 2.5 Hz pulse
        }
      }
    }
  }
}
