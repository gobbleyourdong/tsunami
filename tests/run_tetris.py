#!/usr/bin/env python3
import asyncio, sys, time
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

# Wait for pixel city to finish
time.sleep(600)

config = TsunamiConfig(
    model_backend='api',
    model_name='Qwen3.5-9B',
    model_endpoint='http://localhost:8090',
    workspace_dir='/home/jb/ComfyUI/CelebV-HQ/ark/workspace',
    max_iterations=10,
    max_tokens=8192,
)
agent = Agent(config)

result = asyncio.run(agent.run(
    'Build a Tetris clone. Save to /home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/tetris/index.html. '
    'Single HTML file with canvas. All 7 tetromino pieces with correct rotations. '
    'Arrow keys: left/right move, up rotates, down soft drop, spacebar hard drop. '
    'Score, level, next piece preview. Speed increases with level. '
    'Line clear animation. Game over detection. Dark theme with colored pieces. '
    'Write complete file in one file_write call.'
))
print(f'Done: {result[:200]}')
print(f'Iterations: {agent.state.iteration}')
