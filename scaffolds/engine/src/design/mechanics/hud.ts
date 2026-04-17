// HUD — Phase 3 action-core mechanic.
//
// Collects named values from archetypes, mechanics, or singletons each
// frame and publishes them via expose(). The renderer's HUD overlay reads
// expose().rows at draw time. v1 doesn't do the actual DOM/canvas draw —
// that's the harness's job. This mechanic just produces the row list.

import type { Game } from '../../game/game'
import type { HudParams, MechanicInstance } from '../schema'
import { mechanicRegistry, type MechanicRuntime } from './index'

type HudField = HudParams['fields'][number]

interface RuntimeShape { expose(): Record<string, unknown> }

class HudRuntime implements MechanicRuntime {
  private params: HudParams
  private game!: Game
  private rows: Array<{ label: string; value: string | number | boolean }> = []

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as HudParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void {
    this.rows = []
    for (const f of this.params.fields ?? []) {
      const v = this.readField(f)
      if (v === undefined) continue
      this.rows.push({ label: labelOf(f), value: v })
    }
  }

  dispose(): void { this.rows = [] }

  expose(): Record<string, unknown> {
    return {
      layout: this.params.layout ?? 'corners',
      rows: this.rows,
    }
  }

  private readField(f: HudField): string | number | boolean | undefined {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    if (!active) return undefined
    const props = active.properties as Record<string, unknown> | undefined

    if ('archetype' in f && 'component' in f) {
      const entities = (active.entities as Array<Record<string, unknown>> | undefined) ?? []
      for (const e of entities) {
        if (e.type !== f.archetype as unknown as string) continue
        const p = (e.properties as Record<string, unknown> | undefined) ?? {}
        const v = p[f.component as string]
        if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v
      }
      return undefined
    }
    if ('mechanic' in f && 'field' in f) {
      const runtimes = props?.mechanic_runtimes as Record<string, RuntimeShape> | undefined
      const r = runtimes?.[f.mechanic as unknown as string]
      const e = r?.expose?.()
      const v = e?.[f.field as string]
      if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v
      return undefined
    }
    if ('singleton' in f && 'field' in f) {
      const singletons = props?.singletons as Record<string, Record<string, unknown>> | undefined
      const s = singletons?.[f.singleton as unknown as string]
      const v = s?.[f.field as string]
      if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') return v
      return undefined
    }
    return undefined
  }
}

function labelOf(f: HudField): string {
  if (f.label) return f.label
  if ('component' in f) return f.component as string
  if ('field' in f) return f.field as string
  return '?'
}

mechanicRegistry.register('HUD', (instance, game) => {
  const rt = new HudRuntime(instance)
  rt.init(game)
  return rt
})
