/**
 * AudioEngine — single AudioContext, lazy-init on first user gesture.
 * SoundPool, spatial audio, mixer with channel volumes, music crossfade.
 */

import { Vec3 } from '../math/vec'

export type AudioChannel = 'master' | 'music' | 'sfx' | 'voice'

export class AudioEngine {
  private ctx: AudioContext | null = null
  private buffers = new Map<string, AudioBuffer>()
  private activeSources = new Map<string, AudioBufferSourceNode[]>()

  // Mixer: GainNode tree
  private masterGain: GainNode | null = null
  private channelGains = new Map<AudioChannel, GainNode>()

  // Music state
  private currentMusic: AudioBufferSourceNode | null = null
  private currentMusicGain: GainNode | null = null
  private musicId = ''

  private initialized = false
  private muted = false

  /** Lazy-init on first user gesture. Call from click/keydown handler. */
  init(): void {
    if (this.initialized) return
    this.ctx = new AudioContext()
    this.masterGain = this.ctx.createGain()
    this.masterGain.connect(this.ctx.destination)

    for (const ch of ['master', 'music', 'sfx', 'voice'] as AudioChannel[]) {
      const gain = this.ctx.createGain()
      gain.connect(this.masterGain)
      this.channelGains.set(ch, gain)
    }

    this.initialized = true
  }

  /** Ensure context is running (browsers suspend until user gesture). */
  private ensureRunning(): AudioContext | null {
    if (!this.ctx) return null
    if (this.ctx.state === 'suspended') this.ctx.resume()
    return this.ctx
  }

  /** Pre-decode an audio file from URL or ArrayBuffer. */
  async load(id: string, source: string | ArrayBuffer): Promise<void> {
    if (!this.ctx) this.init()
    const ctx = this.ctx!

    let arrayBuffer: ArrayBuffer
    if (typeof source === 'string') {
      const response = await fetch(source)
      arrayBuffer = await response.arrayBuffer()
    } else {
      arrayBuffer = source
    }

    const buffer = await ctx.decodeAudioData(arrayBuffer)
    this.buffers.set(id, buffer)
  }

  /** Play a one-shot SFX. Returns source node for stop control. */
  play(id: string, options?: {
    channel?: AudioChannel
    volume?: number
    playbackRate?: number
    loop?: boolean
  }): AudioBufferSourceNode | null {
    const ctx = this.ensureRunning()
    if (!ctx || this.muted) return null

    const buffer = this.buffers.get(id)
    if (!buffer) return null

    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.playbackRate.value = options?.playbackRate ?? 1
    source.loop = options?.loop ?? false

    const gain = ctx.createGain()
    gain.gain.value = options?.volume ?? 1

    const channel = this.channelGains.get(options?.channel ?? 'sfx')
    source.connect(gain)
    gain.connect(channel ?? this.masterGain!)

    source.start()

    // Track for cleanup
    if (!this.activeSources.has(id)) this.activeSources.set(id, [])
    this.activeSources.get(id)!.push(source)
    source.onended = () => {
      const arr = this.activeSources.get(id)
      if (arr) {
        const idx = arr.indexOf(source)
        if (idx !== -1) arr.splice(idx, 1)
      }
    }

    return source
  }

  /** Play a sound at a 3D world position (spatial audio via PannerNode). */
  playAt(id: string, worldPos: Vec3, options?: {
    channel?: AudioChannel
    volume?: number
    refDistance?: number
    maxDistance?: number
  }): AudioBufferSourceNode | null {
    const ctx = this.ensureRunning()
    if (!ctx || this.muted) return null

    const buffer = this.buffers.get(id)
    if (!buffer) return null

    const source = ctx.createBufferSource()
    source.buffer = buffer

    const panner = ctx.createPanner()
    panner.panningModel = 'HRTF'
    panner.distanceModel = 'inverse'
    panner.refDistance = options?.refDistance ?? 1
    panner.maxDistance = options?.maxDistance ?? 50
    panner.positionX.value = worldPos[0]
    panner.positionY.value = worldPos[1]
    panner.positionZ.value = worldPos[2]

    const gain = ctx.createGain()
    gain.gain.value = options?.volume ?? 1

    const channel = this.channelGains.get(options?.channel ?? 'sfx')
    source.connect(panner)
    panner.connect(gain)
    gain.connect(channel ?? this.masterGain!)

    source.start()
    return source
  }

  /** Set listener position and orientation for spatial audio. */
  setListenerPosition(position: Vec3, forward: Vec3, up: Vec3 = [0, 1, 0]): void {
    const ctx = this.ensureRunning()
    if (!ctx) return
    const l = ctx.listener
    if (l.positionX) {
      l.positionX.value = position[0]
      l.positionY.value = position[1]
      l.positionZ.value = position[2]
      l.forwardX.value = forward[0]
      l.forwardY.value = forward[1]
      l.forwardZ.value = forward[2]
      l.upX.value = up[0]
      l.upY.value = up[1]
      l.upZ.value = up[2]
    }
  }

  /** Play background music with crossfade. */
  playMusic(id: string, fadeDuration = 2): void {
    if (id === this.musicId) return
    const ctx = this.ensureRunning()
    if (!ctx) return

    const buffer = this.buffers.get(id)
    if (!buffer) return

    const now = ctx.currentTime

    // Fade out current
    if (this.currentMusic && this.currentMusicGain) {
      this.currentMusicGain.gain.setValueAtTime(this.currentMusicGain.gain.value, now)
      this.currentMusicGain.gain.linearRampToValueAtTime(0, now + fadeDuration)
      const old = this.currentMusic
      setTimeout(() => { try { old.stop() } catch {} }, fadeDuration * 1000 + 100)
    }

    // Start new
    const source = ctx.createBufferSource()
    source.buffer = buffer
    source.loop = true

    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0, now)
    gain.gain.linearRampToValueAtTime(1, now + fadeDuration)

    const musicChannel = this.channelGains.get('music')
    source.connect(gain)
    gain.connect(musicChannel ?? this.masterGain!)
    source.start()

    this.currentMusic = source
    this.currentMusicGain = gain
    this.musicId = id
  }

  /** Stop current music with fade. */
  stopMusic(fadeDuration = 1): void {
    const ctx = this.ensureRunning()
    if (!ctx || !this.currentMusic || !this.currentMusicGain) return

    const now = ctx.currentTime
    this.currentMusicGain.gain.setValueAtTime(this.currentMusicGain.gain.value, now)
    this.currentMusicGain.gain.linearRampToValueAtTime(0, now + fadeDuration)
    const old = this.currentMusic
    setTimeout(() => { try { old.stop() } catch {} }, fadeDuration * 1000 + 100)

    this.currentMusic = null
    this.currentMusicGain = null
    this.musicId = ''
  }

  /** Stop all instances of a sound. */
  stop(id: string): void {
    const sources = this.activeSources.get(id)
    if (sources) {
      for (const s of sources) { try { s.stop() } catch {} }
      this.activeSources.delete(id)
    }
  }

  /** Set channel volume (0-1). */
  setVolume(channel: AudioChannel, volume: number): void {
    if (channel === 'master' && this.masterGain) {
      this.masterGain.gain.value = volume
    } else {
      const gain = this.channelGains.get(channel)
      if (gain) gain.gain.value = volume
    }
  }

  getVolume(channel: AudioChannel): number {
    if (channel === 'master') return this.masterGain?.gain.value ?? 1
    return this.channelGains.get(channel)?.gain.value ?? 1
  }

  /** Mute/unmute all audio (clean, no pop). */
  setMuted(muted: boolean): void {
    this.muted = muted
    if (this.masterGain) {
      this.masterGain.gain.value = muted ? 0 : 1
    }
  }

  get isMuted(): boolean { return this.muted }

  /** Check if a sound is loaded. */
  has(id: string): boolean { return this.buffers.has(id) }

  /** Suspend AudioContext (for pause). */
  suspend(): void { this.ctx?.suspend() }

  /** Resume AudioContext (for unpause). */
  resume(): void { this.ctx?.resume() }

  destroy(): void {
    this.ctx?.close()
    this.buffers.clear()
    this.activeSources.clear()
    this.initialized = false
  }
}
