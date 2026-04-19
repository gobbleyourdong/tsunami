/**
 * Button component renderer — ButtonDef → immediate-mode calls.
 *
 * # Status
 *   render_button   ✓ scaffold — variant + color + size + disabled
 *   Icon left/right TODO fire 7 (needs icon atlas)
 *   Hover / press states TODO (needs input system)
 *
 * Follows `text.ts` scaffolding pattern: one exported function,
 * type-import-only from webgpu_compiler to avoid circular runtime deps.
 */

import type { ButtonDef } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

export function render_button(spec: ButtonDef, ctx: RenderContext): void {
  const label = String(ctx.resolve(spec.label) ?? '')
  const disabled = spec.disabled ? Boolean(ctx.resolve(spec.disabled)) : false

  const clicked = ctx.ui.button(label, {
    variant: spec.variant,
    color: spec.color,
    size: spec.size,
    disabled,
    icon_left: spec.icon_left,
    icon_right: spec.icon_right,
  })

  if (clicked && spec.on_click && !disabled) {
    ctx.dispatch(spec.on_click)
  }
}
