/**
 * VFX module — public API barrel export.
 */

// Shader graph
export {
  ShaderNode, UVNode, TimeNode, WorldPosNode, NormalNode, ViewDirNode, ConstantNode,
  AddNode, MultiplyNode, LerpNode, StepNode, SmoothStepNode, RemapNode,
  NoiseNode, FBMNode,
  GradientNode, FresnelNode,
  compileShaderGraph,
  NOISE_LIBRARY,
} from './shader_graph'
export type { ValueType, ShaderPort, MaterialOutput } from './shader_graph'

// Particles
export { ParticleSystem } from './particles'
export type { ParticleEmitterConfig } from './particles'

// Post-processing
export {
  createPostProcessPipelines,
  FULLSCREEN_VERT,
  BLOOM_THRESHOLD_FRAG, BLUR_FRAG, COMPOSITE_FRAG, TONEMAP_FRAG,
  DEFAULT_BLOOM,
} from './postprocess'
export type { BloomConfig, PostProcessPipelines } from './postprocess'

// Presets
export { PRESETS, lavaPreset, waterPreset, forceFieldPreset, hologramPreset, dissolvePreset } from './presets'
