"""Canary — scaffolds/cli/config-generator.

- Directory + required files exist
- `python -m config_generator --help` exits 0
- Bundled `app.yaml.j2` renders from the sample params file and the
  output parses as YAML with expected values
- `--set` overrides win over file params, with dotted keys descending
- Env-prefix loader picks up `CFG_*` vars
- Missing params fail loudly via StrictUndefined
- Invalid rendered output (forced bad template) fails the validation gate

Run with::

    pytest tests/scaffolds/config-generator/
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "cli" / "config-generator"
SRC = SCAFFOLD / "src"
PARAMS = SCAFFOLD / "data" / "sample_params.yaml"


def _run(args: list[str], env_extra: dict | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "config_generator", *args],
        capture_output=True, env=env, cwd=str(REPO_ROOT), timeout=30,
    )


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "pyproject.toml",
        "README.md",
        "src/config_generator/__init__.py",
        "src/config_generator/__main__.py",
        "src/config_generator/cli.py",
        "src/config_generator/params.py",
        "src/config_generator/render.py",
        "src/config_generator/templates/app.yaml.j2",
        "src/config_generator/templates/dotenv.env.j2",
        "data/sample_params.yaml",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_help_exits_zero() -> None:
    pytest.importorskip("click")
    proc = _run(["--help"])
    assert proc.returncode == 0, proc.stderr
    assert b"TEMPLATE" in proc.stdout


def test_render_bundled_yaml() -> None:
    pytest.importorskip("click")
    proc = _run(["app.yaml.j2", "--params", str(PARAMS), "--format", "yaml"])
    assert proc.returncode == 0, proc.stderr
    data = yaml.safe_load(proc.stdout.decode())
    assert data["app"]["name"] == "orbit"
    assert data["app"]["env"] == "production"
    assert data["server"]["port"] == 8080
    assert data["database"]["url"].startswith("postgres://")


def test_set_overrides_win() -> None:
    pytest.importorskip("click")
    proc = _run([
        "app.yaml.j2",
        "--params", str(PARAMS),
        "--format", "yaml",
        "--set", "app.env=staging",
        "--set", "server.port=9090",
    ])
    assert proc.returncode == 0, proc.stderr
    data = yaml.safe_load(proc.stdout.decode())
    assert data["app"]["env"] == "staging"
    assert data["server"]["port"] == 9090


def test_env_prefix_loader() -> None:
    pytest.importorskip("click")
    with tempfile.TemporaryDirectory() as td:
        tpl = Path(td) / "greet.txt.j2"
        tpl.write_text("hello {{ name }} from {{ city }}\n")
        proc = _run(
            [str(tpl), "--env-prefix", "CFG_", "--format", "text"],
            env_extra={"CFG_NAME": "alice", "CFG_CITY": "seattle"},
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode().strip() == "hello alice from seattle"


def test_missing_param_fails_loudly() -> None:
    pytest.importorskip("click")
    with tempfile.TemporaryDirectory() as td:
        tpl = Path(td) / "broken.txt.j2"
        tpl.write_text("value = {{ not_provided }}\n")
        proc = _run([str(tpl), "--format", "text"])
        assert proc.returncode != 0
        combined = (proc.stderr + proc.stdout).lower()
        assert b"not_provided" in combined or b"undefined" in combined


def test_validation_catches_bad_output() -> None:
    pytest.importorskip("click")
    with tempfile.TemporaryDirectory() as td:
        tpl = Path(td) / "bad.json.j2"
        tpl.write_text('{"incomplete": {{ value }}')
        proc = _run([str(tpl), "--format", "json", "--set", "value=42"])
        assert proc.returncode != 0
        assert b"validation" in proc.stderr.lower() or b"json" in proc.stderr.lower()


def test_dotenv_feature_flags() -> None:
    pytest.importorskip("click")
    proc = _run([
        "dotenv.env.j2",
        "--params", str(PARAMS),
        "--format", "env",
    ])
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout.decode()
    lines = {l.split("=", 1)[0]: l.split("=", 1)[1] for l in out.splitlines()
             if l and not l.startswith("#") and "=" in l}
    assert lines["APP_NAME"] == "orbit"
    assert lines["APP_ENV"] == "production"
    assert lines["FEATURE_DARK_MODE"] == "true"
    assert lines["FEATURE_BETA_API"] == "false"
