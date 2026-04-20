"""Tests for F-E3 doctrine_history — delivery_count, cold_start, saturation."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))

from tsunami import doctrine_history as dh  # noqa: E402


def test_disabled_is_noop():
    dh.disable()
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh._DEFAULT_PATH = tmpfile
        dh.log_pick("style", "shadcn_startup")
        assert not tmpfile.exists()


def test_delivery_count():
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh.enable(tmpfile)
        try:
            for _ in range(35):
                dh.log_pick("style", "shadcn_startup")
            for _ in range(5):
                dh.log_pick("style", "photo_studio")
            assert dh.delivery_count("style", "shadcn_startup") == 35
            assert dh.delivery_count("style", "photo_studio") == 5
            assert dh.delivery_count("style", "nonexistent") == 0
        finally:
            dh.disable()


def test_cold_start_threshold():
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh.enable(tmpfile)
        try:
            for _ in range(29):
                dh.log_pick("style", "newsroom_editorial")
            # v9.1 C1 threshold: <30 is cold-start
            assert dh.is_cold_start("style", "newsroom_editorial") is True
            dh.log_pick("style", "newsroom_editorial")  # 30th
            assert dh.is_cold_start("style", "newsroom_editorial") is False
        finally:
            dh.disable()


def test_recent_picks():
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh.enable(tmpfile)
        try:
            # 3 style picks: A A B
            dh.log_pick("style", "atelier_warm")
            dh.log_pick("style", "atelier_warm")
            dh.log_pick("style", "swiss_modern")
            # Genre picks interleaved — should NOT show up for domain=style
            dh.log_pick("genre", "platformer")
            recent = dh.recent_picks("style", n=5)
            assert recent == ["atelier_warm", "atelier_warm", "swiss_modern"]
            recent_genre = dh.recent_picks("genre", n=5)
            assert recent_genre == ["platformer"]
        finally:
            dh.disable()


def test_saturation_signal_input():
    """F-E2 needs recent_picks(n=5).count(current) >= 4 to fire."""
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh.enable(tmpfile)
        try:
            for _ in range(5):
                dh.log_pick("style", "shadcn_startup")
            recent = dh.recent_picks("style", n=5)
            assert recent.count("shadcn_startup") == 5
            # Saturation threshold per F-E2 spec: >=4 of last 5
            assert recent.count("shadcn_startup") >= 4
        finally:
            dh.disable()


def test_empty_name_noop():
    with tempfile.TemporaryDirectory() as td:
        tmpfile = Path(td) / "history.jsonl"
        dh.enable(tmpfile)
        try:
            dh.log_pick("style", "")
            assert not tmpfile.exists() or tmpfile.read_text().strip() == ""
        finally:
            dh.disable()


def main():
    tests = [
        test_disabled_is_noop,
        test_delivery_count,
        test_cold_start_threshold,
        test_recent_picks,
        test_saturation_signal_input,
        test_empty_name_noop,
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
