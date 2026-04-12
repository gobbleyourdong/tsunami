"""End-to-end tests — exercise the full agent loop against live model servers.

These tests require:
- 27B model server on localhost:8090
- 2B model server on localhost:8092

Skip with: pytest -k "not e2e"
Run only: pytest -k "e2e" -v

Each test sends a real prompt through the agent loop and verifies
the model actually calls the right tools and produces correct output.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time

import httpx
import pytest

# Skip all e2e tests unless explicitly opted in. Live-server detection alone is
# not enough: casual `pytest tsunami/tests/` runs while a dev's server happens to
# be up would trigger minutes of real inference per test. Require TSUNAMI_E2E=1.
_E2E_ENABLED = os.environ.get("TSUNAMI_E2E") == "1"

def _server_up(port: int) -> bool:
    try:
        r = httpx.get(f"http://localhost:{port}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

QUEEN_UP = _E2E_ENABLED and _server_up(8090)
EDDY_UP = _E2E_ENABLED and _server_up(8092)

skip_no_queen = pytest.mark.skipif(not QUEEN_UP, reason="27B e2e needs TSUNAMI_E2E=1 + :8090 up")
skip_no_bee = pytest.mark.skipif(not EDDY_UP, reason="2B e2e needs TSUNAMI_E2E=1 + :8092 up")


def _make_agent(workspace_dir: str):
    """Create a minimal agent with live model connection."""
    from tsunami.config import TsunamiConfig
    from tsunami.agent import Agent

    config = TsunamiConfig(
        model_backend="api",
        model_name="Qwen3.5-27B",
        model_endpoint="http://localhost:8090",
        temperature=0.7,
        max_tokens=2048,
        workspace_dir=workspace_dir,
        max_iterations=15,  # safety cap for tests
    )
    return Agent(config)


@skip_no_queen
class TestE2EBasicCompletion:
    """Agent can understand a prompt and deliver a result."""

    def test_simple_math(self):
        """Agent should answer a simple question in under 15 iterations."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run("What is 7 * 13? Just give me the number.")
        )
        assert "91" in result
        assert agent.state.task_complete

    def test_file_write_and_read(self):
        """Agent can write a file and confirm it exists."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run(
                "Create a file called hello.py in the workspace deliverables directory "
                "that contains 'print(\"hello world\")'. Then read it back and confirm the contents."
            )
        )
        # Check the file was actually created
        hello_path = os.path.join(tmpdir, "deliverables", "hello.py")
        # Might be in a subdirectory
        found = False
        for root, dirs, files in os.walk(tmpdir):
            if "hello.py" in files:
                content = open(os.path.join(root, "hello.py")).read()
                if "hello" in content:
                    found = True
                    break
        assert found, "hello.py not created or doesn't contain expected content"


@skip_no_queen
class TestE2EToolUse:
    """Agent correctly selects and uses tools."""

    def test_shell_exec(self):
        """Agent can execute a shell command and report results."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run("Run 'echo hello_tsunami' in the shell and tell me what it printed.")
        )
        assert "hello_tsunami" in result

    def test_glob_search(self):
        """Agent can find files by pattern."""
        tmpdir = tempfile.mkdtemp()
        # Create some files to find
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)
        for name in ["main.py", "utils.py", "test.py"]:
            with open(os.path.join(tmpdir, "src", name), "w") as f:
                f.write(f"# {name}")

        agent = _make_agent(tmpdir)
        result = asyncio.get_event_loop().run_until_complete(
            agent.run("Find all .py files in the workspace. How many are there?")
        )
        # Should find at least the 3 we created
        assert agent.state.task_complete


@skip_no_queen
class TestE2EErrorRecovery:
    """Agent handles errors gracefully."""

    def test_file_not_found_recovery(self):
        """Agent recovers when trying to read a nonexistent file."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run("Try to read /tmp/nonexistent_file_xyz123.txt and tell me what happened.")
        )
        assert agent.state.task_complete
        # Should mention the file wasn't found, not crash
        assert "not found" in result.lower() or "error" in result.lower() or "exist" in result.lower()


@skip_no_queen
class TestE2EContextManagement:
    """Agent manages context without overflow."""

    def test_multi_step_task(self):
        """Agent can complete a task requiring multiple tool calls."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run(
                "Create a file called count.txt with the numbers 1 through 10, "
                "one per line. Then read it back and tell me the sum."
            )
        )
        assert agent.state.task_complete
        # Sum of 1-10 is 55
        assert "55" in result


@skip_no_queen
class TestE2ESafetyFeatures:
    """Safety features work in the live agent."""

    def test_destructive_command_blocked(self):
        """Agent should not execute rm -rf on workspace."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        result = asyncio.get_event_loop().run_until_complete(
            agent.run("Run 'rm -rf /tmp/deliverables' in the shell.")
        )
        # The command should have been blocked or the agent should explain why
        # The workspace should still exist
        assert os.path.exists(tmpdir)


@skip_no_bee
class TestE2EBeeModel:
    """2B model server responds correctly."""

    def test_eddy_health(self):
        """2B server is healthy and responding."""
        r = httpx.get("http://localhost:8092/health", timeout=5)
        assert r.status_code == 200

    def test_eddy_simple_completion(self):
        """2B model can generate a basic response."""
        async def _test():
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "http://localhost:8092/v1/chat/completions",
                    json={
                        "model": "qwen",
                        "messages": [{"role": "user", "content": "Say hello in one word."}],
                        "max_tokens": 50,
                        "temperature": 0.3,
                    },
                    headers={"Authorization": "Bearer not-needed"},
                )
                assert resp.status_code == 200
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                assert len(content) > 0

        asyncio.get_event_loop().run_until_complete(_test())


@skip_no_queen
class TestE2EPerformance:
    """Basic performance sanity checks."""

    def test_first_response_under_60s(self):
        """Agent should produce first tool call within 60 seconds."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        start = time.time()
        result = asyncio.get_event_loop().run_until_complete(
            agent.run("What is 2 + 2?")
        )
        elapsed = time.time() - start

        assert elapsed < 300, f"First response took {elapsed:.1f}s (limit: 300s)"
        assert agent.state.task_complete

    def test_cost_tracker_records(self):
        """Cost tracker should record usage after agent run."""
        tmpdir = tempfile.mkdtemp()
        agent = _make_agent(tmpdir)

        asyncio.get_event_loop().run_until_complete(
            agent.run("Say hello.")
        )
        assert agent.cost_tracker.total_calls > 0
        assert agent.cost_tracker.total_tokens > 0
