/**
 * ComponentDef → DOM descriptor compiler.
 *
 * Parallel to `webgpu_compiler.ts`. Produces a structural descriptor
 * tree (no hard React dep) that web scaffolds convert to real React
 * elements via `React.createElement` or JSX-wrap in their own
 * `components/ui` library.
 *
 * # Status
 *   DomDescriptor type        ✓ scaffold — React-shaped, framework-free
 *   DomRenderContext          ✓ scaffold — resolve + dispatch + compile
 *   compileToReact            ✓ scaffold — exhaustive 25-case switch
 *   Component→element map     ✓ scaffold — best-guess native tags +
 *                              `data-ui-*` annotations for scaffold
 *                              adapters to recognize
 *   Real React impl           TODO — lives in `scaffolds/_shared/ui-spec/`
 *                              (not the engine scaffold; engine stays
 *                              React-free). Scaffold wraps each
 *                              DomDescriptor via React.createElement
 *                              using its own `components/ui` library.
 *   Controlled input wiring   TODO scaffold-side — `onChange` on
 *                              MechanicRef-bound inputs dispatches
 *                              `set_field` actions
 *   Accessibility (ARIA)      TODO scaffold-side — mirror tree for
 *                              screen readers
 *
 * Follows `text.ts` pattern: interface + stub + factory. Output is a
 * typed descriptor tree; no rendering happens here.
 *
 * # Why not return ReactNode directly?
 *
 * The engine scaffold is zero-dep, WebGPU-first. Importing React as
 * a runtime dep would add ~50 KB to every game scaffold. Instead:
 *   - This compiler returns `DomDescriptor` (plain data)
 *   - Web scaffolds (auth-app, dashboard, fullstack) import this +
 *     their React `components/ui` + walk the descriptor tree via
 *     `React.createElement(tag_or_comp, props, children)` to get a
 *     real ReactNode
 *   - The walker is ~30 lines and lives in `_shared/ui-spec/`
 *
 * Tradeoff: one extra adapter pass in web scaffolds, zero React in
 * the engine. Net win for the zero-dep ethos.
 */

import type {
  ComponentDef, UIActionRef, ValueRef, MechanicRef, HUDField, BoxStyleSpec,
} from './component_def'
import { isMechanicRef, assertNever } from './component_def'

// ── DomDescriptor ────────────────────────────────────────────────

/**
 * React-shaped descriptor. `tag` may be an HTML element name
 * ('div', 'button') or a component name from scaffold's `components/ui`
 * ('Button', 'Card'). Scaffolds resolve it at walk time.
 *
 * `key` comes along for reconciliation; props include `className`,
 * `style`, `onClick`, etc. `children` is a heterogeneous array.
 */
export interface DomDescriptor {
  tag: string
  key?: string | number
  props: Record<string, unknown>
  children?: (DomDescriptor | string | number | null)[]
}

// ── DomRenderContext ─────────────────────────────────────────────

export interface DomRenderContext {
  /** Resolve literal or MechanicRef to a current value. */
  resolve: <T>(v: ValueRef<T>) => T
  /**
   * Translate a UIActionRef into an event handler.
   * Scaffolds typically return `() => dispatch(action)` closures, so
   * the handler can be passed directly to React `onClick` etc.
   */
  to_handler: (action: UIActionRef) => () => void
  /** Recurse into a child ComponentDef. */
  compile: (spec: ComponentDef) => DomDescriptor | null
}

/** Logging stub ctx for previews and tests. */
export function createStubDomRenderContext(): DomRenderContext {
  const ctx: DomRenderContext = {
    resolve: <T>(v: ValueRef<T>): T => {
      if (isMechanicRef(v)) {
        console.warn(
          `stub DomRenderContext: cannot resolve MechanicRef ` +
          `${v.mechanic_ref}.${v.field}`,
        )
        return undefined as T
      }
      return v
    },
    to_handler: (action: UIActionRef): (() => void) => {
      return () => console.log('[dom action]', action)
    },
    compile: (spec: ComponentDef): DomDescriptor | null => compileToReact(spec, ctx),
  }
  return ctx
}

// ── Helpers ──────────────────────────────────────────────────────

function d(
  tag: string,
  props: Record<string, unknown> = {},
  ...children: (DomDescriptor | string | number | null | undefined)[]
): DomDescriptor {
  return {
    tag,
    props,
    children: children
      .filter((c): c is DomDescriptor | string | number | null => c !== undefined),
  }
}

/** Subset of ComponentDef props commonly mapped to `data-ui-*` attrs. */
function anno(spec: { id?: string; type: string }): Record<string, string> {
  const out: Record<string, string> = { 'data-ui-type': spec.type }
  if (spec.id) out['data-ui-id'] = spec.id
  return out
}

function text_content(v: ValueRef<string>, ctx: DomRenderContext): string {
  const r = ctx.resolve(v)
  return r === undefined || r === null ? '' : String(r)
}

function maybe_bool<T>(v: ValueRef<T> | undefined, ctx: DomRenderContext): boolean {
  if (v === undefined) return false
  return Boolean(ctx.resolve(v))
}

function compile_children(children: ComponentDef[], ctx: DomRenderContext): DomDescriptor[] {
  const out: DomDescriptor[] = []
  for (const child of children) {
    const c = ctx.compile(child)
    if (c) out.push(c)
  }
  return out
}

// ── compileToReact ───────────────────────────────────────────────

/**
 * Walk a ComponentDef tree, return a DomDescriptor. Scaffolds wrap
 * with React.createElement at render time.
 */
export function compileToReact(
  spec: ComponentDef,
  ctx: DomRenderContext,
): DomDescriptor | null {
  switch (spec.type) {
    // ── Atoms ─────────────────────────────────────────────────
    case 'Box':
      return d('div', { ...anno(spec), style: to_box_style(spec.style) },
        ...compile_children(spec.children, ctx))

    case 'Text':
      return d('span', {
        ...anno(spec),
        'data-ui-style': JSON.stringify(spec.style ?? {}),
      }, text_content(spec.content, ctx))

    case 'Image':
      return d('img', {
        ...anno(spec),
        src: text_content(spec.src, ctx),
        alt: spec.alt ?? '',
        style: { objectFit: spec.fit ?? 'contain' },
      })

    case 'Icon':
      return d('span', {
        ...anno(spec),
        'data-ui-icon': text_content(spec.name, ctx),
        'data-ui-size': spec.size,
        'data-ui-color': spec.color,
      })

    // ── Form atoms ────────────────────────────────────────────
    case 'Button':
      return d('Button', {   // scaffold components/ui/Button
        ...anno(spec),
        variant: spec.variant,
        color: spec.color,
        size: spec.size,
        disabled: maybe_bool(spec.disabled, ctx),
        onClick: spec.on_click ? ctx.to_handler(spec.on_click) : undefined,
      }, text_content(spec.label, ctx))

    case 'Input':
      return d('Input', {
        ...anno(spec),
        value: ctx.resolve(spec.value as ValueRef<string>) ?? '',
        placeholder: spec.placeholder,
        type: spec.input_type ?? 'text',
        disabled: maybe_bool(spec.disabled, ctx),
        'data-ui-bind-ref': spec.value.mechanic_ref,
        'data-ui-bind-field': spec.value.field,
        onSubmit: spec.on_submit ? ctx.to_handler(spec.on_submit) : undefined,
      })

    case 'Toggle':
      return d('Switch', {
        ...anno(spec),
        checked: Boolean(ctx.resolve(spec.value as ValueRef<boolean>)),
        disabled: maybe_bool(spec.disabled, ctx),
        'data-ui-bind-ref': spec.value.mechanic_ref,
        'data-ui-bind-field': spec.value.field,
        onChange: spec.on_change ? ctx.to_handler(spec.on_change) : undefined,
      }, spec.label ? text_content(spec.label, ctx) : null)

    case 'Select':
      return d('Select', {
        ...anno(spec),
        value: ctx.resolve(spec.value as ValueRef<unknown>),
        placeholder: spec.placeholder,
        disabled: maybe_bool(spec.disabled, ctx),
        options: spec.options.map(o => ({
          label: ctx.resolve(o.label),
          value: o.value,
          icon: o.icon,
        })),
        'data-ui-bind-ref': spec.value.mechanic_ref,
        'data-ui-bind-field': spec.value.field,
        onChange: spec.on_change ? ctx.to_handler(spec.on_change) : undefined,
      })

    case 'Slider':
      return d('Slider', {
        ...anno(spec),
        value: ctx.resolve(spec.value as ValueRef<number>),
        min: spec.min,
        max: spec.max,
        step: spec.step,
        'data-ui-bind-ref': spec.value.mechanic_ref,
        'data-ui-bind-field': spec.value.field,
        onChange: spec.on_change ? ctx.to_handler(spec.on_change) : undefined,
      }, spec.label ? text_content(spec.label, ctx) : null)

    // ── Display atoms ─────────────────────────────────────────
    case 'Badge':
      return d('Badge', {
        ...anno(spec),
        color: spec.color,
        variant: spec.variant,
        size: spec.size,
      }, text_content(spec.label, ctx))

    case 'Progress':
      return d('Progress', {
        ...anno(spec),
        value: Number(ctx.resolve(spec.value)),
        max: spec.max !== undefined ? Number(ctx.resolve(spec.max)) : 1,
        color: spec.color,
        size: spec.size,
        showLabel: spec.show_label,
      })

    case 'Avatar':
      return d('Avatar', {
        ...anno(spec),
        src: spec.src ? text_content(spec.src, ctx) : undefined,
        initials: spec.initials ? text_content(spec.initials, ctx) : undefined,
        size: spec.size,
        shape: spec.shape,
      })

    case 'Skeleton':
      return d('Skeleton', {
        ...anno(spec),
        shape: spec.shape,
      })

    case 'Separator':
      return d('Separator', {
        ...anno(spec),
        direction: spec.direction,
        color: spec.color,
      })

    // ── Container atoms ──────────────────────────────────────
    case 'Card':
      return d('Card', {
        ...anno(spec),
        glass: spec.style?.glass,
      }, ...compile_children(spec.children, ctx))

    case 'Dialog': {
      const open = Boolean(ctx.resolve(spec.open))
      if (!open) return null
      return d('Dialog', {
        ...anno(spec),
        open,
        title: spec.title ? text_content(spec.title, ctx) : undefined,
        size: spec.size,
        dismissable: spec.dismissable,
        onClose: spec.on_close ? ctx.to_handler(spec.on_close) : undefined,
      }, ...compile_children(spec.children, ctx))
    }

    case 'Tooltip':
      return d('Tooltip', {
        ...anno(spec),
        content: text_content(spec.content, ctx),
        delayMs: spec.delay_ms,
        placement: spec.placement,
      }, ctx.compile(spec.target))

    case 'Accordion':
      return d('Accordion', {
        ...anno(spec),
        multiOpen: spec.multi_open,
        items: spec.items.map(item => ({
          id: item.id,
          title: text_content(item.title, ctx),
          open: maybe_bool(item.open, ctx),
          content: compile_children(item.content, ctx),
        })),
      })

    case 'Scrollable':
      return d('Scrollable', {
        ...anno(spec),
        direction: spec.direction ?? 'vertical',
      }, ...compile_children(spec.children, ctx))

    case 'Alert':
      return d('Alert', {
        ...anno(spec),
        title: spec.title ? text_content(spec.title, ctx) : undefined,
        color: spec.color ?? 'info',
        dismissable: spec.dismissable,
        icon: spec.icon,
        onDismiss: spec.on_dismiss ? ctx.to_handler(spec.on_dismiss) : undefined,
      }, text_content(spec.content, ctx))

    case 'Tabs':
      return d('Tabs', {
        ...anno(spec),
        value: ctx.resolve(spec.value as ValueRef<string>),
        orientation: spec.orientation,
        tabs: spec.tabs.map(tab => ({
          id: tab.id,
          label: text_content(tab.label, ctx),
          icon: tab.icon,
          content: compile_children(tab.content, ctx),
        })),
        'data-ui-bind-ref': spec.value.mechanic_ref,
        'data-ui-bind-field': spec.value.field,
      })

    // ── Game composites ─────────────────────────────────────
    case 'HUD':
      return d('HUD', {
        ...anno(spec),
        anchor: spec.anchor,
        style: spec.style,
        layoutDirection: spec.layout_direction,
        fields: spec.fields.map(f => hud_field_descriptor(f, ctx)),
      })

    case 'Menu':
      return d('Menu', {
        ...anno(spec),
        title: spec.title ? text_content(spec.title, ctx) : undefined,
        orientation: spec.orientation,
        anchor: spec.anchor,
        panelStyle: spec.style?.panel,
        items: spec.items.map(item => ({
          label: text_content(item.label, ctx),
          icon: item.icon,
          hotkey: item.hotkey,
          disabled: maybe_bool(item.disabled, ctx),
          onClick: ctx.to_handler(item.action),
        })),
        onBack: spec.on_back ? ctx.to_handler(spec.on_back) : undefined,
      })

    case 'DialogTree':
      return d('DialogTree', {
        ...anno(spec),
        speaker: spec.speaker ? text_content(spec.speaker, ctx) : undefined,
        portrait: spec.portrait ? text_content(spec.portrait, ctx) : undefined,
        content: text_content(spec.content, ctx),
        anchor: spec.anchor,
        size: spec.size,
        panelStyle: spec.style?.panel,
        typewriter: spec.typewriter,
        choices: spec.choices
          ?.filter(c => !c.gate || Boolean(ctx.resolve(c.gate)))
          .map(c => ({
            label: text_content(c.label, ctx),
            preview: c.preview ? text_content(c.preview, ctx) : undefined,
            onClick: ctx.to_handler(c.action),
          })),
        onAdvance: spec.on_advance ? ctx.to_handler(spec.on_advance) : undefined,
      })

    case 'InventoryPanel':
      return d('InventoryPanel', {
        ...anno(spec),
        slots: spec.slots,
        columns: spec.columns,
        itemSize: spec.item_size,
        'data-ui-bind-ref': spec.inventory.mechanic_ref,
        'data-ui-bind-field': spec.inventory.field,
        onSelect: spec.on_select ? ctx.to_handler(spec.on_select) : undefined,
        onUse: spec.on_use ? ctx.to_handler(spec.on_use) : undefined,
        emptySlotIcon: spec.empty_slot_icon,
        panelStyle: spec.style?.panel,
      })

    case 'ShopPanel':
      return d('ShopPanel', {
        ...anno(spec),
        title: spec.title ? text_content(spec.title, ctx) : undefined,
        allowSell: spec.allow_sell,
        'data-ui-inventory-ref': spec.inventory.mechanic_ref,
        'data-ui-inventory-field': spec.inventory.field,
        'data-ui-wallet-ref': spec.wallet.mechanic_ref,
        'data-ui-wallet-field': spec.wallet.field,
        onBuy: spec.on_buy ? ctx.to_handler(spec.on_buy) : undefined,
        onSell: spec.on_sell ? ctx.to_handler(spec.on_sell) : undefined,
      })

    case 'TutorialCallout':
      return d('TutorialCallout', {
        ...anno(spec),
        target: spec.target,
        placement: spec.placement,
        dismissOn: spec.dismiss_on,
        step: spec.step,
        onDismiss: spec.on_dismiss ? ctx.to_handler(spec.on_dismiss) : undefined,
      }, text_content(spec.content, ctx))

    default:
      return assertNever(spec)
  }
}

// ── Helper: HUD field → plain descriptor object ─────────────────

function hud_field_descriptor(f: HUDField, ctx: DomRenderContext): Record<string, unknown> {
  return {
    type: f.type,
    value: ctx.resolve(f.value),
    max: f.max ? ctx.resolve(f.max) : undefined,
    label: f.label ? ctx.resolve(f.label) : undefined,
    color: f.color,
    icon: f.icon,
    format: f.format,
  }
}

// ── Helper: style spec → CSS-ish object ─────────────────────────

function to_box_style(
  style: BoxStyleSpec | undefined,
): Record<string, unknown> | undefined {
  if (!style) return undefined
  const s = style as Record<string, unknown>
  const css: Record<string, unknown> = {}
  if (s.bg !== undefined)           css['data-bg']           = s.bg
  if (s.border !== undefined)       css['data-border']       = s.border
  if (s.border_width !== undefined) css['data-border-width'] = s.border_width
  if (s.rounded !== undefined)      css['data-rounded']      = s.rounded
  if (s.shadow !== undefined)       css['data-shadow']       = s.shadow
  if (s.opacity !== undefined)      css.opacity              = s.opacity
  return css
}

// ── Re-exports for compiler callers ─────────────────────────────

export type { MechanicRef, UIActionRef, ValueRef } from './component_def'
