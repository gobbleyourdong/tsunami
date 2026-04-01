#!/usr/bin/env python3
"""Test 2: Interactive quiz — medium complexity for undertow QA."""
import asyncio
import sys

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 20
agent = Agent(config)

PROMPT = """Build an interactive trivia quiz game.

Save to /home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/quiz-test/index.html

Single HTML file. No frameworks. Requirements:
- 5 multiple-choice questions about science
- Each question shows 4 answer buttons (A, B, C, D)
- Clicking an answer highlights it green (correct) or red (wrong)
- Score counter at the top that updates after each answer
- Next button to advance to the next question
- Results screen at the end showing final score out of 5
- Progress bar showing question X of 5
- Dark theme with clean typography

Write the complete file in one file_write call."""

result = asyncio.run(agent.run(PROMPT))
print(f'Result: {result[:300]}')
print(f'Iterations: {agent.state.iteration}')
