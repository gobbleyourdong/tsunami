/**
 * GameOver scene — shown on player HP = 0.
 * Minimal: title, "Continue from last checkpoint" / "Restart" options.
 * Composes CheckpointProgression for the resume path.
 */

import config from '../../data/config.json'

export class GameOver {
  readonly name = 'gameover'
  description = 'game-over screen with continue / restart options'

  setup(): void {
    // No mechanics to mount at game-over — just input-driven menu.
  }

  teardown(): void { /* no state */ }

  /** Which title/subtitle to show. */
  getTitle(): string {
    return config.title_gameover ?? 'You died. Continue?'
  }
}
