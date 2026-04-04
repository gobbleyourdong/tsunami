/**
 * Animation state machine — manages transitions between animation clips.
 * Handles blending during transitions, animation events, and root motion.
 */

import { AnimationClip } from './clip'
import { Skeleton } from './skeleton'

export interface AnimationEvent {
  name: string
  time: number  // normalized 0-1 within the clip
}

export interface AnimState {
  name: string
  clip: AnimationClip
  speed: number
  loop: boolean
  events: AnimationEvent[]
}

export interface AnimTransition {
  from: string
  to: string
  duration: number  // blend duration in seconds
  condition?: () => boolean
}

export class AnimationStateMachine {
  private states = new Map<string, AnimState>()
  private transitions: AnimTransition[] = []
  private currentState: string = ''
  private currentTime = 0
  private blendState: string | null = null
  private blendTime = 0
  private blendDuration = 0
  private firedEvents = new Set<string>()

  // Callbacks
  onEvent?: (stateName: string, eventName: string) => void
  onStateChange?: (from: string, to: string) => void

  addState(name: string, clip: AnimationClip, options?: {
    speed?: number
    loop?: boolean
    events?: AnimationEvent[]
  }): this {
    this.states.set(name, {
      name,
      clip,
      speed: options?.speed ?? 1.0,
      loop: options?.loop ?? true,
      events: options?.events ?? [],
    })
    if (!this.currentState) this.currentState = name
    return this
  }

  addTransition(from: string, to: string, duration: number, condition?: () => boolean): this {
    this.transitions.push({ from, to, duration, condition })
    return this
  }

  /** Force transition to a state. */
  transitionTo(stateName: string, blendDuration = 0.3): void {
    if (stateName === this.currentState && !this.blendState) return
    const state = this.states.get(stateName)
    if (!state) return

    this.blendState = stateName
    this.blendTime = 0
    this.blendDuration = blendDuration
    this.firedEvents.clear()
  }

  /** Get current playing state name. */
  get current(): string {
    return this.blendState ?? this.currentState
  }

  /** Get current time within the active clip (seconds). */
  get time(): number {
    return this.currentTime
  }

  /**
   * Advance time and sample into skeleton.
   */
  update(dt: number, skeleton: Skeleton): void {
    // Check auto-transitions
    for (const trans of this.transitions) {
      if (trans.from === this.currentState && !this.blendState && trans.condition?.()) {
        this.transitionTo(trans.to, trans.duration)
        break
      }
    }

    const currentAnim = this.states.get(this.currentState)
    if (!currentAnim) return

    // Advance current time
    this.currentTime += dt * currentAnim.speed
    if (currentAnim.loop && currentAnim.clip.duration > 0) {
      this.currentTime = this.currentTime % currentAnim.clip.duration
    } else {
      this.currentTime = Math.min(this.currentTime, currentAnim.clip.duration)
    }

    // Fire events
    this.checkEvents(currentAnim)

    if (this.blendState) {
      const blendAnim = this.states.get(this.blendState)
      if (!blendAnim) {
        this.blendState = null
        return
      }

      this.blendTime += dt
      const blendWeight = Math.min(this.blendTime / this.blendDuration, 1.0)

      // Sample current at full weight, then blend target on top
      currentAnim.clip.sample(this.currentTime, skeleton, 1.0)
      const blendClipTime = this.blendTime * blendAnim.speed
      blendAnim.clip.sample(blendClipTime, skeleton, blendWeight)

      if (blendWeight >= 1.0) {
        // Transition complete
        const from = this.currentState
        this.currentState = this.blendState
        this.currentTime = blendClipTime
        this.blendState = null
        this.blendTime = 0
        this.firedEvents.clear()
        this.onStateChange?.(from, this.currentState)
      }
    } else {
      currentAnim.clip.sample(this.currentTime, skeleton, 1.0)
    }
  }

  private checkEvents(state: AnimState): void {
    if (state.clip.duration <= 0) return
    const normalizedTime = this.currentTime / state.clip.duration

    for (const event of state.events) {
      const key = `${state.name}:${event.name}:${Math.floor(this.currentTime / state.clip.duration)}`
      if (normalizedTime >= event.time && !this.firedEvents.has(key)) {
        this.firedEvents.add(key)
        this.onEvent?.(state.name, event.name)
      }
    }
  }
}
