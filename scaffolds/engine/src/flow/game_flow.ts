/**
 * Game flow — high-level pipeline that wires scene manager to standard game phases.
 * Title → Customization → Intro → Tutorial → Gameplay → Game Over → loop.
 */

import { SceneManager, GameScene, TransitionType } from './scene_manager'

export interface FlowStep {
  scene: string
  transition?: TransitionType
  duration?: number      // transition duration ms
  condition?: string     // expression key that triggers advancing to next step
}

export class GameFlow {
  private sceneManager: SceneManager
  private steps: FlowStep[] = []
  private currentStepIndex = 0
  private conditions = new Map<string, boolean>()
  private paused = false

  onPause?: () => void
  onResume?: () => void

  constructor(sceneManager: SceneManager) {
    this.sceneManager = sceneManager
  }

  /** Define the game flow as ordered steps. */
  setFlow(steps: FlowStep[]): void {
    this.steps = steps
  }

  /** Start the flow from the first step. */
  async start(): Promise<void> {
    this.currentStepIndex = 0
    await this.gotoCurrentStep()
  }

  /** Advance to the next step in the flow. */
  async next(): Promise<void> {
    this.currentStepIndex++
    if (this.currentStepIndex >= this.steps.length) {
      this.currentStepIndex = 0 // loop back
    }
    await this.gotoCurrentStep()
  }

  /** Jump to a specific step by scene name. */
  async gotoScene(sceneName: string): Promise<void> {
    const idx = this.steps.findIndex(s => s.scene === sceneName)
    if (idx >= 0) {
      this.currentStepIndex = idx
      await this.gotoCurrentStep()
    }
  }

  /** Set a condition flag (checked for auto-advancing). */
  setCondition(key: string, value = true): void {
    this.conditions.set(key, value)
  }

  /** Get current step index. */
  get currentStep(): number { return this.currentStepIndex }

  /** Get current scene name. */
  get currentScene(): string {
    return this.steps[this.currentStepIndex]?.scene ?? ''
  }

  get isPaused(): boolean { return this.paused }

  /** Toggle pause state. */
  togglePause(): void {
    this.paused = !this.paused
    if (this.paused) this.onPause?.()
    else this.onResume?.()
  }

  /** Call every frame. Checks conditions and drives scene manager. */
  update(dt: number): void {
    if (this.paused) return

    // Check if current step's condition is met for auto-advance
    const step = this.steps[this.currentStepIndex]
    if (step?.condition && this.conditions.get(step.condition)) {
      this.conditions.delete(step.condition)
      this.next()
      return
    }

    this.sceneManager.update(dt)
  }

  render(dt: number): void {
    if (!this.paused) {
      this.sceneManager.render(dt)
    }
  }

  private async gotoCurrentStep(): Promise<void> {
    const step = this.steps[this.currentStepIndex]
    if (!step) return
    await this.sceneManager.goto(step.scene, {
      type: step.transition ?? 'fade',
      duration: step.duration ?? 500,
    })
  }
}
