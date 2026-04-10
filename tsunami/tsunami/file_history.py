"""File history tracking — atomic change tracking for rollback.

Tracks file modifications made by the agent during a session.
Each edit creates a backup snapshot, enabling rollback to any
previous state without relying on git history.

Stored as a circular buffer of snapshots (max 100) in workspace/.file_history/.
Each snapshot is tied to a specific agent iteration for traceability.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("tsunami.file_history")

MAX_SNAPSHOTS = 100
BACKUP_DIR_NAME = ".file_history"


@dataclass
class FileBackup:
    """A backup of a single file at a point in time."""
    original_path: str
    backup_path: str  # path to the backup copy
    existed_before: bool  # False if file was newly created
    size_bytes: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class HistorySnapshot:
    """A snapshot of all file changes at a specific iteration."""
    iteration: int
    tool_name: str  # which tool made the change
    tool_args: dict = field(default_factory=dict)
    files: list[FileBackup] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class FileHistory:
    """Tracks file modifications for rollback capability.

    Usage:
    1. Before any file write/edit, call track_before_edit(path)
    2. The original content is saved as a backup
    3. To rollback, call rollback_to(iteration) or rollback_last()
    """

    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.backup_dir = Path(workspace_dir) / BACKUP_DIR_NAME
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots: list[HistorySnapshot] = []
        self._current_snapshot: HistorySnapshot | None = None

    def begin_snapshot(self, iteration: int, tool_name: str, tool_args: dict = {}):
        """Start a new snapshot for the current tool execution."""
        self._current_snapshot = HistorySnapshot(
            iteration=iteration,
            tool_name=tool_name,
            tool_args=tool_args,
        )

    def track_before_edit(self, file_path: str) -> FileBackup | None:
        """Save a backup of a file before it's modified.

        Call this BEFORE any write/edit operation.
        Returns the backup info, or None if backup failed.
        """
        p = Path(file_path)
        existed = p.exists()

        # Generate unique backup filename
        ts = int(time.time() * 1000)
        safe_name = p.name.replace("/", "_").replace("\\", "_")
        backup_name = f"{ts}_{safe_name}"
        backup_path = self.backup_dir / backup_name

        try:
            if existed:
                shutil.copy2(str(p), str(backup_path))
                size = p.stat().st_size
            else:
                # File doesn't exist yet — record that it was new
                backup_path.write_text("")  # empty placeholder
                size = 0

            backup = FileBackup(
                original_path=str(p.resolve()),
                backup_path=str(backup_path),
                existed_before=existed,
                size_bytes=size,
            )

            if self._current_snapshot:
                self._current_snapshot.files.append(backup)

            log.debug(f"Backed up {file_path} → {backup_path}")
            return backup

        except Exception as e:
            log.warning(f"Failed to backup {file_path}: {e}")
            return None

    def commit_snapshot(self):
        """Finalize the current snapshot and add to history."""
        if self._current_snapshot and self._current_snapshot.files:
            self.snapshots.append(self._current_snapshot)
            # Circular buffer
            if len(self.snapshots) > MAX_SNAPSHOTS:
                # Remove oldest and clean up its backup files
                oldest = self.snapshots.pop(0)
                for fb in oldest.files:
                    try:
                        os.unlink(fb.backup_path)
                    except OSError:
                        pass
            log.debug(
                f"Snapshot committed: iteration {self._current_snapshot.iteration}, "
                f"{len(self._current_snapshot.files)} files"
            )
        self._current_snapshot = None

    def rollback_last(self) -> list[str]:
        """Rollback the most recent snapshot.

        Returns list of file paths that were restored.
        """
        if not self.snapshots:
            return []
        return self._rollback_snapshot(self.snapshots.pop())

    def rollback_to(self, iteration: int) -> list[str]:
        """Rollback all changes after a specific iteration.

        Returns list of file paths that were restored.
        """
        restored = []
        while self.snapshots and self.snapshots[-1].iteration > iteration:
            snapshot = self.snapshots.pop()
            restored.extend(self._rollback_snapshot(snapshot))
        return restored

    def _rollback_snapshot(self, snapshot: HistorySnapshot) -> list[str]:
        """Restore files from a snapshot."""
        restored = []
        for fb in reversed(snapshot.files):  # reverse order for safety
            try:
                if fb.existed_before:
                    # Restore from backup
                    shutil.copy2(fb.backup_path, fb.original_path)
                    restored.append(fb.original_path)
                    log.info(f"Restored {fb.original_path} from backup")
                else:
                    # File was created by agent — remove it
                    if os.path.exists(fb.original_path):
                        os.unlink(fb.original_path)
                        restored.append(fb.original_path)
                        log.info(f"Removed {fb.original_path} (was created by agent)")
            except Exception as e:
                log.warning(f"Rollback failed for {fb.original_path}: {e}")

            # Clean up backup file
            try:
                os.unlink(fb.backup_path)
            except OSError:
                pass

        return restored

    def get_history(self) -> list[dict]:
        """Get a summary of all snapshots for display."""
        return [
            {
                "iteration": s.iteration,
                "tool": s.tool_name,
                "files": len(s.files),
                "timestamp": s.timestamp,
                "paths": [fb.original_path for fb in s.files],
            }
            for s in self.snapshots
        ]

    @property
    def snapshot_count(self) -> int:
        return len(self.snapshots)

    def save_index(self):
        """Persist snapshot index to disk for session resume."""
        index_path = self.backup_dir / "index.json"
        data = {
            "snapshots": [
                {
                    "iteration": s.iteration,
                    "tool_name": s.tool_name,
                    "timestamp": s.timestamp,
                    "files": [
                        {
                            "original_path": fb.original_path,
                            "backup_path": fb.backup_path,
                            "existed_before": fb.existed_before,
                            "size_bytes": fb.size_bytes,
                        }
                        for fb in s.files
                    ],
                }
                for s in self.snapshots
            ],
        }
        index_path.write_text(json.dumps(data, indent=2))

    @classmethod
    def load_index(cls, workspace_dir: str) -> FileHistory:
        """Load history from saved index."""
        fh = cls(workspace_dir)
        index_path = fh.backup_dir / "index.json"
        if not index_path.exists():
            return fh
        try:
            data = json.loads(index_path.read_text())
            for sd in data.get("snapshots", []):
                snapshot = HistorySnapshot(
                    iteration=sd["iteration"],
                    tool_name=sd["tool_name"],
                    timestamp=sd.get("timestamp", 0),
                )
                for fd in sd.get("files", []):
                    if os.path.exists(fd["backup_path"]):
                        snapshot.files.append(FileBackup(
                            original_path=fd["original_path"],
                            backup_path=fd["backup_path"],
                            existed_before=fd["existed_before"],
                            size_bytes=fd.get("size_bytes", 0),
                        ))
                if snapshot.files:
                    fh.snapshots.append(snapshot)
        except (json.JSONDecodeError, KeyError) as e:
            log.warning(f"Failed to load file history index: {e}")
        return fh
