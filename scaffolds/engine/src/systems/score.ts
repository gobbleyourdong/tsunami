/**
 * Score/combo system.
 * Tracks points, combo multiplier, high scores.
 */

export class ScoreSystem {
  score = 0
  combo = 0
  maxCombo = 0
  multiplier = 1
  highScore = 0

  // Combo timing
  private comboTimer = 0
  private comboWindow: number  // seconds before combo drops

  onScoreChange?: (score: number, delta: number) => void
  onComboChange?: (combo: number, multiplier: number) => void
  onHighScore?: (score: number) => void

  constructor(comboWindow = 2) {
    this.comboWindow = comboWindow
  }

  /** Add points (modified by current multiplier). */
  addPoints(base: number): number {
    const actual = Math.floor(base * this.multiplier)
    this.score += actual
    this.combo++
    this.comboTimer = 0

    if (this.combo > this.maxCombo) this.maxCombo = this.combo
    this.multiplier = 1 + Math.floor(this.combo / 5) * 0.5  // +0.5x every 5 combo

    this.onScoreChange?.(this.score, actual)
    this.onComboChange?.(this.combo, this.multiplier)

    if (this.score > this.highScore) {
      this.highScore = this.score
      this.onHighScore?.(this.highScore)
    }

    return actual
  }

  /** Update combo timer. Call every frame. */
  update(dt: number): void {
    if (this.combo > 0) {
      this.comboTimer += dt
      if (this.comboTimer >= this.comboWindow) {
        this.dropCombo()
      }
    }
  }

  /** Force-drop the combo. */
  dropCombo(): void {
    if (this.combo > 0) {
      this.combo = 0
      this.multiplier = 1
      this.onComboChange?.(0, 1)
    }
  }

  reset(): void {
    this.score = 0
    this.combo = 0
    this.maxCombo = 0
    this.multiplier = 1
    this.comboTimer = 0
  }

  serialize(): { score: number; highScore: number; maxCombo: number } {
    return { score: this.score, highScore: this.highScore, maxCombo: this.maxCombo }
  }

  deserialize(data: { score: number; highScore: number; maxCombo: number }): void {
    this.score = data.score
    this.highScore = data.highScore
    this.maxCombo = data.maxCombo
  }
}
