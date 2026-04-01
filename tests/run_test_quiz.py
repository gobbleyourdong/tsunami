#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 40
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a trivia quiz app. 5 science questions, 4 answer choices each. "
    "Click an answer to see if correct (green) or wrong (red). "
    "Score counter, progress bar, results screen at end. Dark theme. "
    "Save to workspace/deliverables/quiz-test/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
