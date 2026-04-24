// SF2-style damage-volume system — public module exports.
//
// Design reference: scaffolds/.claude/combat/SF2_HITBOX_SYSTEM.md
//
// Use pattern:
//   1. Define a BoxPalette per character (hurtboxes, hitboxes, etc. +
//      hit_properties keyed by hitbox ID).
//   2. Define a BoxTimeline per (character, animation) — one FrameBoxes
//      per frame of the anim, listing which palette IDs are active.
//   3. Each tick: collect CombatEntityState per live entity, call
//      resolveCombat({entities, palettes, timelines}) — returns a list
//      of CollisionEvents (clean_hit / trade / clank / push_overlap /
//      throw / proj_hit / proj_clash).
//   4. Hand events to systems above: damage-applier, hitstun-setter,
//      pushback-solver.

export * from './box_types'
export * from './collision_resolver'
export * from './equipment'
export * from './attack_entity'
export * from './weapon_class'
export * from './combat_world'
export * from './damage_resolver'
export * from './attack_canon'
export * from './damage_effects'
