/**
 * Fullscreen nearest-neighbor blit — samples a source texture onto the
 * current render target with no filtering. Used for pixel-art-style
 * low-resolution rendering: scene renders into a small internal texture,
 * blitter upscales it to the canvas with nearest filter so pixels stay
 * crisp at any zoom (Celeste / Stardew model).
 *
 * Uses the classic vertex-id fullscreen-triangle trick — no vertex buffer
 * required. Triangle covers [-1,+3]² in clip space; UV is derived from
 * vertex_index bits.
 */

const BLIT_SHADER = /* wgsl */ `
@group(0) @binding(0) var src: texture_2d<f32>;
@group(0) @binding(1) var samp: sampler;

struct VsOut {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
}

@vertex
fn vs_main(@builtin(vertex_index) vid: u32) -> VsOut {
  // Verts 0/1/2 map to clip (-1,-1) (3,-1) (-1,3) — covers full NDC.
  let c = vec2f(f32((vid << 1u) & 2u), f32(vid & 2u));
  var out: VsOut;
  out.position = vec4f(c * 2.0 - 1.0, 0.0, 1.0);
  out.uv = vec2f(c.x, 1.0 - c.y);
  return out;
}

@fragment
fn fs_main(@location(0) uv: vec2f) -> @location(0) vec4f {
  return textureSample(src, samp, uv);
}
`

export interface Blitter {
  blit(encoder: GPUCommandEncoder, destView: GPUTextureView): void
}

export function createBlitter(
  device: GPUDevice,
  format: GPUTextureFormat,
  sourceView: GPUTextureView
): Blitter {
  const shader = device.createShaderModule({ code: BLIT_SHADER, label: 'blit-shader' })

  const pipeline = device.createRenderPipeline({
    label: 'blit-pipeline',
    layout: 'auto',
    vertex: { module: shader, entryPoint: 'vs_main' },
    fragment: {
      module: shader,
      entryPoint: 'fs_main',
      targets: [{ format }],
    },
    primitive: { topology: 'triangle-list' },
  })

  const sampler = device.createSampler({
    label: 'blit-nearest',
    magFilter: 'nearest',
    minFilter: 'nearest',
  })

  const bindGroup = device.createBindGroup({
    layout: pipeline.getBindGroupLayout(0),
    entries: [
      { binding: 0, resource: sourceView },
      { binding: 1, resource: sampler },
    ],
  })

  return {
    blit(encoder, destView) {
      const pass = encoder.beginRenderPass({
        colorAttachments: [
          {
            view: destView,
            loadOp: 'clear',
            storeOp: 'store',
            clearValue: { r: 0, g: 0, b: 0, a: 1 },
          },
        ],
      })
      pass.setPipeline(pipeline)
      pass.setBindGroup(0, bindGroup)
      pass.draw(3)
      pass.end()
    },
  }
}
