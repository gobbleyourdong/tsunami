/**
 * Behavior Tree — Sequence, Selector, Decorator, Action, Condition nodes.
 * Tick-based evaluation. Returns SUCCESS, FAILURE, or RUNNING.
 */

export type BTStatus = 'success' | 'failure' | 'running'

export abstract class BTNode {
  abstract tick(dt: number): BTStatus
  reset(): void {}
}

/** Runs children in order. Fails on first failure, succeeds if all succeed. */
export class Sequence extends BTNode {
  private children: BTNode[]
  private currentIndex = 0

  constructor(children: BTNode[]) {
    super()
    this.children = children
  }

  tick(dt: number): BTStatus {
    while (this.currentIndex < this.children.length) {
      const status = this.children[this.currentIndex].tick(dt)
      if (status === 'failure') {
        this.currentIndex = 0
        return 'failure'
      }
      if (status === 'running') return 'running'
      this.currentIndex++
    }
    this.currentIndex = 0
    return 'success'
  }

  reset(): void {
    this.currentIndex = 0
    for (const child of this.children) child.reset()
  }
}

/** Runs children until one succeeds. Fails if all fail. */
export class Selector extends BTNode {
  private children: BTNode[]
  private currentIndex = 0

  constructor(children: BTNode[]) {
    super()
    this.children = children
  }

  tick(dt: number): BTStatus {
    while (this.currentIndex < this.children.length) {
      const status = this.children[this.currentIndex].tick(dt)
      if (status === 'success') {
        this.currentIndex = 0
        return 'success'
      }
      if (status === 'running') return 'running'
      this.currentIndex++
    }
    this.currentIndex = 0
    return 'failure'
  }

  reset(): void {
    this.currentIndex = 0
    for (const child of this.children) child.reset()
  }
}

/** Wraps a child with a condition or modifier. */
export class Decorator extends BTNode {
  constructor(
    private child: BTNode,
    private check: (status: BTStatus) => BTStatus
  ) {
    super()
  }

  tick(dt: number): BTStatus {
    return this.check(this.child.tick(dt))
  }

  reset(): void { this.child.reset() }
}

/** Inverts child result: success↔failure. */
export class Inverter extends BTNode {
  constructor(private child: BTNode) { super() }

  tick(dt: number): BTStatus {
    const s = this.child.tick(dt)
    if (s === 'success') return 'failure'
    if (s === 'failure') return 'success'
    return 'running'
  }

  reset(): void { this.child.reset() }
}

/** Repeats child N times or until failure. */
export class Repeater extends BTNode {
  private count: number
  private current = 0

  constructor(private child: BTNode, count = Infinity) {
    super()
    this.count = count
  }

  tick(dt: number): BTStatus {
    if (this.current >= this.count) {
      this.current = 0
      return 'success'
    }
    const s = this.child.tick(dt)
    if (s === 'failure') {
      this.current = 0
      return 'failure'
    }
    if (s === 'success') this.current++
    return this.current >= this.count ? 'success' : 'running'
  }

  reset(): void { this.current = 0; this.child.reset() }
}

/** Leaf: run a function. */
export class Action extends BTNode {
  constructor(private fn: (dt: number) => BTStatus) { super() }
  tick(dt: number): BTStatus { return this.fn(dt) }
}

/** Leaf: check a condition (instant, no RUNNING). */
export class Condition extends BTNode {
  constructor(private fn: () => boolean) { super() }
  tick(): BTStatus { return this.fn() ? 'success' : 'failure' }
}

/** Wait for a duration. */
export class Wait extends BTNode {
  private elapsed = 0
  constructor(private duration: number) { super() }

  tick(dt: number): BTStatus {
    this.elapsed += dt
    if (this.elapsed >= this.duration) {
      this.elapsed = 0
      return 'success'
    }
    return 'running'
  }

  reset(): void { this.elapsed = 0 }
}
