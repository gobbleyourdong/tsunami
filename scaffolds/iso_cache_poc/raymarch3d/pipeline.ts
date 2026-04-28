// pipeline.ts — WebGPU render pipeline + bind group layout for the
// raymarch shader. Single render target (color), no depth.

import shaderSource from './raymarch.wgsl?raw';

export interface RaymarchPipeline {
  pipeline: GPURenderPipeline;
  bindGroupLayout: GPUBindGroupLayout;
}

export function createRaymarchPipeline(
  device: GPUDevice,
  format: GPUTextureFormat,
): RaymarchPipeline {
  const module = device.createShaderModule({
    label: 'raymarch3d-shader',
    code: shaderSource,
  });

  const bindGroupLayout = device.createBindGroupLayout({
    label: 'raymarch3d-bgl',
    entries: [
      // 0: uniform — camera + counts
      {
        binding: 0,
        visibility: GPUShaderStage.FRAGMENT,
        buffer: { type: 'uniform' },
      },
      // 1: primitives storage (read-only)
      {
        binding: 1,
        visibility: GPUShaderStage.FRAGMENT,
        buffer: { type: 'read-only-storage' },
      },
      // 2: palette storage (read-only)
      {
        binding: 2,
        visibility: GPUShaderStage.FRAGMENT,
        buffer: { type: 'read-only-storage' },
      },
    ],
  });

  const pipelineLayout = device.createPipelineLayout({
    label: 'raymarch3d-pipeline-layout',
    bindGroupLayouts: [bindGroupLayout],
  });

  const pipeline = device.createRenderPipeline({
    label: 'raymarch3d-pipeline',
    layout: pipelineLayout,
    vertex: { module, entryPoint: 'vs_main' },
    fragment: {
      module,
      entryPoint: 'fs_main',
      targets: [{ format }],
    },
    primitive: { topology: 'triangle-list' },
  });

  return { pipeline, bindGroupLayout };
}
