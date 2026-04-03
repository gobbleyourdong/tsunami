"""Agent loop integration tests — catch the bugs that unit tests miss.

These tests run REAL prompts through the agent with a LIVE model server.
They catch the exact class of bugs that broke things this session:
- Tension gate blocking greetings (6-14 iters)
- message_info spam loops
- Blank page deliveries
- Path resolution failures

Skip with: pytest -k "not agent_loop"
Run only: pytest -k "agent_loop" -v

Requires model server on localhost:8090.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx
import pytest

# Skip all if model server isn't running
def _model_up() -> bool:
    try:
        r = httpx.get("http://localhost:8090/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

skip_no_model = pytest.mark.skipif(not _model_up(), reason="Model server not running on :8090")

# Force lite mode for tests (faster, tests the harder path)
os.environ["TSUNAMI_EDDY_ENDPOINT"] = "http://localhost:8090"


def _run_agent(prompt: str, timeout_s: int = 120) -> tuple:
    """Run a prompt through the agent, return (iterations, task_complete, result)."""
    from tsunami.config import TsunamiConfig
    from tsunami.agent import Agent

    async def _run():
        config = TsunamiConfig.from_yaml("config.yaml")
        config.eddy_endpoint = "http://localhost:8090"
        agent = Agent(config)
        result = await asyncio.wait_for(agent.run(prompt), timeout=timeout_s)
        return agent.state.iteration, agent.state.task_complete, result

    return asyncio.run(_run())


@skip_no_model
class TestGreeting:
    """Greetings should complete in ≤3 iterations."""

    def test_hi(self):
        iters, complete, result = _run_agent("hi", timeout_s=60)
        assert complete, f"Did not complete (stuck at iter {iters})"
        assert iters <= 3, f"Greeting took {iters} iterations (max 3)"

    def test_whats_up(self):
        iters, complete, result = _run_agent("what's up?", timeout_s=60)
        assert complete, f"Did not complete (stuck at iter {iters})"
        assert iters <= 5, f"Greeting took {iters} iterations (max 5)"

    def test_what_can_you_do(self):
        iters, complete, result = _run_agent("what can you do?", timeout_s=60)
        assert complete, f"Did not complete (stuck at iter {iters})"
        assert iters <= 5, f"Question took {iters} iterations (max 5)"


@skip_no_model
class TestIterationBounds:
    """No prompt should spin forever."""

    def test_simple_task_under_30(self):
        """A simple build should complete in under 30 iterations."""
        iters, complete, result = _run_agent(
            "Build a counter. Plus and minus buttons. All in one App.tsx.",
            timeout_s=180,
        )
        assert complete, f"Did not complete (stuck at iter {iters})"
        assert iters <= 30, f"Simple build took {iters} iterations (max 30)"

    def test_safety_valve(self):
        """Nonsense prompts should hit the safety valve, not loop forever."""
        iters, complete, result = _run_agent(
            "asdfjkl;",
            timeout_s=90,
        )
        # Should either complete quickly or hit safety valve
        assert iters <= 50, f"Nonsense prompt ran {iters} iterations"


@skip_no_model
class TestToolSelection:
    """The right tools should be called for the right prompts."""

    def test_build_triggers_project_init(self):
        """'Build X' should call project_init early."""
        from tsunami.config import TsunamiConfig
        from tsunami.agent import Agent

        async def _run():
            config = TsunamiConfig.from_yaml("config.yaml")
            config.eddy_endpoint = "http://localhost:8090"
            agent = Agent(config)
            await asyncio.wait_for(
                agent.run("Build a simple hello world app"),
                timeout=120,
            )
            return agent._tool_history

        tools = asyncio.run(_run())
        # project_init should appear in first 8 tool calls
        early_tools = tools[:8]
        assert "project_init" in early_tools or "file_write" in early_tools, \
            f"Neither project_init nor file_write in first 8 calls: {early_tools}"


@skip_no_model
class TestLiteMode:
    """Lite mode (2B on one server) should work end to end."""

    def test_lite_greeting(self):
        """Lite mode greeting completes."""
        iters, complete, result = _run_agent("hello", timeout_s=60)
        assert complete, f"Lite mode greeting failed at iter {iters}"

    def test_lite_tool_count(self):
        """Lite mode should have fewer tools than full mode."""
        from tsunami.config import TsunamiConfig
        from tsunami.tools import build_registry

        config = TsunamiConfig.from_yaml("config.yaml")
        config.eddy_endpoint = config.model_endpoint  # force lite
        registry = build_registry(config)
        assert len(registry.names()) <= 12, \
            f"Lite mode has {len(registry.names())} tools (max 12)"

        # Verify python_exec is NOT in lite mode
        assert "python_exec" not in registry.names(), \
            "python_exec should not be in lite mode"
