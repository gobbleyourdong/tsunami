// Canonical attack-animation patterns — per `memory/attack_doctrine.md`.
//
// Sister-instance codified the framework's canonical attack animation
// convention on 2026-04-22:
//
//   6 frames per attack: 0=neutral, 1=anticipation, 2=wind-up, 3=STRIKE,
//                        4=impact, 5=follow-through/recovery.
//   Hitbox ACTIVE only on frames 3-4 (33ms window at 60fps).
//   Sprite is BARE-HAND; weapon composites via per-frame `hand` anchor.
//
// This module provides factory helpers to build BoxTimelines that
// conform to the doctrine, so scaffolds don't re-derive the frame
// assignments each time.

import type { BoxTimeline, FrameAttachment, FrameBoxes } from './box_types'

/**
 * Per-frame hand anchor for a canonical 6-frame attack. Authored by
 * running hand-tracking on the bare-hand sprite chain (classical CV
 * pass, see attack_doctrine §pipeline-steps). Order matches the 6
 * canonical frames.
 */
export type Canonical6FrameHandTrack = readonly [
  FrameAttachment, FrameAttachment, FrameAttachment,
  FrameAttachment, FrameAttachment, FrameAttachment,
]

export interface CanonicalAttackConfig {
  /** Timeline animation-id label (e.g. 'slash' or 'thrust'). */
  readonly animation_id: string
  /** Palette ID for the single hitbox that this attack publishes on
   *  frames 3-4. Scaffold-author picks the box geometry in the palette. */
  readonly hitbox_id: number
  /** Hurtbox IDs that publish on EVERY frame (character stays hittable
   *  throughout). Typically [head, torso, legs]. */
  readonly hurtbox_ids: readonly number[]
  /** Per-frame hand-anchor track from the hand-tracking pass. */
  readonly hand_track: Canonical6FrameHandTrack
  /** Optional pushbox ID present on all frames. */
  readonly pushbox_id?: number
}

/**
 * Build a doctrine-compliant 6-frame attack BoxTimeline.
 *
 * Frame assignments:
 *   F0 neutral        — hurtboxes only, hand anchor for weapon-at-rest
 *   F1 anticipation   — hurtboxes + hand pulling back
 *   F2 wind-up        — hurtboxes + hand at max compression
 *   F3 STRIKE         — hurtboxes + HITBOX + hand at fastest motion
 *   F4 impact         — hurtboxes + HITBOX + hand at extension
 *   F5 recovery       — hurtboxes + hand returning
 */
export function buildCanonical6FrameAttack(cfg: CanonicalAttackConfig): BoxTimeline {
  const mkFrame = (frame_idx: number, with_hitbox: boolean): FrameBoxes => ({
    hurtboxes: cfg.hurtbox_ids,
    ...(with_hitbox ? { hitboxes: [cfg.hitbox_id] } : {}),
    ...(cfg.pushbox_id !== undefined ? { pushbox: cfg.pushbox_id } : {}),
    attachments: { hand: cfg.hand_track[frame_idx] },
  })

  const frames: FrameBoxes[] = [
    mkFrame(0, false),  // neutral
    mkFrame(1, false),  // anticipation
    mkFrame(2, false),  // wind-up
    mkFrame(3, true),   // STRIKE — hitbox active
    mkFrame(4, true),   // impact — hitbox active
    mkFrame(5, false),  // recovery
  ]
  return { animation_id: cfg.animation_id, frame_count: 6, frames }
}

/**
 * Tight 4-frame variant per attack_doctrine § "quick attacks can drop
 * to 4 frames (skip anticipation + recovery)". Wind-up → strike → impact
 * → brief recovery. Hitbox active on frames 1-2.
 */
export function build4FrameQuickAttack(cfg: CanonicalAttackConfig): BoxTimeline {
  const mkFrame = (frame_idx: number, with_hitbox: boolean): FrameBoxes => ({
    hurtboxes: cfg.hurtbox_ids,
    ...(with_hitbox ? { hitboxes: [cfg.hitbox_id] } : {}),
    ...(cfg.pushbox_id !== undefined ? { pushbox: cfg.pushbox_id } : {}),
    attachments: { hand: cfg.hand_track[Math.min(frame_idx + 1, 5)] },
  })
  const frames: FrameBoxes[] = [
    mkFrame(0, false),  // wind-up
    mkFrame(1, true),   // STRIKE
    mkFrame(2, true),   // impact
    mkFrame(3, false),  // recovery
  ]
  return { animation_id: cfg.animation_id, frame_count: 4, frames }
}

/**
 * Heavy attack variant per attack_doctrine § "heavy attacks may use
 * 8–10 frames (slower wind-up, bigger recovery)". Hitbox on frames 4-5.
 * 8-frame spec:
 *   F0 neutral, F1 anticipation, F2-3 long wind-up, F4 STRIKE, F5 impact,
 *   F6-7 big recovery.
 */
export function build8FrameHeavyAttack(cfg: CanonicalAttackConfig & {
  /** Heavy attacks need 8 frames of hand-track. Extra slots for the
   *  extended wind-up + recovery. */
  readonly hand_track_8: readonly [
    FrameAttachment, FrameAttachment, FrameAttachment, FrameAttachment,
    FrameAttachment, FrameAttachment, FrameAttachment, FrameAttachment,
  ]
}): BoxTimeline {
  const mkFrame = (frame_idx: number, with_hitbox: boolean): FrameBoxes => ({
    hurtboxes: cfg.hurtbox_ids,
    ...(with_hitbox ? { hitboxes: [cfg.hitbox_id] } : {}),
    ...(cfg.pushbox_id !== undefined ? { pushbox: cfg.pushbox_id } : {}),
    attachments: { hand: cfg.hand_track_8[frame_idx] },
  })
  const frames: FrameBoxes[] = [
    mkFrame(0, false),  // neutral
    mkFrame(1, false),  // anticipation
    mkFrame(2, false),  // wind-up start
    mkFrame(3, false),  // wind-up peak
    mkFrame(4, true),   // STRIKE
    mkFrame(5, true),   // impact
    mkFrame(6, false),  // recovery begin
    mkFrame(7, false),  // recovery end
  ]
  return { animation_id: cfg.animation_id, frame_count: 8, frames }
}

/**
 * Per the doctrine, "1 sprite per azimuth (the "recoil" pose). Engine-side
 * effects do the rest." A hit-stun BoxTimeline is a single frame held
 * until the invincibility window ends. Carries no hitbox (the victim
 * isn't attacking) but keeps the hurtbox present unless the scaffold
 * wants invincibility frames.
 */
export function buildHitStunTimeline(
  animation_id: string,
  hurtbox_ids: readonly number[],
  invuln: boolean = false,
): BoxTimeline {
  const frame: FrameBoxes = {
    hurtboxes: invuln ? [] : hurtbox_ids,
  }
  return { animation_id, frame_count: 1, frames: [frame] }
}

/**
 * Hitbox-active frames for a canonical 6-frame attack. Exported so
 * scaffolds / tests can assert canonical compliance.
 */
export const CANONICAL_6FRAME_ACTIVE_FRAMES: readonly number[] = [3, 4]

/**
 * Default attack lock duration matching attack_doctrine's 6-frame spec:
 * at 60fps, 6 frames = 100ms. Scaffold may override per weapon-class.
 */
export const DEFAULT_ATTACK_LOCK_FRAMES = 6
