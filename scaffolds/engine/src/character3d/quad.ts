/**
 * Unit quad in XY plane, corners at -1..+1. 4 vertices, 2 triangles.
 * Used for view-space-aligned billboard sprites.
 */

export const QUAD_VERTICES = new Float32Array([
  -1, -1,
   1, -1,
  -1,  1,
   1,  1,
])

export const QUAD_INDICES = new Uint16Array([0, 1, 2, 2, 1, 3])

export const QUAD_VERTEX_COUNT = 4
export const QUAD_INDEX_COUNT = 6
