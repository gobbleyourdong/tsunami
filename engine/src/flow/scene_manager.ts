/**
 * Scene manager — load/unload/transition between game scenes.
 * Each scene has lifecycle hooks: init, enter, update, render, exit.
 * Transitions: fade, slide, instant.
 */

export type TransitionType = 'instant' | 'fade' | 'slide-left' | 'slide-right' | 'slide-up'

export interface GameScene {
  name: string
  init?(): void | Promise<void>
  enter?(from?: string): void
  update?(dt: number): void
  render?(dt: number): void
  exit?(to?: string): void
  destroy?(): void
}

export interface SceneTransition {
  type: TransitionType
  duration: number  // ms
}

type TransitionState = 'none' | 'out' | 'in'

export class SceneManager {
  private scenes = new Map<string, GameScene>()
  private currentScene: GameScene | null = null
  private currentName = ''

  // Transition state
  private transitionState: TransitionState = 'none'
  private transitionProgress = 0
  private transitionConfig: SceneTransition = { type: 'instant', duration: 0 }
  private pendingScene = ''
  private transitionElapsed = 0

  onTransitionProgress?: (progress: number, phase: 'out' | 'in') => void
  onSceneChange?: (from: string, to: string) => void

  /** Register a scene. */
  add(scene: GameScene): this {
    this.scenes.set(scene.name, scene)
    return this
  }

  /** Remove a registered scene. */
  remove(name: string): void {
    const scene = this.scenes.get(name)
    scene?.destroy?.()
    this.scenes.delete(name)
  }

  /** Get current scene name. */
  get current(): string {
    return this.currentName
  }

  /** Is a transition currently in progress? */
  get isTransitioning(): boolean {
    return this.transitionState !== 'none'
  }

  /** Transition progress 0-1 (for rendering overlays). */
  get progress(): number {
    return this.transitionProgress
  }

  /** Go to a scene with optional transition. */
  async goto(name: string, transition?: Partial<SceneTransition>): Promise<void> {
    const scene = this.scenes.get(name)
    if (!scene) throw new Error(`Scene '${name}' not registered`)

    const config: SceneTransition = {
      type: transition?.type ?? 'instant',
      duration: transition?.duration ?? 300,
    }

    if (config.type === 'instant' || !this.currentScene) {
      await this.switchImmediate(name, scene)
    } else {
      this.pendingScene = name
      this.transitionConfig = config
      this.transitionState = 'out'
      this.transitionElapsed = 0
      this.transitionProgress = 0
    }
  }

  private async switchImmediate(name: string, scene: GameScene): Promise<void> {
    const from = this.currentName
    this.currentScene?.exit?.(name)
    await scene.init?.()
    this.currentScene = scene
    this.currentName = name
    scene.enter?.(from)
    this.onSceneChange?.(from, name)
  }

  /** Call every frame — drives transition animation + current scene update. */
  update(dt: number): void {
    if (this.transitionState !== 'none') {
      this.transitionElapsed += dt * 1000
      const halfDuration = this.transitionConfig.duration / 2

      if (this.transitionState === 'out') {
        this.transitionProgress = Math.min(this.transitionElapsed / halfDuration, 1)
        this.onTransitionProgress?.(this.transitionProgress, 'out')

        if (this.transitionElapsed >= halfDuration) {
          // Switch scene at midpoint
          const scene = this.scenes.get(this.pendingScene)!
          const from = this.currentName
          this.currentScene?.exit?.(this.pendingScene)
          scene.init?.() // sync init during transition
          this.currentScene = scene
          this.currentName = this.pendingScene
          scene.enter?.(from)
          this.onSceneChange?.(from, this.pendingScene)

          this.transitionState = 'in'
          this.transitionElapsed = 0
        }
      } else if (this.transitionState === 'in') {
        this.transitionProgress = 1 - Math.min(this.transitionElapsed / halfDuration, 1)
        this.onTransitionProgress?.(this.transitionProgress, 'in')

        if (this.transitionElapsed >= halfDuration) {
          this.transitionState = 'none'
          this.transitionProgress = 0
          this.pendingScene = ''
        }
      }
    }

    this.currentScene?.update?.(dt)
  }

  /** Call every frame for rendering. */
  render(dt: number): void {
    this.currentScene?.render?.(dt)
  }

  /** Get a registered scene by name. */
  get(name: string): GameScene | undefined {
    return this.scenes.get(name)
  }

  /** List all registered scene names. */
  list(): string[] {
    return Array.from(this.scenes.keys())
  }

  destroy(): void {
    for (const scene of this.scenes.values()) scene.destroy?.()
    this.scenes.clear()
    this.currentScene = null
  }
}
