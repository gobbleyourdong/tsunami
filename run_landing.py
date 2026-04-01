#!/usr/bin/env python3
"""Launch Tsunami to build its own landing page."""
import asyncio
import sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')

from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig(
    model_backend='api',
    model_name='Qwen3.5-9B',
    model_endpoint='http://localhost:8090',
    temperature=0.7,
    max_tokens=4096,
    workspace_dir='/home/jb/ComfyUI/CelebV-HQ/ark/workspace',
    max_iterations=30,
)
agent = Agent(config)

prompt = """Build a landing page. Save it to the absolute path /home/jb/ComfyUI/CelebV-HQ/ark/docs/landing/index.html

Use pure HTML + Tailwind CSS via CDN. No React. No build step.
Reference hero-bg.png for the hero background (same directory).

Theme: dark oceanic. Background #0b0b14, teal #4aeeff, indigo #4a9eff.

Sections:
1. HERO - background image hero-bg.png with dark overlay. Left side: large "tsunami" text, "autonomous ai agent" in gradient, "when agents spawn, the tide rises". Right side: dark terminal card with green monospace typewriter animation.
2. STATS BAR - indigo bg. 607 tests | 43 modules | 10GB stack | 5.9 tasks/sec
3. ARCHITECTURE - wave/eddy/tide/whirlpool flow diagram with boxes
4. FEATURES - 6 cards: Vision, Function Calling, Parallel Eddies, SD-Turbo, Sandbox, One-Click Install
5. INSTALL - curl command code block + scaling table
6. FOOTER

Write the COMPLETE file in one file_write call. Then message_result."""

print("Starting agent...")
result = asyncio.run(agent.run(prompt))
print(f'\nRESULT: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
print(f'Cost: {agent.cost_tracker.format_summary()}')
