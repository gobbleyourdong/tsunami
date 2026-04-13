/**
 * GLTF 2.0 loader — mesh, skeleton, animation, PBR materials.
 * Loads .glb (binary) and .gltf+bin (separate) formats.
 */

import { SceneNode } from './node'
import { Mesh } from './mesh'
import { Material, createDefaultMaterial } from './material'
import { loadTexture, TextureHandle } from '../renderer/texture'

export interface GLTFResult {
  scenes: SceneNode[]
  meshes: Mesh[]
  materials: Material[]
  animations: GLTFAnimation[]
  skins: GLTFSkin[]
}

export interface GLTFAnimation {
  name: string
  channels: GLTFChannel[]
  duration: number
}

export interface GLTFChannel {
  targetNode: number
  path: 'translation' | 'rotation' | 'scale' | 'weights'
  interpolation: 'LINEAR' | 'STEP' | 'CUBICSPLINE'
  times: Float32Array
  values: Float32Array
}

export interface GLTFSkin {
  joints: number[]
  inverseBindMatrices: Float32Array
  skeleton?: number
}

// Component type byte sizes
const COMPONENT_SIZES: Record<number, number> = {
  5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4,
}
const TYPE_COUNTS: Record<string, number> = {
  SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16,
}

interface ParsedGLTF {
  json: any
  bin: ArrayBuffer
  baseUrl: string
}

async function parseGLB(buffer: ArrayBuffer): Promise<ParsedGLTF> {
  const view = new DataView(buffer)
  const magic = view.getUint32(0, true)
  if (magic !== 0x46546C67) throw new Error('Not a valid GLB file')

  let offset = 12 // skip header
  let json: any = null
  let bin: ArrayBuffer = new ArrayBuffer(0)

  while (offset < buffer.byteLength) {
    const chunkLength = view.getUint32(offset, true)
    const chunkType = view.getUint32(offset + 4, true)
    offset += 8

    if (chunkType === 0x4E4F534A) { // JSON
      const decoder = new TextDecoder()
      json = JSON.parse(decoder.decode(new Uint8Array(buffer, offset, chunkLength)))
    } else if (chunkType === 0x004E4942) { // BIN
      bin = buffer.slice(offset, offset + chunkLength)
    }
    offset += chunkLength
  }

  return { json, bin, baseUrl: '' }
}

async function parseGLTF(url: string): Promise<ParsedGLTF> {
  const response = await fetch(url)
  const contentType = response.headers.get('content-type') ?? ''

  if (url.endsWith('.glb') || contentType.includes('model/gltf-binary')) {
    return parseGLB(await response.arrayBuffer())
  }

  const json = await response.json()
  const baseUrl = url.substring(0, url.lastIndexOf('/') + 1)
  let bin = new ArrayBuffer(0)

  if (json.buffers?.[0]?.uri) {
    const binUrl = json.buffers[0].uri.startsWith('data:')
      ? json.buffers[0].uri
      : baseUrl + json.buffers[0].uri
    const binResponse = await fetch(binUrl)
    bin = await binResponse.arrayBuffer()
  }

  return { json, bin, baseUrl }
}

function getAccessorData(
  gltf: ParsedGLTF,
  accessorIndex: number
): { data: ArrayBuffer; componentType: number; count: number; type: string } {
  const accessor = gltf.json.accessors[accessorIndex]
  const bufferView = gltf.json.bufferViews[accessor.bufferView ?? 0]
  const byteOffset = (bufferView.byteOffset ?? 0) + (accessor.byteOffset ?? 0)
  const componentSize = COMPONENT_SIZES[accessor.componentType] ?? 4
  const typeCount = TYPE_COUNTS[accessor.type] ?? 1
  const byteLength = accessor.count * typeCount * componentSize

  return {
    data: gltf.bin.slice(byteOffset, byteOffset + byteLength),
    componentType: accessor.componentType,
    count: accessor.count,
    type: accessor.type,
  }
}

function accessorToFloat32(gltf: ParsedGLTF, idx: number): Float32Array {
  const { data, componentType } = getAccessorData(gltf, idx)
  if (componentType === 5126) return new Float32Array(data)
  // Convert other types to float
  if (componentType === 5123) {
    const u16 = new Uint16Array(data)
    return Float32Array.from(u16)
  }
  if (componentType === 5121) {
    const u8 = new Uint8Array(data)
    return Float32Array.from(u8)
  }
  return new Float32Array(data)
}

function accessorToUint32(gltf: ParsedGLTF, idx: number): Uint32Array {
  const { data, componentType } = getAccessorData(gltf, idx)
  if (componentType === 5125) return new Uint32Array(data)
  if (componentType === 5123) {
    const u16 = new Uint16Array(data)
    return Uint32Array.from(u16)
  }
  if (componentType === 5121) {
    const u8 = new Uint8Array(data)
    return Uint32Array.from(u8)
  }
  return new Uint32Array(data)
}

/**
 * Load a GLTF/GLB file and create GPU resources.
 */
export async function loadGLTF(
  device: GPUDevice,
  url: string
): Promise<GLTFResult> {
  const gltf = await parseGLTF(url)
  const { json } = gltf

  // --- Parse materials ---
  const materials: Material[] = (json.materials ?? []).map((mat: any) => {
    const pbr = mat.pbrMetallicRoughness ?? {}
    const baseColor = pbr.baseColorFactor ?? [1, 1, 1, 1]
    return {
      name: mat.name ?? 'unnamed',
      albedo: baseColor as [number, number, number, number],
      roughness: pbr.roughnessFactor ?? 1.0,
      metallic: pbr.metallicFactor ?? 0.0,
      emissive: mat.emissiveFactor ?? [0, 0, 0],
      alphaMode: mat.alphaMode ?? 'OPAQUE',
      alphaCutoff: mat.alphaCutoff ?? 0.5,
      doubleSided: mat.doubleSided ?? false,
    } as Material
  })

  // --- Parse meshes ---
  const meshes: Mesh[] = (json.meshes ?? []).map((meshDef: any) => {
    const primitives = meshDef.primitives.map((prim: any) => {
      // Interleave position + normal + uv
      const positions = accessorToFloat32(gltf, prim.attributes.POSITION)
      const normals = prim.attributes.NORMAL != null
        ? accessorToFloat32(gltf, prim.attributes.NORMAL)
        : new Float32Array(positions.length) // zero normals fallback
      const uvs = prim.attributes.TEXCOORD_0 != null
        ? accessorToFloat32(gltf, prim.attributes.TEXCOORD_0)
        : new Float32Array((positions.length / 3) * 2)

      const vertexCount = positions.length / 3
      const interleaved = new Float32Array(vertexCount * 8)
      for (let v = 0; v < vertexCount; v++) {
        interleaved[v * 8 + 0] = positions[v * 3 + 0]
        interleaved[v * 8 + 1] = positions[v * 3 + 1]
        interleaved[v * 8 + 2] = positions[v * 3 + 2]
        interleaved[v * 8 + 3] = normals[v * 3 + 0]
        interleaved[v * 8 + 4] = normals[v * 3 + 1]
        interleaved[v * 8 + 5] = normals[v * 3 + 2]
        interleaved[v * 8 + 6] = uvs[v * 2 + 0]
        interleaved[v * 8 + 7] = uvs[v * 2 + 1]
      }

      const vertexBuffer = device.createBuffer({
        size: interleaved.byteLength,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
        label: `${meshDef.name ?? 'mesh'}-vb`,
      })
      device.queue.writeBuffer(vertexBuffer, 0, interleaved)

      const indices = prim.indices != null
        ? accessorToUint32(gltf, prim.indices)
        : Uint32Array.from({ length: vertexCount }, (_, i) => i)

      const indexBuffer = device.createBuffer({
        size: indices.byteLength,
        usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
        label: `${meshDef.name ?? 'mesh'}-ib`,
      })
      device.queue.writeBuffer(indexBuffer, 0, indices)

      const material = prim.material != null && materials[prim.material]
        ? materials[prim.material]
        : createDefaultMaterial()

      return {
        vertexBuffer,
        indexBuffer,
        indexCount: indices.length,
        indexFormat: 'uint32' as GPUIndexFormat,
        material,
      }
    })

    // Compute bounding radius from first primitive
    let boundingRadius = 1
    if (meshDef.primitives[0]?.attributes.POSITION != null) {
      const pos = accessorToFloat32(gltf, meshDef.primitives[0].attributes.POSITION)
      let maxDist = 0
      for (let i = 0; i < pos.length; i += 3) {
        const d = Math.sqrt(pos[i] * pos[i] + pos[i + 1] * pos[i + 1] + pos[i + 2] * pos[i + 2])
        if (d > maxDist) maxDist = d
      }
      boundingRadius = maxDist
    }

    return {
      name: meshDef.name ?? 'mesh',
      primitives,
      boundingRadius,
    }
  })

  // --- Parse animations ---
  const animations: GLTFAnimation[] = (json.animations ?? []).map((animDef: any) => {
    const channels: GLTFChannel[] = animDef.channels.map((ch: any) => {
      const sampler = animDef.samplers[ch.sampler]
      const times = accessorToFloat32(gltf, sampler.input)
      const values = accessorToFloat32(gltf, sampler.output)
      return {
        targetNode: ch.target.node,
        path: ch.target.path,
        interpolation: sampler.interpolation ?? 'LINEAR',
        times,
        values,
      }
    })

    let duration = 0
    for (const ch of channels) {
      const maxTime = ch.times[ch.times.length - 1]
      if (maxTime > duration) duration = maxTime
    }

    return { name: animDef.name ?? 'anim', channels, duration }
  })

  // --- Parse skins ---
  const skins: GLTFSkin[] = (json.skins ?? []).map((skinDef: any) => {
    const ibm = skinDef.inverseBindMatrices != null
      ? accessorToFloat32(gltf, skinDef.inverseBindMatrices)
      : new Float32Array(skinDef.joints.length * 16)
    return {
      joints: skinDef.joints,
      inverseBindMatrices: ibm,
      skeleton: skinDef.skeleton,
    }
  })

  // --- Build scene graph ---
  const nodes: SceneNode[] = (json.nodes ?? []).map((nodeDef: any, i: number) => {
    const node = new SceneNode(nodeDef.name ?? `node_${i}`)
    if (nodeDef.translation) {
      node.position = nodeDef.translation as [number, number, number]
    }
    if (nodeDef.scale) {
      node.scale = nodeDef.scale as [number, number, number]
    }
    if (nodeDef.rotation) {
      // Convert quaternion to euler (approximate for scene graph)
      const [qx, qy, qz, qw] = nodeDef.rotation
      node.rotation = quaternionToEuler(qx, qy, qz, qw)
    }
    if (nodeDef.mesh != null) {
      node.setComponent('mesh', meshes[nodeDef.mesh])
      node.boundingRadius = meshes[nodeDef.mesh].boundingRadius
    }
    if (nodeDef.skin != null) {
      node.setComponent('skin', skins[nodeDef.skin])
    }
    return node
  })

  // Wire parent-child
  ;(json.nodes ?? []).forEach((nodeDef: any, i: number) => {
    if (nodeDef.children) {
      for (const childIdx of nodeDef.children) {
        nodes[i].addChild(nodes[childIdx])
      }
    }
  })

  // Build scenes
  const scenes: SceneNode[] = (json.scenes ?? [{ nodes: [0] }]).map((sceneDef: any) => {
    const root = new SceneNode('scene-root')
    for (const nodeIdx of sceneDef.nodes ?? []) {
      root.addChild(nodes[nodeIdx])
    }
    root.updateWorldTransforms()
    return root
  })

  return { scenes, meshes, materials, animations, skins }
}

function quaternionToEuler(x: number, y: number, z: number, w: number): [number, number, number] {
  // YXZ order (common in 3D engines)
  const sinr_cosp = 2 * (w * x + y * z)
  const cosr_cosp = 1 - 2 * (x * x + y * y)
  const pitch = Math.atan2(sinr_cosp, cosr_cosp)

  const sinp = 2 * (w * y - z * x)
  const yaw = Math.abs(sinp) >= 1
    ? (Math.PI / 2) * Math.sign(sinp)
    : Math.asin(sinp)

  const siny_cosp = 2 * (w * z + x * y)
  const cosy_cosp = 1 - 2 * (y * y + z * z)
  const roll = Math.atan2(siny_cosp, cosy_cosp)

  return [pitch, yaw, roll]
}
