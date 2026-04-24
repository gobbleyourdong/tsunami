/**
 * Mixamo FBX → bake JSON. Offline one-shot converter.
 *
 * Reads a Mixamo FBX, extracts:
 *   - bone hierarchy (LimbNodes + parent via Connections)
 *   - rest-pose local translation per bone (Lcl Translation in Properties70)
 *   - per-frame euler rotations + translations (AnimationCurveNodes + AnimationCurves)
 *
 * Emits a JSON consumed by the browser runtime to populate our VAT buffer
 * in the same format bakeSkeletonVAT uses.
 *
 * Usage: node scripts/bake_mixamo.mjs <input.fbx> <output.json>
 * Default paths: Running.fbx from Downloads → public/mixamo_running.json
 */

import { parseBinary } from 'fbx-parser'
import { readFileSync, writeFileSync } from 'node:fs'

const FBX_TIME_UNIT = 46186158000n    // 1s in FBX time units (bigint)

const IN  = process.argv[2] ?? '/home/jb/Downloads/Running.fbx'
const OUT = process.argv[3] ?? '/home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/engine/public/mixamo_running.json'

const fbx = parseBinary(readFileSync(IN))

// --- Object map: id → node ---
const objectsNode = fbx.find((n) => n.name === 'Objects')
const objMap = new Map()
for (const obj of objectsNode.nodes ?? []) {
  objMap.set(obj.props[0], obj)
}

// --- Connections ---
// C: "OO", childId, parentId            → parent/child
// C: "OP", childId, parentId, propName  → property connection
// An object can appear as child in multiple connections (e.g. a bone is child
// of its parent bone AND of every Cluster that skins it). Store lists.
const connNode = fbx.find((n) => n.name === 'Connections')
const parentsOfChild = new Map()         // childId → Array<{parentId, propName, type}>
const parentToChildren = new Map()       // parentId → Array<{childId, propName, type}>
for (const c of connNode.nodes ?? []) {
  if (c.name !== 'C') continue
  const [type, childId, parentId, propName] = c.props
  if (!parentsOfChild.has(childId)) parentsOfChild.set(childId, [])
  parentsOfChild.get(childId).push({ parentId, propName, type })
  if (!parentToChildren.has(parentId)) parentToChildren.set(parentId, [])
  parentToChildren.get(parentId).push({ childId, propName, type })
}

// --- LimbNodes (bones) ---
const bones = []
const idToBoneIdx = new Map()
for (const [id, obj] of objMap) {
  if (obj.name !== 'Model' || obj.props[2] !== 'LimbNode') continue
  const nameFull = obj.props[1]
  const name = nameFull.replace(/^Model::/, '').replace(/^mixamorig:/, '')

  let trans = [0, 0, 0]
  let preRot = [0, 0, 0]
  const props70 = obj.nodes?.find((n) => n.name === 'Properties70')
  if (props70) {
    for (const p of props70.nodes ?? []) {
      if (p.name !== 'P') continue
      if (p.props[0] === 'Lcl Translation')
        trans = [Number(p.props[4]), Number(p.props[5]), Number(p.props[6])]
      if (p.props[0] === 'PreRotation')
        preRot = [Number(p.props[4]), Number(p.props[5]), Number(p.props[6])]
    }
  }

  idToBoneIdx.set(id, bones.length)
  bones.push({ id, name, translation: trans, preRotation: preRot, parentIdx: -1 })
}

// Wire parents: find the unique OO connection where this bone is the child
// AND the other end is either another bone or the scene root (0).
for (const bone of bones) {
  const conns = parentsOfChild.get(bone.id) ?? []
  for (const { parentId, type } of conns) {
    if (type !== 'OO') continue
    if (parentId === 0) { bone.parentIdx = -1; break }          // root
    const parentIdx = idToBoneIdx.get(parentId)
    if (parentIdx !== undefined) { bone.parentIdx = parentIdx; break }
  }
}

// --- Animation: AnimationCurveNode bound to each bone's "Lcl Rotation" + "Lcl Translation" ---
// For each bone (by id), collect its R / T AnimationCurveNode ids.
// Must iterate all connections and filter — the curveNode appears as child
// in multiple conns (layer AND bone-property binding).
const boneAnims = new Map()
for (const c of connNode.nodes ?? []) {
  if (c.name !== 'C' || c.props[0] !== 'OP') continue
  const [, childId, parentId, propName] = c.props
  const childObj = objMap.get(childId)
  if (!childObj || childObj.name !== 'AnimationCurveNode') continue
  if (!idToBoneIdx.has(parentId)) continue
  const entry = boneAnims.get(parentId) ?? {}
  if (propName === 'Lcl Rotation')    entry.R = childId
  if (propName === 'Lcl Translation') entry.T = childId
  if (propName === 'Lcl Scaling')     entry.S = childId
  boneAnims.set(parentId, entry)
}

// Extract all AnimationCurve data once (cached), then look up by id.
const curveCache = new Map()  // curveId → { times: Float64Array, values: Float64Array }
for (const [id, obj] of objMap) {
  if (obj.name !== 'AnimationCurve') continue
  const keyTimeNode = obj.nodes?.find((n) => n.name === 'KeyTime')
  const keyValNode  = obj.nodes?.find((n) => n.name === 'KeyValueFloat')
  if (!keyTimeNode || !keyValNode) continue
  const rawTimes = keyTimeNode.props[0]   // BigInt64Array-ish or number[]
  const times = new Float64Array(rawTimes.length)
  for (let i = 0; i < rawTimes.length; i++) {
    const raw = rawTimes[i]
    times[i] = typeof raw === 'bigint' ? Number(raw) / Number(FBX_TIME_UNIT) : raw / Number(FBX_TIME_UNIT)
  }
  const values = new Float64Array(keyValNode.props[0])
  curveCache.set(id, { times, values })
}

// Map curveNodeId → {x, y, z} curve ids.
const curveNodeChannels = new Map()
for (const [id, obj] of objMap) {
  if (obj.name !== 'AnimationCurveNode') continue
  const channels = {}
  const children = parentToChildren.get(id) ?? []
  for (const { childId, propName } of children) {
    const curveObj = objMap.get(childId)
    if (!curveObj || curveObj.name !== 'AnimationCurve') continue
    if (propName === 'd|X') channels.x = childId
    if (propName === 'd|Y') channels.y = childId
    if (propName === 'd|Z') channels.z = childId
  }
  curveNodeChannels.set(id, channels)
}

function sampleCurve(curveId, t) {
  if (curveId === undefined) return 0
  const c = curveCache.get(curveId)
  if (!c || c.times.length === 0) return 0
  const { times, values } = c
  if (t <= times[0]) return values[0]
  if (t >= times[times.length - 1]) return values[values.length - 1]
  // Binary search would be cleaner, linear is fine for small tracks.
  for (let i = 0; i < times.length - 1; i++) {
    if (t <= times[i + 1]) {
      const a = (t - times[i]) / (times[i + 1] - times[i])
      return values[i] * (1 - a) + values[i + 1] * a
    }
  }
  return values[values.length - 1]
}

function sampleNode(nodeId, t, fallback) {
  if (nodeId === undefined) return fallback
  const ch = curveNodeChannels.get(nodeId)
  if (!ch) return fallback
  return [
    ch.x !== undefined ? sampleCurve(ch.x, t) : fallback[0],
    ch.y !== undefined ? sampleCurve(ch.y, t) : fallback[1],
    ch.z !== undefined ? sampleCurve(ch.z, t) : fallback[2],
  ]
}

// --- Actual animation duration derived from keyframes ---
// Mixamo often sets TimeSpanStop longer than the actual loop cycle; trust
// the keyframe data instead. Also skip tiny static curves (e.g. scale
// tracks that only have one key) by requiring >1 key.
let maxKeyTime = 0
for (const { times } of curveCache.values()) {
  if (times.length > 1 && times[times.length - 1] > maxKeyTime) {
    maxKeyTime = times[times.length - 1]
  }
}
const durationSec = maxKeyTime

const FPS = 30
const NUM_FRAMES = Math.max(1, Math.round(durationSec * FPS))

console.log(`FBX:      ${IN}`)
console.log(`Duration: ${durationSec.toFixed(3)}s`)
console.log(`Baking:   ${NUM_FRAMES} frames at ${FPS}fps`)
console.log(`Bones:    ${bones.length}`)

// --- Bake poses ---
const poses = []
const DEG = Math.PI / 180
for (let f = 0; f < NUM_FRAMES; f++) {
  const t = f / FPS
  const pose = []
  for (const bone of bones) {
    const anim = boneAnims.get(bone.id) ?? {}
    const rDeg = sampleNode(anim.R, t, [0, 0, 0])
    const trans = sampleNode(anim.T, t, bone.translation)
    pose.push({
      r: [rDeg[0] * DEG, rDeg[1] * DEG, rDeg[2] * DEG],
      t: trans,
    })
  }
  poses.push(pose)
}

const output = {
  source: IN,
  fps: FPS,
  numFrames: NUM_FRAMES,
  durationSec,
  joints: bones.map((b) => ({
    name: b.name,
    parent: b.parentIdx,
    offset: b.translation,
    preRotation: b.preRotation.map((v) => v * DEG),
  })),
  poses,
}

const json = JSON.stringify(output)
writeFileSync(OUT, json)
console.log(`Wrote ${OUT}  (${(json.length / 1024).toFixed(1)} KB)`)
