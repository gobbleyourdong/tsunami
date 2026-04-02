"""Tests for match tools default ignore behavior."""

import asyncio
from pathlib import Path

from tsunami.tools.match import MatchGlob, MatchGrep, _expand_brace_patterns


class FakeConfig:
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_match_glob_skips_runtime_trees_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    write_text(tmp_path / "src" / "keep.txt", "keep")
    write_text(tmp_path / ".venv" / "hidden.txt", "venv")
    write_text(tmp_path / "llama.cpp" / "hidden.txt", "llama")
    write_text(tmp_path / "cli" / "node_modules" / "hidden.txt", "node")
    write_text(workspace / ".history" / "session.txt", "history")

    result = run(tool.execute(pattern="**/*.txt", directory=str(tmp_path)))

    assert not result.is_error
    assert "src/keep.txt" in result.content
    assert ".venv/hidden.txt" not in result.content
    assert "llama.cpp/hidden.txt" not in result.content
    assert "cli/node_modules/hidden.txt" not in result.content
    assert "workspace/.history/session.txt" not in result.content


def test_match_glob_allows_explicit_search_inside_ignored_tree(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    target = tmp_path / ".venv" / "hidden.txt"
    write_text(target, "venv")

    result = run(tool.execute(pattern="**/*.txt", directory=str(tmp_path / ".venv")))

    assert not result.is_error
    assert "hidden.txt" in result.content


def test_match_glob_skips_nested_node_modules_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    write_text(tmp_path / "project" / "src" / "App.tsx", "export default function App() {}")
    write_text(tmp_path / "project" / "node_modules" / "pkg" / "index.tsx", "export const noisy = true")

    result = run(tool.execute(pattern="**/*.tsx", directory=str(tmp_path / "project")))

    assert not result.is_error
    assert "src/App.tsx" in result.content
    assert "node_modules/pkg/index.tsx" not in result.content


def test_match_glob_allows_explicit_node_modules_pattern(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    write_text(tmp_path / "project" / "node_modules" / "pkg" / "index.tsx", "export const noisy = true")

    result = run(
        tool.execute(
            pattern="node_modules/**/*.tsx",
            directory=str(tmp_path / "project"),
        )
    )

    assert not result.is_error
    assert "node_modules/pkg/index.tsx" in result.content


def test_match_grep_skips_runtime_trees_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGrep(config)

    write_text(tmp_path / "src" / "keep.txt", "needle in src")
    write_text(tmp_path / ".venv" / "hidden.txt", "needle in venv")
    write_text(tmp_path / "llama.cpp" / "hidden.txt", "needle in llama")
    write_text(tmp_path / "cli" / "node_modules" / "hidden.txt", "needle in node")

    result = run(tool.execute(pattern="needle", directory=str(tmp_path), file_pattern="*.txt"))

    assert not result.is_error
    assert "src/keep.txt" in result.content
    assert ".venv/hidden.txt" not in result.content
    assert "llama.cpp/hidden.txt" not in result.content
    assert "cli/node_modules/hidden.txt" not in result.content


def test_match_grep_allows_explicit_search_inside_ignored_tree(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGrep(config)

    write_text(tmp_path / "cli" / "node_modules" / "hidden.txt", "needle in node")

    result = run(
        tool.execute(
            pattern="needle",
            directory=str(tmp_path / "cli" / "node_modules"),
            file_pattern="*.txt",
        )
    )

    assert not result.is_error
    assert "hidden.txt" in result.content


def test_match_grep_skips_nested_node_modules_by_default(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGrep(config)

    write_text(tmp_path / "project" / "src" / "App.tsx", "needle in app")
    write_text(tmp_path / "project" / "node_modules" / "pkg" / "index.tsx", "needle in package")

    result = run(
        tool.execute(
            pattern="needle",
            directory=str(tmp_path / "project"),
            file_pattern="**/*.tsx",
        )
    )

    assert not result.is_error
    assert "src/App.tsx" in result.content
    assert "node_modules/pkg/index.tsx" not in result.content


def test_match_glob_resolves_relative_directory_from_repo_root(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    write_text(tmp_path / "src" / "App.tsx", "export default function App() {}")

    result = run(tool.execute(pattern="*.tsx", directory="src"))

    assert not result.is_error
    assert "App.tsx" in result.content


def test_expand_brace_patterns():
    assert _expand_brace_patterns("**/*.{ts,tsx,css}") == [
        "**/*.ts",
        "**/*.tsx",
        "**/*.css",
    ]


def test_match_glob_supports_brace_patterns(tmp_path):
    workspace = tmp_path / "workspace"
    config = FakeConfig(str(workspace))
    tool = MatchGlob(config)

    write_text(tmp_path / "project" / "src" / "App.tsx", "tsx")
    write_text(tmp_path / "project" / "src" / "main.ts", "ts")
    write_text(tmp_path / "project" / "src" / "index.css", "css")

    result = run(
        tool.execute(
            pattern="**/*.{ts,tsx,css}",
            directory=str(tmp_path / "project"),
        )
    )

    assert not result.is_error
    assert "src/App.tsx" in result.content
    assert "src/main.ts" in result.content
    assert "src/index.css" in result.content
