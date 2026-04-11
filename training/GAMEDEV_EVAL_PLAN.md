# Gamedev Model Eval Plan — Target 475/500

## Eval Structure (mirrors app-builder, adapted for games)

### L1: Format (40 points, 8 tests per difficulty)
Does the model produce valid tool calls for game prompts?
- Trivial: "What games can you build?", "Hello" → message_chat
- Easy: "Build a snake game" → project_init
- Medium: "Build a tetris with rotation" → project_init
- Hard: "Build a 3D dungeon crawler" → project_init
- Extreme: "Build a multiplayer battle royale" → project_init

### L2: Scaffold Selection (12 points)
Does it pick the game scaffold?
- "Build a snake game" → game scaffold
- "Build a 3D space game" → webgpu scaffold
- "Build a multiplayer game" → realtime scaffold
- All game prompts → game or webgpu scaffold (NOT react-app, dashboard, etc.)

### L3: Error Recovery (6 tests, 17 points each = ~100 points)
Game-specific errors:
- ER01: Missing @engine module → shell_exec npm install or file_edit import
- ER02: Canvas type error → file_edit
- ER03: Syntax error in game loop → file_edit
- ER04: Missing game asset file → file_write
- ER05: Wrong path (same as app-builder)
- ER06: Missing FrameLoop import → file_edit

### L4: Hack-Free Behavior (10 tests, 10 points each = 100 points)
- HF01: Auto-scaffold for game prompts → project_init
- HF02: Research gate for "game like X" → search_web first
- HF03: Stall detection → stop reading, start writing
- HF04: Code-write gate → file_write after scaffold
- HF05: Shell loop detection → file_write missing component
- HF06: Conversation → message_chat
- HF07: Engine imports (NOT React) in game code
- HF08: Canvas 2D pattern (NOT DOM manipulation)
- HF09: Complex game → plan_update first
- HF10: QA before delivery → undertow

### L5: Integration (9 tests, ~11 points each = ~100 points)
Real end-to-end game builds:
- Easy: snake, pong, breakout
- Medium: platformer, space invaders, flappy bird
- Hard: tower defense, top-down shooter, rhythm game

**Pass criteria**: project scaffolded, main.ts written with @engine/ imports,
Canvas 2D rendering, game loop (FrameLoop), builds successfully, delivered.

## Implementation

`training/eval_gamedev.py` — mirrors eval_all.py structure but with:
- Game-specific system prompt (from build_gamedev_v2.py SYSTEM_TEXT)
- Game-specific tool schemas
- L4 checks for @engine/ imports, Canvas patterns, no React
- L5 runs real builds against the game scaffold

## 475/500 Breakdown
| Layer | Target | Notes |
|-------|--------|-------|
| L1 | 40/40 | Same format as app-builder, should transfer |
| L2 | 12/12 | Game scaffold selection |
| L3 | 5/6 | ER05 (wrong path) is the chronic 4B failure |
| L4 | 9/10 | HF09 (plan gate) is chronic |
| L5 | 8/9 | 1 hard game may timeout |
| **Total** | **474** | Barely 475 if we nail one more L3 or L4 |

To hit 475 reliably, we need either:
- L3=100% (6/6) → 483 (requires ER05 to pass)
- L4=100% (10/10) → 484 (requires HF09 to pass)
- L5=100% + L3=83% + L4=90% → 473 (just short)
- **31B solves this** — 427 base means L3/L4 may be 100% out of the box

## 31B Strategy
1. Fix serve_transformers.py for 31B (may need device_map tweaks)
2. Eval base 31B on app-builder suite → establish baseline
3. If 490+ on apps: eval on gamedev prompts (zero-shot, no fine-tuning)
4. If gamedev < 475: minimal LoRA (10-15 game examples, r=32, LR=2e-5, 1-3 epochs)
5. If gamedev ≥ 475 zero-shot: ship it. No fine-tuning needed.
