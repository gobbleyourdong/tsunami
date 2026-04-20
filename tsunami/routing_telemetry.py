"""Routing telemetry (F-C1 / F-C4).

Append-only JSONL log of every `pick_*` outcome and every
`force_miss` ledger entry. Non-blocking: swallows all I/O errors so a
disk-full scenario never breaks the agent loop.

Per sigma v7.1 Struggle-as-Signal: the distribution of routing
fallbacks IS the corpus gap map. Aggregator `stall_report()` groups
events by (domain, winner) so the top fall-through keywords surface
for the next essence-extraction pass.

OPT-IN behavior change. `log_pick` is a no-op unless either:
  * env TSUNAMI_ROUTING_TELEMETRY=1 is set, OR
  * a caller has explicitly called enable() at process start.

This lets the overnight dispatcher turn telemetry on per-worker
without changing behavior of normal interactive tsunami runs.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

_DEFAULT_LOG_DIR = Path.home() / ".tsunami" / "telemetry"
_ROUTING_LOG = "routing.jsonl"
_FORCE_MISS_LOG = "force_miss.jsonl"

_ENABLED_AT_RUNTIME = False


def enable(log_dir: str | Path | None = None) -> None:
    """Turn on telemetry for the current process (bypasses the env check)."""
    global _ENABLED_AT_RUNTIME, _DEFAULT_LOG_DIR
    _ENABLED_AT_RUNTIME = True
    if log_dir:
        _DEFAULT_LOG_DIR = Path(log_dir)


def disable() -> None:
    global _ENABLED_AT_RUNTIME
    _ENABLED_AT_RUNTIME = False


def _enabled() -> bool:
    return _ENABLED_AT_RUNTIME or os.environ.get("TSUNAMI_ROUTING_TELEMETRY") == "1"


def _log_dir() -> Path:
    override = os.environ.get("TSUNAMI_TELEMETRY_DIR")
    return Path(override) if override else _DEFAULT_LOG_DIR


@dataclass
class RoutingEvent:
    ts: str
    domain: str            # scaffold | style | genre | industry | game_replica
    task_hash: str         # sha256[:12] of normalized task text
    task_len: int
    winner: str            # rule that matched, or `default`
    default: str           # the default value when no rule matched
    match_source: str      # keyword | env | random | default | seed | explore


def log_pick(
    domain: str,
    task: str,
    winner: str,
    default: str,
    match_source: str = "keyword",
) -> None:
    """Append a routing event. Non-blocking. No-op unless enabled."""
    if not _enabled():
        return
    try:
        path = _log_dir() / _ROUTING_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        ev = RoutingEvent(
            ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
            domain=domain,
            task_hash=hashlib.sha256(task.strip().lower().encode()).hexdigest()[:12],
            task_len=len(task),
            winner=winner if winner else default,
            default=default,
            match_source=match_source,
        )
        with path.open("a") as f:
            f.write(json.dumps(asdict(ev)) + "\n")
    except Exception:
        pass


def log_force_miss(forced: str, actual: str, iteration: int) -> None:
    """Append a force-miss event (F-C4). Non-blocking. No-op unless enabled."""
    if not _enabled():
        return
    try:
        path = _log_dir() / _FORCE_MISS_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
                "forced": forced,
                "actual": actual,
                "iteration": iteration,
            }) + "\n")
    except Exception:
        pass


def _iter_events(path: Path) -> Iterable[dict]:
    if not path.is_file():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def stall_report(domain: str | None = None, log_dir: str | Path | None = None) -> dict:
    """Read routing.jsonl, return per-domain fallback stats.

    `domain=None` returns all domains keyed by name. Each value has:
      { total, default_count, default_rate,
        top_keywords: [(name, count), ...],
        top_fallthrough_task_hashes: [hash, ...] }
    """
    from collections import Counter
    root = Path(log_dir) if log_dir else _log_dir()
    path = root / _ROUTING_LOG
    by_domain: dict[str, list[dict]] = {}
    for ev in _iter_events(path):
        if domain and ev.get("domain") != domain:
            continue
        by_domain.setdefault(ev.get("domain", ""), []).append(ev)
    out: dict[str, dict] = {}
    for dom, evs in by_domain.items():
        total = len(evs)
        defaults = sum(1 for ev in evs if ev.get("winner") == ev.get("default"))
        winners = Counter(ev["winner"] for ev in evs if ev.get("winner") != ev.get("default"))
        fallthroughs = [ev["task_hash"] for ev in evs if ev.get("winner") == ev.get("default")]
        out[dom] = {
            "total": total,
            "default_count": defaults,
            "default_rate": defaults / total if total else 0.0,
            "top_keywords": winners.most_common(10),
            "top_fallthrough_task_hashes": fallthroughs[-20:],
        }
    return out


def force_miss_report(log_dir: str | Path | None = None) -> dict:
    """Aggregate force_miss.jsonl: counts per (forced, actual) pair."""
    from collections import Counter
    root = Path(log_dir) if log_dir else _log_dir()
    path = root / _FORCE_MISS_LOG
    pairs = Counter(
        (ev.get("forced", ""), ev.get("actual", ""))
        for ev in _iter_events(path)
    )
    total = sum(pairs.values())
    return {
        "total": total,
        "top_pairs": pairs.most_common(10),
    }


__all__ = [
    "enable", "disable",
    "log_pick", "log_force_miss",
    "stall_report", "force_miss_report",
]
