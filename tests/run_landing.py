#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 30
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a landing page for a coffee shop called 'Nebula Brew'. "
    "Hero section with tagline, features section with 3 cards, "
    "menu section, contact info, footer. Dark cosmic theme. "
    "Save to workspace/deliverables/landing-coffee/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
