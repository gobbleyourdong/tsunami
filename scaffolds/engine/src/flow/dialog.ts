/**
 * Dialog/cutscene system — sequential text display with choices.
 * Typewriter effect, speaker portraits, branching via choices.
 */

export interface DialogLine {
  speaker?: string
  text: string
  speed?: number  // chars per second (0 = instant)
  choices?: DialogChoice[]
  onShow?: () => void
  onComplete?: () => void
}

export interface DialogChoice {
  text: string
  nextLabel?: string  // jump to labeled line
  onSelect?: () => void
}

export interface DialogScript {
  lines: DialogLine[]
  labels: Record<string, number>  // label → line index
}

export class DialogSystem {
  private script: DialogScript | null = null
  private lineIndex = 0
  private charIndex = 0
  private charTimer = 0
  private complete = false
  private waitingForChoice = false
  private _active = false

  // Current display state (read by renderer)
  currentSpeaker = ''
  currentText = ''      // revealed portion
  fullText = ''         // entire line
  choices: DialogChoice[] = []

  onLineStart?: (line: DialogLine) => void
  onLineComplete?: (line: DialogLine) => void
  onDialogEnd?: () => void
  onChoiceSelected?: (choice: DialogChoice, index: number) => void

  get active(): boolean { return this._active }
  get isComplete(): boolean { return this.complete }
  get isWaitingForChoice(): boolean { return this.waitingForChoice }

  /** Start a dialog script. */
  start(script: DialogScript): void {
    this.script = script
    this.lineIndex = 0
    this._active = true
    this.complete = false
    this.showCurrentLine()
  }

  /** Build a simple script from an array of lines. */
  static createScript(lines: DialogLine[]): DialogScript {
    const labels: Record<string, number> = {}
    return { lines, labels }
  }

  private showCurrentLine(): void {
    if (!this.script || this.lineIndex >= this.script.lines.length) {
      this.end()
      return
    }

    const line = this.script.lines[this.lineIndex]
    this.currentSpeaker = line.speaker ?? ''
    this.fullText = line.text
    this.currentText = ''
    this.charIndex = 0
    this.charTimer = 0
    this.complete = false
    this.waitingForChoice = false
    this.choices = line.choices ?? []

    line.onShow?.()
    this.onLineStart?.(line)

    if ((line.speed ?? 30) === 0) {
      this.currentText = this.fullText
      this.charIndex = this.fullText.length
      this.complete = true
      if (this.choices.length > 0) {
        this.waitingForChoice = true
      }
      line.onComplete?.()
      this.onLineComplete?.(line)
    }
  }

  /** Update typewriter. Call every frame. */
  update(dt: number): void {
    if (!this._active || this.complete) return

    const line = this.script?.lines[this.lineIndex]
    if (!line) return

    const speed = line.speed ?? 30
    this.charTimer += dt * speed
    const newChars = Math.floor(this.charTimer)
    this.charTimer -= newChars

    this.charIndex = Math.min(this.charIndex + newChars, this.fullText.length)
    this.currentText = this.fullText.substring(0, this.charIndex)

    if (this.charIndex >= this.fullText.length) {
      this.complete = true
      if (this.choices.length > 0) {
        this.waitingForChoice = true
      }
      line.onComplete?.()
      this.onLineComplete?.(line)
    }
  }

  /** Advance: skip typewriter or go to next line. */
  advance(): void {
    if (!this._active) return

    if (!this.complete) {
      // Skip typewriter — show full text
      this.currentText = this.fullText
      this.charIndex = this.fullText.length
      this.complete = true
      const line = this.script?.lines[this.lineIndex]
      if (line?.choices && line.choices.length > 0) {
        this.waitingForChoice = true
        this.choices = line.choices
      }
      line?.onComplete?.()
      this.onLineComplete?.(line!)
      return
    }

    if (this.waitingForChoice) return // must select a choice

    this.lineIndex++
    this.showCurrentLine()
  }

  /** Select a choice (0-indexed). */
  selectChoice(index: number): void {
    if (!this.waitingForChoice || index < 0 || index >= this.choices.length) return

    const choice = this.choices[index]
    choice.onSelect?.()
    this.onChoiceSelected?.(choice, index)
    this.waitingForChoice = false

    if (choice.nextLabel && this.script?.labels[choice.nextLabel] !== undefined) {
      this.lineIndex = this.script.labels[choice.nextLabel]
    } else {
      this.lineIndex++
    }
    this.showCurrentLine()
  }

  /** End the dialog immediately. */
  end(): void {
    this._active = false
    this.script = null
    this.onDialogEnd?.()
  }

  /** Current line index. */
  get currentLineIndex(): number {
    return this.lineIndex
  }
}
