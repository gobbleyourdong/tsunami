"""Tests for structured diff parsing."""

import pytest

from tsunami.diff_display import (
    parse_unified_diff,
    format_inline_edit,
    DiffResult,
    FileDiff,
    DiffHunk,
    MAX_LINES_PER_FILE,
)


SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
index abc1234..def5678 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,5 +1,6 @@
 import os
 import sys
+import json

 def main():
-    print("hello")
+    print("hello world")
"""

MULTI_FILE_DIFF = """\
diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,3 +1,4 @@
 line1
+added line
 line2
 line3
diff --git a/file2.py b/file2.py
new file mode 100644
--- /dev/null
+++ b/file2.py
@@ -0,0 +1,3 @@
+new file
+content
+here
"""


class TestParseUnifiedDiff:
    """Parse git diff output into structured data."""

    def test_single_file(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        assert result.files_changed == 1
        assert result.files[0].path == "src/main.py"

    def test_additions_and_deletions(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        f = result.files[0]
        assert f.additions == 2  # +import json, +print("hello world")
        assert f.deletions == 1  # -print("hello")

    def test_total_stats(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        assert result.total_additions == 2
        assert result.total_deletions == 1

    def test_hunk_parsed(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        assert len(result.files[0].hunks) == 1
        hunk = result.files[0].hunks[0]
        assert hunk.old_start == 1
        assert hunk.old_count == 5
        assert hunk.new_start == 1
        assert hunk.new_count == 6

    def test_multi_file(self):
        result = parse_unified_diff(MULTI_FILE_DIFF)
        assert result.files_changed == 2
        assert result.files[0].path == "file1.py"
        assert result.files[1].path == "file2.py"

    def test_new_file_flag(self):
        result = parse_unified_diff(MULTI_FILE_DIFF)
        assert result.files[1].is_new is True
        assert result.files[0].is_new is False

    def test_deleted_file(self):
        diff = """\
diff --git a/old.py b/old.py
deleted file mode 100644
--- a/old.py
+++ /dev/null
@@ -1,3 +0,0 @@
-line1
-line2
-line3
"""
        result = parse_unified_diff(diff)
        assert result.files[0].is_deleted is True
        assert result.files[0].deletions == 3

    def test_binary_file(self):
        diff = """\
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
        result = parse_unified_diff(diff)
        assert result.files[0].is_binary is True

    def test_empty_diff(self):
        result = parse_unified_diff("")
        assert result.files_changed == 0

    def test_rename(self):
        diff = """\
diff --git a/old_name.py b/new_name.py
rename from old_name.py
rename to new_name.py
"""
        result = parse_unified_diff(diff)
        assert result.files[0].old_path == "old_name.py"
        assert result.files[0].path == "new_name.py"


class TestDiffResultFormatting:
    """Display formatting."""

    def test_format_stats(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        stats = result.format_stats()
        assert "1 file changed" in stats
        assert "2 insertions" in stats
        assert "1 deletion" in stats

    def test_format_stats_plural(self):
        result = parse_unified_diff(MULTI_FILE_DIFF)
        stats = result.format_stats()
        assert "2 files changed" in stats

    def test_format_full(self):
        result = parse_unified_diff(SAMPLE_DIFF)
        full = result.format_full()
        assert "src/main.py" in full
        assert "+import json" in full
        assert "-    print(\"hello\")" in full

    def test_format_full_respects_max_lines(self):
        # Create a diff with many lines
        lines = "\n".join(f"+line {i}" for i in range(500))
        diff = f"""\
diff --git a/big.py b/big.py
--- a/big.py
+++ b/big.py
@@ -0,0 +1,500 @@
{lines}
"""
        result = parse_unified_diff(diff)
        full = result.format_full(max_lines=10)
        assert "more lines" in full


class TestFormatInlineEdit:
    """Inline edit diff display."""

    def test_simple_edit(self):
        old = "hello world"
        new = "hello universe"
        result = format_inline_edit("test.py", old, new)
        assert "-hello world" in result
        assert "+hello universe" in result

    def test_no_change(self):
        result = format_inline_edit("test.py", "same", "same")
        assert "No visible changes" in result

    def test_file_path_in_header(self):
        result = format_inline_edit("src/main.py", "old", "new")
        assert "src/main.py" in result
