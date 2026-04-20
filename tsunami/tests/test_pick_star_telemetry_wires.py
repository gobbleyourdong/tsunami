"""Tests for the 4 pick_* telemetry wires (F-C1 + F-C2).

Each router that returns a single winner must call
`routing_telemetry.log_pick` with the outcome. This is a regression
guard: if someone refactors a picker and forgets the log_pick line,
the morning stall_report would silently miss that domain's events
— and the dark-pattern never gets detected.

Approach: import + invoke each picker with telemetry enabled into a
temp dir, confirm the jsonl line appears with the expected domain.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO))


def _read_routing_events(log_dir: Path) -> list[dict]:
    path = log_dir / "routing.jsonl"
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text().strip().splitlines() if l.strip()]


def test_pick_scaffold_logs_event():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            from tsunami.planfile import pick_scaffold
            result = pick_scaffold("build a kanban board")
            events = _read_routing_events(Path(td))
            assert any(e["domain"] == "scaffold" and e["winner"] == result
                       for e in events), f"no scaffold event: {events}"
        finally:
            rt.disable()


def test_pick_style_logs_event():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            from tsunami.style_scaffolds import pick_style
            pick_style("brutalist website", "react-app")
            events = _read_routing_events(Path(td))
            assert any(e["domain"] == "style" for e in events), (
                f"no style event: {events}"
            )
        finally:
            rt.disable()


def test_pick_industry_logs_event():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            from tsunami.brand_scaffold import _match_industry
            _match_industry("hypercar manufacturer landing")
            events = _read_routing_events(Path(td))
            assert any(e["domain"] == "industry" for e in events), (
                f"no industry event: {events}"
            )
        finally:
            rt.disable()


def test_pick_game_replica_logs_event_on_match():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            from tsunami.game_content import pick_game_replica
            result = pick_game_replica("build a zelda-like top-down")
            events = _read_routing_events(Path(td))
            assert any(
                e["domain"] == "game_replica" and e["winner"] == result
                for e in events
            ), f"no game_replica event: {events}"
        finally:
            rt.disable()


def test_pick_genre_logs_event_when_scaffold_gamedev():
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            from tsunami.genre_scaffolds import pick_genre
            pick_genre("build a zelda-like", "gamedev")
            events = _read_routing_events(Path(td))
            assert any(e["domain"] == "genre" for e in events), (
                f"no genre event: {events}"
            )
        finally:
            rt.disable()


def test_all_4_domains_one_session():
    """Integration — run a gamedev prompt through all pick_ paths,
    verify all 4 domains land in the routing log."""
    from tsunami import routing_telemetry as rt
    with tempfile.TemporaryDirectory() as td:
        rt.enable(log_dir=td)
        try:
            prompt = "build a zelda-like top-down action-adventure"
            from tsunami.planfile import pick_scaffold
            scaffold = pick_scaffold(prompt)
            from tsunami.genre_scaffolds import pick_genre
            pick_genre(prompt, scaffold)
            from tsunami.style_scaffolds import pick_style
            pick_style(prompt, scaffold)
            from tsunami.brand_scaffold import _match_industry
            _match_industry(prompt)
            from tsunami.game_content import pick_game_replica
            pick_game_replica(prompt)
            events = _read_routing_events(Path(td))
            domains = {e["domain"] for e in events}
            expected = {"scaffold", "genre", "style", "industry", "game_replica"}
            assert expected <= domains, (
                f"missing domains: {expected - domains}"
            )
        finally:
            rt.disable()


def main():
    tests = [
        test_pick_scaffold_logs_event,
        test_pick_style_logs_event,
        test_pick_industry_logs_event,
        test_pick_game_replica_logs_event_on_match,
        test_pick_genre_logs_event_when_scaffold_gamedev,
        test_all_4_domains_one_session,
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
