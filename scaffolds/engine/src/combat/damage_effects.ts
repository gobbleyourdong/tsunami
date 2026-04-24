// Damage-visual-effect events — per `memory/damage_doctrine.md`.
//
// Sister-instance codified the damage animation convention:
//   "1 sprite per azimuth (the "recoil" pose). Engine-side effects do the rest."
//
// Four engine-side layers drive the damage feel, NOT multi-frame sprite animation:
//   1. Transform shake — translate 2-4 pixels random, 100ms (2-3 frames @ 60fps)
//   2. Palette flash   — swap to pure white/inverted for 1-2 frames (SNES i-frame convention)
//   3. Impact particles — small VFX sprite overlaid at hit point
//   4. Screen shake (optional) — camera 1-4 px amplitude for damage-scale punch
//
// damage_resolver.ts emits these structured events; the scaffold's
// renderer + VFX system consume them. Keeps sprite budget tight and
// gives designers live-tunable damage feel without re-baking.

export interface DamageEffectSpec {
  /** The hit target. */
  readonly target_id: string
  /** Who dealt the damage — for directional effects (knockback angle). */
  readonly source_id: string
  /** Final damage dealt (post-resistance). 0 for pure-whiff / blocked. */
  readonly damage: number
  /** Original element mask — renderer may tint particles by element
   *  (fire = orange sparks, ice = blue shards, curse = purple smoke). */
  readonly element_mask: number

  // ─── Layer 1: Transform shake ───
  /** Pixel amplitude for sprite shake. 2-4 for light, 5-8 for heavy. */
  readonly shake_amplitude_px: number
  /** Duration in frames (60fps). 2-3 light, 4-6 heavy. */
  readonly shake_frames: number

  // ─── Layer 2: Palette flash ───
  /** Kind of flash — controls the target's palette override. */
  readonly flash_kind: 'none' | 'white' | 'invert' | 'elemental_tint'
  /** Flash frames (60fps). 1-2 for standard i-frame convention. */
  readonly flash_frames: number

  // ─── Layer 3: Impact particles ───
  /** VFX sprite ID the scaffold's particle system spawns at hit position.
   *  null = no particles this hit (rare; almost always present). */
  readonly particle_vfx_id: string | null
  /** Pixel offset from target center for the particle spawn origin.
   *  Typically the weapon's contact point, not target center. */
  readonly particle_origin: { x: number; y: number }

  // ─── Layer 4: Screen shake (optional) ───
  /** Camera shake amplitude. 0 = no screen shake. 1-4 for damage scaling. */
  readonly screen_shake_amplitude: number
  /** Screen shake duration. */
  readonly screen_shake_frames: number

  // ─── Derived engine behaviors ───
  /** Recoil pose to swap the target to for hitstun duration. Scaffold
   *  chooses per-character; framework doesn't care about its identity,
   *  just passes through. */
  readonly recoil_animation_id: string
  /** Knockback impulse — engine translates the target per-frame over
   *  the stun window. */
  readonly knockback_velocity: { x: number; y: number }
  /** Total hitstun frames (target can't input for this long). */
  readonly hitstun_frames: number
  /** Damage-resolver's move_id so the consumer can log/audit. */
  readonly move_id: string
}

/**
 * Default damage-effect spec builder — scaffolds override fields as
 * needed but the defaults follow the doctrine's "SNES i-frame" baseline.
 *
 * Reads the hit's damage magnitude to scale shake / flash intensity:
 *   light hit  (≤ 10 dmg): 2px shake, 1-frame flash, no screen shake
 *   medium hit (11-30):    3px shake, 2-frame flash, 1px screen shake
 *   heavy hit  (> 30):     5px shake, 3-frame flash, 3px screen shake
 */
export function defaultDamageEffect(opts: {
  target_id: string
  source_id: string
  damage: number
  element_mask: number
  move_id: string
  hitstun_frames: number
  recoil_animation_id?: string
  particle_origin?: { x: number; y: number }
  knockback_direction?: 1 | -1
  knockback_magnitude?: number
}): DamageEffectSpec {
  const dmg = opts.damage
  const tier = dmg <= 10 ? 'light' : dmg <= 30 ? 'medium' : 'heavy'

  const shake_px = tier === 'light' ? 2 : tier === 'medium' ? 3 : 5
  const shake_f  = tier === 'light' ? 2 : tier === 'medium' ? 3 : 4
  const flash_f  = tier === 'light' ? 1 : tier === 'medium' ? 2 : 3
  const scr_px   = tier === 'light' ? 0 : tier === 'medium' ? 1 : 3
  const scr_f    = tier === 'light' ? 0 : tier === 'medium' ? 2 : 4

  const dir = opts.knockback_direction ?? 1
  const mag = opts.knockback_magnitude ?? (dmg * 0.3)

  return {
    target_id: opts.target_id,
    source_id: opts.source_id,
    damage: dmg,
    element_mask: opts.element_mask,
    shake_amplitude_px: shake_px,
    shake_frames: shake_f,
    flash_kind: 'white',            // SNES canonical
    flash_frames: flash_f,
    particle_vfx_id: elementToParticleVfx(opts.element_mask),
    particle_origin: opts.particle_origin ?? { x: 0, y: 0 },
    screen_shake_amplitude: scr_px,
    screen_shake_frames: scr_f,
    recoil_animation_id: opts.recoil_animation_id ?? 'hit_recoil',
    knockback_velocity: { x: dir * mag, y: 0 },
    hitstun_frames: opts.hitstun_frames,
    move_id: opts.move_id,
  }
}

/**
 * Pick a particle-VFX id based on element mask. Scaffolds declare the
 * VFX assets; this maps element to asset name convention.
 */
function elementToParticleVfx(element_mask: number): string | null {
  // Check in priority order; elemental bits dominate over physical
  // for visual flavor.
  if (element_mask & (1 << 4))  return 'vfx_fire_burst'
  if (element_mask & (1 << 5))  return 'vfx_ice_shards'
  if (element_mask & (1 << 6))  return 'vfx_thunder_arc'
  if (element_mask & (1 << 7))  return 'vfx_holy_glow'
  if (element_mask & (1 << 8))  return 'vfx_dark_smoke'
  if (element_mask & (1 << 9))  return 'vfx_curse_swirl'
  if (element_mask & (1 << 10)) return 'vfx_poison_cloud'
  if (element_mask & (1 << 11)) return 'vfx_water_splash'
  if (element_mask & (1 << 0))  return 'vfx_slash_spark'       // CUT
  if (element_mask & (1 << 1))  return 'vfx_strike_impact'     // STRIKE
  if (element_mask & (1 << 2))  return 'vfx_pierce_burst'      // PIERCE
  if (element_mask & (1 << 3))  return 'vfx_explosion'         // EXPLOSIVE
  return 'vfx_neutral_hit'
}
