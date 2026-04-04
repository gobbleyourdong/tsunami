/**
 * Procedural SFX Synthesizer — generate game sounds from parameters.
 * No audio files needed. Every sound is a Web Audio oscillator chain.
 *
 * Usage:
 *   const synth = new GameSynth()
 *   synth.play('swordSlash')
 *   synth.play('explosion', { intensity: 0.8 })
 *   synth.play('footstep', { surface: 'stone' })
 */

type OscType = OscillatorType

interface SFXParams {
  intensity?: number   // 0-1, scales volume and pitch range
  surface?: string     // for footsteps: grass, stone, wood, sand
  pitch?: number       // base pitch multiplier
}

interface SFXDef {
  name: string
  build: (ctx: AudioContext, dest: AudioNode, params: SFXParams) => void
}

export class GameSynth {
  private ctx: AudioContext | null = null
  private master: GainNode | null = null
  volume = 0.4

  private init(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext()
      this.master = this.ctx.createGain()
      this.master.gain.value = this.volume
      this.master.connect(this.ctx.destination)
    }
    if (this.ctx.state === 'suspended') this.ctx.resume()
    return this.ctx
  }

  play(name: string, params: SFXParams = {}): void {
    const ctx = this.init()
    const def = SFX_LIBRARY[name]
    if (!def) return
    def.build(ctx, this.master!, params)
  }

  setVolume(v: number): void {
    this.volume = v
    if (this.master) this.master.gain.value = v
  }
}

// --- SFX Definitions ---

function osc(ctx: AudioContext, type: OscType, freq: number, duration: number, dest: AudioNode, volume = 0.3): { osc: OscillatorNode; gain: GainNode } {
  const o = ctx.createOscillator()
  const g = ctx.createGain()
  o.type = type
  o.frequency.value = freq
  g.gain.value = volume
  o.connect(g)
  g.connect(dest)
  o.start()
  o.stop(ctx.currentTime + duration)
  return { osc: o, gain: g }
}

function noise(ctx: AudioContext, duration: number, dest: AudioNode, volume = 0.1): { source: AudioBufferSourceNode; gain: GainNode } {
  const bufferSize = ctx.sampleRate * duration
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
  const data = buffer.getChannelData(0)
  for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1

  const source = ctx.createBufferSource()
  source.buffer = buffer
  const g = ctx.createGain()
  g.gain.value = volume
  source.connect(g)
  g.connect(dest)
  source.start()
  return { source, gain: g }
}

const SFX_LIBRARY: Record<string, SFXDef> = {

  // --- Combat ---
  swordSlash: {
    name: 'swordSlash',
    build(ctx, dest, p) {
      const t = ctx.currentTime
      const int = p.intensity ?? 0.7
      // Noise burst (whoosh)
      const { gain: ng } = noise(ctx, 0.15, dest, 0.2 * int)
      ng.gain.setValueAtTime(0.2 * int, t)
      ng.gain.exponentialRampToValueAtTime(0.001, t + 0.15)
      // High pitch sweep
      const { osc: o } = osc(ctx, 'sawtooth', 800 * int, 0.1, dest, 0.15 * int)
      o.frequency.exponentialRampToValueAtTime(200, t + 0.1)
    },
  },

  swordHit: {
    name: 'swordHit',
    build(ctx, dest, p) {
      const t = ctx.currentTime
      const int = p.intensity ?? 0.8
      // Impact thud
      const { osc: o1 } = osc(ctx, 'sine', 150 * int, 0.2, dest, 0.3 * int)
      o1.frequency.exponentialRampToValueAtTime(40, t + 0.2)
      // Metal clang
      const { osc: o2 } = osc(ctx, 'square', 1200, 0.05, dest, 0.1 * int)
      o2.frequency.exponentialRampToValueAtTime(600, t + 0.05)
      // Noise crunch
      const { gain: ng } = noise(ctx, 0.08, dest, 0.15 * int)
      ng.gain.exponentialRampToValueAtTime(0.001, t + 0.08)
    },
  },

  explosion: {
    name: 'explosion',
    build(ctx, dest, p) {
      const t = ctx.currentTime
      const int = p.intensity ?? 1.0
      // Low boom
      const { osc: o1 } = osc(ctx, 'sine', 120 * int, 0.5, dest, 0.4 * int)
      o1.frequency.exponentialRampToValueAtTime(20, t + 0.5)
      // Noise crackle
      const { gain: ng } = noise(ctx, 0.4, dest, 0.25 * int)
      ng.gain.setValueAtTime(0.25 * int, t)
      ng.gain.exponentialRampToValueAtTime(0.001, t + 0.4)
      // Sub rumble
      const { osc: o2 } = osc(ctx, 'sine', 40, 0.6, dest, 0.2 * int)
      o2.frequency.exponentialRampToValueAtTime(15, t + 0.6)
    },
  },

  magicCast: {
    name: 'magicCast',
    build(ctx, dest, p) {
      const t = ctx.currentTime
      // Rising shimmer
      const { osc: o1 } = osc(ctx, 'sine', 300, 0.3, dest, 0.15)
      o1.frequency.exponentialRampToValueAtTime(1200, t + 0.2)
      o1.frequency.exponentialRampToValueAtTime(800, t + 0.3)
      // Sparkle overtone
      const { osc: o2 } = osc(ctx, 'triangle', 2000, 0.2, dest, 0.08)
      o2.frequency.setValueAtTime(2000, t + 0.1)
      o2.frequency.exponentialRampToValueAtTime(3000, t + 0.2)
    },
  },

  // --- Movement ---
  footstep: {
    name: 'footstep',
    build(ctx, dest, p) {
      const surface = p.surface ?? 'grass'
      const t = ctx.currentTime
      if (surface === 'stone') {
        // Hard click
        const { osc: o } = osc(ctx, 'triangle', 200, 0.06, dest, 0.1)
        o.frequency.exponentialRampToValueAtTime(80, t + 0.06)
      } else if (surface === 'wood') {
        // Hollow thump
        const { osc: o } = osc(ctx, 'sine', 150, 0.08, dest, 0.12)
        o.frequency.exponentialRampToValueAtTime(60, t + 0.08)
      } else if (surface === 'sand') {
        // Soft scrunch
        const { gain: ng } = noise(ctx, 0.1, dest, 0.04)
        ng.gain.exponentialRampToValueAtTime(0.001, t + 0.1)
      } else {
        // Grass: soft thud + rustle
        const { osc: o } = osc(ctx, 'sine', 100, 0.07, dest, 0.06)
        o.frequency.exponentialRampToValueAtTime(40, t + 0.07)
        const { gain: ng } = noise(ctx, 0.05, dest, 0.02)
        ng.gain.exponentialRampToValueAtTime(0.001, t + 0.05)
      }
    },
  },

  // --- UI ---
  menuSelect: {
    name: 'menuSelect',
    build(ctx, dest) {
      const t = ctx.currentTime
      osc(ctx, 'sine', 440, 0.08, dest, 0.1)
      const { osc: o2 } = osc(ctx, 'sine', 660, 0.08, dest, 0.08)
      o2.frequency.setValueAtTime(660, t + 0.04)
    },
  },

  menuBack: {
    name: 'menuBack',
    build(ctx, dest) {
      const { osc: o } = osc(ctx, 'sine', 440, 0.1, dest, 0.08)
      o.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.1)
    },
  },

  questComplete: {
    name: 'questComplete',
    build(ctx, dest) {
      const t = ctx.currentTime
      // Triumphant arpeggio: C E G C
      osc(ctx, 'triangle', 523, 0.15, dest, 0.12) // C5
      setTimeout(() => osc(ctx, 'triangle', 659, 0.15, dest, 0.12), 100) // E5
      setTimeout(() => osc(ctx, 'triangle', 784, 0.15, dest, 0.12), 200) // G5
      setTimeout(() => osc(ctx, 'triangle', 1047, 0.25, dest, 0.15), 300) // C6
    },
  },

  pickup: {
    name: 'pickup',
    build(ctx, dest) {
      const t = ctx.currentTime
      const { osc: o } = osc(ctx, 'sine', 600, 0.12, dest, 0.12)
      o.frequency.exponentialRampToValueAtTime(1200, t + 0.08)
      o.frequency.setValueAtTime(1200, t + 0.08)
    },
  },

  coinCollect: {
    name: 'coinCollect',
    build(ctx, dest) {
      const t = ctx.currentTime
      osc(ctx, 'square', 1800, 0.04, dest, 0.06)
      setTimeout(() => osc(ctx, 'square', 2400, 0.06, dest, 0.06), 50)
    },
  },

  playerHurt: {
    name: 'playerHurt',
    build(ctx, dest) {
      const t = ctx.currentTime
      const { osc: o } = osc(ctx, 'sawtooth', 200, 0.2, dest, 0.15)
      o.frequency.exponentialRampToValueAtTime(80, t + 0.2)
      const { gain: ng } = noise(ctx, 0.1, dest, 0.1)
      ng.gain.exponentialRampToValueAtTime(0.001, t + 0.1)
    },
  },

  playerDeath: {
    name: 'playerDeath',
    build(ctx, dest) {
      const t = ctx.currentTime
      // Descending tone
      const { osc: o } = osc(ctx, 'sawtooth', 400, 0.8, dest, 0.15)
      o.frequency.exponentialRampToValueAtTime(40, t + 0.8)
      // Rumble
      const { osc: o2 } = osc(ctx, 'sine', 60, 1.0, dest, 0.1)
      o2.frequency.exponentialRampToValueAtTime(20, t + 1.0)
    },
  },

  // --- Ambient ---
  wind: {
    name: 'wind',
    build(ctx, dest) {
      const { gain: ng } = noise(ctx, 2.0, dest, 0.02)
      const filter = ctx.createBiquadFilter()
      filter.type = 'lowpass'
      filter.frequency.value = 400
      // Rewire through filter
      ng.disconnect()
      ng.connect(filter)
      filter.connect(dest)
      // Slow volume modulation
      const lfo = ctx.createOscillator()
      const lfoGain = ctx.createGain()
      lfo.frequency.value = 0.3
      lfoGain.gain.value = 0.01
      lfo.connect(lfoGain)
      lfoGain.connect(ng.gain)
      lfo.start()
      lfo.stop(ctx.currentTime + 2.0)
    },
  },
}

export { SFX_LIBRARY }
