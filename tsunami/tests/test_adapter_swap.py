"""LoRA adapter swap helper — pure-function tests.

Covers the QA feature request (per-request adapter selection): the swap
helper serializes state transitions via the caller's gpu_sem, short-circuits
when the adapter hasn't changed, and reports a status string the server can
log. No torch / transformers imports needed.
"""

from __future__ import annotations

from tsunami.adapter_swap import apply_adapter_swap


class _FakeModel:
    """Stand-in for a PEFT-wrapped model. Records which methods were called."""
    def __init__(self, supports=("set_adapter", "disable_adapter_layers")):
        self.calls: list[tuple[str, tuple, dict]] = []
        if "set_adapter" in supports:
            self.set_adapter = lambda name: self.calls.append(("set_adapter", (name,), {}))
        if "disable_adapter_layers" in supports:
            self.disable_adapter_layers = lambda: self.calls.append(("disable_adapter_layers", (), {}))
        if "load_adapter" in supports:
            self.load_adapter = lambda name, adapter_name=None: self.calls.append(
                ("load_adapter", (name,), {"adapter_name": adapter_name})
            )


def test_noop_when_target_matches_current():
    """Same adapter requested twice — second call is a no-op, no swap."""
    m = _FakeModel()
    status, new_current = apply_adapter_swap(m, "adapter-A", "adapter-A")
    assert status == "no-change"
    assert new_current == "adapter-A"
    assert m.calls == []


def test_swap_to_new_adapter_calls_set_adapter():
    m = _FakeModel()
    status, new_current = apply_adapter_swap(m, "adapter-B", "adapter-A")
    assert status == "swapped→adapter-B"
    assert new_current == "adapter-B"
    assert m.calls == [("set_adapter", ("adapter-B",), {})]


def test_swap_to_none_calls_disable_adapter_layers():
    """'none' → base model, calls disable_adapter_layers."""
    m = _FakeModel()
    status, new_current = apply_adapter_swap(m, "none", "adapter-A")
    assert status == "swapped→none"
    assert new_current == "none"
    assert m.calls == [("disable_adapter_layers", (), {})]


def test_swap_from_fresh_start():
    """First request ever — current is None, request asks for an adapter."""
    m = _FakeModel()
    status, new_current = apply_adapter_swap(m, "adapter-X", None)
    assert status == "swapped→adapter-X"
    assert new_current == "adapter-X"
    assert m.calls == [("set_adapter", ("adapter-X",), {})]


def test_fresh_adapter_skips_load_when_set_adapter_works():
    """PEFT's set_adapter activates an already-loaded-on-disk adapter.
    set_adapter always wins when present — load_adapter is the fallback path
    for adapters that weren't preloaded at --adapters-dir boot time."""
    m = _FakeModel(supports=("set_adapter", "load_adapter"))
    status, new_current = apply_adapter_swap(m, "adapter-new", None)
    assert status == "swapped→adapter-new"
    assert new_current == "adapter-new"
    # set_adapter wins; load_adapter is not called when set_adapter is available
    assert m.calls == [("set_adapter", ("adapter-new",), {})]


def test_unsupported_model_returns_unsupported():
    """Model with no adapter methods at all — status is 'unsupported'."""
    m = _FakeModel(supports=())
    status, new_current = apply_adapter_swap(m, "adapter-A", None)
    assert status == "unsupported"
    assert new_current is None  # state unchanged
    assert m.calls == []


def test_set_adapter_exception_returns_error_status():
    """Swap attempt raises — helper catches and reports without losing current."""
    m = _FakeModel()
    def _boom(name):
        raise RuntimeError("adapter weights missing on disk")
    m.set_adapter = _boom
    status, new_current = apply_adapter_swap(m, "adapter-broken", "adapter-A")
    assert status.startswith("error:")
    assert "adapter weights missing" in status
    assert new_current == "adapter-A"  # unchanged on failure


def test_abab_sequence_serializes_swaps():
    """A→B→A→B alternating: each transition costs one swap, same-adapter is free."""
    m = _FakeModel()
    current: str | None = None
    expected_calls: list[tuple[str, tuple, dict]] = []
    for target in ["A", "A", "B", "B", "A", "A", "B"]:
        status, current = apply_adapter_swap(m, target, current)
        if target != (expected_calls[-1][1][0] if expected_calls else None):
            expected_calls.append(("set_adapter", (target,), {}))
    # 4 distinct transitions in the A→A→B→B→A→A→B sequence
    assert len(m.calls) == 4
    assert [c[1][0] for c in m.calls] == ["A", "B", "A", "B"]
    assert current == "B"


def test_disable_attr_missing_returns_unsupported_for_none():
    """Model with set_adapter but no disable_adapter_layers — 'none' unsupported."""
    m = _FakeModel(supports=("set_adapter",))
    status, new_current = apply_adapter_swap(m, "none", "adapter-A")
    assert status == "unsupported"
    assert new_current == "adapter-A"
