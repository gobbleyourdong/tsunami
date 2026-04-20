/**
 * CharSelect scene — fighter roster grid.
 *
 * Shows roster from data/characters.json as portrait tiles. Cursor
 * navigation (left/right) → confirm → forwards to VsScreen with the
 * chosen fighter pair. Stage may be auto-selected from chosen
 * fighter's stage_affinity (default) or forced via a later menu.
 *
 * Data-driven: adding a character means appending to characters.json
 * and bundling a portrait — no code change required.
 */

import charactersData from '../../data/characters.json'

export class CharSelect {
  readonly name = 'char_select'
  description = ''
  private roster: Array<{ id: string; display_name: string; archetype: string }>

  constructor() {
    const chars = (charactersData as { characters: Record<string, any> }).characters
    this.roster = Object.entries(chars).map(([id, c]: [string, any]) => ({
      id,
      display_name: c.display_name ?? id,
      archetype: c.archetype ?? 'unknown',
    }))
    this.description = `${this.roster.length} fighters available`
  }

  setup(): void {
    // Nothing to mount — this scene is pure input + rendering. Future:
    // hook InputMapper for cursor navigation.
  }

  teardown(): void { /* no state */ }

  /** Used by VsScreen to pick P1/P2. */
  getRoster(): Array<{ id: string; display_name: string; archetype: string }> {
    return [...this.roster]
  }

  /** Agent-facing helper for tests: fetch a fighter by id. */
  getFighter(id: string): { id: string; display_name: string; archetype: string } | undefined {
    return this.roster.find((f) => f.id === id)
  }
}
