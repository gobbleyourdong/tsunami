/**
 * ComponentDef → immediate-mode UI calls (WebGPU compiler).
 *
 * Walks a ComponentDef tree and dispatches to an ImmediateUI instance.
 * Parallel to `dom_compiler.tsx` which compiles the same spec to
 * React/JSX for web scaffolds.
 *
 * # Status
 *   RenderContext               ✓ scaffold — holds ui + theme + value
 *                               resolver + action dispatcher
 *   compileToWebGPU             ✓ scaffold — exhaustive switch over all
 *                               25 ComponentDef kinds
 *   Atom cases                  ✓ scaffold — Box, Text, Image, Icon
 *   Form atom cases             ✓ scaffold — Button, Input, Toggle,
 *                               Select, Slider (basic rendering)
 *   Display atom cases          ✓ scaffold — Badge, Progress, Avatar,
 *                               Skeleton, Separator
 *   Container atom cases        ✓ scaffold — Card, Dialog, Tooltip,
 *                               Accordion, Scrollable, Alert, Tabs
 *                               (open/close state simplified to literal)
 *   Game composite cases        ✓ scaffold — HUD, Menu, DialogTree,
 *                               InventoryPanel, ShopPanel, TutorialCallout
 *                               (delegates to components/ when those land
 *                               in fire 6; inline rendering for now)
 *   Detailed implementations    TODO fire 6 — extract complex cases
 *                               (DialogTree, HUD, InventoryPanel, etc.)
 *                               into `components/<name>.ts`
 *
 * Follows `text.ts` pattern: public types + helpers first, then the
 * switch. No GPU setup lives here — the ImmediateUI owns that.
 */

import type { ImmediateUI } from './immediate'
import type { Theme } from './theme'
import { DEFAULT_THEME } from './theme'
import type {
  ComponentDef, MechanicRef, UIActionRef, ValueRef,
} from './component_def'
import { isMechanicRef, assertNever } from './component_def'
import {
  render_button, render_card, render_dialog, render_progress,
  render_input, render_hud, render_menu, render_dialog_tree,
} from './components'

// ── RenderContext ───────────────────────────────────────────────

/**
 * Everything a compiler pass needs to render one frame of UI. Callers
 * construct this once per frame (cheap) and pass it into
 * `compileToWebGPU(spec, ctx)`.
 */
export interface RenderContext {
  /** The immediate-mode UI sink. */
  ui: ImmediateUI
  /** Theme for token resolution. */
  theme: Theme
  /**
   * Resolve a ValueRef<T> to the current live T. Literals return as-is;
   * MechanicRefs hit a live mechanic state lookup. Callers (the action-
   * blocks runtime) provide this.
   */
  resolve: <T>(v: ValueRef<T>) => T
  /**
   * Dispatch a UIActionRef. Caller hooks into the flow / event system.
   * A no-op is acceptable for preview / test contexts.
   */
  dispatch: (action: UIActionRef) => void
  /**
   * Recurse into a child ComponentDef. Populated by compileToWebGPU on
   * entry so component renderers (components/*.ts) can call
   * `ctx.compile(child)` without importing compileToWebGPU directly
   * (avoids circular module deps).
   */
  compile: (spec: ComponentDef) => void
}

/**
 * Minimal RenderContext factory for testing + previews. Literal-only
 * resolver (logs a warning on MechanicRef), no-op dispatcher.
 */
export function createStubRenderContext(ui: ImmediateUI, theme: Theme = DEFAULT_THEME): RenderContext {
  const ctx: RenderContext = {
    ui,
    theme,
    resolve: <T>(v: ValueRef<T>): T => {
      if (isMechanicRef(v)) {
        console.warn(`stub RenderContext: cannot resolve MechanicRef ${v.mechanic_ref}.${v.field}`)
        return undefined as T
      }
      return v
    },
    dispatch: (action: UIActionRef): void => {
      // Log for visibility during UI development.
      console.log('[ui action]', action)
    },
    compile: (spec: ComponentDef): void => compileToWebGPU(spec, ctx),
  }
  return ctx
}

// ── compileToWebGPU ─────────────────────────────────────────────

/**
 * Walk a ComponentDef tree, dispatch to ctx.ui's immediate-mode API.
 *
 * Exhaustive switch: TypeScript enforces handling every ComponentDef
 * kind via `assertNever` fallthrough.
 */
export function compileToWebGPU(spec: ComponentDef, ctx: RenderContext): void {
  // Populate ctx.compile if caller omitted — components/ rely on it to
  // recurse without importing compileToWebGPU directly (breaks cycles).
  if (!ctx.compile) {
    const self_ref: RenderContext = {
      ...ctx,
      compile: (s: ComponentDef) => compileToWebGPU(s, self_ref),
    }
    ctx = self_ref
  }

  switch (spec.type) {
    // ── Atoms ─────────────────────────────────────────────────
    case 'Box':
      ctx.ui.begin_box({
        layout: spec.layout,
        style: spec.style,
        id: spec.id,
      })
      for (const child of spec.children) compileToWebGPU(child, ctx)
      ctx.ui.end_box()
      return

    case 'Text': {
      const content = ctx.resolve(spec.content)
      ctx.ui.text(String(content ?? ''), spec.style)
      return
    }

    case 'Image': {
      // TODO fire 6 — route through sprite manifest; for now draw
      // a placeholder icon-sized rect via ui.icon.
      ctx.ui.icon(String(ctx.resolve(spec.src) ?? ''), { size: 'md' })
      return
    }

    case 'Icon': {
      const name = String(ctx.resolve(spec.name) ?? '')
      ctx.ui.icon(name, { size: spec.size, color: spec.color })
      return
    }

    // ── Form atoms ────────────────────────────────────────────
    case 'Button':
      render_button(spec, ctx); return

    case 'Input':
      render_input(spec, ctx); return

    case 'Toggle': {
      const value = Boolean(ctx.resolve(spec.value as ValueRef<boolean>))
      const label = spec.label ? String(ctx.resolve(spec.label) ?? '') : ''
      // TODO fire 6 — real toggle visual. Scaffold: button whose text
      // indicates current state. Click dispatches set_field.
      const clicked = ctx.ui.button(`${label} ${value ? '[on]' : '[off]'}`, {
        variant: 'outline',
        color: value ? 'primary' : 'muted',
      })
      if (clicked) {
        ctx.dispatch({ kind: 'set_field', ref: spec.value, value: !value })
        if (spec.on_change) ctx.dispatch(spec.on_change)
      }
      return
    }

    case 'Select': {
      // TODO fire 6 — dropdown popover. Scaffold: render current option
      // as a pressable "button" with its label.
      const current_value = ctx.resolve(spec.value as ValueRef<unknown>)
      const current_option = spec.options.find(o => o.value === current_value)
      const label = current_option
        ? String(ctx.resolve(current_option.label) ?? '')
        : (spec.placeholder ?? 'select…')
      const clicked = ctx.ui.button(`${label} ▾`, { variant: 'outline', color: 'muted' })
      if (clicked && spec.on_change) ctx.dispatch(spec.on_change)
      return
    }

    case 'Slider': {
      const v = Number(ctx.resolve(spec.value as ValueRef<number>))
      const frac = (v - spec.min) / Math.max(spec.max - spec.min, 1e-6)
      if (spec.label) ctx.ui.text(String(ctx.resolve(spec.label) ?? ''), { size: 'sm' })
      ctx.ui.progress(frac, 1, { color: 'primary' })
      return
    }

    // ── Display atoms ─────────────────────────────────────────
    case 'Badge': {
      const label = String(ctx.resolve(spec.label) ?? '')
      // Scaffold: render as a small outlined button, non-interactive.
      ctx.ui.button(label, {
        variant: spec.variant ?? 'outline',
        color: spec.color,
        size: spec.size ?? 'xs',
        disabled: true,
      })
      return
    }

    case 'Progress':
      render_progress(spec, ctx); return

    case 'Avatar': {
      // TODO fire 6 — real image circle with initials fallback.
      // Scaffold: small colored box.
      ctx.ui.icon('avatar', { size: spec.size, color: 'muted' })
      return
    }

    case 'Skeleton': {
      // TODO fire 6 — shimmer animation. Scaffold: muted rect.
      ctx.ui.begin_box({
        layout: spec.layout,
        style: { bg: 'muted', rounded: spec.shape === 'circle' ? 'full' : 'sm' },
      })
      ctx.ui.end_box()
      return
    }

    case 'Separator': {
      // TODO fire 6 — proper horizontal line. Scaffold: 1px rect.
      ctx.ui.spacer(4)
      return
    }

    // ── Container atoms ──────────────────────────────────────
    case 'Card':
      render_card(spec, ctx); return

    case 'Dialog':
      render_dialog(spec, ctx); return

    case 'Tooltip':
      // Scaffold: render the wrapped child, ignore tooltip text.
      // TODO fire 6 — hover-detect + delayed popover.
      compileToWebGPU(spec.target, ctx)
      return

    case 'Accordion': {
      for (const item of spec.items) {
        const is_open = item.open ? Boolean(ctx.resolve(item.open)) : false
        ctx.ui.begin_box({
          layout: { direction: 'column', gap: 4 },
          style: { bg: 'panel', rounded: 'sm' },
        })
        const title = String(ctx.resolve(item.title) ?? '')
        ctx.ui.text(is_open ? `▾ ${title}` : `▸ ${title}`, { size: 'md', weight: 'bold' })
        if (is_open) {
          for (const child of item.content) compileToWebGPU(child, ctx)
        }
        ctx.ui.end_box()
      }
      return
    }

    case 'Scrollable':
      // TODO fire 6 — actual scroll container. Scaffold: pass through.
      ctx.ui.begin_box({ layout: spec.layout })
      for (const child of spec.children) compileToWebGPU(child, ctx)
      ctx.ui.end_box()
      return

    case 'Alert': {
      ctx.ui.begin_box({
        layout: { direction: 'column', gap: 4, padding: 12 },
        style: {
          bg: 'panel', rounded: 'md',
          border: spec.color ?? 'info', border_width: 1,
        },
      })
      if (spec.title) {
        ctx.ui.text(String(ctx.resolve(spec.title) ?? ''), {
          size: 'md', weight: 'bold', color: spec.color ?? 'info',
        })
      }
      ctx.ui.text(String(ctx.resolve(spec.content) ?? ''), { size: 'sm' })
      ctx.ui.end_box()
      return
    }

    case 'Tabs': {
      const active_id = String(ctx.resolve(spec.value as ValueRef<string>))
      // Tab headers row.
      ctx.ui.begin_box({ layout: { direction: 'row', gap: 8 } })
      for (const tab of spec.tabs) {
        const label = String(ctx.resolve(tab.label) ?? '')
        const is_active = tab.id === active_id
        const clicked = ctx.ui.button(label, {
          variant: is_active ? 'solid' : 'ghost',
          color: is_active ? 'primary' : 'muted',
          size: 'sm',
        })
        if (clicked) {
          ctx.dispatch({ kind: 'set_field', ref: spec.value, value: tab.id })
        }
      }
      ctx.ui.end_box()
      // Active tab content.
      const active_tab = spec.tabs.find(t => t.id === active_id) ?? spec.tabs[0]
      if (active_tab) {
        ctx.ui.begin_box({ layout: { direction: 'column', gap: 8 } })
        for (const child of active_tab.content) compileToWebGPU(child, ctx)
        ctx.ui.end_box()
      }
      return
    }

    // ── Game composites ─────────────────────────────────────
    // Delegated to components/<name>.ts; see fire 6.
    case 'HUD':
      render_hud(spec, ctx); return

    case 'Menu':
      render_menu(spec, ctx); return

    case 'DialogTree':
      render_dialog_tree(spec, ctx); return

    case 'InventoryPanel': {
      // TODO fire 6 — grid layout + item rendering from sprite manifest.
      // Scaffold: labeled card.
      ctx.ui.begin_box({
        layout: { direction: 'column', gap: 4, padding: 12 },
        style: { bg: 'panel', rounded: 'md' },
      })
      ctx.ui.text(`Inventory (${spec.slots} slots, ${spec.columns} cols)`, {
        size: 'md', weight: 'bold',
      })
      ctx.ui.end_box()
      return
    }

    case 'ShopPanel': {
      // TODO fire 6 — buy/sell interface. Scaffold: labeled card.
      ctx.ui.begin_box({
        layout: { direction: 'column', gap: 4, padding: 12 },
        style: { bg: 'panel', rounded: 'md' },
      })
      const title = spec.title ? String(ctx.resolve(spec.title) ?? '') : 'Shop'
      ctx.ui.text(title, { size: 'md', weight: 'bold' })
      ctx.ui.text('(buy / sell UI TODO)', { size: 'sm', color: 'muted' })
      ctx.ui.end_box()
      return
    }

    case 'TutorialCallout': {
      ctx.ui.begin_box({
        layout: { anchor: 'top', padding: 16 },
        style: { bg: 'panel', rounded: 'md', border: 'accent', border_width: 2 },
      })
      ctx.ui.text(String(ctx.resolve(spec.content) ?? ''), { size: 'md' })
      ctx.ui.end_box()
      return
    }

    // ── Exhaustiveness check ─────────────────────────────────
    default:
      assertNever(spec)
  }
}

// ── Convenience: resolve-then-narrow helper ─────────────────────

/**
 * Resolve a `MechanicRef` passed as a `ValueRef<T>`. Literal values
 * pass through. Exists so compilers don't repeat the isMechanicRef
 * pattern at every reference site.
 */
export function resolveValue<T>(v: ValueRef<T> | undefined, ctx: RenderContext, fallback: T): T {
  if (v === undefined) return fallback
  return ctx.resolve(v)
}

/**
 * Batch-dispatch multiple actions. Handy for on_change + on_something
 * pairs emitted by the same event.
 */
export function dispatchAll(actions: (UIActionRef | undefined)[], ctx: RenderContext): void {
  for (const a of actions) if (a) ctx.dispatch(a)
}

// ── Re-exported helpers from component_def for compiler callers ─

export { isMechanicRef } from './component_def'
export type { MechanicRef, UIActionRef, ValueRef } from './component_def'
