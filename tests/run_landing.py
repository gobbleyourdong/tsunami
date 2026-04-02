#!/usr/bin/env python3
"""Launch Tsunami to build its own landing page."""
import asyncio
import sys
from pathlib import Path

# Allow running from project root or tests/ subdirectory
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig(
    model_backend='api',
    model_name='Qwen3.5-9B',
    model_endpoint='http://localhost:8090',
    temperature=0.7,
    max_tokens=4096,
    workspace_dir=str(_PROJECT_ROOT / 'workspace'),
    max_iterations=30,
)

agent = Agent(config)

result = asyncio.run(agent.run(
    "Build a landing page for a coffee shop called 'Nebula Brew'. "
    "Hero section with tagline, features section with 3 cards, "
    "menu section, contact info, footer. Dark cosmic theme. "
    "Save to workspace/deliverables/landing-coffee/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
