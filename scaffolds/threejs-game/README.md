# 3D Game Template

React 19 + TypeScript + React Three Fiber + Rapier Physics + Drei helpers.

## Pre-built Components

Import from `./components`:
- `Scene` — ready-to-use 3D scene with camera, lighting, physics, orbit controls
- `Ground` — static physics ground plane
- `Box` — physics-enabled box (drop it, it falls)
- `Sphere` — physics-enabled sphere (rolls, bounces)
- `HUD` — 2D overlay for score, health, menus

## Build Loop

1. Write game types in `src/types.ts`
2. Add game objects as children of `Scene` — they get physics automatically
3. Write game logic (spawning, input, scoring) as hooks or components
4. Use `HUD` for 2D UI overlay on top of the 3D scene
5. Wire in `src/App.tsx`

## Usage Example

```tsx
import { Scene, Ground, Box, Sphere, HUD } from "./components"

<HUD><span>SCORE: {score}</span></HUD>
<Scene bgColor="#0a0a1a" gravity={[0, -9.81, 0]}>
  <Ground />
  <Box position={[0, 5, 0]} color="#ff6644" />
  <Sphere position={[2, 10, 0]} color="#44aaff" />
  {/* Add your game objects here */}
</Scene>
```

## Scene Props

- `bgColor` — background color (default: "#1a1a2e")
- `gravity` — physics gravity vector (default: [0, -9.81, 0])
- `debug` — show physics wireframes and grid (default: false)
- `camera` — position and fov (default: { position: [0, 8, 12], fov: 50 })

## File Structure

```
src/
  App.tsx            ← Wire your game here
  components/
    Scene.tsx         ← Camera + lights + physics (ready to use)
    Ground.tsx        ← Physics floor (ready to use)
    Box.tsx           ← Physics box (ready to use)
    Sphere.tsx        ← Physics sphere (ready to use)
    HUD.tsx           ← 2D overlay (ready to use)
    index.ts          ← Barrel exports
```
