import { describe, it, expect } from 'vitest'
import { SphereShape, BoxShape, CapsuleShape, ConvexHullShape } from '../src/physics/shapes'
import { SpatialHashGrid, aabbOverlap, computeAABB } from '../src/physics/broadphase'
import { gjkTest, narrowphaseTest } from '../src/physics/gjk'
import { RigidBody } from '../src/physics/rigidbody'
import { PhysicsWorld } from '../src/physics/world'
import { rayAABB, raySphere } from '../src/physics/raycast'
import type { Quat } from '../src/math/quat'
import type { Vec3 } from '../src/math/vec'

const ID_QUAT: Quat = [0, 0, 0, 1]

describe('Collision Shapes', () => {
  it('sphere support returns point on surface', () => {
    const s = new SphereShape(2)
    const p = s.support([1, 0, 0], [0, 0, 0], ID_QUAT)
    expect(p[0]).toBeCloseTo(2)
    expect(p[1]).toBeCloseTo(0)
  })

  it('sphere bounding radius', () => {
    expect(new SphereShape(3).boundingRadius()).toBe(3)
  })

  it('box support returns correct corner', () => {
    const b = new BoxShape([1, 1, 1])
    const p = b.support([1, 1, 1], [0, 0, 0], ID_QUAT)
    expect(p[0]).toBeCloseTo(1)
    expect(p[1]).toBeCloseTo(1)
    expect(p[2]).toBeCloseTo(1)
  })

  it('box bounding radius is diagonal', () => {
    const r = new BoxShape([1, 1, 1]).boundingRadius()
    expect(r).toBeCloseTo(Math.sqrt(3))
  })

  it('capsule support extends along axis', () => {
    const c = new CapsuleShape(0.5, 1)
    const p = c.support([0, 1, 0], [0, 0, 0], ID_QUAT)
    expect(p[1]).toBeCloseTo(1.5) // halfHeight + radius
  })

  it('convex hull from vertices', () => {
    const hull = ConvexHullShape.fromVertices(
      new Float32Array([1, 0, 0, -1, 0, 0, 0, 1, 0, 0, -1, 0])
    )
    expect(hull.vertices.length).toBe(4)
    const p = hull.support([1, 0, 0], [0, 0, 0], ID_QUAT)
    expect(p[0]).toBeCloseTo(1)
  })
})

describe('Broadphase', () => {
  it('AABB overlap detection', () => {
    expect(aabbOverlap(
      { min: [0, 0, 0], max: [2, 2, 2] },
      { min: [1, 1, 1], max: [3, 3, 3] }
    )).toBe(true)

    expect(aabbOverlap(
      { min: [0, 0, 0], max: [1, 1, 1] },
      { min: [5, 5, 5], max: [6, 6, 6] }
    )).toBe(false)
  })

  it('spatial hash finds pairs', () => {
    const grid = new SpatialHashGrid(2)
    grid.insert(0, { min: [0, 0, 0], max: [1, 1, 1] })
    grid.insert(1, { min: [0.5, 0.5, 0.5], max: [1.5, 1.5, 1.5] })
    grid.insert(2, { min: [100, 100, 100], max: [101, 101, 101] })

    const pairs = grid.queryPairs()
    expect(pairs.length).toBe(1)
    expect(pairs[0]).toEqual([0, 1])
  })

  it('spatial hash query by AABB', () => {
    const grid = new SpatialHashGrid(2)
    grid.insert(0, { min: [0, 0, 0], max: [1, 1, 1] })
    grid.insert(1, { min: [10, 10, 10], max: [11, 11, 11] })

    const hits = grid.query({ min: [-1, -1, -1], max: [2, 2, 2] })
    expect(hits).toContain(0)
    expect(hits).not.toContain(1)
  })

  it('remove clears entry', () => {
    const grid = new SpatialHashGrid(2)
    grid.insert(0, { min: [0, 0, 0], max: [1, 1, 1] })
    grid.insert(1, { min: [0.5, 0, 0], max: [1.5, 1, 1] })
    grid.remove(0)
    expect(grid.queryPairs().length).toBe(0)
  })
})

describe('GJK Narrowphase', () => {
  it('detects sphere-sphere collision', () => {
    const a = new SphereShape(1)
    const b = new SphereShape(1)
    const result = gjkTest(a, [0, 0, 0], ID_QUAT, b, [1, 0, 0], ID_QUAT)
    expect(result.colliding).toBe(true)
  })

  it('detects sphere-sphere separation', () => {
    const a = new SphereShape(1)
    const b = new SphereShape(1)
    const result = gjkTest(a, [0, 0, 0], ID_QUAT, b, [5, 0, 0], ID_QUAT)
    expect(result.colliding).toBe(false)
  })

  it('detects box-box collision', () => {
    const a = new BoxShape([1, 1, 1])
    const b = new BoxShape([1, 1, 1])
    const result = gjkTest(a, [0, 0, 0], ID_QUAT, b, [1.5, 0, 0], ID_QUAT)
    expect(result.colliding).toBe(true)
  })

  it('detects box-box separation', () => {
    const a = new BoxShape([1, 1, 1])
    const b = new BoxShape([1, 1, 1])
    const result = gjkTest(a, [0, 0, 0], ID_QUAT, b, [5, 0, 0], ID_QUAT)
    expect(result.colliding).toBe(false)
  })

  it('narrowphaseTest returns contact info', () => {
    const a = new SphereShape(1)
    const b = new SphereShape(1)
    const contact = narrowphaseTest(a, [0, 0, 0], ID_QUAT, b, [1.5, 0, 0], ID_QUAT)
    expect(contact.colliding).toBe(true)
    expect(contact.depth).toBeGreaterThan(0)
    // Normal should point roughly from A to B
    expect(contact.normal[0]).toBeGreaterThan(0)
  })

  it('sphere-capsule collision', () => {
    const sphere = new SphereShape(1)
    const capsule = new CapsuleShape(0.5, 1)
    const result = gjkTest(sphere, [0, 0, 0], ID_QUAT, capsule, [1.2, 0, 0], ID_QUAT)
    expect(result.colliding).toBe(true)
  })
})

describe('RigidBody', () => {
  it('creates with correct mass properties', () => {
    const body = new RigidBody(new SphereShape(1), { mass: 5 })
    expect(body.mass).toBe(5)
    expect(body.inverseMass).toBeCloseTo(0.2)
    expect(body.type).toBe('dynamic')
  })

  it('static body has zero inverse mass', () => {
    const body = new RigidBody(new SphereShape(1), { type: 'static' })
    expect(body.inverseMass).toBe(0)
  })

  it('integrates under gravity', () => {
    const body = new RigidBody(new SphereShape(1), { position: [0, 10, 0] })
    body.integrate(1 / 60, [0, -9.81, 0])
    expect(body.position[1]).toBeLessThan(10)
    expect(body.velocity[1]).toBeLessThan(0)
  })

  it('applies impulse', () => {
    const body = new RigidBody(new SphereShape(1), { mass: 1 })
    body.applyImpulse([10, 0, 0])
    expect(body.velocity[0]).toBeCloseTo(10)
  })

  it('sleeps when stationary', () => {
    const body = new RigidBody(new SphereShape(1))
    body.velocity = [0, 0, 0]
    body.angularVelocity = [0, 0, 0]
    for (let i = 0; i < 120; i++) {
      body.integrate(1 / 60, [0, 0, 0])
    }
    expect(body.sleeping).toBe(true)
  })

  it('wakes on force', () => {
    const body = new RigidBody(new SphereShape(1))
    body.sleeping = true
    body.applyForce([10, 0, 0])
    expect(body.sleeping).toBe(false)
  })
})

describe('Raycasting', () => {
  it('ray-AABB hit', () => {
    const result = rayAABB([0, 0, -5], [0, 0, 1], { min: [-1, -1, -1], max: [1, 1, 1] })
    expect(result.hit).toBe(true)
    expect(result.tMin).toBeCloseTo(4)
  })

  it('ray-AABB miss', () => {
    const result = rayAABB([0, 5, -5], [0, 0, 1], { min: [-1, -1, -1], max: [1, 1, 1] })
    expect(result.hit).toBe(false)
  })

  it('ray-sphere hit', () => {
    const result = raySphere([0, 0, -5], [0, 0, 1], [0, 0, 0], 1)
    expect(result.hit).toBe(true)
    expect(result.distance).toBeCloseTo(4)
    expect(result.normal[2]).toBeCloseTo(-1)
  })

  it('ray-sphere miss', () => {
    const result = raySphere([5, 0, -5], [0, 0, 1], [0, 0, 0], 1)
    expect(result.hit).toBe(false)
  })
})

describe('PhysicsWorld', () => {
  it('adds and removes bodies', () => {
    const world = new PhysicsWorld()
    const body = new RigidBody(new SphereShape(1))
    world.addBody(body)
    expect(world.bodyCount).toBe(1)
    world.removeBody(body)
    expect(world.bodyCount).toBe(0)
  })

  it('sphere falls under gravity', () => {
    const world = new PhysicsWorld()
    const ball = new RigidBody(new SphereShape(0.5), {
      position: [0, 10, 0], mass: 1,
    })
    world.addBody(ball)

    for (let i = 0; i < 60; i++) {
      world.step(1 / 60)
    }

    expect(ball.position[1]).toBeLessThan(6)
  })

  it('sphere collides with static sphere', () => {
    const world = new PhysicsWorld()
    // Static sphere at origin, radius 1 (top at y=1)
    const floor = new RigidBody(new SphereShape(1), {
      type: 'static', position: [0, 0, 0],
    })
    // Dynamic sphere above, radius 0.5, starts at y=3
    const ball = new RigidBody(new SphereShape(0.5), {
      position: [0, 3, 0], mass: 1, restitution: 0,
    })
    world.addBody(floor)
    world.addBody(ball)

    for (let i = 0; i < 300; i++) {
      world.step(1 / 60)
    }

    // Ball should rest on top of floor sphere (y ≈ 1.5), not fall through
    expect(ball.position[1]).toBeGreaterThan(0)
    expect(ball.position[1]).toBeLessThan(3)
  })

  it('sphere-box collision detected by GJK', () => {
    const sphere = new SphereShape(0.5)
    const box = new BoxShape([5, 0.5, 5])
    // Sphere at [0, 0.2, 0], box centered at [0, -0.5, 0]
    // Sphere bottom at -0.3, box top at 0 → overlapping by 0.3
    const contact = narrowphaseTest(
      box, [0, -0.5, 0], ID_QUAT,
      sphere, [0, 0.2, 0], ID_QUAT
    )
    expect(contact.colliding).toBe(true)
    expect(contact.depth).toBeGreaterThan(0)
  })

  it('triggers fire enter/exit callbacks', () => {
    const world = new PhysicsWorld()
    world.gravity = [0, 0, 0]
    const entered: string[] = []
    const exited: string[] = []

    const trigger = new RigidBody(new SphereShape(2), {
      type: 'static', position: [0, 0, 0], isTrigger: true,
    })
    const mover = new RigidBody(new SphereShape(0.5), {
      position: [0, 0, 0], mass: 1,
    })
    mover.velocity = [10, 0, 0]

    world.addBody(trigger)
    world.addBody(mover)
    world.onTriggerEnter = () => entered.push('enter')
    world.onTriggerExit = () => exited.push('exit')

    // Step while inside trigger
    world.step(1 / 60)
    expect(entered.length).toBe(1)

    // Move far away
    for (let i = 0; i < 60; i++) world.step(1 / 60)
    expect(exited.length).toBeGreaterThan(0)
  })

  it('world raycast hits bodies', () => {
    const world = new PhysicsWorld()
    world.gravity = [0, 0, 0]
    const body = new RigidBody(new SphereShape(1), {
      position: [0, 0, 5], type: 'static',
    })
    world.addBody(body)

    const hit = world.raycast([0, 0, 0], [0, 0, 1])
    expect(hit).not.toBeNull()
    expect(hit!.body).toBe(body)
    expect(hit!.distance).toBeCloseTo(4) // origin to sphere surface
  })
})
