/**
 * Input combo system — ring buffer for pattern matching.
 * Detects sequences like ↓↘→+P (fighting game inputs).
 */

export interface ComboInput {
  action: string
  time: number  // timestamp in seconds
}

export interface ComboPattern {
  name: string
  sequence: string[]  // action names in order
  windowMs: number    // max time between first and last input
  onMatch: () => void
}

export class ComboSystem {
  private buffer: ComboInput[] = []
  private bufferSize: number
  private patterns: ComboPattern[] = []

  constructor(bufferSize = 10) {
    this.bufferSize = bufferSize
  }

  /** Register a combo pattern. */
  addPattern(pattern: ComboPattern): this {
    this.patterns.push(pattern)
    return this
  }

  /** Push a new input into the ring buffer. */
  push(action: string, time: number): void {
    this.buffer.push({ action, time })
    if (this.buffer.length > this.bufferSize) {
      this.buffer.shift()
    }
    this.checkPatterns(time)
  }

  /** Check if any registered pattern matches the recent buffer. */
  private checkPatterns(currentTime: number): void {
    for (const pattern of this.patterns) {
      if (this.matchPattern(pattern, currentTime)) {
        pattern.onMatch()
        // Clear buffer after match to prevent re-triggering
        this.buffer.length = 0
        break
      }
    }
  }

  private matchPattern(pattern: ComboPattern, currentTime: number): boolean {
    const seq = pattern.sequence
    if (this.buffer.length < seq.length) return false

    // Search backwards from end of buffer
    let seqIdx = seq.length - 1
    let firstTime = 0

    for (let i = this.buffer.length - 1; i >= 0 && seqIdx >= 0; i--) {
      if (this.buffer[i].action === seq[seqIdx]) {
        if (seqIdx === seq.length - 1) {
          // Record time of last input
        }
        if (seqIdx === 0) {
          firstTime = this.buffer[i].time
        }
        seqIdx--
      }
    }

    if (seqIdx >= 0) return false // didn't match all

    // Check timing window
    const elapsed = (currentTime - firstTime) * 1000
    return elapsed <= pattern.windowMs
  }

  /** Clear the input buffer. */
  clear(): void {
    this.buffer.length = 0
  }

  /** Get current buffer contents (for debug display). */
  getBuffer(): readonly ComboInput[] {
    return this.buffer
  }
}
