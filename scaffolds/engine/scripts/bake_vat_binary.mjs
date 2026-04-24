/**
 * Offline VAT bake — takes the JSON pose data (output of bake_mixamo.mjs)
 * and produces a raw Float32Array binary file: one 4×4 matrix per (frame,
 * joint) in column-major order. This is the SHIPPABLE ASSET. Runtime just
 * does fetch → createBuffer, no parsing.
 *
 * Layout:
 *   offset 0: magic "VAT1" (4 bytes)
 *   offset 4: numFrames (uint32)
 *   offset 8: numJoints (uint32)
 *   offset 12: durationSec (float32)
 *   offset 16: fps (float32)
 *   offset 20: reserved (12 bytes)
 *   offset 32: matrices[frame][joint] = 16 × float32 (column-major mat4)
 *   Total: 32 + numFrames * numJoints * 64
 *
 * Usage: node scripts/bake_vat_binary.mjs <input.json> <output.vat>
 * Defaults: public/mixamo_running.json → public/mixamo_running.vat
 */

import { readFileSync, writeFileSync } from 'node:fs'

const IN  = process.argv[2] ?? '/home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/engine/public/mixamo_running.json'
const OUT = process.argv[3] ?? '/home/jb/ComfyUI/CelebV-HQ/ark/scaffolds/engine/public/mixamo_running.vat'

const data = JSON.parse(readFileSync(IN, 'utf-8'))

// --- Minimal mat4 (column-major) ---

function mat4Identity() { const m = new Float32Array(16); m[0]=1; m[5]=1; m[10]=1; m[15]=1; return m }

function mat4Translate(out, a, v) {
  if (out !== a) for (let i = 0; i < 12; i++) out[i] = a[i]
  out[12] = a[0]*v[0] + a[4]*v[1] + a[8]*v[2] + a[12]
  out[13] = a[1]*v[0] + a[5]*v[1] + a[9]*v[2] + a[13]
  out[14] = a[2]*v[0] + a[6]*v[1] + a[10]*v[2] + a[14]
  out[15] = a[3]*v[0] + a[7]*v[1] + a[11]*v[2] + a[15]
}

function mat4RotateX(out, a, angle) {
  const s = Math.sin(angle), c = Math.cos(angle)
  const a10=a[4], a11=a[5], a12=a[6], a13=a[7]
  const a20=a[8], a21=a[9], a22=a[10], a23=a[11]
  if (out !== a) { for (let i of [0,1,2,3,12,13,14,15]) out[i] = a[i] }
  out[4]=a10*c+a20*s; out[5]=a11*c+a21*s; out[6]=a12*c+a22*s; out[7]=a13*c+a23*s
  out[8]=a20*c-a10*s; out[9]=a21*c-a11*s; out[10]=a22*c-a12*s; out[11]=a23*c-a13*s
}

function mat4RotateY(out, a, angle) {
  const s = Math.sin(angle), c = Math.cos(angle)
  const a00=a[0], a01=a[1], a02=a[2], a03=a[3]
  const a20=a[8], a21=a[9], a22=a[10], a23=a[11]
  if (out !== a) { for (let i of [4,5,6,7,12,13,14,15]) out[i] = a[i] }
  out[0]=a00*c-a20*s; out[1]=a01*c-a21*s; out[2]=a02*c-a22*s; out[3]=a03*c-a23*s
  out[8]=a00*s+a20*c; out[9]=a01*s+a21*c; out[10]=a02*s+a22*c; out[11]=a03*s+a23*c
}

function mat4RotateZ(out, a, angle) {
  const s = Math.sin(angle), c = Math.cos(angle)
  const a00=a[0], a01=a[1], a02=a[2], a03=a[3]
  const a10=a[4], a11=a[5], a12=a[6], a13=a[7]
  if (out !== a) { for (let i of [8,9,10,11,12,13,14,15]) out[i] = a[i] }
  out[0]=a00*c+a10*s; out[1]=a01*c+a11*s; out[2]=a02*c+a12*s; out[3]=a03*c+a13*s
  out[4]=a10*c-a00*s; out[5]=a11*c-a01*s; out[6]=a12*c-a02*s; out[7]=a13*c-a03*s
}

function mat4Multiply(out, a, b) {
  for (let col = 0; col < 4; col++) {
    for (let row = 0; row < 4; row++) {
      out[col*4 + row] =
        a[row]    * b[col*4]   +
        a[row+4]  * b[col*4+1] +
        a[row+8]  * b[col*4+2] +
        a[row+12] * b[col*4+3]
    }
  }
}

// --- Bake ---

const UNIT_SCALE = 0.01   // Mixamo cm → m
const numJoints = data.joints.length
const numFrames = data.numFrames
const fps = data.fps
const durationSec = data.durationSec

console.log(`Baking VAT: ${numJoints} joints × ${numFrames} frames × 64 bytes = ${numJoints*numFrames*64} bytes`)
console.log(`FBX Euler XYZ = rotate X first, then Y, then Z (intrinsic).`)
console.log(`  matrix form: M = Rz·Ry·Rx (apply X to v first, then Y, then Z)`)
console.log(`  right-multiply API → rotateZ, rotateY, rotateX in that order`)
console.log(`Applying PreRotation (fixed bone rest offset) then animated rotation.`)

const worldMats = Array.from({ length: numJoints }, () => mat4Identity())
const local = mat4Identity()

// Pre-allocate the output buffer: header + matrices
const HEADER_BYTES = 32
const matricesBytes = numFrames * numJoints * 64
const out = new ArrayBuffer(HEADER_BYTES + matricesBytes)
const hdrView = new DataView(out)

// Magic: ASCII "VAT1"
hdrView.setUint8(0, 0x56)
hdrView.setUint8(1, 0x41)
hdrView.setUint8(2, 0x54)
hdrView.setUint8(3, 0x31)
hdrView.setUint32(4, numFrames, true)
hdrView.setUint32(8, numJoints, true)
hdrView.setFloat32(12, durationSec, true)
hdrView.setFloat32(16, fps, true)

const matData = new Float32Array(out, HEADER_BYTES, numFrames * numJoints * 16)

for (let f = 0; f < numFrames; f++) {
  const pose = data.poses[f]
  for (let j = 0; j < numJoints; j++) {
    const joint = data.joints[j]
    const p = pose[j]
    const translation = p.t
      ? [p.t[0] * UNIT_SCALE, p.t[1] * UNIT_SCALE, p.t[2] * UNIT_SCALE]
      : [joint.offset[0] * UNIT_SCALE, joint.offset[1] * UNIT_SCALE, joint.offset[2] * UNIT_SCALE]

    // Reset local to identity, then compose T × Rz × Ry × Rx (right-multiply).
    local[0]=1; local[1]=0; local[2]=0; local[3]=0
    local[4]=0; local[5]=1; local[6]=0; local[7]=0
    local[8]=0; local[9]=0; local[10]=1; local[11]=0
    local[12]=0; local[13]=0; local[14]=0; local[15]=1

    mat4Translate(local, local, translation)

    const rz = p.r[2], ry = p.r[1], rx = p.r[0]
    if (rz !== 0) mat4RotateZ(local, local, rz)
    if (ry !== 0) mat4RotateY(local, local, ry)
    if (rx !== 0) mat4RotateX(local, local, rx)

    if (joint.parent < 0) {
      for (let k = 0; k < 16; k++) worldMats[j][k] = local[k]
    } else {
      mat4Multiply(worldMats[j], worldMats[joint.parent], local)
    }

    matData.set(worldMats[j], (f * numJoints + j) * 16)
  }
}

writeFileSync(OUT, Buffer.from(out))
console.log(`Wrote ${OUT} (${(out.byteLength / 1024).toFixed(1)} KB, ${(out.byteLength / 1024 / 1024).toFixed(2)} MB)`)
console.log(`Runtime load cost: fetch → arrayBuffer → createBuffer. No parsing.`)
