#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 40
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a snake game. Arrow keys to move, eat food to grow, "
    "don't hit walls or yourself. Score counter. Speed increases. "
    "Dark theme with neon green snake. "
    "Save to workspace/deliverables/snake-game/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
