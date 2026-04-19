/**
 * Game scaffold entry point — engine-only, design-script driven.
 *
 * engine_handoff_001 §B — replaces the prior auto-mount-React shim with
 * a deterministic flow:
 *   1. Initialize WebGPU on the #game canvas.
 *   2. Fetch /game_definition.json (produced by Tsunami's
 *      `emit_design` tool, deposited under public/).
 *   3. Game.fromDefinition(def) → activateScene(flow[0].scene) → start().
 *
 * React is gone. Web-app scaffolds keep React; this game scaffold is
 * engine-only. If a gamedev model wants to override the entry point, it
 * writes a replacement main.ts — the shim-detect pattern is retired.
 *
 * Any failure (missing WebGPU, missing game_definition.json, invalid
 * design) renders an actionable overlay instead of a blank canvas.
 */

import { Game } from '@engine/game/game'
import { initGPU } from '@engine/renderer/gpu'
import type { GameDefinition } from '@engine/game/game'
// Side-effect registration: importing the mechanics barrel runs each
// `mechanicRegistry.register(...)` side-effect. Without this, `Game`
// can't build runtimes for any type.
import '@engine/design/mechanics'

// ─────────────────────────────────────────────────────────────
//   Error overlay
// ─────────────────────────────────────────────────────────────

function showFatal(title: string, detail: string, hint?: string): void {
  const existing = document.getElementById('fatal-overlay')
  if (existing) existing.remove()
  const panel = document.createElement('div')
  panel.id = 'fatal-overlay'
  panel.style.cssText = [
    'position:fixed', 'inset:0',
    'display:flex', 'flex-direction:column',
    'align-items:center', 'justify-content:center',
    'padding:32px', 'z-index:100',
    'background:rgba(10,10,26,0.96)',
    'color:#e2e8f0', 'font-family:monospace', 'font-size:14px',
    'gap:12px', 'text-align:center',
  ].join(';')
  const h = document.createElement('div')
  h.style.cssText = 'font-size:20px;color:#f87171'
  h.textContent = title
  panel.appendChild(h)
  const d = document.createElement('pre')
  d.style.cssText = 'max-width:640px;white-space:pre-wrap;color:#cbd5e1;margin:0'
  d.textContent = detail
  panel.appendChild(d)
  if (hint) {
    const hHint = document.createElement('div')
    hHint.style.cssText = 'color:#94a3b8;max-width:640px'
    hHint.textContent = hint
    panel.appendChild(hHint)
  }
  document.body.appendChild(panel)
}

// ─────────────────────────────────────────────────────────────
//   Bootstrap
// ─────────────────────────────────────────────────────────────

async function bootstrap(): Promise<void> {
  const canvas = document.getElementById('game') as HTMLCanvasElement | null
  if (!canvas) {
    showFatal(
      'Canvas missing',
      'The scaffold expects a <canvas id="game"> in index.html.',
    )
    return
  }
  // Pixel-matched backing store — CSS sizes canvas to viewport; pixel
  // buffer matches devicePixelRatio × CSS pixels.
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(canvas.clientWidth * dpr))
  canvas.height = Math.max(1, Math.floor(canvas.clientHeight * dpr))

  // 1. Initialize WebGPU. Fatal if unsupported / no adapter / context fails.
  try {
    await initGPU(canvas)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    showFatal(
      'WebGPU init failed',
      msg,
      'This build requires a browser with WebGPU enabled (Chrome 113+, ' +
      'Edge 113+, or Firefox Nightly with `dom.webgpu.enabled`). ' +
      'Try a different browser or device.',
    )
    return
  }

  // 2. Fetch the design deliverable. The `emit_design` tool writes
  //    `game_definition.json` under deliverables/<project>/public/, which
  //    Vite serves at the site root.
  let def: GameDefinition
  try {
    const res = await fetch('/game_definition.json', { cache: 'no-store' })
    if (!res.ok) {
      showFatal(
        'game_definition.json missing',
        `HTTP ${res.status} when fetching /game_definition.json.`,
        'Run `emit_design` from Tsunami (or run `npm run prebuild` with ' +
        'an assets manifest present) to deposit the file under public/.',
      )
      return
    }
    def = (await res.json()) as GameDefinition
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    showFatal(
      'Failed to load game_definition.json',
      msg,
      'Check that public/game_definition.json exists and is valid JSON.',
    )
    return
  }

  // 3. Build Game + register scenes + activate first scene + start.
  let game: Game
  try {
    game = Game.fromDefinition(def)
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    showFatal(
      'Game.fromDefinition() threw',
      msg,
      'The GameDefinition shape is invalid. Re-run `emit_design` to ' +
      'regenerate from a validated DesignScript.',
    )
    return
  }

  // setFlow wires SceneBuilders into the SceneManager. Pass the
  // compiled flow from def; fall back to an empty list when the design
  // has no explicit flow (single-scene games).
  game.setFlow(def.flow ?? [])

  const firstScene = def.flow?.[0]?.scene ?? Object.keys(def.scenes)[0]
  if (firstScene) game.activateScene(firstScene)

  try {
    await game.start()
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    showFatal(
      'Game.start() threw',
      msg,
      'Frame loop or flow initialization failed. See console for the full stack.',
    )
    return
  }

  // Expose for devtools inspection when not in production.
  if (import.meta.env?.MODE !== 'production') {
    ;(window as unknown as Record<string, unknown>).__game = game
    ;(window as unknown as Record<string, unknown>).__def = def
  }
}

void bootstrap()
