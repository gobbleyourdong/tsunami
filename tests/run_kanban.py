#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 30
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a Kanban board app. Three columns: To Do, In Progress, Done. "
    "Add new cards with a title. Click cards to move them to the next column. "
    "Card count per column. Dark theme. "
    "Save to workspace/deliverables/kanban/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
