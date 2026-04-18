# UI framework spec — attempt 001

> Single-thread design. No helper instance; scope is just the
> declarative `ComponentDef` spec where DRY between web scaffolds and
> the game UI actually lives. The renderer is JB's (MSDF text + WebGPU
> + layout). The DOM fallback is a thin React compiler over the same
> spec.

## Scope

A framework-neutral UI vocabulary that compiles to two renderers:

- **DOM renderer** — `ComponentDef` → React/JSX using the existing
  `scaffolds/*/components/ui` library (Button, Card, Input, Badge,
  Dialog, Select, Progress, Avatar, Switch, Tooltip, Dropdown,
  Accordion, Alert, Skeleton). For web scaffolds (auth-app,
  dashboard, fullstack, etc.).

- **WebGPU renderer** — `ComponentDef` → immediate-mode calls in the
  game frame loop. For the action-blocks scaffold and any native-
  wrapped deployment. JB's MSDF text + layout + quad batcher backs
  this path.

Same authoring vocabulary. Two renderers. Tsunami writes one spec;
it runs in a browser tab, in Electron/Tauri, in a mobile WebView, or
in a wgpu-native wrapper without re-authoring.

## What this doc does NOT cover

Out of scope — JB is handling:
- MSDF / text rendering
- 2D quad batcher
- Layout engine internals (Yoga or custom flex)
- Immediate-mode shell
- Any GPU shader code

Out of scope — v1.2+:
- Animation / transitions (deferred)
- Drag-and-drop affordances
- Complex data tables / virtualized lists
- Video / WebRTC overlays
- Fullscreen inventory grid-DnD (covered by `InventoryPanel` but
  drag interactions deferred)

In scope:
- `ComponentDef` union
- Layout type
- Style tokens (color / size / variant) — renderer-agnostic
- Value bindings (`MechanicRef` reuse from action-blocks)
- Event bindings (`ActionRef` reuse from action-blocks)
- Compiler contracts — both renderers' APIs
- Action-blocks UI-mechanic integration
- Theme tokens

## Architecture

```
             ┌─ ComponentDef (this doc) ───────┐
             │  typed declarative UI spec      │
             │  branded IDs, tokens, bindings  │
             └───────────────┬─────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                          ▼
 ┌─────────────────┐                    ┌─────────────────────┐
 │ DOM compiler    │                    │ WebGPU compiler     │
 │ → React/JSX     │                    │ → immediate-mode    │
 │   from shared   │                    │   UI calls          │
 │   components/ui │                    │ (MSDF + Yoga + ...) │
 └─────────────────┘                    └─────────────────────┘
        │                                          │
 web scaffolds                              game scaffold,
 (auth-app, dash,                           Electron/Tauri,
  fullstack, ...)                           mobile WebView,
                                            native-wrapped
```

DRY surface is the spec. Renderers are separate concerns. Each
scaffold picks which renderer to mount at startup.

## Core types (paste-ready TS)

```ts
// ═════════════════════════════════════════════════════════════════
// UI framework — declarative ComponentDef spec
// ═════════════════════════════════════════════════════════════════

// ── Branded IDs ──────────────────────────────────────────────────

export type ComponentId = string & { __brand: 'ComponentId' }

// Reuse from action-blocks schema:
import type { MechanicId, ConditionKey } from '@action-blocks/schema'

export interface MechanicRef {
  mechanic_ref: MechanicId
  field: string
}

// Subset of ActionRef used in UI handlers.
// Full ActionRef union imported from action-blocks.
export type UIActionRef =
  | { kind: 'emit';       condition: ConditionKey }
  | { kind: 'set_flag';   name: string; value: unknown }
  | { kind: 'focus';      target: ComponentId }
  | { kind: 'close';      target?: ComponentId }      // closes nearest Dialog if no target
  | { kind: 'open';       target: ComponentId }
  | { kind: 'play_sfx_ref'; library_ref: MechanicId; preset: string }  // bridge to audio ext

// Value bindings — literal or reactive.
export type ValueRef<T> = T | MechanicRef

// ── Layout ────────────────────────────────────────────────────────

export type Size =
  | number                          // pixels
  | `${number}%`                    // percentage of parent
  | 'auto'                          // content-driven
  | 'fill'                          // flex grow
  | SizeToken                       // token-resolved

export type SizeToken = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

export type Anchor =
  | 'top-left'    | 'top'    | 'top-right'
  | 'left'        | 'center' | 'right'
  | 'bottom-left' | 'bottom' | 'bottom-right'

export interface Layout {
  // Flex-like flow (row/column)
  direction?: 'row' | 'column'
  gap?: Size
  padding?: Size | [Size, Size, Size, Size]   // all or [top,right,bottom,left]
  align?: 'start' | 'center' | 'end' | 'stretch'      // cross-axis
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly'  // main-axis
  wrap?: boolean

  // Flex child properties
  grow?: number
  shrink?: number
  basis?: Size

  // Explicit sizing
  width?: Size
  height?: Size
  min_width?: Size
  min_height?: Size
  max_width?: Size
  max_height?: Size

  // Absolute positioning (opt-in; primary use: HUD corners)
  anchor?: Anchor
  offset?: [Size, Size]             // [x, y] from anchor point
  z?: number                        // stacking order within parent
}

// ── Style tokens (renderer-agnostic) ─────────────────────────────

export type ColorToken =
  | 'default'  | 'primary' | 'secondary' | 'accent'
  | 'muted'    | 'danger'  | 'warning'   | 'success' | 'info'

export type VariantToken = 'solid' | 'outline' | 'ghost' | 'link'

export type BorderRadius = 'none' | SizeToken | 'full'

export interface BoxStyle {
  bg?: ColorToken | 'none' | 'panel' | 'glass'
  border?: ColorToken | 'none'
  rounded?: BorderRadius
  shadow?: SizeToken | 'none'
  opacity?: number                   // 0..1
}

export interface TextStyle {
  size?: SizeToken
  weight?: 'normal' | 'medium' | 'bold'
  color?: ColorToken
  align?: 'left' | 'center' | 'right'
  italic?: boolean
  truncate?: boolean                 // ellipsize on overflow
  wrap?: boolean                     // default true
  font?: 'sans' | 'serif' | 'mono' | 'display'
}

// Theme — one object per scaffold, resolved at startup. Renderer-
// specific (DOM: CSS vars / tailwind classes; WebGPU: palette LUT).
// Spec references tokens by name; theme does the mapping.
export interface Theme {
  colors: Record<ColorToken, string>         // hex or CSS color
  sizes:  Record<SizeToken,  number>         // px base unit multipliers
  radii:  Record<BorderRadius, number>       // px
  font_family?: Record<NonNullable<TextStyle['font']>, string>
  font_size_base?: number                    // px; other sizes scale from this
}

// ═════════════════════════════════════════════════════════════════
// ComponentDef union — the vocabulary
// ═════════════════════════════════════════════════════════════════

export type ComponentDef =
  // Atoms
  | BoxDef | TextDef | ImageDef | IconDef
  // Form atoms
  | ButtonDef | InputDef | ToggleDef | SelectDef | SliderDef
  // Display atoms
  | BadgeDef | ProgressDef | AvatarDef | SkeletonDef | SeparatorDef
  // Container atoms
  | CardDef | DialogDef | TooltipDef | AccordionDef | ScrollableDef | AlertDef | TabsDef
  // Game composites (higher-level than web library; action-blocks UI mechanics compile to these)
  | HUDDef | MenuDef | DialogTreeDef | InventoryPanelDef | ShopPanelDef | TutorialCalloutDef

// ── Atoms ────────────────────────────────────────────────────────

export interface BoxDef {
  type: 'Box'
  id?: ComponentId
  layout?: Layout
  style?: BoxStyle
  children: ComponentDef[]
}

export interface TextDef {
  type: 'Text'
  id?: ComponentId
  content: ValueRef<string>
  style?: TextStyle
}

export interface ImageDef {
  type: 'Image'
  id?: ComponentId
  src: ValueRef<string>            // asset id (from sprite manifest) or URL
  alt?: string
  fit?: 'contain' | 'cover' | 'fill' | 'none'
  layout?: Layout
}

export interface IconDef {
  type: 'Icon'
  id?: ComponentId
  name: ValueRef<string>           // icon name from MSDF atlas
  size?: SizeToken
  color?: ColorToken
}

// ── Form atoms ───────────────────────────────────────────────────

export interface ButtonDef {
  type: 'Button'
  id?: ComponentId
  label: ValueRef<string>
  variant?: VariantToken
  color?: ColorToken
  size?: SizeToken
  icon_left?: string
  icon_right?: string
  disabled?: ValueRef<boolean>
  on_click?: UIActionRef
  layout?: Layout
}

export interface InputDef {
  type: 'Input'
  id?: ComponentId
  value: MechanicRef                // two-way bound; sets the field on change
  placeholder?: string
  input_type?: 'text' | 'number' | 'password' | 'email'
  disabled?: ValueRef<boolean>
  on_submit?: UIActionRef
  layout?: Layout
}

export interface ToggleDef {
  type: 'Toggle'
  id?: ComponentId
  value: MechanicRef                // two-way bound boolean
  label?: ValueRef<string>
  disabled?: ValueRef<boolean>
  on_change?: UIActionRef
}

export interface SelectDef {
  type: 'Select'
  id?: ComponentId
  value: MechanicRef                // two-way bound
  options: Array<{ label: ValueRef<string>; value: unknown; icon?: string }>
  placeholder?: string
  disabled?: ValueRef<boolean>
  on_change?: UIActionRef
  layout?: Layout
}

export interface SliderDef {
  type: 'Slider'
  id?: ComponentId
  value: MechanicRef                // two-way bound number
  min: number
  max: number
  step?: number
  label?: ValueRef<string>
  on_change?: UIActionRef
}

// ── Display atoms ────────────────────────────────────────────────

export interface BadgeDef {
  type: 'Badge'
  id?: ComponentId
  label: ValueRef<string>
  color?: ColorToken
  variant?: VariantToken
  size?: SizeToken
}

export interface ProgressDef {
  type: 'Progress'
  id?: ComponentId
  value: ValueRef<number>
  max?: ValueRef<number>            // default 1.0
  color?: ColorToken
  show_label?: boolean              // e.g. "75/100"
  size?: SizeToken
  layout?: Layout
}

export interface AvatarDef {
  type: 'Avatar'
  id?: ComponentId
  src?: ValueRef<string>            // asset id; falls back to initials
  initials?: ValueRef<string>
  size?: SizeToken
  shape?: 'circle' | 'rounded' | 'square'
}

export interface SkeletonDef {
  type: 'Skeleton'
  id?: ComponentId
  layout?: Layout                   // width/height from layout
  shape?: 'rect' | 'circle' | 'text-line'
}

export interface SeparatorDef {
  type: 'Separator'
  id?: ComponentId
  direction?: 'horizontal' | 'vertical'
  color?: ColorToken
}

// ── Container atoms ──────────────────────────────────────────────

export interface CardDef {
  type: 'Card'
  id?: ComponentId
  layout?: Layout
  style?: BoxStyle & { glass?: boolean }
  children: ComponentDef[]
}

export interface DialogDef {
  type: 'Dialog'
  id?: ComponentId
  open: ValueRef<boolean>           // controlled open state
  title?: ValueRef<string>
  children: ComponentDef[]
  on_close?: UIActionRef
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'fullscreen'
  dismissable?: boolean             // click-outside or Esc closes
}

export interface TooltipDef {
  type: 'Tooltip'
  id?: ComponentId
  content: ValueRef<string>
  delay_ms?: number
  placement?: 'top' | 'bottom' | 'left' | 'right'
  target: ComponentDef              // the child gets the tooltip behavior
}

export interface AccordionDef {
  type: 'Accordion'
  id?: ComponentId
  items: Array<{
    id: ComponentId
    title: ValueRef<string>
    content: ComponentDef[]
    open?: ValueRef<boolean>        // default closed
  }>
  multi_open?: boolean              // allow multiple items open simultaneously
}

export interface ScrollableDef {
  type: 'Scrollable'
  id?: ComponentId
  layout?: Layout
  direction?: 'vertical' | 'horizontal' | 'both'
  children: ComponentDef[]
}

export interface AlertDef {
  type: 'Alert'
  id?: ComponentId
  title?: ValueRef<string>
  content: ValueRef<string>
  color?: ColorToken                // default 'info'
  dismissable?: boolean
  on_dismiss?: UIActionRef
  icon?: string
}

export interface TabsDef {
  type: 'Tabs'
  id?: ComponentId
  value: MechanicRef                // two-way bound; which tab is active
  tabs: Array<{
    id: string
    label: ValueRef<string>
    icon?: string
    content: ComponentDef[]
  }>
  orientation?: 'horizontal' | 'vertical'
}

// ═════════════════════════════════════════════════════════════════
// Game composites — action-blocks UI mechanics compile to these.
// Higher-level than web-library atoms; not typically used directly
// in web scaffolds.
// ═════════════════════════════════════════════════════════════════

export interface HUDDef {
  type: 'HUD'
  id?: ComponentId
  anchor: Anchor                    // position on screen edge/corner
  fields: HUDField[]
  style?: {
    gap?: SizeToken
    padding?: SizeToken
    bg?: 'none' | 'panel' | 'glass'
  }
  layout_direction?: 'row' | 'column'
}

export interface HUDField {
  type: 'text' | 'bar' | 'icon+text' | 'avatar' | 'counter' | 'mini_map'
  value: ValueRef<number | string>
  max?: ValueRef<number>            // for bar
  label?: ValueRef<string>
  color?: ColorToken
  icon?: string                     // asset id
  format?: string                   // e.g. '{value}/{max}', 'x{value}'
}

export interface MenuDef {
  type: 'Menu'
  id?: ComponentId
  title?: ValueRef<string>
  items: MenuItem[]
  orientation?: 'vertical' | 'horizontal'
  keyboard_navigable?: boolean      // default true; supports arrow keys
  on_back?: UIActionRef             // emitted on Esc / Back
  anchor?: Anchor                   // default 'center'
  style?: { panel?: 'solid' | 'glass' | 'transparent' }
}

export interface MenuItem {
  label: ValueRef<string>
  icon?: string
  action: UIActionRef
  disabled?: ValueRef<boolean>
  submenu?: MenuItem[]
  hotkey?: string                   // e.g. 'Enter', 'Space', 'P'
}

export interface DialogTreeDef {
  type: 'DialogTree'
  id?: ComponentId
  speaker?: ValueRef<string>
  portrait?: ValueRef<string>       // asset id (char portrait from sprite manifest)
  content: ValueRef<string>
  choices?: DialogChoice[]          // none = auto-advance on click/input
  on_advance?: UIActionRef          // fired when content is dismissed w/o choice
  anchor?: Anchor                   // default 'bottom'
  size?: 'compact' | 'standard' | 'full'
  style?: { panel?: 'parchment' | 'tech' | 'clean' | 'retro' | 'comic' }
  typewriter?: { enabled: boolean; chars_per_sec?: number }
}

export interface DialogChoice {
  label: ValueRef<string>
  action: UIActionRef
  gate?: MechanicRef                // show only if this field is truthy
  preview?: ValueRef<string>        // hover/focus hint text
}

export interface InventoryPanelDef {
  type: 'InventoryPanel'
  id?: ComponentId
  inventory: MechanicRef            // binds to Inventory component's items field
  slots: number | 'dynamic'
  columns: number
  item_size?: SizeToken
  on_select?: UIActionRef
  on_use?: UIActionRef
  empty_slot_icon?: string
  style?: { panel?: 'grid' | 'list' }
}

export interface ShopPanelDef {
  type: 'ShopPanel'
  id?: ComponentId
  inventory: MechanicRef            // shop's available items
  wallet: MechanicRef               // player's currency
  on_buy?: UIActionRef
  on_sell?: UIActionRef
  allow_sell?: boolean
  title?: ValueRef<string>
}

export interface TutorialCalloutDef {
  type: 'TutorialCallout'
  id?: ComponentId
  target?: ComponentId | 'screen'   // what this callout is pointing at
  content: ValueRef<string>
  placement?: 'top' | 'bottom' | 'left' | 'right'
  dismiss_on?: ConditionKey | 'click' | 'next_step'
  on_dismiss?: UIActionRef
  step?: number                     // for multi-step tutorials
}
```

## Compiler contracts

Each renderer implements:

```ts
// ── Compiler signature (same for both renderers) ────────────────

export interface UIRenderer {
  name: 'dom' | 'webgpu'
  mount(root: HTMLElement | GPUCanvasContext, theme: Theme): UIInstance
}

export interface UIInstance {
  /** Render the spec. Called each frame (webgpu) or on state change (dom). */
  render(spec: ComponentDef): void

  /** Tear down. */
  destroy(): void

  /** Resolve a MechanicRef to current value (both renderers use the same binding layer). */
  resolve<T>(ref: ValueRef<T>): T

  /** Dispatch a UIActionRef (both renderers share). */
  dispatch(action: UIActionRef): void
}
```

### DOM renderer (React)

Thin compiler from `ComponentDef` → React element tree, targeting the
existing `scaffolds/*/components/ui` library.

```ts
// ark/scaffolds/_shared/ui/dom_compiler.tsx (or similar)

import * as UI from './components/ui'  // Button, Card, Dialog, etc.

export function compileToReact(spec: ComponentDef, ctx: RenderContext): React.ReactNode {
  switch (spec.type) {
    case 'Box':
      return (
        <div style={layoutToCss(spec.layout)} className={boxStyleClass(spec.style)}>
          {spec.children.map((c, i) => compileToReact(c, ctx))}
        </div>
      )
    case 'Text':
      return <span className={textStyleClass(spec.style)}>{ctx.resolve(spec.content)}</span>
    case 'Button':
      return (
        <UI.Button
          variant={spec.variant}
          color={spec.color}
          disabled={ctx.resolve(spec.disabled ?? false)}
          onClick={() => ctx.dispatch(spec.on_click!)}
        >
          {ctx.resolve(spec.label)}
        </UI.Button>
      )
    case 'Progress':
      return <UI.Progress value={ctx.resolve(spec.value)} max={ctx.resolve(spec.max ?? 1)} />
    // ... one case per component type
    case 'HUD':
      // HUD in DOM: a fixed-position container with flex children
      return (
        <div style={hudPositionCss(spec.anchor, spec.style)}>
          {spec.fields.map((f, i) => <HUDFieldReact key={i} field={f} ctx={ctx} />)}
        </div>
      )
    case 'DialogTree':
      return <DialogTreeReact spec={spec} ctx={ctx} />
    // ...
  }
}
```

Reuses the existing 14-component library verbatim. Game composites
(HUD, DialogTree, InventoryPanel, etc.) compile to React components
written once per scaffold family.

### WebGPU renderer (immediate-mode)

Delegates to JB's renderer (MSDF text + quad batcher + Yoga layout +
immediate-mode UI shell). The compiler just traverses the spec tree
and issues immediate-mode calls.

```ts
// ark/scaffolds/engine/src/ui/webgpu_compiler.ts

import { ui } from '@engine/ui'   // JB's immediate-mode API

export function compileToWebGPU(spec: ComponentDef, ctx: RenderContext): void {
  switch (spec.type) {
    case 'Box':
      ui.begin_box(layoutToYoga(spec.layout), boxStyle(spec.style))
      for (const child of spec.children) compileToWebGPU(child, ctx)
      ui.end_box()
      break
    case 'Text':
      ui.text(ctx.resolve(spec.content), textStyle(spec.style))
      break
    case 'Button':
      if (ui.button(ctx.resolve(spec.label), buttonStyle(spec))) {
        ctx.dispatch(spec.on_click!)
      }
      break
    case 'Progress':
      ui.progress(ctx.resolve(spec.value), ctx.resolve(spec.max ?? 1), progressStyle(spec))
      break
    case 'HUD':
      ui.anchor(anchorFor(spec.anchor), spec.style)
      for (const field of spec.fields) renderHUDField(field, ctx)
      ui.end_anchor()
      break
    // ... one case per component
  }
}
```

Immediate-mode idiom: `if (ui.button(...))` returns true when clicked
this frame. Matches Dear ImGui conventions JB likely already thinks in.

## Action-blocks UI-mechanic integration

Seven action-blocks mechanics are UI-space. Their compilers (in the
engine's `design/mechanics/` tree) take mechanic params + produce a
`ComponentDef` subtree, which then goes to either renderer.

| Mechanic | Compiles to |
|---|---|
| `HUD` | `HUDDef` |
| `Menu` (flow) | `MenuDef` |
| `DialogTree` | `DialogTreeDef` |
| `Tutorial` | `TutorialCalloutDef` |
| `Shop` | `ShopPanelDef` |
| `InventoryPanel` (display of Inventory component) | `InventoryPanelDef` |
| `HotspotMechanic` action-menu (when hotspot is clicked and shows choices) | `MenuDef` with dynamic position |

Example — `HUD` mechanic lowering:

```ts
// engine/src/design/mechanics/hud.ts
import type { HudParams, ComponentDef, HUDDef } from '@engine/schema'

export function lowerHUD(m: {id: string, params: HudParams}): ComponentDef {
  return {
    type: 'HUD',
    id: m.id as ComponentId,
    anchor: m.params.layout === 'corners' ? 'top-right' : 'top',
    fields: m.params.fields.map(field_to_hud_field),
    style: { gap: 'md', padding: 'md', bg: 'glass' },
  }
}

function field_to_hud_field(f): HUDField {
  if ('component' in f) {
    // archetype.component reference
    return {
      type: detectFieldType(f.component),   // e.g. 'Health' → bar, 'Score' → counter
      value: { mechanic_ref: archetypeToMechanic(f.archetype), field: f.component },
      max:   detectMax(f),
      label: f.label,
      color: colorForField(f.component),
    }
  } else {
    // mechanic.field reference (e.g. waves.wave_index)
    return {
      type: 'counter',
      value: { mechanic_ref: f.mechanic, field: f.field },
      label: f.label,
    }
  }
}
```

The UI framework doesn't own mechanic semantics; mechanics emit
ComponentDefs, the UI framework renders them.

## State binding model

Both renderers share one binding layer. The `RenderContext.resolve()`
function reads a `MechanicRef` against the live game state (or
component state, for web scaffolds).

```ts
export interface RenderContext {
  /** Resolve a ValueRef<T> to current T (live read per frame / render). */
  resolve<T>(ref: ValueRef<T>): T
  /** Dispatch a UIActionRef to the engine's event system. */
  dispatch(action: UIActionRef): void
  /** Current theme. */
  theme: Theme
}
```

In the WebGPU renderer: reads directly from the mechanic instance's
exposed fields (`ctx.publishField` machinery from the action-blocks
runtime).

In the DOM renderer: reads from a React state store (Zustand /
context / whatever the scaffold uses). Mechanic refs in DOM mode map
to store keys — the compiler produces subscription wrappers so
progress bars etc. re-render on change.

Two-way bound components (`Input`, `Toggle`, `Select`, `Slider`,
`Tabs`) also call `dispatch` with an implicit `set_field` action on
user input:

```ts
// Implicit action dispatched by Input on change:
{ kind: 'set_field', ref: { mechanic_ref, field }, value: newValue }
```

`set_field` is added to the UIActionRef union above as needed.

## Theme

```ts
// Default theme — scaffold can override.
const DEFAULT_THEME: Theme = {
  colors: {
    default:   '#1a1a1a',
    primary:   '#3b82f6',
    secondary: '#8b5cf6',
    accent:    '#f59e0b',
    muted:     '#6b7280',
    danger:    '#ef4444',
    warning:   '#f97316',
    success:   '#10b981',
    info:      '#06b6d4',
  },
  sizes: { xs: 0.75, sm: 0.875, md: 1.0, lg: 1.25, xl: 1.5 },
  radii: { none: 0, xs: 2, sm: 4, md: 6, lg: 8, xl: 12, full: 9999 },
  font_size_base: 16,
}

// Scaffold-specific theme (game scaffold might lean retro):
const RETRO_GAME_THEME: Theme = {
  colors: {
    default: '#0f380f',   // Game Boy green
    primary: '#8bac0f',
    // ...
  },
  font_family: { sans: 'PressStart2P', mono: 'PressStart2P', display: 'PressStart2P', serif: 'PressStart2P' },
  // ...
}
```

Theme is loaded at renderer mount time; color/size/radius tokens
resolve through it.

## Scaffold selection

```ts
// scaffolds/game/src/main.ts
import { WebGPURenderer } from '@engine/ui'

const renderer = new WebGPURenderer()
renderer.mount(canvas.getContext('webgpu'), RETRO_GAME_THEME)
// ... game loop calls renderer.render(compiledSpec) each frame

// scaffolds/auth-app/src/App.tsx
import { DOMRenderer } from '@shared/ui/dom'

const renderer = new DOMRenderer()
renderer.mount(document.getElementById('root')!, DEFAULT_THEME)
// ... React handles its own re-render loop
```

Each scaffold picks one. Choice is mount-time, not runtime.

## Tsunami prompt scaffold integration

Tsunami emits `ComponentDef` subtrees as part of design scripts. The
prompt scaffold (a section in `tsunami/context/design_script.md`) gives
the LLM:

1. **One-line descriptions** of each component type.
2. **Layout + token vocab** — Size, ColorToken, SizeToken, Anchor, VariantToken.
3. **2–3 example subtrees per common use case** (HUD, main menu, dialog, inventory).
4. **The `@ui-spec` import reference** — where types live.

Example block the LLM sees:

```markdown
## UI: ComponentDef

Declarative UI tree. Compiles to DOM (for web scaffolds) or WebGPU
(for the game scaffold). Same vocabulary, two renderers.

### Common cases

**Main menu (top-level):**
```json
{
  "type": "Menu",
  "title": "Pause",
  "items": [
    { "label": "Resume",     "action": { "kind": "close" } },
    { "label": "Save",       "action": { "kind": "emit", "condition": "save_requested" } },
    { "label": "Quit",       "action": { "kind": "emit", "condition": "quit_requested" } }
  ],
  "anchor": "center",
  "style": { "panel": "solid" }
}
```

**HUD (corner overlay):**
```json
{
  "type": "HUD",
  "anchor": "top-right",
  "fields": [
    { "type": "bar", "label": "HP",
      "value": { "mechanic_ref": "player_health", "field": "health" },
      "max":   { "mechanic_ref": "player_health", "field": "maxHealth" },
      "color": "danger" },
    { "type": "counter", "label": "Score",
      "value": { "mechanic_ref": "score", "field": "current" },
      "color": "accent" },
    { "type": "counter", "label": "Wave",
      "value": { "mechanic_ref": "waves", "field": "wave_index" } }
  ]
}
```

### Tokens
- Sizes: `xs` `sm` `md` `lg` `xl`
- Colors: `default` `primary` `secondary` `accent` `muted` `danger` `warning` `success` `info`
- Variants: `solid` `outline` `ghost` `link`
- Anchors: `top-left` `top` `top-right` `left` `center` `right` `bottom-left` `bottom` `bottom-right`
```

That section replaces / augments the UI portion of the prose dump in
`agent.py:2696-2716`.

## Validator errors

Additions to the action-blocks validator table:

| Error kind | Condition |
|---|---|
| `unknown_component_type` | `ComponentDef.type` not in the union |
| `invalid_component_tree` | structural issue (e.g. Text with no content, Dialog with missing children) |
| `unresolved_component_ref` | `UIActionRef.kind:'focus'` / `'open'` / `'close'` references a `ComponentId` not present in the tree |
| `invalid_value_ref` | `MechanicRef` binding points to a non-exposed field on the target mechanic |
| `layout_impossible` | contradictory layout constraints (e.g. `width: 'fill'` on an absolutely-positioned child with `anchor` set — pick one) |

5 new classes. Wire into the same validator as action-blocks.

## Ship criteria

11 tests; all pass before v1.1 UI framework ships:

1. **Type-spec compiles.** The full `ComponentDef` union plus
   layout/style/theme types typecheck in TS strict mode.
2. **DOM renderer coverage.** Every non-game-composite component (27
   types) has a working React compiler case that renders without
   crashing given a minimal fixture.
3. **WebGPU renderer coverage.** Every non-game-composite component
   has a working immediate-mode compiler case (JB's renderer).
4. **Game composites DOM.** HUD + Menu + DialogTree + InventoryPanel
   + ShopPanel + TutorialCallout compile to working React trees.
5. **Game composites WebGPU.** Same 6 compile to working immediate-
   mode calls.
6. **Two-way binding.** `Input` bound to a `MechanicRef`: typing
   updates the ref; ref change updates displayed value. Both
   renderers.
7. **Action dispatch.** `Button.on_click` with `{kind:'emit', condition:'foo'}`
   fires the condition on flow. Both renderers.
8. **Theme override.** Mounting with a non-default Theme produces
   correctly-tinted output. Both renderers.
9. **Action-blocks integration.** One design script with `HUD` +
   `Menu` + `DialogTree` mechanics compiles + runs on the game scaffold.
10. **Tsunami emission.** Tsunami-written design script with
    `ComponentDef` subtrees validates against the schema.
11. **Validator.** 5 malformed specs produce the correct 5 error
    classes.

## Rendering identity check

Both renderers should produce visually similar (not identical) output
for the same spec + theme. The contract is structural parity:

- Same layout proportions (flex + absolute positioning both render the
  same bounding boxes)
- Same token-resolved colors
- Same typography hierarchy (headings bigger than body; bold where bold)
- Same affordances (buttons look clickable; disabled looks disabled)

Pixel-exact parity is not required. DOM uses browser text rendering
(subpixel AA, native kerning); WebGPU uses JB's MSDF (whatever he
tunes). Authors compose against the spec; the renderer decides exact
pixels.

## Out of scope (v1.2+)

| Item | When | Why |
|---|---|---|
| Animations (transitions, tweens, easing) | v1.2 | Additive; needs a motion spec layer |
| Drag-and-drop | v1.2 | Inventory-DnD is the main use case; needs event model extension |
| Virtualized lists / infinite scroll | v1.2 | Performance optimization; not v1.1-blocking |
| Custom canvas widgets (charts, spectrograms) | v1.2+ | Escape hatch; spec allows a `Custom` component kind |
| Rich text (inline colors, bold, links) in `Text` | v1.2 | For now, split into multiple `Text` + layout. `TextSpan` added v1.2 |
| Video / WebRTC overlays | v1.3+ | Out of primitive scope |
| Accessibility tree (ARIA mirror for WebGPU renderer) | v1.2 | Important but separable; ~1 day work on its own |
| RTL / bidi text | v1.2 | MSDF side; JB's concern |
| IME input composition | v1.2 | Hybrid input shim; ~2 days |
| Native drag-and-drop from OS (files) | never in UI framework; use scaffold-level API |

## Open questions

1. **Size token resolution.** `size: 'md'` on a button — should the
   theme scale relative to `font_size_base` (so one theme tweak
   rescales everything) or hold absolute px per token? Recommendation:
   theme-scaled. Authors get one-knob type-scale control.

2. **Component composition vs. direct atoms in scaffolds.** Should
   web scaffolds (auth-app etc.) author in `ComponentDef` and go
   through the DOM compiler, or keep authoring in native JSX with
   direct `UI.Button` imports? Recommendation: **both are valid.**
   Authors use `ComponentDef` when they want cross-renderer portability
   (embeddable widgets, snippets shared with game UI); JSX when it's
   a pure web app.

3. **Theme per-scaffold vs. shared theme object.** Each scaffold can
   ship its own theme; the spec doesn't prescribe a sharing model.
   Worth a `theme.ts` file convention per scaffold.

4. **Icon atlas source.** Icons resolve by name; who owns the atlas?
   Recommendation: part of the sprite extension — icons live in
   `assets.manifest.json` with `category: 'ui_element'`. Existing
   sprite pipeline bakes them; this UI spec refers by asset id.

5. **Hot-reload semantics.** In DOM, React handles it. In WebGPU
   immediate-mode, spec re-render per-frame handles it automatically
   (edit spec → next frame shows change). Both fine.

6. **Gamepad input mapping.** UI framework needs directional focus
   navigation for controllers. Deferred to v1.2 or handled at the
   engine input layer — mechanic proposal rather than UI proposal.

## Implementation order

For the programmer landing this (after JB's renderer lands):

1. **Types module.** Port the TS spec above to
   `ark/scaffolds/_shared/ui-spec/index.ts`. No behavior; just types.
2. **DOM compiler.** `_shared/ui-spec/dom_compiler.tsx` — React
   compiler using scaffold's `components/ui` library. One case per
   component type.
3. **WebGPU compiler.** `ark/scaffolds/engine/src/ui/webgpu_compiler.ts` —
   immediate-mode compiler calling JB's `@engine/ui` API.
4. **Theme module.** `_shared/ui-spec/theme.ts` — DEFAULT_THEME +
   per-scaffold overrides.
5. **Action-blocks UI-mechanic compilers.** `engine/src/design/mechanics/
   hud.ts`, `menu.ts`, `dialog_tree.ts`, `tutorial.ts`, `shop.ts`,
   `inventory_panel.ts`. Each mechanic's lowering returns a
   `ComponentDef`.
6. **Validator additions.** 5 new error classes wired into the
   action-blocks validator.
7. **Tsunami prompt scaffold update.** Replace/extend the UI portion
   of `agent.py:2696-2716` with the ComponentDef vocabulary and
   example subtrees.
8. **Tests.** 11 ship-criteria tests above, split across DOM/WebGPU
   modules.

Each phase is PR-sized. Depend on JB's renderer for phases 3+5+8.

## Summary

- **DRY at the spec layer, not the renderer.** One `ComponentDef`
  union; two renderers compile it.
- **Web scaffolds** use the DOM renderer over the existing
  `components/ui` library — no new React work beyond the thin
  compiler.
- **Game scaffold** uses the WebGPU renderer (JB's MSDF text + quad
  batcher + Yoga + immediate-mode shell).
- **Action-blocks UI mechanics** (HUD, Menu, DialogTree, Tutorial,
  Shop, InventoryPanel) compile to ComponentDef subtrees.
- **Tsunami authors ComponentDef** as part of design scripts.
- **Theme tokens** (color, size, radius, font) resolve per renderer.
- **Cross-platform by construction**: any surface that can run WebGPU
  gets the same UI without re-authoring.

Ready for JB's renderer to slot in. Programmer can start on phases
1–2 (types + DOM compiler) immediately; phases 3+5+8 gate on JB.
