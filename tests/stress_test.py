#!/usr/bin/env python3
"""
TSUNAMI Stress Test — Edge Cases and Resilience

Tests the agent loop handles real-world model misbehavior:
- Unknown tool names
- Malformed arguments
- Empty responses
- Error escalation after 3 failures
- Graceful recovery
- Session persistence through errors

Run: python stress_test.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tsunami.agent import Agent
from tsunami.config import TsunamiConfig
from tsunami.model import LLMModel, LLMResponse, ToolCall
from tsunami.tools.plan import set_agent_state


class MisbehavingModel(LLMModel):
    """A model that deliberately misbehaves to test error handling."""

    def __init__(self):
        self._step = 0
        self._script = [
            # Step 1: Empty response (no content, no tool call)
            ("_empty", None),
            # Step 2: Another empty response
            ("_empty", None),
            # Step 3: Unknown tool name
            ("_unknown_tool", {"nonexistent_tool": {"arg": "value"}}),
            # Step 4: Valid tool, wrong argument names
            ("_bad_args", {"file_read": {"wrong_param": "value"}}),
            # Step 5: Valid info message (recovery)
            ("message_info", {"text": "Recovered from errors. Adapting approach."}),
            # Step 6: Valid shell command
            ("shell_exec", {"command": "echo 'resilience test passed'"}),
            # Step 7: Valid file write
            ("file_write", {"path": "./workspace/stress_test_artifact.txt",
                           "content": "Created under duress. The loop held."}),
            # Step 8: Deliver
            ("message_result", {
                "text": "Stress test complete. Survived: 2 empty responses, 1 unknown tool, "
                        "1 bad argument set. Recovered and delivered."
            }),
        ]

    async def _call(self, messages, tools=None) -> LLMResponse:
        if self._step >= len(self._script):
            return LLMResponse(
                content="",
                tool_call=ToolCall(name="message_result",
                                   arguments={"text": "Script exhausted."}),
            )

        name, args = self._script[self._step]
        self._step += 1

        if name == "_empty":
            return LLMResponse(content="", tool_call=None)

        if name == "_unknown_tool":
            return LLMResponse(
                content="",
                tool_call=ToolCall(name="totally_fake_tool", arguments={"x": 1}),
            )

        if name == "_bad_args":
            return LLMResponse(
                content="",
                tool_call=ToolCall(name="file_read",
                                   arguments={"nonexistent_param": "/tmp/nope",
                                             "also_wrong": 42}),
            )

        return LLMResponse(
            content=f"[Stress step {self._step}]",
            tool_call=ToolCall(name=name, arguments=args),
        )


async def test_misbehaving_model():
    """Test that the agent loop survives model misbehavior."""
    print("  Test: Misbehaving model (empty, unknown tool, bad args)...")
    cfg = TsunamiConfig()
    cfg.ensure_dirs()
    agent = Agent(cfg)
    agent.model = MisbehavingModel()

    result = await agent.run("Stress test — survive model errors")

    assert agent.state.task_complete, f"Task should complete. Got: {result[:200]}"
    assert agent.state.iteration >= 5, f"Should have run 5+ iterations, got {agent.state.iteration}"

    # Check that the artifact was created despite errors
    artifact = Path("./workspace/stress_test_artifact.txt")
    assert artifact.exists(), "Artifact should exist despite earlier errors"
    content = artifact.read_text()
    assert "under duress" in content

    # Check that errors were tracked
    assert len(agent.state.error_counts) > 0, "Should have recorded errors"

    print(f"    PASS — {agent.state.iteration} iterations, "
          f"{len(agent.state.error_counts)} errors tracked, artifact created")
    return True


async def test_session_survives_errors():
    """Test that sessions are saved even when errors occur."""
    print("  Test: Session persistence through errors...")
    cfg = TsunamiConfig()
    cfg.ensure_dirs()
    agent = Agent(cfg)
    agent.model = MisbehavingModel()

    await agent.run("Session persistence test")

    session_dir = Path(cfg.workspace_dir) / ".history"
    sessions = list(session_dir.glob("*.jsonl"))
    assert len(sessions) > 0, "Should have saved at least one session"

    # Read the session and verify it has messages
    from tsunami.session import load_session
    loaded = load_session(session_dir, agent.session_id)
    assert loaded is not None, f"Session {agent.session_id} should be loadable"
    assert len(loaded.conversation) > 3, f"Session should have messages, got {len(loaded.conversation)}"

    print(f"    PASS — session {agent.session_id} saved with {len(loaded.conversation)} messages")
    return True


async def test_tool_argument_safety():
    """Test that tools handle unexpected arguments gracefully."""
    print("  Test: Tool argument safety...")
    from tsunami.tools.filesystem import FileRead, FileWrite
    from tsunami.tools.shell import ShellExec

    cfg = TsunamiConfig()

    # file_read with nonexistent file
    fr = FileRead(cfg)
    r = await fr.execute(path="/nonexistent/path/file.txt")
    assert r.is_error, "Should error on nonexistent file"

    # file_write with empty content
    fw = FileWrite(cfg)
    r = await fw.execute(path="./workspace/empty_test.txt", content="")
    assert not r.is_error, "Empty content should be valid"
    Path("./workspace/empty_test.txt").unlink(missing_ok=True)

    # shell with command that fails
    sh = ShellExec(cfg)
    r = await sh.execute(command="false")  # always exits 1
    assert r.is_error, "Failed command should be marked as error"

    # shell with very short timeout
    r = await sh.execute(command="sleep 10", timeout=1)
    assert r.is_error, "Should timeout"
    assert "timed out" in r.content.lower()

    print("    PASS — all edge cases handled gracefully")
    return True


async def test_plan_edge_cases():
    """Test plan lifecycle edge cases."""
    print("  Test: Plan edge cases...")
    from tsunami.state import AgentState, Plan, Phase
    from tsunami.tools.plan import PlanUpdate, PlanAdvance, set_agent_state

    cfg = TsunamiConfig()
    state = AgentState()
    set_agent_state(state)

    # Advance with no plan
    pa = PlanAdvance(cfg)
    r = await pa.execute(summary="test")
    assert r.is_error, "Advancing with no plan should error"

    # Create plan
    pu = PlanUpdate(cfg)
    r = await pu.execute(goal="test", phases=[{"title": "Only phase"}])
    assert not r.is_error

    # Advance past all phases
    r = await pa.execute(summary="done")
    assert "ALL PHASES COMPLETE" in r.content

    # Advance again when all complete
    r = await pa.execute(summary="extra")
    assert "ALL PHASES COMPLETE" in r.content or r.is_error

    print("    PASS — plan lifecycle handles all edge cases")
    return True


async def test_compression_safety():
    """Test that compression doesn't crash on small conversations."""
    print("  Test: Compression safety...")
    from tsunami.compression import needs_compression, estimate_tokens
    from tsunami.state import AgentState

    # Empty state
    state = AgentState()
    assert not needs_compression(state), "Empty state shouldn't need compression"
    assert estimate_tokens(state) == 0

    # Small state
    state.add_user("hello")
    assert not needs_compression(state)

    print("    PASS — compression safe on edge cases")
    return True


def main():
    print("=" * 60)
    print("  TSUNAMI STRESS TEST — Edge Cases & Resilience")
    print("=" * 60)
    print()

    tests = [
        test_tool_argument_safety,
        test_plan_edge_cases,
        test_compression_safety,
        test_misbehaving_model,
        test_session_survives_errors,
    ]

    passed = 0
    failed = 0

    for test_fn in tests:
        try:
            asyncio.run(test_fn())
            passed += 1
        except Exception as e:
            print(f"    FAIL: {e}")
            failed += 1

    print()
    print("-" * 60)
    print(f"  Stress results: {passed} passed, {failed} failed")
    print("-" * 60)

    if failed == 0:
        print()
        print("  The loop held under stress.")
        print("  Empty responses, unknown tools, bad arguments,")
        print("  timeouts, failed commands — all survived.")
        print("  The standing wave is resilient.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
