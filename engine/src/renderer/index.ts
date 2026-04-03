/**
 * Renderer module — public API barrel export.
 */

export { initGPU, resizeGPU, createDepthTexture } from './gpu'
export type { GPUContext } from './gpu'
export { compileShader, clearShaderCache, TRIANGLE_SHADER, MESH_SHADER, INSTANCED_SHADER } from './shader'
export {
  createRenderPipeline,
  createComputePipeline,
  clearPipelineCache,
  createBindGroup,
} from './pipeline'
export type { RenderPipelineDesc, ComputePipelineDesc } from './pipeline'
export {
  createVertexBuffer,
  createIndexBuffer,
  createUniformBuffer,
  createStorageBuffer,
  updateBuffer,
  VERTEX_POSITION_COLOR,
  VERTEX_POSITION_NORMAL_UV,
  VERTEX_POSITION_NORMAL,
} from './buffer'
export { loadTexture, createTextureFromBitmap, createSolidColorTexture } from './texture'
export type { TextureHandle } from './texture'
export { Camera } from './camera'
export type { CameraOptions, CameraMode, ControlMode, FrustumPlane } from './camera'
export { FrameLoop, colorPass } from './frame'
export type { FrameStats, FrameCallback } from './frame'
export { createCubeGeometry, createPlaneGeometry, createSphereGeometry } from './geometry'
export type { GeometryData } from './geometry'
