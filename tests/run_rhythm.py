#!/usr/bin/env python3
"""Build a rhythm typing game — decomposition + undertow test."""
import asyncio
import sys

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 40
agent = Agent(config)

PROMPT = """Build a rhythm-based typing game that teaches typing.

Save to /home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/rhythm-type/

The game: letters fall from the top of screen in rhythm with a beat.
Player types the matching letter before it reaches the bottom.
Correct = points + combo. Miss = combo breaks. Speed ramps up.
Show accuracy %, WPM, and combo counter.

Dark theme. Neon colors. Satisfying hit feedback (flash, particle, sound).
Must be playable and fun immediately."""

result = asyncio.run(agent.run(PROMPT))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
