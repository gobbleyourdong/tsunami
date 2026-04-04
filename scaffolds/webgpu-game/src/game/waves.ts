/**
 * Wave manager — spawns escalating waves of enemies.
 */

import type { GameState } from './state'
import { EnemyManager, EnemyType } from './enemies'

interface WaveDefinition {
  enemies: { type: EnemyType; count: number }[]
  spawnDelay: number  // seconds between spawns
}

const WAVE_DEFS: WaveDefinition[] = [
  // Wave 1-3: Rushers only (tutorial)
  { enemies: [{ type: 'rusher', count: 3 }], spawnDelay: 0.5 },
  { enemies: [{ type: 'rusher', count: 5 }], spawnDelay: 0.4 },
  { enemies: [{ type: 'rusher', count: 4 }, { type: 'shooter', count: 1 }], spawnDelay: 0.4 },

  // Wave 4-6: Mixed
  { enemies: [{ type: 'rusher', count: 4 }, { type: 'shooter', count: 3 }], spawnDelay: 0.3 },
  { enemies: [{ type: 'shooter', count: 4 }, { type: 'rusher', count: 3 }], spawnDelay: 0.3 },
  { enemies: [{ type: 'rusher', count: 3 }, { type: 'shooter', count: 3 }, { type: 'tank', count: 1 }], spawnDelay: 0.3 },

  // Wave 7-9: Hard
  { enemies: [{ type: 'tank', count: 2 }, { type: 'shooter', count: 4 }], spawnDelay: 0.25 },
  { enemies: [{ type: 'rusher', count: 6 }, { type: 'tank', count: 2 }, { type: 'shooter', count: 3 }], spawnDelay: 0.2 },
  { enemies: [{ type: 'tank', count: 3 }, { type: 'shooter', count: 5 }, { type: 'rusher', count: 4 }], spawnDelay: 0.15 },

  // Wave 10: BOSS + minions
  { enemies: [{ type: 'boss', count: 1 }, { type: 'rusher', count: 4 }, { type: 'shooter', count: 3 }], spawnDelay: 0.3 },
]

export class WaveManager {
  private state: GameState
  private enemies: EnemyManager
  private spawnQueue: { type: EnemyType; delay: number }[] = []
  private spawnTimer = 0
  private waveCompleteTimer = 0
  private betweenWaves = false
  private wavePauseDuration = 3

  onWaveStart?: (wave: number) => void
  onWaveComplete?: (wave: number) => void
  onAllWavesComplete?: () => void

  constructor(state: GameState, enemies: EnemyManager) {
    this.state = state
    this.enemies = enemies
  }

  startNextWave(): void {
    this.state.wave++
    if (this.state.wave > this.state.maxWave) {
      this.onAllWavesComplete?.()
      return
    }

    this.state.difficulty.advanceByLevel(this.state.wave, this.state.maxWave)

    const def = WAVE_DEFS[Math.min(this.state.wave - 1, WAVE_DEFS.length - 1)]
    this.spawnQueue = []
    let delay = 0
    for (const group of def.enemies) {
      for (let i = 0; i < group.count; i++) {
        this.spawnQueue.push({ type: group.type, delay })
        delay += def.spawnDelay
      }
    }
    this.spawnTimer = 0
    this.betweenWaves = false

    // Save checkpoint at wave start
    this.state.checkpoint.setCheckpoint(`wave_${this.state.wave}`)
    this.state.checkpoint.save('auto')

    this.onWaveStart?.(this.state.wave)
  }

  update(dt: number): void {
    // Between-wave pause
    if (this.betweenWaves) {
      this.waveCompleteTimer -= dt
      if (this.waveCompleteTimer <= 0) {
        this.startNextWave()
      }
      return
    }

    // Spawn from queue
    this.spawnTimer += dt
    while (this.spawnQueue.length > 0 && this.spawnTimer >= this.spawnQueue[0].delay) {
      const spawn = this.spawnQueue.shift()!
      const pos = this.randomEdgePosition()
      this.enemies.spawn(spawn.type, pos.x, pos.y)
    }

    // Check wave complete
    if (this.spawnQueue.length === 0 && this.enemies.aliveCount === 0) {
      this.onWaveComplete?.(this.state.wave)
      if (this.state.wave >= this.state.maxWave) {
        this.onAllWavesComplete?.()
      } else {
        this.betweenWaves = true
        this.waveCompleteTimer = this.wavePauseDuration
      }
    }
  }

  private randomEdgePosition(): { x: number; y: number } {
    const bound = 12
    const side = Math.floor(Math.random() * 4)
    switch (side) {
      case 0: return { x: -bound, y: (Math.random() - 0.5) * bound * 2 } // left
      case 1: return { x: bound, y: (Math.random() - 0.5) * bound * 2 }  // right
      case 2: return { x: (Math.random() - 0.5) * bound * 2, y: -bound } // top
      default: return { x: (Math.random() - 0.5) * bound * 2, y: bound } // bottom
    }
  }
}
