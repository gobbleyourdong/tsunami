/**
 * Scene-tree / component (ECS-flavored) drone-API fixture. The engine
 * doesn't ship a classic-ECS world; the drone-facing primitive is
 * SceneNode (Godot-style: each node has a transform + a key-value
 * component map). Most engine systems (Mesh, Health, etc.) attach to
 * nodes via `node.setComponent('mesh', mesh)` / `getComponent('mesh')`.
 *
 * Tests cover parent/child wiring, transform recompute, component
 * lifecycle, traversal, find/findByName — everything a drone reaches
 * for when wiring entities in main.ts.
 */

import { describe, it, expect } from 'vitest'
import { SceneNode } from '@engine/scene/node'
import { Scene } from '@engine/scene/scene'

describe('SceneNode — parent/child wiring', () => {
  it('addChild sets the child.parent backpointer', () => {
    const root = new SceneNode('root')
    const a = new SceneNode('a')
    root.addChild(a)
    expect(a.parent).toBe(root)
    expect(root.children).toContain(a)
  })

  it('addChild on a node with an existing parent reparents it', () => {
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    const c = new SceneNode('c')
    a.addChild(c)
    b.addChild(c)
    expect(c.parent).toBe(b)
    expect(a.children).not.toContain(c)
    expect(b.children).toContain(c)
  })

  it('removeChild detaches', () => {
    const root = new SceneNode()
    const child = new SceneNode()
    root.addChild(child)
    root.removeChild(child)
    expect(child.parent).toBeNull()
    expect(root.children).not.toContain(child)
  })

  it('detach() unhooks from parent', () => {
    const root = new SceneNode()
    const child = new SceneNode()
    root.addChild(child)
    child.detach()
    expect(child.parent).toBeNull()
    expect(root.children).not.toContain(child)
  })

  it('node ids are unique and monotonic', () => {
    const a = new SceneNode()
    const b = new SceneNode()
    expect(b.id).toBeGreaterThan(a.id)
  })

  it('default name is `node_<id>` when omitted', () => {
    const n = new SceneNode()
    expect(n.name).toMatch(/^node_\d+$/)
  })
})

describe('SceneNode — components (ECS-style)', () => {
  it('setComponent / getComponent / hasComponent / removeComponent', () => {
    const n = new SceneNode()
    expect(n.hasComponent('mesh')).toBe(false)
    n.setComponent('mesh', { vertices: 8 })
    expect(n.hasComponent('mesh')).toBe(true)
    expect(n.getComponent<{ vertices: number }>('mesh')?.vertices).toBe(8)
    n.removeComponent('mesh')
    expect(n.hasComponent('mesh')).toBe(false)
    expect(n.getComponent('mesh')).toBeUndefined()
  })

  it('component setters are chainable', () => {
    const n = new SceneNode()
      .setComponent('hp', 100)
      .setComponent('damage', 5)
    expect(n.getComponent('hp')).toBe(100)
    expect(n.getComponent('damage')).toBe(5)
  })

  it('different keys hold different values', () => {
    const n = new SceneNode()
    n.setComponent('a', 1)
    n.setComponent('b', 'hello')
    expect(n.getComponent<number>('a')).toBe(1)
    expect(n.getComponent<string>('b')).toBe('hello')
  })
})

describe('SceneNode — transforms', () => {
  it('local position propagates to world position via updateWorldTransforms', () => {
    const root = new SceneNode()
    const child = new SceneNode()
    root.addChild(child)
    root.position = [10, 0, 0]
    child.position = [0, 5, 0]
    root.updateWorldTransforms()
    const wp = child.getWorldPosition()
    expect(wp[0]).toBeCloseTo(10, 5)
    expect(wp[1]).toBeCloseTo(5, 5)
    expect(wp[2]).toBeCloseTo(0, 5)
  })

  it('updateWorldTransforms recurses through subtree', () => {
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    const c = new SceneNode('c')
    a.addChild(b)
    b.addChild(c)
    a.position = [1, 0, 0]
    b.position = [2, 0, 0]
    c.position = [4, 0, 0]
    a.updateWorldTransforms()
    expect(c.getWorldPosition()[0]).toBeCloseTo(7, 5)
  })

  it('scale propagates to children', () => {
    const root = new SceneNode()
    const child = new SceneNode()
    root.addChild(child)
    root.scale = [2, 2, 2]
    child.position = [3, 0, 0]
    root.updateWorldTransforms()
    expect(child.getWorldPosition()[0]).toBeCloseTo(6, 5)
  })
})

describe('SceneNode — traversal & find', () => {
  it('traverse visits self + every descendant', () => {
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    const c = new SceneNode('c')
    a.addChild(b)
    b.addChild(c)
    const seen: string[] = []
    a.traverse(n => seen.push(n.name))
    expect(seen).toEqual(['a', 'b', 'c'])
  })

  it('find returns the first matching node depth-first', () => {
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    const c = new SceneNode('c')
    a.addChild(b)
    a.addChild(c)
    expect(a.find(n => n.name === 'c')).toBe(c)
    expect(a.find(n => n.name === 'missing')).toBeUndefined()
  })

  it('findByName matches by exact name', () => {
    const root = new SceneNode('root')
    const enemy = new SceneNode('enemy_1')
    root.addChild(enemy)
    expect(root.findByName('enemy_1')).toBe(enemy)
    expect(root.findByName('player')).toBeUndefined()
  })
})

describe('Scene — top-level container', () => {
  it('exposes a default `root` SceneNode named "root"', () => {
    const s = new Scene()
    expect(s.root).toBeInstanceOf(SceneNode)
    expect(s.root.name).toBe('root')
  })

  it('addNode wires the node under root', () => {
    const s = new Scene()
    const n = new SceneNode('player')
    s.addNode(n)
    expect(n.parent).toBe(s.root)
    expect(s.root.children).toContain(n)
  })

  it('removeNode detaches from root', () => {
    const s = new Scene()
    const n = new SceneNode()
    s.addNode(n)
    s.removeNode(n)
    expect(n.parent).toBeNull()
    expect(s.root.children).not.toContain(n)
  })

  it('updateTransforms walks from root', () => {
    const s = new Scene()
    const n = new SceneNode('p')
    n.position = [3, 0, 0]
    s.addNode(n)
    s.updateTransforms()
    expect(n.getWorldPosition()[0]).toBeCloseTo(3, 5)
  })

  it('findByName forwards to the root subtree', () => {
    const s = new Scene()
    const n = new SceneNode('boss')
    s.addNode(n)
    expect(s.findByName('boss')).toBe(n)
  })

  it('nodeCount excludes the root', () => {
    const s = new Scene()
    expect(s.nodeCount).toBe(0)
    s.addNode(new SceneNode())
    s.addNode(new SceneNode())
    expect(s.nodeCount).toBe(2)
  })
})
