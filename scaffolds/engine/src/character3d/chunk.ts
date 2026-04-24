/**
 * Chunk-based skinned-mesh system — the successor to cube-per-joint.
 *
 * DESIGN
 * ======
 * A character is a set of CHUNKS. Each chunk is an independent skinned
 * mesh with its own sub-skeleton, its own UV atlas, and its own palette
 * slot(s). Chunks meet at hard boundaries (neck, shoulder, hip) — there
 * is no cross-chunk vertex deformation. This is the classic pixel/sprite
 * rigging approach (Octopath Traveler, Final Fantasy Tactics, Muramasa,
 * Dead Cells) as opposed to continuous-skin AAA character rigs.
 *
 * WHY DISCONNECTED CHUNKS FOR SPRITE OUTPUT
 * -----------------------------------------
 *   1. Clean per-chunk UV projections (cylindrical on limbs/torso, planar
 *      or spherical on head) — no seams crossing chunk boundaries.
 *   2. Dismemberment: hide the chunk mesh + truncate its sub-skeleton.
 *      No neighbor re-weighting; the neighbor's mesh doesn't reach across.
 *   3. Equipment swap at chunk granularity (head/armor/boots).
 *   4. Authoring: each chunk can be authored at its own fidelity without
 *      gradient-blending constraints.
 *   5. Damage decals: swap a chunk's texture to a bloody/burnt variant.
 *
 * WHERE THIS REPLACES THE CUBE SYSTEM
 * -----------------------------------
 *   - `chibiBoneDisplayMats` returns one display matrix per joint, and
 *     `skeleton_renderer` instance-draws a single unit cube at each. The
 *     chunk system instead has one mesh per CHUNK, not per joint — a
 *     chunk spans many joints (e.g. Head chunk spans Neck + Head +
 *     HeadTop_End + face features).
 *   - `chibiMaterial` assigns one palette index per joint. The chunk
 *     system assigns palette indices per chunk (and optionally per-vertex
 *     within a chunk if e.g. the head chunk has distinct eye/mouth regions
 *     that should recolor independently).
 *
 * MIGRATION PATH (incremental, chunk-at-a-time)
 * ---------------------------------------------
 *   Phase A  types + proc-gen primitives (this file)
 *   Phase B  chunk_renderer.ts — a skinned vertex shader pipeline
 *            running alongside the existing cube skeleton_renderer
 *   Phase C  Head chunk migration — proc-gen capsule mesh rigidly skinned
 *            to the Head joint; cube Head suppressed
 *   Phase D  Real skinning — within the Head chunk, verts weighted to
 *            Head + Neck + face sub-bones so jaw-drop actually deforms
 *   Phase E  Cylindrical UVs computed at chunk-creation time; UV atlas
 *            generation; start painting per-chunk textures
 *   Phase F  Migrate remaining chunks: torso, arms, legs
 *
 * The host rig (Mixamo 65-bone) is UNCHANGED. Chunks reference existing
 * joint indices. Virtual joints (face/hair/accessories/body parts) stay
 * as-is because they're part of the rig; chunks are a DISPLAY concern.
 */

import type { Joint } from './skeleton'

/** A skinned mesh segment attached to a sub-skeleton. */
export interface ChunkMesh {
  name: string
  /** Tightly-packed vertex buffer. Stride = 8 floats: position(3) + normal(3) + uv(2). */
  vertices: Float32Array
  /** Triangle indices, uint16 unless vertex count > 65535. */
  indices: Uint16Array | Uint32Array
  /** Per-vertex bone weight (up to 4 non-zero weights). Stride = 4 floats. */
  weights: Float32Array
  /** Per-vertex bone indices INTO THE HOST RIG. Stride = 4 uint32 (or uint8 packed). */
  boneIndices: Uint32Array
  /** Palette slot for uniform per-chunk recolor. When per-vertex recolor
   *  is needed (eyes, mouth within head chunk), encode it in a second
   *  palette-index attribute; kept out of v1 for simplicity. */
  paletteSlot: number
  /** The joint whose world matrix anchors the chunk in space when all
   *  vertex weights point at a single bone. Used as a fallback + for
   *  bounds/culling; fully-skinned chunks don't strictly need it. */
  parentJoint: string
}

// --- Vertex layout helpers ---
export const VERTEX_STRIDE = 8   // px, py, pz, nx, ny, nz, u, v

function pushVertex(
  verts: number[], x: number, y: number, z: number,
  nx: number, ny: number, nz: number, u: number, v: number
) {
  verts.push(x, y, z, nx, ny, nz, u, v)
}

// --- Procedural primitives ---
// These generate clean-topology meshes we can use as stand-ins while we
// figure out real mesh authoring. A capsule is the natural head shape; a
// cylinder is natural for limbs/torso. Cylindrical UVs are produced at
// generation time so the mesh can be textured immediately.

/**
 * Axis-aligned box with 24 verts (6 faces × 4 verts) so each face has
 * distinct UVs and flat normals. Used as a direct cube-replacement when
 * we want to start the chunk renderer without full skinning.
 */
export function makeBoxMesh(halfExtents: [number, number, number]): { vertices: Float32Array; indices: Uint16Array } {
  const [hx, hy, hz] = halfExtents
  const v: number[] = []
  // +X face (n = +X), UV = ZY-plane wrap
  pushVertex(v,  hx, -hy, -hz,  1, 0, 0, 0, 0)
  pushVertex(v,  hx, -hy,  hz,  1, 0, 0, 1, 0)
  pushVertex(v,  hx,  hy,  hz,  1, 0, 0, 1, 1)
  pushVertex(v,  hx,  hy, -hz,  1, 0, 0, 0, 1)
  // -X face
  pushVertex(v, -hx, -hy,  hz, -1, 0, 0, 0, 0)
  pushVertex(v, -hx, -hy, -hz, -1, 0, 0, 1, 0)
  pushVertex(v, -hx,  hy, -hz, -1, 0, 0, 1, 1)
  pushVertex(v, -hx,  hy,  hz, -1, 0, 0, 0, 1)
  // +Y face (top)
  pushVertex(v, -hx,  hy,  hz, 0, 1, 0, 0, 0)
  pushVertex(v,  hx,  hy,  hz, 0, 1, 0, 1, 0)
  pushVertex(v,  hx,  hy, -hz, 0, 1, 0, 1, 1)
  pushVertex(v, -hx,  hy, -hz, 0, 1, 0, 0, 1)
  // -Y face (bottom)
  pushVertex(v, -hx, -hy, -hz, 0, -1, 0, 0, 0)
  pushVertex(v,  hx, -hy, -hz, 0, -1, 0, 1, 0)
  pushVertex(v,  hx, -hy,  hz, 0, -1, 0, 1, 1)
  pushVertex(v, -hx, -hy,  hz, 0, -1, 0, 0, 1)
  // +Z face (front)
  pushVertex(v, -hx, -hy,  hz, 0, 0, 1, 0, 0)
  pushVertex(v,  hx, -hy,  hz, 0, 0, 1, 1, 0)
  pushVertex(v,  hx,  hy,  hz, 0, 0, 1, 1, 1)
  pushVertex(v, -hx,  hy,  hz, 0, 0, 1, 0, 1)
  // -Z face (back)
  pushVertex(v,  hx, -hy, -hz, 0, 0, -1, 0, 0)
  pushVertex(v, -hx, -hy, -hz, 0, 0, -1, 1, 0)
  pushVertex(v, -hx,  hy, -hz, 0, 0, -1, 1, 1)
  pushVertex(v,  hx,  hy, -hz, 0, 0, -1, 0, 1)
  const indices = new Uint16Array(6 * 6)
  for (let face = 0; face < 6; face++) {
    const b = face * 4
    const o = face * 6
    indices[o + 0] = b + 0; indices[o + 1] = b + 1; indices[o + 2] = b + 2
    indices[o + 3] = b + 0; indices[o + 4] = b + 2; indices[o + 5] = b + 3
  }
  return { vertices: new Float32Array(v), indices }
}

/**
 * Capsule (cylinder with hemisphere caps) — natural head shape for an
 * upright character. Oriented along +Y. Cylindrical UVs around the body
 * (u = angle/2π, v = y/height), caps continue the v mapping.
 *
 * `radius` is the cylinder radius; `length` is the straight section
 * between the two hemispheres (total height = length + 2*radius).
 */
export function makeCapsuleMesh(
  radius: number,
  length: number,
  radialSegments = 12,
  capRings = 4,
): { vertices: Float32Array; indices: Uint16Array } {
  const v: number[] = []
  const idx: number[] = []
  const h = length / 2   // half-cylinder length
  const totalH = length + 2 * radius
  const toV = (y: number) => (y + (totalH / 2)) / totalH   // world-y → [0,1]

  const verticesPerRing = radialSegments + 1   // duplicate seam vertex for UV continuity

  // --- Bottom hemisphere ---
  for (let r = 0; r <= capRings; r++) {
    const phi = (r / capRings) * (Math.PI / 2)   // 0 (equator) → π/2 (pole)
    const ringY = -h - radius * Math.sin(phi)
    const ringR = radius * Math.cos(phi)
    for (let s = 0; s < verticesPerRing; s++) {
      const theta = (s / radialSegments) * Math.PI * 2
      const cx = Math.cos(theta), sx = Math.sin(theta)
      const x = ringR * cx, z = ringR * sx
      const nx = x / radius, ny = (ringY - (-h)) / radius, nz = z / radius
      const len = Math.hypot(nx, ny, nz) || 1
      pushVertex(v, x, ringY, z, nx / len, ny / len, nz / len, s / radialSegments, toV(ringY))
    }
  }
  // --- Cylinder middle (2 rings: bottom at y=-h, top at y=+h) ---
  for (const ringY of [-h, h]) {
    for (let s = 0; s < verticesPerRing; s++) {
      const theta = (s / radialSegments) * Math.PI * 2
      const cx = Math.cos(theta), sx = Math.sin(theta)
      pushVertex(v, radius * cx, ringY, radius * sx, cx, 0, sx, s / radialSegments, toV(ringY))
    }
  }
  // --- Top hemisphere ---
  for (let r = 0; r <= capRings; r++) {
    const phi = (r / capRings) * (Math.PI / 2)
    const ringY = h + radius * Math.sin(phi)
    const ringR = radius * Math.cos(phi)
    for (let s = 0; s < verticesPerRing; s++) {
      const theta = (s / radialSegments) * Math.PI * 2
      const cx = Math.cos(theta), sx = Math.sin(theta)
      const x = ringR * cx, z = ringR * sx
      const nx = x / radius, ny = (ringY - h) / radius, nz = z / radius
      const len = Math.hypot(nx, ny, nz) || 1
      pushVertex(v, x, ringY, z, nx / len, ny / len, nz / len, s / radialSegments, toV(ringY))
    }
  }

  const totalRings = (capRings + 1) + 2 + (capRings + 1)   // bottom cap + cyl + top cap
  for (let r = 0; r < totalRings - 1; r++) {
    const a = r * verticesPerRing
    const b = (r + 1) * verticesPerRing
    for (let s = 0; s < radialSegments; s++) {
      idx.push(a + s, b + s, b + s + 1)
      idx.push(a + s, b + s + 1, a + s + 1)
    }
  }
  return { vertices: new Float32Array(v), indices: new Uint16Array(idx) }
}

/**
 * Build a ChunkMesh with all verts rigidly weighted to a single joint.
 * This is the simplest skinning case — the whole chunk moves with one
 * bone. Phase D will blend across multiple bones for real deformation.
 */
export function rigidChunk(
  name: string,
  mesh: { vertices: Float32Array; indices: Uint16Array },
  parentJoint: string,
  parentJointIdx: number,
  paletteSlot: number,
): ChunkMesh {
  const vertCount = mesh.vertices.length / VERTEX_STRIDE
  const weights = new Float32Array(vertCount * 4)
  const boneIndices = new Uint32Array(vertCount * 4)
  for (let i = 0; i < vertCount; i++) {
    weights[i * 4 + 0] = 1      // full weight on the anchor bone
    boneIndices[i * 4 + 0] = parentJointIdx
  }
  return {
    name,
    vertices: mesh.vertices,
    indices: mesh.indices,
    weights,
    boneIndices,
    paletteSlot,
    parentJoint,
  }
}

// --- Default chunk set (used as we migrate off the cube system) ---
// Chunks are LOOKED UP by joint name at creation time, then bound to
// the joint index for that character's rig. Dimensions tuned to the
// current chibi cube sizing so the transition is visually continuous.
export function defaultChunks(rig: Joint[]): ChunkMesh[] {
  const idxOf = (name: string) => rig.findIndex((j) => j.name === name)
  const chunks: ChunkMesh[] = []
  const headIdx = idxOf('Head')
  if (headIdx >= 0) {
    // Head chunk — capsule tuned to the current cube (half-extents
    // [0.19, 0.21, 0.19]). Capsule radius ≈ 0.19, length ≈ 0.04 (short
    // cylinder + two hemispheres = ~0.42 total height, matches cube Y).
    const mesh = makeCapsuleMesh(0.19, 0.04, 14, 4)
    chunks.push(rigidChunk('HeadChunk', mesh, 'Head', headIdx, 2))   // slot 2 = skin
  }
  return chunks
}
