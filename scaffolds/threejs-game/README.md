# 3D Game Scaffold

React Three Fiber + Rapier physics + Drei helpers. Drop objects into Scene, they have physics.

## Quick Start
```tsx
import { Scene, Ground, Box, PlayerController, HUD, HUDStat } from "./components"

export default function App() {
  return (
    <>
      <HUD><HUDStat label="Score" value={0} /></HUD>
      <Scene>
        <Ground />
        <PlayerController />
        <Box position={[3, 1, 0]} color="#ff6644" />
      </Scene>
    </>
  )
}
```

## Components (import from `./components`)

### Scene
`<Scene gravity={[0,-9.81,0]} bgColor="#08090d" camera={{position:[0,8,12]}} debug>`
- Canvas + camera + lighting + Rapier physics + OrbitControls
- Everything inside has physics automatically

### Ground
`<Ground size={[50,50]} color="#2a2a3e" />`
- Static physics plane

### Box / Sphere
`<Box position={[0,5,0]} color="#ff6644" mass={1} />`
`<Sphere position={[0,5,0]} color="#44aaff" radius={0.7} />`
- Physics-enabled rigid bodies

### PlayerController
`<PlayerController speed={5} jumpForce={5} color="#00ffcc" />`
- WASD + Arrow keys to move, Space to jump
- Physics-enabled, lock rotations

### HUD / HUDStat
`<HUD><HUDStat label="Score" value={100} /><HUDStat label="HP" value={80} color="#f44" /></HUD>`
- 2D overlay, neon glow, pointer-events pass through

### Advanced
- `CustomShaderMaterial` + NEON_FRAG, NOISE_FRAG, WATER_FRAG
- `ProceduralTerrain`, `ProceduralPlanet`
- `SpriteSheet` for billboarded 2D sprites in 3D
- `useProceduralTexture` + drawCheckerboard, drawNoise, drawGradient, drawBricks

## CSS Classes
- `.hud-3d`, `.hud-stat` — neon overlay
- `.game-overlay-3d` — fullscreen menu/game-over
- `.crosshair` — FPS crosshair
- `.health-bar`, `.health-bar-fill` — health bar

## Key Libraries
- `@react-three/fiber` — React renderer for Three.js
- `@react-three/drei` — OrbitControls, Environment, Grid, etc.
- `@react-three/rapier` — Rapier physics (RigidBody, colliders)
- `useFrame(callback)` — runs every frame (game loop)
