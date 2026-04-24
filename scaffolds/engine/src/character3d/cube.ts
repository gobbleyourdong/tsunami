/**
 * Unit cube mesh — 24 vertices (4 per face with face normals), 12 triangles.
 * Position ±1. Duplicated verts per face so flat shading via per-face normals
 * works without derivative tricks.
 *
 * Vertex layout: (px, py, pz, nx, ny, nz) — stride 24 bytes.
 */

export const CUBE_VERTICES = new Float32Array([
  // Front (+Z)
  -1, -1,  1,  0, 0, 1,   1, -1,  1,  0, 0, 1,   1,  1,  1,  0, 0, 1,  -1,  1,  1,  0, 0, 1,
  // Back (-Z)
   1, -1, -1,  0, 0, -1, -1, -1, -1,  0, 0, -1, -1,  1, -1,  0, 0, -1,  1,  1, -1,  0, 0, -1,
  // Top (+Y)
  -1,  1,  1,  0, 1, 0,   1,  1,  1,  0, 1, 0,   1,  1, -1,  0, 1, 0,  -1,  1, -1,  0, 1, 0,
  // Bottom (-Y)
  -1, -1, -1,  0, -1, 0,  1, -1, -1,  0, -1, 0,  1, -1,  1,  0, -1, 0, -1, -1,  1,  0, -1, 0,
  // Right (+X)
   1, -1,  1,  1, 0, 0,   1, -1, -1,  1, 0, 0,   1,  1, -1,  1, 0, 0,   1,  1,  1,  1, 0, 0,
  // Left (-X)
  -1, -1, -1, -1, 0, 0,  -1, -1,  1, -1, 0, 0,  -1,  1,  1, -1, 0, 0,  -1,  1, -1, -1, 0, 0,
])

export const CUBE_INDICES = new Uint16Array([
   0,  1,  2,   0,  2,  3,    // front
   4,  5,  6,   4,  6,  7,    // back
   8,  9, 10,   8, 10, 11,    // top
  12, 13, 14,  12, 14, 15,    // bottom
  16, 17, 18,  16, 18, 19,    // right
  20, 21, 22,  20, 22, 23,    // left
])

export const CUBE_VERTEX_COUNT = 24
export const CUBE_INDEX_COUNT = 36
export const CUBE_VERTEX_STRIDE = 24   // 6 floats × 4 bytes
