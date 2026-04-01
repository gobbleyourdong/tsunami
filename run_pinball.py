#!/usr/bin/env python3
"""Build a Three.js 3D pinball game via Tsunami — stress test."""
import asyncio
import sys

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
agent = Agent(config)

PROMPT = """Build a complete 3D pinball game using Three.js, inspired by Windows 3D Pinball Space Cadet.

REQUIREMENTS:
- Single HTML file at /home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/pinball/index.html
- Load Three.js from CDN: https://unpkg.com/three@0.160.0/build/three.module.js via importmap
- Dark neon theme with glowing elements

TABLE LAYOUT:
- Tilted rectangular table (6-7 degree tilt) with walls
- Plunger lane on the right side (hold spacebar to charge, release to launch)
- Two flippers at bottom (left/right arrow keys), with pivot rotation physics
- Gap between flippers (drain) — ball falls through = lose a ball
- 3 circular bumpers in upper area that bounce ball hard and score points
- Field of small pegs/pins in middle area
- Score lanes at the top (rollovers)

PHYSICS (2D on table plane):
- Gravity pulls ball toward drain (along table tilt)
- Circle-line collision for walls and flippers
- Circle-circle collision for bumpers and pegs
- Flippers rotate around pivot point, apply impulse on contact
- Proper collision response with restitution
- Sub-stepping for stability (3-4 sub-steps per frame)

GAME LOGIC:
- 3 balls per game
- Score display with combo multiplier
- Bumper hits = 100 pts, pegs = 10 pts
- All rollovers lit = bonus multiplier
- Ball drain = lose a ball, reset
- Game over after 3 balls, press R to restart

VISUALS:
- Neon glow on bumpers (point lights per bumper)
- Particle effects on bumper hits
- Ball trail effect
- HUD overlay: score, ball count, multiplier
- Plunger charge bar on right side

AUDIO:
- Web Audio API procedural sounds (no external files)
- Different tones for: bumper hit, flipper, peg, drain, launch

Write the COMPLETE file in a single file_write call. Do NOT split into multiple writes.
The file must be fully playable immediately — no placeholder code."""

result = asyncio.run(agent.run(PROMPT))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
