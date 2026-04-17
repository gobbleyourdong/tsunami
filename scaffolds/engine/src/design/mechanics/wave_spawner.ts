// WaveSpawner — Phase 3 action-core mechanic.
//
// Spawns waves of enemy archetype on a rest timer. Scales base_count and
// rest_sec by the referenced Difficulty mechanic's spawnRateMul when one
// is wired. intro_delay_sec delays the first wave so the player can
// orient.

import type { Game } from '../../game/game'
import type { MechanicInstance, WaveSpawnerParams } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

interface DifficultyRuntimeShape {
  expose(): Record<string, unknown>
}

class WaveSpawnerRuntime implements MechanicRuntime {
  private params: WaveSpawnerParams
  private game!: Game
  private sinceLastWaveSec = 0
  private introRemainingSec: number
  private waveIndex = 0
  private totalSpawned = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as WaveSpawnerParams
    this.introRemainingSec = this.params.intro_delay_sec ?? 0
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    if (this.introRemainingSec > 0) {
      this.introRemainingSec -= dt
      return
    }
    this.sinceLastWaveSec += dt
    const restSec = this.params.rest_sec / this.spawnRateMul()
    if (this.sinceLastWaveSec >= restSec) {
      this.sinceLastWaveSec = 0
      this.spawnWave()
    }
  }

  dispose(): void { /* fire-and-forget spawns; no cleanup */ }

  expose(): Record<string, unknown> {
    return {
      waveIndex: this.waveIndex,
      totalSpawned: this.totalSpawned,
      nextWaveInSec: Math.max(0, this.params.rest_sec / this.spawnRateMul() - this.sinceLastWaveSec),
    }
  }

  private spawnRateMul(): number {
    if (!this.params.difficulty_ref) return 1
    // Engine wires runtime lookup by id via game.sceneManager.activeScene().properties.mechanic_runtimes
    const runtime = this.lookupRuntime(this.params.difficulty_ref as unknown as string)
    if (!runtime) return 1
    const exposed = runtime.expose()
    const m = exposed.spawnRateMul
    return typeof m === 'number' && m > 0 ? m : 1
  }

  private lookupRuntime(id: string): DifficultyRuntimeShape | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return null
    const props = active.properties as Record<string, unknown> | undefined
    const runtimes = props?.mechanic_runtimes as Record<string, DifficultyRuntimeShape> | undefined
    return runtimes?.[id] ?? null
  }

  private spawnWave(): void {
    const mul = this.spawnRateMul()
    const count = Math.max(1, Math.round(this.params.base_count * mul))
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return
    const spawn = (active as Record<string, (type: string, opts?: Record<string, unknown>) => void>)
      .spawn
    if (typeof spawn !== 'function') return
    const r = this.params.arena_radius
    for (let i = 0; i < count; i++) {
      const theta = (i / count) * Math.PI * 2
      const position: [number, number, number] = [Math.cos(theta) * r, 0, Math.sin(theta) * r]
      try {
        spawn(this.params.archetype as unknown as string, { position })
        this.totalSpawned += 1
      } catch { /* drop one spawn on scene transition races */ }
    }
    this.waveIndex += 1
  }
}

mechanicRegistry.register('WaveSpawner', (instance, game) => {
  const rt = new WaveSpawnerRuntime(instance)
  rt.init(game)
  return rt
})
