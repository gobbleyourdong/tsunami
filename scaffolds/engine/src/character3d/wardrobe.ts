/**
 * Wardrobe — silhouette-breaking armor / clothing layered on top of the
 * body. Each WardrobePiece defines bones (virtual joints) + their primitive
 * geometry. Pieces compose into a named outfit (`knight`, `mage`, etc.)
 * that the demo can equip via a single string lookup.
 *
 * Architecture (mirrors DEFAULT_BODY_PARTS / DEFAULT_CAPE_PARTS):
 *   - extendRigWithBodyParts is reused — wardrobe pieces are BodyParts.
 *   - chibiRaymarchPrimitives's body-parts branch emits primitives for
 *     /^WP_/ named entries with armor blend group + palette slot.
 *   - Multiple armor groups (11-15) so different layers can fuse with
 *     themselves but stay distinct from body group 6.
 *
 * Authoring rule: every WardrobePiece bone name starts with "WP_" so
 * the prim emitter can detect them with a simple regex.
 */

import type { BodyPart } from './mixamo_loader'

/** A single garment piece — one or more virtual joints + primitives. */
export interface WardrobePiece {
  name: string
  parts: BodyPart[]
}

/** Full outfit — list of pieces. */
export interface WardrobeOutfit {
  name: string
  pieces: WardrobePiece[]
}

/**
 * Knight outfit — full plate armor, 14 visible primitives.
 *
 *   helmet     — Head, ellipsoid larger than the head sphere
 *   pauldron   — each shoulder, big rounded ball over the joint
 *   chest_plate — Spine2, larger ellipsoid biased forward
 *   back_plate — Spine2, ellipsoid biased back
 *   belt       — Hips, thin band (using a flat roundedBox as torus stand-in)
 *   vambrace   — each forearm, ringed cylinder
 *   gauntlet   — each hand, sphere
 *   greave     — each lower leg, cylinder
 *   boot       — each foot, larger roundedBox replacing shoe
 *
 * All bones get the "WP_" prefix so the prim emitter routes them to
 * the wardrobe branch. Blend group 11 (armor) — pieces fuse with each
 * other where overlapping (chest+pauldron seam) but hard-min vs body
 * (group 6).
 */
export const WARDROBE_KNIGHT: WardrobeOutfit = {
  name: 'knight',
  pieces: [
    { name: 'helmet', parts: [
      // Slightly larger than head sphere (head is r=0.18). +0.04 for visible armor.
      { name: 'WP_Helmet',  parentName: 'Head',          offset: [0, 0.12, 0.005], displaySize: [0.22, 0.22, 0.22] },
    ]},
    { name: 'pauldrons', parts: [
      // Shoulder spheres: bigger than the existing 0.065 shoulder ball.
      { name: 'WP_PauldronL', parentName: 'LeftShoulder',  offset: [0, 0, 0], displaySize: [0.10, 0.10, 0.10] },
      { name: 'WP_PauldronR', parentName: 'RightShoulder', offset: [0, 0, 0], displaySize: [0.10, 0.10, 0.10] },
    ]},
    { name: 'chest', parts: [
      // Chest plate: ellipsoid in front of Spine2 + back plate behind.
      { name: 'WP_ChestPlate', parentName: 'Spine2', offset: [0,  0.00,  0.04], displaySize: [0.20, 0.18, 0.14] },
      { name: 'WP_BackPlate',  parentName: 'Spine2', offset: [0,  0.00, -0.04], displaySize: [0.20, 0.18, 0.14] },
    ]},
    { name: 'belt', parts: [
      // Belt: thin disc around hips (palette accent).
      { name: 'WP_Belt', parentName: 'Hips', offset: [0, 0.07, 0], displaySize: [0.18, 0.04, 0.16] },
    ]},
    { name: 'arms', parts: [
      { name: 'WP_VambraceL', parentName: 'LeftForeArm',  offset: [0, 0.10, 0], displaySize: [0.075, 0.10, 0.075] },
      { name: 'WP_VambraceR', parentName: 'RightForeArm', offset: [0, 0.10, 0], displaySize: [0.075, 0.10, 0.075] },
      { name: 'WP_GauntletL', parentName: 'LeftHand',  offset: [0, 0, 0], displaySize: [0.060, 0.060, 0.060] },
      { name: 'WP_GauntletR', parentName: 'RightHand', offset: [0, 0, 0], displaySize: [0.060, 0.060, 0.060] },
    ]},
    { name: 'legs', parts: [
      { name: 'WP_GreaveL', parentName: 'LeftLeg',  offset: [0, 0.10, 0], displaySize: [0.085, 0.12, 0.085] },
      { name: 'WP_GreaveR', parentName: 'RightLeg', offset: [0, 0.10, 0], displaySize: [0.085, 0.12, 0.085] },
      { name: 'WP_BootL', parentName: 'LeftFoot',  offset: [0, 0.04, 0.02], displaySize: [0.060, 0.08, 0.110] },
      { name: 'WP_BootR', parentName: 'RightFoot', offset: [0, 0.04, 0.02], displaySize: [0.060, 0.08, 0.110] },
    ]},
  ],
}

/** Flatten an outfit's pieces into a single BodyPart array — what the
 *  rig-extension functions accept directly. */
export function outfitToBodyParts(outfit: WardrobeOutfit): BodyPart[] {
  const out: BodyPart[] = []
  for (const piece of outfit.pieces) {
    for (const part of piece.parts) out.push(part)
  }
  return out
}

/**
 * Mage outfit — flowing robe + hood + sash. 6 cloth pieces.
 * All pieces prefixed `WP_Mage_` so they map to the cloth palette slot
 * via accessorySlot's prefix routing in mixamo_loader.ts. Hood uses an
 * explicit `shape: 'round'` since the name doesn't match the helmet
 * regex but we want the ellipsoid silhouette over the cranium.
 */
export const WARDROBE_MAGE: WardrobeOutfit = {
  name: 'mage',
  pieces: [
    { name: 'hood', parts: [
      { name: 'WP_Mage_Hood',  parentName: 'Head',   offset: [0, 0.08, -0.02], displaySize: [0.24, 0.20, 0.24], shape: 'round' },
    ]},
    { name: 'robe', parts: [
      // Two stacked boxes — chest + flowing skirt — to fake a long robe
      // silhouette without authoring a chain. Skirt is wider than chest.
      { name: 'WP_Mage_RobeChest', parentName: 'Spine2', offset: [0, -0.02, 0.00], displaySize: [0.20, 0.20, 0.16] },
      { name: 'WP_Mage_RobeSkirt', parentName: 'Hips',   offset: [0, -0.05, 0.00], displaySize: [0.22, 0.18, 0.20] },
    ]},
    { name: 'sleeves', parts: [
      // Wide sleeves bell out at the forearm — ellipsoid is too round, use box.
      { name: 'WP_Mage_SleeveL', parentName: 'LeftForeArm',  offset: [0, 0.10, 0], displaySize: [0.085, 0.12, 0.085] },
      { name: 'WP_Mage_SleeveR', parentName: 'RightForeArm', offset: [0, 0.10, 0], displaySize: [0.085, 0.12, 0.085] },
    ]},
    { name: 'sash', parts: [
      { name: 'WP_Mage_Belt', parentName: 'Hips', offset: [0, 0.08, 0], displaySize: [0.20, 0.04, 0.18] },
    ]},
  ],
}

/**
 * Light armor outfit — chest plate + boots + bracers. 6 pieces, mostly
 * leather with a single armor-slot chest. Mid-silhouette: more skin
 * showing than knight, less than barbarian.
 */
export const WARDROBE_LIGHT: WardrobeOutfit = {
  name: 'light',
  pieces: [
    { name: 'chest', parts: [
      // Just front plate — no back plate. Strap pads on shoulders.
      { name: 'WP_Light_ChestPlate', parentName: 'Spine2', offset: [0,  0.00,  0.05], displaySize: [0.18, 0.16, 0.12] },
    ]},
    { name: 'pads', parts: [
      // Small leather shoulder caps (smaller than knight pauldrons).
      { name: 'WP_Light_PauldronL', parentName: 'LeftShoulder',  offset: [0, 0, 0], displaySize: [0.085, 0.085, 0.085] },
      { name: 'WP_Light_PauldronR', parentName: 'RightShoulder', offset: [0, 0, 0], displaySize: [0.085, 0.085, 0.085] },
    ]},
    { name: 'belt', parts: [
      { name: 'WP_Light_Belt', parentName: 'Hips', offset: [0, 0.07, 0], displaySize: [0.18, 0.035, 0.16] },
    ]},
    { name: 'bracers', parts: [
      { name: 'WP_Light_BracerL', parentName: 'LeftForeArm',  offset: [0, 0.10, 0], displaySize: [0.070, 0.085, 0.070] },
      { name: 'WP_Light_BracerR', parentName: 'RightForeArm', offset: [0, 0.10, 0], displaySize: [0.070, 0.085, 0.070] },
    ]},
    { name: 'boots', parts: [
      { name: 'WP_Light_BootL', parentName: 'LeftFoot',  offset: [0, 0.04, 0.02], displaySize: [0.058, 0.075, 0.105] },
      { name: 'WP_Light_BootR', parentName: 'RightFoot', offset: [0, 0.04, 0.02], displaySize: [0.058, 0.075, 0.105] },
    ]},
  ],
}

/**
 * Barbarian outfit — pauldrons, belt, boots, no chest. Maximum skin
 * exposure; emphasizes the chest/torso silhouette underneath.
 */
export const WARDROBE_BARBARIAN: WardrobeOutfit = {
  name: 'barbarian',
  pieces: [
    { name: 'pauldrons', parts: [
      // Bigger fur-style pads on shoulders — leather slot for warm tone.
      { name: 'WP_Barb_PauldronL', parentName: 'LeftShoulder',  offset: [0, 0.02, 0], displaySize: [0.11, 0.10, 0.11] },
      { name: 'WP_Barb_PauldronR', parentName: 'RightShoulder', offset: [0, 0.02, 0], displaySize: [0.11, 0.10, 0.11] },
    ]},
    { name: 'belt', parts: [
      { name: 'WP_Barb_Belt', parentName: 'Hips', offset: [0, 0.07, 0], displaySize: [0.18, 0.05, 0.16] },
    ]},
    { name: 'loincloth', parts: [
      // Hanging loin cloth front + back — square boxes below the belt.
      { name: 'WP_Barb_LoinFront', parentName: 'Hips', offset: [0,  -0.06,  0.10], displaySize: [0.10, 0.10, 0.03] },
      { name: 'WP_Barb_LoinBack',  parentName: 'Hips', offset: [0,  -0.06, -0.10], displaySize: [0.10, 0.10, 0.03] },
    ]},
    { name: 'boots', parts: [
      { name: 'WP_Barb_BootL', parentName: 'LeftFoot',  offset: [0, 0.04, 0.02], displaySize: [0.060, 0.080, 0.110] },
      { name: 'WP_Barb_BootR', parentName: 'RightFoot', offset: [0, 0.04, 0.02], displaySize: [0.060, 0.080, 0.110] },
    ]},
  ],
}

/**
 * Ninja outfit — hooded mask + wraps + sash. 7 cloth pieces, all dark.
 * Silhouette is intentionally minimal — meant to read as a stealth
 * agent against a normal background. Uses the cloth palette slot via
 * the WP_Mage_ prefix routing (we reuse the slot — both outfits get
 * one stealth-friendly tone, distinct only by their distinct
 * displaySize / part counts).
 */
export const WARDROBE_NINJA: WardrobeOutfit = {
  name: 'ninja',
  pieces: [
    { name: 'hood', parts: [
      // Tighter than mage hood — wraps the cranium rather than pooling.
      { name: 'WP_Ninja_Hood', parentName: 'Head', offset: [0, 0.10, -0.01], displaySize: [0.21, 0.18, 0.21], shape: 'round' },
    ]},
    { name: 'mask', parts: [
      // Lower-face cover — small box on the front of the head sphere,
      // sits under the hood, breaks up the silhouette across the eyes.
      { name: 'WP_Ninja_Mask', parentName: 'Head', offset: [0,  0.07, 0.10], displaySize: [0.10, 0.06, 0.04] },
    ]},
    { name: 'wraps', parts: [
      { name: 'WP_Ninja_WrapL', parentName: 'LeftForeArm',  offset: [0, 0.08, 0], displaySize: [0.062, 0.10, 0.062] },
      { name: 'WP_Ninja_WrapR', parentName: 'RightForeArm', offset: [0, 0.08, 0], displaySize: [0.062, 0.10, 0.062] },
    ]},
    { name: 'sash', parts: [
      // Diagonal sash: two thin boxes on Spine2, one on each chest side.
      { name: 'WP_Ninja_SashL', parentName: 'Spine2', offset: [-0.03,  0.02,  0.05], displaySize: [0.04, 0.10, 0.10], rotationDeg: [0, 0, 30] },
      { name: 'WP_Ninja_SashR', parentName: 'Spine2', offset: [ 0.03,  0.02,  0.05], displaySize: [0.04, 0.10, 0.10], rotationDeg: [0, 0,-30] },
    ]},
    { name: 'belt', parts: [
      { name: 'WP_Ninja_Belt', parentName: 'Hips', offset: [0, 0.07, 0], displaySize: [0.18, 0.04, 0.16] },
    ]},
  ],
}

/** Registry of named outfits. Demo or character spec picks one by name. */
export const WARDROBE: Record<string, WardrobeOutfit> = {
  knight:    WARDROBE_KNIGHT,
  mage:      WARDROBE_MAGE,
  light:     WARDROBE_LIGHT,
  barbarian: WARDROBE_BARBARIAN,
  ninja:     WARDROBE_NINJA,
}
