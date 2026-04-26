/**
 * Face pixel-stamp data — encodes the screen-space face element styles
 * (eyes, mouth) as small lists of (dx, dy, paletteSlot) entries instead
 * of hardcoding them in the WGSL shader. Same visual output, but the
 * format is now editor-friendly: a UI widget can paint cells, save/load
 * presets, and bake to this data shape.
 *
 * Authoring rules:
 *   - dx/dy are pixel offsets from the eye/mouth anchor (CPU-projected
 *     screen point). Eyes anchor at the inner column of the 2-wide block;
 *     mouths at the centre.
 *   - paletteSlot is the index into the material's palette (eyewhite,
 *     pupil, mouth, accent, …). Existing styles use up to 4 distinct
 *     slots — main pupil, eye-white, accent (goggles rim / glow), tear.
 *   - Empty slot = transparent (no overwrite).
 *
 * Mirroring is built into the shader — for eye styles, the LEFT eye uses
 * the entries directly; the RIGHT eye negates dx automatically. So you
 * only author the LEFT eye and the right one mirrors.
 *
 *   Eye styles are anchored at the INNER column of each eye block:
 *     dx=0 is the column closest to the face centre,
 *     dx=+1 is the outer column,
 *     dy=-1 is one pixel above the centre row,
 *     dy=+1 is one pixel below.
 *
 *   Mouth styles are anchored at the centre pixel:
 *     dx in [-1, +1], dy in [-1, +1].
 */

/** Palette slot semantics for face pixels. Resolved at upload time to
 *  the material's actual palette index (so character recolour follows). */
export type FacePixelSlot =
  | 'pupil'      // main eye colour (black/dark)
  | 'eyewhite'   // eye white area
  | 'accent'     // goggles rim / glow tint / scar mark
  | 'tear'       // crying tear stream — cyan
  | 'mouth'      // mouth colour
  | 'glow_core'  // bright core for glowing eyes

/** A single pixel in a face stamp. */
export interface FacePixel {
  dx: number
  dy: number
  slot: FacePixelSlot
}

/** A named face element preset — eyes, mouth, etc. */
export interface FacePixelGrid {
  name: string
  /** Pixel data. For eyes, only LEFT eye authored — right eye mirrors. */
  pixels: FacePixel[]
  /** Optional auto-glow modulation — when set, this slot's pixels
   *  pulse with the shader's glow uniform. Used by the "glowing" eye
   *  style; left undefined for ordinary stamps. */
  glowSlot?: FacePixelSlot
}

// ============================================================================
// EYE STYLES — author LEFT eye only; right is auto-mirrored
// ============================================================================
//
// Block convention: the anchor (dx=0, dy=0) is on the INNER column,
// middle row. The eye block spans dx ∈ {0, +1} (inner→outer) and
// dy ∈ {-1, 0, +1} (top→middle→bottom).

/** mario — Mario-style 2×3: outer column all white, inner column W/B/B
 *  pupil pillar. Inner = inward (toward face centre). */
export const FACE_EYE_MARIO: FacePixelGrid = {
  name: 'mario',
  pixels: [
    // Outer column (dx=+1) — all white
    { dx: 1, dy: -1, slot: 'eyewhite' },
    { dx: 1, dy:  0, slot: 'eyewhite' },
    { dx: 1, dy:  1, slot: 'eyewhite' },
    // Inner column (dx=0) — white top, black middle + bottom
    { dx: 0, dy: -1, slot: 'eyewhite' },
    { dx: 0, dy:  0, slot: 'pupil' },
    { dx: 0, dy:  1, slot: 'pupil' },
  ],
}

/** dot — single pixel pupil. */
export const FACE_EYE_DOT: FacePixelGrid = {
  name: 'dot',
  pixels: [
    { dx: 0, dy: 0, slot: 'pupil' },
  ],
}

/** round — 2×2 solid pupil block. */
export const FACE_EYE_ROUND: FacePixelGrid = {
  name: 'round',
  pixels: [
    { dx: 0, dy: -1, slot: 'pupil' },
    { dx: 1, dy: -1, slot: 'pupil' },
    { dx: 0, dy:  0, slot: 'pupil' },
    { dx: 1, dy:  0, slot: 'pupil' },
  ],
}

/** goggles — 3×3 with accent rim + inner pupil. */
export const FACE_EYE_GOGGLES: FacePixelGrid = {
  name: 'goggles',
  pixels: [
    // Top row of rim
    { dx: -1, dy: -1, slot: 'accent' },
    { dx:  0, dy: -1, slot: 'accent' },
    { dx:  1, dy: -1, slot: 'accent' },
    // Middle row — accent edges + pupil centre
    { dx: -1, dy:  0, slot: 'accent' },
    { dx:  0, dy:  0, slot: 'pupil' },
    { dx:  1, dy:  0, slot: 'accent' },
    // Bottom row of rim
    { dx: -1, dy:  1, slot: 'accent' },
    { dx:  0, dy:  1, slot: 'accent' },
    { dx:  1, dy:  1, slot: 'accent' },
  ],
}

/** glowing — 2×2 pulsing block. Glow modulates the bright core. */
export const FACE_EYE_GLOWING: FacePixelGrid = {
  name: 'glowing',
  pixels: [
    { dx: 0, dy: -1, slot: 'accent' },
    { dx: 1, dy: -1, slot: 'accent' },
    { dx: 0, dy:  0, slot: 'glow_core' },
    { dx: 1, dy:  0, slot: 'accent' },
  ],
  glowSlot: 'glow_core',
}

/** closed — 2×1 horizontal line (also forced when blink is on). */
export const FACE_EYE_CLOSED: FacePixelGrid = {
  name: 'closed',
  pixels: [
    { dx: 0, dy: 0, slot: 'pupil' },
    { dx: 1, dy: 0, slot: 'pupil' },
  ],
}

/** crying — closed line + 2-pixel cyan tear stream below inner column. */
export const FACE_EYE_CRYING: FacePixelGrid = {
  name: 'crying',
  pixels: [
    // Closed line
    { dx: 0, dy: 0, slot: 'pupil' },
    { dx: 1, dy: 0, slot: 'pupil' },
    // Tear stream on inner column
    { dx: 0, dy: 1, slot: 'tear' },
    { dx: 0, dy: 2, slot: 'tear' },
  ],
}

// ============================================================================
// MOUTH STYLES — anchor at the centre, dx ∈ [-1, +1], dy ∈ [-1, +1]
// ============================================================================

/** off — no mouth drawn. */
export const FACE_MOUTH_OFF: FacePixelGrid = { name: 'off', pixels: [] }

/** line — 3×1 horizontal line. */
export const FACE_MOUTH_LINE: FacePixelGrid = {
  name: 'line',
  pixels: [
    { dx: -1, dy: 0, slot: 'mouth' },
    { dx:  0, dy: 0, slot: 'mouth' },
    { dx:  1, dy: 0, slot: 'mouth' },
  ],
}

/** smile — corners up, dip below. */
export const FACE_MOUTH_SMILE: FacePixelGrid = {
  name: 'smile',
  pixels: [
    { dx: -1, dy:  0, slot: 'mouth' },
    { dx:  1, dy:  0, slot: 'mouth' },
    { dx:  0, dy:  1, slot: 'mouth' },
  ],
}

/** open_o — 2×2 filled square. */
export const FACE_MOUTH_OPEN_O: FacePixelGrid = {
  name: 'open_o',
  pixels: [
    { dx: 0, dy: 0, slot: 'mouth' },
    { dx: 1, dy: 0, slot: 'mouth' },
    { dx: 0, dy: 1, slot: 'mouth' },
    { dx: 1, dy: 1, slot: 'mouth' },
  ],
}

/** frown — corners down, rise above. */
export const FACE_MOUTH_FROWN: FacePixelGrid = {
  name: 'frown',
  pixels: [
    { dx: -1, dy:  0, slot: 'mouth' },
    { dx:  1, dy:  0, slot: 'mouth' },
    { dx:  0, dy: -1, slot: 'mouth' },
  ],
}

/** pout — single pixel. */
export const FACE_MOUTH_POUT: FacePixelGrid = {
  name: 'pout',
  pixels: [
    { dx: 0, dy: 0, slot: 'mouth' },
  ],
}

// ============================================================================
// REGISTRY — id-aligned with the existing shader switch IDs
// ============================================================================

/** Eye styles in the same order their IDs use in the shader's faceFlags.x. */
export const EYE_STYLES: FacePixelGrid[] = [
  FACE_EYE_MARIO,    // 0
  FACE_EYE_DOT,      // 1
  FACE_EYE_ROUND,    // 2
  FACE_EYE_GOGGLES,  // 3
  FACE_EYE_GLOWING,  // 4
  FACE_EYE_CLOSED,   // 5
  FACE_EYE_CRYING,   // 6
]

/** Mouth styles aligned with faceFlags.y IDs. */
export const MOUTH_STYLES: FacePixelGrid[] = [
  FACE_MOUTH_OFF,    // 0
  FACE_MOUTH_LINE,   // 1
  FACE_MOUTH_SMILE,  // 2
  FACE_MOUTH_OPEN_O, // 3
  FACE_MOUTH_FROWN,  // 4
  FACE_MOUTH_POUT,   // 5
]

/** Resolve a slot label to the material palette index. The face-pixel
 *  shader code looks up palette[index] for each pixel — so the same
 *  pixel data renders correctly regardless of palette tweaks. */
export function resolveSlot(slot: FacePixelSlot, namedSlots: Record<string, number>): number {
  switch (slot) {
    case 'pupil':     return namedSlots.pupil     ?? 7
    case 'eyewhite':  return namedSlots.eyewhite  ?? 6
    case 'accent':    return namedSlots.accent    ?? 11
    case 'mouth':     return namedSlots.mouth     ?? 8
    // tear / glow_core fall back to a built-in cyan / amber via shader
    // constants — these aren't in the standard palette so the shader
    // hard-codes a sentinel index that means "use built-in colour."
    case 'tear':      return 28   // sentinel: shader maps to cyan
    case 'glow_core': return 29   // sentinel: shader maps to bright amber
  }
}
