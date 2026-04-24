/**
 * Combat × doctrine integration tests.
 *
 * Proves the combat framework ingests sister-instance's pipeline-side
 * doctrines cleanly:
 *   - attack_doctrine: 6-frame attack, hitbox on 3-4, hand-anchor per frame
 *   - damage_doctrine: 1 recoil sprite + 4 engine-effect layers
 *   - Bare-hand + weapon-layer-composition via per-frame attachments
 */

import { describe, it, expect } from 'vitest'
import {
  buildCanonical6FrameAttack, build4FrameQuickAttack, build8FrameHeavyAttack,
  buildHitStunTimeline, CANONICAL_6FRAME_ACTIVE_FRAMES,
  defaultDamageEffect, Element,
  type FrameAttachment, type Canonical6FrameHandTrack,
} from '../src/combat'

// Canonical bare-hand track for a side-view slash (Alucard-tier, 48×80).
// Numbers are sprite-pixel offsets from sprite origin (top-left) to the
// hand position in each of the 6 frames. Authored by hand-tracking pass.
const sideSlashTrack: Canonical6FrameHandTrack = [
  { x: 28, y: 44, angle:   0, depth: 'front' },  // F0 neutral — sword at hip
  { x: 24, y: 42, angle: -20, depth: 'front' },  // F1 anticipation — pulling back
  { x: 18, y: 38, angle: -60, depth: 'back'  },  // F2 wind-up — max coil, behind head
  { x: 34, y: 38, angle:  30, depth: 'front' },  // F3 STRIKE — fastest motion
  { x: 44, y: 44, angle:  90, depth: 'front' },  // F4 impact — full extension
  { x: 36, y: 46, angle:  60, depth: 'front' },  // F5 recovery
]

describe('attack_doctrine integration — 6-frame canonical', () => {
  const timeline = buildCanonical6FrameAttack({
    animation_id: 'slash',
    hitbox_id: 1,
    hurtbox_ids: [1, 2, 3],  // head / torso / legs per SF2 decomposition
    hand_track: sideSlashTrack,
  })

  it('produces exactly 6 frames', () => {
    expect(timeline.frame_count).toBe(6)
    expect(timeline.frames).toHaveLength(6)
  })

  it('hitbox is active ONLY on frames 3-4 (doctrine canonical)', () => {
    const active_frames: number[] = []
    for (let i = 0; i < timeline.frame_count; i++) {
      if ((timeline.frames[i].hitboxes ?? []).length > 0) active_frames.push(i)
    }
    expect(active_frames).toEqual([...CANONICAL_6FRAME_ACTIVE_FRAMES])
    expect(active_frames).toEqual([3, 4])
  })

  it('hurtboxes are ALWAYS present (character stays hittable throughout)', () => {
    for (const frame of timeline.frames) {
      expect(frame.hurtboxes).toEqual([1, 2, 3])
    }
  })

  it('every frame has a hand attachment (bare-hand + weapon-layer pattern)', () => {
    for (const frame of timeline.frames) {
      expect(frame.attachments?.hand).toBeDefined()
    }
  })

  it('hand anchor rotation tracks the swing arc (0° → -60° → +90°)', () => {
    const angles = timeline.frames.map(f => f.attachments!.hand.angle!)
    // F2 is max wind-up (negative), F4 is full extension (max positive)
    expect(angles[2]).toBeLessThan(angles[0])
    expect(angles[4]).toBeGreaterThan(angles[0])
    expect(angles[4]).toBeGreaterThan(angles[3])
  })

  it('depth_layer flips to "back" on wind-up frame 2 (sword behind body)', () => {
    expect(timeline.frames[2].attachments!.hand.depth).toBe('back')
    expect(timeline.frames[0].attachments!.hand.depth).toBe('front')
    expect(timeline.frames[4].attachments!.hand.depth).toBe('front')
  })
})

describe('attack_doctrine — 4-frame quick variant', () => {
  it('quick attack has 4 frames, hitbox on 1-2', () => {
    const t = build4FrameQuickAttack({
      animation_id: 'jab',
      hitbox_id: 1, hurtbox_ids: [1, 2, 3],
      hand_track: sideSlashTrack,
    })
    expect(t.frame_count).toBe(4)
    const active: number[] = []
    for (let i = 0; i < 4; i++) {
      if ((t.frames[i].hitboxes ?? []).length > 0) active.push(i)
    }
    expect(active).toEqual([1, 2])
  })
})

describe('attack_doctrine — 8-frame heavy variant', () => {
  it('heavy attack has 8 frames, hitbox on 4-5', () => {
    const heavyTrack: FrameAttachment[] = Array.from({ length: 8 }, (_, i) => ({
      x: 30 + i * 2, y: 40, angle: i * 10,
    }))
    const t = build8FrameHeavyAttack({
      animation_id: 'heavy_overhead',
      hitbox_id: 1, hurtbox_ids: [1, 2, 3],
      hand_track: sideSlashTrack,
      hand_track_8: heavyTrack as any,
    })
    expect(t.frame_count).toBe(8)
    const active: number[] = []
    for (let i = 0; i < 8; i++) {
      if ((t.frames[i].hitboxes ?? []).length > 0) active.push(i)
    }
    expect(active).toEqual([4, 5])
  })
})

describe('attack_doctrine — weapon-layer composition (bare-hand + anchor)', () => {
  it('one attack timeline serves N weapon instances — doctrine payoff', () => {
    // The whole point of the bare-hand pattern: same hand-track, many weapons.
    // A scaffold registers the slash timeline once, then composites any
    // weapon at the per-frame `hand` anchor.
    const slashTimeline = buildCanonical6FrameAttack({
      animation_id: 'slash',
      hitbox_id: 1, hurtbox_ids: [1, 2, 3],
      hand_track: sideSlashTrack,
    })

    // 4 weapon instances — all use this one timeline
    const weapons = [
      { id: 'wooden_sword', sprite: 'wooden_sword.png', grip_offset: { x: 0, y: 2 } },
      { id: 'master_sword', sprite: 'master_sword.png', grip_offset: { x: 0, y: 2 } },
      { id: 'golden_sword', sprite: 'golden_sword.png', grip_offset: { x: 0, y: 2 } },
      { id: 'dagger',       sprite: 'dagger.png',       grip_offset: { x: 0, y: 1 } },
    ]

    // Renderer composite logic (conceptual): for each frame + each weapon,
    // draw weapon_sprite at (hand_x + grip_offset_x, hand_y + grip_offset_y)
    // rotated by hand_angle, z-order from hand_depth.
    for (const w of weapons) {
      for (const frame of slashTimeline.frames) {
        const hand = frame.attachments!.hand
        const weaponX = hand.x + w.grip_offset.x
        const weaponY = hand.y + w.grip_offset.y
        expect(weaponX).toBeGreaterThanOrEqual(0)
        expect(weaponY).toBeGreaterThanOrEqual(0)
      }
    }
    // The key property: adding a new sword = 1 grip_offset + 1 sprite, zero re-bake.
  })
})

describe('damage_doctrine integration — 1 recoil sprite + engine effects', () => {
  it('hit-stun timeline is 1 frame — no multi-frame sprite animation', () => {
    const t = buildHitStunTimeline('hit_recoil', [1, 2, 3])
    expect(t.frame_count).toBe(1)
    expect(t.frames[0].hurtboxes).toEqual([1, 2, 3])
    expect(t.frames[0].hitboxes).toBeUndefined()  // victim isn't attacking
  })

  it('invuln hit-stun sets hurtboxes to empty (i-frame window)', () => {
    const t = buildHitStunTimeline('hit_recoil', [1, 2, 3], /*invuln*/ true)
    expect(t.frames[0].hurtboxes).toEqual([])
  })

  it('defaultDamageEffect scales shake/flash/screen-shake by damage tier', () => {
    const light = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 8,
      element_mask: Element.CUT, move_id: 'jab', hitstun_frames: 10,
    })
    const heavy = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 45,
      element_mask: Element.CUT, move_id: 'heavy_slash', hitstun_frames: 24,
    })
    expect(heavy.shake_amplitude_px).toBeGreaterThan(light.shake_amplitude_px)
    expect(heavy.screen_shake_amplitude).toBeGreaterThan(light.screen_shake_amplitude)
    expect(heavy.flash_frames).toBeGreaterThan(light.flash_frames)
  })

  it('elemental hit picks elemental particle VFX', () => {
    const fire = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 20,
      element_mask: Element.CUT | Element.FIRE, move_id: 'flame_slash', hitstun_frames: 16,
    })
    expect(fire.particle_vfx_id).toBe('vfx_fire_burst')

    const ice = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 20,
      element_mask: Element.ICE, move_id: 'ice_bolt', hitstun_frames: 16,
    })
    expect(ice.particle_vfx_id).toBe('vfx_ice_shards')

    const plain = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 20,
      element_mask: Element.CUT, move_id: 'basic_slash', hitstun_frames: 16,
    })
    expect(plain.particle_vfx_id).toBe('vfx_slash_spark')  // CUT physical
  })

  it('default flash_kind is white (SNES i-frame canonical)', () => {
    const d = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 15,
      element_mask: Element.CUT, move_id: 'x', hitstun_frames: 12,
    })
    expect(d.flash_kind).toBe('white')
  })

  it('knockback direction honors caller input', () => {
    const rightKb = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 20,
      element_mask: Element.CUT, move_id: 'x', hitstun_frames: 12,
      knockback_direction: 1,
    })
    const leftKb = defaultDamageEffect({
      target_id: 'enemy', source_id: 'player', damage: 20,
      element_mask: Element.CUT, move_id: 'x', hitstun_frames: 12,
      knockback_direction: -1,
    })
    expect(rightKb.knockback_velocity.x).toBeGreaterThan(0)
    expect(leftKb.knockback_velocity.x).toBeLessThan(0)
  })
})
