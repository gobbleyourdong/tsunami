"""data_pipeline_probe tests — script ETL + DBT variants."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tsunami.core.data_pipeline_probe import data_pipeline_probe
from tsunami.core.dispatch import _PROBES, detect_scaffold


_REPO = Path(__file__).resolve().parent.parent.parent
_FIX = _REPO / "tests" / "fixtures" / "data_pipeline"


def _run(coro):
    return asyncio.run(coro)


class TestDispatchRegistration:
    def test_in_PROBES(self):
        assert "data-pipeline" in _PROBES
        assert _PROBES["data-pipeline"] is data_pipeline_probe

    @pytest.mark.parametrize("name", [
        "script-pandas", "script-duckdb", "dbt-minimal",
    ])
    def test_detect_pass_fixtures(self, name):
        assert detect_scaffold(_FIX / "pass" / name) == "data-pipeline"


@pytest.mark.parametrize("name", [
    "script-pandas", "script-duckdb", "dbt-minimal",
])
def test_pass_fixtures_accepted(name):
    res = _run(data_pipeline_probe(_FIX / "pass" / name))
    assert res["passed"] is True, (
        f"pass/{name} rejected: {res['issues']}\n{res['raw']}"
    )


def test_fail_empty_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "empty"))
    assert res["passed"] is False
    assert "no pipeline entry" in res["issues"] or "not found" in res["issues"]


def test_fail_no_entry_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "no-entry"))
    assert res["passed"] is False
    assert "no pipeline entry" in res["issues"]


def test_fail_no_data_lib_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "no-data-lib"))
    assert res["passed"] is False
    assert "data library" in res["issues"] or "import" in res["issues"]


def test_fail_no_source_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "no-source"))
    assert res["passed"] is False
    assert "source" in res["issues"].lower() or "extract" in res["issues"].lower()


def test_fail_no_sink_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "no-sink"))
    assert res["passed"] is False
    assert "sink" in res["issues"].lower() or "load" in res["issues"].lower()


def test_fail_dbt_no_models_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "dbt-no-models"))
    assert res["passed"] is False
    assert "models" in res["issues"]


def test_fail_dbt_empty_sql_rejected():
    res = _run(data_pipeline_probe(_FIX / "fail" / "dbt-empty-sql"))
    assert res["passed"] is False
    assert "SELECT" in res["issues"] or "select" in res["issues"].lower()


def test_non_directory_rejected():
    res = _run(data_pipeline_probe(_FIX / "nonexistent"))
    assert res["passed"] is False
    assert "not found" in res["issues"]
