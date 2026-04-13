/**
 * Texture loading (PNG/JPEG → GPUTexture) with mipmap generation.
 */

export interface TextureHandle {
  texture: GPUTexture
  view: GPUTextureView
  sampler: GPUSampler
  width: number
  height: number
}

export async function loadTexture(
  device: GPUDevice,
  url: string,
  options?: {
    generateMipmaps?: boolean
    filterMode?: GPUFilterMode
    addressMode?: GPUAddressMode
  }
): Promise<TextureHandle> {
  const response = await fetch(url)
  const blob = await response.blob()
  const bitmap = await createImageBitmap(blob, { colorSpaceConversion: 'none' })

  return createTextureFromBitmap(device, bitmap, options)
}

export function createTextureFromBitmap(
  device: GPUDevice,
  bitmap: ImageBitmap,
  options?: {
    generateMipmaps?: boolean
    filterMode?: GPUFilterMode
    addressMode?: GPUAddressMode
  }
): TextureHandle {
  const { width, height } = bitmap
  const genMips = options?.generateMipmaps ?? true
  const mipCount = genMips ? Math.floor(Math.log2(Math.max(width, height))) + 1 : 1

  const texture = device.createTexture({
    size: { width, height },
    format: 'rgba8unorm',
    usage:
      GPUTextureUsage.TEXTURE_BINDING |
      GPUTextureUsage.COPY_DST |
      GPUTextureUsage.RENDER_ATTACHMENT,
    mipLevelCount: mipCount,
  })

  device.queue.copyExternalImageToTexture(
    { source: bitmap },
    { texture, mipLevel: 0 },
    { width, height }
  )

  if (genMips && mipCount > 1) {
    generateMipmaps(device, texture, width, height, mipCount)
  }

  const view = texture.createView()

  const filterMode = options?.filterMode ?? 'linear'
  const addressMode = options?.addressMode ?? 'repeat'
  const sampler = device.createSampler({
    magFilter: filterMode,
    minFilter: filterMode,
    mipmapFilter: filterMode,
    addressModeU: addressMode,
    addressModeV: addressMode,
    addressModeW: addressMode,
    maxAnisotropy: filterMode === 'linear' ? 4 : 1,
  })

  return { texture, view, sampler, width, height }
}

// Simple blit-based mipmap generation
const mipShaderCode = /* wgsl */ `
@group(0) @binding(0) var mipSampler: sampler;
@group(0) @binding(1) var mipTexture: texture_2d<f32>;

struct VertexOutput {
  @builtin(position) position: vec4f,
  @location(0) uv: vec2f,
};

@vertex
fn vs_main(@builtin(vertex_index) idx: u32) -> VertexOutput {
  // fullscreen triangle
  var pos = array<vec2f, 3>(
    vec2f(-1.0, -1.0),
    vec2f( 3.0, -1.0),
    vec2f(-1.0,  3.0),
  );
  var uv = array<vec2f, 3>(
    vec2f(0.0, 1.0),
    vec2f(2.0, 1.0),
    vec2f(0.0, -1.0),
  );
  var out: VertexOutput;
  out.position = vec4f(pos[idx], 0.0, 1.0);
  out.uv = uv[idx];
  return out;
}

@fragment
fn fs_main(in: VertexOutput) -> @location(0) vec4f {
  return textureSample(mipTexture, mipSampler, in.uv);
}
`

let mipPipeline: GPURenderPipeline | null = null
let mipSampler: GPUSampler | null = null

function getMipPipeline(device: GPUDevice): { pipeline: GPURenderPipeline; sampler: GPUSampler } {
  if (!mipPipeline) {
    const module = device.createShaderModule({ code: mipShaderCode, label: 'mip-gen' })
    mipPipeline = device.createRenderPipeline({
      label: 'mip-gen-pipeline',
      layout: 'auto',
      vertex: { module, entryPoint: 'vs_main' },
      fragment: {
        module,
        entryPoint: 'fs_main',
        targets: [{ format: 'rgba8unorm' }],
      },
    })
    mipSampler = device.createSampler({ minFilter: 'linear', magFilter: 'linear' })
  }
  return { pipeline: mipPipeline!, sampler: mipSampler! }
}

function generateMipmaps(
  device: GPUDevice,
  texture: GPUTexture,
  width: number,
  height: number,
  mipCount: number
): void {
  const { pipeline, sampler } = getMipPipeline(device)
  const encoder = device.createCommandEncoder({ label: 'mip-gen' })

  let mipWidth = width
  let mipHeight = height

  for (let level = 1; level < mipCount; level++) {
    const srcView = texture.createView({
      baseMipLevel: level - 1,
      mipLevelCount: 1,
    })

    mipWidth = Math.max(1, mipWidth >> 1)
    mipHeight = Math.max(1, mipHeight >> 1)

    const dstView = texture.createView({
      baseMipLevel: level,
      mipLevelCount: 1,
    })

    const bindGroup = device.createBindGroup({
      layout: pipeline.getBindGroupLayout(0),
      entries: [
        { binding: 0, resource: sampler },
        { binding: 1, resource: srcView },
      ],
    })

    const pass = encoder.beginRenderPass({
      colorAttachments: [
        {
          view: dstView,
          loadOp: 'clear',
          storeOp: 'store',
        },
      ],
    })
    pass.setPipeline(pipeline)
    pass.setBindGroup(0, bindGroup)
    pass.draw(3)
    pass.end()
  }

  device.queue.submit([encoder.finish()])
}

export function createSolidColorTexture(
  device: GPUDevice,
  r: number,
  g: number,
  b: number,
  a = 255
): TextureHandle {
  const texture = device.createTexture({
    size: { width: 1, height: 1 },
    format: 'rgba8unorm',
    usage: GPUTextureUsage.TEXTURE_BINDING | GPUTextureUsage.COPY_DST,
  })
  device.queue.writeTexture(
    { texture },
    new Uint8Array([r, g, b, a]),
    { bytesPerRow: 4 },
    { width: 1, height: 1 }
  )
  const view = texture.createView()
  const sampler = device.createSampler()
  return { texture, view, sampler, width: 1, height: 1 }
}
