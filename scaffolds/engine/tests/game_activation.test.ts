// engine_handoff_001 §A — mechanic-runtime activation tests.
//
// Asserts that Game.fromDefinition + activateScene actually instantiates
// runtimes via mechanicRegistry, ticks them per frame, and tears them
// down on scene transition. The older `design_e2e.test.ts` only exercises
// the compiler's output shape; this file checks the runtime edge the
// audit (engine_audit_001 item 2) flagged as dormant.
//
// When the compiler stops emitting `def.mechanics` OR the onSceneChange
// hook fails to fire OR a mechanic's runtime fails to tick, one of these
// expect() calls will trip and point at the missing edge.

import { describe, it, expect } from 'vitest'
import { Game } from '../src/game/game'
import { validate } from '../src/design/validate'
import { compile } from '../src/design/compiler'
import { mechanicRegistry } from '../src/design/mechanics/_registry'
import type { MechanicInstance, ValidatedDesign } from '../src/design/schema'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
// Side-effect register the mechanics so the registry knows about them.
import '../src/design/mechanics'

const EXAMPLES = join(__dirname, '..', '..', '..', 'tsunami', 'context', 'examples')

function compileExample(filename: string) {
  const raw = readFileSync(join(EXAMPLES, filename), 'utf8')
  const parsed = JSON.parse(raw)
  const r = validate(parsed)
  if (!r.ok) throw new Error(`validate failed on ${filename}: ${JSON.stringify(r.errors)}`)
  return compile(r.design as ValidatedDesign)
}

// ─────────────────────────────────────────────────────────────
// Plumbing: compiler must surface def.mechanics
// ─────────────────────────────────────────────────────────────

describe('GameDefinition.mechanics (compiler plumbing)', () => {
  it('surfaces the design.mechanics array on the compiled GameDefinition', () => {
    const def = compileExample('arena_shooter.json')
    expect(def.mechanics).toBeDefined()
    expect(Array.isArray(def.mechanics)).toBe(true)
    expect(def.mechanics!.length).toBeGreaterThan(0)
    // Every id referenced by scene.properties.mechanics must resolve
    // against def.mechanics by id.
    const miById = new Map(def.mechanics!.map(m => [m.id as unknown as string, m]))
    for (const [sceneName, sceneDef] of Object.entries(def.scenes)) {
      const props = (sceneDef as unknown as { properties?: Record<string, unknown> }).properties
      const ids = (props?.mechanics ?? []) as string[]
      for (const id of ids) {
        expect(
          miById.has(id),
          `scene '${sceneName}' references mechanic '${id}' not in def.mechanics`,
        ).toBe(true)
      }
    }
  })
})

// ─────────────────────────────────────────────────────────────
// Plumbing: runtimes instantiate + tick
// ─────────────────────────────────────────────────────────────

describe('Game.activateScene wires mechanicRegistry runtimes', () => {
  it('populates mechanicsForScene with runtimes for each id in scene.properties.mechanics', () => {
    const def = compileExample('arena_shooter.json')
    const game = Game.fromDefinition(def)
    const sceneName = def.flow[0]!.scene
    game.activateScene(sceneName)

    const runtimes = game.mechanicsForScene(sceneName)
    const expectedIds = (
      (def.scenes[sceneName] as unknown as { properties?: Record<string, unknown> })
        .properties?.mechanics ?? []
    ) as string[]

    // Each runtime should exist for a registered mechanic type. Runtimes
    // may be null when a mechanic type has no runtime registered yet;
    // registeredTypes() tells us which are wired today so we can assert
    // only against those.
    const wired = new Set(mechanicRegistry.registeredTypes())
    const expectedWiredIds = expectedIds.filter(id => {
      const mi = def.mechanics!.find(m => (m.id as unknown as string) === id)
      return mi && wired.has(mi.type)
    })
    expect(runtimes.length).toBe(expectedWiredIds.length)
  })

  it('ticks runtimes via the game-owned update path (init/update/dispose observed)', () => {
    let tickCount = 0
    let initCalled = 0
    let disposeCalled = 0
    mechanicRegistry.register('ProbeMechanic' as unknown as MechanicInstance['type'], (_instance, game) => {
      const rt = {
        init() { initCalled++ },
        update(dt: number) {
          tickCount++
          expect(dt).toBeGreaterThanOrEqual(0)
        },
        dispose() { disposeCalled++ },
      }
      rt.init(game)  // factory convention — see hud.ts/wave_spawner.ts/difficulty.ts
      return rt
    })

    const def = {
      config: {
        mode: '3d' as const, width: 640, height: 480, title: 't', pixelPerfect: false,
        camera: 'perspective' as const, gravity: [0, -9.81, 0] as [number, number, number],
        physicsRate: 60, antialias: true,
      },
      scenes: {
        main: {
          name: 'main', entities: [],
          properties: { mechanics: ['probe'] },
        } as unknown as import('../src/game/game').SceneDefinition,
      },
      flow: [{ scene: 'main' }],
      mechanics: [
        { id: 'probe', type: 'ProbeMechanic', params: {} } as unknown as MechanicInstance,
      ],
    }
    const game = Game.fromDefinition(def)
    game.activateScene('main')
    expect(initCalled).toBe(1)

    // Drive the per-frame tick by poking the private method. In prod,
    // start() wires frameLoop.onUpdate → tickMechanics; we exercise the
    // same edge without pulling in RAF.
    const tick = (game as unknown as { tickMechanics: (dt: number) => void })
      .tickMechanics.bind(game)
    tick(0.016)
    tick(0.016)
    tick(0.016)
    expect(tickCount).toBe(3)
    expect(disposeCalled).toBe(0)

    // Switch to a different scene — prior runtime should dispose.
    game.activateScene('other')
    expect(disposeCalled).toBe(1)
  })

  it('tears down runtimes when scene deactivates', () => {
    let disposeCalled = 0
    mechanicRegistry.register('TearProbe' as unknown as MechanicInstance['type'], () => ({
      init() {},
      update() {},
      dispose() { disposeCalled++ },
    }))

    const def = {
      config: {
        mode: '3d' as const, width: 640, height: 480, title: 't', pixelPerfect: false,
        camera: 'perspective' as const, gravity: [0, -9.81, 0] as [number, number, number],
        physicsRate: 60, antialias: true,
      },
      scenes: {
        a: {
          name: 'a', entities: [], properties: { mechanics: ['tp'] },
        } as unknown as import('../src/game/game').SceneDefinition,
        b: {
          name: 'b', entities: [], properties: { mechanics: [] },
        } as unknown as import('../src/game/game').SceneDefinition,
      },
      flow: [{ scene: 'a' }, { scene: 'b' }],
      mechanics: [
        { id: 'tp', type: 'TearProbe', params: {} } as unknown as MechanicInstance,
      ],
    }
    const game = Game.fromDefinition(def)
    game.activateScene('a')
    expect(disposeCalled).toBe(0)
    game.activateScene('b')
    expect(disposeCalled).toBe(1)
  })

  it('silently skips ids that reference unknown MechanicInstances', () => {
    const def = {
      config: {
        mode: '3d' as const, width: 640, height: 480, title: 't', pixelPerfect: false,
        camera: 'perspective' as const, gravity: [0, -9.81, 0] as [number, number, number],
        physicsRate: 60, antialias: true,
      },
      scenes: {
        main: {
          name: 'main', entities: [],
          properties: { mechanics: ['ghost', 'real'] },
        } as unknown as import('../src/game/game').SceneDefinition,
      },
      flow: [{ scene: 'main' }],
      mechanics: [
        // 'ghost' is omitted intentionally; 'real' is registered.
        { id: 'real', type: 'DummyProbe', params: {} } as unknown as MechanicInstance,
      ],
    }
    // Register the real one for this test only.
    mechanicRegistry.register('DummyProbe' as unknown as MechanicInstance['type'], () => ({
      init() {}, update() {}, dispose() {},
    }))

    const game = Game.fromDefinition(def)
    // Swallow the `console.warn` from the ghost-mechanic path so vitest
    // output stays clean. We still assert below that the single-runtime
    // case survived.
    const origWarn = console.warn
    console.warn = () => {}
    try {
      game.activateScene('main')
    } finally {
      console.warn = origWarn
    }
    const rts = game.mechanicsForScene('main')
    expect(rts.length).toBe(1)
  })
})
