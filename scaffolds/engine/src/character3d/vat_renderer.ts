/**
 * VAT-driven instanced SPRITE renderer.
 *
 * Each instance is a view-space billboard quad sampled from a pre-baked
 * sprite texture (e.g. the output of our UNMIX → BPAD → 4CONN pipeline).
 * Sprite size is LOCKED to the source texture's native pixel dimensions —
 * a 32×32 PNG always renders as 32×32 screen pixels, never scaled.
 *
 * Vertex shader applies pixel-snap to the quad's center so the sprite's
 * internal pixels (eyes, outline, etc.) stay stable as the instance moves
 * through space. Fragment samples with nearest filtering; transparent
 * pixels are discarded.
 */

import type { VATData } from './vat'
import type { SpriteTexture } from './sprite_texture'
import { QUAD_VERTICES, QUAD_INDICES, QUAD_INDEX_COUNT } from './quad'

const VAT_SHADER = /* wgsl */ `
struct Uniforms {
  view: mat4x4f,
  proj: mat4x4f,
  frameIdx: f32,
  numInstances: f32,
  sceneW: f32,
  sceneH: f32,
  spriteHalfW: f32,   // sprite width / 2, in render-target pixels
  spriteHalfH: f32,
  pixelSnap: f32,     // 0 = off, 1 = on
  _pad: f32,
}

@group(0) @binding(0) var<uniform> uniforms: Uniforms;
@group(0) @binding(1) var<storage, read> vat: array<vec4f>;
@group(0) @binding(2) var spriteTex: texture_2d<f32>;
@group(0) @binding(3) var spriteSamp: sampler;

struct VsOut {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@vertex
fn vs_main(
  @location(0) corner: vec2f,
  @builtin(instance_index) instIdx: u32,
) -> VsOut {
  let f = u32(uniforms.frameIdx);
  let n = u32(uniforms.numInstances);
  let center = vat[f * n + instIdx].xyz;

  let centerClip = uniforms.proj * uniforms.view * vec4f(center, 1.0);
  let sceneSize = vec2f(uniforms.sceneW, uniforms.sceneH);

  let ndc = centerClip.xy / centerClip.w;
  let centerPx = (ndc * 0.5 + 0.5) * sceneSize;
  let snappedCenterPx = select(centerPx, floor(centerPx) + 0.5, uniforms.pixelSnap > 0.5);

  // Corner offset in pixel space — LOCKED to sprite's native size.
  let halfPx = vec2f(uniforms.spriteHalfW, uniforms.spriteHalfH);
  let finalPx = snappedCenterPx + corner * halfPx;
  let finalNdc = (finalPx / sceneSize) * 2.0 - 1.0;

  // UV: corner -1..+1 → 0..1, flip Y (texture origin top-left, corner Y up).
  let uv = vec2f(corner.x * 0.5 + 0.5, 1.0 - (corner.y * 0.5 + 0.5));

  var out: VsOut;
  out.position = vec4f(finalNdc * centerClip.w, centerClip.z, centerClip.w);
  out.uv = uv;
  return out;
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  let sample = textureSample(spriteTex, spriteSamp, uv);
  // Binary alpha (our BPAD pipeline emits 0 or 255) — hard discard.
  if (sample.a < 0.5) { discard; }
  return sample;
}
`

export interface VATRenderer {
  draw(
    pass: GPURenderPassEncoder,
    view: Float32Array,
    proj: Float32Array,
    frameIdx: number,
    opts?: {
      sceneW?: number
      sceneH?: number
      pixelSnap?: boolean
    }
  ): void
}

export function createVATRenderer(
  device: GPUDevice,
  format: GPUTextureFormat,
  vat: VATData,
  sprite: SpriteTexture
): VATRenderer {
  const shader = device.createShaderModule({ code: VAT_SHADER, label: 'vat-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'vat-pipeline',
    layout: 'auto',
    vertex: {
      module: shader,
      entryPoint: 'vs_main',
      buffers: [
        {
          arrayStride: 8,
          attributes: [{ shaderLocation: 0, offset: 0, format: 'float32x2' }],
        },
      ],
    },
    fragment: {
      module: shader,
      entryPoint: 'fs_main',
      targets: [
        {
          format,
          blend: {
            color: {
              srcFactor: 'src-alpha',
              dstFactor: 'one-minus-src-alpha',
            },
            alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha' },
          },
        },
      ],
    },
    primitive: { topology: 'triangle-list', cullMode: 'none', frontFace: 'ccw' },
    depthStencil: {
      format: 'depth24plus-stencil8',
      depthWriteEnabled: true,
      depthCompare: 'less',
    },
  })

  const vb = device.createBuffer({
    size: QUAD_VERTICES.byteLength,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(vb, 0, QUAD_VERTICES)

  const ib = device.createBuffer({
    size: QUAD_INDICES.byteLength,
    usage: GPUBufferUsage.INDEX | GPUBufferUsage.COPY_DST,
  })
  device.queue.writeBuffer(ib, 0, QUAD_INDICES)

  // Uniforms: 64 + 64 + 8×f32 = 160 bytes
  const uniformBuffer = device.createBuffer({
    size: 160,
    usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
  })
  const uniformData = new Float32Array(40)

  const bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: { buffer: uniformBuffer } },
      { binding: 1, resource: { buffer: vat.buffer } },
      { binding: 2, resource: sprite.view },
      { binding: 3, resource: sprite.sampler },
    ],
  })

  const halfW = sprite.width / 2
  const halfH = sprite.height / 2

  return {
    draw(pass, view, proj, frameIdx, opts = {}) {
      uniformData.set(view, 0)
      uniformData.set(proj, 16)
      uniformData[32] = frameIdx
      uniformData[33] = vat.numInstances
      uniformData[34] = opts.sceneW ?? 640
      uniformData[35] = opts.sceneH ?? 360
      uniformData[36] = halfW
      uniformData[37] = halfH
      uniformData[38] = opts.pixelSnap ? 1 : 0
      device.queue.writeBuffer(uniformBuffer, 0, uniformData)

      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.setVertexBuffer(0, vb)
      pass.setIndexBuffer(ib, 'uint16')
      pass.drawIndexed(QUAD_INDEX_COUNT, vat.numInstances)
    },
  }
}
