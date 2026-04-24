/**
 * Combat collision resolver — SF2-style damage-volume tests.
 *
 * Scenarios taken from the SF2 research brief:
 *   - Clean hit: attacker hitbox ∩ defender hurtbox, no reciprocal.
 *   - Trade: both hit simultaneously (SF2-strict = no tie-break).
 *   - Tier tie-break: when tier differs, higher wins (non-SF2-strict mode).
 *   - Clank: both hitboxes overlap, neither touches the other's hurtbox.
 *   - Disjoint hitbox: jab-DP-style attack with no hurtbox on the limb
 *     — attacker cannot be counter-hit even though hitbox is extended.
 *   - Pushbox: two bodies walking into each other.
 *   - Throw: grabber's throwbox ∩ target's throwable.
 *   - Throw-invulnerable post-wakeup: target's throwable id = undefined
 *     on these frames.
 *   - Projectile: fireball entity hits defender.
 *   - Projectile clash: two fireballs meet.
 *   - Already-hit filter: same move-id can't rehit.
 *   - Facing flip: negative-facing entity negates x-offsets correctly.
 */

import { describe, it, expect } from 'vitest'
import {
  type BoxPalette, type BoxTimeline, type CombatEntityState,
  type HitProperties, type FrameBoxes,
  resolveCombat, boxesOverlap, resolveChannel,
} from '../src/combat'

// ─────────────────────────────────────────────────────────────────────
//  helpers
// ─────────────────────────────────────────────────────────────────────

const box = (x: number, y: number, w: number, h: number) =>
  ({ x, y, w, h })

function palette(
  char: string,
  data: {
    hurt?: Record<number, { x: number; y: number; w: number; h: number }>
    hit?: Record<number, { x: number; y: number; w: number; h: number }>
    push?: Record<number, { x: number; y: number; w: number; h: number }>
    thrb?: Record<number, { x: number; y: number; w: number; h: number }>
    thra?: Record<number, { x: number; y: number; w: number; h: number }>
    phit?: Record<number, { x: number; y: number; w: number; h: number }>
    phurt?: Record<number, { x: number; y: number; w: number; h: number }>
    hit_props?: Record<number, HitProperties>
  },
): BoxPalette {
  const mk = (r: Record<number, any> | undefined) =>
    new Map(Object.entries(r ?? {}).map(([k, v]) => [Number(k), v]))
  return {
    character_id: char,
    hurtboxes:      mk(data.hurt),
    hitboxes:       mk(data.hit),
    pushboxes:      mk(data.push),
    throwboxes:     mk(data.thrb),
    throwables:     mk(data.thra),
    proj_hitboxes:  mk(data.phit),
    proj_hurtboxes: mk(data.phurt),
    hit_properties: mk(data.hit_props),
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

function hitProp(move_id: string, damage = 10, tier: number | null = null): HitProperties {
  return {
    damage, hitstun_frames: 16, blockstun_frames: 10,
    hit_level: 'mid', knockdown: false, tier, move_id,
  }
}

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
//  scenarios
// ─────────────────────────────────────────────────────────────────────

describe('combat — box overlap primitive', () => {
  it('boxes sharing edges do NOT overlap (strict inequality)', () => {
    const a = { owner: 'a', channel: 'hitbox' as const, palette_id: 1,
                x_min: 0, x_max: 10, y_min: 0, y_max: 10 }
    const b = { owner: 'b', channel: 'hurtbox' as const, palette_id: 1,
                x_min: 10, x_max: 20, y_min: 0, y_max: 10 }
    expect(boxesOverlap(a, b)).toBe(false)
  })

  it('boxes sharing an overlap of 1 pixel DO overlap', () => {
    const a = { owner: 'a', channel: 'hitbox' as const, palette_id: 1,
                x_min: 0, x_max: 10, y_min: 0, y_max: 10 }
    const b = { owner: 'b', channel: 'hurtbox' as const, palette_id: 1,
                x_min: 9, x_max: 20, y_min: 0, y_max: 10 }
    expect(boxesOverlap(a, b)).toBe(true)
  })
})

describe('combat — clean hit (Ryu cl.HP vs standing Ken)', () => {
  it('attacker hitbox ∩ defender hurtbox with no reciprocal = clean_hit', () => {
    const ryu = palette('ryu', {
      hurt: { 1: box(0, 40, 40, 80) },
      hit:  { 1: box(30, 50, 30, 20) },           // arm extends to the right
      hit_props: { 1: hitProp('ryu_clHP', 16) },
    })
    const ken = palette('ken', {
      hurt: { 1: box(0, 40, 40, 80) },             // standing
    })
    const tRyu = timeline('ryu', 'clHP', [{ hitboxes: [1], hurtboxes: [1] }])
    const tKen = timeline('ken', 'idle', [{ hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [
        entity('p1', 'ryu', 'clHP', 0, 0, 0),
        entity('p2', 'ken', 'idle', 0, 45, 0),     // just-in-range
      ],
      [ryu, ken],
      [['ryu', 'clHP', tRyu], ['ken', 'idle', tKen]],
    ))
    expect(events).toHaveLength(1)
    expect(events[0].kind).toBe('clean_hit')
    if (events[0].kind === 'clean_hit') {
      expect(events[0].attacker).toBe('p1')
      expect(events[0].defender).toBe('p2')
      expect(events[0].hitbox.hit_props?.damage).toBe(16)
    }
  })
})

describe('combat — trade (simultaneous mutual clean-hit)', () => {
  it('SF2-strict: both clean hits → trade event (no tier-break)', () => {
    const ryu = palette('ryu', {
      hurt: { 1: box(0, 40, 40, 80) },
      hit:  { 1: box(30, 50, 30, 20) },
      hit_props: { 1: hitProp('ryu_clHP', 16) },
    })
    const ken = palette('ken', {
      hurt: { 1: box(0, 40, 40, 80) },
      hit:  { 1: box(-30, 50, 30, 20) },           // arm extends to the left
      hit_props: { 1: hitProp('ken_clHP', 14) },
    })
    const tRyu = timeline('ryu', 'a', [{ hitboxes: [1], hurtboxes: [1] }])
    const tKen = timeline('ken', 'a', [{ hitboxes: [1], hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [
        entity('p1', 'ryu', 'a', 0, 0, 0),
        // Ken is facing left — hitbox extends to -x, which in world = left.
        entity('p2', 'ken', 'a', 0, 55, 0, 1),
      ],
      [ryu, ken],
      [['ryu', 'a', tRyu], ['ken', 'a', tKen]],
    ))
    expect(events).toHaveLength(1)
    expect(events[0].kind).toBe('trade')
  })

  it('tier tie-break mode: higher tier wins', () => {
    const ryu = palette('ryu', {
      hurt: { 1: box(0, 40, 40, 80) },
      hit:  { 1: box(30, 50, 30, 20) },
      hit_props: { 1: hitProp('ryu_sHK', 20, /*tier*/ 3) },  // heavy kick priority
    })
    const ken = palette('ken', {
      hurt: { 1: box(0, 40, 40, 80) },
      hit:  { 1: box(-30, 50, 30, 20) },
      hit_props: { 1: hitProp('ken_lp', 8, /*tier*/ 1) },    // jab priority
    })
    const tRyu = timeline('ryu', 'a', [{ hitboxes: [1], hurtboxes: [1] }])
    const tKen = timeline('ken', 'a', [{ hitboxes: [1], hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('p1', 'ryu', 'a', 0, 0, 0),
       entity('p2', 'ken', 'a', 0, 55, 0, 1)],
      [ryu, ken],
      [['ryu', 'a', tRyu], ['ken', 'a', tKen]],
    ))
    expect(events).toHaveLength(1)
    expect(events[0].kind).toBe('clean_hit')
    if (events[0].kind === 'clean_hit') expect(events[0].attacker).toBe('p1')
  })
})

describe('combat — disjoint hitbox (jab-DP-style invulnerability)', () => {
  it('hitbox extends with NO hurtbox on the arm → attacker uncounterable there', () => {
    // Ryu jab-DP ascending frames: arm is unhittable from the shoulder up.
    // Authored as: hurtbox covers torso/legs only; hitbox extends above.
    const ryu = palette('ryu', {
      hurt: { 1: box(0, 30, 40, 60) },             // torso/legs only
      hit:  { 1: box(0, 100, 40, 40) },            // extends above shoulder
      hit_props: { 1: hitProp('ryu_jabDP', 12) },
    })
    const ken = palette('ken', {
      hurt: { 1: box(0, 30, 40, 60) },
      hit:  { 1: box(30, 100, 50, 20) },           // trying to hit Ryu's shoulder
      hit_props: { 1: hitProp('ken_jHK', 14) },
    })
    const tRyu = timeline('ryu', 'dp', [{ hitboxes: [1], hurtboxes: [1] }])
    const tKen = timeline('ken', 'jhk', [{ hitboxes: [1], hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [
        entity('p1', 'ryu', 'dp', 0, 0, 0),
        entity('p2', 'ken', 'jhk', 0, 50, 0),
      ],
      [ryu, ken],
      [['ryu', 'dp', tRyu], ['ken', 'jhk', tKen]],
    ))
    // Ryu's hitbox (y=100, 40×40) should hit Ken's hurtbox (y=30, 40×60)
    // only if vertical overlap exists. Y80..120 vs Y0..60 = no overlap.
    // Ken's hitbox (at Ryu position offset -50 then -30 = out of range).
    // Result: nothing hits. This is the disjoint-invuln demonstration:
    // Ryu's arm is ABOVE Ken's highest hurtbox.
    // Note: this is spatially authored — the system itself does nothing
    // special, which is the SF2 insight — disjoint invuln is emergent.
    expect(events.filter(e => e.kind === 'clean_hit' || e.kind === 'trade'))
      .toHaveLength(0)
  })
})

describe('combat — pushbox (two bodies walking into each other)', () => {
  it('overlapping pushboxes emit push_overlap with separation delta', () => {
    const ryu = palette('ryu', { push: { 1: box(0, 40, 30, 80) } })
    const ken = palette('ken', { push: { 1: box(0, 40, 30, 80) } })
    const t = timeline('*', 'idle', [{ pushbox: 1 }])
    const events = resolveCombat(makeInput(
      [entity('p1', 'ryu', 'idle', 0, 0, 0),
       entity('p2', 'ken', 'idle', 0, 20, 0)],    // 10-unit overlap
      [ryu, ken],
      [['ryu', 'idle', t], ['ken', 'idle', t]],
    ))
    const pe = events.find(e => e.kind === 'push_overlap')
    expect(pe).toBeDefined()
    if (pe?.kind === 'push_overlap') {
      expect(pe.overlap_x).toBeGreaterThan(0)
      expect(pe.overlap_x).toBeLessThanOrEqual(10)
    }
  })
})

describe('combat — throw (Zangief SPD range)', () => {
  it('grabber throwbox ∩ target throwable emits throw event', () => {
    const zangief = palette('zangief', {
      thrb: { 1: box(25, 40, 60, 80) },            // huge throwbox
    })
    const ken = palette('ken', {
      thra: { 1: box(0, 40, 30, 80) },
    })
    const tZ = timeline('zangief', 'spd', [{ throwbox: 1 }])
    const tK = timeline('ken', 'idle', [{ throwable: 1 }])

    const events = resolveCombat(makeInput(
      [entity('p1', 'zangief', 'spd', 0, 0, 0),
       entity('p2', 'ken', 'idle', 0, 50, 0)],
      [zangief, ken],
      [['zangief', 'spd', tZ], ['ken', 'idle', tK]],
    ))
    const te = events.find(e => e.kind === 'throw')
    expect(te).toBeDefined()
    if (te?.kind === 'throw') {
      expect(te.grabber).toBe('p1')
      expect(te.target).toBe('p2')
    }
  })

  it('throwable = undefined (post-wakeup invuln) prevents throw', () => {
    const zangief = palette('zangief', { thrb: { 1: box(25, 40, 60, 80) } })
    const ken = palette('ken', { thra: { 1: box(0, 40, 30, 80) } })
    const tZ = timeline('zangief', 'spd', [{ throwbox: 1 }])
    // Ken's wakeup frame has NO throwable — 13 frames of throw-invuln.
    const tKwake = timeline('ken', 'wakeup', [{}])

    const events = resolveCombat(makeInput(
      [entity('p1', 'zangief', 'spd', 0, 0, 0),
       entity('p2', 'ken', 'wakeup', 0, 50, 0)],
      [zangief, ken],
      [['zangief', 'spd', tZ], ['ken', 'wakeup', tKwake]],
    ))
    expect(events.find(e => e.kind === 'throw')).toBeUndefined()
  })
})

describe('combat — projectile (Hadouken)', () => {
  it('projectile with its own hitbox can hit a distant defender', () => {
    // Fireball lives as a separate entity with proj_hitbox set.
    const fireball = palette('hadouken', {
      phit: { 1: box(0, 40, 30, 30) },
      hit_props: { 1: hitProp('hadouken', 20) },
    })
    const ken = palette('ken', { hurt: { 1: box(0, 40, 40, 80) } })
    const tF = timeline('hadouken', 'fly', [{ proj_hitboxes: [1] }])
    const tK = timeline('ken', 'idle', [{ hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('proj1', 'hadouken', 'fly', 0, 100, 0),
       entity('p2', 'ken', 'idle', 0, 115, 0)],
      [fireball, ken],
      [['hadouken', 'fly', tF], ['ken', 'idle', tK]],
    ))
    const pe = events.find(e => e.kind === 'proj_hit')
    expect(pe).toBeDefined()
    if (pe?.kind === 'proj_hit') {
      expect(pe.projectile).toBe('proj1')
      expect(pe.defender).toBe('p2')
    }
  })

  it('two opposing projectiles mid-air cause proj_clash', () => {
    const hadou = palette('hadouken', {
      phit: { 1: box(0, 40, 30, 30) },
      hit_props: { 1: hitProp('hadouken', 20) },
    })
    const fireball = palette('fireball', {
      phit: { 1: box(0, 40, 30, 30) },
      hit_props: { 1: hitProp('fireball', 20) },
    })
    const t1 = timeline('hadouken', 'fly', [{ proj_hitboxes: [1] }])
    const t2 = timeline('fireball', 'fly', [{ proj_hitboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('proj1', 'hadouken', 'fly', 0, 100, 0),
       entity('proj2', 'fireball', 'fly', 0, 110, 0)],
      [hadou, fireball],
      [['hadouken', 'fly', t1], ['fireball', 'fly', t2]],
    ))
    expect(events.find(e => e.kind === 'proj_clash')).toBeDefined()
  })
})

describe('combat — already-hit filter', () => {
  it('same move_id cannot hit the same defender twice on the same move', () => {
    const ryu = palette('ryu', {
      hit: { 1: box(30, 40, 40, 40) },
      hit_props: { 1: hitProp('ryu_sweep', 12) },
    })
    const ken = palette('ken', { hurt: { 1: box(0, 40, 40, 80) } })
    const tRyu = timeline('ryu', 'sweep', [{ hitboxes: [1] }])
    const tKen = timeline('ken', 'idle', [{ hurtboxes: [1] }])

    const events = resolveCombat(makeInput(
      [entity('p1', 'ryu', 'sweep', 0, 0, 0),
       entity('p2', 'ken', 'idle', 0, 40, 0, 1, 100, ['ryu_sweep'])],
      [ryu, ken],
      [['ryu', 'sweep', tRyu], ['ken', 'idle', tKen]],
    ))
    expect(events.find(e => e.kind === 'clean_hit')).toBeUndefined()
  })
})

describe('combat — facing flip', () => {
  it('facing -1 negates x-offset so same palette serves both directions', () => {
    const ryu = palette('ryu', {
      hit: { 1: box(30, 40, 40, 40) },  // +x offset in palette
      hit_props: { 1: hitProp('ryu_sweep', 12) },
    })
    const ken = palette('ken', { hurt: { 1: box(0, 40, 40, 80) } })
    const tRyu = timeline('ryu', 'sweep', [{ hitboxes: [1] }])
    const tKen = timeline('ken', 'idle', [{ hurtboxes: [1] }])

    // Ryu at x=100, facing LEFT. Hitbox should land at x ≈ 100 - 30 = 70.
    // Ken at x=70 → hit should register.
    const events = resolveCombat(makeInput(
      [entity('p1', 'ryu', 'sweep', 0, 100, 0, -1),
       entity('p2', 'ken', 'idle', 0, 70, 0)],
      [ryu, ken],
      [['ryu', 'sweep', tRyu], ['ken', 'idle', tKen]],
    ))
    expect(events.find(e => e.kind === 'clean_hit')).toBeDefined()
  })
})

describe('combat — multi-box per frame (head/torso/legs)', () => {
  it('hurtboxes[head, torso, legs] all participate in collision test', () => {
    const ken = palette('ken', {
      hurt: {
        1: box(0, 100, 30, 25),  // head
        2: box(0, 60, 35, 40),   // torso
        3: box(0, 20, 30, 40),   // legs
      },
    })
    const ryu = palette('ryu', {
      hit: { 1: box(30, 100, 30, 20) },  // aimed at head only
      hit_props: { 1: hitProp('ryu_jHP', 18) },
    })
    const tRyu = timeline('ryu', 'jhp', [{ hitboxes: [1] }])
    const tKen = timeline('ken', 'idle', [{ hurtboxes: [1, 2, 3] }])

    const events = resolveCombat(makeInput(
      [entity('p1', 'ryu', 'jhp', 0, 0, 0),
       entity('p2', 'ken', 'idle', 0, 35, 0)],
      [ryu, ken],
      [['ryu', 'jhp', tRyu], ['ken', 'idle', tKen]],
    ))
    expect(events.find(e => e.kind === 'clean_hit')).toBeDefined()
  })
})

describe('combat — channel resolver smoke', () => {
  it('resolveChannel returns empty for frames out of range', () => {
    const pal = palette('ryu', { hurt: { 1: box(0, 40, 40, 80) } })
    const tl = timeline('ryu', 'idle', [{ hurtboxes: [1] }])
    const ent = entity('p1', 'ryu', 'idle', 999, 0, 0)  // bogus frame
    expect(resolveChannel(ent, tl, pal, 'hurtbox' as any)).toEqual([])
  })

  it('resolveChannel returns empty for channel absent on frame', () => {
    const pal = palette('ryu', { hurt: { 1: box(0, 40, 40, 80) } })
    const tl = timeline('ryu', 'idle', [{ hurtboxes: [1] }])   // no hitbox
    const ent = entity('p1', 'ryu', 'idle', 0, 0, 0)
    expect(resolveChannel(ent, tl, pal, 'hitbox' as any)).toEqual([])
  })
})
