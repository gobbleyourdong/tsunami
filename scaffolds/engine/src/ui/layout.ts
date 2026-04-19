/**
 * UI layout engine — flex-like, framework-neutral.
 *
 * Scaffolds describe layout declaratively via the `Layout` struct;
 * `computeLayout(root, viewport)` resolves it to pixel rects.
 *
 * # Status
 *   Size / Anchor / Layout types  ✓ scaffold
 *   LayoutNode / LayoutResult      ✓ scaffold
 *   resolveSize(Size, …) helper    ✓ scaffold (handles all Size shapes)
 *   computeLayout stub             ✓ scaffold — stacks children
 *                                    top-to-bottom, ignores flex, returns
 *                                    plausible rects for consumer testing
 *   Full flex engine               TODO — options: Yoga port, or
 *                                    custom 200-line flex.
 *                                    JB decides. See attempt_001 §Layout.
 *   Grid layout                    TODO v1.2
 *   Absolute-positioned anchors    ✓ scaffold (partial — uses viewport)
 *
 * Follows `text.ts` scaffolding pattern: types + stable interface
 * first; real computation replaceable without consumer changes.
 */

import type { SizeToken } from './theme'
import { DEFAULT_THEME, resolveSizeToken } from './theme'

// ── Primitive size types ─────────────────────────────────────────

export type Size =
  | number                          // absolute pixels
  | `${number}%`                    // percentage of parent
  | 'auto'                          // content-driven
  | 'fill'                          // grow to fill available
  | SizeToken                       // theme-resolved pixels

export type Anchor =
  | 'top-left'    | 'top'    | 'top-right'
  | 'left'        | 'center' | 'right'
  | 'bottom-left' | 'bottom' | 'bottom-right'

// ── Layout directive ─────────────────────────────────────────────

export interface Layout {
  // Flex flow
  direction?: 'row' | 'column'
  gap?: Size
  padding?: Size | [Size, Size, Size, Size]    // all or [top, right, bottom, left]
  align?: 'start' | 'center' | 'end' | 'stretch'
  justify?: 'start' | 'center' | 'end' | 'between' | 'around' | 'evenly'
  wrap?: boolean

  // Flex child
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

  // Absolute positioning (HUD corners, tooltips)
  anchor?: Anchor
  offset?: [Size, Size]
  z?: number
}

// ── Layout tree ──────────────────────────────────────────────────

export interface LayoutNode {
  /** Directive for this node. */
  layout?: Layout
  /** Children in flow order. */
  children?: LayoutNode[]
  /** Intrinsic size for leaf nodes (e.g. a text measurement). */
  intrinsic?: { width: number; height: number }
  /** Optional debug tag. */
  id?: string
}

export interface LayoutResult {
  x: number
  y: number
  width: number
  height: number
  z: number
  children: LayoutResult[]
  id?: string
}

// ── Size resolver ────────────────────────────────────────────────

/**
 * Convert a Size value to pixels given a parent dimension and theme.
 * Handles numbers, percentages, SizeToken names, 'auto', 'fill'.
 * 'auto' and 'fill' require context beyond this function — the
 * layout engine handles them; `resolveSize` returns `NaN` for
 * those as a sentinel.
 */
export function resolveSize(
  size: Size | undefined,
  parent_dim: number,
  theme = DEFAULT_THEME,
  fallback = 0,
): number {
  if (size === undefined || size === null) return fallback
  if (typeof size === 'number') return size
  if (size === 'auto' || size === 'fill') return Number.NaN
  if (typeof size === 'string' && size.endsWith('%')) {
    const n = parseFloat(size.slice(0, -1))
    return (n / 100) * parent_dim
  }
  // SizeToken
  return resolveSizeToken(size as SizeToken, theme)
}

// ── Anchor helper ────────────────────────────────────────────────

/**
 * Anchor origin as a (ox, oy) pair in 0..1 units of the parent.
 * Element's own origin alignment; applied with offset.
 */
export function anchorOrigin(a: Anchor): [number, number] {
  switch (a) {
    case 'top-left':     return [0.0, 0.0]
    case 'top':          return [0.5, 0.0]
    case 'top-right':    return [1.0, 0.0]
    case 'left':         return [0.0, 0.5]
    case 'center':       return [0.5, 0.5]
    case 'right':        return [1.0, 0.5]
    case 'bottom-left':  return [0.0, 1.0]
    case 'bottom':       return [0.5, 1.0]
    case 'bottom-right': return [1.0, 1.0]
  }
}

// ── Stub layout engine ───────────────────────────────────────────

/**
 * Compute layout for a tree rooted at `node` within the given viewport.
 *
 * STUB behavior (fire-1 scaffold):
 *   - Vertical stack of children
 *   - Each child takes its intrinsic size or 100 × 40 default
 *   - Absolute anchors position within viewport
 *   - `gap`, `padding`, `align`, `justify`, `wrap`, `grow/shrink/basis`
 *     are all ignored in the stub — they land with the real flex engine
 *
 * Consumers can call this today and get non-broken bounding boxes for
 * debug draws. Real layout happens when the flex engine lands.
 */
export function computeLayout(
  node: LayoutNode,
  viewport: { width: number; height: number },
  theme = DEFAULT_THEME,
): LayoutResult {
  return layoutStub(node, { x: 0, y: 0, width: viewport.width, height: viewport.height }, theme)
}

function layoutStub(
  node: LayoutNode,
  container: { x: number; y: number; width: number; height: number },
  theme: typeof DEFAULT_THEME,
): LayoutResult {
  const layout = node.layout ?? {}

  // Explicit sizes if given; otherwise intrinsic; otherwise container.
  const req_w = resolveSize(layout.width, container.width, theme, Number.NaN)
  const req_h = resolveSize(layout.height, container.height, theme, Number.NaN)

  const intr_w = node.intrinsic?.width ?? 100
  const intr_h = node.intrinsic?.height ?? 40

  const width  = Number.isNaN(req_w) ? intr_w : req_w
  const height = Number.isNaN(req_h) ? intr_h : req_h

  // Anchor / absolute positioning
  let x = container.x
  let y = container.y
  if (layout.anchor) {
    const [ox, oy] = anchorOrigin(layout.anchor)
    const offx = layout.offset ? resolveSize(layout.offset[0], container.width, theme, 0) : 0
    const offy = layout.offset ? resolveSize(layout.offset[1], container.height, theme, 0) : 0
    x = container.x + ox * container.width  - ox * width  + offx
    y = container.y + oy * container.height - oy * height + offy
  }

  // Children: stack vertically (stub). Real flex replaces this block.
  const children: LayoutResult[] = []
  let cursor_y = y
  for (const child of node.children ?? []) {
    const child_container = {
      x,
      y: cursor_y,
      width,
      height: height - (cursor_y - y),
    }
    const result = layoutStub(child, child_container, theme)
    children.push(result)
    cursor_y += result.height
  }

  return {
    x, y, width, height,
    z: layout.z ?? 0,
    children,
    id: node.id,
  }
}
