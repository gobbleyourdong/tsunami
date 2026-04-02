#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 40
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a todo list app with a backend. "
    "Add tasks, mark complete, delete. Tasks persist in a database. "
    "Clean UI with dark theme. "
    "Save to workspace/deliverables/todo-app/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
