/**
 * Mesh component — links geometry buffers to scene nodes.
 * Supports multiple submeshes with different materials.
 */

import { GeometryData } from '../renderer/geometry'
import { Material, createDefaultMaterial } from './material'

export interface MeshPrimitive {
  vertexBuffer: GPUBuffer
  indexBuffer: GPUBuffer
  indexCount: number
  indexFormat: GPUIndexFormat
  material: Material
}

export interface Mesh {
  name: string
  primitives: MeshPrimitive[]
  boundingRadius: number
}

/**
 * Compute a bounding sphere radius from interleaved vertex data.
 * Assumes positions at stride offset 0, with given stride in floats.
 */
export function computeBoundingRadius(vertices: Float32Array, stride: number): number {
  let maxDist = 0
  for (let i = 0; i < vertices.length; i += stride) {
    const x = vertices[i]
    const y = vertices[i + 1]
    const z = vertices[i + 2]
    const dist = Math.sqrt(x * x + y * y + z * z)
    if (dist > maxDist) maxDist = dist
  }
  return maxDist
}

/**
 * Create a Mesh from raw GeometryData, automatically building GPU buffers.
 */
export function createMesh(
  device: GPUDevice,
  geometry: GeometryData,
  material?: Material,
  name?: string
): Mesh {
  const vertexBuffer = device.createBuffer({
    size: geometry.vertices.byteLength,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    label: `${name ?? 'mesh'}-vb`,
  })
  device.queue.writeBuffer(vertexBuffer, 0, geometry.vertices)

  const indexBuffer = device.createBuffer({
    size: geometry.indices.byteLength,
    usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
    label: `${name ?? 'mesh'}-ib`,
  })
  device.queue.writeBuffer(indexBuffer, 0, geometry.indices)

  const boundingRadius = computeBoundingRadius(geometry.vertices, 8)

  return {
    name: name ?? 'mesh',
    primitives: [
      {
        vertexBuffer,
        indexBuffer,
        indexCount: geometry.indexCount,
        indexFormat: 'uint32',
        material: material ?? createDefaultMaterial(),
      },
    ],
    boundingRadius,
  }
}
