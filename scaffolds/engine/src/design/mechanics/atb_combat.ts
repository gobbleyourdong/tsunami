// ATBCombat — Phase 3 JRPG mechanic (v1.2).
//
// Active-Time-Battle loop. Each combatant has an ATB meter [0..1] that
// fills over time at a rate proportional to their speed * atb_speed.
// When a meter reaches 1.0 the actor's action window opens and a
// command queued via queueCommand() fires, resetting the meter to 0.
//
// Distinct from TurnBasedCombat by real-time pressure: enemies can
// act between player inputs if their meter fills first. Corpus
// heritage (JOB-A + JOB-F seed): FF4 (1991), Chrono Trigger (1995),
// FF6-IX, Grandia. Sister seed picked ATB over turn-based for the
// JRPG scaffold.

import type { Game } from '../../game/game'
import type { ATBCombatParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface Combatant {
  id: string
  team: 'party' | 'enemy'
  hp: number
  hp_max: number
  /** Base speed stat — drives ATB fill rate. */
  speed: number
  /** Meter [0..1]. When >=1 the actor's action window is open. */
  atb: number
  ko: boolean
  /** Back row halves damage dealt + received (FF5 mechanic). */
  row?: 'front' | 'back'
}

type CommandKind = 'attack' | 'magic' | 'item' | 'defend' | 'run' | 'skip'

interface PendingCommand {
  actor: string
  kind: CommandKind
  target?: string
  payload?: string
}

type CombatOutcome = 'ongoing' | 'victory' | 'defeat' | 'fled'

/** Base fill rate — a 10-speed actor fills in 10 seconds at atb_speed=1.0. */
const ATB_FILL_BASE = 0.01

class ATBCombatRuntime implements MechanicRuntime {
  private params: ATBCombatParams
  private game!: Game
  private combatants = new Map<string, Combatant>()
  private pending: PendingCommand[] = []
  private outcome: CombatOutcome = 'ongoing'
  private lastResolved: {
    actor: string; kind: CommandKind; target?: string; damage?: number
  } | null = null

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as ATBCombatParams
  }

  init(game: Game): void { this.game = game }

  update(dt: number): void {
    if (this.outcome !== 'ongoing') return

    // Advance ATB bars. Cap at 1.0 — the action window stays open
    // until a command fires or the actor is KO'd.
    for (const c of this.combatants.values()) {
      if (c.ko) continue
      c.atb = Math.min(1.0, c.atb + c.speed * ATB_FILL_BASE * this.params.atb_speed * dt)
    }

    // Fire queued commands for actors whose meter is full.
    for (let i = this.pending.length - 1; i >= 0; i--) {
      const cmd = this.pending[i]
      const actor = this.combatants.get(cmd.actor)
      if (!actor || actor.ko) { this.pending.splice(i, 1); continue }
      if (actor.atb < 1.0) continue
      this.resolve(cmd)
      actor.atb = 0
      this.pending.splice(i, 1)
      if (this.outcome !== 'ongoing') return
    }

    // Enemies auto-attack when their meter fills (simple default AI).
    for (const c of this.combatants.values()) {
      if (c.ko || c.team !== 'enemy' || c.atb < 1.0) continue
      const target = this.firstAliveOpponent('enemy')
      if (!target) break
      this.resolve({ actor: c.id, kind: 'attack', target: target.id })
      c.atb = 0
      if (this.outcome !== 'ongoing') return
    }
  }

  dispose(): void {
    this.combatants.clear()
    this.pending.length = 0
    this.outcome = 'ongoing'
    this.lastResolved = null
  }

  expose(): Record<string, unknown> {
    const meters: Record<string, number> = {}
    for (const [id, c] of this.combatants) meters[id] = c.atb
    return {
      outcome: this.outcome,
      atb_meters: meters,
      party_alive: this.aliveOnTeam('party').length,
      enemy_alive: this.aliveOnTeam('enemy').length,
      ready_actors: [...this.combatants.values()]
        .filter((c) => !c.ko && c.atb >= 1.0)
        .map((c) => c.id),
      last_resolved: this.lastResolved ? { ...this.lastResolved } : null,
    }
  }

  /** Public API — begin the fight. Combatants' ATB meters start at 0. */
  startCombat(party: Combatant[], enemies: Combatant[]): void {
    this.combatants.clear()
    for (const c of [...party, ...enemies]) {
      this.combatants.set(c.id, { ...c, atb: c.atb ?? 0, row: c.row ?? 'front' })
    }
    this.outcome = 'ongoing'
    this.lastResolved = null
  }

  /** Public API — queue a command for an actor. Fires when their meter fills. */
  queueCommand(actor: string, kind: CommandKind, target?: string, payload?: string): boolean {
    if (kind !== 'skip' && kind !== 'run' && !this.params.command_menu.includes(kind)) {
      return false
    }
    const c = this.combatants.get(actor)
    if (!c || c.ko || c.team !== 'party') return false
    this.pending = this.pending.filter((p) => p.actor !== actor)
    this.pending.push({ actor, kind, target, payload })
    return true
  }

  /** Public API — toggle row (front/back) if rules allow. FF5+ feature. */
  setRow(actor: string, row: 'front' | 'back'): boolean {
    if (!this.params.can_swap_rows) return false
    const c = this.combatants.get(actor)
    if (!c || c.team !== 'party') return false
    c.row = row
    return true
  }

  isActorReady(actor: string): boolean {
    const c = this.combatants.get(actor)
    return !!c && !c.ko && c.atb >= 1.0
  }

  getOutcome(): CombatOutcome { return this.outcome }
  getMeter(actor: string): number { return this.combatants.get(actor)?.atb ?? 0 }
  getCombatant(id: string): Combatant | undefined {
    const c = this.combatants.get(id)
    return c ? { ...c } : undefined
  }

  // ---- internals ----

  private resolve(cmd: PendingCommand): void {
    const actor = this.combatants.get(cmd.actor)
    if (!actor) return

    switch (cmd.kind) {
      case 'attack': {
        const tgt = cmd.target ? this.combatants.get(cmd.target) : this.firstAliveOpponent(actor.team)
        if (!tgt || tgt.ko) {
          this.lastResolved = { actor: cmd.actor, kind: cmd.kind }
          return
        }
        let dmg = Math.max(1, Math.floor(actor.speed * 0.5) + 5)
        if (actor.row === 'back') dmg = Math.max(1, Math.floor(dmg / 2))
        if (tgt.row === 'back') dmg = Math.max(1, Math.floor(dmg / 2))
        this.applyDamage(tgt, dmg)
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind, target: tgt.id, damage: dmg }
        return
      }
      case 'magic':
      case 'item':
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind, target: cmd.target }
        return
      case 'defend':
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind }
        return
      case 'run':
        if (actor.team === 'party') {
          this.outcome = 'fled'
          try { writeWorldFlag(this.game, 'combat.fled', true) } catch { /* ignore */ }
        }
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind }
        return
      case 'skip':
      default:
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind }
        return
    }
  }

  private applyDamage(target: Combatant, amount: number): void {
    target.hp = Math.max(0, target.hp - amount)
    if (target.hp === 0) target.ko = true
    this.combatants.set(target.id, target)
    this.checkVictoryDefeat()
  }

  private firstAliveOpponent(team: 'party' | 'enemy'): Combatant | undefined {
    const opp: 'party' | 'enemy' = team === 'party' ? 'enemy' : 'party'
    return this.aliveOnTeam(opp)[0]
  }

  private aliveOnTeam(team: 'party' | 'enemy'): Combatant[] {
    return [...this.combatants.values()].filter((c) => c.team === team && !c.ko)
  }

  private checkVictoryDefeat(): void {
    if (this.aliveOnTeam('enemy').length === 0) {
      this.outcome = 'victory'
      try { writeWorldFlag(this.game, 'combat.victory', true) } catch { /* ignore */ }
    } else if (this.aliveOnTeam('party').length === 0) {
      this.outcome = 'defeat'
      try { writeWorldFlag(this.game, 'combat.defeat', true) } catch { /* ignore */ }
    }
  }
}

mechanicRegistry.register('ATBCombat', (instance, game) => {
  const rt = new ATBCombatRuntime(instance)
  rt.init(game)
  return rt
})
