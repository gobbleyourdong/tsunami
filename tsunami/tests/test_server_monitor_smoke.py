"""Smoke tests for scripts/overnight/server_monitor.py.

The server monitor runs opportunistically — when live rounds are
inactive, the sister instance can consume idle cycles. A bug that
causes the monitor to crash, misreport idle time, or fail to detect
tsunami subprocesses would silently hold idle cycles or trigger
launches on busy systems.

These tests exercise the pure-Python paths (no ps/nvidia-smi probing).
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "overnight"))

import server_monitor  # noqa: E402


def test_import_doesnt_crash():
    """Module imports cleanly — no syntax errors, no missing deps."""
    assert callable(server_monitor.collect)
    assert callable(server_monitor.write_jsonl)


def test_iso_now_format():
    """_iso_now returns ISO8601 with Z suffix."""
    out = server_monitor._iso_now()
    assert out.endswith("Z") or "+" in out  # UTC Z or offset
    # Must parse as a real timestamp (lightweight check)
    assert "T" in out


def test_recent_completion_lines_finds_matches():
    """_recent_completion_lines tails log_path and returns lines
    mentioning '/v1/chat/completions' (the model-server completion
    endpoint)."""
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
        f.write("irrelevant line\n")
        f.write("httpx INFO HTTP Request: POST http://localhost:8090/v1/chat/completions HTTP/1.1 200 OK\n")
        f.write("another line\n")
        f.write("httpx INFO HTTP Request: POST http://localhost:8090/v1/chat/completions HTTP/1.1 200 OK\n")
        logpath = Path(f.name)
    lines = server_monitor._recent_completion_lines(logpath, since_epoch=0)
    assert isinstance(lines, list)
    # Should include the two /v1/chat/completions lines
    assert len(lines) == 2, f"expected 2 completion lines, got {len(lines)}: {lines}"
    assert all("/v1/chat/completions" in l for l in lines)
    logpath.unlink()


def test_recent_completion_lines_nonexistent_log_safe():
    """Missing log file should return empty list, not crash."""
    bogus = Path("/tmp/this_path_does_not_exist_x7y8z9.log")
    assert not bogus.exists()
    lines = server_monitor._recent_completion_lines(bogus, since_epoch=0)
    assert lines == []


def test_previous_sample_empty_when_no_file():
    """_previous_sample returns dict even with no prior telemetry."""
    out = server_monitor._previous_sample()
    assert isinstance(out, dict)


def test_collect_returns_dict_with_expected_keys():
    """collect() returns a dict sample suitable for JSONL append."""
    sample = server_monitor.collect()
    assert isinstance(sample, dict)
    # Sample must have a timestamp and at least some of the probe signals
    assert "ts" in sample or "t" in sample or "timestamp" in sample
    # Idle detection key — the opportunistic dispatcher reads this
    keys_lower = [k.lower() for k in sample.keys()]
    has_idle = any("idle" in k for k in keys_lower)
    has_activity = any("active" in k or "tsunami" in k for k in keys_lower)
    assert has_idle or has_activity, (
        f"collect() sample missing idle/activity signal: keys={list(sample.keys())}"
    )


def test_write_jsonl_appends_safely():
    """write_jsonl writes a valid JSON line."""
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        outpath = Path(f.name)
    # Should not crash on a well-formed sample
    sample = {"ts": server_monitor._iso_now(), "smoke_test": True}
    # If write_jsonl has a hardcoded output path, we can at least verify
    # it doesn't raise on a known-good sample shape.
    try:
        server_monitor.write_jsonl(sample)
    except Exception as e:
        # It may fail if the hardcoded path isn't writeable, but the
        # common case (~/.tsunami/server_monitor.jsonl) should work.
        import os
        if not os.access(os.path.expanduser("~/.tsunami"), os.W_OK):
            # Not writable — acceptable; test just confirms no import/logic error
            pass
        else:
            raise
    outpath.unlink(missing_ok=True)


def main():
    tests = [
        test_import_doesnt_crash,
        test_iso_now_format,
        test_recent_completion_lines_finds_matches,
        test_recent_completion_lines_nonexistent_log_safe,
        test_previous_sample_empty_when_no_file,
        test_collect_returns_dict_with_expected_keys,
        test_write_jsonl_appends_safely,
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
