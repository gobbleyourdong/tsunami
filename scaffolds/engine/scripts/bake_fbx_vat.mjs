/**
 * FBX (Mixamo) → VAT2 binary baker.
 *
 * WHY THIS EXISTS: the shipping pipeline is DAE-based (clean row-major
 * matrices, no Euler ambiguity). But Mixamo's bulk-download queue exports
 * FBX by default and re-downloading as Collada is a click. This baker
 * exists as a fallback when only .fbx is on disk.
 *
 * Scope — MIXAMO ONLY. We assume:
 *   - Bones are Model::mixamorig:<Name> with typeflag "LimbNode"
 *   - EulerOrder = XYZ (rotation matrix = Rz × Ry × Rx)
 *   - InheritType = 1 (RSrs): parent's scale does not propagate rotations
 *   - Rotation pivots + offsets are identity
 *   - Units in cm; convert to m
 *   - AnimationStack's LocalStop gives total duration in FBX time
 *   - Each animated bone's T/R/S channels live in AnimCurveNode::T/R/S
 *     with per-axis curves d|X, d|Y, d|Z
 *
 * Outputs the SAME binary layout as bake_dae_vat.mjs so the runtime and
 * VAT meta.json stay compatible.
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { parseBinary, parseText } from 'fbx-parser'

const IN  = process.argv[2] ?? '/home/jb/Downloads/Running.fbx'
const OUT = process.argv[3] ?? '/home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/engine/public/mixamo_running.vat'
const TARGET_FPS = 30
const STRIP_ROOT_MOTION = process.argv.includes('--strip-root')
const UNIT_SCALE = 1 / 100   // Mixamo FBX uses cm; runtime math is in meters

// FBX encodes time as 1/46186158000 s per unit (KTime).
const FBX_TIME_TO_SEC = 1 / 46186158000

// --- Parse FBX ---

// Mixamo exports both binary and ASCII FBX. Try binary first (cheaper);
// fall back to text parsing on the "Not a binary FBX file" throw.
let fbx
try {
  fbx = parseBinary(readFileSync(IN))
} catch {
  fbx = parseText(readFileSync(IN, 'utf-8'))
}
const objects = fbx.find((n) => n.name === 'Objects')
const connections = fbx.find((n) => n.name === 'Connections')
if (!objects) throw new Error('FBX has no Objects section')
if (!connections) throw new Error('FBX has no Connections section')

function propOf(p70, name) {
  for (const p of p70?.nodes ?? []) if (p.props[0] === name) return p.props
  return null
}

// Index Models by their uint64 id (first prop of Model node).
// Mixamo bones have name "Model::mixamorig:<BoneName>" and typeflag "LimbNode".
const modelsById = new Map()
for (const n of objects.nodes) {
  if (n.name !== 'Model') continue
  const [id, fullName, typeflag] = n.props
  if (typeflag !== 'LimbNode') continue
  const rawName = typeof fullName === 'string' ? fullName : ''
  const clean = rawName.replace(/^Model::/, '').replace(/^mixamorig:/, '')
  const p70 = n.nodes.find((c) => c.name === 'Properties70')
  const preRot = propOf(p70, 'PreRotation') ?? [0, 0, 0, '', '', 0, 0, 0]
  const lclT   = propOf(p70, 'Lcl Translation') ?? [0, 0, 0, '', '', 0, 0, 0]
  const lclR   = propOf(p70, 'Lcl Rotation') ?? [0, 0, 0, '', '', 0, 0, 0]
  const lclS   = propOf(p70, 'Lcl Scaling') ?? [0, 0, 0, '', '', 1, 1, 1]
  modelsById.set(id, {
    id,
    name: clean,
    preRot: [Number(preRot[4]), Number(preRot[5]), Number(preRot[6])],
    restT:  [Number(lclT[4]),   Number(lclT[5]),   Number(lclT[6])],
    restR:  [Number(lclR[4]),   Number(lclR[5]),   Number(lclR[6])],
    restS:  [Number(lclS[4]),   Number(lclS[5]),   Number(lclS[6])],
    parent: -1,
  })
}
console.log(`Bones found: ${modelsById.size}`)

// Connection records are "C" nodes with props [kind, srcId, dstId, optPropName].
//   kind = "OO" = object-to-object (hierarchy)
//   kind = "OP" = object-to-property (animation curve targets)
for (const c of connections.nodes) {
  if (c.name !== 'C') continue
  const [kind, srcId, dstId, propName] = c.props
  if (kind === 'OO' && modelsById.has(srcId) && modelsById.has(dstId)) {
    modelsById.get(srcId).parent = dstId   // temporarily store parent id
  }
  // OP handled below for curve wiring
}

// --- Topological order: depth-first from roots so parent indices < child indices. ---
// Build children map from id → [child ids].
const childrenById = new Map()
for (const m of modelsById.values()) childrenById.set(m.id, [])
for (const m of modelsById.values()) {
  if (m.parent !== -1 && childrenById.has(m.parent)) childrenById.get(m.parent).push(m.id)
}
const joints = []       // ordered: { name, parent(index), modelId, ... }
const indexOf = new Map()
function dfs(id, parentIdx) {
  const m = modelsById.get(id)
  const idx = joints.length
  joints.push({ ...m, parent: parentIdx })
  indexOf.set(id, idx)
  for (const cid of childrenById.get(id)) dfs(cid, idx)
}
// Root bones: parent not in modelsById (parent is scene root 0).
for (const m of modelsById.values()) {
  if (!modelsById.has(m.parent)) dfs(m.id, -1)
}
console.log(`Ordered joints: ${joints.length}`)

// --- Collect animation curves + wire to model properties via CurveNode intermediates. ---
// Each AnimationCurveNode has props [id, "AnimCurveNode::X", ""] where X ∈ {T, R, S}.
// AnimationCurves have props [id, "AnimCurve::", ""] + child KeyTime/KeyValueFloat arrays.
// Connections chain: Curve → (prop d|X/d|Y/d|Z) → CurveNode → (Lcl Translation|Rotation|Scaling) → Model.

const curvesById = new Map()   // curveId → { times: [FBX units], values: [float] }
for (const n of objects.nodes) {
  if (n.name !== 'AnimationCurve') continue
  const id = n.props[0]
  const times = n.nodes.find((c) => c.name === 'KeyTime')?.props[0] ?? []
  const values = n.nodes.find((c) => c.name === 'KeyValueFloat')?.props[0] ?? []
  curvesById.set(id, { times: Array.from(times), values: Array.from(values) })
}

const curveNodesById = new Map() // cnId → { kind: 'T'|'R'|'S', axes: { X, Y, Z — curveIds } }
for (const n of objects.nodes) {
  if (n.name !== 'AnimationCurveNode') continue
  const id = n.props[0]
  const fullName = String(n.props[1] ?? '')
  const kind = fullName.endsWith('::T') ? 'T' : fullName.endsWith('::R') ? 'R' : fullName.endsWith('::S') ? 'S' : null
  if (!kind) continue
  curveNodesById.set(id, { id, kind, axes: { X: null, Y: null, Z: null } })
}

// Wire curves (srcId) to curve-nodes (dstId) via OP connections with property "d|X"/"d|Y"/"d|Z".
for (const c of connections.nodes) {
  if (c.name !== 'C') continue
  const [kind, srcId, dstId, propName] = c.props
  if (kind !== 'OP') continue
  if (!curvesById.has(srcId) || !curveNodesById.has(dstId)) continue
  const axis = String(propName).replace('d|', '')
  if (axis in curveNodesById.get(dstId).axes) {
    curveNodesById.get(dstId).axes[axis] = srcId
  }
}

// Wire curve-nodes to models via OP connections with property "Lcl Translation|Rotation|Scaling".
const modelAnim = new Map()   // modelId → { T: cnId?, R: cnId?, S: cnId? }
for (const m of modelsById.values()) modelAnim.set(m.id, { T: null, R: null, S: null })
for (const c of connections.nodes) {
  if (c.name !== 'C') continue
  const [kind, srcId, dstId, propName] = c.props
  if (kind !== 'OP') continue
  if (!curveNodesById.has(srcId) || !modelsById.has(dstId)) continue
  const p = String(propName)
  const slot = p === 'Lcl Translation' ? 'T' : p === 'Lcl Rotation' ? 'R' : p === 'Lcl Scaling' ? 'S' : null
  if (!slot) continue
  modelAnim.get(dstId)[slot] = srcId
}

// Duration from curves. Mixamo's AnimationStack.LocalStop reports a nominal
// clip length (often 3+s), but the actual keyframe data frequently covers
// only one cycle (~0.6s). Using LocalStop baked many dead-pose frames past
// the last keyframe. We take the max keyframe time across all curves as the
// source-of-truth duration.
let durationSec = 0
for (const cv of curvesById.values()) {
  if (cv.times.length === 0) continue
  const last = Number(cv.times[cv.times.length - 1]) * FBX_TIME_TO_SEC
  if (last > durationSec) durationSec = last
}
const numFrames = Math.max(1, Math.round(durationSec * TARGET_FPS))
console.log(`Duration ${durationSec.toFixed(3)}s → ${numFrames} frames @ ${TARGET_FPS}fps`)

// --- Curve sampling (linear interp between keys). ---

function sampleCurve(curveId, tSec, fallback) {
  if (curveId == null) return fallback
  const cv = curvesById.get(curveId)
  if (!cv || cv.times.length === 0) return fallback
  const tFbx = tSec / FBX_TIME_TO_SEC
  const n = cv.times.length
  if (tFbx <= Number(cv.times[0])) return cv.values[0]
  if (tFbx >= Number(cv.times[n - 1])) return cv.values[n - 1]
  // Binary search would be tidier; linear is fine for ≤200 keys.
  for (let i = 0; i < n - 1; i++) {
    const t0 = Number(cv.times[i])
    const t1 = Number(cv.times[i + 1])
    if (tFbx >= t0 && tFbx < t1) {
      const u = (tFbx - t0) / (t1 - t0)
      return cv.values[i] * (1 - u) + cv.values[i + 1] * u
    }
  }
  return cv.values[n - 1]
}

function sampleAxes(cnId, tSec, fallback) {
  if (cnId == null) return fallback
  const cn = curveNodesById.get(cnId)
  return [
    sampleCurve(cn.axes.X, tSec, fallback[0]),
    sampleCurve(cn.axes.Y, tSec, fallback[1]),
    sampleCurve(cn.axes.Z, tSec, fallback[2]),
  ]
}

// --- Math: Euler (degrees, XYZ order) → column-major mat4. ---
// FBX's "EulerXYZ" rotates around X, then Y, then Z. Composed matrix:
//   R = Rz × Ry × Rx   (post-multiplied to column vector: Rx applied first).

function eulerXYZToMat3(xDeg, yDeg, zDeg) {
  const x = xDeg * Math.PI / 180
  const y = yDeg * Math.PI / 180
  const z = zDeg * Math.PI / 180
  const cx = Math.cos(x), sx = Math.sin(x)
  const cy = Math.cos(y), sy = Math.sin(y)
  const cz = Math.cos(z), sz = Math.sin(z)
  // Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]
  // Ry = [[cy,0,sy],[0,1,0],[-sy,0,cy]]
  // Rz = [[cz,-sz,0],[sz,cz,0],[0,0,1]]
  // R  = Rz * Ry * Rx  (row-major composition)
  const m00 =  cy * cz
  const m01 =  sx * sy * cz - cx * sz
  const m02 =  cx * sy * cz + sx * sz
  const m10 =  cy * sz
  const m11 =  sx * sy * sz + cx * cz
  const m12 =  cx * sy * sz - sx * cz
  const m20 = -sy
  const m21 =  sx * cy
  const m22 =  cx * cy
  return [m00, m01, m02, m10, m11, m12, m20, m21, m22]
}

function composeLocalMat(out16, T, Rdeg, PreRotDeg, S) {
  // Mixamo composition: M = T × PreRot × Lcl_R × diag(S)
  const preR = eulerXYZToMat3(PreRotDeg[0], PreRotDeg[1], PreRotDeg[2])
  const lclR = eulerXYZToMat3(Rdeg[0], Rdeg[1], Rdeg[2])
  // R = PreR × lclR  (row-major)
  const r = new Float64Array(9)
  for (let i = 0; i < 3; i++) {
    for (let j = 0; j < 3; j++) {
      r[i * 3 + j] =
        preR[i * 3 + 0] * lclR[0 * 3 + j] +
        preR[i * 3 + 1] * lclR[1 * 3 + j] +
        preR[i * 3 + 2] * lclR[2 * 3 + j]
    }
  }
  // Column-major mat4 output: col k is (r[0*3+k]*Sk, r[1*3+k]*Sk, r[2*3+k]*Sk, 0)
  // col3 = (Tx*UNIT_SCALE, Ty*UNIT_SCALE, Tz*UNIT_SCALE, 1)
  out16[0]  = r[0] * S[0]
  out16[1]  = r[3] * S[0]
  out16[2]  = r[6] * S[0]
  out16[3]  = 0
  out16[4]  = r[1] * S[1]
  out16[5]  = r[4] * S[1]
  out16[6]  = r[7] * S[1]
  out16[7]  = 0
  out16[8]  = r[2] * S[2]
  out16[9]  = r[5] * S[2]
  out16[10] = r[8] * S[2]
  out16[11] = 0
  out16[12] = T[0] * UNIT_SCALE
  out16[13] = T[1] * UNIT_SCALE
  out16[14] = T[2] * UNIT_SCALE
  out16[15] = 1
}

// --- Hips rest XZ for root-motion strip ---
const hipsIdx = joints.findIndex((j) => j.name === 'Hips')
const restHipsX = hipsIdx >= 0 ? joints[hipsIdx].restT[0] * UNIT_SCALE : 0
const restHipsZ = hipsIdx >= 0 ? joints[hipsIdx].restT[2] * UNIT_SCALE : 0

// --- Bake ---

const numJoints = joints.length
const HEADER_BYTES = 32
const matBytes = numFrames * numJoints * 64
const out = new ArrayBuffer(HEADER_BYTES + matBytes)
const hdr = new DataView(out)
hdr.setUint8(0, 0x56); hdr.setUint8(1, 0x41); hdr.setUint8(2, 0x54); hdr.setUint8(3, 0x32)
hdr.setUint32(4, numFrames, true)
hdr.setUint32(8, numJoints, true)
hdr.setFloat32(12, durationSec, true)
hdr.setFloat32(16, TARGET_FPS, true)
const matData = new Float32Array(out, HEADER_BYTES, numFrames * numJoints * 16)

const local = new Float32Array(16)
for (let f = 0; f < numFrames; f++) {
  const t = (f / numFrames) * durationSec
  for (let j = 0; j < numJoints; j++) {
    const joint = joints[j]
    const anim = modelAnim.get(joint.id)
    const T = sampleAxes(anim.T, t, joint.restT)
    const R = sampleAxes(anim.R, t, joint.restR)
    const S = sampleAxes(anim.S, t, joint.restS)
    composeLocalMat(local, T, R, joint.preRot, S)
    if (STRIP_ROOT_MOTION && j === hipsIdx) {
      local[12] = restHipsX
      local[14] = restHipsZ
    }
    matData.set(local, (f * numJoints + j) * 16)
  }
}
if (STRIP_ROOT_MOTION) console.log('Stripped root motion on Hips (XZ pinned).')

writeFileSync(OUT, Buffer.from(out))
console.log(`Wrote ${OUT} (${(out.byteLength / 1024).toFixed(1)} KB)`)

// --- Sidecar meta.json (rig hierarchy for runtime). ---

const meta = {
  source: IN,
  durationSec,
  fps: TARGET_FPS,
  numFrames,
  joints: joints.map((j) => ({
    name: j.name,
    parent: j.parent,
    // Offset in rest pose = Lcl Translation column × unit scale. Runtime
    // doesn't strictly need this for retargeting but keeps sidecar parity
    // with the DAE path.
    offset: [j.restT[0] * UNIT_SCALE, j.restT[1] * UNIT_SCALE, j.restT[2] * UNIT_SCALE],
  })),
}
writeFileSync(OUT.replace(/\.vat$/, '.meta.json'), JSON.stringify(meta, null, 2))
console.log(`Wrote ${OUT.replace(/\.vat$/, '.meta.json')}`)
