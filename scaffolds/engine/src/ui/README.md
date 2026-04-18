# UI — WebGPU-native declarative UI subsystem

Current state: **text rendering scaffold only**. This directory is
the foundation for the full UI framework; the other instance extends
it per the architecture in
`ark/tsunami/design/action_blocks/ui_framework/attempts/attempt_001.md`.

## What's here today

| File | Status | Notes |
|---|---|---|
| `text.ts` | **interface-stable, impl-stubbed** | `TextRenderer` public interface + `StubTextRenderer` placeholder. Real MSDF-variant impl (JB's) slots in without changing consumers. |
| `index.ts` | stable | Barrel export |
| `README.md` | this file | Onboarding |

## What's next (other instance's scope)

Per `ui_framework/attempts/attempt_001.md`:

1. **Declarative `ComponentDef` spec** — framework-neutral UI
   vocabulary (Box, Text, Button, Card, HUD, Menu, DialogTree, ...).
   Lives at `ark/scaffolds/_shared/ui-spec/` (shared between web and
   game scaffolds).
2. **WebGPU compiler** — `ComponentDef` → immediate-mode UI calls.
   Lives at `scaffolds/engine/src/ui/webgpu_compiler.ts`.
3. **Layout engine** — flex-like via Yoga or custom. Lives at
   `scaffolds/engine/src/ui/layout.ts`.
4. **Quad batcher + style renderer** — rect/rounded-rect/border
   drawing. Lives at `scaffolds/engine/src/ui/primitives.ts`.
5. **Theme** — token-to-value resolver (color, size, radius).
   Lives at `scaffolds/engine/src/ui/theme.ts`.
6. **Component library** — widgets that compose the above into
   Button, Card, ProgressBar, Dialog, etc. Lives at
   `scaffolds/engine/src/ui/components/`.
7. **Action-blocks UI-mechanic lowering** — seven UI-space mechanics
   (HUD, Menu, Dialog, Tutorial, Shop, InventoryPanel, hotspot menu)
   compile to ComponentDef subtrees. Lives at
   `engine/src/design/mechanics/`.

## Contract with the text renderer

Consumers import `TextRenderer` and call `createTextRenderer(gpu)`.
The stub's `measure` returns approximate pixel dimensions (rough
0.55em-per-glyph heuristic) so layout engines produce plausible
bounds even without real text drawing. When the MSDF renderer lands,
the factory flips — zero consumer changes.

## For the extending instance

Read, in order:

1. This README
2. `ui_framework/attempts/attempt_001.md` (full architecture)
3. `text.ts` interface (stable — extend but don't break)
4. `ark/scaffolds/engine/tools/sprite_pipeline.py` (reference for the
   sibling sprite extension; same sort of extension shape)

The text-rendering slot exists so the full UI framework can be built
around it without waiting for the MSDF implementation. Treat
`TextRenderer` as the canonical contract; if JB's real implementation
needs interface changes, flag them in
`ui_framework/observations/note_NNN.md` before landing.
