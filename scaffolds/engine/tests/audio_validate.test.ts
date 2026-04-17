// Phase 5 — audio v1.1 validator tests (ship-gate checks 2 & 3).
//
// Five known-good scripts validate clean; five malformed scripts each
// trigger exactly one of the six new audio error kinds:
//   unknown_sfx_preset / invalid_chiptune_track /
//   library_ref_not_sfx_library / unknown_mechanic_field /
//   invalid_quantize_source / overlay_condition_mismatch

import { describe, it, expect } from 'vitest'
import { validate } from '../src/design/validate'
import type { DesignScript, SfxrParams } from '../src/design/schema'


function baseConfig() {
  return {
    mode: '2d' as const,
    camera: 'orthographic' as const,
    gravity: [0, 0, 0] as [number, number, number],
    playfield: { kind: 'continuous' as const, arena: { shape: 'rect' as const, size: 16 } },
  }
}

function minimalSfxrParams(): SfxrParams {
  return {
    waveType: 'square',
    envelopeAttack: 0, envelopeSustain: 0.1, envelopePunch: 0.3, envelopeDecay: 0.2,
    baseFreq: 0.5, freqLimit: 0, freqRamp: 0, freqDeltaRamp: 0,
    vibratoStrength: 0, vibratoSpeed: 0,
    arpMod: 0, arpSpeed: 0,
    duty: 0.5, dutyRamp: 0, repeatSpeed: 0,
    flangerOffset: 0, flangerRamp: 0,
    lpFilterCutoff: 1, lpFilterCutoffRamp: 0, lpFilterResonance: 0,
    hpFilterCutoff: 0, hpFilterCutoffRamp: 0,
    masterVolume: 0.25, sampleRate: 44100, sampleSize: 16,
  }
}

function makeDesign(overrides: Partial<DesignScript>): DesignScript {
  return {
    meta: { title: 'Audio Test', shape: 'action', vibe: [] },
    config: baseConfig(),
    singletons: {},
    archetypes: {
      player: { mesh: 'capsule', controller: 'topdown',
                components: [], tags: ['player'] },
    },
    mechanics: [],
    flow: { kind: 'scene', name: 'main' as unknown as never },
    ...overrides,
  } as DesignScript
}


// ─────────────────────────────────────────────────────────────
//   5 known-good audio scripts
// ─────────────────────────────────────────────────────────────

describe('audio validator: 5 known-good scripts', () => {
  it('good-a1: ChipMusic with minimal base_track (numeric bpm)', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: {
              bpm: 128, loop: true, bars: 1,
              channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
            },
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-a2: SfxLibrary with 2 valid presets', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'sfx' as unknown as never, type: 'SfxLibrary',
          params: {
            sfx: {
              pickup: minimalSfxrParams(),
              laser: { ...minimalSfxrParams(), waveType: 'sawtooth' },
            },
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-a3: ChipMusic + SfxLibrary + play_sfx_ref ActionRef', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: { bpm: 120, loop: true, bars: 1,
                          channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] } },
            channel: 'music',
          } as unknown as never },
        { id: 'sfx' as unknown as never, type: 'SfxLibrary',
          params: { sfx: { coin: minimalSfxrParams() } } as unknown as never },
        { id: 'pickup_trigger' as unknown as never, type: 'HUD',
          params: { fields: [] } as unknown as never,
        },
      ] as unknown as never,
    })
    // Thread a play_sfx_ref via an archetype trigger.
    d.archetypes.coin = {
      mesh: 'sphere', controller: 'none', components: [], tags: ['pickup'],
      trigger: {
        kind: 'pickup', contact_side: 'any',
        on_contact: { kind: 'play_sfx_ref', library_ref: 'sfx' as unknown as never,
                      preset: 'coin' },
      },
    } as unknown as never
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-a4: ChipMusic with overlay_tracks + matching overlay_conditions', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: { bpm: 120, loop: true, bars: 1,
                          channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] } },
            overlay_tracks: [
              { bpm: 120, loop: true, bars: 1,
                channels: { triangle: [{ time: 0, note: 'G3', duration: 1 }] } },
              { bpm: 120, loop: true, bars: 1,
                channels: { noise: [{ time: 0, note: 'kick', duration: 0.25 }] } },
            ],
            overlay_conditions: ['intensity_high' as unknown as never,
                                 'boss_phase_2' as unknown as never],
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })

  it('good-a5: ChipMusic with bpm as MechanicRef to Difficulty.level', () => {
    // NOTE: 'level' IS in Difficulty's emits_fields (per catalog entry).
    const d = makeDesign({
      mechanics: [
        { id: 'diff' as unknown as never, type: 'Difficulty',
          params: { drive: 'time',
                    easy: { spawnRateMul: 0.5 }, hard: { spawnRateMul: 1.5 },
                    max_level: 10 } as unknown as never },
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: {
              bpm: { mechanic_ref: 'diff' as unknown as never, field: 'level' },
              loop: true, bars: 1,
              channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
            },
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(true)
  })
})


// ─────────────────────────────────────────────────────────────
//   5 malformed audio scripts — each hits a specific error kind
// ─────────────────────────────────────────────────────────────

describe('audio validator: 5 malformed scripts, correct error kinds', () => {
  it('bad-a1: unknown_sfx_preset', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'sfx' as unknown as never, type: 'SfxLibrary',
          params: { sfx: { coin: minimalSfxrParams() } } as unknown as never },
      ] as unknown as never,
    })
    d.archetypes.coin = {
      mesh: 'sphere', controller: 'none', components: [], tags: ['pickup'],
      trigger: {
        kind: 'pickup', contact_side: 'any',
        on_contact: { kind: 'play_sfx_ref',
                      library_ref: 'sfx' as unknown as never,
                      preset: 'nonexistent_preset' },
      },
    } as unknown as never
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('unknown_sfx_preset')
  })

  it('bad-a2: invalid_chiptune_track (negative duration)', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: {
              bpm: 120, loop: true, bars: 1,
              channels: { pulse1: [{ time: 0, note: 'C4', duration: -0.5 }] },
            },
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('invalid_chiptune_track')
  })

  it('bad-a3: library_ref_not_sfx_library', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'hud' as unknown as never, type: 'HUD',
          params: { fields: [] } as unknown as never },
      ] as unknown as never,
    })
    d.archetypes.coin = {
      mesh: 'sphere', controller: 'none', components: [], tags: ['pickup'],
      trigger: {
        kind: 'pickup', contact_side: 'any',
        // library_ref points to HUD, not SfxLibrary
        on_contact: { kind: 'play_sfx_ref',
                      library_ref: 'hud' as unknown as never,
                      preset: 'coin' },
      },
    } as unknown as never
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('library_ref_not_sfx_library')
  })

  it('bad-a4: unknown_mechanic_field (bpm refs field not in emits_fields)', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'diff' as unknown as never, type: 'Difficulty',
          params: { drive: 'time',
                    easy: { spawnRateMul: 0.5 }, hard: { spawnRateMul: 1.5 },
                    max_level: 10 } as unknown as never },
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: {
              bpm: { mechanic_ref: 'diff' as unknown as never,
                     field: 'nonexistent_field' },
              loop: true, bars: 1,
              channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
            },
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('unknown_mechanic_field')
  })

  it('bad-a5: overlay_condition_mismatch', () => {
    const d = makeDesign({
      mechanics: [
        { id: 'music' as unknown as never, type: 'ChipMusic',
          params: {
            base_track: {
              bpm: 120, loop: true, bars: 1,
              channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
            },
            overlay_tracks: [
              { bpm: 120, loop: true, bars: 1,
                channels: { triangle: [{ time: 0, note: 'G3', duration: 1 }] } },
              { bpm: 120, loop: true, bars: 1,
                channels: { noise: [{ time: 0, note: 'kick', duration: 0.25 }] } },
            ],
            // 2 tracks but only 1 condition
            overlay_conditions: ['intensity_high' as unknown as never],
            channel: 'music',
          } as unknown as never },
      ] as unknown as never,
    })
    const r = validate(d)
    expect(r.ok).toBe(false)
    if (r.ok) return
    expect(r.errors.map(e => e.kind)).toContain('overlay_condition_mismatch')
  })
})
