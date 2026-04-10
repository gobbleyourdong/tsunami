"""Tests for file history tracking and rollback."""

import os
import tempfile
import pytest

from tsunami.file_history import FileHistory, MAX_SNAPSHOTS


class TestFileHistoryBasic:
    """Track edits and verify backups exist."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fh = FileHistory(self.tmpdir)

    def _write_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_track_existing_file(self):
        path = self._write_file("test.py", "original content")
        self.fh.begin_snapshot(1, "file_edit")
        backup = self.fh.track_before_edit(path)
        assert backup is not None
        assert backup.existed_before is True
        assert os.path.exists(backup.backup_path)

    def test_track_new_file(self):
        path = os.path.join(self.tmpdir, "new.py")
        self.fh.begin_snapshot(1, "file_write")
        backup = self.fh.track_before_edit(path)
        assert backup is not None
        assert backup.existed_before is False

    def test_backup_contains_original(self):
        path = self._write_file("test.py", "hello world")
        self.fh.begin_snapshot(1, "file_edit")
        backup = self.fh.track_before_edit(path)
        assert open(backup.backup_path).read() == "hello world"

    def test_commit_snapshot(self):
        path = self._write_file("test.py", "original")
        self.fh.begin_snapshot(1, "file_edit")
        self.fh.track_before_edit(path)
        self.fh.commit_snapshot()
        assert self.fh.snapshot_count == 1

    def test_no_commit_without_files(self):
        self.fh.begin_snapshot(1, "file_edit")
        self.fh.commit_snapshot()
        assert self.fh.snapshot_count == 0  # nothing tracked


class TestFileHistoryRollback:
    """Rollback to previous states."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fh = FileHistory(self.tmpdir)

    def _write_file(self, name: str, content: str) -> str:
        path = os.path.join(self.tmpdir, name)
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_rollback_last_restores_content(self):
        path = self._write_file("test.py", "original")
        # Track and then modify
        self.fh.begin_snapshot(1, "file_edit")
        self.fh.track_before_edit(path)
        self.fh.commit_snapshot()
        # Simulate edit
        with open(path, "w") as f:
            f.write("modified")
        assert open(path).read() == "modified"
        # Rollback
        restored = self.fh.rollback_last()
        assert path in restored
        assert open(path).read() == "original"

    def test_rollback_removes_new_file(self):
        new_path = os.path.join(self.tmpdir, "created.py")
        # Track before creation
        self.fh.begin_snapshot(1, "file_write")
        self.fh.track_before_edit(new_path)
        self.fh.commit_snapshot()
        # Create the file
        with open(new_path, "w") as f:
            f.write("new content")
        assert os.path.exists(new_path)
        # Rollback should remove it
        restored = self.fh.rollback_last()
        assert new_path in restored
        assert not os.path.exists(new_path)

    def test_rollback_to_iteration(self):
        path = self._write_file("test.py", "v1")

        # Iteration 1: v1 → v2
        self.fh.begin_snapshot(1, "file_edit")
        self.fh.track_before_edit(path)
        self.fh.commit_snapshot()
        with open(path, "w") as f:
            f.write("v2")

        # Iteration 2: v2 → v3
        self.fh.begin_snapshot(2, "file_edit")
        self.fh.track_before_edit(path)
        self.fh.commit_snapshot()
        with open(path, "w") as f:
            f.write("v3")

        assert open(path).read() == "v3"

        # Rollback to iteration 1 (should restore v2, which was saved at iter 2)
        self.fh.rollback_to(1)
        assert open(path).read() == "v2"

    def test_rollback_empty_history(self):
        restored = self.fh.rollback_last()
        assert restored == []

    def test_multiple_files_in_one_snapshot(self):
        p1 = self._write_file("a.py", "a_original")
        p2 = self._write_file("b.py", "b_original")

        self.fh.begin_snapshot(1, "batch_edit")
        self.fh.track_before_edit(p1)
        self.fh.track_before_edit(p2)
        self.fh.commit_snapshot()

        with open(p1, "w") as f:
            f.write("a_modified")
        with open(p2, "w") as f:
            f.write("b_modified")

        restored = self.fh.rollback_last()
        assert len(restored) == 2
        assert open(p1).read() == "a_original"
        assert open(p2).read() == "b_original"


class TestFileHistoryBounds:
    """Circular buffer and size limits."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.fh = FileHistory(self.tmpdir)

    def test_max_snapshots(self):
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("content")

        for i in range(MAX_SNAPSHOTS + 20):
            self.fh.begin_snapshot(i, "file_edit")
            self.fh.track_before_edit(path)
            self.fh.commit_snapshot()

        assert self.fh.snapshot_count <= MAX_SNAPSHOTS


class TestFileHistoryPersistence:
    """Save/load index for session resume."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_save_and_load(self):
        fh = FileHistory(self.tmpdir)
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("hello")

        fh.begin_snapshot(1, "file_edit")
        fh.track_before_edit(path)
        fh.commit_snapshot()
        fh.save_index()

        # Load in a new instance
        fh2 = FileHistory.load_index(self.tmpdir)
        assert fh2.snapshot_count == 1
        assert fh2.snapshots[0].iteration == 1

    def test_load_nonexistent(self):
        fh = FileHistory.load_index("/tmp/nonexistent_dir_12345")
        assert fh.snapshot_count == 0

    def test_get_history(self):
        fh = FileHistory(self.tmpdir)
        path = os.path.join(self.tmpdir, "test.py")
        with open(path, "w") as f:
            f.write("hello")

        fh.begin_snapshot(1, "file_edit", {"path": "test.py"})
        fh.track_before_edit(path)
        fh.commit_snapshot()

        history = fh.get_history()
        assert len(history) == 1
        assert history[0]["iteration"] == 1
        assert history[0]["tool"] == "file_edit"
        assert history[0]["files"] == 1
