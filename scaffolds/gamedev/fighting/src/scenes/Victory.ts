/**
 * Victory scene — post-match win screen.
 *
 * Shows winner portrait + "YOU WIN / YOU LOSE" + option to rematch or
 * return to CharSelect. Can also be where MK-style fatality prompt
 * appears (timer-driven finisher input window).
 */

export class Victory {
  readonly name = 'victory'
  description = 'winner announcement + rematch / return-to-char-select'
  private winner_id = ''

  setup(): void {
    // No mechanics to mount — input-driven menu.
  }

  teardown(): void { /* no state */ }

  setWinner(fighter_id: string): void {
    this.winner_id = fighter_id
  }

  getWinner(): string {
    return this.winner_id
  }
}
