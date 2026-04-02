# 2D Game Template

React 19 + TypeScript + PixiJS 8 + Matter.js physics.

## Pre-built Components

Import from `./components`:
- `GameCanvas` — PixiJS canvas component (get the app instance via `onApp`)
- `createRect(x, y, w, h, color)` — colored rectangle sprite
- `createCircle(x, y, radius, color)` — circle sprite
- `createText(content, x, y, style?)` — text display
- `createPhysicsWorld(gravity?)` — Matter.js physics world
- `syncSprite(sprite, body)` — sync PixiJS sprite position with physics body

## Build Loop

1. Write game types in `src/types.ts`
2. Use `GameCanvas` to get the PixiJS app
3. Create sprites with `createRect`/`createCircle`/`createText`
4. Create physics with `createPhysicsWorld`, add bodies, sync with sprites
5. Wire in `src/App.tsx`

## Usage Example

```tsx
import { GameCanvas, createRect, createCircle, createPhysicsWorld, syncSprite } from "./components"

function Game() {
  const handleApp = (app) => {
    const physics = createPhysicsWorld({ x: 0, y: 1 })
    
    // Static ground
    physics.addStatic(400, 580, 800, 20)
    const groundSprite = createRect(0, 570, 800, 20, 0x333366)
    app.stage.addChild(groundSprite)

    // Falling ball
    const ball = physics.addCircle(400, 100, 20)
    const ballSprite = createCircle(400, 100, 20, 0xff4488)
    app.stage.addChild(ballSprite)

    // Game loop
    app.ticker.add(() => syncSprite(ballSprite, ball, -20, -20))
    physics.start()
  }

  return <GameCanvas width={800} height={600} onApp={handleApp} />
}
```

## File Structure

```
src/
  App.tsx               ← Wire your game here
  components/
    GameCanvas.tsx       ← PixiJS canvas + sprite helpers (ready to use)
    Physics2D.ts         ← Matter.js wrapper + sync (ready to use)
    index.ts             ← Barrel exports
```
