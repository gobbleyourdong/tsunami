# WebGPU Game Scaffold

Custom game engine (Tsunami Engine) — WebGPU native, zero dependencies.

## Engine API

```ts
import { Game } from 'tsunami-engine'

const game = new Game({ mode: '3d' })
const level = game.scene('level1')
level.spawn('player', { mesh: 'capsule', position: [0,1,0], controller: 'fps' })
level.ground(50, 'grid')
level.light('directional', { direction: [1,-1,0.5] })
game.start()
```

## Engine Modules

| Module | What | Key Classes |
|--------|------|-------------|
| `renderer` | WebGPU init, shaders, pipelines, camera | `GPU`, `Camera`, `FrameLoop`, `Shader` |
| `scene` | Scene graph, GLTF, materials, instancing | `SceneNode`, `GLTFLoader`, `Material` |
| `physics` | Custom solver, GJK/EPA, rigidbodies | `PhysicsWorld`, `RigidBody`, `Sphere/Box/Capsule` |
| `animation` | Skeleton, clips, state machine, IK | `Skeleton`, `AnimationClip`, `AnimationStateMachine` |
| `ai` | FSM, behavior trees, NavMesh A* | `FSM`, `BehaviorTree`, `NavMesh` |
| `audio` | Web Audio API, spatial, pooling | `AudioEngine`, `Sound`, `SpatialAudio` |
| `input` | Keyboard, gamepad, touch, combos | `KeyboardInput`, `GamepadInput`, `ActionMap` |
| `vfx` | GPU particles, shader graph, post-fx | `GPUParticleSystem`, `ShaderGraph`, `PostProcess` |
| `flow` | Scenes, menus, dialog, tutorial | `SceneManager`, `Menu`, `Dialog`, `Tutorial` |
| `systems` | Health, inventory, save, score | `HealthSystem`, `Inventory`, `Checkpoint`, `Score` |
| `game` | Top-level orchestrator | `Game`, `SceneBuilder` |

## Spawn Options

```ts
level.spawn('name', {
  mesh: 'box' | 'sphere' | 'capsule' | 'plane',
  position: [x, y, z],
  rotation: [rx, ry, rz],
  scale: [sx, sy, sz] | number,
  material: string,
  controller: 'fps' | 'orbit' | 'topdown',
  ai: 'patrol' | 'chase' | 'flee',
  patrol: [[x,y,z], [x,y,z], ...],
  mass: number,         // 0 = static
  isStatic: boolean,
  trigger: string,      // collision callback name
  properties: {},       // custom data
})
```

## Development
```bash
npm install
npm run dev     # Vite dev server
npm run build   # Production build
```
