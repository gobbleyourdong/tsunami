/**
 * UI immediate-mode shell — ImGui-style API over primitives + text.
 *
 * Usage pattern:
 *   ui.begin_frame(pass, viewport)
 *   ui.begin_box({ layout: { direction: 'column', gap: 8 }, style: { bg: 'panel' } })
 *     ui.text('Hello', { size: 'md', color: 'fg' })
 *     if (ui.button('Click me', { variant: 'solid', color: 'primary' })) {
 *       handle_click()
 *     }
 *     ui.progress(player_hp / max_hp, { color: 'danger' })
 *   ui.end_box()
 *   ui.end_frame()
 *
 * # Status
 *   Public interface         ✓ scaffold (ImmediateUI + BoxDirective etc.)
 *   StubImmediateUI           ✓ scaffold — records call log; button()=false
 *   WebGPUImmediateUI         ✓ scaffold — begin/end nesting, cursor-
 *                              based top-to-bottom stack, primitive +
 *                              text dispatch. No flex yet (cursor layout
 *                              only); no input / hit-test (button()
 *                              returns false until input is wired).
 *   Hit-testing + clicks      TODO — needs input system integration
 *   Focus management          TODO v1.2
 *   Keyboard navigation       TODO v1.2
 *   Scroll containers         TODO v1.2
 *
 * Follows `text.ts` pattern: interface + stub + real impl + factory.
 */

import type { GPUContext } from '../renderer/gpu'
import type {
  ColorToken, SizeToken, VariantToken, BorderRadius, RGBA, Theme,
} from './theme'
import { DEFAULT_THEME, resolveColor, resolveSize, resolveRadius } from './theme'
import type { Layout, Anchor } from './layout'
import type { PrimitiveRenderer, RectStyle } from './primitives'
import { createPrimitiveRenderer } from './primitives'
import type { TextRenderer, TextStyle } from './text'
import { createTextRenderer } from './text'

// ── Public directive types ───────────────────────────────────────

export interface BoxStyle {
  /** Token or literal. 'panel' / 'glass' / 'none' map to semi-transparent fills. */
  bg?: ColorToken | 'panel' | 'glass' | 'none'
  /** Border color token. */
  border?: ColorToken | 'none'
  /** Border width in pixels; default 0. */
  border_width?: number
  /** Corner radius token. */
  rounded?: BorderRadius
  /** Shadow token (v1.2; ignored in scaffold). */
  shadow?: SizeToken | 'none'
}

export interface BoxDirective {
  layout?: Layout
  style?: BoxStyle
  /** Opaque id for focus tracking (future). */
  id?: string
}

export interface ButtonDirective {
  variant?: VariantToken
  color?: ColorToken
  size?: SizeToken
  disabled?: boolean
  icon_left?: string
  icon_right?: string
  /** Width in px or Size; defaults to content. */
  width?: number
}

export interface ProgressDirective {
  color?: ColorToken
  size?: SizeToken
  /** Show label like "75/100" next to bar. */
  show_label?: boolean
  width?: number
}

export interface UITextStyle {
  size?: SizeToken | number
  color?: ColorToken
  weight?: 'normal' | 'medium' | 'bold'
  align?: 'left' | 'center' | 'right'
  atlas?: string
}

export interface IconDirective {
  size?: SizeToken | number
  color?: ColorToken
}

export interface FrameViewport {
  width: number
  height: number
}

// ── Immediate UI interface ───────────────────────────────────────

export interface ImmediateUI {
  /** Start a frame. Internally calls primitives.begin + text.begin. */
  begin_frame(pass: GPURenderPassEncoder, viewport: FrameViewport): void

  /** Open a box (container). Pushes a layout context. */
  begin_box(d?: BoxDirective): void

  /** Close the most recent box. Pops a layout context. */
  end_box(): void

  /**
   * Draw a button. Returns `true` on frames where it was clicked.
   * Scaffold: always `false` until input is wired.
   */
  button(label: string, d?: ButtonDirective): boolean

  /** Draw a progress bar (value 0..max). */
  progress(value: number, max?: number, d?: ProgressDirective): void

  /** Draw text. */
  text(content: string, d?: UITextStyle): void

  /** Draw an icon by name (atlas lookup; v1 is placeholder). */
  icon(name: string, d?: IconDirective): void

  /** Fill remaining width/height with a colored rect (separator-like). */
  spacer(size?: number): void

  /** Flush everything. Internally calls primitives.end + text.end. */
  end_frame(): void

  /** Free GPU resources. */
  destroy(): void
}

// ── Internal box stack frame ─────────────────────────────────────

interface BoxFrame {
  x: number
  y: number
  width: number
  height: number
  cursor_x: number
  cursor_y: number
  direction: 'row' | 'column'
  gap: number
  padding_top: number
  padding_left: number
  id?: string
}

// ── Stub implementation ─────────────────────────────────────────

export class StubImmediateUI implements ImmediateUI {
  public readonly calls: Array<
    | { kind: 'begin_frame'; viewport: FrameViewport }
    | { kind: 'begin_box'; d?: BoxDirective }
    | { kind: 'end_box' }
    | { kind: 'button'; label: string; d?: ButtonDirective }
    | { kind: 'progress'; value: number; max: number; d?: ProgressDirective }
    | { kind: 'text'; content: string; d?: UITextStyle }
    | { kind: 'icon'; name: string; d?: IconDirective }
    | { kind: 'spacer'; size?: number }
    | { kind: 'end_frame' }
  > = []

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_gpu?: GPUContext, _theme?: Theme) {}

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  begin_frame(_pass: GPURenderPassEncoder, viewport: FrameViewport): void {
    this.calls.length = 0
    this.calls.push({ kind: 'begin_frame', viewport })
  }
  begin_box(d?: BoxDirective): void { this.calls.push({ kind: 'begin_box', d }) }
  end_box(): void { this.calls.push({ kind: 'end_box' }) }
  button(label: string, d?: ButtonDirective): boolean {
    this.calls.push({ kind: 'button', label, d })
    return false
  }
  progress(value: number, max = 1, d?: ProgressDirective): void {
    this.calls.push({ kind: 'progress', value, max, d })
  }
  text(content: string, d?: UITextStyle): void {
    this.calls.push({ kind: 'text', content, d })
  }
  icon(name: string, d?: IconDirective): void {
    this.calls.push({ kind: 'icon', name, d })
  }
  spacer(size?: number): void { this.calls.push({ kind: 'spacer', size }) }
  end_frame(): void { this.calls.push({ kind: 'end_frame' }) }
  destroy(): void { /* noop */ }
}

// ── Real WebGPU implementation ──────────────────────────────────

const PANEL_BG: RGBA = [0.10, 0.11, 0.13, 0.92]
const GLASS_BG: RGBA = [0.12, 0.14, 0.18, 0.55]

export class WebGPUImmediateUI implements ImmediateUI {
  private primitives: PrimitiveRenderer
  private text_renderer: TextRenderer
  private theme: Theme
  private stack: BoxFrame[] = []
  private frame_viewport: FrameViewport = { width: 1, height: 1 }
  /** True between begin_frame and end_frame. */
  private active = false

  constructor(gpu: GPUContext, theme: Theme = DEFAULT_THEME) {
    this.primitives = createPrimitiveRenderer(gpu)
    this.text_renderer = createTextRenderer(gpu)
    this.theme = theme
  }

  // Expose the text renderer so scaffolds can load_atlas externally.
  get text_sub(): TextRenderer { return this.text_renderer }

  begin_frame(pass: GPURenderPassEncoder, viewport: FrameViewport): void {
    this.frame_viewport = viewport
    this.stack.length = 0
    // Seed with a root frame spanning the viewport.
    this.stack.push(this.make_frame(0, 0, viewport.width, viewport.height, 'column', 0, 0, 0))
    this.primitives.begin(pass, viewport)
    this.text_renderer.begin(pass, viewport)
    this.active = true
  }

  begin_box(d?: BoxDirective): void {
    if (!this.active) return
    const parent = this.stack[this.stack.length - 1]

    const layout = d?.layout ?? {}
    const style = d?.style ?? {}

    const w = layout.width  === undefined ? parent.width  - (parent.cursor_x - parent.x)
                                          : this.resolve_size(layout.width, parent.width)
    const h = layout.height === undefined ? 0  // grown by children
                                          : this.resolve_size(layout.height, parent.height)

    const x = parent.cursor_x
    const y = parent.cursor_y

    // Background rect if any.
    if (style.bg && style.bg !== 'none') {
      const bg = this.resolve_bg(style.bg)
      const radius = style.rounded ? resolveRadius(style.rounded, this.theme) : 0
      const rect_style: RectStyle = { fill: bg, radius }
      if (style.border && style.border !== 'none') {
        rect_style.border = resolveColor(style.border, this.theme)
        rect_style.border_width = style.border_width ?? 1
      }
      // Deferred: can't know height until children land; for scaffold,
      // draw a placeholder with current-height. A proper retained-mode
      // pass would compute sizes first then draw. TODO when flex lands.
      this.primitives.rect(x, y, w, h || 1, rect_style)
    }

    const gap = layout.gap ? this.resolve_size(layout.gap, parent.width) : 0
    const padding = this.resolve_padding(layout.padding, parent.width)

    this.stack.push(this.make_frame(
      x + padding.left,
      y + padding.top,
      w - padding.left - padding.right,
      h - padding.top - padding.bottom,
      layout.direction ?? 'column',
      gap,
      padding.top,
      padding.left,
      d?.id,
    ))
  }

  end_box(): void {
    if (this.stack.length <= 1) return  // never pop the root frame
    const popped = this.stack.pop()!
    const parent = this.stack[this.stack.length - 1]
    // Advance parent cursor past this box in its flow direction.
    if (parent.direction === 'column') {
      const consumed_h = popped.cursor_y - popped.y
      parent.cursor_y += consumed_h + parent.gap
    } else {
      const consumed_w = popped.cursor_x - popped.x
      parent.cursor_x += consumed_w + parent.gap
    }
  }

  button(label: string, d?: ButtonDirective): boolean {
    if (!this.active) return false
    const frame = this.stack[this.stack.length - 1]
    const size_px = d?.size ? resolveSize(d.size, this.theme) : 16
    const padding_y = size_px * 0.4
    const padding_x = size_px * 0.8
    const bg = d?.color ? resolveColor(d.color, this.theme)
                        : resolveColor('primary', this.theme)
    const fg = resolveColor('fg', this.theme)
    const measured = this.text_renderer.measure(label, { color: fg, size: size_px })
    const w = d?.width ?? measured.width + padding_x * 2
    const h = measured.height + padding_y * 2

    const variant = d?.variant ?? 'solid'
    const is_ghost   = variant === 'ghost'
    const is_outline = variant === 'outline'
    const is_link    = variant === 'link'
    const fill: RGBA = is_ghost || is_outline || is_link ? [0, 0, 0, 0] : bg

    if (!is_link) {
      this.primitives.rounded_rect(frame.cursor_x, frame.cursor_y, w, h, 4, {
        fill,
        border: is_outline ? bg : undefined,
        border_width: is_outline ? 1 : 0,
      })
    }
    this.text_renderer.draw(label, [
      frame.cursor_x + padding_x,
      frame.cursor_y + padding_y,
    ], { color: is_link ? bg : fg, size: size_px })

    this.advance_cursor(frame, w, h)
    // TODO: wire up input system to detect click-within-rect this frame.
    return false
  }

  progress(value: number, max = 1, d?: ProgressDirective): void {
    if (!this.active) return
    const frame = this.stack[this.stack.length - 1]
    const size_px = d?.size ? resolveSize(d.size, this.theme) : 10
    const w = d?.width ?? Math.min(200, frame.width)
    const h = size_px
    const track_color: RGBA = [0.2, 0.22, 0.28, 1.0]
    const fill_color = d?.color ? resolveColor(d.color, this.theme)
                                : resolveColor('primary', this.theme)
    const frac = Math.max(0, Math.min(1, value / Math.max(max, 1e-6)))

    this.primitives.rounded_rect(frame.cursor_x, frame.cursor_y, w, h, h / 2, {
      fill: track_color,
    })
    if (frac > 0) {
      this.primitives.rounded_rect(frame.cursor_x, frame.cursor_y, w * frac, h, h / 2, {
        fill: fill_color,
      })
    }
    this.advance_cursor(frame, w, h)
  }

  text(content: string, d?: UITextStyle): void {
    if (!this.active) return
    const frame = this.stack[this.stack.length - 1]
    const size_px = typeof d?.size === 'number'
      ? d.size
      : resolveSize((d?.size ?? 'md') as SizeToken, this.theme)
    const color = d?.color ? resolveColor(d.color, this.theme)
                           : resolveColor('fg', this.theme)
    const measured = this.text_renderer.measure(content, {
      color, size: size_px, atlas: d?.atlas,
    })
    this.text_renderer.draw(content, [frame.cursor_x, frame.cursor_y], {
      color, size: size_px, atlas: d?.atlas,
    })
    this.advance_cursor(frame, measured.width, measured.height)
  }

  icon(name: string, d?: IconDirective): void {
    if (!this.active) return
    const frame = this.stack[this.stack.length - 1]
    const size_px = typeof d?.size === 'number'
      ? d.size
      : resolveSize((d?.size ?? 'md') as SizeToken, this.theme)
    // TODO: icon atlas system. For scaffold, draw a placeholder square.
    const color = d?.color ? resolveColor(d.color, this.theme)
                           : resolveColor('muted', this.theme)
    this.primitives.rounded_rect(frame.cursor_x, frame.cursor_y, size_px, size_px, 2, {
      fill: color,
    })
    this.advance_cursor(frame, size_px, size_px)
    // Silence unused-param warning; kept for future atlas lookup.
    void name
  }

  spacer(size = 8): void {
    const frame = this.stack[this.stack.length - 1]
    if (frame.direction === 'column') {
      frame.cursor_y += size
    } else {
      frame.cursor_x += size
    }
  }

  end_frame(): void {
    this.primitives.end()
    this.text_renderer.end()
    this.stack.length = 0
    this.active = false
  }

  destroy(): void {
    this.primitives.destroy()
    this.text_renderer.destroy()
  }

  // ── helpers ───────────────────────────────────────────────────

  private make_frame(
    x: number, y: number, w: number, h: number,
    direction: 'row' | 'column',
    gap: number, padding_top: number, padding_left: number,
    id?: string,
  ): BoxFrame {
    return {
      x, y, width: w, height: h,
      cursor_x: x, cursor_y: y,
      direction, gap, padding_top, padding_left, id,
    }
  }

  private advance_cursor(frame: BoxFrame, w: number, h: number): void {
    if (frame.direction === 'column') {
      frame.cursor_y += h + frame.gap
    } else {
      frame.cursor_x += w + frame.gap
    }
  }

  private resolve_size(size: number | string, parent_dim: number): number {
    if (typeof size === 'number') return size
    if (size === 'fill' || size === 'auto') return parent_dim
    if (typeof size === 'string' && size.endsWith('%')) {
      return (parseFloat(size.slice(0, -1)) / 100) * parent_dim
    }
    return resolveSize(size as SizeToken, this.theme)
  }

  private resolve_padding(
    padding: Layout['padding'],
    parent_dim: number,
  ): { top: number; right: number; bottom: number; left: number } {
    if (padding === undefined) return { top: 0, right: 0, bottom: 0, left: 0 }
    if (Array.isArray(padding)) {
      return {
        top:    this.resolve_size(padding[0] as number | string, parent_dim),
        right:  this.resolve_size(padding[1] as number | string, parent_dim),
        bottom: this.resolve_size(padding[2] as number | string, parent_dim),
        left:   this.resolve_size(padding[3] as number | string, parent_dim),
      }
    }
    const v = this.resolve_size(padding as number | string, parent_dim)
    return { top: v, right: v, bottom: v, left: v }
  }

  private resolve_bg(bg: NonNullable<BoxStyle['bg']>): RGBA {
    if (bg === 'panel') return PANEL_BG
    if (bg === 'glass') return GLASS_BG
    if (bg === 'none') return [0, 0, 0, 0]
    return resolveColor(bg, this.theme)
  }

  private unused_anchor(_a: Anchor): void { /* silence import */ }
}

// ── Factory ─────────────────────────────────────────────────────

export function createImmediateUI(gpu: GPUContext, theme?: Theme): ImmediateUI {
  return new WebGPUImmediateUI(gpu, theme)
}

export function createStubImmediateUI(gpu?: GPUContext, theme?: Theme): ImmediateUI {
  return new StubImmediateUI(gpu, theme)
}

// ── Anchor import guard ─────────────────────────────────────────
// Imported above for use in future anchored overlays (HUD). Keep the
// symbol live so tree-shakers don't drop the layout module's Anchor
// type from callers that depend on ImmediateUI's re-exports.
export type { Anchor }
