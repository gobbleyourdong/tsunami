/**
 * Game state — shared across all subsystems.
 */

import { ScoreSystem } from '@engine/systems/score'
import { HealthSystem } from '@engine/systems/health'
import { CheckpointSystem } from '@engine/systems/checkpoint'
import { DifficultyManager } from '@engine/flow/difficulty'

export interface GameState {
  score: ScoreSystem
  playerHealth: HealthSystem
  difficulty: DifficultyManager
  checkpoint: CheckpointSystem
  wave: number
  maxWave: number
  paused: boolean
  gameOver: boolean
  phase: 'title' | 'tutorial' | 'arena' | 'gameover'
}
