// Ship gate #13 — three end-to-end examples: validate + compile + structural
// inspect. Full 60s autoplay requires WebGPU + a browser harness, which
// lives in the vitest browser mode (slow; gated behind the
// `test:browser` script). This file runs headless in node and asserts
// the build path reaches a valid GameDefinition with expected scene +
// flow shapes for each of arena-shooter / rhythm / narrative.
//
// If any of these fail, the Tsunami emit_design loop is broken end-to-end.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { validate } from '../src/design/validate'
import { compile } from '../src/design/compiler'
import type { DesignScript, ValidatedDesign } from '../src/design/schema'

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

describe('e2e: arena_shooter.json', () => {
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

describe('e2e: rhythm.json', () => {
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

describe('e2e: narrative.json', () => {
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

describe('e2e: all three compile cleanly (ship-gate #13 headless variant)', () => {
  it('three examples validate + compile without throwing', () => {
    for (const f of ['arena_shooter.json', 'rhythm.json', 'narrative.json']) {
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
