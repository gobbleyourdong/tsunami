"""Doctrine delivery history (F-E3).

Append-only JSONL log of every doctrine pick that survived all the way
to `format_*_directive()` injection. Answers three downstream questions:

  1. delivery_count(domain, name) — has this doctrine seen ≥30 deliveries?
     (v9.1 C1 Output Quality Gradient: first 30 runs are cold-start)
  2. recent_picks(domain, n) — saturation signal source for F-E2
  3. Per-doctrine adoption histograms — feeds morning consolidator

OPT-IN via env TSUNAMI_DOCTRINE_HISTORY=1 OR enable() at process start.
Non-blocking; swallows I/O errors.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

_DEFAULT_PATH = Path.home() / ".tsunami" / "telemetry" / "doctrine_history.jsonl"

_ENABLED_AT_RUNTIME = False


def enable(path: str | Path | None = None) -> None:
    global _ENABLED_AT_RUNTIME, _DEFAULT_PATH
    _ENABLED_AT_RUNTIME = True
    if path:
        _DEFAULT_PATH = Path(path)


def disable() -> None:
    global _ENABLED_AT_RUNTIME
    _ENABLED_AT_RUNTIME = False


def _enabled() -> bool:
    return _ENABLED_AT_RUNTIME or os.environ.get("TSUNAMI_DOCTRINE_HISTORY") == "1"


def _path() -> Path:
    override = os.environ.get("TSUNAMI_TELEMETRY_DIR")
    if override:
        return Path(override) / "doctrine_history.jsonl"
    return _DEFAULT_PATH


def log_pick(
    domain: str,
    name: str,
    scaffold: str = "",
    task_hash: str = "",
) -> None:
    """Append one pick. domain ∈ {style, genre, industry, game_replica}."""
    if not _enabled() or not name:
        return
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        ev = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            "domain": domain,
            "name": name,
            "scaffold": scaffold,
            "task_hash": task_hash,
        }
        with path.open("a") as f:
            f.write(json.dumps(ev) + "\n")
    except Exception:
        pass


def _iter_events(path: Path | None = None):
    p = path or _path()
    if not p.is_file():
        return
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def delivery_count(domain: str, name: str, path: Path | None = None) -> int:
    """How many deliveries has this (domain, name) pair served?"""
    return sum(
        1 for ev in _iter_events(path)
        if ev.get("domain") == domain and ev.get("name") == name
    )


def is_cold_start(domain: str, name: str, threshold: int = 30) -> bool:
    """v9.1 C1 — first N deliveries are cold-start; don't judge quality."""
    return delivery_count(domain, name) < threshold


def recent_picks(domain: str, n: int = 10, path: Path | None = None) -> list[str]:
    """Last n picks for this domain, oldest first. Feeds F-E2 saturation
    detector in progress.py."""
    picks = [ev["name"] for ev in _iter_events(path) if ev.get("domain") == domain]
    return picks[-n:]


def picks_by_domain(path: Path | None = None) -> dict[str, Counter]:
    """Per-domain name → count. Used by the morning consolidator."""
    out: dict[str, Counter] = {}
    for ev in _iter_events(path):
        dom = ev.get("domain", "")
        name = ev.get("name", "")
        if not name:
            continue
        out.setdefault(dom, Counter())[name] += 1
    return out


__all__ = [
    "enable", "disable",
    "log_pick", "delivery_count", "is_cold_start",
    "recent_picks", "picks_by_domain",
]
