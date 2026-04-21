"""Canary — scaffolds/cli/data-processor.

Verifies the scaffold ships runnable:

- Directory + required files exist
- `python -m data_processor --help` exits 0
- Sample JSONL pipes through `process --filter` and emits a subset
- `count --group-by` returns one record per distinct group

Run with::

    pytest tests/scaffolds/data-processor/

The canary invokes the scaffold as an isolated subprocess with
PYTHONPATH pointed at ``scaffolds/cli/data-processor/src`` — no
install step, no dependency on the surrounding venv beyond Python
+ ``click`` (already a tsunami dep).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "cli" / "data-processor"
SRC = SCAFFOLD / "src"
SAMPLE = SCAFFOLD / "data" / "sample.jsonl"


def _run(args: list[str], stdin: bytes | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "data_processor", *args],
        input=stdin,
        capture_output=True,
        env=env,
        cwd=str(REPO_ROOT),
        timeout=30,
    )


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir(), f"missing scaffold: {SCAFFOLD}"
    for rel in (
        "pyproject.toml",
        "README.md",
        "src/data_processor/__init__.py",
        "src/data_processor/__main__.py",
        "src/data_processor/cli.py",
        "src/data_processor/io.py",
        "src/data_processor/operators.py",
        "data/sample.jsonl",
        "data/schema.json",
    ):
        assert (SCAFFOLD / rel).exists(), f"missing: {rel}"


def test_sample_fixture_parses() -> None:
    records = [json.loads(line) for line in SAMPLE.read_text().splitlines() if line.strip()]
    assert len(records) == 5
    for r in records:
        assert {"id", "user", "status"}.issubset(r.keys())


def test_help_exits_zero() -> None:
    pytest.importorskip("click")
    proc = _run(["--help"])
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert b"data-processor" in proc.stdout


def test_process_filter_and_project() -> None:
    pytest.importorskip("click")
    proc = _run(
        ["process", "-i", str(SAMPLE),
         "--filter", "status==active",
         "--select", "id,user.name"],
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    lines = [l for l in proc.stdout.decode().splitlines() if l.strip()]
    records = [json.loads(l) for l in lines]
    assert len(records) == 3, records
    for r in records:
        assert set(r.keys()) == {"id", "user.name"}
        assert isinstance(r["id"], int)
        assert isinstance(r["user.name"], str)
    ids = sorted(r["id"] for r in records)
    assert ids == [1, 3, 4]


def test_process_stdin_roundtrip() -> None:
    pytest.importorskip("click")
    payload = b'{"id": 99, "status": "active", "score": 0.7}\n'
    proc = _run(
        ["process", "--filter", "score>=0.5", "--select", "id"],
        stdin=payload,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    out = proc.stdout.decode().strip()
    assert out == '{"id":99}'


def test_count_group_by() -> None:
    pytest.importorskip("click")
    proc = _run(["count", "-i", str(SAMPLE), "--group-by", "user.city"])
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    rows = [json.loads(l) for l in proc.stdout.decode().splitlines() if l.strip()]
    buckets = {r["user.city"]: r["count"] for r in rows}
    assert buckets == {"seattle": 2, "nyc": 2, "sf": 1}, buckets
