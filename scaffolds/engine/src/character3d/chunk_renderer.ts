/**
 * Chunk renderer — draws a BakedMesh (output of isosurface.ts) with
 * per-vertex palette slot + per-vertex skinning.
 *
 * Sits alongside skeleton_renderer.ts. The skeleton renderer draws a
 * unit cube instanced per rig joint (our v1 display). This renderer
 * draws a skinned mesh whose vertices carry (position, normal,
 * paletteSlot, boneIdx). The VAT buffer (same one the cube skeleton
 * reads) supplies the per-bone world matrix.
 *
 * Shader output matches skeleton_renderer's MRT variant so the existing
 * outline pass + cel lighting work unchanged — chunks just feed the
 * color/normal/depth G-buffer targets like cubes do.
 *
 * Single-bone skinning (1 weight per vertex = 1.0) is what the current
 * isosurface bake produces. Multi-bone blending (for cross-bone chunks
 * like a torso that spans Spine1+Spine2) is a vertex-attribute extension
 * — add weights[4] + boneIndices[4]. The shader change is 10 lines.
 */

import type { BakedMesh } from './isosurface'
import type { SpriteMaterial } from './mixamo_loader'

/** Same VATData handle the skeleton renderer consumes — a GPU buffer
 *  containing per-frame per-joint world matrices, indexed by
 *  (frameIdx × numJoints + jointIdx). */
export interface VATData {
  buffer: GPUBuffer
  numInstances: number
  numFrames: number
}

const CHUNK_SHADER = /* wgsl */ `
struct Uniforms {
  view:      mat4x4<f32>,
  proj:      mat4x4<f32>,
  numJoints: u32,
  frameIdx:  u32,
  _pad0:     u32,
  _pad1:     u32,
}

@group(0) @binding(0) var<uniform> u: Uniforms;
// vatMats: flat array of mat4 column-major, same layout the composer writes.
@group(0) @binding(1) var<storage, read> vatMats: array<vec4f>;
// palette LUT — slot index → RGBA. Edit via writeBuffer for live recolor.
@group(0) @binding(2) var<storage, read> palette: array<vec4f>;

struct VsIn {
  @location(0) position: vec3f,
  @location(1) normal:   vec3f,
  @location(2) paletteSlot: f32,
  @location(3) boneIdx:  f32,
}

struct VsOut {
  @builtin(position) clip: vec4f,
  @location(0) tint:    vec3f,
  @location(1) nWorld:  vec3f,
  @location(2) depthNdc: f32,
}

fn readMat4(base: u32) -> mat4x4<f32> {
  // Each mat4 is 4 vec4s in the storage buffer (column-major).
  return mat4x4<f32>(
    vatMats[base + 0u],
    vatMats[base + 1u],
    vatMats[base + 2u],
    vatMats[base + 3u],
  );
}

@vertex
fn vs_main(in: VsIn) -> VsOut {
  let bone = u32(in.boneIdx);
  // Row stride per-vertex matrix = 4 vec4s = 16 floats = one mat4.
  let matBase = (u.frameIdx * u.numJoints + bone) * 4u;
  let world = readMat4(matBase);

  let wPos = world * vec4f(in.position, 1.0);
  // Rotate the normal. Translation in col3 doesn't matter for directions;
  // non-uniform scales in col0..2 would require inverse-transpose, but the
  // retargeting composer uses uniform-ish scales so this is visually fine.
  let wNormal = normalize((world * vec4f(in.normal, 0.0)).xyz);

  let clip = u.proj * u.view * wPos;

  let slot = u32(in.paletteSlot);
  let tint = palette[slot].rgb;

  var out: VsOut;
  out.clip = clip;
  out.tint = tint;
  out.nWorld = wNormal;
  out.depthNdc = clamp(clip.z / clip.w, 0.0, 1.0);
  return out;
}

struct FsOut {
  @location(0) color:  vec4f,
  @location(1) normal: vec4f,
  @location(2) depth:  vec4f,
}

@fragment
fn fs_main(in: VsOut) -> FsOut {
  let n = normalize(in.nWorld);
  var out: FsOut;
  out.color  = vec4f(in.tint, 1.0);
  out.normal = vec4f(n * 0.5 + 0.5, 1.0);
  out.depth  = vec4f(in.depthNdc, 0.0, 0.0, 1.0);
  return out;
}
`

export interface ChunkRenderer {
  draw(pass: GPURenderPassEncoder, view: Float32Array, proj: Float32Array, frameIdx: number): void
  /** Hot-edit a palette slot (same LUT as skeleton_renderer — both
   *  renderers can share a palette buffer; for independence we give each
   *  their own here). */
  setPaletteSlot(slot: number, r: number, g: number, b: number, a?: number): void
  rebind(mesh: BakedMesh, material: SpriteMaterial, vat: VATData): void
}

export function createChunkRenderer(
  device: GPUDevice,
  format: GPUTextureFormat,
  mesh: BakedMesh,
  material: SpriteMaterial,
  vat: VATData,
): ChunkRenderer {
  const shader = device.createShaderModule({ code: CHUNK_SHADER, label: 'chunk-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'chunk-pipeline',
    layout: 'auto',
    vertex: {
      module: shader,
      entryPoint: 'vs_main',
      buffers: [{
        arrayStride: 8 * 4,   // 8 floats per vertex
        attributes: [
          { shaderLocation: 0, offset: 0 * 4,  format: 'float32x3' },   // position
          { shaderLocation: 1, offset: 3 * 4,  format: 'float32x3' },   // normal
          { shaderLocation: 2, offset: 6 * 4,  format: 'float32' },     // paletteSlot
          { shaderLocation: 3, offset: 7 * 4,  format: 'float32' },     // boneIdx
        ],
      }],
    },
    fragment: {
      module: shader,
      entryPoint: 'fs_main',
      targets: [{ format }, { format }, { format }],
    },
    primitive: { topology: 'triangle-list', cullMode: 'back' },
    depthStencil: {
      format: 'depth24plus-stencil8',
      depthWriteEnabled: true,
      depthCompare: 'less',
    },
  })

  // Uniform buffer: view(16f) + proj(16f) + numJoints(u32) + frameIdx(u32) + 2×u32 pad = 144 bytes.
  const uniformBuffer = device.createBuffer({
    label: 'chunk-uniforms',
    size: 144,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })

  // Palette LUT buffer — independent from skeleton_renderer's palette so
  // the two can host different materials if needed. Recolor via
  // setPaletteSlot writes directly into this buffer.
  let paletteBuffer = device.createBuffer({
    label: 'chunk-palette',
    size: material.palette.byteLength,
    usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(paletteBuffer, 0, material.palette)

  // Vertex + index buffers for the baked mesh.
  let vertexBuffer = device.createBuffer({
    label: 'chunk-vertices',
    size: mesh.vertices.byteLength,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(vertexBuffer, 0, mesh.vertices)

  let indexBuffer = device.createBuffer({
    label: 'chunk-indices',
    size: mesh.indices.byteLength,
    usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(indexBuffer, 0, mesh.indices)

  let indexCount = mesh.indices.length

  let bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: uniformBuffer } },
      { binding: 1, resource: { buffer: vat.buffer } },
      { binding: 2, resource: { buffer: paletteBuffer } },
    ],
  })

  let currentNumJoints = vat.numInstances

  const uniformData = new Float32Array(36)   // 144 bytes aligned
  function writeUniforms(view: Float32Array, proj: Float32Array, frameIdx: number) {
    uniformData.set(view, 0)
    uniformData.set(proj, 16)
    // numJoints + frameIdx as u32 — write via DataView on the same buffer.
    const u32 = new Uint32Array(uniformData.buffer, 32 * 4, 2)
    u32[0] = currentNumJoints
    u32[1] = frameIdx
    device.queue.writeBuffer(uniformBuffer, 0, uniformData)
  }

  return {
    draw(pass, view, proj, frameIdx) {
      writeUniforms(view, proj, frameIdx)
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.setVertexBuffer(0, vertexBuffer)
      pass.setIndexBuffer(indexBuffer, 'uint32')
      pass.drawIndexed(indexCount)
    },
    setPaletteSlot(slot, r, g, b, a = 1) {
      const tmp = new Float32Array([r, g, b, a])
      device.queue.writeBuffer(paletteBuffer, slot * 16, tmp)
    },
    rebind(newMesh, newMaterial, newVat) {
      vertexBuffer.destroy()
      indexBuffer.destroy()
      vertexBuffer = device.createBuffer({
        label: 'chunk-vertices',
        size: newMesh.vertices.byteLength,
        usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
      })
      device.queue.writeBuffer(vertexBuffer, 0, newMesh.vertices)
      indexBuffer = device.createBuffer({
        label: 'chunk-indices',
        size: newMesh.indices.byteLength,
        usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
      })
      device.queue.writeBuffer(indexBuffer, 0, newMesh.indices)
      indexCount = newMesh.indices.length

      if (newMaterial.palette.byteLength !== paletteBuffer.size) {
        paletteBuffer.destroy()
        paletteBuffer = device.createBuffer({
          label: 'chunk-palette',
          size: newMaterial.palette.byteLength,
          usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
        })
      }
      device.queue.writeBuffer(paletteBuffer, 0, newMaterial.palette)

      currentNumJoints = newVat.numInstances
      bindGroup = device.createBindGroup({
        layout: pipeline.getBindGroupLayout(0),
        entries: [
          { binding: 0, resource: { buffer: uniformBuffer } },
          { binding: 1, resource: { buffer: newVat.buffer } },
          { binding: 2, resource: { buffer: paletteBuffer } },
        ],
      })
    },
  }
}

