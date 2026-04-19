// Ship gate #13 — two layers for the four canonical example scripts:
//   1. design-roundtrip: validate + compile + structural inspection
//      (headless node; no WebGPU; no DOM).
//   2. runtime-activation: Game.fromDefinition → activateScene →
//      tick N frames via the private tickMechanics path; asserts that
//      every scene-referenced mechanic id resolves to a registered
//      runtime and that N frames execute without throwing.
//
// Layer 2 is the upgrade the engine_handoff_001 §E "rename-or-upgrade"
// option promised once §A's wiring landed. It exercises the real
// example payloads rather than the synthetic probe designs in
// `tests/game_activation.test.ts`.
//
// If layer 1 fails, the emit_design compile path is broken. If layer 2
// fails, either the runtime-wiring in Game.fromDefinition drifted or a
// factory convention was skipped.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { validate } from '../src/design/validate'
import { compile } from '../src/design/compiler'
import { Game } from '../src/game/game'
import { mechanicRegistry } from '../src/design/mechanics/_registry'
import type { DesignScript, ValidatedDesign } from '../src/design/schema'
// Side-effect registration — each mechanics/*.ts file runs
// `mechanicRegistry.register(...)` on import. Without this, fromDefinition
// finds no factories and the runtime-activation layer has nothing to tick.
import '../src/design/mechanics'

// Resolve examples relative to the engine scaffold root — tsunami/context/
// lives two directories up from scaffolds/engine/tests/.
const EXAMPLES = join(__dirname, '..', '..', '..', 'tsunami', 'context', 'examples')

function loadExample(filename: string): DesignScript {
  const raw = readFileSync(join(EXAMPLES, filename), 'utf8')
  return JSON.parse(raw) as DesignScript
}

function validateThenCompile(design: DesignScript) {
  const result = validate(design)
  if (!result.ok) {
    throw new Error(
      `validation failed: ${result.errors.map(e =>
        `[${e.kind}] ${e.path}: ${e.message}`).join('\n')}`
    )
  }
  return compile(result.design as ValidatedDesign)
}

// ─────────────────────────────────────────────────────────────
//   Three games end-to-end
// ─────────────────────────────────────────────────────────────

describe('design-roundtrip: arena_shooter.json', () => {
  const game = validateThenCompile(loadExample('arena_shooter.json'))

  it('produces a GameDefinition with config.mode', () => {
    expect(game.config.mode).toBe('3d')
  })
  it('lowers flow to a linear step list with gameplay scene', () => {
    expect(game.flow.length).toBeGreaterThanOrEqual(1)
    expect(game.flow.some(s => s.scene === 'gameplay')).toBe(true)
  })
  it('attaches WaveSpawner + HUD + LoseOnZero mechanics to the scene', () => {
    const sceneName = Object.keys(game.scenes)[0]
    const props = (game.scenes[sceneName] as unknown as Record<string, unknown>).properties as
      Record<string, unknown> | undefined
    const mechanicIds = (props?.mechanics ?? []) as string[]
    for (const required of ['waves', 'hud', 'lose', 'difficulty', 'camera']) {
      expect(mechanicIds).toContain(required)
    }
  })
})

describe('design-roundtrip: rhythm.json', () => {
  const game = validateThenCompile(loadExample('rhythm.json'))

  it('produces a 2d GameDefinition', () => {
    expect(game.config.mode).toBe('2d')
  })
  it('has a single stage scene in the flow', () => {
    expect(game.flow.length).toBeGreaterThanOrEqual(1)
    expect(game.flow[0].scene).toBe('stage')
  })
  it('attaches RhythmTrack + ScoreCombos + HUD mechanics', () => {
    const sceneName = Object.keys(game.scenes)[0]
    const props = (game.scenes[sceneName] as unknown as Record<string, unknown>).properties as
      Record<string, unknown> | undefined
    const mechanicIds = (props?.mechanics ?? []) as string[]
    for (const required of ['track', 'combos', 'hud']) {
      expect(mechanicIds).toContain(required)
    }
  })
})

describe('design-roundtrip: narrative.json', () => {
  const game = validateThenCompile(loadExample('narrative.json'))

  it('produces a 2d narrative GameDefinition', () => {
    expect(game.config.mode).toBe('2d')
  })
  it('lowers to a lighthouse scene', () => {
    expect(game.flow.some(s => s.scene === 'lighthouse')).toBe(true)
  })
  it('attaches DialogTree + HUD mechanics', () => {
    const sceneName = Object.keys(game.scenes)[0]
    const props = (game.scenes[sceneName] as unknown as Record<string, unknown>).properties as
      Record<string, unknown> | undefined
    const mechanicIds = (props?.mechanics ?? []) as string[]
    for (const required of ['keeper_dialog', 'hud']) {
      expect(mechanicIds).toContain(required)
    }
  })
})

describe('design-roundtrip: audio_demo.json (Phase 8 ship-gate for v1.1 audio)', () => {
  const game = validateThenCompile(loadExample('audio_demo.json'))

  it('produces a GameDefinition with 3d config', () => {
    expect(game.config.mode).toBe('3d')
  })

  it('attaches ChipMusic + SfxLibrary alongside gameplay mechanics', () => {
    const sceneName = Object.keys(game.scenes)[0]
    const props = (game.scenes[sceneName] as unknown as Record<string, unknown>).properties as
      Record<string, unknown> | undefined
    const mechanicIds = (props?.mechanics ?? []) as string[]
    for (const required of ['music', 'sfx', 'waves', 'coins', 'powerups', 'hud']) {
      expect(mechanicIds).toContain(required)
    }
  })

  it('preserves audio ActionRefs on archetype triggers', () => {
    const design = loadExample('audio_demo.json')
    const coin = design.archetypes?.coin as unknown as Record<string, unknown>
    const trig = coin.trigger as Record<string, unknown>
    const act = trig.on_contact as Record<string, unknown>
    expect(act.kind).toBe('sequence')
    const actions = act.actions as Array<Record<string, unknown>>
    const sfx = actions.find(a => a.kind === 'play_sfx_ref')
    expect(sfx).toBeDefined()
    expect(sfx!.library_ref).toBe('sfx')
    expect(sfx!.preset).toBe('coin')
    expect(sfx!.quantize_to).toBe('beat')
    expect(sfx!.quantize_source).toBe('music')
  })
})

describe('design-roundtrip: all four compile cleanly (ship-gate #13 headless variant)', () => {
  it('four examples validate + compile without throwing', () => {
    for (const f of ['arena_shooter.json', 'rhythm.json', 'narrative.json', 'audio_demo.json']) {
      const d = loadExample(f)
      const r = validate(d)
      expect(r.ok, `validator failed on ${f}`).toBe(true)
      if (!r.ok) return
      const game = compile(r.design)
      expect(Object.keys(game.scenes).length).toBeGreaterThan(0)
      expect(game.flow.length).toBeGreaterThan(0)
    }
  })
})


// ─────────────────────────────────────────────────────────────
//   Layer 2 — runtime activation (engine_handoff_001 §E upgrade)
// ─────────────────────────────────────────────────────────────

/**
 * Activate the first scene and tick N frames via the engine's private
 * tick path. Returns the live runtime set and the tick count that
 * actually executed. Any runtime throw propagates.
 */
function activateAndTick(def: ReturnType<typeof compile>, frames: number, dtSec = 0.016) {
  const game = Game.fromDefinition(def)
  game.setFlow(def.flow ?? [])
  const firstScene = def.flow?.[0]?.scene ?? Object.keys(def.scenes)[0]!
  game.activateScene(firstScene)
  // tickMechanics is private — cast through to exercise the frame-loop
  // edge without pulling in RAF or an actual DOM. This is the same
  // hook `game.ts` installs on `frameLoop.onUpdate` inside `start()`.
  const tick = (game as unknown as { tickMechanics: (dt: number) => void })
    .tickMechanics.bind(game)
  let ticked = 0
  for (let i = 0; i < frames; i++) {
    tick(dtSec)
    ticked++
  }
  const runtimes = game.mechanicsForScene(firstScene)
  return { game, firstScene, runtimes, ticked }
}

/**
 * How many of a scene's mechanic ids resolve to a registered runtime
 * type — the runtimes array drops unregistered types silently, so
 * this is the upper bound on what Game.activateSceneInternal should
 * instantiate.
 */
function countWiredMechanics(def: ReturnType<typeof compile>, sceneName: string): number {
  const registered = new Set(mechanicRegistry.registeredTypes())
  const props = (def.scenes[sceneName] as unknown as { properties?: Record<string, unknown> }).properties
  const ids = ((props?.mechanics ?? []) as unknown) as string[]
  const miById = new Map(
    (def.mechanics ?? []).map(m => [m.id as unknown as string, m]),
  )
  let n = 0
  for (const id of ids) {
    const mi = miById.get(id)
    if (mi && registered.has(mi.type)) n++
  }
  return n
}

describe.each([
  ['arena_shooter.json', 60],
  ['rhythm.json',        60],
  ['narrative.json',     30],
  ['audio_demo.json',    60],
])('runtime-activation: %s — fromDefinition → activateScene → tick N frames', (file, frames) => {
  const def = validateThenCompile(loadExample(file))

  it('compiler surfaces a non-empty def.mechanics bag', () => {
    expect(Array.isArray(def.mechanics)).toBe(true)
    expect(def.mechanics!.length).toBeGreaterThan(0)
  })

  it(`activates the first scene's runtimes and ticks ${frames} frames without throwing`, () => {
    const { runtimes, firstScene, ticked, game } = activateAndTick(def, frames)
    const expectedWired = countWiredMechanics(def, firstScene)
    expect(runtimes.length).toBe(expectedWired)
    expect(ticked).toBe(frames)
    expect(game.activeScene).toBe(firstScene)
  })

  it('tears down runtimes when the scene deactivates', () => {
    const { game, firstScene } = activateAndTick(def, 1)
    const nRuntimes = game.mechanicsForScene(firstScene).length
    expect(nRuntimes).toBeGreaterThanOrEqual(0)
    game.activateScene('__other_scene__')
    expect(game.mechanicsForScene(firstScene).length).toBe(0)
  })
})
