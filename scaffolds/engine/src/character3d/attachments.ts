/**
 * Hand + foot attachments — meshes that plug into the limb's terminal
 * joint. The body's limb beziers terminate at the wrist / ankle (an
 * implicit point); attachments fill in the visible flesh / armor at
 * those points. Default = skin-colored sphere on each hand bone, skin-
 * colored wedge on each foot bone. Replacements: knight gauntlet,
 * cartoon mitt, reptile claw, plate boot, etc. — each is a different
 * AttachmentPart bound to the same joint.
 *
 * Architecturally these are tiny, named single-prim definitions parallel
 * to AnatomyCurve. They're emitted alongside the body, not blended INTO
 * the body except by smin (so a gauntlet on top of skin reads as armor
 * over skin, not as merged geometry).
 *
 * The module is intentionally minimal today — DEFAULT_HANDS only. Future
 * ticks add DEFAULT_FEET + named libraries (HAND_LIBRARY, FOOT_LIBRARY)
 * and wire wardrobe outfits to override the default with their own
 * gauntlet / boot entries.
 */

export interface AttachmentPart {
  /** Stable identifier — character spec / wardrobe references this by
   *  name. Convention: lowercase + L/R suffix for paired entries. */
  name: string
  /** Rig joint NAME the primitive attaches to. */
  jointName: string
  /** Primitive type (matches raymarch_renderer's type IDs). 0 = sphere,
   *  2 = roundedBox, 3 = ellipsoid, etc. */
  type: number
  /** Type-specific params (4 floats). */
  params: [number, number, number, number]
  /** Translation offset in joint-local frame. */
  offsetInBone: [number, number, number]
  /** Optional rotation quat (x, y, z, w). Identity if absent. */
  rotation?: [number, number, number, number]
  /** Palette slot lookup key — resolved against material.namedSlots
   *  at emit time. Defaults to 'skin' for raw-flesh defaults. */
  paletteSlot?: 'skin' | 'shirt' | 'pants' | 'shoes' | 'armor' | 'leather' | 'cloth'
  /** Smin blend group + radius. Default group = matches the limb the
   *  joint belongs to (arm group for Hand, leg group for Foot). */
  blendGroup?: number
  blendRadius?: number
}

/**
 * DEFAULT_HANDS — left + right skin spheres on the wrist bones. The
 * arm bezier tapers to a point at the wrist; this fist sits at the
 * end and smin's into the limb (blend group 2 / 3).
 *
 * Radius 0.055 = slightly thicker than the wrist taper (~0.04 from
 * the limb profile) so the wrist reads as a distinct joint between
 * forearm and fist.
 */
export const DEFAULT_HANDS: AttachmentPart[] = [
  {
    name: 'hand_skin_L',
    jointName: 'LeftHand',
    type: 0,
    params: [0.055, 0, 0, 0],
    offsetInBone: [0, 0.055 * 0.4, 0],
    paletteSlot: 'skin',
    blendGroup: 2, blendRadius: 0.04,
  },
  {
    name: 'hand_skin_R',
    jointName: 'RightHand',
    type: 0,
    params: [0.055, 0, 0, 0],
    offsetInBone: [0, 0.055 * 0.4, 0],
    paletteSlot: 'skin',
    blendGroup: 3, blendRadius: 0.04,
  },
]

/**
 * DEFAULT_FEET — left + right shoe-shape wedges on the ankle bones.
 * roundedBox primitive with toe-direction Y, narrow Z (height), wider
 * X (sole). Reads as a foot/shoe rather than a sphere.
 *
 * halfY = 0.085 — a ~17cm foot. halfX = 0.036 (sole half-width),
 * halfZ = 0.040 (height). These match what the inline foot emission
 * computed on average from CHIBI_LIMB_THICKNESS + child-offset length.
 *
 * Skin palette by default — wardrobe outfits' boot pieces will
 * override these slots once the equip system lands. (Knight boot,
 * cartoon round shoe, reptile claw, etc.)
 */
export const DEFAULT_FEET: AttachmentPart[] = [
  // Wedge — flat sharp-edged box, half the length of the old boot shape
  // and zero corner-rounding. Reads as a foot-shape in pixel art without
  // the boot mass. Foot bone is no longer in the legs scale group, so
  // the offset is at its natural (unscaled) value — keep it small so
  // the wedge sits close to the ankle on chibi-squashed legs.
  {
    name: 'foot_skin_L',
    jointName: 'LeftFoot',
    type: 1,
    params: [0.030, 0.045, 0.025, 0],   // halfX sole, halfY length (toe-dir), halfZ height
    offsetInBone: [0, 0.045, 0],
    paletteSlot: 'shoes',
    blendGroup: 4, blendRadius: 0.04,
  },
  {
    name: 'foot_skin_R',
    jointName: 'RightFoot',
    type: 1,
    params: [0.030, 0.045, 0.025, 0],
    offsetInBone: [0, 0.045, 0],
    paletteSlot: 'shoes',
    blendGroup: 5, blendRadius: 0.04,
  },
]

/** Combined defaults — what chibiRaymarchPrimitives uses when no
 *  explicit attachments list is passed. Loadout/wardrobe overrides
 *  build their own AttachmentPart[] and pass it in. */
export const DEFAULT_ATTACHMENTS: AttachmentPart[] = [...DEFAULT_HANDS, ...DEFAULT_FEET]

// ============================================================================
// Variant libraries — keyed by style name. Loadout pickers select an entry.
// ============================================================================

/**
 * HAND_LIBRARY — named hand-style variants. Each entry is a 2-element
 * AttachmentPart[] (left + right) so the picker swaps both at once.
 *
 *   skin  = the default skin sphere (matches DEFAULT_HANDS).
 *   mitt  = oversized cartoon glove (Mickey-mouse / Kingdom-Hearts).
 *           Inflated ellipsoid, shirt palette so it picks up the
 *           character's accent shirt color (often white).
 *   fist  = beefier skin-color fist for muscular / brawler builds.
 *   claw  = pointier ellipsoid with vertical taper, leather palette
 *           (reads as a dark talon / reptile claw).
 */
export const HAND_LIBRARY: Record<string, AttachmentPart[]> = {
  skin: DEFAULT_HANDS,
  mitt: [
    {
      name: 'hand_mitt_L', jointName: 'LeftHand',  type: 3,
      params: [0.090, 0.080, 0.090, 0],     // bulky ellipsoid
      offsetInBone: [0, 0.060, 0],
      paletteSlot: 'shirt',
      blendGroup: 2, blendRadius: 0.04,
    },
    {
      name: 'hand_mitt_R', jointName: 'RightHand', type: 3,
      params: [0.090, 0.080, 0.090, 0],
      offsetInBone: [0, 0.060, 0],
      paletteSlot: 'shirt',
      blendGroup: 3, blendRadius: 0.04,
    },
  ],
  fist: [
    {
      name: 'hand_fist_L', jointName: 'LeftHand',  type: 0,
      params: [0.072, 0, 0, 0],             // bigger skin sphere
      offsetInBone: [0, 0.045, 0],
      paletteSlot: 'skin',
      blendGroup: 2, blendRadius: 0.05,
    },
    {
      name: 'hand_fist_R', jointName: 'RightHand', type: 0,
      params: [0.072, 0, 0, 0],
      offsetInBone: [0, 0.045, 0],
      paletteSlot: 'skin',
      blendGroup: 3, blendRadius: 0.05,
    },
  ],
  claw: [
    {
      name: 'hand_claw_L', jointName: 'LeftHand',  type: 3,
      params: [0.045, 0.075, 0.040, 0],     // long-along-Y, narrow
      offsetInBone: [0, 0.060, 0],
      paletteSlot: 'leather',
      blendGroup: 2, blendRadius: 0.03,
    },
    {
      name: 'hand_claw_R', jointName: 'RightHand', type: 3,
      params: [0.045, 0.075, 0.040, 0],
      offsetInBone: [0, 0.060, 0],
      paletteSlot: 'leather',
      blendGroup: 3, blendRadius: 0.03,
    },
  ],
}

/**
 * FOOT_LIBRARY — named foot-style variants.
 *
 *   shoe  = brown wedge (matches DEFAULT_FEET) — a generic shoe.
 *   bare  = smaller skin-color wedge for sandals / barefoot characters.
 *   boot  = chunkier wedge in leather palette for adventurer builds.
 */
export const FOOT_LIBRARY: Record<string, AttachmentPart[]> = {
  shoe: DEFAULT_FEET,
  bare: [
    {
      name: 'foot_bare_L', jointName: 'LeftFoot',  type: 2,
      params: [0.030, 0.075, 0.034, 0.014],
      offsetInBone: [0, 0.075, 0],
      paletteSlot: 'skin',
      blendGroup: 4, blendRadius: 0.06,
    },
    {
      name: 'foot_bare_R', jointName: 'RightFoot', type: 2,
      params: [0.030, 0.075, 0.034, 0.014],
      offsetInBone: [0, 0.075, 0],
      paletteSlot: 'skin',
      blendGroup: 5, blendRadius: 0.06,
    },
  ],
  boot: [
    {
      name: 'foot_boot_L', jointName: 'LeftFoot',  type: 2,
      params: [0.045, 0.095, 0.050, 0.020],
      offsetInBone: [0, 0.095, 0],
      paletteSlot: 'leather',
      blendGroup: 4, blendRadius: 0.07,
    },
    {
      name: 'foot_boot_R', jointName: 'RightFoot', type: 2,
      params: [0.045, 0.095, 0.050, 0.020],
      offsetInBone: [0, 0.095, 0],
      paletteSlot: 'leather',
      blendGroup: 5, blendRadius: 0.07,
    },
  ],
}
