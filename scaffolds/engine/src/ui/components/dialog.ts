/**
 * Dialog component renderer — DialogDef → immediate-mode calls.
 *
 * # Status
 *   render_dialog      ✓ scaffold — open-gated, centered, title + children
 *   Backdrop dimmer    TODO fire 7 (full-screen semi-transparent rect)
 *   Esc / click-outside TODO (input system dependency)
 *   Size presets       ✓ scaffold — sm/md/lg/xl/fullscreen as padding hint
 */

import type { DialogDef } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'
import type { SizeToken } from '../theme'

const SIZE_PADDING: Record<NonNullable<DialogDef['size']>, SizeToken> = {
  sm: 'md',
  md: 'lg',
  lg: 'xl',
  xl: '2xl',
  fullscreen: '2xl',
}

export function render_dialog(spec: DialogDef, ctx: RenderContext): void {
  const open = Boolean(ctx.resolve(spec.open))
  if (!open) return

  const padding = SIZE_PADDING[spec.size ?? 'md']

  ctx.ui.begin_box({
    layout: { anchor: 'center', padding },
    style: {
      bg: 'panel',
      border: 'muted',
      border_width: 1,
      rounded: 'lg',
    },
    id: spec.id,
  })

  if (spec.title) {
    ctx.ui.text(String(ctx.resolve(spec.title) ?? ''), {
      size: 'lg',
      weight: 'bold',
      color: 'fg',
    })
    ctx.ui.spacer(8)
  }

  for (const child of spec.children) ctx.compile(child)

  ctx.ui.end_box()
}
