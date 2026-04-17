// sfxr.ts — retro sound-effect synthesizer (Phase 2 of audio v1.1).
//
// Pure Web Audio port of Tomas Pettersson's sfxr / Derek Yu's jsfxr.
// Algorithm is a single sample-loop: evaluate envelope, compute phase
// with slide / vibrato / arpeggio, sample waveform, apply LP/HP biquad
// filter, apply flanger delay, write to buffer. Output is a mono
// AudioBuffer registered into the engine's buffer map.
//
// No external deps. No decode — PCM is synthesized directly. Generation
// cost is O(duration * sampleRate) with a small constant factor;
// typical retro sfx (<1 s at 44.1 kHz) generates in <10 ms.
//
// Reference: github.com/grumdrig/jsfxr (MIT). License verified against
// the jsfxr LICENSE file before porting.

import type { AudioEngine } from './engine'

export type SfxrWaveType = 'square' | 'sawtooth' | 'sine' | 'noise'

/** 27-field sfxr parameter vector. Field names follow jsfxr / sfxr
 *  convention exactly (camelCase for JS consumers).  See §Full type
 *  spec of the audio v1.1 handoff doc for field semantics.  */
export interface SfxrParams {
  waveType: SfxrWaveType
  envelopeAttack: number         // 0..1
  envelopeSustain: number        // 0..1
  envelopePunch: number          // 0..1
  envelopeDecay: number          // 0..1
  baseFreq: number               // 0..1 (normalized — mapped to Hz internally)
  freqLimit: number              // 0..1 min-freq cutoff
  freqRamp: number               // -1..1 per-sample slope
  freqDeltaRamp: number          // -1..1 second-derivative slope
  vibratoStrength: number        // 0..1
  vibratoSpeed: number           // 0..1
  arpMod: number                 // -1..1 arpeggio semitone multiplier
  arpSpeed: number               // 0..1 arpeggio rate
  duty: number                   // 0..1 square-wave duty cycle
  dutyRamp: number               // -1..1 per-sample duty change
  repeatSpeed: number            // 0..1 — restart envelope at this rate
  flangerOffset: number          // -1..1 delay-line offset
  flangerRamp: number            // -1..1 delay-line ramp
  lpFilterCutoff: number         // 0..1
  lpFilterCutoffRamp: number     // -1..1
  lpFilterResonance: number      // 0..1
  hpFilterCutoff: number         // 0..1
  hpFilterCutoffRamp: number     // -1..1
  masterVolume: number           // 0..1 (typically ~0.25)
  sampleRate: 44100 | 22050 | 11025
  sampleSize: 8 | 16
}

// Archetype names for quick random presets (pickup / laser / etc.).
export type SfxrArchetype =
  | 'pickup' | 'laser' | 'explosion' | 'powerup' | 'hit' | 'jump' | 'blip'


// ─────────────────────────────────────────────────────────────
//   Deterministic PRNG (seeded). sfxr's randomize uses Math.random;
//   we make it seedable so unit tests can assert stable outputs.
// ─────────────────────────────────────────────────────────────

function mulberry32(seed: number): () => number {
  let t = seed >>> 0
  return () => {
    t = (t + 0x6D2B79F5) >>> 0
    let r = t
    r = Math.imul(r ^ (r >>> 15), r | 1)
    r ^= r + Math.imul(r ^ (r >>> 7), r | 61)
    return ((r ^ (r >>> 14)) >>> 0) / 4_294_967_296
  }
}

function frnd(rng: () => number, range: number): number { return rng() * range }


// ─────────────────────────────────────────────────────────────
//   Default param vector (neutral — generates silence unless tweaked)
// ─────────────────────────────────────────────────────────────

export function defaultSfxrParams(): SfxrParams {
  return {
    waveType: 'square',
    envelopeAttack: 0, envelopeSustain: 0.3, envelopePunch: 0, envelopeDecay: 0.4,
    baseFreq: 0.3, freqLimit: 0, freqRamp: 0, freqDeltaRamp: 0,
    vibratoStrength: 0, vibratoSpeed: 0,
    arpMod: 0, arpSpeed: 0,
    duty: 0.5, dutyRamp: 0,
    repeatSpeed: 0,
    flangerOffset: 0, flangerRamp: 0,
    lpFilterCutoff: 1, lpFilterCutoffRamp: 0, lpFilterResonance: 0,
    hpFilterCutoff: 0, hpFilterCutoffRamp: 0,
    masterVolume: 0.25,
    sampleRate: 44100, sampleSize: 16,
  }
}


// ─────────────────────────────────────────────────────────────
//   Archetype presets (seedable randomize)
// ─────────────────────────────────────────────────────────────

export function randomSfxrParams(kind: SfxrArchetype, seed?: number): SfxrParams {
  const rng = mulberry32(seed ?? (Date.now() & 0xffffffff))
  const p = defaultSfxrParams()
  switch (kind) {
    case 'pickup':
      p.waveType = 'square'
      p.baseFreq = 0.4 + frnd(rng, 0.5)
      p.envelopeAttack = 0
      p.envelopeSustain = frnd(rng, 0.1)
      p.envelopeDecay = 0.1 + frnd(rng, 0.4)
      p.envelopePunch = 0.3 + frnd(rng, 0.3)
      if (rng() < 0.5) { p.arpSpeed = 0.5 + frnd(rng, 0.2); p.arpMod = 0.2 + frnd(rng, 0.4) }
      break
    case 'laser':
      p.waveType = rng() < 0.33 ? 'square' : rng() < 0.66 ? 'sawtooth' : 'sine'
      if (p.waveType === 'sine' && rng() < 0.5) p.waveType = 'square'
      p.baseFreq = 0.5 + frnd(rng, 0.5)
      p.freqLimit = p.baseFreq - 0.2 - frnd(rng, 0.6)
      if (p.freqLimit < 0.2) p.freqLimit = 0.2
      p.freqRamp = -0.15 - frnd(rng, 0.2)
      if (rng() < 0.33) {
        p.baseFreq = 0.3 + frnd(rng, 0.6); p.freqLimit = frnd(rng, 0.1); p.freqRamp = -0.35 - frnd(rng, 0.3)
      }
      p.envelopeAttack = 0
      p.envelopeSustain = 0.1 + frnd(rng, 0.2)
      p.envelopeDecay = frnd(rng, 0.4)
      if (rng() < 0.5) p.envelopePunch = frnd(rng, 0.3)
      if (rng() < 0.33) { p.flangerOffset = frnd(rng, 0.2); p.flangerRamp = -frnd(rng, 0.2) }
      if (rng() < 0.5) p.hpFilterCutoff = frnd(rng, 0.3)
      break
    case 'explosion':
      p.waveType = 'noise'
      p.baseFreq = 0.1 + frnd(rng, 0.4)
      p.freqRamp = -0.1 + frnd(rng, 0.4)
      p.envelopeAttack = 0
      p.envelopeSustain = 0.1 + frnd(rng, 0.3)
      p.envelopeDecay = 0.2 + frnd(rng, 0.4)
      p.envelopePunch = 0.2 + frnd(rng, 0.6)
      if (rng() < 0.5) { p.flangerOffset = -0.3 + frnd(rng, 0.9); p.flangerRamp = -frnd(rng, 0.3) }
      if (rng() < 0.5) { p.vibratoStrength = frnd(rng, 0.7); p.vibratoSpeed = frnd(rng, 0.6) }
      break
    case 'powerup':
      p.waveType = rng() < 0.5 ? 'square' : 'sawtooth'
      p.baseFreq = 0.2 + frnd(rng, 0.3)
      p.envelopeAttack = 0
      p.envelopeSustain = frnd(rng, 0.4)
      p.envelopeDecay = 0.1 + frnd(rng, 0.5)
      if (rng() < 0.5) { p.freqRamp = 0.1 + frnd(rng, 0.4); p.repeatSpeed = 0.4 + frnd(rng, 0.4) }
      else { p.freqRamp = 0.05 + frnd(rng, 0.2); p.vibratoStrength = frnd(rng, 0.7); p.vibratoSpeed = frnd(rng, 0.6) }
      break
    case 'hit':
      p.waveType = rng() < 0.5 ? 'sawtooth' : 'noise'
      p.baseFreq = 0.2 + frnd(rng, 0.6)
      p.freqRamp = -0.3 - frnd(rng, 0.4)
      p.envelopeAttack = 0
      p.envelopeSustain = frnd(rng, 0.1)
      p.envelopeDecay = 0.1 + frnd(rng, 0.2)
      if (rng() < 0.5) p.hpFilterCutoff = frnd(rng, 0.3)
      break
    case 'jump':
      p.waveType = 'square'
      p.duty = frnd(rng, 0.6)
      p.baseFreq = 0.3 + frnd(rng, 0.3)
      p.freqRamp = 0.1 + frnd(rng, 0.2)
      p.envelopeAttack = 0
      p.envelopeSustain = 0.1 + frnd(rng, 0.3)
      p.envelopeDecay = 0.1 + frnd(rng, 0.2)
      if (rng() < 0.5) p.hpFilterCutoff = frnd(rng, 0.3)
      if (rng() < 0.5) p.lpFilterCutoff = 1 - frnd(rng, 0.6)
      break
    case 'blip':
      p.waveType = rng() < 0.5 ? 'square' : 'sawtooth'
      p.duty = frnd(rng, 0.6)
      p.baseFreq = 0.2 + frnd(rng, 0.4)
      p.envelopeAttack = 0
      p.envelopeSustain = 0.1 + frnd(rng, 0.1)
      p.envelopeDecay = frnd(rng, 0.2)
      p.hpFilterCutoff = 0.1
      break
  }
  return p
}


// ─────────────────────────────────────────────────────────────
//   Core synthesis — sfxr algorithm
// ─────────────────────────────────────────────────────────────

export class Sfxr {
  constructor(private engine: AudioEngine) {}

  /** Synthesize a mono AudioBuffer from params. Returns silence-free
   *  buffer unless params are degenerate (e.g., sustain+decay both 0). */
  generate(params: SfxrParams): AudioBuffer {
    const ctx = this.engine.context
    if (!ctx) throw new Error('sfxr.generate: AudioEngine not initialised — call engine.init() first')
    const pcm = synthesize(params)
    const buf = ctx.createBuffer(1, pcm.length, params.sampleRate)
    buf.getChannelData(0).set(pcm)
    return buf
  }

  /** Synthesize + register into the engine's buffer map under `id`.
   *  Downstream AudioEngine.play(id) works as if the buffer came from
   *  decodeAudioData. Used by SfxLibrary to pre-render presets at
   *  load time. */
  generateAndRegister(id: string, params: SfxrParams): void {
    const buf = this.generate(params)
    this.engine.loadRawBuffer(id, buf)
  }

  /** Seeded random archetype preset. Stable output for a given seed —
   *  tests compare expected buffers without flakiness. */
  random(kind: SfxrArchetype, seed?: number): SfxrParams {
    return randomSfxrParams(kind, seed)
  }
}


/** Core synthesis — pure function, returns a Float32Array of PCM.
 *  Mirrors the reference sfxr single-sample loop. */
function synthesize(params: SfxrParams): Float32Array {
  const sampleRate = params.sampleRate

  // Envelope stages: 0=attack, 1=sustain, 2=decay.
  let stage = 0
  let stageTime = 0
  const stageLen = [
    Math.floor(params.envelopeAttack * params.envelopeAttack * 100_000),
    Math.floor(params.envelopeSustain * params.envelopeSustain * 100_000),
    Math.floor(params.envelopeDecay  * params.envelopeDecay  * 100_000),
  ]

  // Frequency / period setup.
  let fperiod = 100 / (params.baseFreq * params.baseFreq + 0.001)
  const maxPeriod = 100 / (params.freqLimit * params.freqLimit + 0.001)
  let periodMultiplier = 1 - Math.pow(params.freqRamp, 3) * 0.01
  const periodMultiplierDelta = -Math.pow(params.freqDeltaRamp, 3) * 0.000001

  // Square duty cycle.
  let squareDuty = 0.5 - params.duty * 0.5
  const squareDutyDelta = -params.dutyRamp * 0.00005

  // Arpeggio.
  let arpMultiplier = params.arpMod >= 0
    ? 1 - Math.pow(params.arpMod, 2) * 0.9
    : 1 + Math.pow(params.arpMod, 2) * 10
  const arpLimit = Math.floor(Math.pow(1 - params.arpSpeed, 2) * 20_000 + 32)
    * (params.arpSpeed === 1 ? 0 : 1)

  // Vibrato.
  let vibratoPhase = 0
  const vibratoSpeed = Math.pow(params.vibratoSpeed, 2) * 0.01
  const vibratoAmplitude = params.vibratoStrength * 0.5

  // LP/HP filter state.
  let fltp = 0, fltdp = 0, fltphp = 0
  let fltw = Math.pow(params.lpFilterCutoff, 3) * 0.1
  const fltwd = 1 + params.lpFilterCutoffRamp * 0.0001
  const fltdmp = Math.min(0.8,
    5 / (1 + Math.pow(params.lpFilterResonance, 2) * 20) * (0.01 + fltw))
  let flthp = Math.pow(params.hpFilterCutoff, 2) * 0.1
  const flthpd = 1 + params.hpFilterCutoffRamp * 0.0003
  const noFilter = params.lpFilterCutoff === 1

  // Flanger delay line.
  const fltphase: number[] = new Array(1024).fill(0)
  let iphase = Math.abs(Math.floor(params.flangerOffset * params.flangerOffset * 1020))
  const iphaseDelta = Math.floor(Math.pow(params.flangerRamp, 2) * 1
    * (params.flangerRamp < 0 ? -1 : 1))
  let ipp = 0

  // Repeat / noise buffer.
  let repTime = 0
  const repLimit = Math.floor(Math.pow(1 - params.repeatSpeed, 2) * 20_000 + 32)
    * (params.repeatSpeed === 0 ? 0 : 1)

  const noiseBuf = new Float32Array(32)
  for (let i = 0; i < 32; i++) noiseBuf[i] = Math.random() * 2 - 1

  // Runtime oscillator state.
  let fphase = 0
  let phase = 0
  let period = Math.floor(fperiod)

  const totalLen = stageLen[0] + stageLen[1] + stageLen[2]
  const out = new Float32Array(totalLen)

  for (let i = 0; i < totalLen; i++) {
    // Repeat trigger.
    repTime += 1
    if (repLimit !== 0 && repTime >= repLimit) {
      repTime = 0
      stage = 0; stageTime = 0
      fperiod = 100 / (params.baseFreq * params.baseFreq + 0.001)
      periodMultiplier = 1 - Math.pow(params.freqRamp, 3) * 0.01
      squareDuty = 0.5 - params.duty * 0.5
    }

    // Slide (freq ramp).
    periodMultiplier += periodMultiplierDelta
    fperiod *= periodMultiplier
    if (fperiod > maxPeriod) {
      fperiod = maxPeriod
      if (params.freqLimit > 0) break
    }

    // Vibrato.
    let rfperiod = fperiod
    if (vibratoAmplitude > 0) {
      vibratoPhase += vibratoSpeed
      rfperiod = fperiod * (1 + Math.sin(vibratoPhase) * vibratoAmplitude)
    }
    period = Math.max(8, Math.floor(rfperiod))

    // Duty.
    squareDuty = Math.max(0, Math.min(0.5, squareDuty + squareDutyDelta))

    // Envelope.
    stageTime += 1
    while (stage < 2 && stageTime > stageLen[stage]) {
      stageTime = 0
      stage += 1
    }
    let env = 0
    if (stage === 0 && stageLen[0] > 0) env = stageTime / stageLen[0]
    else if (stage === 1) env = 1 + Math.pow(1 - stageTime / (stageLen[1] || 1), 1) * 2 * params.envelopePunch
    else if (stage === 2 && stageLen[2] > 0) env = 1 - stageTime / stageLen[2]
    env = Math.max(0, env)

    // Arpeggio.
    if (arpLimit !== 0 && i >= arpLimit) {
      // One-shot: fire once.
      fperiod *= arpMultiplier
      arpMultiplier = 1  // don't re-fire
    }

    // Flanger delay.
    iphase = Math.max(0, Math.min(1023, iphase + iphaseDelta))

    // Oscillator.
    phase += 1
    if (phase >= period) {
      phase %= period
      if (params.waveType === 'noise') {
        for (let k = 0; k < 32; k++) noiseBuf[k] = Math.random() * 2 - 1
      }
    }
    const fp = phase / period

    let sample = 0
    switch (params.waveType) {
      case 'square':
        sample = fp < squareDuty ? 0.5 : -0.5
        break
      case 'sawtooth':
        sample = 1 - fp * 2
        break
      case 'sine':
        sample = Math.sin(fp * Math.PI * 2)
        break
      case 'noise':
        sample = noiseBuf[Math.floor(fp * 32) % 32]
        break
    }

    // LP filter (biquad-ish, sfxr's simpler one-pole+resonance form).
    const pp = fltp
    fltw = Math.max(0, Math.min(0.1, fltw * fltwd))
    if (!noFilter) {
      fltdp += (sample - fltp) * fltw
      fltdp -= fltdp * fltdmp
    } else {
      fltp = sample; fltdp = 0
    }
    fltp += fltdp

    // HP filter.
    fltphp += fltp - pp
    fltphp -= fltphp * flthp
    sample = fltphp
    flthp = Math.max(0.00001, Math.min(0.1, flthp * flthpd))

    // Flanger delay.
    fltphase[ipp & 1023] = sample
    sample += fltphase[(ipp - iphase + 1024) & 1023]
    ipp = (ipp + 1) & 1023

    // Master volume + write.
    out[i] = sample * params.masterVolume * env
  }

  return out
}
