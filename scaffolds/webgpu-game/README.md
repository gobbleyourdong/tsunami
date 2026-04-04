# WebGPU Game Scaffold

Zero-dependency game engine + playable demo (Sigma Arena).

## Quick Start
```bash
npm install
npm run dev     # http://localhost:5174
npm run build   # 35KB gzipped production build
```

## Demo Game: Sigma Arena
Top-down arena shooter — 10 waves + boss fight. WASD to move, mouse to aim
(auto-aim with keyboard only), Space to shoot, Escape to pause.

## Engine Imports
```ts
import { Camera, FrameLoop } from '@engine/renderer'
import { SceneNode, Scene } from '@engine/scene'
import { PhysicsWorld, RigidBody, SphereShape } from '@engine/physics'
import { Skeleton, AnimationClip, AnimationStateMachine } from '@engine/animation'
import { FiniteStateMachine, NavMesh, Sequence, Action } from '@engine/ai'
import { AudioEngine } from '@engine/audio'
import { KeyboardInput, ActionMap, GamepadInput } from '@engine/input'
import { compileShaderGraph, NoiseNode, GradientNode } from '@engine/vfx'
import { SceneManager, MenuSystem, DialogSystem, DifficultyManager } from '@engine/flow'
import { HealthSystem, Inventory, ScoreSystem, CheckpointSystem } from '@engine/systems'
import { Game, SceneBuilder } from '@engine/game'
```

## Engine Modules (45 source files, 256 unit tests)

| Module | Files | What |
|--------|-------|------|
| `renderer/` | 8 | WebGPU init, WGSL shaders, buffers, pipelines, textures, camera, frame loop, geometry |
| `scene/` | 7 | Node tree, GLTF 2.0 loader, PBR materials, mesh, instancing, frustum culling |
| `animation/` | 6 | Skeleton, clips, state machine, IK (two-bone + FABRIK), GPU skinning, root motion |
| `physics/` | 8 | Collision shapes, spatial hash broadphase, GJK/EPA, rigidbody, solver, raycasting, character controller |
| `vfx/` | 4 | Shader graph compiler (15 node types), WGSL noise lib, GPU particles, post-processing |
| `ai/` | 3 | FSM, behavior tree (Sequence/Selector/etc), NavMesh A* pathfinding |
| `systems/` | 4 | Health/damage, inventory, checkpoint/save, score/combo |
| `audio/` | 1 | Web Audio API, spatial HRTF, mixer, music crossfade |
| `input/` | 5 | Keyboard, gamepad, touch, pointer lock, action map, combos |
| `flow/` | 6 | Scene manager, menus, dialog, tutorial, difficulty curve, game flow |
| `game/` | 2 | Game API, scene builder |
| `math/` | 2 | Vec3/Mat4/Quat, column-major, zero deps |

## Game Structure
```
src/
  main.ts           — game entry, scene wiring, boot
  game/
    state.ts        — shared GameState type
    player.ts       — WASD + mouse aim + auto-aim + shooting
    enemies.ts      — 4 types (rusher/shooter/tank/boss) with behavior trees
    projectiles.ts  — spawn, move, collide, despawn + hit callbacks
    waves.ts        — 10-wave spawner with difficulty S-curve
    pickups.ts      — health/speed/rapidfire/shield drops
    renderer.ts     — Canvas 2D renderer (WebGPU upgrade path ready)
    hud.ts          — HTML overlay (HP, score, combo, wave, screens)
    audio.ts        — Procedural SFX via oscillators (zero audio files)
```

## Tests
```bash
npx tsx tests/smoke.ts       # Playwright: title → tutorial → arena → pause
npx tsx tests/death.ts       # Playwright: play → die → game over
npx tsx tests/full_loop.ts   # Playwright: play → die → retry → play again
```
