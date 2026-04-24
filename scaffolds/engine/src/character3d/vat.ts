/**
 * Vertex Animation Texture (VAT) — bakes per-instance, per-frame transform
 * data into a linear storage buffer of vec4f entries. Layout is row-major
 * [frame][instance]: index = frame * numInstances + instance.
 *
 * Storage buffer (vs 2D texture) avoids `textureLoad` integer-coord overhead
 * in the vertex shader and gives direct linear indexing. Same binary layout
 * either way; just the binding type changes.
 *
 * Extends to skeletons by packing joint matrices (4 vec4f per joint per
 * frame) in the same buffer later — shader just reads a different stride.
 *
 * This module produces PROCEDURAL animation data (orbit + vertical bob)
 * for pipeline validation. Swap in real Mixamo joint transforms later.
 */

export interface VATData {
  buffer: GPUBuffer
  numInstances: number
  numFrames: number
}

/** Orbiting + vertical-bob animation — instances distributed across
 *  concentric shells so camera sweeps produce honest overdraw instead
 *  of one flat ring. Each shell has a different radius, phase, and
 *  vertical offset; spheres intermix as the orbit advances. */
export function createOrbitVAT(
  device: GPUDevice,
  numInstances: number,
  numFrames: number,
  innerRadius = 1.0,
  outerRadius = 5.0
): VATData {
  const data = new Float32Array(numInstances * numFrames * 4)
  const shells = 8
  const perShell = Math.ceil(numInstances / shells)
  for (let f = 0; f < numFrames; f++) {
    const t = f / numFrames
    for (let i = 0; i < numInstances; i++) {
      const shell = Math.floor(i / perShell)
      const inShell = i - shell * perShell
      const r = innerRadius + (shell / (shells - 1)) * (outerRadius - innerRadius)
      const baseAngle = (inShell / perShell) * Math.PI * 2 + shell * 0.3
      const speed = 1.0 + shell * 0.15
      const spin = baseAngle + t * Math.PI * 2 * speed
      const yOffset = (shell - shells / 2) * 0.4
      const idx = (f * numInstances + i) * 4
      data[idx + 0] = Math.cos(spin) * r
      data[idx + 1] = Math.sin(spin * 2 + i * 0.3) * 0.5 + yOffset
      data[idx + 2] = Math.sin(spin) * r
      data[idx + 3] = 1.0
    }
  }

  const buffer = device.createBuffer({
    label: 'vat-orbit',
    size: data.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(buffer, 0, data)

  return { buffer, numInstances, numFrames }
}
