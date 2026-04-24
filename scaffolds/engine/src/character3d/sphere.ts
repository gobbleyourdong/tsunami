/**
 * Hardcoded unit icosahedron — 12 vertices, 20 faces.
 * Positions double as normals (each vertex is a point on the unit sphere).
 * Cheap to rasterize; looks like a sphere at small sizes.
 */

const PHI = (1 + Math.sqrt(5)) / 2
const NORM = 1 / Math.sqrt(1 + PHI * PHI)

const RAW = [
  [-1,  PHI,  0], [ 1,  PHI,  0], [-1, -PHI,  0], [ 1, -PHI,  0],
  [ 0, -1,  PHI], [ 0,  1,  PHI], [ 0, -1, -PHI], [ 0,  1, -PHI],
  [ PHI,  0, -1], [ PHI,  0,  1], [-PHI,  0, -1], [-PHI,  0,  1],
]

export const SPHERE_VERTICES = new Float32Array(
  RAW.flatMap((v) => v.map((c) => c * NORM))
)

export const SPHERE_INDICES = new Uint16Array([
  0, 11,  5,   0,  5,  1,   0,  1,  7,   0,  7, 10,   0, 10, 11,
  1,  5,  9,   5, 11,  4,  11, 10,  2,  10,  7,  6,   7,  1,  8,
  3,  9,  4,   3,  4,  2,   3,  2,  6,   3,  6,  8,   3,  8,  9,
  4,  9,  5,   2,  4, 11,   6,  2, 10,   8,  6,  7,   9,  8,  1,
])

export const SPHERE_VERTEX_COUNT = 12
export const SPHERE_INDEX_COUNT = 60
