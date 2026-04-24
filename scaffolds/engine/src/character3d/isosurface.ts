/**
 * SDF → polygonal mesh via Surface Nets (a.k.a. Naive Surface Nets).
 *
 * We use surface nets rather than classic marching cubes because:
 *   - ~100 lines vs. MC's 256-entry edge+tri tables
 *   - Produces quads (→ 2 tris), uniform vertex density
 *   - Output meshes pixelize cleanly at our target resolutions (24²–80²)
 *   - Organic SDFs (face, rocks) don't benefit from MC's extra precision
 *     once everything gets quantized through BPAD / the pose cache
 *
 * Per the SDF-as-bake thesis, the OUTPUT of this file is the data fed
 * to the live renderer: a skinned mesh with per-vertex palette slot and
 * bone binding. The renderer then stays identical to what it was before;
 * only the asset-authoring substrate has changed.
 */

import type { Vec3 } from '../math/vec'
import { gradient, normalize, type SDF } from './sdf'

/** One primitive within a ChunkSpec: its shape, the palette slot vertices
 *  on its surface should take, and the rig joint that skins it. */
export interface SDFPrimitive {
  sdf: SDF
  paletteSlot: number
  /** Joint name — resolved to index at bake time against the character rig. */
  parentJoint: string
}

/** A character/prop region's authored spec — composed SDF with palette
 *  and rig bindings, plus a bounding box for the MC sampling grid. */
export interface ChunkSpec {
  name: string
  primitives: SDFPrimitive[]
  /** Axis-aligned bbox to sample. Should bound the union of primitives. */
  bbox: [Vec3, Vec3]
}

/** Output of the bake — ready to drop into the skinned renderer. */
export interface BakedMesh {
  /** Interleaved per-vertex: px py pz nx ny nz paletteIdx boneIdx. */
  vertices: Float32Array
  indices: Uint32Array
  /** Parallel to vertices; name of the parent joint for each (referenced
   *  by boneIdx). Enables the host to look up joint indices in its rig. */
  jointNames: string[]
}

const VERTEX_FLOATS = 8   // px py pz nx ny nz paletteSlot boneIdx

/** Evaluate the composed SDF at p: return the NEAREST-surface distance
 *  along with the primitive that owned it (for palette + bone tagging).
 *  This is min-of-distances — standard SDF union semantics. */
function evalNearest(
  prims: SDFPrimitive[],
  p: Vec3,
): { dist: number; primIdx: number } {
  let best = Infinity
  let bestIdx = 0
  for (let i = 0; i < prims.length; i++) {
    const d = prims[i].sdf(p)
    if (d < best) { best = d; bestIdx = i }
  }
  return { dist: best, primIdx: bestIdx }
}

/** Compound SDF for normal-gradient sampling (primitive-agnostic). */
function compoundSDF(prims: SDFPrimitive[]): SDF {
  return (p) => {
    let d = Infinity
    for (const pr of prims) {
      const di = pr.sdf(p)
      if (di < d) d = di
    }
    return d
  }
}

/** Surface Nets: grid-sample the SDF, place one vertex inside each cell
 *  whose corners straddle the surface, then connect vertices by emitting
 *  quads along each sign-changing edge.
 *
 *  `cellSize` controls resolution — 0.02m gives ~32 cells across a 64cm
 *  face, plenty for chibi-tier output. Halving doubles grid count in
 *  each axis so bake cost is O(N³). Stay coarse unless you see artifacts.
 */
export function bakeIsosurface(spec: ChunkSpec, cellSize: number): BakedMesh {
  const [bmin, bmax] = spec.bbox
  const nx = Math.max(2, Math.ceil((bmax[0] - bmin[0]) / cellSize))
  const ny = Math.max(2, Math.ceil((bmax[1] - bmin[1]) / cellSize))
  const nz = Math.max(2, Math.ceil((bmax[2] - bmin[2]) / cellSize))

  // Sample SDF at every grid corner (a 3D scalar field).
  const gridSize = (nx + 1) * (ny + 1) * (nz + 1)
  const field = new Float32Array(gridSize)
  const primAt = new Int32Array(gridSize)
  const compound = compoundSDF(spec.primitives)
  const cIdx = (i: number, j: number, k: number) => i + (nx + 1) * (j + (ny + 1) * k)
  for (let k = 0; k <= nz; k++) {
    const z = bmin[2] + k * cellSize
    for (let j = 0; j <= ny; j++) {
      const y = bmin[1] + j * cellSize
      for (let i = 0; i <= nx; i++) {
        const x = bmin[0] + i * cellSize
        const e = evalNearest(spec.primitives, [x, y, z])
        const idx = cIdx(i, j, k)
        field[idx] = e.dist
        primAt[idx] = e.primIdx
      }
    }
  }

  // Per-cell vertex: if the 8 corners straddle the surface, place a vertex
  // at the weighted centroid of edge crossings.
  const cellVertIdx = new Int32Array(nx * ny * nz).fill(-1)
  const verts: number[] = []
  // Joint-index lookup: map parentJoint name → boneIdx index into
  // spec primitives' uniq joints. We build the list as we go.
  const jointNames: string[] = []
  const jointIdxOf = new Map<string, number>()
  for (const pr of spec.primitives) {
    if (!jointIdxOf.has(pr.parentJoint)) {
      jointIdxOf.set(pr.parentJoint, jointNames.length)
      jointNames.push(pr.parentJoint)
    }
  }

  // 12 edges of a unit cube, as (corner-A, corner-B) index pairs into
  // the 8 corners labeled (i+dx, j+dy, k+dz), dx/dy/dz ∈ {0,1}.
  const CORNER_OFFSETS: [number, number, number][] = [
    [0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
    [0, 0, 1], [1, 0, 1], [0, 1, 1], [1, 1, 1],
  ]
  const EDGES: [number, number][] = [
    [0, 1], [2, 3], [4, 5], [6, 7],   // X edges
    [0, 2], [1, 3], [4, 6], [5, 7],   // Y edges
    [0, 4], [1, 5], [2, 6], [3, 7],   // Z edges
  ]

  for (let k = 0; k < nz; k++) {
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const cornerField: number[] = new Array(8)
        const cornerPrim: number[] = new Array(8)
        for (let c = 0; c < 8; c++) {
          const [dx, dy, dz] = CORNER_OFFSETS[c]
          const ci = cIdx(i + dx, j + dy, k + dz)
          cornerField[c] = field[ci]
          cornerPrim[c] = primAt[ci]
        }
        let mask = 0
        for (let c = 0; c < 8; c++) if (cornerField[c] < 0) mask |= 1 << c
        if (mask === 0 || mask === 0xff) continue   // all inside or all outside

        // Accumulate edge-crossing positions to place the cell vertex.
        let cx = 0, cy = 0, cz = 0, crossings = 0
        // Dominant palette slot: majority vote of primitives at "inside" corners.
        const slotVotes: Record<number, number> = {}
        const boneVotes: Record<number, number> = {}
        for (const [a, b] of EDGES) {
          const fa = cornerField[a], fb = cornerField[b]
          if ((fa < 0) === (fb < 0)) continue   // no sign change on this edge
          const t = fa / (fa - fb)
          const [ax, ay, az] = CORNER_OFFSETS[a]
          const [bx, by, bz] = CORNER_OFFSETS[b]
          cx += (ax + (bx - ax) * t)
          cy += (ay + (by - ay) * t)
          cz += (az + (bz - az) * t)
          crossings++
        }
        for (let c = 0; c < 8; c++) {
          if (cornerField[c] >= 0) continue
          const prim = spec.primitives[cornerPrim[c]]
          const slot = prim.paletteSlot
          const bone = jointIdxOf.get(prim.parentJoint) ?? 0
          slotVotes[slot] = (slotVotes[slot] ?? 0) + 1
          boneVotes[bone] = (boneVotes[bone] ?? 0) + 1
        }
        cx /= crossings; cy /= crossings; cz /= crossings

        // Transform from cell-local [0,1] to world space.
        const wx = bmin[0] + (i + cx) * cellSize
        const wy = bmin[1] + (j + cy) * cellSize
        const wz = bmin[2] + (k + cz) * cellSize

        // Normal from SDF gradient at the vertex location.
        const n = normalize(gradient(compound, [wx, wy, wz], cellSize * 0.5))

        // Majority-vote slot + bone (ties broken by first-seen order).
        let bestSlot = 0, bestSlotCount = -1
        for (const [s, c] of Object.entries(slotVotes)) {
          if (c > bestSlotCount) { bestSlotCount = c; bestSlot = Number(s) }
        }
        let bestBone = 0, bestBoneCount = -1
        for (const [b, c] of Object.entries(boneVotes)) {
          if (c > bestBoneCount) { bestBoneCount = c; bestBone = Number(b) }
        }

        cellVertIdx[i + nx * (j + ny * k)] = verts.length / VERTEX_FLOATS
        verts.push(wx, wy, wz, n[0], n[1], n[2], bestSlot, bestBone)
      }
    }
  }

  // Emit quads along every sign-changing axis-aligned edge in the grid.
  // Each such edge is shared by 4 cells (the cells whose corners include
  // that edge). Connect their vertices into a quad, triangulated as 2
  // tris with winding chosen by the sign direction.
  const idx: number[] = []
  const fieldAt = (i: number, j: number, k: number) => field[cIdx(i, j, k)]
  const cellIdx = (i: number, j: number, k: number) => cellVertIdx[i + nx * (j + ny * k)]

  // X-axis edges from (i,j,k) to (i+1,j,k); shared by cells offset in y/z.
  for (let k = 1; k < nz; k++) {
    for (let j = 1; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const fa = fieldAt(i, j, k), fb = fieldAt(i + 1, j, k)
        if ((fa < 0) === (fb < 0)) continue
        const a = cellIdx(i, j - 1, k - 1), b = cellIdx(i, j, k - 1)
        const c = cellIdx(i, j, k),         d = cellIdx(i, j - 1, k)
        if (a < 0 || b < 0 || c < 0 || d < 0) continue
        if (fa < 0) {
          idx.push(a, b, c); idx.push(a, c, d)
        } else {
          idx.push(a, c, b); idx.push(a, d, c)
        }
      }
    }
  }
  // Y-axis edges
  for (let k = 1; k < nz; k++) {
    for (let j = 0; j < ny; j++) {
      for (let i = 1; i < nx; i++) {
        const fa = fieldAt(i, j, k), fb = fieldAt(i, j + 1, k)
        if ((fa < 0) === (fb < 0)) continue
        const a = cellIdx(i - 1, j, k - 1), b = cellIdx(i, j, k - 1)
        const c = cellIdx(i, j, k),         d = cellIdx(i - 1, j, k)
        if (a < 0 || b < 0 || c < 0 || d < 0) continue
        if (fa < 0) {
          idx.push(a, c, b); idx.push(a, d, c)
        } else {
          idx.push(a, b, c); idx.push(a, c, d)
        }
      }
    }
  }
  // Z-axis edges
  for (let k = 0; k < nz; k++) {
    for (let j = 1; j < ny; j++) {
      for (let i = 1; i < nx; i++) {
        const fa = fieldAt(i, j, k), fb = fieldAt(i, j, k + 1)
        if ((fa < 0) === (fb < 0)) continue
        const a = cellIdx(i - 1, j - 1, k), b = cellIdx(i, j - 1, k)
        const c = cellIdx(i, j, k),         d = cellIdx(i - 1, j, k)
        if (a < 0 || b < 0 || c < 0 || d < 0) continue
        if (fa < 0) {
          idx.push(a, b, c); idx.push(a, c, d)
        } else {
          idx.push(a, c, b); idx.push(a, d, c)
        }
      }
    }
  }

  return {
    vertices: new Float32Array(verts),
    indices: new Uint32Array(idx),
    jointNames,
  }
}
