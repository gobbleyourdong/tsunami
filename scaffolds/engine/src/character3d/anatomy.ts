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
  // ── Pec (chest mass) ──────────────────────────────────────────────
  // Curves from sternum (Spine2 + forward offset) through clavicle
  // (Shoulder) to shoulder joint (Arm). The bulged profile sits over
  // the upper-chest area where the pec belly is.
  // Group 6 = torso group; smin's with Spine ellipsoid and the
  // shoulder ball to form a single chest surface.
  {
    name: 'pecL',
    jointA: 'Spine2', jointB: 'LeftShoulder',  jointC: 'LeftArm',
    offsetA: [-0.04, 0.04, 0.08],   // left-of-centre, slight up, forward
    profile: [0.04, 0.10, 0.09, 0.04],
    blendGroup: 6, blendRadius: 0.05,
  },
  {
    name: 'pecR',
    jointA: 'Spine2', jointB: 'RightShoulder', jointC: 'RightArm',
    offsetA: [ 0.04, 0.04, 0.08],
    profile: [0.04, 0.10, 0.09, 0.04],
    blendGroup: 6, blendRadius: 0.05,
  },

  // ── Glute (rear hip mass) ─────────────────────────────────────────
  // Curves from sacrum (Hips + back/down offset) through hip joint
  // (UpLeg) to mid-thigh (Leg). Bulged profile in the middle creates
  // the visible glute shape on the back of the figure.
  // Lives in the LEG group of its side so the glute fuses with the
  // upper leg into one continuous surface (no seam at the hip joint).
  {
    name: 'gluteL',
    jointA: 'Hips', jointB: 'LeftUpLeg',  jointC: 'LeftLeg',
    offsetA: [-0.06, -0.04, -0.06],   // left, slight down, back
    profile: [0.06, 0.095, 0.075, 0.05],
    blendGroup: 4, blendRadius: 0.05,
  },
  {
    name: 'gluteR',
    jointA: 'Hips', jointB: 'RightUpLeg', jointC: 'RightLeg',
    offsetA: [ 0.06, -0.04, -0.06],
    profile: [0.06, 0.095, 0.075, 0.05],
    blendGroup: 5, blendRadius: 0.05,
  },

  // ── Hip flare (lateral hip mass — sex characteristic) ─────────────
  // Curves from outboard-of-Hips (pure +/-X offset) through UpLeg to
  // mid-thigh. Profile is BIGGEST at the start (the flare itself),
  // tapering through the thigh to a narrow knee. This is the
  // hourglass / pear silhouette: wide hips taper to slim knee. Subtle
  // by default — the body's "muscularity / sex" knob in CharacterSpec
  // (next tick) will scale this profile per character.
  // Lives in the per-side leg blend group (4 / 5) so it merges with
  // the leg bezier into one curve from hip outline down to the foot.
  {
    name: 'hipFlareL',
    jointA: 'Hips', jointB: 'LeftUpLeg',  jointC: 'LeftLeg',
    offsetA: [-0.09, 0.00, 0.00],
    profile: [0.10, 0.075, 0.055, 0.05],
    blendGroup: 4, blendRadius: 0.06,
  },
  {
    name: 'hipFlareR',
    jointA: 'Hips', jointB: 'RightUpLeg', jointC: 'RightLeg',
    offsetA: [ 0.09, 0.00, 0.00],
    profile: [0.10, 0.075, 0.055, 0.05],
    blendGroup: 5, blendRadius: 0.06,
  },

  // ── Jawline (chin / jaw curve) ────────────────────────────────────
  // Curves from the left jaw corner across the chin to the right jaw
  // corner. Profile bulges at the chin (control point B). Smin's into
  // the head ellipsoid (group 1) so the chin reads as a continuous
  // jawline rather than a stuck-on bump. Subtle by default — a
  // muscular or "strong jaw" character would profile this fatter.
  {
    name: 'jawline',
    jointA: 'Anchor_JawL', jointB: 'Anchor_Chin', jointC: 'Anchor_JawR',
    profile: [0.025, 0.045, 0.045, 0.025],
    blendGroup: 1, blendRadius: 0.04,
  },

  // ── Brow ridge (forehead horizontal line) ─────────────────────────
  // Curves from left brow across the forehead bridge to right brow.
  // Profile peaks slightly mid-forehead — gives a subtle brow ridge
  // that reads as masculine when emphasised, neutral when small.
  {
    name: 'brow',
    jointA: 'Anchor_BrowL', jointB: 'Anchor_BrowMid', jointC: 'Anchor_BrowR',
    profile: [0.020, 0.035, 0.035, 0.020],
    blendGroup: 1, blendRadius: 0.04,
  },

  // ── Cheekbone L / R (vertical curve down the side of the face) ────
  // From brow ridge through cheekbone apex to jaw corner. Profile
  // bulges at the cheek apex — defines the side-of-face silhouette
  // that distinguishes "high cheekbones" vs "soft jaw" characters.
  {
    name: 'cheekboneL',
    jointA: 'Anchor_BrowL', jointB: 'Anchor_CheekL', jointC: 'Anchor_JawL',
    profile: [0.020, 0.040, 0.040, 0.020],
    blendGroup: 1, blendRadius: 0.04,
  },
  {
    name: 'cheekboneR',
    jointA: 'Anchor_BrowR', jointB: 'Anchor_CheekR', jointC: 'Anchor_JawR',
    profile: [0.020, 0.040, 0.040, 0.020],
    blendGroup: 1, blendRadius: 0.04,
  },
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
export interface BuildPreset {
  limbs?:   Record<string, ProfileTuple>
  anatomy?: Record<string, ProfileTuple>
}
export const BUILD_PRESETS: Record<string, BuildPreset> = {
  // Default character — no overrides. Limbs use the muscular-by-default
  // profile from chibiRaymarchPrimitives, anatomy uses DEFAULT_ANATOMY.
  standard: {},

  // Skinny — narrower limbs, modest pec/glute, smaller hip flare.
  skinny: {
    limbs: {
      LeftArm:    [0.036, 0.046, 0.046, 0.036],
      RightArm:   [0.036, 0.046, 0.046, 0.036],
      LeftUpLeg:  [0.054, 0.068, 0.068, 0.054],
      RightUpLeg: [0.054, 0.068, 0.068, 0.054],
    },
    anatomy: {
      pecL: [0.025, 0.060, 0.050, 0.025],
      pecR: [0.025, 0.060, 0.050, 0.025],
      gluteL: [0.040, 0.060, 0.052, 0.040],
      gluteR: [0.040, 0.060, 0.052, 0.040],
      hipFlareL: [0.072, 0.062, 0.050, 0.045],
      hipFlareR: [0.072, 0.062, 0.050, 0.045],
    },
  },

  // Strong — beefier limbs (bicep + calf bulks), large pec + glute.
  // Hip flare stays modest so the silhouette reads "wide shoulders /
  // narrow waist" rather than "pear-shaped".
  strong: {
    limbs: {
      LeftArm:    [0.054, 0.090, 0.080, 0.044],
      RightArm:   [0.054, 0.090, 0.080, 0.044],
      LeftUpLeg:  [0.082, 0.110, 0.092, 0.062],
      RightUpLeg: [0.082, 0.110, 0.092, 0.062],
    },
    anatomy: {
      pecL: [0.045, 0.130, 0.105, 0.040],
      pecR: [0.045, 0.130, 0.105, 0.040],
      gluteL: [0.065, 0.118, 0.092, 0.054],
      gluteR: [0.065, 0.118, 0.092, 0.054],
      hipFlareL: [0.095, 0.075, 0.058, 0.050],
      hipFlareR: [0.095, 0.075, 0.058, 0.050],
    },
  },

  // Hourglass — slim limbs, full pec, generous glute, BIG hip flare.
  // Classic feminine silhouette: shoulders ≤ hips, narrow waist
  // (implicit via the limb-vs-flare ratio).
  hourglass: {
    limbs: {
      LeftArm:    [0.040, 0.052, 0.050, 0.038],
      RightArm:   [0.040, 0.052, 0.050, 0.038],
      LeftUpLeg:  [0.072, 0.090, 0.080, 0.058],
      RightUpLeg: [0.072, 0.090, 0.080, 0.058],
    },
    anatomy: {
      pecL: [0.040, 0.115, 0.092, 0.038],
      pecR: [0.040, 0.115, 0.092, 0.038],
      gluteL: [0.062, 0.122, 0.094, 0.054],
      gluteR: [0.062, 0.122, 0.094, 0.054],
      hipFlareL: [0.130, 0.088, 0.060, 0.050],
      hipFlareR: [0.130, 0.088, 0.060, 0.050],
    },
  },
}
