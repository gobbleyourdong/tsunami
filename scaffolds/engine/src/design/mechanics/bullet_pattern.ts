// BulletPattern — Phase 1 content-multiplier mechanic.
//
// Emits bullet entities from an emitter archetype in one of six layout
// families (line / ring / spiral / spread / aimed / custom). Patterns
// are sequenced either round-robin, weighted, or via a fixed script.
// v1 ships layout generators for line/ring/spiral/spread/aimed; custom
// is a noop hook left for user extension.
//
// Each bullet is spawned through the active SceneBuilder's spawn() with
// the bullet_archetype's controller+mesh+components baked into an entity
// at (x,y) relative to the emitter's current world position. Bullet
// velocity is passed via entity.properties.initial_velocity so the
// physics system can apply it on spawn.

import type { Game } from '../../game/game'
import type {
  BulletPatternParams,
  MechanicInstance,
} from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type Pattern = BulletPatternParams['patterns'][number]

class BulletPatternRuntime implements MechanicRuntime {
  private params: BulletPatternParams
  private game!: Game
  private patternIndex = 0
  private cooldownMs = 0
  private bulletsFired = 0

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as BulletPatternParams
  }

  init(game: Game): void {
    this.game = game
  }

  update(dt: number): void {
    const dtMs = dt * 1000
    this.cooldownMs -= dtMs
    if (this.cooldownMs > 0) return
    const pattern = this.selectPattern()
    if (!pattern) return
    this.firePattern(pattern)
    this.cooldownMs = pattern.duration_ms ?? 500
    this.advanceSelector()
  }

  dispose(): void { /* fire-and-forget; no cleanup */ }

  expose(): Record<string, unknown> {
    return {
      bulletsFired: this.bulletsFired,
      currentPattern: this.selectPattern()?.name ?? null,
    }
  }

  // ───────── selection ─────────

  private selectPattern(): Pattern | null {
    const patterns = this.params.patterns ?? []
    if (patterns.length === 0) return null
    if (this.params.sequence === 'round_robin') {
      return patterns[this.patternIndex % patterns.length]
    }
    if (this.params.sequence === 'weighted') {
      const total = patterns.reduce((s, p) => s + ((p.layout_params?.weight as number | undefined) ?? 1), 0)
      let r = Math.random() * total
      for (const p of patterns) {
        r -= (p.layout_params?.weight as number | undefined) ?? 1
        if (r <= 0) return p
      }
      return patterns[patterns.length - 1]
    }
    if (this.params.sequence === 'scripted' && this.params.scripted_order) {
      const name = this.params.scripted_order[
        this.patternIndex % this.params.scripted_order.length
      ]
      return patterns.find(p => p.name === name) ?? patterns[0]
    }
    return patterns[0]
  }

  private advanceSelector(): void {
    this.patternIndex = (this.patternIndex + 1) % Math.max(
      1, this.params.patterns?.length ?? 1,
    )
  }

  // ───────── firing ─────────

  private firePattern(pattern: Pattern): void {
    const emitterPos = this.findEmitterWorldPos()
    if (!emitterPos) return
    const bullets = this.generateBulletSpawns(pattern, emitterPos)
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return
    const spawn = (active as Record<string, (type: string, opts?: Record<string, unknown>) => void>)
      .spawn
    if (typeof spawn !== 'function') return
    for (const b of bullets) {
      try {
        spawn(pattern.bullet_archetype as unknown as string, {
          position: b.position,
          properties: { initial_velocity: b.velocity },
        })
        this.bulletsFired += 1
      } catch { /* scene may be transitioning; drop the shot */ }
    }
  }

  private generateBulletSpawns(
    pattern: Pattern,
    emitter: [number, number, number],
  ): Array<{ position: [number, number, number]; velocity: [number, number, number] }> {
    const p = pattern.layout_params ?? {}
    const count = Math.max(1, Math.round((p.count as number | undefined) ?? 1))
    const speed = (p.speed as number | undefined) ?? 10
    const spread = (p.spread_deg as number | undefined) ?? 60
    const baseAngle = ((p.angle_deg as number | undefined) ?? 0) * Math.PI / 180

    const out: Array<{ position: [number, number, number]; velocity: [number, number, number] }> = []
    switch (pattern.layout) {
      case 'line': {
        const step = (p.spacing as number | undefined) ?? 0.5
        for (let i = 0; i < count; i++) {
          const off = (i - (count - 1) / 2) * step
          out.push({
            position: [emitter[0] + off * Math.cos(baseAngle),
                       emitter[1], emitter[2] + off * Math.sin(baseAngle)],
            velocity: [Math.cos(baseAngle) * speed, 0, Math.sin(baseAngle) * speed],
          })
        }
        return out
      }
      case 'ring': {
        for (let i = 0; i < count; i++) {
          const a = (i / count) * Math.PI * 2 + baseAngle
          out.push({
            position: [...emitter] as [number, number, number],
            velocity: [Math.cos(a) * speed, 0, Math.sin(a) * speed],
          })
        }
        return out
      }
      case 'spiral': {
        const spiralStep = (p.spiral_step_deg as number | undefined) ?? 30
        for (let i = 0; i < count; i++) {
          const a = baseAngle + (i * spiralStep * Math.PI / 180)
          out.push({
            position: [...emitter] as [number, number, number],
            velocity: [Math.cos(a) * speed, 0, Math.sin(a) * speed],
          })
        }
        return out
      }
      case 'spread': {
        const half = (spread * Math.PI / 180) / 2
        for (let i = 0; i < count; i++) {
          const t = count === 1 ? 0.5 : i / (count - 1)
          const a = baseAngle - half + t * (half * 2)
          out.push({
            position: [...emitter] as [number, number, number],
            velocity: [Math.cos(a) * speed, 0, Math.sin(a) * speed],
          })
        }
        return out
      }
      case 'aimed': {
        const target = this.findAimTarget()
        if (!target) {
          out.push({
            position: [...emitter] as [number, number, number],
            velocity: [Math.cos(baseAngle) * speed, 0, Math.sin(baseAngle) * speed],
          })
          return out
        }
        const dx = target[0] - emitter[0]
        const dz = target[2] - emitter[2]
        const len = Math.hypot(dx, dz) || 1
        out.push({
          position: [...emitter] as [number, number, number],
          velocity: [(dx / len) * speed, 0, (dz / len) * speed],
        })
        return out
      }
      case 'custom':
      default:
        return out
    }
  }

  private findEmitterWorldPos(): [number, number, number] | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const emitter = entities.find(e => e.type === this.params.emitter_archetype as unknown as string)
    if (!emitter) return null
    return (emitter.position as [number, number, number] | undefined) ?? [0, 0, 0]
  }

  private findAimTarget(): [number, number, number] | null {
    // Heuristic: target the first archetype tagged 'player' in the active
    // scene. Future: an explicit target_tag param on BulletPatternParams.
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const target = entities.find(e => {
      const props = e.properties as Record<string, unknown> | undefined
      const tags = (props?.tags ?? []) as string[]
      return Array.isArray(tags) && tags.includes('player')
    })
    if (!target) return null
    return (target.position as [number, number, number] | undefined) ?? null
  }
}

mechanicRegistry.register('BulletPattern', (instance, game) => {
  const rt = new BulletPatternRuntime(instance)
  rt.init(game)
  return rt
})
