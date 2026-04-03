/**
 * PBR Material system — metallic-roughness workflow.
 * Maps to WebGPU bind groups for rendering.
 */

import { TextureHandle } from '../renderer/texture'

export interface Material {
  name: string
  albedo: [number, number, number, number]  // RGBA base color
  roughness: number
  metallic: number
  emissive: [number, number, number]

  albedoTexture?: TextureHandle
  normalTexture?: TextureHandle
  roughnessMetallicTexture?: TextureHandle
  emissiveTexture?: TextureHandle
  aoTexture?: TextureHandle

  alphaMode: 'opaque' | 'mask' | 'blend'
  alphaCutoff: number
  doubleSided: boolean
}

export function createDefaultMaterial(name?: string): Material {
  return {
    name: name ?? 'default',
    albedo: [0.8, 0.8, 0.8, 1.0],
    roughness: 0.5,
    metallic: 0.0,
    emissive: [0, 0, 0],
    alphaMode: 'opaque',
    alphaCutoff: 0.5,
    doubleSided: false,
  }
}

/**
 * Pack material properties into a uniform-ready Float32Array.
 * Layout (16 floats = 64 bytes):
 *   [0-3]:   albedo RGBA
 *   [4]:     roughness
 *   [5]:     metallic
 *   [6-7]:   padding
 *   [8-10]:  emissive RGB
 *   [11]:    alphaCutoff
 *   [12-15]: reserved
 */
export function packMaterialUniforms(mat: Material): Float32Array {
  const data = new Float32Array(16)
  data[0] = mat.albedo[0]; data[1] = mat.albedo[1]
  data[2] = mat.albedo[2]; data[3] = mat.albedo[3]
  data[4] = mat.roughness; data[5] = mat.metallic
  data[8] = mat.emissive[0]; data[9] = mat.emissive[1]; data[10] = mat.emissive[2]
  data[11] = mat.alphaCutoff
  return data
}
