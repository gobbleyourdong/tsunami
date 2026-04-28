/**
 * Anatomy curve library — bezier-profile primitives that layer additive
 * muscle / fat / shape masses onto the base body. Each curve is a
 * type-17 bezier-profile capsule (see raymarch_renderer.ts) that smin's
 * into a target blend group, fusing with the limb / spine / hip
 * primitives that are already there.
 *
 * The (parent-bone-pair, profile, blend-k) triple per the architecture
 * design: anatomy is JUST a list of (joint triple, radius profile,
 * blend strength) — no special emission code, no separate shader path.
 * Composes with the existing SDF system because everything is already
 * group-blended. "CSG anatomy" — the body builds itself from named
 * sculpt primitives.
 *
 *   Bicep + calf — already in the LIMB's own profile (mixamo_loader's
 *   type-17 emission). They're not separate anatomy curves; the limb
 *   IS the bicep when the profile bulges.
 *
 *   Pec, glute, hip flare, etc. — separate curves because they don't
 *   align with a single bone chain (chest spans Spine2→Shoulder→Arm,
 *   glute spans Hips→UpLeg→Leg). One entry per side for left/right.
 *
 * Design constraint: an anatomy entry references rig joints by NAME so
 * it works on any compatible rig. The emission step resolves names to
 * indices once.
 */

export type AnatomyPaletteSlot = 'skin' | 'shirt' | 'pants'

export interface AnatomyCurve {
  /** Stable identifier — character spec stores per-curve overrides keyed
   *  off this. Convention: lowercase + L/R suffix for paired entries. */
  name: string
  /** Three joint NAMES define the bezier control points: A (curve
   *  start), B (mid / bend control), C (end). Resolution to indices
   *  happens at emit time against the active rig. */
  jointA: string
  jointB: string
  jointC: string
  /** Optional offset applied to joint A's position in A's bone-local
   *  frame. Lets a pec sit forward-of-spine instead of inside it. */
  offsetA?: [number, number, number]
  /** Cubic Bezier of radii along the curve — r0..r3 control points.
   *  Same convention as type-17's profile slot. */
  profile: [number, number, number, number]
  /** Palette slot the surface samples (color routing). Default 'skin'. */
  paletteSlot?: AnatomyPaletteSlot
  /** Smin blend group + radius. Use the limb / torso group of the
   *  underlying body so anatomy fuses into the same surface. */
  blendGroup: number
  blendRadius: number
}

/**
 * DEFAULT_ANATOMY — base humanoid muscle / fat library.
 *
 * Not exhaustive — bicep / calf live in the limb profile, jawline /
 * brow / cheekbone come on later ticks once the head ellipsoid +
 * cone-jaw upgrade is settled. This is what we ship today.
 *
 * Coordinates are in METERS, applied in joint-local frame for offsetA.
 * For Spine2: +Z is face-forward, +Y is up, +X is character-right.
 * For Hips: same convention.
 */
export const DEFAULT_ANATOMY: AnatomyCurve[] = [
  // All body anatomy curves (pecL/R, gluteL/R, hipFlareL/R) retired
  // when the segment-bezier architecture landed (Phase B+D). Their
  // function is now baked into the host segment's cross-section:
  //   - pec → Spine1→Spine2 segment, raZpos > raZneg at chest end
  //   - glute → Hips→Spine segment, raZneg > raZpos at hip end
  //   - hipFlare → upper-leg segment, raX > raZ (next iter — leg
  //     migration to type-18 directional-Z)
  // Face anatomy curves (jawline / brow / cheekbones) retired earlier;
  // sub-pixel at sprite res, replaced by screen-space face stamps.
  // Result: zero secondary smin'd anatomy primitives. Anatomy lives in
  // the segment profile, where it should.
]

/** Anatomy anchor — a virtual joint added to the rig purely as a
 *  POSITIONAL REFERENCE for anatomy curve control points. Anchors emit
 *  no primitive of their own; they exist so face anatomy curves
 *  (jawline / brow / cheekbones) can reference three distinct world
 *  positions even though the head is a single bone.
 *
 *  Demo calls extendRigWithAnchors during VAT init; AnatomyCurve
 *  entries reference anchors by name. Anchor bones inherit their
 *  parent's animated transform so they move with the head naturally. */
export interface AnatomyAnchor {
  name: string
  parentName: string
  offset: [number, number, number]
}

/**
 * Face anchors — fixed positions on the head ellipsoid surface,
 * named for anatomical role. All parented to Head with offsets in
 * Head-local frame:
 *   +X = character right, +Y = up, +Z = face-forward.
 * The head ellipsoid is [0.165, 0.20, 0.17] half-extents; offsets
 * land on or just outside that surface.
 */
export const FACE_ANCHORS: AnatomyAnchor[] = [
  { name: 'Anchor_Chin',    parentName: 'Head', offset: [ 0.00, -0.06,  0.07] },
  { name: 'Anchor_JawL',    parentName: 'Head', offset: [-0.10, -0.04,  0.05] },
  { name: 'Anchor_JawR',    parentName: 'Head', offset: [ 0.10, -0.04,  0.05] },
  { name: 'Anchor_BrowL',   parentName: 'Head', offset: [-0.07,  0.10,  0.13] },
  { name: 'Anchor_BrowMid', parentName: 'Head', offset: [ 0.00,  0.11,  0.14] },
  { name: 'Anchor_BrowR',   parentName: 'Head', offset: [ 0.07,  0.10,  0.13] },
  { name: 'Anchor_CheekL',  parentName: 'Head', offset: [-0.10,  0.04,  0.10] },
  { name: 'Anchor_CheekR',  parentName: 'Head', offset: [ 0.10,  0.04,  0.10] },
]

/** Build preset — a partial { limbs, anatomy } profile bundle keyed by
 *  preset name. Selecting a build at runtime copies these maps into the
 *  demo's `profiles` state and rebuilds. Standard = empty (engine
 *  defaults). Each preset only needs to specify the entries it changes;
 *  unset entries fall back to defaults.
 *
 *  Authoring goal: each preset reads as a recognisable archetype at
 *  sprite resolution — skinny vs strong vs hourglass should be visibly
 *  distinct silhouettes from the same rig + animation. */
export type ProfileTuple = [number, number, number, number]
/** Torso ellipsoid override — per-bone half-extents [hx, hy, hz] for the
 *  Hips / Spine / Spine1 / Spine2 sack-core ellipsoids. Drives the body
 *  silhouette (waist taper, shoulder breadth, hip flare) without touching
 *  limb profiles. Skinny / strong / hourglass differ here, not just at
 *  the limbs. */
export type TorsoShape = [number, number, number]
export interface BuildPreset {
  limbs?:   Record<string, ProfileTuple>
  anatomy?: Record<string, ProfileTuple>
  torso?:   Record<string, TorsoShape>
}
export const BUILD_PRESETS: Record<string, BuildPreset> = {
  // Archetype work is shelved pending a rebuild — body shape needs to
  // be reauthored once the segment-bezier torso lands and we can
  // express muscle/fat/sex characteristics through cross-section
  // profiles rather than ad-hoc ellipsoid resizing. For now every
  // build is a no-op, so the buttons stay in the UI but render the
  // same skinny-column baseline. Reintroduce real archetypes when
  // the body system is ready to differentiate properly.
  standard:  {},
  skinny:    {},
  strong:    {},
  hourglass: {},
}
