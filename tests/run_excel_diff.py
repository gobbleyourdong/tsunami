#!/usr/bin/env python3
import asyncio, sys
sys.path.insert(0, '/home/jb/ComfyUI/CelebV-HQ/ark')
from tsunami.config import TsunamiConfig
from tsunami.agent import Agent

config = TsunamiConfig.from_yaml('config.yaml')
config.max_iterations = 60
agent = Agent(config)

result = asyncio.run(agent.run(
    "Build an Excel sheet diff tracker. "
    "Upload an xlsx file, display it as an editable table, "
    "track every cell edit as a diff (original → new value), "
    "accumulate changes in a diff panel, "
    "sign off and submit button that finalizes changes with a summary. "
    "Save to workspace/deliverables/excel-diff/"
))
print(f'Result: {result[:500]}')
print(f'Iterations: {agent.state.iteration}')
