# UI — WebGPU-native declarative UI subsystem

Current state: **full scaffolding landed.** Sample Newton text renderer
shipped (fires 1–5, separate effort); UI framework scaffolded across
fires 1–7 (theme, layout, primitives, immediate-mode shell,
ComponentDef spec, WebGPU compiler, widget components, DOM compiler).

Full architectural spec:
`ark/tsunami/design/action_blocks/ui_framework/attempts/attempt_001.md`.

## What's here today

| File / dir | Status | Notes |
|---|---|---|
| `text.ts` + `text_shader.ts` | **shipped** | Sample Newton Hermite-atlas text renderer. Awaiting hardware validation (winding sign, AA band tuning). See in-file status header. |
| `theme.ts` | ✓ scaffold | Color / size / variant / border-radius / font-family tokens; `DEFAULT_THEME`; `resolveColor / resolveSize / resolveRadius / resolveFontFamily`; `extendTheme(overrides)`. |
| `layout.ts` | ✓ scaffold (stub engine) | `Layout`, `Size`, `Anchor` types; `computeLayout(root, viewport)` does vertical-stack; TODO: real flex (Yoga port or custom). |
| `primitives.ts` + `primitives_shader.ts` | ✓ scaffold | 2D quad batcher; rounded-rect SDF fragment; `rect / rounded_rect / border`. |
| `immediate.ts` | ✓ scaffold | ImGui-style shell: `begin_frame / begin_box / end_box / button / progress / text / icon / spacer / end_frame`. Stack-based cursor layout. Hit-testing TODO (needs input integration). |
| `component_def.ts` | ✓ scaffold | 25-kind discriminated union + `ValueRef<T>` + `MechanicRef` + `UIActionRef` + helpers. Types only. |
| `webgpu_compiler.ts` | ✓ scaffold | `compileToWebGPU(spec, ctx)` exhaustive switch over 25 cases; delegates 8 widgets to `components/`. |
| `components/` (8 files + barrel) | ✓ scaffold | `button / card / dialog / progress / input / hud / menu / dialog_tree` — each exports `render_<widget>(spec, ctx)`. |
| `dom_compiler.tsx` | ✓ scaffold | `compileToReact(spec, ctx): DomDescriptor` — framework-free descriptor; web scaffolds wrap via `React.createElement`. |
| `index.ts` | stable barrel | Single entry point for `import from '@engine'`. |

## Deferred to implementation pass

Called out in each file's status header:

- **Real flex layout engine** (Yoga port or custom 200-line flex) — replaces the vertical-stack stub in `layout.ts` / `immediate.ts`.
- **Hit-testing + click routing** — `ui.button()` returns `false` until input system is wired; see `immediate.ts` TODO.
- **Icon atlas** — `ui.icon()` draws placeholder rects; needs MSDF icon atlas via sprite pipeline.
- **Typewriter animation** in `DialogTree` — needs frame-time delta + char-reveal state.
- **Drop shadow + gradient** primitives — v1.2 in `primitives_shader.ts`.
- **React adapter** — lives in `scaffolds/_shared/ui-spec/` (to be created); walks `DomDescriptor` via `React.createElement` using scaffold's `components/ui` library.
- **Text renderer hardware validation** — winding sign, Newton convergence at cusps, AA band tuning, 60 FPS target. See `text.ts` status header.

## Contracts consumers depend on

From `@engine`:

- Types: `Theme`, `Layout`, `ComponentDef` (+ 25 sub-kinds), `MechanicRef`, `UIActionRef`, `DomDescriptor`, `RenderContext`, `DomRenderContext`.
- Runtime: `createTextRenderer`, `createPrimitiveRenderer`, `createImmediateUI`, `compileToWebGPU`, `compileToReact`.
- Tokens: `DEFAULT_THEME`, `extendTheme`.

All interfaces are stable; additive extensions only. Impl may flip (e.g. stub → real flex) without breaking consumers.

## Reading order (for future implementers)

1. This README
2. `ui_framework/attempts/attempt_001.md` — full architecture
3. `text.ts` — exemplar of the "interface + stub + real + factory" pattern
4. `index.ts` — status grid + export surface
5. Specific file's status header for the part you're working on

Every file lists a status header with `✓` / `TODO fire N` markers. Don't break interfaces; extend additively.
