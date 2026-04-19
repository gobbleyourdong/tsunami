# GAP — electron-app

## Purpose
Desktop app scaffold. Electron main + preload + renderer. Target:
file-based utilities, local media tools, tray apps.

## Wire state
- **Not routed.** No plan, no keyword hit.
- Zero deliveries.

## Numeric gap
- Delivery count: **0**.
- Target: **≥2 deliveries**.

## Structural blockers (known)
- Context isolation + contextBridge API — drones often try to access
  node APIs from renderer, which v-latest forbids.
- Packaging (electron-builder config) — irrelevant for dev-mode
  testing but required for real delivery.
- Vision gate: can screenshot the renderer via playwright's electron
  mode. Doable but new surface.

## Churn lever
1. Add `plan_scaffolds/electron-app.md` — sections: Main, Preload,
   Renderer, IPC, Build.
2. Pin context-isolation=true. Forbid `nodeIntegration: true` in
   the prompt.
3. Delivery gate: playwright.electron launches the app, screenshots
   the main window.
4. Ship: file browser, markdown editor, audio recorder.

## Out of scope
- Auto-updater (separate concern).
- Multi-window apps (start with one BrowserWindow).

## Test suite (inference-free)
Playwright electron mode. Parallel-safe — each instance spawns its
own electron process.

## Success signal
App launches, renderer shows expected UI, IPC round-trip between
preload and main works, no contextBridge exceptions.
