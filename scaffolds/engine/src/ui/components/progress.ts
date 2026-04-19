/**
 * Progress component renderer — ProgressDef → immediate-mode calls.
 *
 * # Status
 *   render_progress  ✓ scaffold — bar + optional value/max label
 *   Striped / animated fill  TODO v1.2
 */

import type { ProgressDef } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

export function render_progress(spec: ProgressDef, ctx: RenderContext): void {
  const value = Number(ctx.resolve(spec.value))
  const max = spec.max !== undefined ? Number(ctx.resolve(spec.max)) : 1

  ctx.ui.progress(value, max, {
    color: spec.color,
    size: spec.size,
  })

  if (spec.show_label) {
    const fmt = (n: number) => Number.isInteger(n) ? String(n) : n.toFixed(1)
    ctx.ui.text(`${fmt(value)} / ${fmt(max)}`, {
      size: 'sm',
      color: 'muted',
    })
  }
}
