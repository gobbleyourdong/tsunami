/**
 * UI theme — renderer-agnostic token resolution.
 *
 * Scaffolds reference colors / sizes / radii by TOKEN NAME, not raw
 * values. The theme resolves tokens at mount time. One theme per
 * scaffold; tokens are the same vocabulary across web and game.
 *
 * # Status
 *   Token types              ✓ scaffold
 *   Theme interface          ✓ scaffold
 *   DEFAULT_THEME             ✓ scaffold (neutral dark)
 *   resolve helpers           ✓ scaffold (direct lookup)
 *   Per-scaffold theme loader TODO — scaffold reads `theme.ts` at its
 *                              root to override DEFAULT_THEME
 *   CSS variable sync (DOM)   TODO — DOM renderer emits `--ui-color-…`
 *                              custom properties for Tailwind-free theming
 *
 * Follows `text.ts` scaffolding pattern: public types + interface +
 * stub/default values + factory helpers. No GPU dependency.
 */

// ── Token types ──────────────────────────────────────────────────

export type ColorToken =
  | 'default'  | 'primary' | 'secondary' | 'accent'
  | 'muted'    | 'danger'  | 'warning'   | 'success' | 'info'
  | 'fg'       | 'bg'       // baseline foreground / background

export type SizeToken = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'

export type VariantToken = 'solid' | 'outline' | 'ghost' | 'link'

export type BorderRadius = 'none' | SizeToken | 'full'

export type FontFamilyToken = 'sans' | 'serif' | 'mono' | 'display'

// ── Theme ────────────────────────────────────────────────────────

export type RGBA = [number, number, number, number]

export interface Theme {
  /** Color tokens → RGBA 0..1. */
  colors: Record<ColorToken, RGBA>
  /** Size tokens → pixels. */
  sizes: Record<SizeToken, number>
  /** Border-radius tokens → pixels. */
  radii: Record<BorderRadius, number>
  /** Font family per token (CSS name for DOM; atlas name for WebGPU). */
  font_family: Record<FontFamilyToken, string>
  /** Base font size in pixels (md body text). */
  font_size_base: number
  /** Line-height multiplier applied to font size by default. */
  line_height_base: number
}

// ── Default theme ────────────────────────────────────────────────

export const DEFAULT_THEME: Theme = {
  colors: {
    default:   [0.10, 0.10, 0.11, 1.00],
    primary:   [0.23, 0.51, 0.96, 1.00],
    secondary: [0.55, 0.36, 0.96, 1.00],
    accent:    [0.96, 0.62, 0.04, 1.00],
    muted:     [0.42, 0.45, 0.50, 1.00],
    danger:    [0.94, 0.27, 0.27, 1.00],
    warning:   [0.98, 0.45, 0.09, 1.00],
    success:   [0.06, 0.73, 0.51, 1.00],
    info:      [0.02, 0.71, 0.83, 1.00],
    fg:        [0.95, 0.95, 0.97, 1.00],
    bg:        [0.06, 0.06, 0.08, 1.00],
  },
  sizes: {
    xs:  10,
    sm:  13,
    md:  16,
    lg:  20,
    xl:  28,
    '2xl': 40,
  },
  radii: {
    none: 0,
    xs: 2, sm: 4, md: 6, lg: 8, xl: 12, '2xl': 16,
    full: 9999,
  },
  font_family: {
    sans:    'regular',
    serif:   'regular',
    mono:    'regular',
    display: 'regular',
  },
  font_size_base: 16,
  line_height_base: 1.4,
}

// ── Resolver helpers ─────────────────────────────────────────────

/** Look up a color token in the theme, with a safe fallback. */
export function resolveColor(token: ColorToken, theme: Theme = DEFAULT_THEME): RGBA {
  return theme.colors[token] ?? theme.colors.default
}

/** Look up a size token; returns pixels. */
export function resolveSize(token: SizeToken, theme: Theme = DEFAULT_THEME): number {
  return theme.sizes[token] ?? theme.sizes.md
}

/** Look up a border-radius token; returns pixels. */
export function resolveRadius(token: BorderRadius, theme: Theme = DEFAULT_THEME): number {
  return theme.radii[token] ?? theme.radii.none
}

/** Look up a font-family token; returns the atlas name or CSS family. */
export function resolveFontFamily(
  token: FontFamilyToken,
  theme: Theme = DEFAULT_THEME,
): string {
  return theme.font_family[token] ?? theme.font_family.sans
}

// ── Theme extension — scaffold-friendly overrides ────────────────

/**
 * Produce a theme derived from DEFAULT_THEME with specific tokens
 * overridden. Intended for scaffold-level customization:
 *
 *   export const MY_SCAFFOLD_THEME = extendTheme({
 *     colors: { primary: [1, 0.4, 0.0, 1] },
 *     font_family: { sans: 'pixel_regular' },
 *   })
 */
export function extendTheme(overrides: Partial<{
  colors: Partial<Record<ColorToken, RGBA>>
  sizes: Partial<Record<SizeToken, number>>
  radii: Partial<Record<BorderRadius, number>>
  font_family: Partial<Record<FontFamilyToken, string>>
  font_size_base: number
  line_height_base: number
}>, base: Theme = DEFAULT_THEME): Theme {
  return {
    colors: { ...base.colors, ...(overrides.colors ?? {}) } as Record<ColorToken, RGBA>,
    sizes:  { ...base.sizes,  ...(overrides.sizes  ?? {}) } as Record<SizeToken, number>,
    radii:  { ...base.radii,  ...(overrides.radii  ?? {}) } as Record<BorderRadius, number>,
    font_family: {
      ...base.font_family,
      ...(overrides.font_family ?? {}),
    } as Record<FontFamilyToken, string>,
    font_size_base:   overrides.font_size_base   ?? base.font_size_base,
    line_height_base: overrides.line_height_base ?? base.line_height_base,
  }
}
