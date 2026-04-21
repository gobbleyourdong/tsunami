"""Canary — scaffolds/cli/file-converter.

- Directory + required files exist
- `python -m file_converter --help` exits 0
- csv → jsonl round-trips structurally
- jsonl → yaml round-trips structurally
- Format inference from extension works
- Stdin csv → stdout jsonl with explicit --from/--to

Run with::

    pytest tests/scaffolds/file-converter/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "cli" / "file-converter"
SRC = SCAFFOLD / "src"
CSV = SCAFFOLD / "data" / "sample.csv"
JSONL = SCAFFOLD / "data" / "sample.jsonl"


def _run(args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "file_converter", *args],
        input=stdin, capture_output=True, env=env,
        cwd=str(REPO_ROOT), timeout=30,
    )


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "pyproject.toml",
        "README.md",
        "src/file_converter/__init__.py",
        "src/file_converter/__main__.py",
        "src/file_converter/cli.py",
        "src/file_converter/formats.py",
        "data/sample.csv",
        "data/sample.jsonl",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_help_exits_zero() -> None:
    pytest.importorskip("click")
    proc = _run(["--help"])
    assert proc.returncode == 0, proc.stderr
    assert b"csv" in proc.stdout.lower() and b"jsonl" in proc.stdout.lower()


def test_csv_to_jsonl(tmp_path: Path) -> None:
    pytest.importorskip("click")
    out = tmp_path / "out.jsonl"
    proc = _run(["-i", str(CSV), "-o", str(out)])
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
    assert len(rows) == 5
    assert {r["name"] for r in rows} == {"alice", "bob", "carol", "dan", "eve"}
    assert all({"id", "name", "city", "score"} == set(r.keys()) for r in rows)


def test_jsonl_to_yaml(tmp_path: Path) -> None:
    pytest.importorskip("click")
    out = tmp_path / "out.yaml"
    proc = _run(["-i", str(JSONL), "-o", str(out)])
    assert proc.returncode == 0, proc.stderr
    parsed = yaml.safe_load(out.read_text())
    assert isinstance(parsed, list) and len(parsed) == 3
    assert parsed[0]["name"] == "alice"


def test_csv_to_json_to_stdout() -> None:
    pytest.importorskip("click")
    proc = _run(["-i", str(CSV), "--to", "json", "-o", "-"])
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout.decode())
    assert isinstance(data, list) and len(data) == 5


def test_stdin_explicit_formats() -> None:
    pytest.importorskip("click")
    payload = b"id,name\n1,a\n2,b\n"
    proc = _run(["--from", "csv", "--to", "jsonl"], stdin=payload)
    assert proc.returncode == 0, proc.stderr
    rows = [json.loads(l) for l in proc.stdout.decode().splitlines() if l.strip()]
    assert rows == [{"id": "1", "name": "a"}, {"id": "2", "name": "b"}]


def test_stdin_without_from_errors() -> None:
    pytest.importorskip("click")
    proc = _run(["--to", "jsonl"], stdin=b"id,name\n1,a\n")
    assert proc.returncode != 0
    assert b"--from required" in proc.stderr.lower().replace(b"\xe2\x80\x94", b"-")
