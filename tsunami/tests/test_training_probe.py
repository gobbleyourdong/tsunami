"""training_probe tests — pass corpus × fail corpus.

Fixture layout:
  tests/fixtures/training/pass/{torch-classic,lightning,hf-trainer}/
  tests/fixtures/training/fail/{empty,no-train-file,no-framework,
                                no-training-loop,no-checkpoint,no-config}/
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.training_probe import training_probe, _find_entry
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIX = _REPO / "tests" / "fixtures" / "training"


def _run(coro):
    return asyncio.run(coro)


# ── Dispatch registration ────────────────────────────────────────────

class TestDispatchRegistration:
    def test_training_in_PROBES(self):
        assert "training" in _PROBES
        assert _PROBES["training"] is training_probe

    @pytest.mark.parametrize("name", ["torch-classic", "lightning", "hf-trainer"])
    def test_detect_pass_fixtures(self, name):
        assert detect_scaffold(_FIX / "pass" / name) == "training"

    def test_detect_no_framework_not_training(self):
        # fail/no-framework has train.py but no ML imports → doesn't
        # fingerprint as training; detector correctly drops through.
        assert detect_scaffold(_FIX / "fail" / "no-framework") != "training"


# ── Entry discovery (unit) ───────────────────────────────────────────

class TestEntryDiscovery:
    def test_torch_classic_train_py(self):
        entry = _find_entry(_FIX / "pass" / "torch-classic")
        assert entry is not None
        assert entry.name == "train.py"

    def test_lightning_train_py(self):
        entry = _find_entry(_FIX / "pass" / "lightning")
        assert entry is not None
        assert entry.name == "train.py"

    def test_hf_trainer_finetune_py(self):
        entry = _find_entry(_FIX / "pass" / "hf-trainer")
        assert entry is not None
        assert entry.name == "finetune.py"

    def test_empty_no_entry(self):
        assert _find_entry(_FIX / "fail" / "empty") is None


# ── Probe pass corpus ────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["torch-classic", "lightning", "hf-trainer"])
def test_pass_fixtures_accepted(name):
    res = _run(training_probe(_FIX / "pass" / name))
    assert res["passed"] is True, (
        f"pass/{name} was rejected: {res['issues']}\n{res['raw']}"
    )


# ── Probe fail corpus ────────────────────────────────────────────────

def test_fail_empty_rejected():
    res = _run(training_probe(_FIX / "fail" / "empty"))
    assert res["passed"] is False
    assert "no entry" in res["issues"].lower()


def test_fail_no_train_file_rejected():
    # README-only, no train.py anywhere
    res = _run(training_probe(_FIX / "fail" / "no-train-file"))
    assert res["passed"] is False
    assert "no entry" in res["issues"].lower()


def test_fail_no_framework_rejected():
    res = _run(training_probe(_FIX / "fail" / "no-framework"))
    assert res["passed"] is False
    assert "framework" in res["issues"].lower() or "import" in res["issues"].lower()


def test_fail_no_training_loop_rejected():
    res = _run(training_probe(_FIX / "fail" / "no-training-loop"))
    assert res["passed"] is False
    assert "loop" in res["issues"].lower()


def test_fail_no_checkpoint_rejected():
    res = _run(training_probe(_FIX / "fail" / "no-checkpoint"))
    assert res["passed"] is False
    assert "save" in res["issues"].lower() or "checkpoint" in res["issues"].lower()


def test_fail_no_config_rejected():
    res = _run(training_probe(_FIX / "fail" / "no-config"))
    assert res["passed"] is False
    assert "config" in res["issues"].lower() or "hparam" in res["issues"].lower()


def test_non_directory_rejected():
    res = _run(training_probe(_FIX / "nonexistent"))
    assert res["passed"] is False
    assert "not found" in res["issues"]
