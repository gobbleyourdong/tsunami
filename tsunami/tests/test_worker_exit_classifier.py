"""Tests for worker.py's exit_reason classification (Fix #32).

Round X (2026-04-20) post-mortem: when the model server was down,
the wave got 5x "Model unreachable" errors and then shipped an empty
message_result with returncode=0. The worker reported this as
`exit_reason: "message_result"` — indistinguishable in runs.jsonl
from a clean non-timeout delivery.

Fix #32 (post-Round X): worker.py scans session log for "Model
unreachable" hits AFTER returncode=0 and reclassifies as
`error:server_unreachable`. This test verifies the detection logic
without actually spawning a subprocess — by checking that the right
reclassification code path exists in the source AND its threshold
matches the heuristic.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def test_worker_classifies_server_unreachable_after_message_result():
    """When returncode=0 (nominal message_result) but session log has
    'Model unreachable' 3+ times, reclassify as error:server_unreachable."""
    src = (REPO / "scripts" / "overnight" / "worker.py").read_text()
    # The reclassification block must be present
    assert 'error:server_unreachable' in src, (
        "worker.py missing server_unreachable reclassification — "
        "Round X-style failures misreport as clean deliveries"
    )
    # Must look for 'Model unreachable' pattern in session log
    assert 'Model unreachable' in src, (
        "reclassifier doesn't scan for 'Model unreachable' marker"
    )
    # Must only trigger when exit_reason was already 'message_result'
    # (don't touch timeout/error classifications)
    assert 'if exit_reason == "message_result":' in src, (
        "reclassifier should only refine message_result, not other kinds"
    )


def test_reclassifier_threshold_is_meaningful():
    """The threshold (3+ hits) should be in source as a real number,
    not magic. Scanning source for the condition guarantees the check
    is non-trivial."""
    src = (REPO / "scripts" / "overnight" / "worker.py").read_text()
    # Either '>= 3' or similar arithmetic comparison on unreachable_hits
    pattern = r'unreachable_hits\s*>=\s*(\d+)'
    m = re.search(pattern, src)
    assert m, "no unreachable_hits threshold check in worker.py"
    threshold = int(m.group(1))
    # Threshold between 1 and 10 is reasonable
    assert 1 <= threshold <= 10, f"threshold {threshold} is out of reasonable range"


def test_reclassifier_wrapped_in_try_except():
    """File I/O can fail (permission, truncated log) — the scan must
    not crash the worker if session log is unreadable. The try/except
    wraps the reclassifier block (look in a wider window for it)."""
    src = (REPO / "scripts" / "overnight" / "worker.py").read_text()
    # Find the reclassifier block; it should have a try/except
    idx = src.find('if exit_reason == "message_result":')
    assert idx >= 0, "reclassifier entry condition missing"
    # Window after the if-line through the next ~600 chars should show try/except
    window = src[idx:idx + 800]
    assert "try:" in window, "reclassifier missing try block"
    assert "except" in window, "reclassifier missing except block"


def main():
    tests = [
        test_worker_classifies_server_unreachable_after_message_result,
        test_reclassifier_threshold_is_meaningful,
        test_reclassifier_wrapped_in_try_except,
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
