/**
 * Minimal GLB (glTF 2.0 binary) loader for skeleton + animation.
 *
 * Why GLB over FBX:
 *   - Rotations stored as QUATERNIONS — no Euler-order ambiguity
 *   - inverseBindMatrices baked in → rest pose is explicit
 *   - Khronos-spec'd, consistent across Blender/Unity/Unreal/Three.js
 *
 * Parses just the subset we need: nodes, skins, animations, accessors.
 * No meshes, no materials, no textures, no morphs. ~350 lines.
 *
 * The sampler returns PRECOMPUTED 4x4 local matrices per (frame, joint),
 * bypassing Euler decomposition entirely. Uses slerp between quaternion
 * keyframes and lerp between translation keyframes.
 */

import type { Vec3 } from '../math/vec'
import type { Joint } from './skeleton'

const UNIT_SCALE = 1.0   // GLB is in meters by convention; Mixamo GLB export
                          // still ships in cm — we detect via hip height and
                          // scale conditionally below.

// --- glTF JSON schema (subset) ---

interface GLTFNode {
  name?: string
  children?: number[]
  translation?: [number, number, number]
  rotation?: [number, number, number, number]   // xyzw quaternion
  scale?: [number, number, number]
}

interface GLTFSkin {
  inverseBindMatrices?: number
  joints: number[]
  skeleton?: number
}

interface GLTFAccessor {
  bufferView: number
  byteOffset?: number
  componentType: number      // 5126 = FLOAT, 5123 = UNSIGNED_SHORT, etc.
  count: number
  type: string               // "SCALAR" | "VEC2" | "VEC3" | "VEC4" | "MAT4"
}

interface GLTFBufferView {
  buffer: number
  byteOffset?: number
  byteLength: number
}

interface GLTFAnimationSampler {
  input: number              // accessor idx for keyframe times
  output: number             // accessor idx for keyframe values
  interpolation?: 'LINEAR' | 'STEP' | 'CUBICSPLINE'
}

interface GLTFAnimationChannel {
  sampler: number
  target: { node: number; path: 'translation' | 'rotation' | 'scale' }
}

interface GLTFAnimation {
  name?: string
  samplers: GLTFAnimationSampler[]
  channels: GLTFAnimationChannel[]
}

interface GLTF {
  nodes: GLTFNode[]
  skins?: GLTFSkin[]
  animations?: GLTFAnimation[]
  accessors: GLTFAccessor[]
  bufferViews: GLTFBufferView[]
  buffers: { byteLength: number }[]
}

// --- Binary GLB container parse ---

function parseGLB(buf: ArrayBuffer): { gltf: GLTF; bin: Uint8Array } {
  const view = new DataView(buf)
  const magic = view.getUint32(0, true)
  if (magic !== 0x46546c67) throw new Error('Not a GLB file (bad magic)')
  const version = view.getUint32(4, true)
  if (version !== 2) throw new Error(`GLB version ${version} not supported (need 2)`)

  // First chunk: JSON
  let offset = 12
  const jsonLen = view.getUint32(offset, true)
  const jsonType = view.getUint32(offset + 4, true)
  if (jsonType !== 0x4e4f534a) throw new Error('First GLB chunk is not JSON')
  const jsonBytes = new Uint8Array(buf, offset + 8, jsonLen)
  const gltf = JSON.parse(new TextDecoder().decode(jsonBytes)) as GLTF
  offset += 8 + jsonLen

  // Second chunk: BIN (optional)
  let bin = new Uint8Array(0)
  if (offset < view.byteLength) {
    const binLen = view.getUint32(offset, true)
    const binType = view.getUint32(offset + 4, true)
    if (binType === 0x004e4942) {
      bin = new Uint8Array(buf, offset + 8, binLen)
    }
  }
  return { gltf, bin }
}

// --- Accessor readers ---

function accessorToFloat32(gltf: GLTF, bin: Uint8Array, idx: number): Float32Array {
  const acc = gltf.accessors[idx]
  const bv = gltf.bufferViews[acc.bufferView]
  const byteOffset = (bv.byteOffset ?? 0) + (acc.byteOffset ?? 0)
  const compCount = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 }[acc.type] ?? 1
  if (acc.componentType !== 5126) {
    throw new Error(`Accessor ${idx}: componentType ${acc.componentType} not FLOAT`)
  }
  return new Float32Array(bin.buffer, bin.byteOffset + byteOffset, acc.count * compCount)
}

// --- Quaternion + matrix helpers (SIMD-free but fine for keyframe counts) ---

function quatToMat4(out: Float32Array, q: ArrayLike<number>) {
  const x = q[0], y = q[1], z = q[2], w = q[3]
  const xx = x * x, yy = y * y, zz = z * z
  const xy = x * y, xz = x * z, yz = y * z
  const wx = w * x, wy = w * y, wz = w * z
  out[0] = 1 - 2 * (yy + zz); out[1] = 2 * (xy + wz);     out[2] = 2 * (xz - wy);     out[3] = 0
  out[4] = 2 * (xy - wz);     out[5] = 1 - 2 * (xx + zz); out[6] = 2 * (yz + wx);     out[7] = 0
  out[8] = 2 * (xz + wy);     out[9] = 2 * (yz - wx);     out[10] = 1 - 2 * (xx + yy); out[11] = 0
  out[12] = 0;                out[13] = 0;                out[14] = 0;                 out[15] = 1
}

function mat4Mul(out: Float32Array, a: Float32Array, b: Float32Array) {
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

function mat4FromTRS(out: Float32Array, t: ArrayLike<number>, r: ArrayLike<number>, s: ArrayLike<number>) {
  quatToMat4(out, r)
  // Apply scale on columns 0..2
  out[0] *= s[0]; out[1] *= s[0]; out[2] *= s[0]
  out[4] *= s[1]; out[5] *= s[1]; out[6] *= s[1]
  out[8] *= s[2]; out[9] *= s[2]; out[10] *= s[2]
  // Translation in column 3
  out[12] = t[0]; out[13] = t[1]; out[14] = t[2]; out[15] = 1
}

// --- Animation sampling ---

interface JointTrack {
  times: Float32Array
  values: Float32Array    // VEC3 or VEC4, depending on path
  interp: 'LINEAR' | 'STEP' | 'CUBICSPLINE'
  stride: number           // 3 or 4
}

interface JointAnim {
  translation?: JointTrack
  rotation?: JointTrack
  scale?: JointTrack
  rest: {
    translation: [number, number, number]
    rotation: [number, number, number, number]
    scale: [number, number, number]
  }
}

function sampleTrack(track: JointTrack, t: number, out: Float32Array) {
  const { times, values, stride } = track
  if (times.length === 0) { for (let i = 0; i < stride; i++) out[i] = 0; return }
  if (t <= times[0]) { for (let i = 0; i < stride; i++) out[i] = values[i]; return }
  const last = times.length - 1
  if (t >= times[last]) { for (let i = 0; i < stride; i++) out[i] = values[last * stride + i]; return }
  for (let i = 0; i < last; i++) {
    if (t <= times[i + 1]) {
      const a = (t - times[i]) / (times[i + 1] - times[i])
      if (stride === 4) {
        const q0 = values.subarray(i * 4, i * 4 + 4)
        const q1 = values.subarray((i + 1) * 4, (i + 1) * 4 + 4)
        quatSlerpPair(out, q0, q1, a)
      } else {
        for (let k = 0; k < stride; k++) {
          out[k] = values[i * stride + k] * (1 - a) + values[(i + 1) * stride + k] * a
        }
      }
      return
    }
  }
}

function quatSlerpPair(out: Float32Array, a: ArrayLike<number>, b: ArrayLike<number>, t: number) {
  let ax = a[0], ay = a[1], az = a[2], aw = a[3]
  let bx = b[0], by = b[1], bz = b[2], bw = b[3]
  let dot = ax * bx + ay * by + az * bz + aw * bw
  if (dot < 0) { bx = -bx; by = -by; bz = -bz; bw = -bw; dot = -dot }
  if (dot > 0.9995) {
    out[0] = ax + t * (bx - ax); out[1] = ay + t * (by - ay)
    out[2] = az + t * (bz - az); out[3] = aw + t * (bw - aw)
    const len = Math.hypot(out[0], out[1], out[2], out[3])
    out[0] /= len; out[1] /= len; out[2] /= len; out[3] /= len
    return
  }
  const theta = Math.acos(dot)
  const sin = Math.sin(theta)
  const s0 = Math.sin((1 - t) * theta) / sin
  const s1 = Math.sin(t * theta) / sin
  out[0] = s0 * ax + s1 * bx; out[1] = s0 * ay + s1 * by
  out[2] = s0 * az + s1 * bz; out[3] = s0 * aw + s1 * bw
}

// --- High-level API ---

export interface LoadedGLB {
  rig: Joint[]
  /** Precomputed local matrices: [frame][joint] = 16-float Float32Array view.
   *  Packed as one flat Float32Array of length numFrames*numJoints*16 for
   *  cache-friendly iteration; use jointMatrix(frame, joint) to read. */
  localMats: Float32Array
  numFrames: number
  fps: number
  durationSec: number
  jointMatrix(frame: number, joint: number): Float32Array
}

export async function loadGLB(
  url: string,
  opts: { fps?: number; animationIdx?: number } = {}
): Promise<LoadedGLB> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`GLB fetch failed: ${url} (${resp.status})`)
  const buf = await resp.arrayBuffer()
  return parseGLBBuffer(buf, opts)
}

/** Parse an already-loaded GLB ArrayBuffer (e.g. from drag-and-drop or
 *  File input). Same output as loadGLB but bypasses fetch — works for
 *  user-provided files without needing public/ placement. */
export function parseGLBBuffer(
  buf: ArrayBuffer,
  opts: { fps?: number; animationIdx?: number } = {}
): LoadedGLB {
  const fps = opts.fps ?? 30
  const animIdx = opts.animationIdx ?? 0

  const { gltf, bin } = parseGLB(buf)

  if (!gltf.skins || gltf.skins.length === 0) throw new Error('GLB has no skins')
  const skin = gltf.skins[0]
  const jointNodes = skin.joints

  // --- Build joint parents via reverse lookup of children arrays. ---
  const nodeToJoint = new Map<number, number>()
  for (let i = 0; i < jointNodes.length; i++) nodeToJoint.set(jointNodes[i], i)
  const parents = new Array<number>(jointNodes.length).fill(-1)
  for (let ni = 0; ni < gltf.nodes.length; ni++) {
    for (const child of gltf.nodes[ni].children ?? []) {
      const cj = nodeToJoint.get(child)
      const pj = nodeToJoint.get(ni)
      if (cj !== undefined && pj !== undefined) parents[cj] = pj
    }
  }

  // --- Rig: take the node's rest translation as the joint offset. ---
  // Detect cm-scale export (Mixamo ships GLB still in cm) from hip height.
  const hipsIdx = jointNodes.findIndex((ni) => /hips/i.test(gltf.nodes[ni].name ?? ''))
  let detectedScale = UNIT_SCALE
  if (hipsIdx >= 0) {
    const hipsT = gltf.nodes[jointNodes[hipsIdx]].translation
    if (hipsT && Math.abs(hipsT[1]) > 10) detectedScale = 0.01
  }

  const rig: Joint[] = jointNodes.map((ni, i) => {
    const node = gltf.nodes[ni]
    const t = node.translation ?? [0, 0, 0]
    const clean = (s: string) => s.replace(/^mixamorig:/, '')
    return {
      name: clean(node.name ?? `joint_${i}`),
      parent: parents[i],
      offset: [t[0] * detectedScale, t[1] * detectedScale, t[2] * detectedScale] as Vec3,
    }
  })

  // --- Animation: collect channels into a per-joint track map. ---
  if (!gltf.animations || gltf.animations.length === 0) throw new Error('GLB has no animations')
  const anim = gltf.animations[animIdx]
  const jointAnims: JointAnim[] = jointNodes.map((ni) => ({
    rest: {
      translation: [...(gltf.nodes[ni].translation ?? [0, 0, 0])] as [number, number, number],
      rotation:    [...(gltf.nodes[ni].rotation    ?? [0, 0, 0, 1])] as [number, number, number, number],
      scale:       [...(gltf.nodes[ni].scale       ?? [1, 1, 1])] as [number, number, number],
    },
  } as JointAnim))

  for (const chan of anim.channels) {
    const jointIdx = nodeToJoint.get(chan.target.node)
    if (jointIdx === undefined) continue
    const sampler = anim.samplers[chan.sampler]
    const times = accessorToFloat32(gltf, bin, sampler.input)
    const values = accessorToFloat32(gltf, bin, sampler.output)
    const stride = chan.target.path === 'rotation' ? 4 : 3
    const track: JointTrack = { times, values, stride, interp: sampler.interpolation ?? 'LINEAR' }
    if (chan.target.path === 'translation') jointAnims[jointIdx].translation = track
    else if (chan.target.path === 'rotation') jointAnims[jointIdx].rotation = track
    else if (chan.target.path === 'scale')    jointAnims[jointIdx].scale = track
  }

  // --- Duration: max keyframe time across all channels. ---
  let durationSec = 0
  for (const s of anim.samplers) {
    const times = accessorToFloat32(gltf, bin, s.input)
    if (times.length) durationSec = Math.max(durationSec, times[times.length - 1])
  }
  const numFrames = Math.max(1, Math.round(durationSec * fps))

  // --- Bake localMats[frame][joint] as flat Float32Array. ---
  const localMats = new Float32Array(numFrames * jointNodes.length * 16)
  const tmpT = new Float32Array(3)
  const tmpR = new Float32Array(4)
  const tmpS = new Float32Array(3)

  for (let f = 0; f < numFrames; f++) {
    const t = (f / numFrames) * durationSec
    for (let j = 0; j < jointNodes.length; j++) {
      const ja = jointAnims[j]
      // Translation (scaled if cm-source)
      if (ja.translation) {
        sampleTrack(ja.translation, t, tmpT)
        tmpT[0] *= detectedScale; tmpT[1] *= detectedScale; tmpT[2] *= detectedScale
      } else {
        tmpT[0] = ja.rest.translation[0] * detectedScale
        tmpT[1] = ja.rest.translation[1] * detectedScale
        tmpT[2] = ja.rest.translation[2] * detectedScale
      }
      // Rotation
      if (ja.rotation) sampleTrack(ja.rotation, t, tmpR)
      else { tmpR[0] = ja.rest.rotation[0]; tmpR[1] = ja.rest.rotation[1]; tmpR[2] = ja.rest.rotation[2]; tmpR[3] = ja.rest.rotation[3] }
      // Scale
      if (ja.scale) sampleTrack(ja.scale, t, tmpS)
      else { tmpS[0] = ja.rest.scale[0]; tmpS[1] = ja.rest.scale[1]; tmpS[2] = ja.rest.scale[2] }

      const matView = new Float32Array(localMats.buffer, localMats.byteOffset + (f * jointNodes.length + j) * 16 * 4, 16)
      mat4FromTRS(matView, tmpT, tmpR, tmpS)
    }
  }

  return {
    rig,
    localMats,
    numFrames,
    fps,
    durationSec,
    jointMatrix(frame, joint) {
      return new Float32Array(localMats.buffer, localMats.byteOffset + (frame * jointNodes.length + joint) * 16 * 4, 16)
    },
  }
}

/** Runtime loader for a pre-baked VAT binary (output of
 *  scripts/bake_vat_binary.mjs).
 *
 *  This is the SHIPPING endpoint for animation assets: no parsing, no
 *  Euler angles, no keyframe interpolation. Just `fetch → createBuffer`.
 *  The file has an 8-byte header + straight Float32Array of world
 *  matrices, already composed and parent-propagated at bake time.
 *
 *  One day: one of these files ships per animation (or one mega-file for
 *  an animation library). Runtime picks by offset. Proportion variation
 *  happens at character-render time via the skeleton shader's scale
 *  input — the VAT itself is shared across all characters using the rig.
 */
export interface LoadedVAT {
  buffer: GPUBuffer
  numFrames: number
  numJoints: number
  durationSec: number
  fps: number
  /** Rig hierarchy from sidecar .meta.json (if available). */
  rig?: Joint[]
  /** Raw local matrices (VAT2 only) — kept in CPU memory for runtime
   *  compose via createRetargetComposer. VAT1 leaves this undefined. */
  localMats?: Float32Array
  isLocal: boolean
}

export async function loadVATBinary(device: GPUDevice, url: string): Promise<LoadedVAT> {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`VAT fetch failed: ${url} (${resp.status})`)
  const buf = await resp.arrayBuffer()
  const dv = new DataView(buf)
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3))
  // VAT1 = pre-baked world matrices (legacy, no retargeting).
  // VAT2 = local matrices, runtime composes world with per-character proportions.
  if (magic !== 'VAT1' && magic !== 'VAT2') throw new Error(`Not a VAT file: got magic "${magic}"`)
  const numFrames = dv.getUint32(4, true)
  const numJoints = dv.getUint32(8, true)
  const durationSec = dv.getFloat32(12, true)
  const fps = dv.getFloat32(16, true)

  const HEADER_BYTES = 32
  const matrixBytes = buf.byteLength - HEADER_BYTES
  const buffer = device.createBuffer({
    label: `vat:${url}`,
    size: matrixBytes,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(buffer, 0, new Uint8Array(buf, HEADER_BYTES))

  // Optional sidecar .meta.json holding rig hierarchy (bone names + parents).
  let rig: Joint[] | undefined
  try {
    const metaUrl = url.replace(/\.vat$/, '.meta.json')
    const mresp = await fetch(metaUrl)
    if (mresp.ok) {
      const meta = await mresp.json()
      rig = meta.joints.map((j: { name: string; parent: number; offset?: [number, number, number] }) => ({
        name: j.name,
        parent: j.parent,
        offset: (j.offset ?? [0, 0, 0]) as Vec3,
      }))
    }
  } catch { /* sidecar optional */ }

  // For VAT2, also keep the raw local matrices in CPU memory for runtime
  // compose. For VAT1, buffer already holds world matrices — use directly.
  const localMats = magic === 'VAT2'
    ? new Float32Array(buf.slice(HEADER_BYTES))
    : undefined

  return { buffer, numFrames, numJoints, durationSec, fps, rig, localMats, isLocal: magic === 'VAT2' }
}

// --- Retargeting composer: local matrices + character scale → world matrices ---

export interface CharacterParams {
  /** Per-joint scale, indexed by rig joint index. Default: all [1,1,1]. */
  scales: Vec3[]
}

export function defaultCharacterParams(numJoints: number): CharacterParams {
  return {
    scales: Array.from({ length: numJoints }, () => [1, 1, 1] as Vec3),
  }
}

/** CPU-side retargeting composer. Each call to update(frameIdx) walks the
 *  rig hierarchy composing per-joint world matrices from local animation
 *  matrices + character proportion scales, then uploads to the GPU buffer.
 *
 *  Cost: O(numJoints) per update. 65 matrix multiplies + 65 scales ≈ 6500
 *  ops/frame on CPU — trivial. Runs once per character per frame. */
export interface RetargetComposer {
  update(frameIdx: number, params: CharacterParams): void
  buffer: GPUBuffer
  numInstances: number
  numFrames: number
  /** CPU-side mirror of the per-frame world matrix array after the most
   *  recent update(). 16 floats per joint, column-major. Mutating this
   *  array is not supported — treat it as read-only view of what's on
   *  the GPU. Exposed so the demo can compute CPU-side bounding volumes
   *  (cache invalidation, BVH culling) without a GPU readback. */
  worldMatrices: Float32Array
}

export function createRetargetComposer(
  device: GPUDevice,
  vat: LoadedVAT,
): RetargetComposer {
  if (!vat.localMats || !vat.rig) {
    throw new Error('createRetargetComposer requires VAT2 with local matrices + rig')
  }
  const localMats = vat.localMats
  const rig = vat.rig
  const numJoints = vat.numJoints
  const numFrames = vat.numFrames

  const worldData = new Float32Array(numJoints * 16)
  // compositionMats: per-joint parent-chained world matrices using PURE
  // rotation columns + scaled col3. These are the matrices we propagate
  // down the hierarchy so scale never compounds.
  const compositionMats: Float32Array[] = Array.from({ length: numJoints }, () => new Float32Array(16))
  const scaledLocal = new Float32Array(16)
  const displayMat = new Float32Array(16)

  function mul(out: Float32Array, a: Float32Array, b: Float32Array) {
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

  return {
    buffer: vat.buffer,         // reuse the same GPU buffer — writeBuffer swaps contents
    numInstances: numJoints,
    numFrames,
    worldMatrices: worldData,   // same array we upload; CPU readers get the latest
    update(frameIdx, params) {
      const base = (frameIdx % numFrames) * numJoints * 16
      for (let j = 0; j < numJoints; j++) {
        const s = params.scales[j] ?? [1, 1, 1]
        const src = base + j * 16
        const parent = rig[j].parent
        const isRoot = parent < 0

        // Composition path (feeds children, prevents scale cascade):
        //   rotation columns UNCHANGED, col3 (translation) × s_j.
        // Scaling own col3 means "this bone's distance from parent is
        // s_j longer" — head moves up when head is scaled 2×. Leaving
        // rotation columns pure means children do not inherit any scale
        // amplification through the hierarchy (no double-scale).
        //
        // ROOT EXCEPTION: the root joint's col3 is the rig's WORLD
        // position (e.g. Hips at ~1m off the ground), not a bone-length
        // offset from a parent. Scaling it translates the whole rig.
        // Leave the root's col3 alone.
        scaledLocal[0]  = localMats[src + 0]
        scaledLocal[1]  = localMats[src + 1]
        scaledLocal[2]  = localMats[src + 2]
        scaledLocal[3]  = localMats[src + 3]
        scaledLocal[4]  = localMats[src + 4]
        scaledLocal[5]  = localMats[src + 5]
        scaledLocal[6]  = localMats[src + 6]
        scaledLocal[7]  = localMats[src + 7]
        scaledLocal[8]  = localMats[src + 8]
        scaledLocal[9]  = localMats[src + 9]
        scaledLocal[10] = localMats[src + 10]
        scaledLocal[11] = localMats[src + 11]
        scaledLocal[12] = isRoot ? localMats[src + 12] : localMats[src + 12] * s[0]
        scaledLocal[13] = isRoot ? localMats[src + 13] : localMats[src + 13] * s[1]
        scaledLocal[14] = isRoot ? localMats[src + 14] : localMats[src + 14] * s[2]
        scaledLocal[15] = localMats[src + 15]

        const comp = compositionMats[j]
        if (isRoot) comp.set(scaledLocal)
        else mul(comp, compositionMats[parent], scaledLocal)

        // Display path (what the renderer reads): composition × diag(s).
        // Only the joint's OWN scale affects its rendered cube size; since
        // this is a post-multiply against the already-composed world
        // matrix, child display matrices don't see parent scale twice.
        displayMat[0]  = comp[0]  * s[0]
        displayMat[1]  = comp[1]  * s[0]
        displayMat[2]  = comp[2]  * s[0]
        displayMat[3]  = comp[3]  * s[0]
        displayMat[4]  = comp[4]  * s[1]
        displayMat[5]  = comp[5]  * s[1]
        displayMat[6]  = comp[6]  * s[1]
        displayMat[7]  = comp[7]  * s[1]
        displayMat[8]  = comp[8]  * s[2]
        displayMat[9]  = comp[9]  * s[2]
        displayMat[10] = comp[10] * s[2]
        displayMat[11] = comp[11] * s[2]
        displayMat[12] = comp[12]
        displayMat[13] = comp[13]
        displayMat[14] = comp[14]
        displayMat[15] = comp[15]
        worldData.set(displayMat, j * 16)
      }
      device.queue.writeBuffer(vat.buffer, 0, worldData)
    },
  }
}

/** Matrix-level VAT baker. Takes the precomputed local matrices from
 *  loadGLB and composes parent chains into world-space matrices (what the
 *  skeleton shader expects). Skips the Euler path entirely — no rotation-
 *  order ambiguity, no FBX quirks, just T·R·S mat4 multiplications. */
export function bakeSkeletonVATFromMatrices(
  device: GPUDevice,
  rig: Joint[],
  numFrames: number,
  localMats: Float32Array,
  scales: Vec3[],
  existing?: GPUBuffer
): { buffer: GPUBuffer; numInstances: number; numFrames: number } {
  const numJoints = rig.length
  const worldData = new Float32Array(numFrames * numJoints * 16)
  const worldMats: Float32Array[] = new Array(numJoints)
  for (let j = 0; j < numJoints; j++) {
    worldMats[j] = new Float32Array(16)
  }
  const tmp = new Float32Array(16)

  for (let f = 0; f < numFrames; f++) {
    for (let j = 0; j < numJoints; j++) {
      const localView = new Float32Array(localMats.buffer, localMats.byteOffset + (f * numJoints + j) * 16 * 4, 16)

      // Optional per-joint proportion scale (copy into tmp, scale cols 0..2).
      const s = scales[j] ?? [1, 1, 1]
      const hasScale = s[0] !== 1 || s[1] !== 1 || s[2] !== 1
      const srcMat = hasScale ? tmp : localView
      if (hasScale) {
        tmp.set(localView)
        tmp[0] *= s[0]; tmp[1] *= s[0]; tmp[2] *= s[0]
        tmp[4] *= s[1]; tmp[5] *= s[1]; tmp[6] *= s[1]
        tmp[8] *= s[2]; tmp[9] *= s[2]; tmp[10] *= s[2]
      }

      if (rig[j].parent < 0) {
        worldMats[j].set(srcMat)
      } else {
        mat4Mul(worldMats[j], worldMats[rig[j].parent], srcMat)
      }
      worldData.set(worldMats[j], (f * numJoints + j) * 16)
    }
  }

  let buffer: GPUBuffer
  if (existing) {
    buffer = existing
    device.queue.writeBuffer(buffer, 0, worldData)
  } else {
    buffer = device.createBuffer({
      label: 'glb-skeleton-vat',
      size: worldData.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    })
    device.queue.writeBuffer(buffer, 0, worldData)
  }

  return { buffer, numInstances: numJoints, numFrames }
}
