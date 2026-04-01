#!/usr/bin/env python3
"""Test 1: Simple calculator — baseline for undertow QA."""
import asyncio
import sys

sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 15
agent = Agent(config)

PROMPT = """Build a simple calculator app.

Save to /home/jb/ComfyUI/CelebV-HQ/ark/workspace/deliverables/calculator/index.html

Single HTML file. No frameworks. Requirements:
- Display showing current input and result
- Buttons for digits 0-9, +, -, *, /, =, C (clear)
- Clicking buttons updates the display
- = evaluates the expression
- C clears everything
- Dark theme, clean grid layout

Write the complete file in one file_write call."""

result = asyncio.run(agent.run(PROMPT))
print(f'Result: {result[:300]}')
print(f'Iterations: {agent.state.iteration}')
