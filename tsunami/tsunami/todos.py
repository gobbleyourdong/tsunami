"""Todo/task tracking — the model manages its own progress checklist.

The agent creates a todo list at the start of complex tasks,
updates items as it progresses, and auto-clears on completion.

This gives the model (and the user) visibility into what's done
and what's pending — especially valuable in long multi-step tasks.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tsunami.todos")


@dataclass
class TodoItem:
    """A single task item."""
    id: str
    title: str
    status: str = "pending"  # pending, in_progress, completed, skipped
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


class TodoList:
    """Session-scoped task list with persistence."""

    def __init__(self, session_id: str = ""):
        self.session_id = session_id
        self.items: list[TodoItem] = []
        self._next_id = 1

    def add(self, title: str) -> TodoItem:
        """Add a new todo item."""
        item = TodoItem(id=f"todo_{self._next_id}", title=title)
        self._next_id += 1
        self.items.append(item)
        log.debug(f"Todo added: {item.id} — {title}")
        return item

    def update(self, item_id: str, status: str) -> TodoItem | None:
        """Update item status."""
        for item in self.items:
            if item.id == item_id:
                item.status = status
                if status == "completed":
                    item.completed_at = time.time()
                log.debug(f"Todo {item_id}: {status}")
                return item
        return None

    def get(self, item_id: str) -> TodoItem | None:
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def set_all(self, todos: list[dict]):
        """Replace all todos (production pattern).

        Accepts a list of {title, status} dicts.
        """
        self.items = []
        self._next_id = 1
        for td in todos:
            item = self.add(td.get("title", ""))
            if td.get("status"):
                item.status = td["status"]
                if item.status == "completed":
                    item.completed_at = time.time()

    @property
    def pending(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == "pending"]

    @property
    def in_progress(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == "in_progress"]

    @property
    def completed(self) -> list[TodoItem]:
        return [i for i in self.items if i.status == "completed"]

    @property
    def all_done(self) -> bool:
        return len(self.items) > 0 and all(
            i.status in ("completed", "skipped") for i in self.items
        )

    @property
    def progress_fraction(self) -> float:
        """Completion fraction (0.0 to 1.0)."""
        if not self.items:
            return 0.0
        done = sum(1 for i in self.items if i.status in ("completed", "skipped"))
        return done / len(self.items)

    def format_summary(self) -> str:
        """Formatted todo list for display."""
        if not self.items:
            return "No tasks."
        lines = []
        for item in self.items:
            marker = {
                "pending": "[ ]",
                "in_progress": "[>]",
                "completed": "[x]",
                "skipped": "[-]",
            }.get(item.status, "[ ]")
            lines.append(f"  {marker} {item.title}")

        done = len(self.completed)
        total = len(self.items)
        pct = int(self.progress_fraction * 100)
        header = f"Tasks: {done}/{total} ({pct}%)"
        return header + "\n" + "\n".join(lines)

    def format_for_context(self) -> str:
        """Compact format for injecting into conversation context.

        Uses the Tsunami pattern of putting task state at the end
        of context (recency bias keeps it salient).
        """
        if not self.items:
            return ""
        return f"[TASK PROGRESS]\n{self.format_summary()}"

    def should_nudge_verification(self) -> bool:
        """Tsunami nudges verification after 3+ completed tasks."""
        return len(self.completed) >= 3 and not self.all_done

    def save(self, workspace_dir: str):
        """Persist to disk."""
        path = Path(workspace_dir) / ".todos" / f"{self.session_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "session_id": self.session_id,
            "items": [
                {
                    "id": i.id,
                    "title": i.title,
                    "status": i.status,
                    "created_at": i.created_at,
                    "completed_at": i.completed_at,
                }
                for i in self.items
            ],
        }
        path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load(cls, workspace_dir: str, session_id: str) -> TodoList | None:
        """Load from disk."""
        path = Path(workspace_dir) / ".todos" / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            tl = cls(session_id=data.get("session_id", session_id))
            for item_data in data.get("items", []):
                item = TodoItem(
                    id=item_data["id"],
                    title=item_data["title"],
                    status=item_data.get("status", "pending"),
                    created_at=item_data.get("created_at", 0),
                    completed_at=item_data.get("completed_at"),
                )
                tl.items.append(item)
            tl._next_id = len(tl.items) + 1
            return tl
        except (json.JSONDecodeError, KeyError):
            return None
