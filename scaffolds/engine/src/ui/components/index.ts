/**
 * Component renderers — one file per widget.
 *
 * Each `render_<widget>` function takes its ComponentDef sub-type and
 * a RenderContext, and dispatches immediate-mode UI calls. Shared
 * pattern; see `text.ts` for the full scaffolding exemplar.
 *
 * `webgpu_compiler.compileToWebGPU` delegates the covered cases here;
 * scaffolds can also call these directly for finer control.
 */

export { render_button } from './button'
export { render_card } from './card'
export { render_dialog } from './dialog'
export { render_progress } from './progress'
export { render_input } from './input'
export { render_hud } from './hud'
export { render_menu } from './menu'
export { render_dialog_tree } from './dialog_tree'
