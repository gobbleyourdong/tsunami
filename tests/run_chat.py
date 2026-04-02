#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 25
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a live chat app. Users type messages and see them appear "
    "in real time. Show who's online. Message history. Dark theme. "
    "Save to workspace/deliverables/chat-app/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
