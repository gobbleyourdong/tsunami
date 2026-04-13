/**
 * Tutorial overlay system — step-by-step instructions.
 * Highlights UI regions, shows prompts, waits for player actions.
 */

export interface TutorialStep {
  id: string
  message: string
  highlight?: { x: number; y: number; width: number; height: number }  // screen region
  waitForAction?: string  // action name to wait for
  duration?: number       // auto-advance after N seconds (0 = wait for action/manual)
  onEnter?: () => void
  onComplete?: () => void
}

export class TutorialSystem {
  private steps: TutorialStep[] = []
  private currentIndex = -1
  private timer = 0
  private _active = false
  private completedSteps = new Set<string>()

  onStepChange?: (step: TutorialStep, index: number) => void
  onComplete?: () => void

  get active(): boolean { return this._active }

  get currentStep(): TutorialStep | null {
    if (this.currentIndex < 0 || this.currentIndex >= this.steps.length) return null
    return this.steps[this.currentIndex]
  }

  get stepIndex(): number { return this.currentIndex }
  get totalSteps(): number { return this.steps.length }

  /** Define tutorial steps and start. */
  start(steps: TutorialStep[]): void {
    this.steps = steps
    this.currentIndex = -1
    this._active = true
    this.nextStep()
  }

  /** Advance to next step. */
  nextStep(): void {
    if (this.currentStep) {
      this.currentStep.onComplete?.()
      this.completedSteps.add(this.currentStep.id)
    }

    this.currentIndex++
    this.timer = 0

    if (this.currentIndex >= this.steps.length) {
      this._active = false
      this.onComplete?.()
      return
    }

    const step = this.steps[this.currentIndex]
    step.onEnter?.()
    this.onStepChange?.(step, this.currentIndex)
  }

  /** Notify that a player action occurred (for waitForAction steps). */
  notifyAction(action: string): void {
    if (!this._active) return
    const step = this.currentStep
    if (step?.waitForAction === action) {
      this.nextStep()
    }
  }

  /** Call every frame — handles duration-based auto-advance. */
  update(dt: number): void {
    if (!this._active) return
    const step = this.currentStep
    if (!step) return

    if (step.duration && step.duration > 0) {
      this.timer += dt
      if (this.timer >= step.duration) {
        this.nextStep()
      }
    }
  }

  /** Skip the entire tutorial. */
  skip(): void {
    this._active = false
    this.onComplete?.()
  }

  /** Check if a specific step was completed. */
  wasCompleted(stepId: string): boolean {
    return this.completedSteps.has(stepId)
  }
}
