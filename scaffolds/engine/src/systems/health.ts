/**
 * Health/damage/stat system.
 * Supports damage types, resistances, shields, death callbacks.
 */

export type DamageType = 'physical' | 'fire' | 'ice' | 'lightning' | 'poison'

export interface DamageEvent {
  amount: number
  type: DamageType
  source?: unknown
}

export class HealthSystem {
  maxHealth: number
  health: number
  shield = 0
  maxShield = 0
  resistances: Partial<Record<DamageType, number>> = {}  // 0-1, reduces damage

  isDead = false

  onDamage?: (event: DamageEvent, actualDamage: number) => void
  onDeath?: () => void
  onHeal?: (amount: number) => void

  constructor(maxHealth: number) {
    this.maxHealth = maxHealth
    this.health = maxHealth
  }

  takeDamage(event: DamageEvent): number {
    if (this.isDead) return 0

    let dmg = event.amount
    const resistance = this.resistances[event.type] ?? 0
    dmg *= (1 - resistance)
    dmg = Math.max(0, dmg)

    // Shield absorbs first
    if (this.shield > 0) {
      const shieldAbsorb = Math.min(this.shield, dmg)
      this.shield -= shieldAbsorb
      dmg -= shieldAbsorb
    }

    this.health = Math.max(0, this.health - dmg)
    this.onDamage?.(event, dmg)

    if (this.health <= 0 && !this.isDead) {
      this.isDead = true
      this.onDeath?.()
    }

    return dmg
  }

  heal(amount: number): void {
    if (this.isDead) return
    const actual = Math.min(amount, this.maxHealth - this.health)
    this.health += actual
    if (actual > 0) this.onHeal?.(actual)
  }

  revive(healthPercent = 1): void {
    this.isDead = false
    this.health = this.maxHealth * healthPercent
  }

  get healthPercent(): number {
    return this.health / this.maxHealth
  }

  serialize(): { health: number; shield: number; isDead: boolean } {
    return { health: this.health, shield: this.shield, isDead: this.isDead }
  }

  deserialize(data: { health: number; shield: number; isDead: boolean }): void {
    this.health = data.health
    this.shield = data.shield
    this.isDead = data.isDead
  }
}
