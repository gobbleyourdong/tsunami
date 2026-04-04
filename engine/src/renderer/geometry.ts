/**
 * Procedural geometry generators — cube, sphere, plane, capsule.
 * Returns interleaved position+normal+uv data + index buffers.
 */

export interface GeometryData {
  vertices: Float32Array  // interleaved [pos.xyz, normal.xyz, uv.xy] × N
  indices: Uint32Array
  vertexCount: number
  indexCount: number
}

export function createCubeGeometry(size = 1): GeometryData {
  const s = size / 2
  // prettier-ignore
  const vertices = new Float32Array([
    // Front face
    -s, -s,  s,   0,  0,  1,   0, 0,
     s, -s,  s,   0,  0,  1,   1, 0,
     s,  s,  s,   0,  0,  1,   1, 1,
    -s,  s,  s,   0,  0,  1,   0, 1,
    // Back face
     s, -s, -s,   0,  0, -1,   0, 0,
    -s, -s, -s,   0,  0, -1,   1, 0,
    -s,  s, -s,   0,  0, -1,   1, 1,
     s,  s, -s,   0,  0, -1,   0, 1,
    // Top face
    -s,  s,  s,   0,  1,  0,   0, 0,
     s,  s,  s,   0,  1,  0,   1, 0,
     s,  s, -s,   0,  1,  0,   1, 1,
    -s,  s, -s,   0,  1,  0,   0, 1,
    // Bottom face
    -s, -s, -s,   0, -1,  0,   0, 0,
     s, -s, -s,   0, -1,  0,   1, 0,
     s, -s,  s,   0, -1,  0,   1, 1,
    -s, -s,  s,   0, -1,  0,   0, 1,
    // Right face
     s, -s,  s,   1,  0,  0,   0, 0,
     s, -s, -s,   1,  0,  0,   1, 0,
     s,  s, -s,   1,  0,  0,   1, 1,
     s,  s,  s,   1,  0,  0,   0, 1,
    // Left face
    -s, -s, -s,  -1,  0,  0,   0, 0,
    -s, -s,  s,  -1,  0,  0,   1, 0,
    -s,  s,  s,  -1,  0,  0,   1, 1,
    -s,  s, -s,  -1,  0,  0,   0, 1,
  ])

  // prettier-ignore
  const indices = new Uint32Array([
     0,  1,  2,   0,  2,  3,  // front
     4,  5,  6,   4,  6,  7,  // back
     8,  9, 10,   8, 10, 11,  // top
    12, 13, 14,  12, 14, 15,  // bottom
    16, 17, 18,  16, 18, 19,  // right
    20, 21, 22,  20, 22, 23,  // left
  ])

  return { vertices, indices, vertexCount: 24, indexCount: 36 }
}

export function createPlaneGeometry(size = 10, segments = 1): GeometryData {
  const s = size / 2
  const step = size / segments
  const vertCount = (segments + 1) * (segments + 1)
  const vertices = new Float32Array(vertCount * 8)
  const indices = new Uint32Array(segments * segments * 6)

  let vi = 0
  for (let z = 0; z <= segments; z++) {
    for (let x = 0; x <= segments; x++) {
      const px = -s + x * step
      const pz = -s + z * step
      vertices[vi++] = px
      vertices[vi++] = 0
      vertices[vi++] = pz
      vertices[vi++] = 0; vertices[vi++] = 1; vertices[vi++] = 0 // normal up
      vertices[vi++] = x / segments
      vertices[vi++] = z / segments
    }
  }

  let ii = 0
  for (let z = 0; z < segments; z++) {
    for (let x = 0; x < segments; x++) {
      const tl = z * (segments + 1) + x
      const tr = tl + 1
      const bl = tl + (segments + 1)
      const br = bl + 1
      indices[ii++] = tl; indices[ii++] = bl; indices[ii++] = tr
      indices[ii++] = tr; indices[ii++] = bl; indices[ii++] = br
    }
  }

  return { vertices, indices, vertexCount: vertCount, indexCount: ii }
}

export function createSphereGeometry(radius = 1, widthSegments = 32, heightSegments = 16): GeometryData {
  const vertices: number[] = []
  const indices: number[] = []

  for (let y = 0; y <= heightSegments; y++) {
    const v = y / heightSegments
    const phi = v * Math.PI

    for (let x = 0; x <= widthSegments; x++) {
      const u = x / widthSegments
      const theta = u * Math.PI * 2

      const nx = Math.sin(phi) * Math.cos(theta)
      const ny = Math.cos(phi)
      const nz = Math.sin(phi) * Math.sin(theta)

      vertices.push(nx * radius, ny * radius, nz * radius) // position
      vertices.push(nx, ny, nz)                              // normal
      vertices.push(u, v)                                     // uv
    }
  }

  for (let y = 0; y < heightSegments; y++) {
    for (let x = 0; x < widthSegments; x++) {
      const a = y * (widthSegments + 1) + x
      const b = a + widthSegments + 1
      indices.push(a, b, a + 1)
      indices.push(a + 1, b, b + 1)
    }
  }

  return {
    vertices: new Float32Array(vertices),
    indices: new Uint32Array(indices),
    vertexCount: (widthSegments + 1) * (heightSegments + 1),
    indexCount: indices.length,
  }
}
