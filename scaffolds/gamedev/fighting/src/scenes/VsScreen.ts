/**
 * VsScreen — splash between CharSelect and Fight.
 *
 * Classic "Ryu VS Ken" portrait splash while stage loads. Plays
 * announcer line, holds ~2.5s, forwards to Fight.
 */

import charactersData from '../../data/characters.json'

export class VsScreen {
  readonly name = 'vs_screen'
  description = 'fighter portrait splash — "<P1> VS <P2>"'
  private p1_id = 'ryu'
  private p2_id = 'ken'

  setup(): void {
    // No mechanics — pure splash. Future: hook SfxLibrary for the
    // announcer line using a 'vs_announce' preset.
  }

  teardown(): void { /* no state */ }

  /** Set the pair for the next match. Called by CharSelect on confirm. */
  setMatchup(p1_id: string, p2_id: string): void {
    this.p1_id = p1_id
    this.p2_id = p2_id
  }

  /** The display pair (for rendering "<P1 name> VS <P2 name>"). */
  getMatchupDisplay(): { p1: string; p2: string } {
    const chars = (charactersData as { characters: Record<string, any> }).characters
    return {
      p1: chars[this.p1_id]?.display_name ?? this.p1_id,
      p2: chars[this.p2_id]?.display_name ?? this.p2_id,
    }
  }
}
