"""Tests for Fix #15 (Round J) — anti-spiral and phase-machine nudges must
route to emit_design (gamedev) vs project_init (react-app) correctly.
Also covers Fix #16, #19, #20, #22, #31 (all scaffold-aware nudge
mechanics; see individual test docstrings).

Round J 2026-04-20 captured: wave received GAMEDEV OVERRIDE at turn 1
saying "do not call project_init" — but every 3-5 file_reads the
anti-spiral system_note fired "Call project_init NOW" + "file_write
App.tsx". Contradictory instructions broke the wave.

Fix: phase_machine.context_note accepts scaffold_kind, emits
gamedev-specific advice when scaffold_kind=='gamedev'. The agent's
read-spiral redirect also checks self._target_scaffold.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def test_phase_machine_default_react_advice():
    """Default (scaffold_kind='react-app') still gets the old
    project_init advice — no regression for web builds."""
    from tsunami.phase_machine import PhaseMachine, Phase
    pm = PhaseMachine()
    pm.phase = Phase.SCAFFOLD
    pm.iters_in_phase = 4
    note = pm.context_note()
    assert "PHASE:SCAFFOLD" in note
    assert "project_init" in note
    assert "emit_design" not in note


def test_phase_machine_gamedev_routes_to_emit_design():
    """scaffold_kind='gamedev' swaps project_init → emit_design."""
    from tsunami.phase_machine import PhaseMachine, Phase
    pm = PhaseMachine()
    pm.phase = Phase.SCAFFOLD
    pm.iters_in_phase = 4
    note = pm.context_note(scaffold_kind="gamedev")
    assert "PHASE:SCAFFOLD-gamedev" in note
    assert "emit_design" in note
    # project_init explicitly advised against
    assert "Do NOT call project_init" in note


def test_phase_machine_gamedev_write_phase_routes_too():
    from tsunami.phase_machine import PhaseMachine, Phase
    pm = PhaseMachine()
    pm.phase = Phase.WRITE
    pm.iters_in_phase = 5
    pm.files_written = 0
    note = pm.context_note(scaffold_kind="gamedev")
    assert "PHASE:WRITE-gamedev" in note
    assert "emit_design" in note
    assert "NOT file_write(App.tsx)" in note
    assert "CONTENT CATALOG" in note


def test_agent_read_spiral_redirect_is_scaffold_aware():
    """agent.py's read-spiral redirect ("Plan your next 1-3 writes...")
    must branch on _target_scaffold == 'gamedev'. Round J captured the
    old non-branching version contradicting the override."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Must have both the original (react-app) and the gamedev variant
    assert 'Plan your next 1-3 writes. For {proj} (react-app scaffold)' in agent_py
    assert 'Plan your next move. For {proj} (GAMEDEV scaffold)' in agent_py
    # The gamedev variant must point to emit_design
    gamedev_idx = agent_py.find("GAMEDEV scaffold")
    window = agent_py[gamedev_idx:gamedev_idx + 800]
    assert "emit_design" in window
    assert "project_init" in window  # but negated (forbidden)
    assert "Do NOT" in window


def test_agent_passes_scaffold_kind_to_phase_machine():
    """agent.py must call phase_machine.context_note(scaffold_kind=...)
    with the correct value, not the default."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The call site must pass scaffold_kind
    assert "phase_machine.context_note(scaffold_kind=" in agent_py
    # The derivation must check both _target_scaffold AND plan Design section
    # (belt-and-suspenders — either source alone is sufficient)
    assert "_target_scaffold" in agent_py
    assert 'plan_manager.section("Design")' in agent_py


def test_emit_design_is_hard_forceable():
    """Round K 2026-04-20 finding: loop_guard correctly set
    forced_action='emit_design' for a stalled gamedev wave, but the
    enforcement block in agent.py only hard-forced file_write /
    shell_exec / message_result — emit_design remained advisory-only
    and the wave ignored 6 consecutive nudges. Fix: add emit_design
    to the hard-force tuple so the tool-schema filter at line ~2200
    physically restricts the drone to emit_design when flagged."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The hard-force tuple must include emit_design
    import re
    # Match the multi-line tuple literal after `forced_action in (`
    match = re.search(
        r'forced_action\s+in\s+\(\s*([^)]+)\)',
        agent_py,
    )
    assert match, "hard-force tuple not found in agent.py"
    tuple_body = match.group(1)
    for required in ("file_write", "shell_exec", "message_result", "emit_design"):
        assert f'"{required}"' in tuple_body, (
            f"{required} missing from hard-force tuple — Round K regression. "
            f"Tuple body: {tuple_body!r}"
        )


def test_loop_forced_tool_cleared_on_emit_design_success():
    """Once the drone successfully emits the forced tool, the
    persistent force must clear so normal schemas resume. Previously
    only file_write / message_result satisfied the clear — but since
    emit_design is now hard-forceable, a successful emit_design call
    must also satisfy and clear the flag. The cleanup block checks
    `tool_call.name in (_pf, "message_result")` which already covers
    emit_design because _pf == forced tool == emit_design."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Confirm the cleanup branch uses a dynamic equality against _pf,
    # not a hardcoded tuple (which would need updating for each new
    # forceable tool).
    assert 'tool_call.name in (_pf, "message_result")' in agent_py, (
        "Cleanup branch must check dynamic _pf, not hardcoded tool list — "
        "otherwise emit_design would stay stuck-forced even after success"
    )


def test_loop_guard_suggests_emit_design_for_gamedev_read_spiral():
    """End-to-end: loop_guard, given gamedev scaffold, must return
    forced_action='emit_design' for a read-spiral — not project_init
    (which contradicts GAMEDEV OVERRIDE)."""
    from tsunami.loop_guard import LoopGuard
    lg = LoopGuard()
    # Simulate 5 consecutive file_reads (soft-loop threshold)
    for _ in range(5):
        lg.record("file_read", {"path": "engine/src/design/schema.ts"}, made_progress=False)
    detection = lg.check(scaffold_kind="gamedev")
    assert detection.detected, "5 file_reads should trip soft loop"
    assert detection.forced_action == "emit_design", (
        f"gamedev read-spiral must route to emit_design, got {detection.forced_action!r}"
    )


def test_gamedev_soft_loop_fires_at_4_reads_not_5():
    """Fix #31 (Round U 2026-04-20): gamedev uses a lower threshold
    (4 file_reads) than react (5) to save one iteration's budget when
    first-token is slow. Round U timed out after 6 file_reads with no
    emit_design because the 5th-read trigger left insufficient budget
    for the emit_design generation.

    This test proves the 4-threshold kicks in for gamedev but the
    5-threshold stays for react-app — no regression. Uses distinct
    paths per call so the hard-loop-3x-identical doesn't mask the
    soft-loop-N-same-tool check."""
    from tsunami.loop_guard import LoopGuard
    # Gamedev: 4 reads (distinct paths) should trip SOFT loop
    lg_gd = LoopGuard()
    for i in range(4):
        lg_gd.record("file_read", {"path": f"x{i}.ts"}, made_progress=False)
    det_gd = lg_gd.check(scaffold_kind="gamedev")
    assert det_gd.detected, (
        "4 distinct file_reads should trip soft loop for gamedev (Fix #31)"
    )
    assert det_gd.loop_type == "soft", (
        f"expected soft loop, got {det_gd.loop_type}"
    )
    # React: 4 distinct file_reads should NOT trip (threshold is 5)
    lg_react = LoopGuard()
    for i in range(4):
        lg_react.record("file_read", {"path": f"x{i}.ts"}, made_progress=False)
    det_r = lg_react.check(scaffold_kind="react-app")
    # React may have a progress-stall fire (no writes), but not a SOFT loop
    assert not det_r.detected or det_r.loop_type != "soft", (
        f"4 file_reads should NOT trip SOFT loop for react — got {det_r.loop_type}"
    )
    # React: 5 distinct file_reads should trip soft loop
    lg_react.record("file_read", {"path": "x4.ts"}, made_progress=False)
    det_r5 = lg_react.check(scaffold_kind="react-app")
    assert det_r5.detected and det_r5.loop_type == "soft", (
        f"5 file_reads should trip SOFT loop for react, got {det_r5.loop_type}"
    )


def test_force_tool_schema_filter_exists():
    """The force_tool schema filter at agent.py:~2571 is the mechanism
    Fix #16 relies on. Without it, _loop_forced_tool='emit_design' would
    set force_tool='emit_design' but the drone would still see the full
    tool list and ignore the advisory. Guard that the filter is still
    present: `if force_tool: all_schemas = [tool_obj.schema()] if tool_obj else []`."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The schema filter block must be present verbatim.
    assert "if force_tool:" in agent_py, "force_tool schema filter removed"
    # Must resolve the tool from the registry (not hardcode schema)
    assert "tool_obj = self.registry.get(force_tool)" in agent_py
    # Must produce a single-item schema list (or empty on missing tool)
    assert "[tool_obj.schema()] if tool_obj else []" in agent_py, (
        "Schema list must contain ONLY the forced tool — any widening "
        "breaks Fix #16's hard-force guarantee"
    )


def test_force_tool_hand_back_to_pending_force():
    """The _pending_force → force_tool hand-off at agent.py:~2204 is
    what makes the force persist across iterations. Without it, the
    force would reset every turn and the drone could bypass it with
    one refusal."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    assert '_pending_force = getattr(self, "_loop_forced_tool", None)' in agent_py
    assert "if _pending_force:" in agent_py
    assert "force_tool = _pending_force" in agent_py


def test_gamedev_runs_probe_alongside_vision_gate():
    """Gap #20 / §14 item 6: gamedev scaffolds produce BOTH dist/index.html
    (engine SPA) AND public/game_definition.json. The pre-fix code
    branched mutually-exclusively (dist_html.is_file() → vision_check
    only; else → probe_for_delivery only). Gamedev needs BOTH:
    vision-gate for the rendered SPA, probe for the compiled design.

    Without this, gamedev deliveries with a built dist/ would ship
    with only vision coverage — the gamedev_probe's catalog-composition
    and entity-count checks would never fire."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Must have a gamedev-specific probe invocation in the vision branch
    assert '_target_scaffold' in agent_py
    # The fix inserts a gamedev-specific probe_for_delivery call AFTER
    # the vision_check in the dist_html-exists branch.
    assert "[gamedev-probe@deliver]" in agent_py, (
        "Fix #20 removed — gamedev probe must run alongside vision at "
        "delivery time. Without this, gamedev deliveries ship with no "
        "game_definition.json validation at the delivery gate."
    )
    # The probe call must be guarded by scaffold=gamedev so react-app
    # doesn't double-gate.
    import re
    match = re.search(
        r'if getattr\(self, "_target_scaffold", ""\) == "gamedev":(.*?)break',
        agent_py, re.DOTALL,
    )
    assert match, "gamedev probe branch guard missing"
    branch = match.group(1)
    assert "probe_for_delivery" in branch
    assert "game_definition" in branch.lower() or "game definition" in branch.lower() or "gamedev" in branch.lower()


def test_validation_failed_tool_calls_count_in_loop_guard():
    """Gap #19 (Round M 2026-04-20): validation-failed tool calls at
    agent.py:3377 used to return early BEFORE loop_guard.record() at
    line 3569. A wave emitting 5 consecutive file_reads where one had
    a malformed arg (e.g. `"limit": "200, offset: 366"`) would only
    count 4 in loop_guard.tool_names — soft-loop (5) never tripped.

    Round M captured this exactly: iter 3 had `'limit' expected integer,
    got str`, and no loop-guard force activated; wave spent 10 min
    generating 6K tokens of text instead of an emit_design call."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The validation-error branch must include a loop_guard.record() call
    # before the early return.
    import re
    # Look for the validation-error block
    match = re.search(
        r'validation_error\s*=\s*tool\.validate_input.*?return error_msg',
        agent_py, re.DOTALL,
    )
    assert match, "validation-error branch not found — agent.py schema changed"
    branch = match.group(0)
    assert "self.loop_guard.record(" in branch, (
        "validation-error branch must call loop_guard.record() before "
        "returning — otherwise validation-failed calls don't count "
        "toward soft-loop detection (gap #19)"
    )


def test_deliver_gates_flags_include_target_scaffold():
    """Gap #22 (Round N 2026-04-20): the _flags dict passed to
    run_deliver_gates at agent.py:~4677 must include 'target_scaffold'
    so code_write_gate's gamedev branch (deliver_gates.py:101) can
    route to the game_definition.json check. Without this key, every
    gamedev delivery was misrouted to the React branch's
    "App.tsx not written" message."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    import re
    # Find the _flags dict construction around run_deliver_gates
    match = re.search(
        r'_flags\s*=\s*\{([^}]+)\}\s*\n\s*_failure\s*=\s*run_deliver_gates',
        agent_py, re.DOTALL,
    )
    assert match, "_flags dict or run_deliver_gates call not found"
    flags_body = match.group(1)
    assert '"target_scaffold"' in flags_body, (
        "_flags dict missing 'target_scaffold' key — gamedev branch of "
        "code_write_gate will never activate (gap #22)"
    )
    assert '_target_scaffold' in flags_body, (
        "_flags must pass self._target_scaffold value, not a hardcoded string"
    )


def test_emit_design_tool_is_registered():
    """Sanity: hard-forcing emit_design is only meaningful if it's
    a registered tool. If emit_design ever got removed from the
    registry (e.g. accidental toolbox refactor), force_tool='emit_design'
    would produce an empty schema list and the drone would have NO
    tools available — effectively bricking the wave."""
    from tsunami.tools import build_registry
    from tsunami.config import TsunamiConfig
    cfg = TsunamiConfig(workspace_dir="/tmp/test_reg_check")
    reg = build_registry(cfg)
    tool = reg.get("emit_design")
    assert tool is not None, "emit_design must be registered for hard-force to work"
    schema = tool.schema()
    assert schema.get("function", {}).get("name") == "emit_design", (
        f"emit_design schema malformed: {schema}"
    )


def main():
    tests = [
        test_phase_machine_default_react_advice,
        test_phase_machine_gamedev_routes_to_emit_design,
        test_phase_machine_gamedev_write_phase_routes_too,
        test_agent_read_spiral_redirect_is_scaffold_aware,
        test_agent_passes_scaffold_kind_to_phase_machine,
        test_emit_design_is_hard_forceable,
        test_loop_forced_tool_cleared_on_emit_design_success,
        test_loop_guard_suggests_emit_design_for_gamedev_read_spiral,
        test_gamedev_soft_loop_fires_at_4_reads_not_5,
        test_force_tool_schema_filter_exists,
        test_force_tool_hand_back_to_pending_force,
        test_validation_failed_tool_calls_count_in_loop_guard,
        test_gamedev_runs_probe_alongside_vision_gate,
        test_deliver_gates_flags_include_target_scaffold,
        test_emit_design_tool_is_registered,
    ]
    failed = []
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed.append(t.__name__)
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed.append(t.__name__)
    print()
    if failed:
        print(f"RESULT: {len(failed)}/{len(tests)} failed: {failed}")
        sys.exit(1)
    print(f"RESULT: {len(tests)}/{len(tests)} passed")


if __name__ == "__main__":
    main()
