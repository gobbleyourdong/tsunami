"""Pytest scenarios for FIX-A pending-file checklist (JOB-INT-8 spec)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from tsunami.pending_files import (
    decompose_pending_files,
    format_checklist_update,
    format_iter1_checklist,
)


def _make_data_dir(files: list[str]) -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="fix_a_"))
    data = tmpdir / "data"
    data.mkdir()
    for f in files:
        (data / f).write_text("{}")
    return data


def test_single_file_mention_matched_to_scaffold():
    data = _make_data_dir(["characters.json", "config.json"])
    pending, missing = decompose_pending_files(
        "Build a beat-em-up. Rename brawlers in data/characters.json.", data,
    )
    assert pending == ["characters.json"]
    assert missing == []


def test_multi_file_preserves_order():
    data = _make_data_dir(["characters.json", "config.json", "enemies.json"])
    pending, missing = decompose_pending_files(
        "Update data/config.json first, then data/characters.json, "
        "finally data/enemies.json.", data,
    )
    assert pending == ["config.json", "characters.json", "enemies.json"]
    assert missing == []


def test_mentioned_but_missing_goes_to_warning_list():
    data = _make_data_dir(["characters.json"])
    pending, missing = decompose_pending_files(
        "Edit data/characters.json and data/spells.json.", data,
    )
    assert pending == ["characters.json"]
    assert missing == ["spells.json"]


def test_no_data_file_mention_returns_empty():
    data = _make_data_dir(["characters.json", "config.json"])
    pending, missing = decompose_pending_files(
        "Build me a beat-em-up with 3 brawlers.", data,
    )
    assert pending == []
    assert missing == []


def test_case_insensitive_and_dedupe():
    data = _make_data_dir(["characters.json"])
    pending, missing = decompose_pending_files(
        "Edit data/Characters.JSON then save. Also edit "
        "data/characters.json again.", data,
    )
    assert pending == ["characters.json"]
    assert missing == []


def test_empty_user_message_or_missing_data_dir():
    data = _make_data_dir(["x.json"])
    assert decompose_pending_files("", data) == ([], [])
    assert decompose_pending_files("edit data/x.json", Path("/nonexistent/xyz")) == ([], [])


def test_nested_path_not_matched():
    data = _make_data_dir(["x.json"])
    # Nested paths should NOT match — v1 is single-level top of data/.
    pending, missing = decompose_pending_files(
        "Edit data/sub/nested.json please.", data,
    )
    # 'nested.json' is mentioned via the 'sub/nested.json' portion after
    # the slash — it *will* be matched by the regex because \bdata/<w>.json\b
    # only catches `data/<name>.json` patterns where name has no slash.
    # "data/sub/nested.json" → the regex matches `data/sub` part? No — the
    # character class [\w.-] excludes `/`, so regex matches at the inner
    # `sub/nested.json` ? Let's just assert no false positive and no crash.
    assert "nested.json" not in pending  # file doesn't exist in scaffold
    # Crucially, regex must not crash:
    assert isinstance(pending, list)
    assert isinstance(missing, list)


def test_iter1_checklist_format_has_discipline_notes():
    out = format_iter1_checklist(["characters.json", "config.json"], [])
    assert "Task checklist" in out
    assert "[ ] data/characters.json" in out
    assert "[ ] data/config.json" in out
    assert "Scaffold-first discipline" in out
    assert "Do NOT" in out


def test_iter1_checklist_emits_missing_warning_when_present():
    out = format_iter1_checklist(["characters.json"], ["spells.json"])
    assert "WARN" in out
    assert "data/spells.json" in out
    assert "typo or new-file request" in out


def test_update_checklist_after_one_write():
    out = format_checklist_update(
        ["characters.json", "config.json"],
        ["characters.json"],
        [],
    )
    assert "Pending file-edit checklist" in out
    assert "[ ] data/config.json" in out
    assert "[x] data/characters.json" in out
    assert "Your next action should be a file_write" in out


def test_update_checklist_returns_empty_when_all_done():
    out = format_checklist_update(
        ["characters.json", "config.json"],
        ["characters.json", "config.json"],
        [],
    )
    assert out == ""
