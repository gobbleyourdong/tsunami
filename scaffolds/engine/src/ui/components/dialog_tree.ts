/**
 * DialogTree component renderer — DialogTreeDef → immediate-mode calls.
 *
 * # Status
 *   render_dialog_tree   ✓ scaffold — speaker + content + choices
 *   Portrait             ✓ scaffold (icon placeholder until sprite manifest)
 *   Typewriter effect    TODO fire 7 (needs frame-time delta + char reveal state)
 *   Gate filter          ✓ scaffold — hides choices where `gate` is falsy
 *   Preview (hover hint) TODO (input system)
 *   Panel style presets  ✓ scaffold — parchment/tech/clean/retro/comic
 *                          mapped to bg + border + rounded combos
 */

import type { DialogTreeDef, UIDialogChoice } from '../component_def'
import type { RenderContext } from '../webgpu_compiler'
import type { BoxStyleSpec } from '../component_def'

const PANEL_STYLES: Record<NonNullable<NonNullable<DialogTreeDef['style']>['panel']>, BoxStyleSpec> = {
  parchment: { bg: 'panel', border: 'accent', border_width: 2, rounded: 'sm' },
  tech:      { bg: 'glass', border: 'info',   border_width: 1, rounded: 'sm' },
  clean:     { bg: 'panel', border: 'muted',  border_width: 1, rounded: 'md' },
  retro:     { bg: 'panel', border: 'fg',     border_width: 2, rounded: 'none' },
  comic:     { bg: 'bg',    border: 'fg',     border_width: 3, rounded: 'xl' },
}

function render_choices(choices: UIDialogChoice[], ctx: RenderContext): void {
  ctx.ui.spacer(8)
  ctx.ui.begin_box({ layout: { direction: 'column', gap: 4 } })
  for (const choice of choices) {
    if (choice.gate) {
      const show = Boolean(ctx.resolve(choice.gate))
      if (!show) continue
    }
    const label = String(ctx.resolve(choice.label) ?? '')
    const clicked = ctx.ui.button(label, {
      variant: 'outline',
      color: 'primary',
    })
    if (clicked) ctx.dispatch(choice.action)
  }
  ctx.ui.end_box()
}

export function render_dialog_tree(spec: DialogTreeDef, ctx: RenderContext): void {
  const panel = PANEL_STYLES[spec.style?.panel ?? 'clean']

  ctx.ui.begin_box({
    layout: {
      anchor: spec.anchor ?? 'bottom',
      direction: 'column',
      gap: 6,
      padding: 16,
    },
    style: panel,
    id: spec.id,
  })

  // Portrait + speaker row.
  if (spec.portrait || spec.speaker) {
    ctx.ui.begin_box({ layout: { direction: 'row', gap: 8 } })
    if (spec.portrait) {
      const portrait = String(ctx.resolve(spec.portrait) ?? '')
      ctx.ui.icon(portrait, { size: '2xl' })
    }
    if (spec.speaker) {
      ctx.ui.text(String(ctx.resolve(spec.speaker) ?? ''), {
        size: 'md', weight: 'bold', color: 'accent',
      })
    }
    ctx.ui.end_box()
  }

  // Main dialogue content.
  // TODO fire 7 — typewriter reveal when typewriter.enabled is true.
  ctx.ui.text(String(ctx.resolve(spec.content) ?? ''), {
    size: 'md',
    color: 'fg',
  })

  // Choices or auto-advance prompt.
  if (spec.choices && spec.choices.length > 0) {
    render_choices(spec.choices, ctx)
  } else {
    ctx.ui.spacer(6)
    ctx.ui.text('▸ continue', { size: 'sm', color: 'muted' })
    // TODO fire 7 — wire advance trigger through input system.
  }

  ctx.ui.end_box()
}
