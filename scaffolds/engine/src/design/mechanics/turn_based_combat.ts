// TurnBasedCombat — Phase 3 JRPG mechanic (v1.2).
//
// Discrete-turn combat loop. Each round, combatants act in an order
// determined by `turn_order` (speed_desc | fixed | random). Players
// queue commands through `queueCommand(actor, command, target)`;
// the runtime resolves them one per update tick when it's that
// actor's turn. Distinct from ATBCombat by the hard turn-boundary
// semantics — no real-time meter pressure.
//
// Corpus heritage (JOB-A): Dragon Quest (1986+), Final Fantasy I
// (1987), Pokemon (1996), most early-JRPG lineage.

import type { Game } from '../../game/game'
import type { TurnBasedCombatParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'
import { writeWorldFlag } from './world_flags'

interface Combatant {
  id: string
  team: 'party' | 'enemy'
  hp: number
  hp_max: number
  speed: number
  /** true when HP ≤ 0 — skipped in turn rotation. */
  ko: boolean
}

type CommandKind = 'attack' | 'magic' | 'item' | 'run' | 'defend' | 'skip'

interface PendingCommand {
  actor: string
  kind: CommandKind
  target?: string
  /** Payload for magic/item (spell id, item id, etc.). */
  payload?: string
}

type CombatOutcome = 'ongoing' | 'victory' | 'defeat' | 'fled'

class TurnBasedCombatRuntime implements MechanicRuntime {
  private params: TurnBasedCombatParams
  private game!: Game
  private combatants = new Map<string, Combatant>()
  private queue: string[] = []
  private queueIndex = 0
  private round = 0
  private pending: PendingCommand[] = []
  private outcome: CombatOutcome = 'ongoing'
  private lastResolved: { actor: string; kind: CommandKind; target?: string; damage?: number } | null = null

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as TurnBasedCombatParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    if (this.outcome !== 'ongoing') return
    if (this.queue.length === 0) return

    // If the current actor has a queued command, resolve it and advance.
    const actor = this.queue[this.queueIndex]
    const cmd = this.pending.find((c) => c.actor === actor)
    if (!cmd) return

    this.resolve(cmd)
    this.pending = this.pending.filter((c) => c !== cmd)
    this.advance()

    if (this.outcome === 'ongoing' && this.queueIndex === 0) {
      this.round += 1
    }
  }

  dispose(): void {
    this.combatants.clear()
    this.queue.length = 0
    this.pending.length = 0
    this.outcome = 'ongoing'
    this.lastResolved = null
  }

  expose(): Record<string, unknown> {
    const actor = this.queue[this.queueIndex]
    return {
      round: this.round,
      current_actor: actor ?? null,
      queue: [...this.queue],
      outcome: this.outcome,
      party_alive: this.aliveOnTeam('party').length,
      enemy_alive: this.aliveOnTeam('enemy').length,
      last_resolved: this.lastResolved ? { ...this.lastResolved } : null,
    }
  }

  /** Public API — seed the fight. Call once when combat begins. */
  startCombat(party: Combatant[], enemies: Combatant[]): void {
    this.combatants.clear()
    for (const c of [...party, ...enemies]) this.combatants.set(c.id, { ...c })
    this.round = 1
    this.queueIndex = 0
    this.outcome = 'ongoing'
    this.rebuildQueue()
  }

  /** Public API — queue a command for an actor whose turn is pending. */
  queueCommand(actor: string, kind: CommandKind, target?: string, payload?: string): boolean {
    // Validate: command must be in the configured menu (attack/magic/item/run).
    // `defend` and `skip` bypass menu validation — they're always allowed.
    if (kind !== 'defend' && kind !== 'skip' && !this.params.command_menu.includes(kind)) {
      return false
    }
    if (kind === 'run' && !this.params.can_flee) return false

    const c = this.combatants.get(actor)
    if (!c || c.ko) return false
    // Replace any existing queued command for this actor.
    this.pending = this.pending.filter((p) => p.actor !== actor)
    this.pending.push({ actor, kind, target, payload })
    return true
  }

  /** True if `actor` is the actor whose turn is currently open. */
  isActorReady(actor: string): boolean {
    return this.queue[this.queueIndex] === actor
  }

  getOutcome(): CombatOutcome { return this.outcome }
  getRound(): number { return this.round }
  getQueue(): string[] { return [...this.queue] }
  getCombatant(id: string): Combatant | undefined {
    const c = this.combatants.get(id)
    return c ? { ...c } : undefined
  }

  // ---- internals ----

  private rebuildQueue(): void {
    const alive = [...this.combatants.values()].filter((c) => !c.ko)
    let ordered: Combatant[]
    switch (this.params.turn_order) {
      case 'speed_desc':
        ordered = alive.slice().sort((a, b) => b.speed - a.speed)
        break
      case 'random':
        ordered = alive.slice().sort(() => Math.random() - 0.5)
        break
      case 'fixed':
      default:
        // Party first in insertion order, then enemies.
        ordered = [
          ...alive.filter((c) => c.team === 'party'),
          ...alive.filter((c) => c.team === 'enemy'),
        ]
        break
    }
    this.queue = ordered.map((c) => c.id)
    this.queueIndex = 0
  }

  private advance(): void {
    // Step past KO'd actors.
    do {
      this.queueIndex += 1
      if (this.queueIndex >= this.queue.length) {
        this.queueIndex = 0
        this.rebuildQueue()
        if (this.queue.length === 0) break
      }
      const next = this.combatants.get(this.queue[this.queueIndex])
      if (!next || !next.ko) break
    } while (true)
    this.checkVictoryDefeat()
  }

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
        const dmg = Math.max(1, Math.floor(actor.speed * 0.5) + 5)
        this.applyDamage(tgt, dmg)
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind, target: tgt.id, damage: dmg }
        return
      }
      case 'magic':
      case 'item': {
        // Payload-driven; the scaffold layer maps payload → effect. Here
        // we just record the resolution so HUD / menus can show it.
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind, target: cmd.target }
        return
      }
      case 'run': {
        if (actor.team === 'party' && this.params.can_flee) {
          this.outcome = 'fled'
          try { writeWorldFlag(this.game, 'combat.fled', true) } catch { /* ignore */ }
        }
        this.lastResolved = { actor: cmd.actor, kind: cmd.kind }
        return
      }
      case 'defend':
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

mechanicRegistry.register('TurnBasedCombat', (instance, game) => {
  const rt = new TurnBasedCombatRuntime(instance)
  rt.init(game)
  return rt
})
