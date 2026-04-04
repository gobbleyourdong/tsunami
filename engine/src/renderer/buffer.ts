/**
 * Vertex buffer layout, index buffers, uniform buffers, storage buffers.
 * Typed helpers for GPU buffer creation and updates.
 */

// --- Vertex buffer layouts ---

export const VERTEX_POSITION_COLOR: GPUVertexBufferLayout = {
  arrayStride: 6 * 4, // 3 pos + 3 color, float32 each
  attributes: [
    { shaderLocation: 0, offset: 0, format: 'float32x3' },     // position
    { shaderLocation: 1, offset: 3 * 4, format: 'float32x3' }, // color
  ],
}

export const VERTEX_POSITION_NORMAL_UV: GPUVertexBufferLayout = {
  arrayStride: 8 * 4, // 3 pos + 3 normal + 2 uv
  attributes: [
    { shaderLocation: 0, offset: 0, format: 'float32x3' },     // position
    { shaderLocation: 1, offset: 3 * 4, format: 'float32x3' }, // normal
    { shaderLocation: 2, offset: 6 * 4, format: 'float32x2' }, // uv
  ],
}

export const VERTEX_POSITION_NORMAL: GPUVertexBufferLayout = {
  arrayStride: 6 * 4, // 3 pos + 3 normal
  attributes: [
    { shaderLocation: 0, offset: 0, format: 'float32x3' },     // position
    { shaderLocation: 1, offset: 3 * 4, format: 'float32x3' }, // normal
  ],
}

// --- Buffer creation helpers ---

export function createVertexBuffer(
  device: GPUDevice,
  data: Float32Array,
  label?: string
): GPUBuffer {
  const buffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
    label: label ?? 'vertex-buffer',
  })
  device.queue.writeBuffer(buffer, 0, data)
  return buffer
}

export function createIndexBuffer(
  device: GPUDevice,
  data: Uint16Array | Uint32Array,
  label?: string
): GPUBuffer {
  const buffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
    label: label ?? 'index-buffer',
  })
  device.queue.writeBuffer(buffer, 0, data)
  return buffer
}

export function createUniformBuffer(
  device: GPUDevice,
  size: number,
  label?: string
): GPUBuffer {
  return device.createBuffer({
    size,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
    label: label ?? 'uniform-buffer',
  })
}

export function createStorageBuffer(
  device: GPUDevice,
  data: ArrayBuffer,
  label?: string
): GPUBuffer {
  const buffer = device.createBuffer({
    size: data.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    label: label ?? 'storage-buffer',
  })
  device.queue.writeBuffer(buffer, 0, data)
  return buffer
}

export function updateBuffer(
  device: GPUDevice,
  buffer: GPUBuffer,
  data: ArrayBufferView,
  offset = 0
): void {
  device.queue.writeBuffer(buffer, offset, data)
}
