"""infra_probe tests — Dockerfile + docker-compose shape validation.

Fixture layout:
  tests/fixtures/infra/pass/{dockerfile-only,compose-only,compose-with-build}/
  tests/fixtures/infra/fail/{empty,compose-malformed,service-no-image,
                             build-dangling,plaintext-secret,empty-dockerfile}/
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.infra_probe import infra_probe
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIX = _REPO / "tests" / "fixtures" / "infra"


def _run(coro):
    return asyncio.run(coro)


# ── Dispatch registration ────────────────────────────────────────────

class TestDispatchRegistration:
    def test_infra_in_PROBES(self):
        assert "infra" in _PROBES
        assert _PROBES["infra"] is infra_probe

    @pytest.mark.parametrize("name", [
        "dockerfile-only", "compose-only", "compose-with-build",
    ])
    def test_detect_pass_fixtures(self, name):
        assert detect_scaffold(_FIX / "pass" / name) == "infra"


# ── Probe pass corpus ────────────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "dockerfile-only", "compose-only", "compose-with-build",
])
def test_pass_fixtures_accepted(name):
    res = _run(infra_probe(_FIX / "pass" / name))
    assert res["passed"] is True, (
        f"pass/{name} rejected: {res['issues']}\n{res['raw']}"
    )


# ── Probe fail corpus ────────────────────────────────────────────────

def test_fail_empty_rejected():
    res = _run(infra_probe(_FIX / "fail" / "empty"))
    assert res["passed"] is False
    assert "no Dockerfile" in res["issues"] or "compose" in res["issues"]


def test_fail_compose_malformed_rejected():
    res = _run(infra_probe(_FIX / "fail" / "compose-malformed"))
    assert res["passed"] is False
    assert "yaml parse" in res["issues"].lower() or "parse" in res["issues"].lower()


def test_fail_service_no_image_rejected():
    res = _run(infra_probe(_FIX / "fail" / "service-no-image"))
    assert res["passed"] is False
    assert "image" in res["issues"] and "build" in res["issues"]


def test_fail_build_dangling_rejected():
    res = _run(infra_probe(_FIX / "fail" / "build-dangling"))
    assert res["passed"] is False
    assert "build" in res["issues"] and "directory" in res["issues"]


def test_fail_plaintext_secret_rejected():
    res = _run(infra_probe(_FIX / "fail" / "plaintext-secret"))
    assert res["passed"] is False
    assert "secret" in res["issues"].lower() or "plaintext" in res["issues"].lower()


def test_fail_empty_dockerfile_rejected():
    res = _run(infra_probe(_FIX / "fail" / "empty-dockerfile"))
    assert res["passed"] is False
    # Empty/comments-only OR no FROM — either message is legit
    assert (
        "empty" in res["issues"].lower()
        or "FROM" in res["issues"]
        or "first instruction" in res["issues"]
    )


def test_non_directory_rejected():
    res = _run(infra_probe(_FIX / "nonexistent"))
    assert res["passed"] is False
    assert "not found" in res["issues"]
