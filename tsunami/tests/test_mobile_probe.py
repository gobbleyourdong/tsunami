"""mobile_probe tests — pass/ (accepted) × fail/ (rejected).

Fixture layout:
  tests/fixtures/mobile/pass/{expo,react-native,pwa}/
  tests/fixtures/mobile/fail/{empty,missing-deps,malformed-manifest,
                              unlinked-manifest,dangling-entry,pwa-no-sw}/

Dispatch tests confirm detect_scaffold routes pass fixtures to
"mobile" (the three PWA/expo/RN paths all map to this).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.mobile_probe import mobile_probe, _detect_variant
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIX = _REPO / "tests" / "fixtures" / "mobile"


def _run(coro):
    return asyncio.run(coro)


# ── Dispatch registration ────────────────────────────────────────────

class TestDispatchRegistration:
    def test_mobile_in_PROBES(self):
        assert "mobile" in _PROBES
        assert _PROBES["mobile"] is mobile_probe

    def test_detect_expo(self):
        assert detect_scaffold(_FIX / "pass" / "expo") == "mobile"

    def test_detect_rn(self):
        assert detect_scaffold(_FIX / "pass" / "react-native") == "mobile"

    def test_detect_pwa(self):
        assert detect_scaffold(_FIX / "pass" / "pwa") == "mobile"


# ── Variant detection ────────────────────────────────────────────────

class TestVariantDetection:
    @staticmethod
    def _pkg(p: Path) -> dict:
        import json
        try:
            return json.loads((p / "package.json").read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def test_expo_detected(self):
        p = _FIX / "pass" / "expo"
        assert _detect_variant(p, self._pkg(p)) == "expo"

    def test_rn_detected(self):
        p = _FIX / "pass" / "react-native"
        assert _detect_variant(p, self._pkg(p)) == "react-native"

    def test_pwa_detected(self):
        p = _FIX / "pass" / "pwa"
        assert _detect_variant(p, self._pkg(p)) == "pwa"

    def test_empty_none(self):
        p = _FIX / "fail" / "empty"
        assert _detect_variant(p, {}) is None

    def test_missing_deps_none(self):
        p = _FIX / "fail" / "missing-deps"
        assert _detect_variant(p, self._pkg(p)) is None


# ── Probe pass corpus ────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["expo", "react-native", "pwa"])
def test_pass_fixtures_accepted(name):
    res = _run(mobile_probe(_FIX / "pass" / name))
    assert res["passed"] is True, (
        f"pass/{name} was rejected: {res['issues']}\n{res['raw']}"
    )


# ── Probe fail corpus ────────────────────────────────────────────────

def test_fail_empty_rejected():
    res = _run(mobile_probe(_FIX / "fail" / "empty"))
    assert res["passed"] is False
    assert "no mobile fingerprint" in res["issues"]


def test_fail_missing_deps_rejected():
    res = _run(mobile_probe(_FIX / "fail" / "missing-deps"))
    assert res["passed"] is False
    assert "no mobile fingerprint" in res["issues"]


def test_fail_malformed_manifest_rejected():
    res = _run(mobile_probe(_FIX / "fail" / "malformed-manifest"))
    # Malformed JSON can't be parsed → fingerprint fails → "no mobile fingerprint"
    # OR if we parsed past the error, PWA check rejects. Either path → passed=False.
    assert res["passed"] is False


def test_fail_unlinked_manifest_rejected():
    res = _run(mobile_probe(_FIX / "fail" / "unlinked-manifest"))
    assert res["passed"] is False
    assert "link rel" in res["issues"] or "no" in res["issues"].lower()


def test_fail_dangling_entry_rejected():
    res = _run(mobile_probe(_FIX / "fail" / "dangling-entry"))
    assert res["passed"] is False
    assert "no main entry" in res["issues"]


def test_fail_pwa_no_sw_rejected_by_fingerprint():
    # PWA without a service worker doesn't even fingerprint as mobile —
    # detect_scaffold's SW requirement filters it out before the probe
    # sees it. Confirms the filter: generic react-app w/manifest-only
    # doesn't get misrouted to mobile_probe.
    assert detect_scaffold(_FIX / "fail" / "pwa-no-sw") != "mobile"


def test_non_directory_rejected():
    res = _run(mobile_probe(_FIX / "nonexistent-variant"))
    assert res["passed"] is False
    assert "not found" in res["issues"]
