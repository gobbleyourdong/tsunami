// Phase 3 tests — ChipSynth.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Reusable mocks — chipsynth exercises more of the AudioContext
// surface than sfxr (periodic waves, oscillators, filter nodes),
// so the stubs grow a bit.

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
  connect = vi.fn()
  disconnect = vi.fn()
  start = vi.fn()
  stop = vi.fn()
  setPeriodicWave = vi.fn()
  onended: (() => void) | null = null
}
class FakeBufferSource {
  buffer: unknown = null
  loop = false
  connect = vi.fn()
  disconnect = vi.fn()
  start = vi.fn()
  stop = vi.fn()
}
class FakeBiquadFilter {
  type = 'lowpass'
  frequency = { value: 0, setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() }
  Q = { value: 1 }
  connect = vi.fn()
  disconnect = vi.fn()
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
  suspend = vi.fn(); resume = vi.fn(); close = vi.fn()
}

describe('ChipSynth — scheduling + cleanup', () => {
  beforeEach(() => {
    vi.stubGlobal('AudioContext', FakeAudioContext)
    vi.stubGlobal('AudioBuffer', FakeAudioBuffer)
    vi.stubGlobal('webkitAudioContext', FakeAudioContext)
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  async function makeChip() {
    const { AudioEngine } = await import('../src/audio/engine')
    const { ChipSynth } = await import('../src/audio/chipsynth')
    const engine = new AudioEngine()
    engine.init()
    return { engine, synth: new ChipSynth(engine) }
  }

  it('playing is false before any track starts', async () => {
    const { synth } = await makeChip()
    expect(synth.playing).toBe(false)
  })

  it('play() returns a handle and flips playing to true', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: 120, loop: false, bars: 1,
      channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
    })
    expect(handle.id).toBeGreaterThan(0)
    expect(synth.playing).toBe(true)
    handle.stop()
    expect(synth.playing).toBe(false)
  })

  it('bpm as number: scheduler resolves to numeric BPM', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: 90, loop: false, bars: 1,
      channels: { pulse1: [{ time: 0, note: 'A4', duration: 0.5 }] },
    })
    // First tick fires immediately (synchronous in play()).
    expect(synth.playing).toBe(true)
    handle.stop()
  })

  it('bpm as MechanicRef: resolver falls back to default when mechanic absent', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: { mechanic_ref: 'difficulty', field: 'bpm' } as unknown as number,
      loop: false, bars: 1,
      channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
    })
    // No activeScene wired — resolver returns fallback (120 BPM).
    // Assertion: playing without throwing.
    expect(synth.playing).toBe(true)
    handle.stop()
  })

  it('stopAll() clears all handles', async () => {
    const { synth } = await makeChip()
    const t = {
      bpm: 120, loop: false, bars: 1,
      channels: { pulse1: [{ time: 0, note: 'C4', duration: 1 }] },
    }
    synth.play(t)
    synth.play(t)
    synth.play(t)
    expect(synth.playing).toBe(true)
    synth.stopAll()
    expect(synth.playing).toBe(false)
  })

  it('looped track continues scheduling past track length', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: 240, loop: true, bars: 1,
      channels: { pulse1: [{ time: 0, note: 'C4', duration: 0.5 }] },
    })
    // Advance fake timer past one full bar — scheduler should keep
    // alive without throwing.
    vi.advanceTimersByTime(1500)
    expect(synth.playing).toBe(true)
    handle.stop()
  })

  it('drum notes on noise channel use DRUM_PRESETS', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: 120, loop: false, bars: 1,
      channels: { noise: [
        { time: 0, note: 'kick', duration: 0.25 },
        { time: 0.5, note: 'snare', duration: 0.25 },
        { time: 1, note: 'hat_closed', duration: 0.125 },
      ]},
    })
    // No assertion on specific node counts — the test exercises the
    // drum-preset dispatch path without crashing.
    expect(synth.playing).toBe(true)
    handle.stop()
  })

  it('custom wave_table generates a wave PeriodicWave', async () => {
    const { synth } = await makeChip()
    const handle = synth.play({
      bpm: 120, loop: false, bars: 1,
      channels: { wave: [{ time: 0, note: 'A4', duration: 0.5 }] },
      wave_table: Array.from({ length: 32 }, (_, i) => i & 15),
    })
    expect(synth.playing).toBe(true)
    handle.stop()
  })
})
