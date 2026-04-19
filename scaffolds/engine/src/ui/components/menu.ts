/**
 * Menu component renderer — MenuDef → immediate-mode calls.
 *
 * # Status
 *   render_menu        ✓ scaffold — anchored list of button items
 *   Vertical / horizontal ✓ scaffold
 *   Title               ✓ scaffold
 *   Submenu nesting     TODO fire 7 (popover layering needed)
 *   Hotkey display      ✓ scaffold (rendered as suffix text)
 *   Keyboard nav        TODO (input system)
 *   Back action         TODO (Esc capture via input system)
 *   Panel styles        ✓ scaffold — solid / glass / transparent
 */

import type { MenuDef, UIMenuItem } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'

function panel_bg(panel: NonNullable<MenuDef['style']>['panel']) {
  switch (panel) {
    case 'transparent': return 'none'
    case 'glass':       return 'glass'
    case 'solid':
    default:             return 'panel'
  }
}

function render_item(item: UIMenuItem, ctx: RenderContext): void {
  const label = String(ctx.resolve(item.label) ?? '')
  const disabled = item.disabled ? Boolean(ctx.resolve(item.disabled)) : false
  const display = item.hotkey ? `${label}  ⟨${item.hotkey}⟩` : label

  const clicked = ctx.ui.button(display, {
    variant: 'ghost',
    color: 'fg',
    disabled,
    icon_left: item.icon,
  })

  if (clicked && !disabled) ctx.dispatch(item.action)
}

export function render_menu(spec: MenuDef, ctx: RenderContext): void {
  ctx.ui.begin_box({
    layout: {
      anchor: spec.anchor ?? 'center',
      direction: spec.orientation === 'horizontal' ? 'row' : 'column',
      gap: 6,
      padding: 16,
    },
    style: {
      bg: panel_bg(spec.style?.panel),
      rounded: 'md',
      border: spec.style?.panel === 'solid' ? 'muted' : undefined,
      border_width: spec.style?.panel === 'solid' ? 1 : 0,
    },
    id: spec.id,
  })

  if (spec.title) {
    ctx.ui.text(String(ctx.resolve(spec.title) ?? ''), {
      size: 'lg',
      weight: 'bold',
      color: 'fg',
      align: 'center',
    })
    ctx.ui.spacer(6)
  }

  for (const item of spec.items) render_item(item, ctx)

  ctx.ui.end_box()
}
