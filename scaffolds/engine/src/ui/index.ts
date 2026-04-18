/**
 * UI subsystem — WebGPU-native declarative UI.
 *
 * # Scaffold status
 *   text             ✓ Sample Newton renderer + atlas baker (shipped)
 *   theme            ✓ scaffold — token types + DEFAULT_THEME + resolvers
 *   layout           ✓ scaffold — Layout/Size/Anchor types + stub engine
 *   primitives       ✓ scaffold — quad batcher + rounded-rect SDF shader
 *   immediate        ✓ scaffold — ImGui-style shell over primitives + text
 *   component_def    ✓ scaffold — discriminated union of 25 ComponentDef kinds
 *   webgpu_compiler  TODO — ComponentDef → immediate-mode calls
 *   components/      TODO — per-widget compositions
 *   dom_compiler     TODO — ComponentDef → React (for web scaffolds)
 *
 * Full spec: `ark/tsunami/design/action_blocks/ui_framework/attempts/attempt_001.md`.
 */

export * from './text'
export { TEXT_SHADER_WGSL } from './text_shader'
export * from './theme'
export * from './layout'
export * from './primitives'
export { PRIMITIVES_SHADER_WGSL } from './primitives_shader'
export * from './immediate'
export * from './component_def'
