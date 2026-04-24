/**
 * Collada (.dae) → VAT binary baker.
 *
 * Writes VAT2 = LOCAL matrices per keyframe per joint (not world).
 * Runtime composes world matrices from these + per-character proportion
 * scales → supports retargeting: one animation plays on any character's
 * rest skeleton, with their own head/limb/torso scales applied.
 *
 * Pipeline:
 *   1. Parse DAE XML
 *   2. Walk scene graph to build joint hierarchy (parent index per joint)
 *   3. Extract per-joint animation tracks (time array + matrix array)
 *   4. For each frame: sample local matrix (row-major → column-major)
 *   5. Write as VAT2 binary: header + local-matrix payload
 *   6. Sidecar .meta.json includes rest-skeleton offsets for runtime use
 *
 * Usage: node scripts/bake_dae_vat.mjs <input.dae> <output.vat>
 * Default: /home/jb/mixamo/anims/walking_raw/Walking.dae → public/mixamo_walking.vat
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { XMLParser } from 'fast-xml-parser'

const IN  = process.argv[2] ?? '/home/jb/mixamo/anims/walking_raw/Walking.dae'
const OUT = process.argv[3] ?? '/home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/engine/public/mixamo_walking.vat'
const TARGET_FPS = 30
// Strip root motion: for animations where Mixamo's "In Place" checkbox is
// not available (backflips, dashes, cartwheels, etc.), zero the hips' XZ
// translation per-frame at bake time. Preserves Y bob. Pass --strip-root.
const STRIP_ROOT_MOTION = process.argv.includes('--strip-root')

// --- Parse DAE ---

const xml = readFileSync(IN, 'utf-8')
const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
  parseAttributeValue: true,
  trimValues: true,
})
const dae = parser.parse(xml).COLLADA

// Unit scale (cm → m typically for Mixamo)
const unitMeter = dae.asset?.unit?.['@_meter'] ?? 1
const UNIT_SCALE = Number(unitMeter)
console.log(`Unit scale: ${UNIT_SCALE} m/unit`)

// --- Parse animations: per-joint time array + matrix array ---

function parseFloatArray(text) {
  return text.split(/\s+/).filter((s) => s.length > 0).map(Number)
}

const jointTracks = new Map() // jointName → { times: Float32Array, matrices: Float32Array (row-major) }

const animations = dae.library_animations?.animation
const animArray = Array.isArray(animations) ? animations : animations ? [animations] : []
console.log(`Animation blocks in DAE: ${animArray.length}`)

for (const anim of animArray) {
  const id = anim['@_id']   // e.g. "mixamorig_Hips-anim"
  const name = id.replace(/-anim$/, '').replace(/^mixamorig_/, '')

  const sources = Array.isArray(anim.source) ? anim.source : [anim.source]
  let times = null
  let matrices = null
  for (const src of sources) {
    const srcId = src['@_id'] ?? ''
    const floatArr = src.float_array?.['#text'] ?? src.float_array
    const vals = typeof floatArr === 'string' ? parseFloatArray(floatArr) : []
    if (srcId.endsWith('-animation-input')) {
      times = new Float32Array(vals)
    } else if (srcId.endsWith('-output-transform')) {
      matrices = new Float32Array(vals)
    }
  }
  if (!times || !matrices) continue
  jointTracks.set(name, { times, matrices })
}

console.log(`Joint animation tracks extracted: ${jointTracks.size}`)

// --- Parse visual scene: walk to find joint hierarchy ---

const visualScene = dae.library_visual_scenes?.visual_scene
const jointNodes = []      // { name, parent: jointIdx, restMatrix: row-major mat4 (unscaled) }
const nameToIdx = new Map()

function walkNode(node, parentJointIdx) {
  if (!node) return
  const nodeList = Array.isArray(node) ? node : [node]
  for (const n of nodeList) {
    const isJoint = n['@_type'] === 'JOINT'
    let thisIdx = parentJointIdx
    if (isJoint) {
      const name = (n['@_sid'] ?? n['@_name'] ?? '').replace(/^mixamorig_/, '')
      const matrixText = typeof n.matrix === 'object' ? (n.matrix['#text'] ?? '') : String(n.matrix ?? '')
      const rest = new Float32Array(parseFloatArray(matrixText))
      if (rest.length !== 16) continue
      thisIdx = jointNodes.length
      jointNodes.push({ name, parent: parentJointIdx, restMatrix: rest })
      nameToIdx.set(name, thisIdx)
    }
    if (n.node) walkNode(n.node, thisIdx)
  }
}

const rootNode = visualScene?.node
walkNode(rootNode, -1)

console.log(`Joints in hierarchy: ${jointNodes.length}`)
if (jointNodes.length === 0) throw new Error('No joints found — scene parse failed')

// --- Determine total duration + per-frame sampling ---

let durationSec = 0
for (const { times } of jointTracks.values()) {
  if (times.length) durationSec = Math.max(durationSec, times[times.length - 1])
}
const numFrames = Math.max(1, Math.round(durationSec * TARGET_FPS))
console.log(`Duration: ${durationSec.toFixed(3)}s @ ${TARGET_FPS}fps → ${numFrames} frames`)

// --- Matrix helpers (column-major for output, but DAE source is row-major) ---

function rowToColMajor(rowSrc, out16) {
  // DAE: [m00 m01 m02 m03 | m10 m11 m12 m13 | m20 m21 m22 m23 | m30 m31 m32 m33]
  // WebGPU column-major: col0=[m00,m10,m20,m30], col1=[m01,m11,m21,m31], ...
  out16[0] = rowSrc[0];  out16[1] = rowSrc[4];  out16[2] = rowSrc[8];  out16[3] = rowSrc[12]
  out16[4] = rowSrc[1];  out16[5] = rowSrc[5];  out16[6] = rowSrc[9];  out16[7] = rowSrc[13]
  out16[8] = rowSrc[2];  out16[9] = rowSrc[6];  out16[10] = rowSrc[10]; out16[11] = rowSrc[14]
  out16[12] = rowSrc[3]; out16[13] = rowSrc[7]; out16[14] = rowSrc[11]; out16[15] = rowSrc[15]
}

function mat4Multiply(out, a, b) {
  // Both column-major.
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      out[col * 4 + row] =
        a[row]      * b[col * 4]     +
        a[row + 4]  * b[col * 4 + 1] +
        a[row + 8]  * b[col * 4 + 2] +
        a[row + 12] * b[col * 4 + 3]
    }
  }
}

function sampleJointMatrix(joint, t, outCol) {
  const track = jointTracks.get(joint.name)
  if (!track) {
    // No animation track — use rest matrix.
    rowToColMajor(joint.restMatrix, outCol)
    return
  }
  const { times, matrices } = track
  const last = times.length - 1
  // Locate interval
  let idx = last
  if (t <= times[0]) idx = 0
  else if (t >= times[last]) idx = last
  else {
    for (let i = 0; i < last; i++) {
      if (t >= times[i] && t < times[i + 1]) { idx = i; break }
    }
  }
  // For simplicity: nearest-neighbor sample (DAE keyframes are dense at 30fps).
  // Proper matrix slerp requires decomposing into TRS, interpolating, and re-composing.
  // Nearest works fine at 30fps source → 30fps target.
  const rowMat = new Float32Array(matrices.buffer, matrices.byteOffset + idx * 16 * 4, 16)
  rowToColMajor(rowMat, outCol)
}

// --- Bake VAT ---

const numJoints = jointNodes.length
const HEADER_BYTES = 32
const matricesBytes = numFrames * numJoints * 64
const out = new ArrayBuffer(HEADER_BYTES + matricesBytes)
const hdrView = new DataView(out)

// Magic "VAT2" (local-matrix variant, runtime composes world with proportions).
hdrView.setUint8(0, 0x56); hdrView.setUint8(1, 0x41); hdrView.setUint8(2, 0x54); hdrView.setUint8(3, 0x32)
hdrView.setUint32(4, numFrames, true)
hdrView.setUint32(8, numJoints, true)
hdrView.setFloat32(12, durationSec, true)
hdrView.setFloat32(16, TARGET_FPS, true)

const matData = new Float32Array(out, HEADER_BYTES, numFrames * numJoints * 16)

// VAT2: store LOCAL matrices (not world). Runtime composes world from
// these + per-character proportion scales via hierarchy walk.
const local = new Float32Array(16)
const localScaled = new Float32Array(16)

// Hips joint index (for root-motion strip). Mixamo root is named "Hips".
const hipsIdx = jointNodes.findIndex((n) => n.name === 'Hips')

// Capture Hips' rest XZ so we can pin it when stripping root motion.
let restHipsX = 0
let restHipsZ = 0
if (hipsIdx >= 0) {
  const restHips = jointNodes[hipsIdx].restMatrix
  restHipsX = restHips[3]  * UNIT_SCALE
  restHipsZ = restHips[11] * UNIT_SCALE
}

for (let f = 0; f < numFrames; f++) {
  const t = (f / numFrames) * durationSec
  for (let j = 0; j < numJoints; j++) {
    const joint = jointNodes[j]
    sampleJointMatrix(joint, t, local)

    // Scale translation column by UNIT_SCALE (cm → m).
    for (let i = 0; i < 16; i++) localScaled[i] = local[i]
    localScaled[12] *= UNIT_SCALE
    localScaled[13] *= UNIT_SCALE
    localScaled[14] *= UNIT_SCALE

    // Strip root-motion on Hips: pin XZ to rest, keep Y (vertical bob).
    if (STRIP_ROOT_MOTION && j === hipsIdx) {
      localScaled[12] = restHipsX
      localScaled[14] = restHipsZ
    }

    matData.set(localScaled, (f * numJoints + j) * 16)
  }
}

if (STRIP_ROOT_MOTION) {
  console.log('Stripped root motion on Hips (XZ pinned to rest, Y preserved).')
}

writeFileSync(OUT, Buffer.from(out))
console.log(`Wrote ${OUT} (${(out.byteLength / 1024).toFixed(1)} KB)`)

// Also emit a JSON sidecar with joint names, parent indices, AND rest
// offsets (from the rest matrix's translation column, cm→m scaled) so the
// runtime display code can orient bone cubes along their rest direction.
const meta = {
  source: IN,
  durationSec,
  fps: TARGET_FPS,
  numFrames,
  joints: jointNodes.map((j) => ({
    name: j.name,
    parent: j.parent,
    // Row-major rest matrix → translation column is elements [3, 7, 11].
    offset: [
      j.restMatrix[3]  * UNIT_SCALE,
      j.restMatrix[7]  * UNIT_SCALE,
      j.restMatrix[11] * UNIT_SCALE,
    ],
  })),
}
writeFileSync(OUT.replace(/\.vat$/, '.meta.json'), JSON.stringify(meta, null, 2))
console.log(`Wrote ${OUT.replace(/\.vat$/, '.meta.json')}`)
