// Phase 2 tests — Sfxr synthesis.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Reuse the fake-audio-context stubs from the engine test module. Keep
// this test file self-contained by inlining — vitest doesn't share
// module state across test files but the stubs are tiny.

class FakeGainNode {
  gain = { value: 1 }
  connect = vi.fn()
  disconnect = vi.fn()
}
class FakeAudioBuffer {
  private channelData: Float32Array[]
  constructor(public numberOfChannels: number, public length: number, public sampleRate: number) {
    this.channelData = Array.from({ length: numberOfChannels },
      () => new Float32Array(length))
  }
  getChannelData(i: number): Float32Array { return this.channelData[i] }
}
class FakeAudioContext {
  currentTime = 0
  state = 'running'
  destination = { connect: vi.fn() }
  createGain = () => new FakeGainNode()
  createBufferSource = () => ({ connect: vi.fn(), disconnect: vi.fn(), start: vi.fn(), stop: vi.fn() })
  createBuffer = (c: number, l: number, sr: number) => new FakeAudioBuffer(c, l, sr)
  decodeAudioData = vi.fn()
  suspend = vi.fn(); resume = vi.fn(); close = vi.fn()
}

describe('Sfxr — archetype generation', () => {
  beforeEach(() => {
    vi.stubGlobal('AudioContext', FakeAudioContext)
    vi.stubGlobal('AudioBuffer', FakeAudioBuffer)
    vi.stubGlobal('webkitAudioContext', FakeAudioContext)
  })
  afterEach(() => { vi.unstubAllGlobals() })

  async function makeSfxr() {
    const { AudioEngine } = await import('../src/audio/engine')
    const { Sfxr } = await import('../src/audio/sfxr')
    const engine = new AudioEngine()
    engine.init()
    return new Sfxr(engine)
  }

  const archetypes: Array<'pickup' | 'laser' | 'explosion' | 'jump' | 'hit'> =
    ['pickup', 'laser', 'explosion', 'jump', 'hit']

  for (const kind of archetypes) {
    it(`generates a non-silent buffer for archetype "${kind}"`, async () => {
      const sfxr = await makeSfxr()
      const params = sfxr.random(kind, 42)
      const buf = sfxr.generate(params)
      expect(buf).not.toBeNull()
      expect(buf.length).toBeGreaterThan(0)
      // Non-silent: at least one sample exceeds 0.01 absolute.
      const data = buf.getChannelData(0)
      const hasSignal = Array.from(data).some(s => Math.abs(s) > 0.01)
      expect(hasSignal).toBe(true)
    })
  }

  it('random() with same seed produces identical params + audio', async () => {
    const sfxr = await makeSfxr()
    const p1 = sfxr.random('pickup', 12345)
    const p2 = sfxr.random('pickup', 12345)
    expect(p1).toEqual(p2)
    const b1 = sfxr.generate(p1)
    const b2 = sfxr.generate(p2)
    expect(b1.length).toBe(b2.length)
    // Exact equality — deterministic PCM for deterministic params. We
    // allow a tiny tolerance for the single-shot noise buffer seeding
    // (uses Math.random internally for noise wavetype only; pickup
    // archetype is square so this should be bit-exact).
    const d1 = Array.from(b1.getChannelData(0))
    const d2 = Array.from(b2.getChannelData(0))
    for (let i = 0; i < d1.length; i++) {
      expect(d1[i]).toBeCloseTo(d2[i], 10)
    }
  })

  it('generates each archetype in under 100 ms', async () => {
    const sfxr = await makeSfxr()
    for (const kind of archetypes) {
      const params = sfxr.random(kind, 0)
      const t0 = performance.now()
      sfxr.generate(params)
      const dt = performance.now() - t0
      expect(dt).toBeLessThan(100)
    }
  })

  it('generateAndRegister stores buffer under id', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const { Sfxr } = await import('../src/audio/sfxr')
    const engine = new AudioEngine()
    engine.init()
    const sfxr = new Sfxr(engine)
    const params = sfxr.random('pickup', 99)
    expect(engine.has('coin')).toBe(false)
    sfxr.generateAndRegister('coin', params)
    expect(engine.has('coin')).toBe(true)
  })
})
