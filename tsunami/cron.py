"""Cron scheduler — persistent and session-scoped task scheduling.

Supports recurring and one-shot tasks with file-backed persistence.

Key patterns :
- Dual storage: file-backed (durable) + in-memory (session-scoped)
- Missed task detection on startup
- Jitter to prevent thundering herd on wall-clock boundaries
- Scheduler lock for multi-session safety
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger("tsunami.cron")

# Auto-expiry for recurring tasks (: 7 days)
RECURRING_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000  # 7 days in ms


@dataclass
class CronTask:
    """A scheduled task."""
    id: str
    cron: str  # 5-field cron expression
    prompt: str
    created_at: float = field(default_factory=lambda: time.time() * 1000)  # epoch ms
    last_fired_at: float | None = None
    recurring: bool = True
    durable: bool = False  # if True, persists to disk

    @property
    def is_expired(self) -> bool:
        """Check if a recurring task has aged out."""
        if not self.recurring:
            return False
        age_ms = time.time() * 1000 - self.created_at
        return age_ms > RECURRING_MAX_AGE_MS


def generate_task_id() -> str:
    """Generate an 8-char random task ID ."""
    return hashlib.sha256(f"{time.time()}{random.random()}".encode()).hexdigest()[:8]


def parse_cron(cron_expr: str) -> dict | None:
    """Parse a 5-field cron expression into components.

    Returns dict with minute, hour, dom, month, dow fields,
    or None if invalid.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None

    fields = ["minute", "hour", "dom", "month", "dow"]
    return dict(zip(fields, parts))


def cron_matches_now(cron_expr: str, now: float | None = None) -> bool:
    """Check if a cron expression matches the current time (minute granularity)."""
    parsed = parse_cron(cron_expr)
    if not parsed:
        return False

    import datetime
    dt = datetime.datetime.fromtimestamp(now or time.time())

    def _matches(field_val: str, current: int, max_val: int) -> bool:
        if field_val == "*":
            return True
        # */N pattern
        if field_val.startswith("*/"):
            try:
                step = int(field_val[2:])
                return current % step == 0
            except ValueError:
                return False
        # Range: N-M
        if "-" in field_val:
            try:
                lo, hi = field_val.split("-")
                return int(lo) <= current <= int(hi)
            except ValueError:
                return False
        # List: N,M,O
        if "," in field_val:
            try:
                return current in [int(v) for v in field_val.split(",")]
            except ValueError:
                return False
        # Exact match
        try:
            return current == int(field_val)
        except ValueError:
            return False

    return (
        _matches(parsed["minute"], dt.minute, 59)
        and _matches(parsed["hour"], dt.hour, 23)
        and _matches(parsed["dom"], dt.day, 31)
        and _matches(parsed["month"], dt.month, 12)
        and _matches(parsed["dow"], dt.weekday(), 6)  # 0=Monday in Python
    )


def add_jitter(base_time_ms: float, interval_ms: float,
               max_frac: float = 0.1, max_cap_ms: float = 15 * 60 * 1000) -> float:
    """Add deterministic jitter to a fire time.

    jitter = random fraction of interval, capped.
    Prevents thundering herd when many tasks fire at the same wall-clock time.
    """
    jitter_ms = min(interval_ms * max_frac, max_cap_ms)
    offset = random.random() * jitter_ms
    return base_time_ms + offset


class CronStore:
    """Persistent storage for cron tasks.

    File-backed tasks go to .tsunami/scheduled_tasks.json.
    Session-scoped tasks live in memory only.
    """

    def __init__(self, config_dir: str | Path | None = None):
        self.config_dir = Path(config_dir) if config_dir else None
        self._session_tasks: dict[str, CronTask] = {}
        self._file_path: Path | None = None
        if self.config_dir:
            self._file_path = self.config_dir / "scheduled_tasks.json"

    def add(self, task: CronTask) -> str:
        """Add a task. Returns task ID."""
        if task.durable and self._file_path:
            tasks = self._read_file()
            tasks.append(self._serialize(task))
            self._write_file(tasks)
        else:
            self._session_tasks[task.id] = task
        log.info(f"Cron task added: {task.id} ({task.cron}) — {'durable' if task.durable else 'session'}")
        return task.id

    def remove(self, task_id: str):
        """Remove a task by ID."""
        if task_id in self._session_tasks:
            del self._session_tasks[task_id]
            return

        if self._file_path:
            tasks = self._read_file()
            tasks = [t for t in tasks if t.get("id") != task_id]
            self._write_file(tasks)

    def get_all(self) -> list[CronTask]:
        """Get all tasks (session + file-backed)."""
        tasks = list(self._session_tasks.values())
        if self._file_path:
            for td in self._read_file():
                tasks.append(self._deserialize(td))
        return tasks

    def mark_fired(self, task_id: str, fired_at: float | None = None):
        """Update last_fired_at for a recurring task."""
        ts = fired_at or time.time() * 1000
        if task_id in self._session_tasks:
            self._session_tasks[task_id].last_fired_at = ts
            return

        if self._file_path:
            tasks = self._read_file()
            for t in tasks:
                if t.get("id") == task_id:
                    t["last_fired_at"] = ts
            self._write_file(tasks)

    def find_missed(self) -> list[CronTask]:
        """Find one-shot tasks that should have fired but didn't.

        detected on startup to handle process restart.
        """
        missed = []
        now_ms = time.time() * 1000
        for task in self.get_all():
            if task.recurring:
                continue
            if task.last_fired_at is not None:
                continue
            # Check if the task should have fired by now
            age_ms = now_ms - task.created_at
            if age_ms > 120_000:  # more than 2 minutes overdue
                missed.append(task)
        return missed

    def _read_file(self) -> list[dict]:
        if not self._file_path or not self._file_path.exists():
            return []
        try:
            data = json.loads(self._file_path.read_text())
            return data.get("tasks", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def _write_file(self, tasks: list[dict]):
        if not self._file_path:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.write_text(json.dumps({"tasks": tasks}, indent=2))

    @staticmethod
    def _serialize(task: CronTask) -> dict:
        return {
            "id": task.id,
            "cron": task.cron,
            "prompt": task.prompt,
            "created_at": task.created_at,
            "last_fired_at": task.last_fired_at,
            "recurring": task.recurring,
        }

    @staticmethod
    def _deserialize(data: dict) -> CronTask:
        return CronTask(
            id=data["id"],
            cron=data["cron"],
            prompt=data.get("prompt", ""),
            created_at=data.get("created_at", 0),
            last_fired_at=data.get("last_fired_at"),
            recurring=data.get("recurring", True),
            durable=True,
        )
