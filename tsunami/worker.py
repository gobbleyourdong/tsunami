"""Worker script — runs a single agent task in an isolated worktree.

Called by the orchestrator via tmux. Reads task from .worker-status.json,
runs the agent, writes result to .worker-result.txt, updates status.
"""

import asyncio
import json
import sys
import time
from pathlib import Path


async def main():
    base_dir = sys.argv[1]
    worktree_dir = sys.argv[2]

    sys.path.insert(0, base_dir)
    from tsunami.agent import Agent
    from tsunami.config import TsunamiConfig

    status_file = Path(worktree_dir) / ".worker-status.json"
    result_file = Path(worktree_dir) / ".worker-result.txt"

    # Read task
    status = json.loads(status_file.read_text())
    task = status["task"]
    worker_id = status["worker_id"]

    # Update status to running
    status["status"] = "running"
    status_file.write_text(json.dumps(status))

    print(f"[{worker_id}] Starting: {task[:80]}")

    # Run agent
    config = TsunamiConfig.from_yaml(f"{base_dir}/config.yaml")
    workspace = Path(worktree_dir) / "workspace"
    workspace.mkdir(exist_ok=True)
    (workspace / "deliverables").mkdir(exist_ok=True)
    config.workspace_dir = str(workspace)
    # No iteration cap — workers run until task_complete or abort

    agent = Agent(config)
    try:
        result = await agent.run(task)
        result_file.write_text(result or "no result")
        status["status"] = "complete" if agent.state.task_complete else "failed"
    except Exception as e:
        result_file.write_text(f"Error: {e}")
        status["status"] = "failed"

    status["iterations"] = agent.state.iteration
    status["finished"] = time.time()
    status_file.write_text(json.dumps(status))
    print(f"[{worker_id}] {status['status']} in {status['iterations']} iterations")


if __name__ == "__main__":
    asyncio.run(main())
