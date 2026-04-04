/**
 * Procedural Music Generator — generates background tracks from parameters.
 * Zero audio files. Builds chord progressions, arpeggios, bass lines,
 * and percussion from Web Audio oscillators.
 *
 * Usage:
 *   const music = new ProceduralMusic()
 *   music.play('village')   // calm, major key, harp arpeggios
 *   music.play('combat')    // intense, minor key, fast drums
 *   music.play('forest')    // mysterious, ambient pads
 *   music.crossfadeTo('combat', 2)  // smooth transition
 */

type Note = number  // frequency in Hz

// Note frequencies (A4 = 440Hz)
const NOTES: Record<string, number> = {
  C3: 130.81, D3: 146.83, E3: 164.81, F3: 174.61, G3: 196.00, A3: 220.00, B3: 246.94,
  C4: 261.63, D4: 293.66, E4: 329.63, F4: 349.23, G4: 392.00, A4: 440.00, B4: 493.88,
  C5: 523.25, D5: 587.33, E5: 659.26, F5: 698.46, G5: 783.99, A5: 880.00, B5: 987.77,
}

// Scale patterns (semitone intervals from root)
const SCALES = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
  dorian: [0, 2, 3, 5, 7, 9, 10],
  pentatonic: [0, 2, 4, 7, 9],
  blues: [0, 3, 5, 6, 7, 10],
}

function noteToFreq(root: number, semitones: number): number {
  return root * Math.pow(2, semitones / 12)
}

function getScale(root: number, scale: keyof typeof SCALES, octaves = 2): number[] {
  const pattern = SCALES[scale]
  const notes: number[] = []
  for (let oct = 0; oct < octaves; oct++) {
    for (const interval of pattern) {
      notes.push(noteToFreq(root, interval + oct * 12))
    }
  }
  return notes
}

interface TrackDef {
  name: string
  bpm: number
  root: number
  scale: keyof typeof SCALES
  layers: LayerDef[]
}

interface LayerDef {
  type: 'arpeggio' | 'bass' | 'pad' | 'perc' | 'melody'
  oscType: OscillatorType
  volume: number
  pattern: number[]  // scale degree indices (0-based)
  rhythm: number[]   // durations in beats (0.25 = 16th, 0.5 = 8th, 1 = quarter)
  octave?: number    // octave offset
}

// Track definitions
const TRACKS: Record<string, TrackDef> = {
  village: {
    name: 'Village Theme',
    bpm: 90,
    root: NOTES.C4,
    scale: 'major',
    layers: [
      { type: 'arpeggio', oscType: 'triangle', volume: 0.06, pattern: [0, 2, 4, 2], rhythm: [0.5, 0.5, 0.5, 0.5] },
      { type: 'bass', oscType: 'sine', volume: 0.08, pattern: [0, 0, 3, 4], rhythm: [2, 2, 2, 2], octave: -1 },
      { type: 'pad', oscType: 'sine', volume: 0.03, pattern: [0, 2, 4], rhythm: [4, 4, 4] },
    ],
  },
  combat: {
    name: 'Battle Theme',
    bpm: 140,
    root: NOTES.A3,
    scale: 'minor',
    layers: [
      { type: 'arpeggio', oscType: 'sawtooth', volume: 0.04, pattern: [0, 2, 4, 5, 4, 2], rhythm: [0.25, 0.25, 0.25, 0.25, 0.25, 0.25] },
      { type: 'bass', oscType: 'square', volume: 0.06, pattern: [0, 0, 3, 4, 3, 0], rhythm: [1, 0.5, 0.5, 1, 0.5, 0.5], octave: -1 },
      { type: 'perc', oscType: 'square', volume: 0.03, pattern: [0], rhythm: [0.5] },
    ],
  },
  forest: {
    name: 'Forest Ambience',
    bpm: 60,
    root: NOTES.E3,
    scale: 'dorian',
    layers: [
      { type: 'pad', oscType: 'sine', volume: 0.04, pattern: [0, 2, 4], rhythm: [8, 8, 8] },
      { type: 'arpeggio', oscType: 'triangle', volume: 0.03, pattern: [4, 6, 4, 2, 0], rhythm: [1, 1, 1, 1, 2] },
    ],
  },
  dungeon: {
    name: 'Dungeon Theme',
    bpm: 70,
    root: NOTES.D3,
    scale: 'blues',
    layers: [
      { type: 'bass', oscType: 'sine', volume: 0.07, pattern: [0, 0, 2, 3, 2, 0], rhythm: [2, 1, 1, 2, 1, 1], octave: -1 },
      { type: 'pad', oscType: 'triangle', volume: 0.025, pattern: [0, 3, 4], rhythm: [4, 4, 4] },
    ],
  },
  title: {
    name: 'Title Theme',
    bpm: 80,
    root: NOTES.G3,
    scale: 'pentatonic',
    layers: [
      { type: 'melody', oscType: 'triangle', volume: 0.05, pattern: [0, 2, 4, 3, 2, 0, 1, 0], rhythm: [1, 0.5, 0.5, 1, 0.5, 0.5, 1, 2] },
      { type: 'pad', oscType: 'sine', volume: 0.03, pattern: [0, 2, 4], rhythm: [4, 4, 4] },
      { type: 'bass', oscType: 'sine', volume: 0.05, pattern: [0, 0, 4, 3], rhythm: [2, 2, 2, 2], octave: -1 },
    ],
  },
  gameover: {
    name: 'Game Over',
    bpm: 50,
    root: NOTES.C3,
    scale: 'minor',
    layers: [
      { type: 'pad', oscType: 'sine', volume: 0.04, pattern: [0, 2, 4], rhythm: [8, 8, 8] },
    ],
  },
}

export class ProceduralMusic {
  private ctx: AudioContext | null = null
  private masterGain: GainNode | null = null
  private activeNodes: { osc: OscillatorNode; gain: GainNode }[] = []
  private scheduleTimer: number | null = null
  private currentTrack: string = ''
  private beatTime = 0
  volume = 0.3

  private init(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext()
      this.masterGain = this.ctx.createGain()
      this.masterGain.gain.value = this.volume
      this.masterGain.connect(this.ctx.destination)
    }
    if (this.ctx.state === 'suspended') this.ctx.resume()
    return this.ctx
  }

  play(trackName: string): void {
    if (trackName === this.currentTrack) return
    this.stop()

    const ctx = this.init()
    const track = TRACKS[trackName]
    if (!track) return

    this.currentTrack = trackName
    const scale = getScale(track.root, track.scale, 3)
    const beatDuration = 60 / track.bpm

    // Schedule notes in a loop
    const scheduleAhead = 0.2  // seconds to schedule ahead
    let nextBeatTime = ctx.currentTime + 0.1

    // Per-layer state: current position in pattern
    const layerState = track.layers.map(() => ({ patIdx: 0, rhythmIdx: 0 }))

    const schedule = () => {
      while (nextBeatTime < ctx.currentTime + scheduleAhead) {
        for (let l = 0; l < track.layers.length; l++) {
          const layer = track.layers[l]
          const state = layerState[l]

          const scaleIdx = layer.pattern[state.patIdx % layer.pattern.length]
          const duration = layer.rhythm[state.rhythmIdx % layer.rhythm.length] * beatDuration
          const octaveShift = (layer.octave ?? 0) * 12
          const freq = scale[Math.min(scaleIdx, scale.length - 1)]
            * Math.pow(2, octaveShift / 12)

          if (layer.type === 'perc') {
            // Percussion: noise burst
            this.scheduleNoise(ctx, nextBeatTime, duration * 0.3, layer.volume)
          } else if (layer.type === 'pad') {
            // Pad: long sustained note with slow attack
            this.scheduleNote(ctx, layer.oscType, freq, nextBeatTime, duration * 0.9, layer.volume, 0.3, 0.5)
          } else {
            // Arpeggio/bass/melody: short notes
            this.scheduleNote(ctx, layer.oscType, freq, nextBeatTime, duration * 0.7, layer.volume, 0.01, 0.1)
          }

          state.rhythmIdx++
          if (state.rhythmIdx % layer.rhythm.length === 0) {
            state.patIdx++
          }
        }

        // Advance by smallest rhythm unit
        const minRhythm = Math.min(...track.layers.map(l => Math.min(...l.rhythm)))
        nextBeatTime += minRhythm * beatDuration
      }

      this.scheduleTimer = window.setTimeout(schedule, 100)
    }

    schedule()
  }

  private scheduleNote(
    ctx: AudioContext, type: OscillatorType, freq: number,
    startTime: number, duration: number, volume: number,
    attack: number, release: number
  ): void {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = type
    osc.frequency.value = freq

    gain.gain.setValueAtTime(0, startTime)
    gain.gain.linearRampToValueAtTime(volume, startTime + attack)
    gain.gain.setValueAtTime(volume, startTime + duration - release)
    gain.gain.linearRampToValueAtTime(0, startTime + duration)

    osc.connect(gain)
    gain.connect(this.masterGain!)
    osc.start(startTime)
    osc.stop(startTime + duration + 0.01)
  }

  private scheduleNoise(ctx: AudioContext, startTime: number, duration: number, volume: number): void {
    const bufferSize = Math.ceil(ctx.sampleRate * duration)
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate)
    const data = buffer.getChannelData(0)
    for (let i = 0; i < bufferSize; i++) data[i] = Math.random() * 2 - 1

    const source = ctx.createBufferSource()
    source.buffer = buffer
    const gain = ctx.createGain()
    const filter = ctx.createBiquadFilter()
    filter.type = 'highpass'
    filter.frequency.value = 5000

    gain.gain.setValueAtTime(volume, startTime)
    gain.gain.exponentialRampToValueAtTime(0.001, startTime + duration)

    source.connect(filter)
    filter.connect(gain)
    gain.connect(this.masterGain!)
    source.start(startTime)
  }

  crossfadeTo(trackName: string, duration = 2): void {
    if (trackName === this.currentTrack) return
    const ctx = this.init()

    // Fade out current
    if (this.masterGain) {
      this.masterGain.gain.setValueAtTime(this.masterGain.gain.value, ctx.currentTime)
      this.masterGain.gain.linearRampToValueAtTime(0, ctx.currentTime + duration / 2)
    }

    setTimeout(() => {
      this.stop()
      if (this.masterGain) this.masterGain.gain.value = this.volume
      this.play(trackName)
    }, (duration / 2) * 1000)
  }

  stop(): void {
    if (this.scheduleTimer) {
      clearTimeout(this.scheduleTimer)
      this.scheduleTimer = null
    }
    this.currentTrack = ''
  }

  setVolume(v: number): void {
    this.volume = v
    if (this.masterGain) this.masterGain.gain.value = v
  }

  get isPlaying(): boolean {
    return this.currentTrack !== ''
  }

  get current(): string {
    return this.currentTrack
  }
}

export { TRACKS }
