"""Tests for Round G fixes — delivery gate + vision gate opened for
gamedev deliveries that don't call project_init (Fix #14).

Round G 2026-04-20 shipped an empty-entities game_definition.json
because the delivery-gate chain (run_deliver_gates + probe_for_delivery)
was gated on `self._project_init_called`. Gamedev deliveries use
emit_design as an engine-only alternative — project_init never fires —
so the gate chain skipped the bounce-back entirely.

Fix #14: both gates now fire on `_project_init_called OR
_has_gamedev_delivery` (game_definition.json exists under deliverables/).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def test_delivery_gate_check_includes_gamedev_fallback():
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The gate sits just below the "Declarative delivery gates" header
    idx = agent_py.find("# Declarative delivery gates")
    window = agent_py[idx:idx + 2000]
    # Must now check for _has_gamedev_delivery alongside _project_init_called
    assert "_has_gamedev_delivery" in window, (
        "delivery-gate check missing gamedev fallback — Round G-style "
        "empty-entity deliveries will ship without probe bouncing them"
    )
    # The fallback must actually detect game_definition.json under deliverables/
    assert "game_definition.json" in window


def test_vision_gate_check_includes_gamedev_fallback():
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # The vision gate sits later — around line 4497
    idx = agent_py.find('os.environ.get("TSUNAMI_VISION_GATE")')
    if idx < 0:
        idx = agent_py.find('_osv.environ.get("TSUNAMI_VISION_GATE")')
    assert idx > 0, "couldn't find vision-gate check"
    window = agent_py[idx:idx + 700]
    # Gamedev fallback must be present
    assert "_has_gamedev_delivery" in window, (
        "vision-gate check missing gamedev fallback"
    )


def test_gamedev_fallback_is_conservative():
    """The fallback triggers ONLY when `public/game_definition.json`
    exists under a `deliverables/<name>/` subdir — not for arbitrary
    game_*.json files anywhere."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    idx = agent_py.find("_has_gamedev_delivery = False")
    window = agent_py[idx:idx + 700]
    # Must navigate deliverables/ → <project>/public/game_definition.json
    assert 'deliverables' in window
    assert '"public"' in window
    assert '"game_definition.json"' in window


def test_fallback_swallows_exceptions():
    """If iterating deliverables/ throws (permission denied, stale
    mount), gate assembly must not crash the tool-call handler."""
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    idx = agent_py.find("_has_gamedev_delivery = False")
    window = agent_py[idx:idx + 600]
    assert "try:" in window
    assert "except Exception" in window


def test_is_gamedev_task_fallback_present():
    """Round H 2026-04-20 captured: wave shipped with NO deliverable
    at all. Gate-open on `_has_gamedev_delivery` missed it (file
    never existed). For gamedev tasks, always fire the gate chain so
    gamedev_probe can bounce a no-deliverable ship.

    Fix: check `_target_scaffold == "gamedev"` as a third OR-condition
    on the gate (alongside _project_init_called and _has_gamedev_delivery).
    """
    agent_py = (REPO / "tsunami" / "agent.py").read_text()
    # Delivery gate
    idx = agent_py.find("# Declarative delivery gates")
    window = agent_py[idx:idx + 2500]
    assert "_is_gamedev_task" in window, (
        "delivery gate missing _is_gamedev_task fallback — Round H "
        "no-deliverable ship will recur"
    )
    assert '_target_scaffold' in window and '== "gamedev"' in window
    # Vision gate
    idx = agent_py.find('_osv.environ.get("TSUNAMI_VISION_GATE")')
    window = agent_py[idx:idx + 500]
    assert "_is_gamedev_task" in window, (
        "vision gate missing _is_gamedev_task fallback"
    )


def main():
    tests = [
        test_delivery_gate_check_includes_gamedev_fallback,
        test_vision_gate_check_includes_gamedev_fallback,
        test_gamedev_fallback_is_conservative,
        test_fallback_swallows_exceptions,
        test_is_gamedev_task_fallback_present,
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
