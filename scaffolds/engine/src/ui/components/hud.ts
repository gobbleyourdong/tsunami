/**
 * HUD component renderer — HUDDef → immediate-mode calls.
 *
 * # Status
 *   render_hud      ✓ scaffold — anchored overlay, per-field dispatch
 *   Text field       ✓ scaffold
 *   Counter field    ✓ scaffold
 *   Bar field        ✓ scaffold
 *   Icon+text field  ✓ scaffold (icon placeholder until icon atlas)
 *   Avatar field     ✓ scaffold (icon placeholder)
 *   Mini-map field   TODO fire 7 (world-overview renderer)
 *   Format string    ✓ scaffold — {value} / {max} substitution
 */

import type { HUDDef, HUDField } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

function apply_format(fmt: string, value: unknown, max?: unknown): string {
  return fmt
    .replace(/\{value\}/g, String(value ?? ''))
    .replace(/\{max\}/g, String(max ?? ''))
}

function render_field(field: HUDField, ctx: RenderContext): void {
  const label = field.label ? `${ctx.resolve(field.label)} ` : ''

  switch (field.type) {
    case 'text':
    case 'counter': {
      const value = ctx.resolve(field.value)
      const max = field.max ? ctx.resolve(field.max) : undefined
      const text = field.format
        ? apply_format(field.format, value, max)
        : `${label}${value ?? ''}`
      ctx.ui.text(text, { size: 'md', color: field.color ?? 'fg' })
      return
    }
    case 'bar': {
      const v = Number(ctx.resolve(field.value))
      const m = field.max ? Number(ctx.resolve(field.max)) : 1
      if (label) ctx.ui.text(label, { size: 'sm', color: 'muted' })
      ctx.ui.progress(v, m, { color: field.color })
      return
    }
    case 'icon+text': {
      if (field.icon) ctx.ui.icon(field.icon, { size: 'md', color: field.color })
      const value = ctx.resolve(field.value)
      ctx.ui.text(`${label}${value ?? ''}`, { size: 'md', color: field.color ?? 'fg' })
      return
    }
    case 'avatar':
      ctx.ui.icon(field.icon ?? 'avatar', { size: 'lg', color: field.color })
      return
    case 'mini_map':
      // TODO fire 7 — real world overview render pass.
      ctx.ui.icon('minimap', { size: '2xl', color: 'muted' })
      return
  }
}

export function render_hud(spec: HUDDef, ctx: RenderContext): void {
  ctx.ui.begin_box({
    layout: {
      anchor: spec.anchor,
      direction: spec.layout_direction ?? 'column',
      gap: spec.style?.gap ?? 'sm',
      padding: spec.style?.padding ?? 'md',
    },
    style: {
      bg: spec.style?.bg ?? 'glass',
      rounded: 'md',
    },
    id: spec.id,
  })

  for (const field of spec.fields) render_field(field, ctx)

  ctx.ui.end_box()
}
