// Phase 5 — ChipMusic + SfxLibrary runtime tests.
//
// Exercises the mechanic registry end-to-end: each runtime is created
// via mechanicRegistry.create(), init/update/expose/dispose go through
// the MechanicRuntime interface, and audio side-effects land on a
// FakeAudioContext (same stubs as audio_chipsynth.test.ts).

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Stubs installed before any of the under-test modules are loaded — the
// mechanics side-effect-register during module init and some touch
// AudioContext at that point via their factory. Register ASAP.

class FakeGainNode {
  gain = {
    value: 1,
    setValueAtTime: vi.fn(),
    linearRampToValueAtTime: vi.fn(),
    exponentialRampToValueAtTime: vi.fn(),
    setTargetAtTime: vi.fn(),
    cancelScheduledValues: vi.fn(),
  }
  connect = vi.fn()
  disconnect = vi.fn()
}
class FakeOscillator {
  type = 'square'
  frequency = { value: 0, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() }
  connect = vi.fn(); disconnect = vi.fn()
  start = vi.fn(); stop = vi.fn()
  setPeriodicWave = vi.fn()
}
class FakeBufferSource {
  buffer: unknown = null; loop = false
  connect = vi.fn(); disconnect = vi.fn()
  start = vi.fn(); stop = vi.fn()
}
class FakeBiquadFilter {
  type = 'lowpass'
  frequency = { value: 0, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() }
  Q = { value: 1 }
  connect = vi.fn(); disconnect = vi.fn()
}
class FakePeriodicWave {}
class FakeAudioBuffer {
  private data: Float32Array[]
  constructor(public numberOfChannels: number, public length: number, public sampleRate: number) {
    this.data = Array.from({ length: numberOfChannels }, () => new Float32Array(length))
  }
  getChannelData(i: number): Float32Array { return this.data[i] }
}
class FakeAudioContext {
  currentTime = 0
  sampleRate = 44100
  state = 'running'
  destination = { connect: vi.fn() }
  createGain = () => new FakeGainNode()
  createOscillator = () => new FakeOscillator()
  createBufferSource = () => new FakeBufferSource()
  createBiquadFilter = () => new FakeBiquadFilter()
  createPeriodicWave = () => new FakePeriodicWave()
  createBuffer = (c: number, l: number, sr: number) => new FakeAudioBuffer(c, l, sr)
  decodeAudioData = vi.fn()
  listener = {
    positionX: { value: 0 }, positionY: { value: 0 }, positionZ: { value: 0 },
    forwardX: { value: 0 }, forwardY: { value: 0 }, forwardZ: { value: -1 },
    upX: { value: 0 }, upY: { value: 1 }, upZ: { value: 0 },
  }
  createPanner = () => ({
    panningModel: 'HRTF', distanceModel: 'inverse',
    refDistance: 1, maxDistance: 50,
    positionX: { value: 0 }, positionY: { value: 0 }, positionZ: { value: 0 },
    connect: vi.fn(), disconnect: vi.fn(),
  })
  suspend = vi.fn(); resume = vi.fn(); close = vi.fn()
}

// Install stubs at module load BEFORE the test body imports anything.
vi.stubGlobal('AudioContext', FakeAudioContext)
vi.stubGlobal('AudioBuffer', FakeAudioBuffer)
vi.stubGlobal('webkitAudioContext', FakeAudioContext)

// Static imports — avoids circular-init hazard of dynamic imports
// inside each test. The registry is fully built by the time the
// `describe` blocks run.
import { mechanicRegistry } from '../src/design/mechanics/index'
import type { MechanicInstance } from '../src/design/schema'
import type { Game } from '../src/game/game'

function makeGame(flags: Record<string, unknown> = {}): Game {
  return {
    sceneManager: {
      activeScene: () => ({ properties: { world_flags: flags } }),
    },
  } as unknown as Game
}

function baseChipInstance(overrides: Record<string, unknown> = {}): MechanicInstance {
  return {
    id: 'music', type: 'ChipMusic',
    params: {
      base_track: {
        bpm: 120, loop: true, bars: 1,
        channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
      },
      channel: 'music',
      ...overrides,
    },
  } as unknown as MechanicInstance
}


describe('ChipMusic runtime', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('registers under ChipMusic', () => {
    expect(mechanicRegistry.has('ChipMusic')).toBe(true)
  })

  it('init with autoplay_on=undefined starts the base track', () => {
    const rt = mechanicRegistry.create(baseChipInstance(), makeGame())!
    expect(rt).not.toBeNull()
    expect((rt.expose!()).is_playing).toBe(true)
    rt.dispose()
  })

  it('autoplay_on arms playback until world_flag is truthy', () => {
    const flags: Record<string, unknown> = {}
    const rt = mechanicRegistry.create(
      baseChipInstance({ autoplay_on: 'boss_alive' }),
      makeGame(flags),
    )!
    rt.update(0.016)
    expect((rt.expose!()).is_playing).toBe(false)
    flags.boss_alive = true
    rt.update(0.016)
    expect((rt.expose!()).is_playing).toBe(true)
    rt.dispose()
  })

  it('stop_on halts all handles', () => {
    const flags: Record<string, unknown> = {}
    const rt = mechanicRegistry.create(
      baseChipInstance({ stop_on: 'game_over' }),
      makeGame(flags),
    )!
    expect((rt.expose!()).is_playing).toBe(true)
    flags.game_over = true
    rt.update(0.016)
    expect((rt.expose!()).is_playing).toBe(false)
    rt.dispose()
  })

  it('overlay_conditions parallel-indexed: active_layer tracks toggles', () => {
    const flags: Record<string, unknown> = {}
    const rt = mechanicRegistry.create(
      baseChipInstance({
        overlay_tracks: [
          { bpm: 120, loop: true, bars: 1,
            channels: { triangle: [{ time: 0, note: 'G3', duration: 1 }] } },
          { bpm: 120, loop: true, bars: 1,
            channels: { noise: [{ time: 0, note: 'kick', duration: 0.25 }] } },
        ],
        overlay_conditions: ['intensity_high', 'boss_phase_2'],
      }),
      makeGame(flags),
    )!
    rt.update(0.016)
    expect((rt.expose!()).active_layer).toBe(0)
    flags.intensity_high = true
    rt.update(0.016)
    expect((rt.expose!()).active_layer).toBeGreaterThanOrEqual(1)
    flags.boss_phase_2 = true
    rt.update(0.016)
    expect((rt.expose!()).active_layer).toBe(2)
    rt.dispose()
  })

  it('expose publishes current_beat as a non-negative number', () => {
    const rt = mechanicRegistry.create(baseChipInstance(), makeGame())!
    const beat = (rt.expose!()).current_beat as number
    expect(typeof beat).toBe('number')
    expect(beat).toBeGreaterThanOrEqual(0)
    rt.dispose()
  })
})


describe('SfxLibrary runtime', () => {
  function minimalSfxrParams() {
    return {
      waveType: 'square' as const,
      envelopeAttack: 0, envelopeSustain: 0.1, envelopePunch: 0.3, envelopeDecay: 0.2,
      baseFreq: 0.5, freqLimit: 0, freqRamp: 0, freqDeltaRamp: 0,
      vibratoStrength: 0, vibratoSpeed: 0,
      arpMod: 0, arpSpeed: 0,
      duty: 0.5, dutyRamp: 0, repeatSpeed: 0,
      flangerOffset: 0, flangerRamp: 0,
      lpFilterCutoff: 1, lpFilterCutoffRamp: 0, lpFilterResonance: 0,
      hpFilterCutoff: 0, hpFilterCutoffRamp: 0,
      masterVolume: 0.25, sampleRate: 44100 as const, sampleSize: 16 as const,
    }
  }

  it('registers under SfxLibrary', () => {
    expect(mechanicRegistry.has('SfxLibrary')).toBe(true)
  })

  it('pre-renders presets under `${id}.${name}` keys', () => {
    const rt = mechanicRegistry.create({
      id: 'sfx', type: 'SfxLibrary',
      params: {
        sfx: {
          pickup: minimalSfxrParams(),
          laser: { ...minimalSfxrParams(), waveType: 'sawtooth' as const },
        },
      },
    } as unknown as MechanicInstance, makeGame())!
    const e = rt.expose!()
    expect(e.preset_count).toBe(2)
    expect(e.presets).toEqual(['pickup', 'laser'])
    rt.dispose()
  })

  it('empty sfx map exposes zero presets', () => {
    const rt = mechanicRegistry.create({
      id: 'sfx', type: 'SfxLibrary',
      params: { sfx: {} },
    } as unknown as MechanicInstance, makeGame())!
    expect((rt.expose!()).preset_count).toBe(0)
    rt.dispose()
  })
})
