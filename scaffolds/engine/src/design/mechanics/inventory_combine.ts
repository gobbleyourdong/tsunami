// InventoryCombine — Phase 4 extension mechanic.
//
// Adventure-game combine: two+ inventory items merge into a new item.
// Recipes carry an ordered ingredient list, a result item, and a consume
// policy. combine(items) attempts to match a recipe, removes consumed
// ingredients, adds the result.

import type { InventoryCombineParams, MechanicInstance } from '../schema'
import type { Game } from '../../game/game'
import { mechanicRegistry, type MechanicRuntime } from './index'

type Recipe = InventoryCombineParams['recipes'][number]

class InventoryCombineRuntime implements MechanicRuntime {
  private params: InventoryCombineParams
  private game!: Game

  constructor(private instance: MechanicInstance) {
    this.params = instance.params as InventoryCombineParams
  }

  init(game: Game): void { this.game = game }

  update(_dt: number): void { /* event-driven */ }

  dispose(): void { /* stateless */ }

  /** External: player combines a set of items. Returns the result item
   *  name on success, or null if no recipe matches. Order-insensitive. */
  combine(items: string[]): string | null {
    const recipe = this.matchRecipe(items)
    if (!recipe) return null
    const owner = this.findOwner()
    if (!owner) return null
    const inv = (((owner.properties as Record<string, unknown>)?.Inventory) ?? []) as unknown
    if (!Array.isArray(inv)) return null
    const invList = (inv as string[]).slice()
    // Confirm all ingredients are actually present.
    const working = invList.slice()
    for (const ing of recipe.ingredients) {
      const i = working.indexOf(ing)
      if (i < 0) return null
      working.splice(i, 1)
    }
    // Consume per policy.
    const toConsume = this.ingredientsToConsume(recipe)
    const finalList = invList.slice()
    for (const ing of toConsume) {
      const i = finalList.indexOf(ing)
      if (i >= 0) finalList.splice(i, 1)
    }
    finalList.push(recipe.result)
    const props = (owner.properties ?? {}) as Record<string, unknown>
    props.Inventory = finalList
    owner.properties = props
    return recipe.result
  }

  expose(): Record<string, unknown> {
    return {
      recipes: (this.params.recipes ?? []).map(r => ({
        ingredients: r.ingredients, result: r.result,
      })),
    }
  }

  private matchRecipe(items: string[]): Recipe | null {
    for (const r of this.params.recipes ?? []) {
      if (this.arraysEqualAsSets(r.ingredients, items)) return r
    }
    return null
  }

  private arraysEqualAsSets(a: string[], b: string[]): boolean {
    if (a.length !== b.length) return false
    const bCounts = new Map<string, number>()
    for (const x of b) bCounts.set(x, (bCounts.get(x) ?? 0) + 1)
    for (const x of a) {
      const n = bCounts.get(x) ?? 0
      if (n === 0) return false
      bCounts.set(x, n - 1)
    }
    return true
  }

  private ingredientsToConsume(recipe: Recipe): string[] {
    if (recipe.consumes === 'all') return recipe.ingredients
    if (recipe.consumes === 'first') return recipe.ingredients.slice(0, 1)
    if (Array.isArray(recipe.consumes)) return recipe.consumes
    return recipe.ingredients
  }

  private findOwner(): Record<string, unknown> | null {
    const active = this.game.sceneManager?.activeScene?.() as
      Record<string, unknown> | undefined
    const entities = (active?.entities as Array<Record<string, unknown>> | undefined) ?? []
    const aid = this.params.archetype as unknown as string
    return entities.find(e => e.type === aid) ?? null
  }
}

mechanicRegistry.register('InventoryCombine', (instance, game) => {
  const rt = new InventoryCombineRuntime(instance)
  rt.init(game)
  return rt
})
