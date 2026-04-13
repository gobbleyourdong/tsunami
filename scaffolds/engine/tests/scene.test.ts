import { describe, it, expect } from 'vitest'
import { SceneNode } from '../src/scene/node'
import { Scene } from '../src/scene/scene'

describe('SceneNode', () => {
  it('creates with auto-incrementing id', () => {
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    expect(b.id).toBeGreaterThan(a.id)
  })

  it('adds and removes children', () => {
    const parent = new SceneNode('parent')
    const child = new SceneNode('child')
    parent.addChild(child)
    expect(parent.children).toContain(child)
    expect(child.parent).toBe(parent)

    parent.removeChild(child)
    expect(parent.children).not.toContain(child)
    expect(child.parent).toBeNull()
  })

  it('re-parents child from old parent', () => {
    const p1 = new SceneNode('p1')
    const p2 = new SceneNode('p2')
    const child = new SceneNode('child')
    p1.addChild(child)
    p2.addChild(child)
    expect(p1.children.length).toBe(0)
    expect(p2.children).toContain(child)
    expect(child.parent).toBe(p2)
  })

  it('computes world transform from parent chain', () => {
    const parent = new SceneNode('parent')
    parent.position = [10, 0, 0]
    const child = new SceneNode('child')
    child.position = [0, 5, 0]
    parent.addChild(child)
    parent.updateWorldTransforms()

    const worldPos = child.getWorldPosition()
    expect(worldPos[0]).toBeCloseTo(10)
    expect(worldPos[1]).toBeCloseTo(5)
    expect(worldPos[2]).toBeCloseTo(0)
  })

  it('scale propagates to children', () => {
    const parent = new SceneNode('parent')
    parent.scale = [2, 2, 2]
    const child = new SceneNode('child')
    child.position = [5, 0, 0]
    parent.addChild(child)
    parent.updateWorldTransforms()

    const worldPos = child.getWorldPosition()
    expect(worldPos[0]).toBeCloseTo(10) // 5 * 2
  })

  it('traverse visits all nodes', () => {
    const root = new SceneNode('root')
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    const c = new SceneNode('c')
    root.addChild(a)
    root.addChild(b)
    a.addChild(c)

    const visited: string[] = []
    root.traverse((n) => visited.push(n.name))
    expect(visited).toEqual(['root', 'a', 'c', 'b'])
  })

  it('finds node by name', () => {
    const root = new SceneNode('root')
    const target = new SceneNode('target')
    const other = new SceneNode('other')
    root.addChild(other)
    other.addChild(target)

    const found = root.findByName('target')
    expect(found).toBe(target)
  })

  it('detach removes from parent', () => {
    const parent = new SceneNode('parent')
    const child = new SceneNode('child')
    parent.addChild(child)
    child.detach()
    expect(parent.children.length).toBe(0)
    expect(child.parent).toBeNull()
  })

  it('component system works', () => {
    const node = new SceneNode()
    node.setComponent('health', 100)
    expect(node.getComponent<number>('health')).toBe(100)
    expect(node.hasComponent('health')).toBe(true)

    node.removeComponent('health')
    expect(node.hasComponent('health')).toBe(false)
  })
})

describe('Scene', () => {
  it('tracks node count', () => {
    const scene = new Scene()
    const a = new SceneNode('a')
    const b = new SceneNode('b')
    scene.addNode(a)
    scene.addNode(b)
    expect(scene.nodeCount).toBe(2)
  })

  it('finds nodes by name', () => {
    const scene = new Scene()
    const node = new SceneNode('findme')
    scene.addNode(node)
    expect(scene.findByName('findme')).toBe(node)
  })
})
