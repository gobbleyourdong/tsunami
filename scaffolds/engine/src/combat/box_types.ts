// SF2-style damage-volume system — box-type taxonomy + geometry.
//
// Reference: `scaffolds/.claude/combat/SF2_HITBOX_SYSTEM.md`. The short
// version: SF2 used ORTHOGONAL CHANNELS (separate arrays per box-type)
// rather than one tagged-box list. "Is this also a throwbox?" is not a
// flag on a box — it's a different channel entirely. This keeps the
// collision loop tiny and makes `regular-attack × throw-hurtbox = no
// interaction` a free no-op (different channels never meet).
//
// Lesson from SF2: their ±128 signed-byte offsets were a false economy
// (Dhalsim forced an override-byte hack; HSF2 widened to 16-bit anyway).
// We start at 16-bit integers day one. No float cost at this box-cardinality.

/**
 * Orthogonal collision channels. Each channel is its own array in the
 * resolver — boxes of different channels NEVER collide. The resolver
 * only runs:
 *   attacker.hitbox × defender.hurtbox
 *   attacker.throwbox × defender.throwable
 *   a.pushbox × b.pushbox
 *   projectile.proj_hitbox × defender.hurtbox
 *   attacker.hitbox × projectile.proj_hurtbox  (e.g. parry a fireball)
 */
export enum BoxChannel {
  HURTBOX      = 'hurtbox',       // "can I be hit" — self, tested by opponent's hitbox
  HITBOX       = 'hitbox',        // "I deal damage here" — self, tests opponent's hurtbox
  PUSHBOX      = 'pushbox',       // "keep bodies apart" — mutual, symmetric
  THROWBOX     = 'throwbox',      // "grab reach" — self, tested against opponent's throwable
  THROWABLE    = 'throwable',     // "I can be grabbed here" — set 0 for throw-invulnerable frames
  PROJ_HITBOX  = 'proj_hitbox',   // projectile-entity attack
  PROJ_HURTBOX = 'proj_hurtbox',  // projectile-entity vulnerability (for parry/clash)
}

/**
 * 2D axis-aligned box in owner-local coordinates (x+y offsets relative
 * to the entity's position; width/height are full dimensions, not
 * half-extents — matches SF2 ROM authoring convention).
 *
 * 16-bit signed integers — covers full NTSC screen range even for
 * stretch-limb characters (Dhalsim analog) without an override hack.
 */
export interface Box {
  /** Center x-offset relative to entity position. Signed. */
  readonly x: number
  /** Center y-offset. Y+ = up in engine convention (SF2 used Y+ = down;
   *  we normalize at spec-load time if importing SF2 data). */
  readonly y: number
  /** Full width (NOT half-extent). */
  readonly w: number
  /** Full height. */
  readonly h: number
}

/**
 * A HITBOX carries hit-properties: how much damage, how much stun, what
 * hit-level, whether it knocks down, trade-priority tier. SF2 had no
 * numeric priority field — trades emerged from authoring. We include a
 * tier because modern games (Skullgirls, RoA) found it useful as a
 * tie-breaker when per-frame-authoring isn't feasible. `tier: null` =
 * SF2-strict mode (priority is emergent, no tier-based tie-breaking).
 */
export interface HitProperties {
  readonly damage: number
  readonly hitstun_frames: number
  readonly blockstun_frames: number
  /** 'high' = must stand-block, 'low' = must crouch-block, 'mid' = either,
   *  'overhead' = mid that must stand-block, 'unblockable' = grab-attack. */
  readonly hit_level: 'high' | 'low' | 'mid' | 'overhead' | 'unblockable'
  readonly knockdown: boolean
  readonly launch_velocity?: { x: number; y: number }
  /** Tie-break when hitbox-A and hitbox-B overlap each other's
   *  vulnerability on the same frame. Higher wins. null = SF2-strict
   *  (no tie-break; trade resolves as "both take damage"). */
  readonly tier: number | null
  /** Identify the source of this hit (character + move ID) — used by
   *  the already-connected filter (SF2 inherited this from Final Fight:
   *  "don't rehit the same target on the same move"). */
  readonly move_id: string
}

/**
 * Per-character box palette. Box geometry lives here keyed by an
 * integer ID. Animation frames reference these IDs rather than inline
 * box data. Three wins from this indirection:
 *   1. 90% of idle/walk frames share the same 3-box hurtbox set.
 *   2. Single edit point — tweak one palette entry, every frame using
 *      it updates.
 *   3. Compact serialization: a 60-frame animation carrying 3 hurtbox
 *      IDs + 1 hitbox ID per frame is 240 small integers, not 240
 *      full box structs.
 *
 * Each character has ONE palette covering all their animations + moves.
 */
export interface BoxPalette {
  readonly character_id: string
  readonly hurtboxes:     ReadonlyMap<number, Box>
  readonly hitboxes:      ReadonlyMap<number, Box>
  readonly pushboxes:     ReadonlyMap<number, Box>
  readonly throwboxes:    ReadonlyMap<number, Box>
  readonly throwables:    ReadonlyMap<number, Box>
  readonly proj_hitboxes: ReadonlyMap<number, Box>
  readonly proj_hurtboxes:ReadonlyMap<number, Box>
  /** Hit-property table, keyed by hitbox ID. A hitbox ID can appear on
   *  multiple frames of an animation; the hit-props come from this
   *  table, not inline per-frame. */
  readonly hit_properties: ReadonlyMap<number, HitProperties>
}

/**
 * Per-frame attachment anchors — where weapon/tool/effect sprites
 * composite onto the character's body. Per `memory/attack_doctrine.md`:
 * attack animations are generated BARE-HAND; the weapon is layered at
 * render time using these per-frame anchor points. One attack animation
 * → many weapons, zero re-bake cost.
 *
 * Anchors are in sprite-design-size pixels (see `memory/engine_resolution_doctrine.md`).
 * Matches ALttP's attribute-byte pattern (x/y + depth_layer flag) but
 * exposes named anchors rather than baked-offsets-per-weapon.
 */
export interface FrameAttachment {
  /** Anchor offset from sprite origin (top-left), sprite-design pixels. */
  readonly x: number
  readonly y: number
  /** Optional rotation in degrees, 0 = horizontal reference. */
  readonly angle?: number
  /** Render order relative to body. 'front' = composite on top; 'back' = behind. */
  readonly depth?: 'front' | 'back'
  /** Sentinel — if true, any attachment on this anchor is HIDDEN this
   *  frame (matches ALttP shield-arm-busy convention). Useful for frames
   *  where the hand is occluded. */
  readonly hidden?: boolean
}

/**
 * Per-frame box references — what channels are active this frame and
 * which palette IDs to look up. A channel's absence (undefined) means
 * "no box of that type this frame" (equivalent to ID 0 in SF2's table,
 * which was conventionally the empty box). Multi-box per frame is
 * first-class: hurtboxes is a list so head/torso/legs can be authored
 * as 3 distinct IDs on the same frame.
 *
 * Optional `attachments` map carries named anchor points for
 * bare-hand-plus-weapon-layer composition (see attack_doctrine).
 */
export interface FrameBoxes {
  readonly hurtboxes?:      readonly number[]
  readonly hitboxes?:       readonly number[]
  readonly pushbox?:        number
  readonly throwbox?:       number
  readonly throwable?:      number
  readonly proj_hitboxes?:  readonly number[]
  readonly proj_hurtboxes?: readonly number[]
  /** Named anchor points for weapon/tool/shield compositing.
   *  Canonical names: `hand`, `off_hand`, `head_top`, `back`, `foot_l`, `foot_r`.
   *  Scaffolds may add more. */
  readonly attachments?:    Readonly<Record<string, FrameAttachment>>
}

/**
 * An animation's full box-timeline. One entry per frame; absent frames
 * have no boxes.
 */
export interface BoxTimeline {
  readonly animation_id: string
  readonly frame_count: number
  /** frames[i] is the box-set on frame i. */
  readonly frames: readonly FrameBoxes[]
}

/**
 * Runtime state: which (character, animation, frame) is an entity on
 * right now? Collision resolver reads this + the palette + timeline to
 * compute world-space boxes for this tick.
 */
export interface CombatEntityState {
  readonly entity_id: string
  readonly character_id: string
  readonly animation_id: string
  readonly frame_index: number
  readonly world_position: { x: number; y: number }
  /** Facing direction — +1 = facing right, -1 = facing left. Negates box
   *  x-offsets when -1 so same palette serves both directions. */
  readonly facing: 1 | -1
  /** Health — for damage application. */
  readonly hp: number
  /** Already-connected set — a hitbox that has hit this entity during
   *  the current move can't hit again. Cleared on move-end. */
  readonly already_hit: ReadonlySet<string>
}
