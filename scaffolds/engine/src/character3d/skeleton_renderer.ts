/**
 * Skeleton renderer — one instanced cube per joint, each transformed by
 * its joint's world matrix sampled from the VAT storage buffer.
 *
 * Buffer layout match skeleton.ts bake output: 4 consecutive vec4f per
 * (frameIdx, jointIdx) = a mat4. Shader reconstructs it and applies to
 * the cube's local verts (scaled to a small joint-size box).
 */

import type { VATData } from './vat'
import type { SpriteMaterial } from './mixamo_loader'
import {
  CUBE_VERTICES,
  CUBE_INDICES,
  CUBE_INDEX_COUNT,
  CUBE_VERTEX_STRIDE,
} from './cube'

const SKELETON_SHADER = /* wgsl */ `
struct Uniforms {
  view: mat4x4f,
  proj: mat4x4f,
  frameIdx: f32,
  numJoints: f32,
  boxScale: f32,
  outputMode: f32,   // 0 = display (LUT color + lighting), 1 = G-buffer packed
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(0) @binding(1) var<storage, read> joints: array<vec4f>;
// Per-bone display matrix: maps unit cube → bone-shaped box pointing along
// the bone direction. 4 vec4f per bone (column-major mat4).
@group(0) @binding(2) var<storage, read> boneDisplay: array<vec4f>;
// Per-bone palette index (material slot). Runtime edits to the palette
// recolor every bone using that slot — classic SNES-CRAM pattern.
@group(0) @binding(3) var<storage, read> paletteIdx: array<u32>;
// Palette LUT. Slot index → RGBA. Edit via writeBuffer for live recolor.
@group(0) @binding(4) var<storage, read> palette: array<vec4f>;

struct VsOut {
  @builtin(position) position: vec4f,
  @location(0) normal: vec3f,
  @location(1) jointTint: vec3f,
  @location(2) paletteSlot: f32,
  @location(3) depthNdc: f32,          // [0, 1] normalized device depth
}

@vertex
fn vs_main(
  @location(0) vPos: vec3f,
  @location(1) vNormal: vec3f,
  @builtin(instance_index) jointIdx: u32,
) -> VsOut {
  let f = u32(uniforms.frameIdx);
  let n = u32(uniforms.numJoints);
  let base = (f * n + jointIdx) * 4u;

  // Reconstruct joint world matrix (column-major).
  let m = mat4x4f(
    joints[base + 0u],
    joints[base + 1u],
    joints[base + 2u],
    joints[base + 3u],
  );

  // Reconstruct the per-bone display matrix (orient + scale cube → bone box).
  let dbase = jointIdx * 4u;
  let d = mat4x4f(
    boneDisplay[dbase + 0u],
    boneDisplay[dbase + 1u],
    boneDisplay[dbase + 2u],
    boneDisplay[dbase + 3u],
  );

  // Local → bone-oriented → joint → world
  let localBonePos = (d * vec4f(vPos, 1.0)).xyz * uniforms.boxScale;
  let worldPos = (m * vec4f(localBonePos, 1.0)).xyz;
  let localBoneNormal = (d * vec4f(vNormal, 0.0)).xyz;
  let worldNormal = normalize((m * vec4f(localBoneNormal, 0.0)).xyz);

  // Palette-indexed color: per-bone slot → LUT lookup. Recolor at runtime
  // by writing palette[slot] — no re-bake, no pipeline state change.
  let slot = paletteIdx[jointIdx];
  let tint = palette[slot].rgb;

  let clip = uniforms.proj * uniforms.view * vec4f(worldPos, 1.0);
  var out: VsOut;
  out.position = clip;
  out.normal = worldNormal;
  out.jointTint = tint;
  out.paletteSlot = f32(slot);
  // Depth: clip.z / clip.w ∈ [0, 1] for ortho/persp after WebGPU projection.
  out.depthNdc = clamp(clip.z / clip.w, 0.0, 1.0);
  return out;
}
`

// Two fragment-shader variants. Selected at pipeline creation via the
// mrt option so existing demos that expect a single-target pipeline
// (sprite_bake, atlas_runtime) keep working unchanged.

// SINGLE-TARGET variant (default): one color output at @location(0).
// outputMode switches between flat (no shading) and gbuffer-packed.
const FS_SINGLE = /* wgsl */ `
@fragment
fn fs_main(in: VsOut) -> @location(0) vec4f {
  let n = normalize(in.normal);
  if (uniforms.outputMode > 0.5) {
    let idx = in.paletteSlot / 255.0;
    return vec4f(idx, n.x * 0.5 + 0.5, n.y * 0.5 + 0.5, in.depthNdc);
  }
  // Flat palette color — no Lambert (pixel-art convention).
  return vec4f(in.jointTint, 1.0);
}
`

// MRT variant: three color outputs.
//   location 0: flat albedo
//   location 1: world-space normal encoded [0,1]
//   location 2: depth in R channel
const FS_MRT = /* wgsl */ `
struct FsOut {
  @location(0) color: vec4f,
  @location(1) normal: vec4f,
  @location(2) depth: vec4f,
}
@fragment
fn fs_main(in: VsOut) -> FsOut {
  let n = normalize(in.normal);
  var out: FsOut;
  out.color  = vec4f(in.jointTint, 1.0);
  out.normal = vec4f(n * 0.5 + 0.5, 1.0);
  out.depth  = vec4f(in.depthNdc, 0.0, 0.0, 1.0);
  return out;
}
`

export interface SkeletonRenderer {
  draw(
    pass: GPURenderPassEncoder,
    view: Float32Array,
    proj: Float32Array,
    frameIdx: number,
    boxScale?: number,
    outputMode?: 'display' | 'gbuffer'
  ): void
  /** Rebind VAT + bone-display + sprite-material (full swap). */
  rebind(vat: VATData, boneDisplay: Float32Array, material: SpriteMaterial): void
  /** Hot-edit a single palette slot. Next render shows the new color. */
  setPaletteSlot(slot: number, r: number, g: number, b: number, a?: number): void
}

export function createSkeletonRenderer(
  device: GPUDevice,
  format: GPUTextureFormat,
  vat: VATData,
  boneDisplay: Float32Array,
  material: SpriteMaterial,
  opts: { mrt?: boolean } = {}
): SkeletonRenderer {
  const mrt = opts.mrt ?? false
  const shaderCode = SKELETON_SHADER + (mrt ? FS_MRT : FS_SINGLE)
  const shader = device.createShaderModule({ code: shaderCode, label: 'skeleton-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'skeleton-pipeline',
    layout: 'auto',
    vertex: {
      module: shader,
      entryPoint: 'vs_main',
      buffers: [
        {
          arrayStride: CUBE_VERTEX_STRIDE,
          attributes: [
            { shaderLocation: 0, offset: 0,  format: 'float32x3' },
            { shaderLocation: 1, offset: 12, format: 'float32x3' },
          ],
        },
      ],
    },
    fragment: {
      module: shader,
      entryPoint: 'fs_main',
      targets: mrt
        ? [{ format }, { format }, { format }]   // MRT: color, normal, depth
        : [{ format }],                          // single-target (back-compat)
    },
    primitive: { topology: 'triangle-list', cullMode: 'back', frontFace: 'ccw' },
    depthStencil: {
      format: 'depth24plus-stencil8',
      depthWriteEnabled: true,
      depthCompare: 'less',
    },
  })

  const vb = device.createBuffer({
    size: CUBE_VERTICES.byteLength,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(vb, 0, CUBE_VERTICES)

  const ib = device.createBuffer({
    size: CUBE_INDICES.byteLength,
    usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(ib, 0, CUBE_INDICES)

  // Uniforms: 64 + 64 + 4×f32 = 144 bytes
  const uniformBuffer = device.createBuffer({
    size: 144,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(36)

  function makeStorageBuffer(label: string, data: ArrayBufferView): GPUBuffer {
    const b = device.createBuffer({
      label,
      size: data.byteLength,
      usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST,
    })
    device.queue.writeBuffer(b, 0, data)
    return b
  }

  let displayBuffer = makeStorageBuffer('skeleton-bone-display', boneDisplay)
  let paletteIdxBuffer = makeStorageBuffer('skeleton-palette-idx', material.paletteIndices)
  let paletteBuffer = makeStorageBuffer('skeleton-palette', material.palette)

  function buildBindGroup(vatBuf: GPUBuffer) {
    return device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: { buffer: uniformBuffer } },
        { binding: 1, resource: { buffer: vatBuf } },
        { binding: 2, resource: { buffer: displayBuffer } },
        { binding: 3, resource: { buffer: paletteIdxBuffer } },
        { binding: 4, resource: { buffer: paletteBuffer } },
      ],
    })
  }

  let bindGroup = buildBindGroup(vat.buffer)
  let currentVAT = vat

  return {
    draw(pass, view, proj, frameIdx, boxScale = 1.0, outputMode = 'display') {
      uniformData.set(view, 0)
      uniformData.set(proj, 16)
      uniformData[32] = frameIdx
      uniformData[33] = currentVAT.numInstances
      uniformData[34] = boxScale
      uniformData[35] = outputMode === 'gbuffer' ? 1 : 0
      device.queue.writeBuffer(uniformBuffer, 0, uniformData)

      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.setVertexBuffer(0, vb)
      pass.setIndexBuffer(ib, 'uint16')
      pass.drawIndexed(CUBE_INDEX_COUNT, currentVAT.numInstances)
    },
    rebind(nextVAT, nextDisplay, nextMaterial) {
      currentVAT = nextVAT
      displayBuffer.destroy()
      paletteIdxBuffer.destroy()
      paletteBuffer.destroy()
      displayBuffer = makeStorageBuffer('skeleton-bone-display', nextDisplay)
      paletteIdxBuffer = makeStorageBuffer('skeleton-palette-idx', nextMaterial.paletteIndices)
      paletteBuffer = makeStorageBuffer('skeleton-palette', nextMaterial.palette)
      bindGroup = buildBindGroup(nextVAT.buffer)
    },
    setPaletteSlot(slot, r, g, b, a = 1) {
      const rgba = new Float32Array([r, g, b, a])
      device.queue.writeBuffer(paletteBuffer, slot * 16, rgba)
    },
  }
}
