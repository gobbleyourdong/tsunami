/**
 * Difficulty curve manager — S-curve ramp from easy → hard.
 * Adjusts enemy stats, spawn rates, time limits based on progression.
 */

export interface DifficultyParams {
  enemyHealthMul: number
  enemyDamageMul: number
  enemySpeedMul: number
  spawnRateMul: number
  timeLimitMul: number
  [key: string]: number
}

const DEFAULT_EASY: DifficultyParams = {
  enemyHealthMul: 0.5,
  enemyDamageMul: 0.5,
  enemySpeedMul: 0.7,
  spawnRateMul: 0.5,
  timeLimitMul: 1.5,
}

const DEFAULT_HARD: DifficultyParams = {
  enemyHealthMul: 2.0,
  enemyDamageMul: 2.0,
  enemySpeedMul: 1.5,
  spawnRateMul: 2.0,
  timeLimitMul: 0.6,
}

export class DifficultyManager {
  private level = 0       // 0-1 normalized progression
  private maxLevel = 1
  private easyParams: DifficultyParams
  private hardParams: DifficultyParams

  constructor(easy?: Partial<DifficultyParams>, hard?: Partial<DifficultyParams>) {
    this.easyParams = { ...DEFAULT_EASY, ...(easy as DifficultyParams) }
    this.hardParams = { ...DEFAULT_HARD, ...(hard as DifficultyParams) }
  }

  /** Set progression 0-1. */
  setLevel(level: number): void {
    this.level = Math.max(0, Math.min(1, level))
  }

  /** Get current difficulty level 0-1. */
  getLevel(): number {
    return this.level
  }

  /** S-curve interpolation (smooth ramp, steep in middle). */
  private sCurve(t: number): number {
    // Hermite smoothstep: 3t² - 2t³
    return t * t * (3 - 2 * t)
  }

  /** Get interpolated difficulty parameter. */
  get(param: keyof DifficultyParams): number {
    const t = this.sCurve(this.level)
    const easy = this.easyParams[param] ?? 1
    const hard = this.hardParams[param] ?? 1
    return easy + (hard - easy) * t
  }

  /** Get all current parameters as an object. */
  getAll(): DifficultyParams {
    const result: Record<string, number> = {}
    const keys = new Set([...Object.keys(this.easyParams), ...Object.keys(this.hardParams)])
    for (const key of keys) {
      result[key] = this.get(key as keyof DifficultyParams)
    }
    return result as DifficultyParams
  }

  /** Auto-advance difficulty based on player score/level/time. */
  advanceByScore(score: number, maxScore: number): void {
    this.setLevel(score / maxScore)
  }

  advanceByLevel(currentLevel: number, totalLevels: number): void {
    this.setLevel(currentLevel / totalLevels)
  }
}
