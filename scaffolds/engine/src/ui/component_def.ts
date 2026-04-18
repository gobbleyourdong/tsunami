/**
 * ComponentDef — framework-neutral declarative UI spec.
 *
 * One vocabulary for authoring UI; two renderers compile it:
 *   - WebGPU compiler → immediate-mode calls (see `webgpu_compiler.ts`)
 *   - DOM compiler    → React/JSX (see `dom_compiler.tsx`)
 *
 * Scaffolds + action-blocks UI mechanics both emit ComponentDef
 * subtrees; renderers don't need to know about their origin.
 *
 * # Status
 *   Branded IDs + value/action refs   ✓ scaffold
 *   Atom types                         ✓ scaffold (Box, Text, Image, Icon)
 *   Form atoms                         ✓ scaffold (Button, Input, Toggle,
 *                                       Select, Slider)
 *   Display atoms                      ✓ scaffold (Badge, Progress, Avatar,
 *                                       Skeleton, Separator)
 *   Container atoms                    ✓ scaffold (Card, Dialog, Tooltip,
 *                                       Accordion, Scrollable, Alert, Tabs)
 *   Game composites                    ✓ scaffold (HUD, Menu, DialogTree,
 *                                       InventoryPanel, ShopPanel,
 *                                       TutorialCallout)
 *   ComponentDef union                 ✓ scaffold
 *
 * Types only. No rendering logic. Full architectural rationale in
 * `ark/tsunami/design/action_blocks/ui_framework/attempts/attempt_001.md`.
 */

import type {
  ColorToken, SizeToken, VariantToken, BorderRadius,
  FontFamilyToken,
} from './theme'
import type { Layout, Anchor } from './layout'

// ── Branded IDs (structural safety for cross-references) ─────────

export type ComponentId = string & { __brand: 'ComponentId' }

/** Reference to an action-blocks mechanic by id. Opaque at this layer. */
export type MechanicId = string & { __brand: 'MechanicId' }

/** Named flow condition. The action-blocks flow emits these. */
export type ConditionKey = string & { __brand: 'ConditionKey' }

// ── Value + action bindings ─────────────────────────────────────

/** Reactive read: points at a mechanic's exposed field. */
export interface MechanicRef {
  mechanic_ref: MechanicId
  field: string
}

/** A value that's either a literal or a live ref to a mechanic field. */
export type ValueRef<T> = T | MechanicRef

/**
 * Action dispatched by UI on click / change / submit / focus events.
 * Subset of action-blocks ActionRef plus UI-specific kinds.
 */
export type UIActionRef =
  | { kind: 'emit';     condition: ConditionKey }
  | { kind: 'set_flag'; name: string;  value: unknown }
  | { kind: 'set_field'; ref: MechanicRef; value: unknown }  // two-way bindings
  | { kind: 'focus';    target: ComponentId }
  | { kind: 'open';     target: ComponentId }
  | { kind: 'close';    target?: ComponentId }                // nearest Dialog if omitted
  | { kind: 'play_sfx_ref'; library_ref: MechanicId; preset: string }  // audio-ext bridge
  | { kind: 'navigate'; to: string }                          // scaffold-level route

// ── Shared style sub-types ──────────────────────────────────────

export type ShadowToken = 'none' | SizeToken

export interface BoxStyleSpec {
  bg?:          ColorToken | 'none' | 'panel' | 'glass'
  border?:      ColorToken | 'none'
  border_width?: number
  rounded?:     BorderRadius
  shadow?:      ShadowToken
  opacity?:     number                 // 0..1
}

export interface TextStyleSpec {
  size?:     SizeToken | number
  weight?:   'normal' | 'medium' | 'bold'
  color?:    ColorToken
  align?:    'left' | 'center' | 'right'
  italic?:   boolean
  truncate?: boolean
  wrap?:     boolean
  font?:     FontFamilyToken
}

// ═════════════════════════════════════════════════════════════════
// ATOMS
// ═════════════════════════════════════════════════════════════════

export interface BoxDef {
  type: 'Box'
  id?: ComponentId
  layout?: Layout
  style?: BoxStyleSpec
  children: ComponentDef[]
}

export interface TextDef {
  type: 'Text'
  id?: ComponentId
  content: ValueRef<string>
  style?: TextStyleSpec
}

export interface ImageDef {
  type: 'Image'
  id?: ComponentId
  src: ValueRef<string>                // asset id (sprite manifest) or URL
  alt?: string
  fit?: 'contain' | 'cover' | 'fill' | 'none'
  layout?: Layout
}

export interface IconDef {
  type: 'Icon'
  id?: ComponentId
  name: ValueRef<string>               // lookup in UI icon atlas
  size?: SizeToken
  color?: ColorToken
}

// ═════════════════════════════════════════════════════════════════
// FORM ATOMS
// ═════════════════════════════════════════════════════════════════

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
  value: MechanicRef                   // two-way bound
  placeholder?: string
  input_type?: 'text' | 'number' | 'password' | 'email'
  disabled?: ValueRef<boolean>
  on_submit?: UIActionRef
  layout?: Layout
}

export interface ToggleDef {
  type: 'Toggle'
  id?: ComponentId
  value: MechanicRef                   // two-way bound boolean
  label?: ValueRef<string>
  disabled?: ValueRef<boolean>
  on_change?: UIActionRef
}

export interface SelectDef {
  type: 'Select'
  id?: ComponentId
  value: MechanicRef                   // two-way bound
  options: Array<{
    label: ValueRef<string>
    value: unknown
    icon?: string
  }>
  placeholder?: string
  disabled?: ValueRef<boolean>
  on_change?: UIActionRef
  layout?: Layout
}

export interface SliderDef {
  type: 'Slider'
  id?: ComponentId
  value: MechanicRef                   // two-way bound number
  min: number
  max: number
  step?: number
  label?: ValueRef<string>
  on_change?: UIActionRef
}

// ═════════════════════════════════════════════════════════════════
// DISPLAY ATOMS
// ═════════════════════════════════════════════════════════════════

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
  max?: ValueRef<number>               // default 1.0
  color?: ColorToken
  show_label?: boolean                 // e.g. "75 / 100"
  size?: SizeToken
  layout?: Layout
}

export interface AvatarDef {
  type: 'Avatar'
  id?: ComponentId
  src?: ValueRef<string>               // asset id; falls back to initials
  initials?: ValueRef<string>
  size?: SizeToken
  shape?: 'circle' | 'rounded' | 'square'
}

export interface SkeletonDef {
  type: 'Skeleton'
  id?: ComponentId
  layout?: Layout
  shape?: 'rect' | 'circle' | 'text-line'
}

export interface SeparatorDef {
  type: 'Separator'
  id?: ComponentId
  direction?: 'horizontal' | 'vertical'
  color?: ColorToken
}

// ═════════════════════════════════════════════════════════════════
// CONTAINER ATOMS
// ═════════════════════════════════════════════════════════════════

export interface CardDef {
  type: 'Card'
  id?: ComponentId
  layout?: Layout
  style?: BoxStyleSpec & { glass?: boolean }
  children: ComponentDef[]
}

export interface DialogDef {
  type: 'Dialog'
  id?: ComponentId
  open: ValueRef<boolean>              // controlled open state
  title?: ValueRef<string>
  children: ComponentDef[]
  on_close?: UIActionRef
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'fullscreen'
  dismissable?: boolean                // click-outside / Esc closes
}

export interface TooltipDef {
  type: 'Tooltip'
  id?: ComponentId
  content: ValueRef<string>
  delay_ms?: number
  placement?: 'top' | 'bottom' | 'left' | 'right'
  target: ComponentDef                 // child that gets the hover behavior
}

export interface AccordionDef {
  type: 'Accordion'
  id?: ComponentId
  items: Array<{
    id: ComponentId
    title: ValueRef<string>
    content: ComponentDef[]
    open?: ValueRef<boolean>
  }>
  multi_open?: boolean
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
  color?: ColorToken                   // default 'info'
  dismissable?: boolean
  on_dismiss?: UIActionRef
  icon?: string
}

export interface TabsDef {
  type: 'Tabs'
  id?: ComponentId
  value: MechanicRef                   // two-way bound; active tab id
  tabs: Array<{
    id: string
    label: ValueRef<string>
    icon?: string
    content: ComponentDef[]
  }>
  orientation?: 'horizontal' | 'vertical'
}

// ═════════════════════════════════════════════════════════════════
// GAME COMPOSITES — action-blocks UI mechanics compile to these.
// ═════════════════════════════════════════════════════════════════

export type HUDFieldKind =
  | 'text' | 'bar' | 'icon+text' | 'avatar' | 'counter' | 'mini_map'

export interface HUDField {
  type: HUDFieldKind
  value: ValueRef<number | string>
  max?: ValueRef<number>               // for bar
  label?: ValueRef<string>
  color?: ColorToken
  icon?: string
  format?: string                      // e.g. "{value}/{max}", "x{value}"
}

export interface HUDDef {
  type: 'HUD'
  id?: ComponentId
  anchor: Anchor
  fields: HUDField[]
  style?: {
    gap?: SizeToken
    padding?: SizeToken
    bg?: 'none' | 'panel' | 'glass'
  }
  layout_direction?: 'row' | 'column'
}

export interface MenuItem {
  label: ValueRef<string>
  icon?: string
  action: UIActionRef
  disabled?: ValueRef<boolean>
  submenu?: MenuItem[]
  hotkey?: string                      // e.g. 'Enter', 'Space', 'P'
}

export interface MenuDef {
  type: 'Menu'
  id?: ComponentId
  title?: ValueRef<string>
  items: MenuItem[]
  orientation?: 'vertical' | 'horizontal'
  keyboard_navigable?: boolean         // default true
  on_back?: UIActionRef
  anchor?: Anchor
  style?: { panel?: 'solid' | 'glass' | 'transparent' }
}

export interface DialogChoice {
  label: ValueRef<string>
  action: UIActionRef
  gate?: MechanicRef                   // show only if truthy
  preview?: ValueRef<string>           // hover/focus hint
}

export interface DialogTreeDef {
  type: 'DialogTree'
  id?: ComponentId
  speaker?: ValueRef<string>
  portrait?: ValueRef<string>          // sprite asset id
  content: ValueRef<string>
  choices?: DialogChoice[]             // omit = auto-advance on input
  on_advance?: UIActionRef
  anchor?: Anchor                      // default 'bottom'
  size?: 'compact' | 'standard' | 'full'
  style?: { panel?: 'parchment' | 'tech' | 'clean' | 'retro' | 'comic' }
  typewriter?: { enabled: boolean; chars_per_sec?: number }
}

export interface InventoryPanelDef {
  type: 'InventoryPanel'
  id?: ComponentId
  inventory: MechanicRef               // Inventory component's items field
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
  inventory: MechanicRef               // shop stock
  wallet: MechanicRef                  // player's currency
  on_buy?: UIActionRef
  on_sell?: UIActionRef
  allow_sell?: boolean
  title?: ValueRef<string>
}

export interface TutorialCalloutDef {
  type: 'TutorialCallout'
  id?: ComponentId
  target?: ComponentId | 'screen'      // what to point at
  content: ValueRef<string>
  placement?: 'top' | 'bottom' | 'left' | 'right'
  dismiss_on?: ConditionKey | 'click' | 'next_step'
  on_dismiss?: UIActionRef
  step?: number                        // multi-step tutorials
}

// ═════════════════════════════════════════════════════════════════
// ComponentDef — the union
// ═════════════════════════════════════════════════════════════════

export type ComponentDef =
  // Atoms
  | BoxDef | TextDef | ImageDef | IconDef
  // Form atoms
  | ButtonDef | InputDef | ToggleDef | SelectDef | SliderDef
  // Display atoms
  | BadgeDef | ProgressDef | AvatarDef | SkeletonDef | SeparatorDef
  // Container atoms
  | CardDef | DialogDef | TooltipDef | AccordionDef
  | ScrollableDef | AlertDef | TabsDef
  // Game composites
  | HUDDef | MenuDef | DialogTreeDef
  | InventoryPanelDef | ShopPanelDef | TutorialCalloutDef

/** Discriminator extraction helper for the exhaustiveness-check pattern. */
export type ComponentDefType = ComponentDef['type']

// ── Helpers for the compilers ────────────────────────────────────

/**
 * Narrow helper: given a ValueRef<T>, callers check `isMechanicRef(v)`
 * to know whether to subscribe or use literally.
 */
export function isMechanicRef<T>(v: ValueRef<T>): v is MechanicRef {
  return typeof v === 'object' && v !== null &&
    'mechanic_ref' in (v as object) && 'field' in (v as object)
}

/** Exhaustiveness helper for switch statements. */
export function assertNever(x: never): never {
  throw new Error(`unexpected ComponentDef.type: ${JSON.stringify(x)}`)
}
