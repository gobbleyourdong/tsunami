# React App Scaffold

Vite + React 19 + TypeScript. Deep atmospheric dark theme with Plus Jakarta Sans.

## Quick Start
Write your app in `src/App.tsx`. Import `./index.css` for the design system.
Build: `npx vite build`

## Design System

### Surface Hierarchy (use for depth)
- `bg-0` — deepest void (#08090d)
- `bg-1` — cards and panels (#111318)
- `bg-2` — elevated surfaces (#191c24)
- `bg-3` — popovers and dropdowns (#21252f)

### CSS Classes
| Category | Classes |
|----------|---------|
| **Layout** | `.container` `.container-sm` `.container-lg` `.flex` `.flex-col` `.flex-center` `.flex-between` `.flex-wrap` `.flex-1` |
| **Grid** | `.grid` `.grid-2` `.grid-3` `.grid-4` `.grid-auto` |
| **Spacing** | `.gap-1/2/3/4/6/8/12` `.mt-1/2/4/6/8/12` `.mb-1/2/4/6/8/12` `.p-2/4/6/8` |
| **Text** | `.text-center` `.text-right` `.text-muted` `.text-dim` `.text-accent` `.text-xs/sm/lg/xl/2xl` `.text-bold` `.text-semibold` `.truncate` |
| **Cards** | `.card` `.card.glass` (blur backdrop) `.card.glow` (accent border on hover) |
| **Buttons** | `button` (default) `button.primary` (gradient+glow) `button.ghost` `button.danger` |
| **Tags** | `.badge` `.badge.accent` `.badge.danger` `.badge.success` `.badge.warning` |
| **Misc** | `.avatar` `.status-dot.online/.offline/.busy` `.skeleton` `.toast` `.divider` |
| **Display** | `.bg-0/1/2/3` `.rounded` `.rounded-lg` `.overflow-hidden` `.relative` `.sticky` `.sr-only` |
| **Animation** | `.animate-in` `.animate-fade` `.animate-scale` `.delay-1/2/3/4/5` |

### CSS Variables (override in your components)
`--accent` `--accent-hover` `--accent-dim` `--danger` `--success` `--warning`
`--shadow-sm/md/lg/glow` `--radius/radius-lg/radius-xl`
`--duration-fast/normal/slow` `--ease-out-expo` `--ease-spring`

## Available UI Components (import from `./components/ui/ComponentName`)
| Component | What |
|-----------|------|
| Dialog | Modal with Escape close, blur backdrop, scale-in |
| Select | Styled select with label, focus glow |
| Skeleton | Loading placeholder (also `.skeleton` class), circle prop |
| Progress | Bar with gradient fill, striped variant, glow |
| Avatar | Circle with initials or image |
| Accordion | Expandable sections, single/multiple mode |
| Alert | Info/success/warning/error with icon, dismiss button |
| Tooltip | 4 positions, scale-in animation |
| Switch | Toggle with keyboard a11y, sm/md sizes, glow |
| Dropdown | Menu with dividers, danger items, left/right align |
| StarRating | Interactive star rating |
| GlowCard | Mouse-tracking glow card |
| Parallax | Scroll parallax wrapper |
| AnimatedCounter | Count-up animation on scroll |
| BeforeAfter | Slider image comparison |
| ColorPicker | Presets + native picker, click-outside close |
| Timeline | Vertical timeline with glowing dots |
| Kanban | Column board with card tags |
| AnnouncementBar | Sticky top bar |
| Marquee | Scrolling text |
| TypeWriter | Typing effect |
| GradientText | Gradient text, optional animation |
| ScrollReveal | Fade-in on scroll |
| Slideshow | Image carousel |

## Available Hooks (import from `./hooks`)
| Hook | What | Example |
|------|------|---------|
| useLocalStorage | Persist state to localStorage, syncs across tabs | `const [tasks, setTasks] = useLocalStorage<Task[]>("tasks", [])` |
| useDebounce | Debounce a value (e.g. search input) | `const debouncedQuery = useDebounce(query, 300)` |
| useMediaQuery | Reactive media query match | `const isDark = useMediaQuery("(prefers-color-scheme: dark)")` |
| useMobile | Reactive mobile viewport match | `const isMobile = useMobile()` |
| useInterval | Declarative setInterval (null to pause). Use for timers/pollers — NEVER roll raw setInterval+useRef | `useInterval(() => tick(), running ? 1000 : null)` |

**Prefer these hooks over rolling your own** — they handle cleanup, cross-tab sync, and stale-closure bugs correctly. Reach for `useLocalStorage` before writing `localStorage.getItem`, and `useInterval` before writing `setInterval` + `clearInterval` + `useRef`.

## Rules
- Don't overwrite `main.tsx`, `vite.config.ts`, or `index.css`
- Write your components in `src/components/`
- `App.tsx` is YOUR file — write the full app there
- React hooks (useState, useEffect, etc.) need explicit imports
- Use CSS classes from the design system — avoid inline styles for colors, spacing, backgrounds
