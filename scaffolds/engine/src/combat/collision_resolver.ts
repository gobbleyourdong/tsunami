// SF2-style damage-volume collision resolver.
//
// Runs once per tick. For each attacker/defender pair, tests the
// orthogonal channels and emits CollisionEvent records. A system above
// this (damage-applier, pushback-solver, hitstun-setter) consumes the
// events.
//
// KEY DESIGN: channels are orthogonal. The resolver does NOT do
// per-box "what type is this?" — it runs dedicated loops per channel
// pair. This is the single most important SF2 design decision.

import type {
  Box, BoxChannel, BoxPalette, BoxTimeline, CombatEntityState,
  FrameBoxes, HitProperties,
} from './box_types'

/**
 * A world-space box — palette + facing + position already resolved.
 * This is what the overlap test actually reads.
 */
export interface WorldBox {
  readonly owner: string
  readonly channel: BoxChannel
  readonly palette_id: number
  /** World-space AABB: min/max corners. */
  readonly x_min: number
  readonly x_max: number
  readonly y_min: number
  readonly y_max: number
  /** Only populated on HITBOX / PROJ_HITBOX channels — the damage
   *  properties for this box. */
  readonly hit_props?: HitProperties
}

/** Resolve a palette-ID box to world-space given entity position + facing. */
function toWorldBox(
  box: Box, owner: CombatEntityState, channel: BoxChannel,
  palette_id: number, hit_props?: HitProperties,
): WorldBox {
  // Flip x-offset by facing. Width stays positive.
  const flipped_x = owner.facing === 1 ? box.x : -box.x
  const cx = owner.world_position.x + flipped_x
  const cy = owner.world_position.y + box.y
  // Box.w/h are full dimensions (not half-extents).
  const hw = box.w / 2
  const hh = box.h / 2
  return {
    owner: owner.entity_id,
    channel,
    palette_id,
    x_min: cx - hw, x_max: cx + hw,
    y_min: cy - hh, y_max: cy + hh,
    hit_props,
  }
}

/**
 * Compute all world-space boxes for an entity on its current frame, for
 * a single channel. Returns [] if no boxes of that channel this frame.
 *
 * Multi-box per frame (hurtboxes: [head, torso, legs]) is handled here
 * by returning one WorldBox per palette-ID.
 */
export function resolveChannel(
  entity: CombatEntityState, timeline: BoxTimeline, palette: BoxPalette,
  channel: BoxChannel,
): WorldBox[] {
  if (entity.frame_index < 0 || entity.frame_index >= timeline.frame_count) return []
  const frame: FrameBoxes = timeline.frames[entity.frame_index]
  const out: WorldBox[] = []
  const push = (id: number, box: Box, hit?: HitProperties) =>
    out.push(toWorldBox(box, entity, channel, id, hit))

  switch (channel) {
    case 'hurtbox':
      for (const id of frame.hurtboxes ?? []) {
        const b = palette.hurtboxes.get(id); if (b) push(id, b)
      }
      break
    case 'hitbox':
      for (const id of frame.hitboxes ?? []) {
        const b = palette.hitboxes.get(id)
        const hp = palette.hit_properties.get(id)
        if (b) push(id, b, hp)
      }
      break
    case 'pushbox':
      if (frame.pushbox !== undefined) {
        const b = palette.pushboxes.get(frame.pushbox); if (b) push(frame.pushbox, b)
      }
      break
    case 'throwbox':
      if (frame.throwbox !== undefined) {
        const b = palette.throwboxes.get(frame.throwbox); if (b) push(frame.throwbox, b)
      }
      break
    case 'throwable':
      if (frame.throwable !== undefined) {
        const b = palette.throwables.get(frame.throwable); if (b) push(frame.throwable, b)
      }
      break
    case 'proj_hitbox':
      for (const id of frame.proj_hitboxes ?? []) {
        const b = palette.proj_hitboxes.get(id)
        const hp = palette.hit_properties.get(id)
        if (b) push(id, b, hp)
      }
      break
    case 'proj_hurtbox':
      for (const id of frame.proj_hurtboxes ?? []) {
        const b = palette.proj_hurtboxes.get(id); if (b) push(id, b)
      }
      break
  }
  return out
}

/** AABB overlap test. Boxes that share an edge do NOT overlap —
 *  strict inequality matches SF2 behavior. */
export function boxesOverlap(a: WorldBox, b: WorldBox): boolean {
  return a.x_min < b.x_max && a.x_max > b.x_min
      && a.y_min < b.y_max && a.y_max > b.y_min
}

/**
 * A discrete collision event emitted by the resolver. The application
 * layer (damage, hitstun, pushback) consumes these.
 */
export type CollisionEvent =
  | { kind: 'clean_hit'; attacker: string; defender: string; hitbox: WorldBox }
  | { kind: 'trade';     a: string; b: string; a_hits: WorldBox; b_hits: WorldBox }
  | { kind: 'clank';     a: string; b: string; a_box: WorldBox; b_box: WorldBox }
  | { kind: 'push_overlap'; a: string; b: string; overlap_x: number; overlap_y: number }
  | { kind: 'throw';     grabber: string; target: string; throwbox: WorldBox }
  | { kind: 'proj_hit';  projectile: string; defender: string; hitbox: WorldBox }
  | { kind: 'proj_clash'; proj_a: string; proj_b: string }

export interface ResolveInput {
  readonly entities: readonly CombatEntityState[]
  /** Keyed by character_id. */
  readonly palettes: ReadonlyMap<string, BoxPalette>
  /** Keyed by (character_id,animation_id). */
  readonly timelines: ReadonlyMap<string, BoxTimeline>
}

function timelineKey(char_id: string, anim_id: string): string {
  return `${char_id}::${anim_id}`
}

function pushOverlap(a: WorldBox, b: WorldBox): { x: number; y: number } {
  // Positive overlap on each axis.
  const x = Math.min(a.x_max, b.x_max) - Math.max(a.x_min, b.x_min)
  const y = Math.min(a.y_max, b.y_max) - Math.max(a.y_min, b.y_min)
  return { x, y }
}

/**
 * Main resolver. Given all combat entities + palettes + timelines,
 * compute the collision events for this tick.
 *
 * Complexity: O(E^2) across entity pairs × constant channels. Fine for
 * fighting games (E ≤ ~4 players + ~8 projectiles); upgrade to
 * broadphase if an arena-brawler scaffold starts pushing E > 20.
 */
export function resolveCombat(input: ResolveInput): CollisionEvent[] {
  const events: CollisionEvent[] = []
  const ents = input.entities
  // Pre-resolve channels for each entity (cheap: 7 channels × few boxes
  // per channel per frame).
  interface Resolved {
    state: CombatEntityState
    hurt: WorldBox[]; hit: WorldBox[]; push: WorldBox[]
    throwbox: WorldBox[]; throwable: WorldBox[]
    proj_hit: WorldBox[]; proj_hurt: WorldBox[]
  }
  const resolved: Resolved[] = ents.map(state => {
    const palette = input.palettes.get(state.character_id)
    const timeline = input.timelines.get(timelineKey(state.character_id, state.animation_id))
    if (!palette || !timeline) {
      return {
        state,
        hurt: [], hit: [], push: [], throwbox: [], throwable: [],
        proj_hit: [], proj_hurt: [],
      }
    }
    return {
      state,
      hurt:      resolveChannel(state, timeline, palette, 'hurtbox' as BoxChannel),
      hit:       resolveChannel(state, timeline, palette, 'hitbox' as BoxChannel),
      push:      resolveChannel(state, timeline, palette, 'pushbox' as BoxChannel),
      throwbox:  resolveChannel(state, timeline, palette, 'throwbox' as BoxChannel),
      throwable: resolveChannel(state, timeline, palette, 'throwable' as BoxChannel),
      proj_hit:  resolveChannel(state, timeline, palette, 'proj_hitbox' as BoxChannel),
      proj_hurt: resolveChannel(state, timeline, palette, 'proj_hurtbox' as BoxChannel),
    }
  })

  // Pairwise resolve — each ordered pair exactly once for asymmetric
  // channels, each unordered pair exactly once for symmetric.
  for (let i = 0; i < resolved.length; i++) {
    for (let j = i + 1; j < resolved.length; j++) {
      const A = resolved[i], B = resolved[j]
      runCombatantPair(A.state, A.hit, A.hurt, B.state, B.hit, B.hurt, events)
      // Pushboxes are mutual — single direction test.
      runPushbox(A.state, A.push, B.state, B.push, events)
      // Throws — each direction.
      runThrow(A.state, A.throwbox, B.state, B.throwable, events)
      runThrow(B.state, B.throwbox, A.state, A.throwable, events)
      // Projectile-vs-combatant — each direction.
      runProjectile(A.state, A.proj_hit, B.state, B.hurt, events)
      runProjectile(B.state, B.proj_hit, A.state, A.hurt, events)
      // Projectile-swat / parry — combatant hitbox strikes projectile's
      // proj_hurtbox (sword-swat an arrow, parry a Hadouken).
      runProjectileSwat(A.state, A.hit, B.state, B.proj_hurt, events)
      runProjectileSwat(B.state, B.hit, A.state, A.proj_hurt, events)
      // Projectile clash — mutual.
      runProjClash(A.state, A.proj_hit, B.state, B.proj_hit, events)
    }
  }

  return events
}

/**
 * Resolve combatant-vs-combatant. This is where trade/clean/clank
 * semantics live. SF2-strict (no tier tie-break): simultaneous-hit
 * produces a TRADE event (both damaged). Tier tie-break mode uses
 * hit_props.tier to pick a winner.
 */
function runCombatantPair(
  A: CombatEntityState, A_hit: WorldBox[], A_hurt: WorldBox[],
  B: CombatEntityState, B_hit: WorldBox[], B_hurt: WorldBox[],
  out: CollisionEvent[],
): void {
  // Does A's hitbox overlap B's hurtbox?
  let A_hits_B: WorldBox | null = null
  for (const ha of A_hit) {
    // Already-hit filter — don't re-hit on same move-id.
    if (ha.hit_props && B.already_hit.has(ha.hit_props.move_id)) continue
    for (const hb of B_hurt) {
      if (boxesOverlap(ha, hb)) { A_hits_B = ha; break }
    }
    if (A_hits_B) break
  }
  let B_hits_A: WorldBox | null = null
  for (const hb of B_hit) {
    if (hb.hit_props && A.already_hit.has(hb.hit_props.move_id)) continue
    for (const ha of A_hurt) {
      if (boxesOverlap(hb, ha)) { B_hits_A = hb; break }
    }
    if (B_hits_A) break
  }

  // Trade / clean hit / no-contact
  if (A_hits_B && B_hits_A) {
    // Tie-break if both have tiers
    const ta = A_hits_B.hit_props?.tier, tb = B_hits_A.hit_props?.tier
    if (ta != null && tb != null && ta !== tb) {
      if (ta > tb) out.push({ kind: 'clean_hit', attacker: A.entity_id, defender: B.entity_id, hitbox: A_hits_B })
      else        out.push({ kind: 'clean_hit', attacker: B.entity_id, defender: A.entity_id, hitbox: B_hits_A })
    } else {
      // SF2-strict trade
      out.push({ kind: 'trade', a: A.entity_id, b: B.entity_id, a_hits: A_hits_B, b_hits: B_hits_A })
    }
    return
  }
  if (A_hits_B) {
    out.push({ kind: 'clean_hit', attacker: A.entity_id, defender: B.entity_id, hitbox: A_hits_B })
    return
  }
  if (B_hits_A) {
    out.push({ kind: 'clean_hit', attacker: B.entity_id, defender: A.entity_id, hitbox: B_hits_A })
    return
  }

  // Clank — both have hitboxes, neither hits the other's hurtbox, but
  // the hitboxes themselves overlap.
  for (const ha of A_hit) {
    for (const hb of B_hit) {
      if (boxesOverlap(ha, hb)) {
        out.push({ kind: 'clank', a: A.entity_id, b: B.entity_id, a_box: ha, b_box: hb })
        return
      }
    }
  }
}

function runPushbox(
  A: CombatEntityState, A_push: WorldBox[],
  B: CombatEntityState, B_push: WorldBox[],
  out: CollisionEvent[],
): void {
  for (const a of A_push) {
    for (const b of B_push) {
      if (boxesOverlap(a, b)) {
        const ov = pushOverlap(a, b)
        out.push({ kind: 'push_overlap', a: A.entity_id, b: B.entity_id,
                   overlap_x: ov.x, overlap_y: ov.y })
        return
      }
    }
  }
}

function runThrow(
  grabber: CombatEntityState, grabber_throw: WorldBox[],
  target: CombatEntityState, target_throwable: WorldBox[],
  out: CollisionEvent[],
): void {
  for (const g of grabber_throw) {
    for (const t of target_throwable) {
      if (boxesOverlap(g, t)) {
        out.push({ kind: 'throw', grabber: grabber.entity_id,
                   target: target.entity_id, throwbox: g })
        return
      }
    }
  }
}

function runProjectile(
  proj: CombatEntityState, proj_hit: WorldBox[],
  target: CombatEntityState, target_hurt: WorldBox[],
  out: CollisionEvent[],
): void {
  for (const p of proj_hit) {
    if (p.hit_props && target.already_hit.has(p.hit_props.move_id)) continue
    for (const h of target_hurt) {
      if (boxesOverlap(p, h)) {
        out.push({ kind: 'proj_hit', projectile: proj.entity_id,
                   defender: target.entity_id, hitbox: p })
        return
      }
    }
  }
}

function runProjClash(
  A: CombatEntityState, A_hit: WorldBox[],
  B: CombatEntityState, B_hit: WorldBox[],
  out: CollisionEvent[],
): void {
  for (const a of A_hit) {
    for (const b of B_hit) {
      if (boxesOverlap(a, b)) {
        out.push({ kind: 'proj_clash', proj_a: A.entity_id, proj_b: B.entity_id })
        return
      }
    }
  }
}

/**
 * A combatant's hitbox striking a projectile's proj_hurtbox. Sword-swat-
 * an-arrow, parry-a-fireball, Link's shield-reflects-projectile (when
 * equipped with a shield-that-has-an-active-hitbox). Emits a clean_hit
 * on the combatant side; the projectile is the "defender" being
 * destroyed/deflected by a consumer.
 */
function runProjectileSwat(
  attacker: CombatEntityState, attacker_hit: WorldBox[],
  projectile: CombatEntityState, projectile_proj_hurt: WorldBox[],
  out: CollisionEvent[],
): void {
  for (const h of attacker_hit) {
    if (h.hit_props && projectile.already_hit.has(h.hit_props.move_id)) continue
    for (const p of projectile_proj_hurt) {
      if (boxesOverlap(h, p)) {
        out.push({ kind: 'clean_hit', attacker: attacker.entity_id,
                   defender: projectile.entity_id, hitbox: h })
        return
      }
    }
  }
}
