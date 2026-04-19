/**
 * Card component renderer — CardDef → immediate-mode calls.
 *
 * # Status
 *   render_card    ✓ scaffold — bg/border/rounded/shadow + children walk
 *   Glass style    ✓ scaffold — routes to 'glass' bg token
 *   Shadow render  TODO v1.2 (needs primitives shadow pass)
 */

import type { CardDef } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

export function render_card(spec: CardDef, ctx: RenderContext): void {
  const style = spec.style ?? {}
  ctx.ui.begin_box({
    layout: spec.layout,
    style: {
      bg: style.glass ? 'glass' : (style.bg ?? 'panel'),
      border: style.border,
      border_width: style.border_width,
      rounded: style.rounded ?? 'md',
      shadow: style.shadow,
      opacity: style.opacity,
    },
    id: spec.id,
  })
  for (const child of spec.children) ctx.compile(child)
  ctx.ui.end_box()
}
