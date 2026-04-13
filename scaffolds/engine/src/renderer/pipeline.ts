/**
 * Render pipeline state objects with caching.
 * Depth/stencil, blend states, compute pipelines.
 */

// --- Pipeline cache ---

const pipelineCache = new Map<string, GPURenderPipeline>()
const computeCache = new Map<string, GPUComputePipeline>()

export interface RenderPipelineDesc {
  label?: string
  shader: GPUShaderModule
  vertexBuffers: GPUVertexBufferLayout[]
  format: GPUTextureFormat
  depthStencil?: boolean
  blend?: GPUBlendState
  topology?: GPUPrimitiveTopology
  cullMode?: GPUCullMode
  bindGroupLayouts?: GPUBindGroupLayout[]
}

function pipelineKey(desc: RenderPipelineDesc): string {
  return `${desc.label ?? ''}_${desc.topology ?? 'triangle-list'}_${desc.cullMode ?? 'back'}_${desc.depthStencil ?? true}_${desc.format}`
}

export function createRenderPipeline(
  device: GPUDevice,
  desc: RenderPipelineDesc
): GPURenderPipeline {
  const key = pipelineKey(desc)
  const cached = pipelineCache.get(key)
  if (cached) return cached

  const pipelineLayout = desc.bindGroupLayouts
    ? device.createPipelineLayout({ bindGroupLayouts: desc.bindGroupLayouts })
    : 'auto'

  const pipeline = device.createRenderPipeline({
    label: desc.label ?? 'render-pipeline',
    layout: pipelineLayout,
    vertex: {
      module: desc.shader,
      entryPoint: 'vs_main',
      buffers: desc.vertexBuffers,
    },
    fragment: {
      module: desc.shader,
      entryPoint: 'fs_main',
      targets: [
        {
          format: desc.format,
          blend: desc.blend ?? {
            color: { srcFactor: 'src-alpha', dstFactor: 'one-minus-src-alpha' },
            alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha' },
          },
        },
      ],
    },
    primitive: {
      topology: desc.topology ?? 'triangle-list',
      cullMode: desc.cullMode ?? 'back',
      frontFace: 'ccw',
    },
    depthStencil: desc.depthStencil !== false
      ? {
          format: 'depth24plus-stencil8',
          depthWriteEnabled: true,
          depthCompare: 'less',
        }
      : undefined,
  })

  pipelineCache.set(key, pipeline)
  return pipeline
}

// --- Compute pipeline ---

export interface ComputePipelineDesc {
  label?: string
  shader: GPUShaderModule
  entryPoint?: string
  bindGroupLayouts?: GPUBindGroupLayout[]
}

export function createComputePipeline(
  device: GPUDevice,
  desc: ComputePipelineDesc
): GPUComputePipeline {
  const key = `${desc.label ?? ''}_${desc.entryPoint ?? 'main'}`
  const cached = computeCache.get(key)
  if (cached) return cached

  const pipelineLayout = desc.bindGroupLayouts
    ? device.createPipelineLayout({ bindGroupLayouts: desc.bindGroupLayouts })
    : 'auto'

  const pipeline = device.createComputePipeline({
    label: desc.label ?? 'compute-pipeline',
    layout: pipelineLayout,
    compute: {
      module: desc.shader,
      entryPoint: desc.entryPoint ?? 'main',
    },
  })

  computeCache.set(key, pipeline)
  return pipeline
}

export function clearPipelineCache(): void {
  pipelineCache.clear()
  computeCache.clear()
}

// --- Bind group helpers ---

export function createBindGroup(
  device: GPUDevice,
  layout: GPUBindGroupLayout,
  entries: GPUBindGroupEntry[],
  label?: string
): GPUBindGroup {
  return device.createBindGroup({
    layout,
    entries,
    label: label ?? 'bind-group',
  })
}
