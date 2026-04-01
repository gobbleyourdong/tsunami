#!/usr/bin/env python3
"""One prompt. Tsunami does the rest."""
import asyncio
import sys

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 60
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a rhythm-based typing game that teaches typing. "
    "Letters fall from the top of the screen. Player types the matching letter "
    "before it hits the bottom. Correct = points + combo. Miss = combo breaks. "
    "Speed ramps up. Show WPM, accuracy %, combo. "
    "Dark neon theme. Satisfying hit feedback with sound and particles. "
    "Save to workspace/deliverables/rhythm-type/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
