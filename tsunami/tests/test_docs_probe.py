"""docs_probe tests — SSG configs + bare markdown trees."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.docs_probe import docs_probe
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIX = _REPO / "tests" / "fixtures" / "docs"


def _run(coro):
    return asyncio.run(coro)


class TestDispatchRegistration:
    def test_in_PROBES(self):
        assert "docs" in _PROBES
        assert _PROBES["docs"] is docs_probe

    @pytest.mark.parametrize("name", ["mkdocs", "docusaurus", "bare-markdown"])
    def test_detect_pass_fixtures(self, name):
        assert detect_scaffold(_FIX / "pass" / name) == "docs"


@pytest.mark.parametrize("name", ["mkdocs", "docusaurus", "bare-markdown"])
def test_pass_fixtures_accepted(name):
    res = _run(docs_probe(_FIX / "pass" / name))
    assert res["passed"] is True, (
        f"pass/{name} rejected: {res['issues']}\n{res['raw']}"
    )


def test_fail_empty_rejected():
    res = _run(docs_probe(_FIX / "fail" / "empty"))
    assert res["passed"] is False
    assert "no SSG" in res["issues"] or "no config" in res["issues"].lower() or "docs" in res["issues"]


def test_fail_config_no_pages_rejected():
    res = _run(docs_probe(_FIX / "fail" / "config-no-pages"))
    assert res["passed"] is False
    # mkdocs.yml present but docs/ empty → should reject at "no pages"
    # (either because the dir doesn't exist, or it's empty)
    assert "pages" in res["issues"] or "no SSG" in res["issues"]


def test_fail_pages_no_homepage_rejected():
    res = _run(docs_probe(_FIX / "fail" / "pages-no-homepage"))
    assert res["passed"] is False
    assert "homepage" in res["issues"] or "index" in res["issues"]


def test_fail_pages_no_content_rejected():
    res = _run(docs_probe(_FIX / "fail" / "pages-no-content"))
    assert res["passed"] is False
    assert "content" in res["issues"] or "chars" in res["issues"] or "stub" in res["issues"]


def test_fail_stub_only_rejected():
    res = _run(docs_probe(_FIX / "fail" / "stub-only"))
    assert res["passed"] is False
    assert "content" in res["issues"] or "stub" in res["issues"]


def test_non_directory_rejected():
    res = _run(docs_probe(_FIX / "nonexistent"))
    assert res["passed"] is False
    assert "not found" in res["issues"]
