"""Tests for shell path normalization."""

from tsunami.tools.shell import _normalize_workspace_paths


def test_normalize_workspace_absolute_path():
    cmd = "cd /workspace/deliverables/demo && ls -la /workspace/deliverables/demo"
    normalized = _normalize_workspace_paths(cmd)
    assert normalized == "cd ./workspace/deliverables/demo && ls -la ./workspace/deliverables/demo"


def test_normalize_skills_absolute_path():
    cmd = "ls /skills && cat /skills/example.md"
    normalized = _normalize_workspace_paths(cmd)
    assert normalized == "ls ./skills && cat ./skills/example.md"


def test_keep_existing_relative_paths_unchanged():
    cmd = "cd ./workspace/deliverables/demo && ls -la ./workspace/deliverables/demo"
    normalized = _normalize_workspace_paths(cmd)
    assert normalized == cmd
