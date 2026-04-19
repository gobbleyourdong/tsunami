/**
 * Input component renderer — InputDef → immediate-mode calls.
 *
 * # Status
 *   render_input  ✓ scaffold — labeled box with current value text
 *   Cursor + selection     TODO fire 7 (input system + IME shim)
 *   Keyboard capture       TODO fire 7
 *   Focus ring              TODO fire 7
 *
 * Scaffold displays the current MechanicRef-bound value as static
 * text inside a bordered box. Interactive editing lands when the
 * input system is integrated.
 */

import type { InputDef, ValueRef } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

export function render_input(spec: InputDef, ctx: RenderContext): void {
  const raw = ctx.resolve(spec.value as ValueRef<string | number>)
  const display = raw === undefined || raw === null || raw === ''
    ? (spec.placeholder ?? '')
    : String(raw)

  const is_placeholder = raw === undefined || raw === null || raw === ''
  const disabled = spec.disabled ? Boolean(ctx.resolve(spec.disabled)) : false

  ctx.ui.begin_box({
    layout: { direction: 'row', gap: 6, padding: 8 },
    style: {
      bg: 'panel',
      rounded: 'sm',
      border: disabled ? 'muted' : 'primary',
      border_width: 1,
      opacity: disabled ? 0.6 : 1,
    },
    id: spec.id,
  })

  ctx.ui.text(display, {
    size: 'md',
    color: is_placeholder ? 'muted' : 'fg',
  })

  ctx.ui.end_box()
}
