#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 25
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a weather dashboard. Show a 5-day forecast with fake data "
    "for New York. Each day shows temperature, weather icon (emoji), "
    "and condition. A line chart of temperature over the 5 days. "
    "Current conditions card at the top. Dark theme. "
    "Save to workspace/deliverables/weather-dash/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
