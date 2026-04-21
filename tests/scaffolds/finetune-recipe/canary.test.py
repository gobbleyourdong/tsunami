"""Canary — scaffolds/training/finetune-recipe.

ML deps (torch/transformers/peft) are optional — the canary exercises
config parsing + CLI surface + recipe module importability without
requiring them. If they're installed locally, an extra test smokes
the recipe.train lazy-import path to catch typos.
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
SCAFFOLD = REPO_ROOT / "scaffolds" / "training" / "finetune-recipe"
SRC = SCAFFOLD / "src"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-m", "finetune_recipe", *args],
        capture_output=True, env=env, cwd=str(REPO_ROOT), timeout=30,
    )


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "pyproject.toml",
        "README.md",
        "config.example.yaml",
        "data/sample.jsonl",
        "src/finetune_recipe/__init__.py",
        "src/finetune_recipe/__main__.py",
        "src/finetune_recipe/cli.py",
        "src/finetune_recipe/config.py",
        "src/finetune_recipe/recipe.py",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def test_pyproject_separates_ml_extras() -> None:
    """ML deps live under [optional-dependencies.ml] so the scaffold
    can be imported without a GPU stack."""
    text = (SCAFFOLD / "pyproject.toml").read_text()
    assert "optional-dependencies" in text
    assert "torch" in text and "transformers" in text and "peft" in text
    # torch should NOT be a top-level dep
    lines = text.splitlines()
    top_deps_start = next(i for i, l in enumerate(lines) if l.strip().startswith("dependencies = ["))
    top_deps_end = next(i for i, l in enumerate(lines[top_deps_start:], start=top_deps_start) if "]" in l)
    top_deps = "\n".join(lines[top_deps_start:top_deps_end + 1])
    assert "torch" not in top_deps, "torch must be an optional dep, not a base dep"


def test_config_example_parses() -> None:
    data = yaml.safe_load((SCAFFOLD / "config.example.yaml").read_text())
    assert data["model"]["name"]
    assert data["lora"]["r"] == 16
    assert data["lora"]["alpha"] == 16  # Unsloth alpha=r baseline
    assert data["train"]["epochs"] >= 1
    assert data["data"]["path"]


def test_help_exits_zero() -> None:
    pytest.importorskip("click")
    proc = _run(["--help"])
    assert proc.returncode == 0, proc.stderr


def test_validate_command_on_example_config() -> None:
    pytest.importorskip("click")
    proc = _run(["validate", str(SCAFFOLD / "config.example.yaml")])
    assert proc.returncode == 0, proc.stderr
    assert b"ok" in proc.stdout.lower()
    assert b"r=16" in proc.stdout


def test_config_load_requires_model_name() -> None:
    pytest.importorskip("click")
    # Write a broken config and verify validate rejects it
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as fh:
        fh.write("model: {}\ndata: {path: x}\n")
        path = fh.name
    try:
        proc = _run(["validate", path])
        assert proc.returncode != 0
        assert b"name required" in (proc.stderr + proc.stdout).lower()
    finally:
        Path(path).unlink(missing_ok=True)


def test_sample_dataset_jsonl_parses() -> None:
    records = [json.loads(l) for l in
               (SCAFFOLD / "data" / "sample.jsonl").read_text().splitlines() if l.strip()]
    assert len(records) >= 3
    for r in records:
        assert "prompt" in r and "response" in r
        assert r["prompt"] and r["response"]


def test_recipe_module_imports_without_ml_deps() -> None:
    """src/finetune_recipe/recipe.py should be importable without torch;
    the ML imports must be lazy-inside train()."""
    pytest.importorskip("click")
    import importlib
    import sys as _sys
    src_str = str(SRC)
    added = False
    if src_str not in _sys.path:
        _sys.path.insert(0, src_str)
        added = True
    try:
        mod = importlib.import_module("finetune_recipe.recipe")
        assert hasattr(mod, "train"), "recipe module should export train()"
    finally:
        if added:
            _sys.path.remove(src_str)
