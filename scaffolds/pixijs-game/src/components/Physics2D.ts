import Matter from "matter-js"

const { Engine, World, Bodies, Body, Events, Runner } = Matter

export interface PhysicsWorld {
  engine: Matter.Engine
  world: Matter.World
  runner: Matter.Runner
  addRect: (x: number, y: number, w: number, h: number, options?: Matter.IBodyDefinition) => Matter.Body
  addCircle: (x: number, y: number, r: number, options?: Matter.IBodyDefinition) => Matter.Body
  addStatic: (x: number, y: number, w: number, h: number) => Matter.Body
  onCollision: (callback: (a: Matter.Body, b: Matter.Body) => void) => void
  remove: (body: Matter.Body) => void
  start: () => void
  stop: () => void
}

/** Create a 2D physics world with Matter.js.
 *  Add bodies, detect collisions, sync with PixiJS sprites. */
export function createPhysicsWorld(gravity = { x: 0, y: 1 }): PhysicsWorld {
  const engine = Engine.create({ gravity })
  const world = engine.world
  const runner = Runner.create()

  return {
    engine,
    world,
    runner,

    addRect(x, y, w, h, options = {}) {
      const body = Bodies.rectangle(x, y, w, h, options)
      World.add(world, body)
      return body
    },

    addCircle(x, y, r, options = {}) {
      const body = Bodies.circle(x, y, r, options)
      World.add(world, body)
      return body
    },

    addStatic(x, y, w, h) {
      const body = Bodies.rectangle(x, y, w, h, { isStatic: true })
      World.add(world, body)
      return body
    },

    onCollision(callback) {
      Events.on(engine, "collisionStart", event => {
        for (const pair of event.pairs) {
          callback(pair.bodyA, pair.bodyB)
        }
      })
    },

    remove(body) {
      World.remove(world, body)
    },

    start() {
      Runner.run(runner, engine)
    },

    stop() {
      Runner.stop(runner)
    },
  }
}

/** Sync a PixiJS sprite position with a Matter.js body */
export function syncSprite(
  sprite: { position: { x: number; y: number }; rotation?: number },
  body: Matter.Body,
  offsetX = 0,
  offsetY = 0,
) {
  sprite.position.x = body.position.x + offsetX
  sprite.position.y = body.position.y + offsetY
  if (sprite.rotation !== undefined) {
    sprite.rotation = body.angle
  }
}
