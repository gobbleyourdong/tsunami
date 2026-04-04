import { describe, it, expect } from 'vitest'
import { FiniteStateMachine } from '../src/ai/fsm'
import {
  Sequence, Selector, Inverter, Repeater,
  Action, Condition, Wait,
} from '../src/ai/behavior_tree'
import { NavMesh } from '../src/ai/pathfinding'

describe('FiniteStateMachine', () => {
  it('starts in first added state', () => {
    const fsm = new FiniteStateMachine({})
    fsm.addState({ name: 'idle' }).addState({ name: 'walk' })
    expect(fsm.current).toBe('idle')
  })

  it('transitions on condition', () => {
    const ctx = { health: 50 }
    const fsm = new FiniteStateMachine(ctx)
    fsm.addState({ name: 'alive' }).addState({ name: 'dead' })
    fsm.addTransition('alive', 'dead', (c) => c.health <= 0)

    fsm.update(0.016)
    expect(fsm.current).toBe('alive')

    ctx.health = 0
    fsm.update(0.016)
    expect(fsm.current).toBe('dead')
  })

  it('calls enter/exit hooks', () => {
    const log: string[] = []
    const fsm = new FiniteStateMachine({})
    fsm.addState({
      name: 'a',
      onExit: () => log.push('exit-a'),
    })
    fsm.addState({
      name: 'b',
      onEnter: () => log.push('enter-b'),
    })
    fsm.setState('b')
    expect(log).toEqual(['exit-a', 'enter-b'])
  })

  it('calls update on current state', () => {
    let updated = false
    const fsm = new FiniteStateMachine({})
    fsm.addState({ name: 'idle', onUpdate: () => { updated = true } })
    fsm.update(0.016)
    expect(updated).toBe(true)
  })

  it('wildcard transition from any state', () => {
    const ctx = { panic: false }
    const fsm = new FiniteStateMachine(ctx)
    fsm.addState({ name: 'idle' }).addState({ name: 'walk' }).addState({ name: 'flee' })
    fsm.addTransition('*', 'flee', (c) => c.panic, 10)

    fsm.setState('walk')
    ctx.panic = true
    fsm.update(0.016)
    expect(fsm.current).toBe('flee')
  })

  it('serializes and deserializes', () => {
    const fsm = new FiniteStateMachine({})
    fsm.addState({ name: 'a' }).addState({ name: 'b' })
    fsm.setState('b')
    const data = fsm.serialize()
    expect(data).toBe('b')

    const fsm2 = new FiniteStateMachine({})
    fsm2.addState({ name: 'a' }).addState({ name: 'b' })
    fsm2.deserialize(data)
    expect(fsm2.current).toBe('b')
  })
})

describe('Behavior Tree', () => {
  it('Sequence succeeds when all children succeed', () => {
    const seq = new Sequence([
      new Action(() => 'success'),
      new Action(() => 'success'),
    ])
    expect(seq.tick(0.016)).toBe('success')
  })

  it('Sequence fails on first failure', () => {
    const order: string[] = []
    const seq = new Sequence([
      new Action(() => { order.push('a'); return 'success' }),
      new Action(() => { order.push('b'); return 'failure' }),
      new Action(() => { order.push('c'); return 'success' }),
    ])
    expect(seq.tick(0.016)).toBe('failure')
    expect(order).toEqual(['a', 'b'])
  })

  it('Selector succeeds on first success', () => {
    const sel = new Selector([
      new Action(() => 'failure'),
      new Action(() => 'success'),
      new Action(() => 'failure'),
    ])
    expect(sel.tick(0.016)).toBe('success')
  })

  it('Selector fails when all fail', () => {
    const sel = new Selector([
      new Action(() => 'failure'),
      new Action(() => 'failure'),
    ])
    expect(sel.tick(0.016)).toBe('failure')
  })

  it('Inverter flips result', () => {
    const inv = new Inverter(new Action(() => 'success'))
    expect(inv.tick(0.016)).toBe('failure')

    const inv2 = new Inverter(new Action(() => 'failure'))
    expect(inv2.tick(0.016)).toBe('success')
  })

  it('Condition checks boolean', () => {
    let flag = false
    const cond = new Condition(() => flag)
    expect(cond.tick(0)).toBe('failure')
    flag = true
    expect(cond.tick(0)).toBe('success')
  })

  it('Wait returns running then success', () => {
    const wait = new Wait(0.1)
    expect(wait.tick(0.05)).toBe('running')
    expect(wait.tick(0.06)).toBe('success')
  })

  it('Repeater repeats N times', () => {
    let count = 0
    const rep = new Repeater(new Action(() => { count++; return 'success' }), 3)
    expect(rep.tick(0)).toBe('running') // 1st
    expect(rep.tick(0)).toBe('running') // 2nd
    expect(rep.tick(0)).toBe('success') // 3rd
    expect(count).toBe(3)
  })

  it('complex tree: patrol + chase', () => {
    let playerNearby = false
    let chasing = false

    const tree = new Selector([
      // Chase branch
      new Sequence([
        new Condition(() => playerNearby),
        new Action(() => { chasing = true; return 'success' }),
      ]),
      // Patrol branch
      new Action(() => { chasing = false; return 'success' }),
    ])

    tree.tick(0.016)
    expect(chasing).toBe(false) // patrol

    playerNearby = true
    tree.tick(0.016)
    expect(chasing).toBe(true) // chase
  })
})

describe('NavMesh Pathfinding', () => {
  it('creates grid NavMesh', () => {
    const mesh = NavMesh.createGrid(10, 10, 2)
    expect(mesh.nodes.length).toBe(25) // 5x5
  })

  it('finds nearest node', () => {
    const mesh = NavMesh.createGrid(10, 10, 2)
    const nearest = mesh.findNearest([0, 0, 0])
    const node = mesh.nodes[nearest]
    // Should be near center
    expect(Math.abs(node.position[0])).toBeLessThan(2)
    expect(Math.abs(node.position[2])).toBeLessThan(2)
  })

  it('finds path between adjacent nodes', () => {
    const mesh = new NavMesh()
    mesh.addNode([0, 0, 0])
    mesh.addNode([1, 0, 0])
    mesh.addNode([2, 0, 0])
    mesh.connect(0, 1)
    mesh.connect(1, 2)

    const path = mesh.findPath(0, 2)
    expect(path.length).toBe(3)
    expect(path[0]).toEqual([0, 0, 0])
    expect(path[2]).toEqual([2, 0, 0])
  })

  it('finds optimal path (not just first)', () => {
    const mesh = new NavMesh()
    mesh.addNode([0, 0, 0])  // 0: start
    mesh.addNode([5, 0, 0])  // 1: detour
    mesh.addNode([1, 0, 0])  // 2: direct
    mesh.addNode([2, 0, 0])  // 3: end
    mesh.connect(0, 1); mesh.connect(1, 3) // long path: 0→1→3
    mesh.connect(0, 2); mesh.connect(2, 3) // short path: 0→2→3

    const path = mesh.findPath(0, 3)
    expect(path.length).toBe(3)
    expect(path[1]).toEqual([1, 0, 0]) // should go through node 2, not 1
  })

  it('returns empty for unreachable target', () => {
    const mesh = new NavMesh()
    mesh.addNode([0, 0, 0])
    mesh.addNode([100, 0, 0])
    // No connection
    const path = mesh.findPath(0, 1)
    expect(path.length).toBe(0)
  })

  it('findWorldPath replaces endpoints', () => {
    const mesh = NavMesh.createGrid(10, 10, 2)
    const path = mesh.findWorldPath([-4, 0, -4], [4, 0, 4])
    expect(path.length).toBeGreaterThan(0)
    expect(path[0]).toEqual([-4, 0, -4])
    expect(path[path.length - 1]).toEqual([4, 0, 4])
  })
})
