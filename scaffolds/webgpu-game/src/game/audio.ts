/**
 * Procedural audio — generates all SFX via Web Audio oscillators.
 * Zero audio files needed.
 */

export class ProceduralAudio {
  private ctx: AudioContext | null = null
  private masterGain: GainNode | null = null
  private musicGain: GainNode | null = null
  private sfxGain: GainNode | null = null
  private musicOsc: OscillatorNode | null = null
  private initialized = false

  private init(): void {
    if (this.initialized) return
    this.ctx = new AudioContext()
    this.masterGain = this.ctx.createGain()
    this.masterGain.gain.value = 0.3
    this.masterGain.connect(this.ctx.destination)

    this.musicGain = this.ctx.createGain()
    this.musicGain.gain.value = 0.15
    this.musicGain.connect(this.masterGain)

    this.sfxGain = this.ctx.createGain()
    this.sfxGain.gain.value = 0.5
    this.sfxGain.connect(this.masterGain)

    this.initialized = true
  }

  private ensure(): AudioContext | null {
    if (!this.ctx) this.init()
    if (this.ctx?.state === 'suspended') this.ctx.resume()
    return this.ctx
  }

  /** Pew sound — short high-frequency chirp. */
  playShoot(): void {
    const ctx = this.ensure()
    if (!ctx || !this.sfxGain) return

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'square'
    osc.frequency.setValueAtTime(880, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(220, ctx.currentTime + 0.08)
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.1)
    osc.connect(gain)
    gain.connect(this.sfxGain)
    osc.start()
    osc.stop(ctx.currentTime + 0.1)
  }

  /** Boom — low frequency explosion. */
  playExplosion(): void {
    const ctx = this.ensure()
    if (!ctx || !this.sfxGain) return

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    const noise = ctx.createOscillator()

    osc.type = 'sine'
    osc.frequency.setValueAtTime(150, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(30, ctx.currentTime + 0.3)
    gain.gain.setValueAtTime(0.5, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)

    noise.type = 'sawtooth'
    noise.frequency.setValueAtTime(100, ctx.currentTime)
    noise.frequency.exponentialRampToValueAtTime(10, ctx.currentTime + 0.3)

    const noiseGain = ctx.createGain()
    noiseGain.gain.setValueAtTime(0.2, ctx.currentTime)
    noiseGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3)

    osc.connect(gain)
    noise.connect(noiseGain)
    gain.connect(this.sfxGain)
    noiseGain.connect(this.sfxGain)
    osc.start(); noise.start()
    osc.stop(ctx.currentTime + 0.4)
    noise.stop(ctx.currentTime + 0.3)
  }

  /** Ding — pickup collect sound. */
  playPickup(): void {
    const ctx = this.ensure()
    if (!ctx || !this.sfxGain) return

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.setValueAtTime(523, ctx.currentTime)
    osc.frequency.setValueAtTime(784, ctx.currentTime + 0.05)
    osc.frequency.setValueAtTime(1047, ctx.currentTime + 0.1)
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2)
    osc.connect(gain)
    gain.connect(this.sfxGain)
    osc.start()
    osc.stop(ctx.currentTime + 0.2)
  }

  /** Thud — player hit. */
  playHit(): void {
    const ctx = this.ensure()
    if (!ctx || !this.sfxGain) return

    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'triangle'
    osc.frequency.setValueAtTime(200, ctx.currentTime)
    osc.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.15)
    gain.gain.setValueAtTime(0.4, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2)
    osc.connect(gain)
    gain.connect(this.sfxGain)
    osc.start()
    osc.stop(ctx.currentTime + 0.2)
  }

  /** Simple ambient drone music. */
  playMusic(): void {
    const ctx = this.ensure()
    if (!ctx || !this.musicGain || this.musicOsc) return

    // Bass drone
    this.musicOsc = ctx.createOscillator()
    this.musicOsc.type = 'sine'
    this.musicOsc.frequency.value = 55 // A1
    this.musicOsc.connect(this.musicGain)
    this.musicOsc.start()

    // Subtle modulation
    const lfo = ctx.createOscillator()
    const lfoGain = ctx.createGain()
    lfo.frequency.value = 0.1
    lfoGain.gain.value = 5
    lfo.connect(lfoGain)
    lfoGain.connect(this.musicOsc.frequency)
    lfo.start()
  }

  stopMusic(): void {
    try { this.musicOsc?.stop() } catch {}
    this.musicOsc = null
  }

  setMasterVolume(v: number): void {
    if (this.masterGain) this.masterGain.gain.value = v
  }
}
