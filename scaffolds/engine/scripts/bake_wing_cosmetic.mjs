/**
 * Wing cosmetic bake — emits a `.cos.json` matching the schema in
 * src/character3d/animated_cosmetic.ts. Authoring source: same flap /
 * fold / idle generators conceptually duplicated from wing_rig.ts
 * (we can't import .ts from .mjs without a TS runner; this is the
 * same approach bake_vat_binary.mjs takes — duplicate the math).
 *
 * Output: public/wings_feathered.cos.json
 *         public/cosmetic_manifest.json (or appends if it exists)
 *
 * Usage: node scripts/bake_wing_cosmetic.mjs
 *
 * To author a NEW wing variant (different bone count, different
 * palette, different flap amplitude), copy this file and tweak the
 * SPEC constants below. Each variant becomes its own .cos.json.
 */

import { writeFileSync, existsSync, readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const PUBLIC_DIR = resolve(__dirname, '..', 'public')

// ============================================================================
// Wing spec — mirror of wing_rig.ts DEFAULT_WING_SPEC
// ============================================================================

const SPEC = {
  segmentCount: 2,           // visible chain segments per wing
  segmentLength: 0.10,       // each segment 10cm long
  halfW: 0.060,              // 6cm wide flat membrane
  halfThick: 0.012,          // 1.2cm thin (≥1px at sz48)
  tipTaper: 0.4,             // 40% cross-section at tip
  paletteSlot: 'feather',
  spreadAngle: Math.PI * 0.50,   // wings held horizontally at bind
  /** Sideways offset from socket center to anchor. Caller (host) can
   *  override at equip time — this is the default tuned for a body
   *  ~17cm wide. */
  attachSidewaysOffset: 0.05,
}

const FPS = 30

// ============================================================================
// Bone construction — mirror of wing_rig.ts buildWingBones
// ============================================================================

function buildBones() {
  const bones = []

  // L side
  const lAnchorIdx = bones.length
  bones.push({
    name: 'WingL_Anchor',
    parent: -1,    // attaches to host socket
    offset: [-SPEC.attachSidewaysOffset, 0, 0],
    // sign = -1 for L. preRotation = [0, 0, -sign × spread] = [0, 0, +spread]
    preRotation: [0, 0, SPEC.spreadAngle],
  })
  for (let i = 0; i <= SPEC.segmentCount; i++) {
    bones.push({
      name: `WingL_Seg${i}`,
      parent: i === 0 ? lAnchorIdx : bones.length - 1,
      offset: i === 0 ? [0, 0, 0] : [0, SPEC.segmentLength, 0],
    })
  }

  // R side
  const rAnchorIdx = bones.length
  bones.push({
    name: 'WingR_Anchor',
    parent: -1,
    offset: [SPEC.attachSidewaysOffset, 0, 0],
    // sign = +1. preRotation Z = -sign × spread = -spread.
    preRotation: [0, 0, -SPEC.spreadAngle],
  })
  for (let i = 0; i <= SPEC.segmentCount; i++) {
    bones.push({
      name: `WingR_Seg${i}`,
      parent: i === 0 ? rAnchorIdx : bones.length - 1,
      offset: i === 0 ? [0, 0, 0] : [0, SPEC.segmentLength, 0],
    })
  }

  return bones
}

// ============================================================================
// Prim construction — one ribbon-chain per side
// ============================================================================

function buildPrims() {
  return [
    {
      type: 23,
      bone: 'WingL_Seg0',
      paletteSlot: SPEC.paletteSlot,
      params: [SPEC.segmentCount + 1, SPEC.halfW, SPEC.halfThick, SPEC.tipTaper],
      offsetInBone: [0, 0, 0],
    },
    {
      type: 23,
      bone: 'WingR_Seg0',
      paletteSlot: SPEC.paletteSlot,
      params: [SPEC.segmentCount + 1, SPEC.halfW, SPEC.halfThick, SPEC.tipTaper],
      offsetInBone: [0, 0, 0],
    },
  ]
}

// ============================================================================
// Animation generators — mirror wing_rig.ts flap/fold
// ============================================================================

/** Symmetric sin flap. Anchor bones rotate around their local Z. The
 *  bind preRotation already handles the spread (+/- π/2 Z), so a
 *  positive Z delta on L pivots the wing UPWARD (anchor +Y rotates
 *  from outward toward up); on R, the same UP pivot needs a NEGATIVE
 *  delta because R's bind frame is mirrored. */
function flapDeltas(phase, amplitude) {
  const flap = Math.sin(phase * 2 * Math.PI) * amplitude
  return {
    WingL_Anchor: [0, 0,  flap],
    WingR_Anchor: [0, 0, -flap],
  }
}

/** Static fold — wings tucked behind the body. Same mirror pattern. */
function foldDeltas(amount) {
  const tuck = amount * Math.PI / 3
  return {
    WingL_Anchor: [0, 0, -tuck],
    WingR_Anchor: [0, 0,  tuck],
  }
}

/** Build a CosmeticAnimation entry from a generator function. */
function makeAnimation(tag, numFrames, genFrame) {
  const frames = []
  for (let f = 0; f < numFrames; f++) {
    frames.push(genFrame(f / numFrames))
  }
  return {
    tag,
    fps: FPS,
    numFrames,
    durationSec: numFrames / FPS,
    frames,
  }
}

// ============================================================================
// Assemble + write cosmetic
// ============================================================================

const cosmetic = {
  schema: 1,
  name: 'wings_feathered',
  category: 'wings',
  defaultSocket: 'BodySeg0',   // bird body midpoint; host can override
  bones: buildBones(),
  prims: buildPrims(),
  animations: {
    idle: makeAnimation('idle', 30, (t) => flapDeltas(t, Math.PI / 18)),   // ±10° shallow
    flap: makeAnimation('flap', 30, (t) => flapDeltas(t, Math.PI / 3)),    // ±60° active
    fold: makeAnimation('fold',  1, ()  => foldDeltas(0.85)),              // static tucked
  },
  defaultAnim: 'idle',
}

const cosPath = resolve(PUBLIC_DIR, `${cosmetic.name}.cos.json`)
writeFileSync(cosPath, JSON.stringify(cosmetic, null, 2))
console.log(`Wrote ${cosmetic.name}.cos.json — ${cosmetic.bones.length} bones, ${cosmetic.prims.length} prims, ${Object.keys(cosmetic.animations).length} anims`)

// ---------- Cosmetic manifest ----------
// Append-or-create. Each cosmetic registers under a unique name.
const manifestPath = resolve(PUBLIC_DIR, 'cosmetic_manifest.json')
let manifest
if (existsSync(manifestPath)) {
  manifest = JSON.parse(readFileSync(manifestPath, 'utf-8'))
  manifest.cosmetics = (manifest.cosmetics || []).filter((c) => c.name !== cosmetic.name)
} else {
  manifest = { version: 1, cosmetics: [] }
}
manifest.cosmetics.push({
  name: cosmetic.name,
  category: cosmetic.category,
  url: `/${cosmetic.name}.cos.json`,
})
manifest.cosmetics.sort((a, b) => a.name.localeCompare(b.name))
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2))
console.log(`Updated cosmetic_manifest.json — ${manifest.cosmetics.length} cosmetics registered`)
