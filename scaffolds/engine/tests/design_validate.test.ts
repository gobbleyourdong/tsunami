// Ship-gate #12 — validator 5/5 good + 5/5 bad with correct error kinds.
//
// Good scripts exercise all 5 Phase 1 mechanics + a minimal no-mechanic
// case so the validator's empty-list path is covered. Bad scripts each
// trigger exactly one of the 12 ValidationError kinds; we pick 5 of the
// most common (the other 7 are covered by harness tests).
//
// Run: npm --prefix scaffolds/engine run test -- design_validate

import { describe, it, expect } from 'vitest'
import { validate } from '../src/design/validate'
import type { DesignScript } from '../src/design/schema'

// ─────────────────────────────────────────────────────────────
//   helpers
// ─────────────────────────────────────────────────────────────

function baseConfig(mode: '2d' | '3d' = '3d') {
  return {
    mode,
    camera: 'perspective' as const,
    gravity: [0, -9.81, 0] as [number, number, number],
    playfield: { kind: 'continuous' as const, arena: { shape: 'rect' as const, size: 20 } },
  }
}

function baseMeta(shape: 'action' | 'rhythm' | 'narrative_adjacent' | 'puzzle' | 'sandbox'
                   | 'skater' | 'fighter' | 'metroidvania' | 'maze_chase' = 'action') {
  return { title: 'Test', shape, vibe: ['test'] }
}

function baseFlow() {
  // Minimal single-scene flow — satisfies the schema without triggering
  // the linear/level_sequence branches.
  return { kind: 'scene' as const, name: 'main' as unknown as never }
}

function design(overrides: Partial<DesignScript>): DesignScript {
  return {
    meta: baseMeta(),
    config: baseConfig(),
    singletons: {},
    archetypes: {
      player: {
        mesh: 'capsule', controller: 'topdown',
        components: ['Health(100)', 'Score'], tags: ['player'],
      },
    },
    mechanics: [],
    flow: baseFlow(),
    ...overrides,
  } as DesignScript
}

// ─────────────────────────────────────────────────────────────
//   5 known-good scripts
// ─────────────────────────────────────────────────────────────

describe('validator: 5 known-good scripts', () => {
  it('good-1: minimal flow, one archetype, no mechanics', () => {
    const d = design({})
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-2: shooter with WaveSpawner + Difficulty + HUD + LoseOnZero', () => {
    const d = design({
      archetypes: {
        player: { mesh: 'capsule', controller: 'topdown',
                  components: ['Health(100)'], tags: ['player'] },
        enemy:  { mesh: 'sphere', ai: 'chase',
                  components: ['Health(10)'], tags: ['enemy'] },
      },
      mechanics: [
        { id: 'diff' as unknown as never, type: 'Difficulty',
          params: { drive: 'wave_index',
                    easy: { spawnRateMul: 0.6 }, hard: { spawnRateMul: 2.0 },
                    max_level: 10 } as unknown as never },
        { id: 'waves' as unknown as never, type: 'WaveSpawner',
          params: { archetype: 'enemy', difficulty_ref: 'diff' as unknown as never,
                    base_count: 3, rest_sec: 2, arena_radius: 10 } as unknown as never },
        { id: 'hud' as unknown as never, type: 'HUD',
          params: { fields: [{ archetype: 'player', component: 'Health' }],
                    layout: 'top' } as unknown as never },
        { id: 'lose' as unknown as never, type: 'LoseOnZero',
          params: { archetype: 'player', field: 'Health',
                    emit_condition: 'player_dead' as unknown as never } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-3: rhythm game with RhythmTrack', () => {
    const d = design({
      meta: baseMeta('rhythm'),
      archetypes: {
        player: { mesh: 'capsule', controller: 'none',
                  components: [], tags: ['player'] },
        beat: { mesh: 'sphere', controller: 'none',
                components: [], tags: ['beat'] },
      },
      mechanics: [
        { id: 'track' as unknown as never, type: 'RhythmTrack',
          params: { bpm: 128, audio_ref: 'music.ogg',
                    beat_spawn_archetype: 'beat' as unknown as never,
                    measure: { beats: 4, note_value: 4 },
                    hit_window_ms: 120 } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-4: narrative with DialogTree and set_flag action', () => {
    const d = design({
      meta: baseMeta('narrative_adjacent'),
      archetypes: {
        player: { mesh: 'capsule', controller: 'topdown',
                  components: [], tags: ['player'] },
        npc: { mesh: 'capsule', controller: 'none',
               components: [], tags: ['npc'] },
      },
      mechanics: [
        { id: 'chat' as unknown as never, type: 'DialogTree',
          params: {
            trigger_archetype: 'npc' as unknown as never,
            tree: { id: 'root', line: 'Hello.', choices: [
              { text: 'Hi', goto: 'end',
                effect: { kind: 'set_flag', world_flag: 'met_npc', value: true } },
            ] },
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-5: shmup with BulletPattern', () => {
    const d = design({
      meta: baseMeta('action'),
      archetypes: {
        player: { mesh: 'capsule', controller: 'topdown',
                  components: ['Health(100)'], tags: ['player'] },
        turret: { mesh: 'sphere', controller: 'none',
                  components: [], tags: ['enemy'] },
        bullet: { mesh: 'sphere', controller: 'none',
                  components: [], tags: ['bullet'] },
      },
      mechanics: [
        { id: 'shots' as unknown as never, type: 'BulletPattern',
          params: {
            emitter_archetype: 'turret' as unknown as never,
            patterns: [{
              name: 'ring', bullet_archetype: 'bullet' as unknown as never,
              layout: 'ring', layout_params: { count: 12, speed: 8 },
              duration_ms: 1200,
            }],
            sequence: 'round_robin',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })
})


// ─────────────────────────────────────────────────────────────
//   5 known-bad scripts — each triggers a specific error kind
// ─────────────────────────────────────────────────────────────

describe('validator: 5 known-bad scripts, correct error kinds', () => {
  it('bad-1: unknown_mechanic_type', () => {
    const d = design({
      mechanics: [
        { id: 'ghost' as unknown as never, type: 'NonExistentMechanic' as unknown as never,
          params: {} as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    const kinds = r.errors.map(e => e.kind)
    expect(kinds).toContain('unknown_mechanic_type')
  })

  it('bad-2: unknown_archetype_ref', () => {
    const d = design({
      mechanics: [
        { id: 'spawn' as unknown as never, type: 'WaveSpawner',
          params: { archetype: 'does_not_exist',
                    base_count: 1, rest_sec: 1, arena_radius: 5 } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    const kinds = r.errors.map(e => e.kind)
    expect(kinds).toContain('unknown_archetype_ref')
  })

  it('bad-3: duplicate_id', () => {
    const d = design({
      archetypes: {
        player: { mesh: 'capsule', controller: 'topdown',
                  components: [], tags: ['player'] },
        enemy: { mesh: 'sphere', controller: 'none',
                 components: [], tags: ['enemy'] },
      },
      mechanics: [
        { id: 'hud' as unknown as never, type: 'HUD',
          params: { fields: [] } as unknown as never },
        { id: 'hud' as unknown as never, type: 'LoseOnZero',
          params: { archetype: 'player', field: 'Health',
                    emit_condition: 'dead' as unknown as never } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    const kinds = r.errors.map(e => e.kind)
    expect(kinds).toContain('duplicate_id')
  })

  it('bad-4: component_parse', () => {
    const d = design({
      archetypes: {
        player: { mesh: 'capsule', controller: 'topdown',
                  // 'Health(100' — unterminated paren, doesn't match grammar
                  components: ['Health(100'], tags: ['player'] },
      },
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    const kinds = r.errors.map(e => e.kind)
    expect(kinds).toContain('component_parse')
  })

  it('bad-5: dangling_condition', () => {
    // flow.linear references a condition nothing emits.
    const d = design({
      flow: {
        kind: 'linear' as const,
        name: 'main' as unknown as never,
        steps: [{ scene: 'main' as unknown as never,
                  condition: 'never_emitted' as unknown as never }],
      } as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    const kinds = r.errors.map(e => e.kind)
    expect(kinds).toContain('dangling_condition')
  })
})
