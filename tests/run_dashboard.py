#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 30
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a cryptocurrency price dashboard. "
    "Show 5 crypto prices with fake data (BTC, ETH, SOL, DOGE, ADA). "
    "Each has a stat card with current price and 24h change %. "
    "A line chart showing 7-day price history. "
    "A table of recent transactions. Dark theme. "
    "Save to workspace/deliverables/crypto-dash/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
