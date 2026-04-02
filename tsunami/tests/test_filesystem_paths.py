"""Tests for file path normalization in filesystem tools."""

from pathlib import Path

from tsunami.tools.filesystem import _resolve_path


def test_resolve_path_normalizes_fake_workspace_absolute_path(tmp_path):
    workspace = tmp_path / "workspace"
    project_file = workspace / "deliverables" / "demo" / "tsunami.md"
    project_file.parent.mkdir(parents=True)
    project_file.write_text("# demo\n")

    resolved = _resolve_path("/workspace/deliverables/demo/tsunami.md", str(workspace))

    assert resolved == project_file.resolve()


def test_resolve_path_normalizes_fake_skills_absolute_path(tmp_path):
    workspace = tmp_path / "workspace"
    skill_file = tmp_path / "skills" / "example.md"
    skill_file.parent.mkdir(parents=True)
    skill_file.write_text("hi\n")

    resolved = _resolve_path("/skills/example.md", str(workspace))

    assert resolved == skill_file.resolve()
