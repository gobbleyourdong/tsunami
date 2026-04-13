/**
 * Instanced rendering — draw thousands of identical meshes with unique transforms.
 * Uses a storage buffer for per-instance model matrices + colors.
 */

import { Mat4, Vec3, mat4 } from '../math/vec'

export interface InstanceData {
  position: Vec3
  rotation: Vec3
  scale: Vec3
  color: [number, number, number, number]
}

export class InstancedBatch {
  readonly maxInstances: number
  instances: InstanceData[] = []
  buffer: GPUBuffer
  private device: GPUDevice
  private dirty = true

  // CPU-side data: mat4 (16 floats) + vec4 color (4 floats) = 20 floats per instance
  private cpuData: Float32Array

  constructor(device: GPUDevice, maxInstances: number) {
    this.device = device
    this.maxInstances = maxInstances
    this.cpuData = new Float32Array(maxInstances * 20)

    this.buffer = device.createBuffer({
      size: this.cpuData.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
      label: 'instance-storage',
    })
  }

  add(instance: InstanceData): number {
    if (this.instances.length >= this.maxInstances) {
      console.warn(`Instance limit reached: ${this.maxInstances}`)
      return -1
    }
    this.instances.push(instance)
    this.dirty = true
    return this.instances.length - 1
  }

  clear(): void {
    this.instances.length = 0
    this.dirty = true
  }

  update(): void {
    if (!this.dirty) return
    this.dirty = false

    const tmpMat = mat4.create()

    for (let i = 0; i < this.instances.length; i++) {
      const inst = this.instances[i]
      const offset = i * 20

      // Build model matrix
      mat4.identity(tmpMat)
      mat4.translate(tmpMat, tmpMat, inst.position)
      mat4.rotateY(tmpMat, tmpMat, inst.rotation[1])
      mat4.rotateX(tmpMat, tmpMat, inst.rotation[0])
      mat4.scale(tmpMat, tmpMat, inst.scale)

      this.cpuData.set(tmpMat, offset)
      this.cpuData[offset + 16] = inst.color[0]
      this.cpuData[offset + 17] = inst.color[1]
      this.cpuData[offset + 18] = inst.color[2]
      this.cpuData[offset + 19] = inst.color[3]
    }

    this.device.queue.writeBuffer(this.buffer, 0, this.cpuData, 0, this.instances.length * 20)
  }

  get count(): number {
    return this.instances.length
  }

  destroy(): void {
    this.buffer.destroy()
  }
}
