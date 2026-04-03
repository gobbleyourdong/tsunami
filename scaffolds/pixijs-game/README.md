# 2D Game Scaffold

PixiJS 8 + Matter.js physics + React. For platformers, shooters, puzzle games.

## Components (import from `./components`)

### GameCanvas
```tsx
<GameCanvas width={800} height={600} onApp={app => {
  const player = createRect(100, 100, 32, 32, 0x00ffcc)
  app.stage.addChild(player)
  app.ticker.add(() => { /* game loop */ })
}} />
```
Helpers: `createRect(x,y,w,h,color)`, `createCircle(x,y,r,color)`, `createText(str,x,y)`

### GameHUD
`<GameHUD score={100} level={3} lives={3} time={120} />`
- Overlay bar with score, level, lives (hearts), timer

### useKeyboard
```tsx
const keys = useKeyboard()
// in ticker: if (isPressed(keys, "ArrowLeft")) player.x -= 5
```

### Physics (Matter.js)
```tsx
const physics = createPhysicsWorld({ x: 0, y: 1 })
const ball = physics.addCircle(400, 100, 20)
const floor = physics.addStatic(400, 580, 800, 20)
physics.onCollision((a, b) => { /* bounce! */ })
physics.start()
// in ticker: syncSprite(pixiSprite, matterBody)
```

### SpriteAnimator
```tsx
const { sprite, update } = createAnimatedSprite(app, "sheet.png", 32, 32, 8, 24, 12)
app.ticker.add(dt => update(dt))
```

## Game Loop Pattern
```tsx
<GameCanvas onApp={app => {
  // 1. Create sprites
  // 2. Set up physics
  // 3. app.ticker.add(dt => { read keys → update physics → sync sprites → check collisions })
}} />
```

## CSS Classes
- `.game-container` — centers canvas with shadow
- `.game-hud` — blurred overlay bar for score/lives
- `.game-overlay` — fullscreen game-over/start screen
