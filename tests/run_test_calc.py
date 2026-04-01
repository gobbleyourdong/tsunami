#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 30
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a calculator app. Buttons for 0-9, +, -, *, /, =, C. "
    "Display shows input and result. Dark theme. "
    "Save to workspace/deliverables/calculator/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
