#!/usr/bin/env python3
"""MoE Build via Swell: types → fire parallel eddies → assemble → test.

The file system is the MoE router.
Each file is an attention head.
types.ts is the shared vocabulary.
Each eddy writes one file.
The undertow is the loss function.
"""
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')

PROJECT_DIR = '/home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/rhythm-type'

# ── Step 1: Scaffold ──
p = Path(PROJECT_DIR)
if not (p / 'package.json').exists():
    p.mkdir(parents=True, exist_ok=True)
    print("Scaffolding Vite + React + TypeScript...")
    subprocess.run(
        ["npm", "create", "vite@latest", ".", "--", "--template", "react-ts"],
        cwd=PROJECT_DIR, capture_output=True, timeout=60,
        env={**__import__("os").environ, "npm_config_yes": "true"},
    )
    subprocess.run(["npm", "install"], cwd=PROJECT_DIR, capture_output=True, timeout=120)
    print("Scaffolded.")

# Create attention heads
for d in ['src/game', 'src/hooks', 'src/components']:
    Path(f'{PROJECT_DIR}/{d}').mkdir(parents=True, exist_ok=True)

# ── Step 2: Types (shared vocabulary) ──
TYPES = """\
export interface Letter {
  id: number;
  char: string;
  x: number;
  y: number;
  speed: number;
  color: string;
}

export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
}

export interface GameState {
  letters: Letter[];
  particles: Particle[];
  score: number;
  combo: number;
  maxCombo: number;
  totalKeys: number;
  correctKeys: number;
  missedLetters: number;
  startTime: number;
  isPlaying: boolean;
  isGameOver: boolean;
}

export type Screen = 'menu' | 'playing' | 'gameover';
"""
(Path(PROJECT_DIR) / 'src/game/types.ts').write_text(TYPES)
print("Wrote types.ts")

# ── Step 3: Define experts ──
# Each expert: (file_path, prompt)
# The eddy reads types.ts (via file_read), writes code to done()

DOMAIN = "Rhythm typing game. Letters fall from top. Type to destroy. Score + combo. Neon dark theme."

EXPERTS = [
    (
        f"{PROJECT_DIR}/src/game/engine.ts",
        f"""Write TypeScript for a rhythm typing game engine.

Read the types first: file_read path="{PROJECT_DIR}/src/game/types.ts"

Then call done() with the complete TypeScript code for engine.ts that exports:
- createInitialState(): GameState
- spawnLetter(state: GameState, canvasWidth: number): void
- updateLetters(state: GameState, dt: number, bottomY: number): number (returns missed count)
- handleKeyPress(state: GameState, key: string): Letter | null
- updateParticles(state: GameState, dt: number): void
- createExplosion(state: GameState, x: number, y: number, color: string): void
- getWPM(state: GameState): number
- getAccuracy(state: GameState): number

Import types from './types'. Pure logic, no React, no DOM."""
    ),
    (
        f"{PROJECT_DIR}/src/hooks/useGameLoop.ts",
        """Write a React hook useGameLoop.ts.

call done() with TypeScript code:
```
import { useEffect, useRef } from 'react';
export function useGameLoop(callback: (dt: number) => void, active: boolean) {
  // useRef for callback, requestAnimationFrame loop, cleanup
}
```
Keep it under 30 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/hooks/useAudio.ts",
        """Write a React hook useAudio.ts for procedural game sounds.

call done() with TypeScript code that exports useAudio() returning:
- playHit(): void — short square wave blip
- playMiss(): void — low descending tone
- playCombo(): void — ascending arpeggio

Use Web Audio API. AudioContext created on first call. Under 60 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/hooks/useInput.ts",
        """Write a React hook useInput.ts for keyboard handling.

call done() with TypeScript code:
```
import { useEffect } from 'react';
export function useInput(onKey: (key: string) => void, active: boolean) {
  // keydown listener, only single letters a-z normalized to uppercase
  // cleanup on inactive/unmount
}
```
Under 20 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/components/GameCanvas.tsx",
        f"""Write a React component GameCanvas.tsx that renders falling letters on a canvas.

Read types first: file_read path="{PROJECT_DIR}/src/game/types.ts"

call done() with TSX code:
- Props: {{ state: GameState, width: number, height: number }}
- useRef<HTMLCanvasElement>, useEffect to draw each frame
- Draw: dark bg (#0a0a1a), neon cyan letters with glow, magenta bottom line, fading particles
- Import GameState from '../game/types'

Just renders state. No game logic. Under 80 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/components/HUD.tsx",
        """Write a React component HUD.tsx — game stats overlay.

call done() with TSX code:
- Props: { score: number, combo: number, wpm: number, accuracy: number }
- Top bar: SCORE (cyan), WPM, ACCURACY %, COMBO
- Use inline styles or className. Neon text on dark transparent bg.

Under 30 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/components/StartScreen.tsx",
        """Write a React component StartScreen.tsx.

call done() with TSX code:
- Props: { onStart: () => void }
- Centered: "RHYTHM TYPE" title (neon cyan), subtitle, START button (glowing), "press any key" hint
- Dark theme.

Under 30 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/components/GameOverScreen.tsx",
        """Write a React component GameOverScreen.tsx.

call done() with TSX code:
- Props: { score: number, wpm: number, accuracy: number, maxCombo: number, onRestart: () => void }
- "GAME OVER" title, stats card, PLAY AGAIN button, "press R" hint
- Dark neon theme.

Under 40 lines. Just the code in done()."""
    ),
    (
        f"{PROJECT_DIR}/src/App.tsx",
        f"""Write the main App.tsx that wires all components together.

Read types: file_read path="{PROJECT_DIR}/src/game/types.ts"

call done() with TSX code that:
- Imports: GameState, Screen from './game/types'
- Imports: all engine functions from './game/engine'
- Imports: useGameLoop, useAudio, useInput from './hooks/*'
- Imports: GameCanvas, HUD, StartScreen, GameOverScreen from './components/*'

- useState for screen (Screen), useRef for gameState (mutated in loop)
- useGameLoop: spawn letters, update positions, check misses (>10 = game over), update particles
- useInput: handleKeyPress, if hit -> playHit + createExplosion, if miss -> playMiss
- Render: screen routing (menu/playing/gameover), canvas fills viewport

Under 100 lines. Just the code in done()."""
    ),
]

# ── Step 4: Fire eddies via swell (parallel) ──

async def main():
    from tsunami.eddy import run_swarm

    tasks = [expert[1] for expert in EXPERTS]
    targets = [expert[0] for expert in EXPERTS]

    system_prompt = (
        "You are a TypeScript expert. Read any files you need with file_read. "
        "Then call done() with ONLY the TypeScript/TSX code. "
        "No markdown fences. No explanation. Just the raw code."
    )

    print(f"\nFiring {len(EXPERTS)} eddies in parallel...\n")

    results = await run_swarm(
        tasks=tasks,
        workdir=PROJECT_DIR,
        max_concurrent=4,
        system_prompt=system_prompt,
        write_targets=targets,
    )

    for result, (target, _) in zip(results, EXPERTS):
        status = "✓" if result.success else "✗"
        fname = Path(target).name
        size = Path(target).stat().st_size if Path(target).exists() else 0
        print(f"  {status} {fname} ({result.turns} turns, {size} bytes)")

    # ── Step 5: Build ──
    print("\nBuilding with Vite...")
    build = subprocess.run(
        ["npx", "vite", "build"],
        cwd=PROJECT_DIR, capture_output=True, text=True, timeout=60,
    )
    if build.returncode == 0:
        print("Build: PASS")
    else:
        print(f"Build: FAIL")
        # Show first few errors
        for line in build.stderr.splitlines()[:15]:
            print(f"  {line}")

asyncio.run(main())
