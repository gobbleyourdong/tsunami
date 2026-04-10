"""Tests for gitignore-aware file filtering."""

import os
import tempfile
import pytest

from tsunami.gitignore import (
    parse_gitignore,
    should_exclude,
    filter_paths,
    ripgrep_ignore_args,
    VCS_DIRECTORIES,
    COMMON_EXCLUDES,
)


class TestParseGitignore:
    """Parse .gitignore files into patterns."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def _write_gitignore(self, content: str) -> str:
        path = os.path.join(self.tmpdir, ".gitignore")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_simple_patterns(self):
        path = self._write_gitignore("*.pyc\n__pycache__/\n.env\n")
        patterns = parse_gitignore(path)
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        assert ".env" in patterns

    def test_skips_comments(self):
        path = self._write_gitignore("# This is a comment\n*.pyc\n")
        patterns = parse_gitignore(path)
        assert len(patterns) == 1
        assert "*.pyc" in patterns

    def test_skips_empty_lines(self):
        path = self._write_gitignore("*.pyc\n\n\n*.log\n")
        patterns = parse_gitignore(path)
        assert len(patterns) == 2

    def test_skips_negation(self):
        path = self._write_gitignore("*.log\n!important.log\n")
        patterns = parse_gitignore(path)
        assert "*.log" in patterns
        assert len(patterns) == 1  # negation skipped

    def test_nonexistent_file(self):
        assert parse_gitignore("/nonexistent/.gitignore") == []


class TestShouldExclude:
    """Path exclusion checks."""

    def test_vcs_directories(self):
        assert should_exclude(".git/objects/pack") is True
        assert should_exclude("src/.svn/entries") is True
        assert should_exclude("project/.hg/store") is True

    def test_common_excludes(self):
        assert should_exclude("node_modules/express/index.js") is True
        assert should_exclude("src/__pycache__/module.pyc") is True

    def test_normal_paths_pass(self):
        assert should_exclude("src/main.py") is False
        assert should_exclude("lib/utils.ts") is False

    def test_gitignore_patterns(self):
        patterns = ["*.pyc", "*.log", "dist/"]
        assert should_exclude("module.pyc", patterns) is True
        assert should_exclude("app.log", patterns) is True
        assert should_exclude("dist/bundle.js", patterns) is True
        assert should_exclude("src/main.py", patterns) is False

    def test_directory_pattern(self):
        patterns = ["build/"]
        assert should_exclude("build/output.js", patterns) is True
        assert should_exclude("src/build.py", patterns) is False  # file named build.py

    def test_wildcard_pattern(self):
        patterns = ["*.min.js"]
        assert should_exclude("app.min.js", patterns) is True
        assert should_exclude("app.js", patterns) is False


class TestFilterPaths:
    """Bulk path filtering."""

    def test_filters_vcs(self):
        paths = ["src/main.py", ".git/HEAD", "lib/utils.py", ".svn/entries"]
        filtered = filter_paths(paths)
        assert ".git/HEAD" not in filtered
        assert ".svn/entries" not in filtered
        assert "src/main.py" in filtered

    def test_filters_common(self):
        paths = ["src/main.py", "node_modules/pkg/index.js", "__pycache__/mod.pyc"]
        filtered = filter_paths(paths)
        assert len(filtered) == 1
        assert filtered[0] == "src/main.py"

    def test_empty_input(self):
        assert filter_paths([]) == []


class TestRipgrepIgnoreArgs:
    """Generate ripgrep --glob negation args."""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_includes_vcs_dirs(self):
        args = ripgrep_ignore_args(self.tmpdir)
        # Should have --glob !.git/ at minimum
        assert "--glob" in args
        git_patterns = [args[i + 1] for i, a in enumerate(args) if a == "--glob"]
        assert any(".git" in p for p in git_patterns)

    def test_gitignore_patterns_prefixed(self):
        # Write a .gitignore
        with open(os.path.join(self.tmpdir, ".gitignore"), "w") as f:
            f.write("*.pyc\ndist/\n")
        args = ripgrep_ignore_args(self.tmpdir)
        glob_args = [args[i + 1] for i, a in enumerate(args) if a == "--glob"]
        # Non-absolute patterns should get **/ prefix
        assert any("**/*.pyc" in p for p in glob_args)

    def test_vcs_set_complete(self):
        """All standard VCS directories are covered."""
        assert ".git" in VCS_DIRECTORIES
        assert ".svn" in VCS_DIRECTORIES
        assert ".hg" in VCS_DIRECTORIES
