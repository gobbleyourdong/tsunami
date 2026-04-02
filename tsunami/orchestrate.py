"""Tmux multi-agent orchestration — parallel workers in isolated worktrees.

Usage:
    python -m tsunami.orchestrate "Build a full-stack todo app" --workers 3

Splits a task into subtasks, spawns each in a tmux pane with its own
git worktree, coordinates via file-based status, merges when done.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from .config import resolve_aux_model_endpoint

log = logging.getLogger("tsunami.orchestrate")


def _run(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, **kwargs)


def create_worktree(base_dir: str, worker_id: str) -> str:
    """Create an isolated git worktree for a worker."""
    branch = f"tsunami-worker-{worker_id}-{int(time.time())}"
    worktree_dir = f"/tmp/tsunami-worktree-{worker_id}"

    # Clean up if exists
    if os.path.exists(worktree_dir):
        _run(f"git worktree remove --force {worktree_dir}", cwd=base_dir)
        shutil.rmtree(worktree_dir, ignore_errors=True)

    # Create worktree from current HEAD
    _run(f"git worktree add -b {branch} {worktree_dir} HEAD", cwd=base_dir)
    return worktree_dir


def cleanup_worktree(base_dir: str, worktree_dir: str):
    """Remove a worktree."""
    _run(f"git worktree remove --force {worktree_dir}", cwd=base_dir)
    shutil.rmtree(worktree_dir, ignore_errors=True)


class Worker:
    """A single agent worker in a tmux pane."""

    def __init__(self, worker_id: str, task: str, worktree_dir: str):
        self.id = worker_id
        self.task = task
        self.worktree_dir = worktree_dir
        self.status_file = Path(worktree_dir) / ".worker-status.json"
        self.result_file = Path(worktree_dir) / ".worker-result.txt"

    def write_task(self):
        """Write task file for the worker to read."""
        self.status_file.write_text(json.dumps({
            "worker_id": self.id,
            "status": "pending",
            "task": self.task,
            "started": time.time(),
        }))

    def get_status(self) -> str:
        if not self.status_file.exists():
            return "pending"
        try:
            data = json.loads(self.status_file.read_text())
            return data.get("status", "pending")
        except Exception:
            return "unknown"

    def get_result(self) -> str:
        if self.result_file.exists():
            return self.result_file.read_text()[:2000]
        return ""


class Orchestrator:
    """Coordinates multiple workers via tmux."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.session_name = f"tsunami-{int(time.time()) % 10000}"
        self.workers: list[Worker] = []

    def plan_subtasks(self, task: str, num_workers: int) -> list[dict]:
        """Use the fast model to decompose a task into parallel subtasks."""
        import httpx, json, re
        endpoint = resolve_aux_model_endpoint()

        try:
            resp = httpx.post(
                f"{endpoint}/v1/chat/completions",
                json={
                    "model": "qwen",
                    "messages": [
                        {"role": "system", "content": f"Decompose this task into exactly {num_workers} independent parallel subtasks. Output a JSON array of task description strings. Nothing else."},
                        {"role": "user", "content": task},
                    ],
                    "max_tokens": 500,
                },
                headers={"Authorization": "Bearer not-needed"},
                timeout=30,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    tasks = json.loads(match.group())
                    if len(tasks) >= num_workers:
                        return [{"id": f"w{i}", "task": t} for i, t in enumerate(tasks[:num_workers])]
        except Exception as e:
            log.warning(f"Task decomposition failed: {e}")

        # Fallback: all workers get the same task
        return [{"id": f"w{i}", "task": task} for i in range(num_workers)]

    def spawn_workers(self, subtasks: list[dict]):
        """Create worktrees and spawn tmux panes."""
        # Create tmux session
        _run(f"tmux new-session -d -s {self.session_name} -x 200 -y 50")

        for i, subtask in enumerate(subtasks):
            worker_id = subtask["id"]
            worktree = create_worktree(self.base_dir, worker_id)

            worker = Worker(worker_id, subtask["task"], worktree)
            worker.write_task()
            self.workers.append(worker)

            # Run the worker script — no inline Python quoting issues
            worker_script = os.path.join(self.base_dir, "tsunami", "worker.py")
            cmd = f"python3 -u {worker_script} {self.base_dir} {worktree}"

            if i == 0:
                # First worker uses the initial pane
                _run(f"tmux send-keys -t {self.session_name} '{cmd}' Enter")
            else:
                # Additional workers get new panes
                _run(f"tmux split-window -t {self.session_name} -h")
                _run(f"tmux send-keys -t {self.session_name} '{cmd}' Enter")

            # Tile evenly
            _run(f"tmux select-layout -t {self.session_name} tiled")

        log.info(f"Spawned {len(self.workers)} workers in tmux session: {self.session_name}")
        print(f"  tmux attach -t {self.session_name}   # to watch")

    def wait_for_completion(self, timeout: int = 600) -> list[dict]:
        """Poll workers until all complete or timeout."""
        start = time.time()
        while time.time() - start < timeout:
            statuses = [(w.id, w.get_status()) for w in self.workers]
            done = sum(1 for _, s in statuses if s in ("complete", "failed"))

            # Print progress
            status_str = " | ".join(f"{wid}:{s}" for wid, s in statuses)
            print(f"\r  [{done}/{len(self.workers)}] {status_str}", end="", flush=True)

            if done == len(self.workers):
                print()
                break
            time.sleep(5)
        else:
            print(f"\n  Timeout after {timeout}s")

        # Collect results
        results = []
        for w in self.workers:
            results.append({
                "worker_id": w.id,
                "status": w.get_status(),
                "result": w.get_result(),
                "worktree": w.worktree_dir,
            })
        return results

    def cleanup(self):
        """Remove worktrees and tmux session."""
        for w in self.workers:
            cleanup_worktree(self.base_dir, w.worktree_dir)
        _run(f"tmux kill-session -t {self.session_name}")


def orchestrate(task: str, num_workers: int = 2, base_dir: str = "."):
    """Main entry point for tmux orchestration."""
    print(f"\n  TSUNAMI ORCHESTRATOR — {num_workers} workers")
    print(f"  Task: {task[:80]}")
    print()

    orch = Orchestrator(base_dir)

    # Plan subtasks
    subtasks = orch.plan_subtasks(task, num_workers)

    # Spawn workers
    orch.spawn_workers(subtasks)

    # Wait
    results = orch.wait_for_completion()

    # Summary
    print("\n  Results:")
    for r in results:
        status = "✓" if r["status"] == "complete" else "✗"
        print(f"  {status} {r['worker_id']}: {r['status']} — {r['result'][:100]}")

    # Cleanup
    orch.cleanup()
    return results


if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "Write hello.py that prints hello world"
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    orchestrate(task, workers, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
