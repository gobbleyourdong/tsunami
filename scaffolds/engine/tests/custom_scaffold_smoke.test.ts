/**
 * Phase 5 smoke test — `scaffolds/gamedev/custom/` scaffold boots
 * cleanly and data files parse.
 *
 * Verifies:
 * - package.json points at the engine via file: link
 * - tsconfig has @engine alias
 * - vite.config resolves @engine/*
 * - index.html mounts a canvas
 * - data/*.json all parse
 * - src/main.ts imports resolve (syntactic check)
 * - src/scenes/MainScene.ts exports the expected class
 */

import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const SCAFFOLD = join(__dirname, '..', '..', 'gamedev', 'custom')

function read(rel: string): string {
  return readFileSync(join(SCAFFOLD, rel), 'utf8')
}
function readJSON(rel: string): any {
  return JSON.parse(read(rel))
}

describe('Phase 5 — custom scaffold smoke', () => {
  it('scaffold directory exists', () => {
    expect(existsSync(SCAFFOLD)).toBe(true)
  })

  it('package.json declares engine dep via file: link', () => {
    const pkg = readJSON('package.json')
    expect(pkg.name).toBe('gamedev-custom-scaffold')
    expect(pkg.dependencies?.engine).toMatch(/^file:/)
    expect(pkg.scripts?.dev).toBe('vite')
  })

  it('tsconfig.json has @engine path alias', () => {
    const tsc = readJSON('tsconfig.json')
    expect(tsc.compilerOptions?.paths?.['@engine']).toBeDefined()
    expect(tsc.compilerOptions?.paths?.['@engine/*']).toBeDefined()
  })

  it('vite.config.ts references @engine resolution', () => {
    const vite = read('vite.config.ts')
    expect(vite).toContain('@engine')
    expect(vite).toContain('defineConfig')
  })

  it('index.html mounts #game-canvas and loads /src/main.ts', () => {
    const html = read('index.html')
    expect(html).toContain('id="game-canvas"')
    expect(html).toContain('/src/main.ts')
  })

  it('src/main.ts imports from @engine/mechanics and MainScene', () => {
    const main = read('src/main.ts')
    expect(main).toContain('@engine/mechanics')
    expect(main).toContain('MainScene')
    expect(main).toContain('game-canvas')
  })

  it('src/scenes/MainScene.ts exports the MainScene class', () => {
    const scene = read('src/scenes/MainScene.ts')
    expect(scene).toContain('export class MainScene')
    expect(scene).toContain('setup()')
    expect(scene).toContain('teardown()')
    expect(scene).toContain('mountMechanic')
  })

  it('data/config.json has required top-level keys', () => {
    const cfg = readJSON('data/config.json')
    expect(cfg.title).toBeDefined()
    expect(cfg.mode).toMatch(/^(2d|3d)$/)
    expect(typeof cfg.width).toBe('number')
    expect(typeof cfg.height).toBe('number')
    expect(cfg.starting_scene).toBeDefined()
  })

  it('data/rules.json has match_format + win_condition', () => {
    const rules = readJSON('data/rules.json')
    expect(rules.match_format).toBeDefined()
    expect(rules.win_condition).toBeDefined()
  })

  it('data/entities.json parses as array with at least one example', () => {
    const ents = readJSON('data/entities.json')
    expect(Array.isArray(ents)).toBe(true)
    expect(ents.length).toBeGreaterThanOrEqual(1)
    expect(ents[0].id).toBeDefined()
  })

  it('README.md documents all three customization paths', () => {
    const readme = read('README.md')
    expect(readme).toContain('data/*.json')
    expect(readme).toContain('MainScene')
    expect(readme).toContain('main.ts')
    // Points users at the mechanic catalog
    expect(readme).toContain('@engine/mechanics')
  })
})
