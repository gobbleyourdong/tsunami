// Phase 1 — AudioEngine v1.1 extension accessor tests.
//
// Stubs the AudioContext globals in node so tests run without a browser.
// The mock records graph connections + tracks created nodes so we can
// assert the additive accessors expose what they should without needing
// a real audio device.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ─────────────────────────────────────────────────────────────
//   Minimal AudioContext stubs
// ─────────────────────────────────────────────────────────────

class FakeGainNode {
  gain = { value: 1 }
  connect = vi.fn()
  disconnect = vi.fn()
}
class FakeBufferSource {
  buffer: unknown = null
  connect = vi.fn()
  disconnect = vi.fn()
  start = vi.fn()
  stop = vi.fn()
  loop = false
  onended: (() => void) | null = null
}
class FakeAudioBuffer {
  constructor(public length: number, public sampleRate: number, public numberOfChannels: number) {}
  getChannelData(_i: number): Float32Array { return new Float32Array(this.length) }
}
class FakeAudioContext {
  currentTime = 0
  state: 'running' | 'suspended' | 'closed' = 'running'
  destination = { connect: vi.fn() }
  createGain(): FakeGainNode { return new FakeGainNode() }
  createBufferSource(): FakeBufferSource { return new FakeBufferSource() }
  createBuffer(channels: number, length: number, sampleRate: number): FakeAudioBuffer {
    return new FakeAudioBuffer(length, sampleRate, channels)
  }
  decodeAudioData = vi.fn(async () => new FakeAudioBuffer(1024, 44100, 1))
  suspend = vi.fn(async () => { this.state = 'suspended' })
  resume = vi.fn(async () => { this.state = 'running' })
  close = vi.fn(async () => { this.state = 'closed' })
}

describe('AudioEngine v1.1 extension accessors', () => {
  beforeEach(() => {
    vi.stubGlobal('AudioContext', FakeAudioContext)
    vi.stubGlobal('AudioBuffer', FakeAudioBuffer)
    // Some engine paths reference webkitAudioContext — stub that too.
    vi.stubGlobal('webkitAudioContext', FakeAudioContext)
  })
  afterEach(() => { vi.unstubAllGlobals() })

  it('context getter is null before init() fires', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const e = new AudioEngine()
    expect(e.context).toBeNull()
  })

  it('context getter returns the AudioContext instance after init()', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const e = new AudioEngine()
    e.init()
    expect(e.context).not.toBeNull()
    expect(e.context).toBeInstanceOf(FakeAudioContext)
  })

  it('loadRawBuffer registers a pre-rendered buffer without decode', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const e = new AudioEngine()
    const buf = new FakeAudioBuffer(2048, 44100, 1) as unknown as AudioBuffer
    expect(e.has('boom')).toBe(false)
    e.loadRawBuffer('boom', buf)
    expect(e.has('boom')).toBe(true)
    // init() auto-fires on first loadRawBuffer.
    expect(e.context).not.toBeNull()
  })

  it('channelGain returns the registered gain for known channels', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const e = new AudioEngine()
    e.init()
    for (const ch of ['master', 'music', 'sfx', 'voice'] as const) {
      const g = e.channelGain(ch)
      expect(g).not.toBeNull()
      expect(g).toBeInstanceOf(FakeGainNode)
    }
  })

  it('channelGain falls back to masterGain when called before init', async () => {
    const { AudioEngine } = await import('../src/audio/engine')
    const e = new AudioEngine()
    // Before init, both channelGains + masterGain are null; the accessor
    // should just return null without throwing.
    expect(e.channelGain('music')).toBeNull()
  })
})
