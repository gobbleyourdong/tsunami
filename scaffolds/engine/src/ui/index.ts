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
 *   webgpu_compiler  ✓ scaffold — exhaustive switch: 25 ComponentDef → immediate UI
 *   components/      ✓ scaffold — 8 widget renderers (button, card, dialog,
 *                                  progress, input, hud, menu, dialog_tree)
 *                                  — webgpu_compiler delegates to these
 *   dom_compiler     ✓ scaffold — ComponentDef → DomDescriptor (framework-free;
 *                                  web scaffolds wrap with React.createElement)
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
export {
  compileToWebGPU,
  createStubRenderContext,
  resolveValue,
  dispatchAll,
} from './webgpu_compiler'
export type { RenderContext } from './webgpu_compiler'
export * from './components'
export {
  compileToReact,
  createStubDomRenderContext,
} from './dom_compiler'
export type { DomDescriptor, DomRenderContext } from './dom_compiler'
