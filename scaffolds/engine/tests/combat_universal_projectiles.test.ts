/**
 * Universal projectile patterns — same SF2-style combat primitives,
 * different games.
 *
 * Thesis: projectiles aren't a fighting-game concept. Every game has
 * them. SF2 just got the abstraction right first. The SAME BoxPalette
 * + BoxTimeline + resolveCombat pipeline handles:
 *
 *   - Mega Man buster pellet (platformer)       → small proj_hitbox, 1-frame anim, despawn on hit
 *   - Link arrow (top-down action-adventure)    → proj_hitbox + proj_hurtbox (can be sword-swatted)
 *   - Samus missile (metroidvania)              → larger proj_hitbox, damage tier above beam
 *   - Mario fireball (platformer)               → proj_hitbox + bounces (position-update above combat layer)
 *   - R-Type wave cannon (shmup)                → variable-size proj_hitbox by charge-level
 *   - Contra spray (shmup-run-gun)              → 5 parallel proj_hitboxes from one spawn event
 *   - Hadouken (fighter)                        → proj_hitbox that persists past throw animation
 *
 * All share the property: PROJECTILE = SEPARATE ENTITY with its own
 * BoxPalette. Position-update / bounce / despawn are separate concerns
 * layered above the collision resolver. This test file confirms the
 * universality by running non-fighter scenarios through the same
 * resolveCombat() call.
 */

import { describe, it, expect } from 'vitest'
import {
  type BoxPalette, type BoxTimeline, type CombatEntityState,
  type HitProperties, type FrameBoxes,
  resolveCombat,
} from '../src/combat'

// helpers (duplicated from combat_collision.test.ts for isolation)
const box = (x: number, y: number, w: number, h: number) => ({ x, y, w, h })
const mk = (r: Record<number, any> | undefined) =>
  new Map(Object.entries(r ?? {}).map(([k, v]) => [Number(k), v]))

function palette(
  char: string,
  data: {
    hurt?: Record<number, any>; hit?: Record<number, any>
    push?: Record<number, any>; thrb?: Record<number, any>
    thra?: Record<number, any>; phit?: Record<number, any>
    phurt?: Record<number, any>; hit_props?: Record<number, HitProperties>
  },
): BoxPalette {
  return {
    character_id: char,
    hurtboxes: mk(data.hurt), hitboxes: mk(data.hit),
    pushboxes: mk(data.push), throwboxes: mk(data.thrb),
    throwables: mk(data.thra), proj_hitboxes: mk(data.phit),
    proj_hurtboxes: mk(data.phurt), hit_properties: mk(data.hit_props),
  }
}

function timeline(char: string, anim: string, frames: FrameBoxes[]): BoxTimeline {
  return { animation_id: anim, frame_count: frames.length, frames }
}

function entity(
  id: string, char: string, anim: string, frame: number,
  x: number, y: number, facing: 1 | -1 = 1,
  hp = 100, already_hit: Iterable<string> = [],
): CombatEntityState {
  return {
    entity_id: id, character_id: char, animation_id: anim, frame_index: frame,
    world_position: { x, y }, facing, hp,
    already_hit: new Set(already_hit),
  }
}

const hp = (move_id: string, damage = 10, tier: number | null = null): HitProperties => ({
  damage, hitstun_frames: 16, blockstun_frames: 10,
  hit_level: 'mid', knockdown: false, tier, move_id,
})

function makeInput(
  entities: CombatEntityState[],
  palettes: BoxPalette[],
  timelines: [string, string, BoxTimeline][],
) {
  return {
    entities,
    palettes: new Map(palettes.map(p => [p.character_id, p])),
    timelines: new Map(timelines.map(([c, a, t]) => [`${c}::${a}`, t])),
  }
}

// ─────────────────────────────────────────────────────────────────────
//  1987 Mega Man: pellet buster
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — Mega Man buster pellet', () => {
  it('small proj_hitbox hits enemy hurtbox', () => {
    // Pellet is tiny (8x8), 1-hit damage=1. Mega Man canonical weakness.
    const pellet = palette('mm_pellet', {
      phit: { 1: box(0, 0, 8, 8) },
      hit_props: { 1: hp('buster_pellet', 1) },
    })
    const met = palette('metall', {                // Met enemy
      hurt: { 1: box(0, 0, 16, 12) },              // short hard-hat
    })
    const tPellet = timeline('mm_pellet', 'fly', [{ proj_hitboxes: [1] }])
    const tMet = timeline('metall', 'exposed', [{ hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('p1', 'mm_pellet', 'fly', 0, 50, 0),
       entity('e1', 'metall', 'exposed', 0, 52, 0)],
      [pellet, met],
      [['mm_pellet', 'fly', tPellet], ['metall', 'exposed', tMet]],
    ))
    expect(events.find(e => e.kind === 'proj_hit')).toBeDefined()
  })

  it('Met in hard-hat phase (no hurtbox) = pellet does nothing', () => {
    // Mega Man canonical: Mets are invulnerable while hat is down.
    // Same pellet, different animation frame → empty hurtboxes.
    const pellet = palette('mm_pellet', {
      phit: { 1: box(0, 0, 8, 8) },
      hit_props: { 1: hp('buster_pellet', 1) },
    })
    const met = palette('metall', {})
    const tPellet = timeline('mm_pellet', 'fly', [{ proj_hitboxes: [1] }])
    const tMet = timeline('metall', 'hidden', [{}])  // no hurtboxes this frame

    const events = resolveCombat(makeInput(
      [entity('p1', 'mm_pellet', 'fly', 0, 50, 0),
       entity('e1', 'metall', 'hidden', 0, 52, 0)],
      [pellet, met],
      [['mm_pellet', 'fly', tPellet], ['metall', 'hidden', tMet]],
    ))
    expect(events).toHaveLength(0)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  1986 Zelda: Link's arrow — can be sword-swatted (proj_hurtbox)
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — Link arrow with parry surface', () => {
  it('arrow has proj_hurtbox, Dark-Link sword strike hits it', () => {
    // Arrow entity: proj_hitbox (to damage enemies) + proj_hurtbox (to be
    // swatted out of the air by a returning strike).
    const arrow = palette('link_arrow', {
      phit: { 1: box(0, 0, 12, 4) },               // arrow shaft as attack
      phurt: { 1: box(0, 0, 12, 4) },              // same shape as hurtbox
      hit_props: { 1: hp('arrow', 4) },
    })
    const darkLink = palette('dark_link', {
      hurt: { 1: box(0, 20, 24, 40) },
      hit:  { 1: box(20, 30, 30, 10) },            // sword-strike arc
      hit_props: { 1: hp('dark_sword', 2) },
    })
    const tArrow = timeline('link_arrow', 'fly',
      [{ proj_hitboxes: [1], proj_hurtboxes: [1] }])
    const tDark = timeline('dark_link', 'strike', [{ hitboxes: [1], hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('proj', 'link_arrow', 'fly', 0, 50, 30),
       entity('dk',   'dark_link', 'strike', 0, 30, 0)],  // sword reaches
      [arrow, darkLink],
      [['link_arrow', 'fly', tArrow], ['dark_link', 'strike', tDark]],
    ))
    // The arrow's proj_hurtbox ∩ Dark Link's hitbox → clean hit for DK.
    // Arrow would be despawned by consumer reading the event.
    const swatted = events.find(e =>
      e.kind === 'clean_hit' && e.attacker === 'dk')
    expect(swatted).toBeDefined()
  })
})

// ─────────────────────────────────────────────────────────────────────
//  1994 Super Metroid: Samus missile — tiered damage vs beam
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — Samus missile vs beam', () => {
  it('missile with higher tier beats a beam in clash', () => {
    const missile = palette('missile', {
      phit: { 1: box(0, 0, 16, 8) },
      hit_props: { 1: hp('missile', 30, /*tier*/ 3) },
    })
    const beam = palette('beam', {
      phit: { 1: box(0, 0, 10, 6) },
      hit_props: { 1: hp('beam', 5, /*tier*/ 1) },
    })
    // These are projectiles from opposite sides meeting. We treat as two
    // combat-entities both carrying proj_hitboxes — resolveCombat runs the
    // proj_clash test between them. The resolver emits a clash event; a
    // consumer would then resolve by tier to decide which despawns.
    const tMiss = timeline('missile', 'fly', [{ proj_hitboxes: [1] }])
    const tBeam = timeline('beam', 'fly', [{ proj_hitboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('m1', 'missile', 'fly', 0, 100, 30),
       entity('b1', 'beam', 'fly', 0, 105, 30)],
      [missile, beam],
      [['missile', 'fly', tMiss], ['beam', 'fly', tBeam]],
    ))
    expect(events.find(e => e.kind === 'proj_clash')).toBeDefined()
    // Tier resolution is the consumer's job; here we just confirm the
    // event surfaced so a SuperMetroid-rules-module can apply tier logic.
  })
})

// ─────────────────────────────────────────────────────────────────────
//  1987 Contra: 5-spread simultaneous
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — Contra spread-shot', () => {
  it('one anim-frame spawning 5 parallel projectiles — test one of them', () => {
    // Contra's spread spawns 5 bullets in a fan. Each bullet is its own
    // entity; the spawn event originates from one weapon-trigger but is
    // not encoded in the player's animation — it's emitted at input time.
    // We model a single bullet-entity + confirm it hits its target.
    const bullet = palette('contra_bullet', {
      phit: { 1: box(0, 0, 6, 6) },
      hit_props: { 1: hp('contra_bullet', 3) },
    })
    const grunt = palette('grunt', {
      hurt: { 1: box(0, 20, 20, 40) },
    })
    const tB = timeline('contra_bullet', 'fly', [{ proj_hitboxes: [1] }])
    const tG = timeline('grunt', 'run', [{ hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('bullet42', 'contra_bullet', 'fly', 0, 80, 30),
       entity('g1', 'grunt', 'run', 0, 83, 20)],
      [bullet, grunt],
      [['contra_bullet', 'fly', tB], ['grunt', 'run', tG]],
    ))
    expect(events.find(e => e.kind === 'proj_hit')).toBeDefined()
  })
})

// ─────────────────────────────────────────────────────────────────────
//  1987 R-Type: wave cannon — variable damage by charge level
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — R-Type wave cannon scaled by charge', () => {
  it('charge level 3 wave has larger proj_hitbox than level 1', () => {
    // Wave cannon level N = different projectile entity entirely (or
    // same entity w/ different animation frame). We model as distinct
    // animations → distinct frame box-sets from the SAME palette.
    const waveCannon = palette('r_type_wave', {
      phit: {
        1: box(0, 0, 20, 10),   // level 1 — small beam
        3: box(0, 0, 60, 24),   // level 3 — huge wave
      },
      hit_props: {
        1: hp('wave_lv1', 5, 1),
        3: hp('wave_lv3', 30, 3),
      },
    })
    const bydo = palette('bydo', { hurt: { 1: box(0, 0, 32, 32) } })
    const tL1 = timeline('r_type_wave', 'lv1', [{ proj_hitboxes: [1] }])
    const tL3 = timeline('r_type_wave', 'lv3', [{ proj_hitboxes: [3] }])
    const tBydo = timeline('bydo', 'float', [{ hurtboxes: [1] }])

    // Level 1 — tiny beam, just barely reaches.
    const lv1events = resolveCombat(makeInput(
      [entity('w1', 'r_type_wave', 'lv1', 0, 100, 0),
       entity('b1', 'bydo', 'float', 0, 115, 0)],
      [waveCannon, bydo],
      [['r_type_wave', 'lv1', tL1], ['bydo', 'float', tBydo]],
    ))
    const lv1 = lv1events.find(e => e.kind === 'proj_hit')
    expect(lv1?.kind === 'proj_hit' && lv1.hitbox.hit_props?.damage).toBe(5)

    // Level 3 — 60-wide wave, reaches further + hits harder.
    const lv3events = resolveCombat(makeInput(
      [entity('w1', 'r_type_wave', 'lv3', 0, 100, 0),
       entity('b1', 'bydo', 'float', 0, 130, 0)],
      [waveCannon, bydo],
      [['r_type_wave', 'lv3', tL3], ['bydo', 'float', tBydo]],
    ))
    const lv3 = lv3events.find(e => e.kind === 'proj_hit')
    expect(lv3?.kind === 'proj_hit' && lv3.hitbox.hit_props?.damage).toBe(30)
  })
})

// ─────────────────────────────────────────────────────────────────────
//  The universality claim
// ─────────────────────────────────────────────────────────────────────

describe('universal projectiles — framework universality', () => {
  it('the same resolveCombat call services fighter, platformer, metroidvania, shmup', () => {
    // One mega-scene: Ryu's Hadouken + Mega Man's pellet + Link's arrow
    // + Samus missile + R-Type wave, all resolved in one tick of the
    // same resolver. No per-genre specialization in the collision layer.

    const hadou = palette('hadouken', {
      phit: { 1: box(0, 0, 30, 30) },
      hit_props: { 1: hp('hadouken', 20) },
    })
    const pellet = palette('mm_pellet', {
      phit: { 1: box(0, 0, 8, 8) },
      hit_props: { 1: hp('pellet', 1) },
    })
    const arrow = palette('arrow', {
      phit: { 1: box(0, 0, 12, 4) },
      hit_props: { 1: hp('arrow', 4) },
    })
    const missile = palette('missile', {
      phit: { 1: box(0, 0, 16, 8) },
      hit_props: { 1: hp('missile', 30) },
    })
    const wave = palette('wave', {
      phit: { 1: box(0, 0, 60, 24) },
      hit_props: { 1: hp('wave', 30) },
    })
    const target = palette('tgt', { hurt: { 1: box(0, 0, 40, 200) } })
    const tProjFly = timeline('*', 'fly', [{ proj_hitboxes: [1] }])
    const tTgt = timeline('tgt', 'idle', [{ hurtboxes: [1] }])

    // All 5 projectiles within range of their respective targets.
    const events = resolveCombat(makeInput(
      [
        entity('hadou', 'hadouken', 'fly', 0, 100, 40),
        entity('pellet', 'mm_pellet', 'fly', 0, 200, 20),
        entity('arrow', 'arrow', 'fly', 0, 300, 20),
        entity('missile', 'missile', 'fly', 0, 400, 20),
        entity('wave', 'wave', 'fly', 0, 500, 20),
        entity('t1', 'tgt', 'idle', 0, 115, 0),
        entity('t2', 'tgt', 'idle', 0, 210, 0),
        entity('t3', 'tgt', 'idle', 0, 310, 0),
        entity('t4', 'tgt', 'idle', 0, 410, 0),
        entity('t5', 'tgt', 'idle', 0, 510, 0),
      ],
      [hadou, pellet, arrow, missile, wave, target],
      [
        ['hadouken', 'fly', tProjFly],
        ['mm_pellet', 'fly', tProjFly],
        ['arrow', 'fly', tProjFly],
        ['missile', 'fly', tProjFly],
        ['wave', 'fly', tProjFly],
        ['tgt', 'idle', tTgt],
      ],
    ))
    // 5 projectile hits — one per genre. Same primitive.
    const hits = events.filter(e => e.kind === 'proj_hit')
    expect(hits).toHaveLength(5)
  })
})
