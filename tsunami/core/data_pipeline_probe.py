"""Data-pipeline delivery gate — ETL script + DBT project shapes.

The data-pipeline vertical covers batch data processing deliverables:
Python/SQL scripts that extract, transform, and load data between
sources and sinks. Probe is offline — we don't execute the pipeline
(would need real sources/sinks + potentially hours of compute).

Two supported shapes:

  **Script ETL**: a single-file or package-style Python pipeline with
    recognizable extract → transform → load stages. Common anchors:
    pandas, polars, pyarrow, sqlalchemy, duckdb, snowflake-connector.

  **DBT project**: `dbt_project.yml` + `models/` directory with ≥1
    .sql file that contains a SELECT. Optional profiles.yml.

Requirements (script ETL):
  1. Entry file exists (pipeline.py / etl.py / ingest.py / main.py
     at root, src/, scripts/, or pipelines/)
  2. Data-library import (pandas, polars, pyarrow, sqlalchemy,
     duckdb, pyspark, apache_beam, boto3-for-S3, snowflake,
     google-cloud, pymongo, psycopg2/psycopg, sqlite3)
  3. Source/extract marker (read_csv, read_parquet, read_json,
     read_sql, from_csv, pd.read_, duckdb.read_, SELECT ... FROM,
     client.query, open() on a .csv path)
  4. Sink/load marker (to_csv, to_parquet, to_sql, write_, INSERT
     INTO, COPY INTO, upload_file, put_object, execute(insert))

Requirements (DBT):
  1. dbt_project.yml exists and parses
  2. models/ directory exists with ≥1 .sql file
  3. At least one .sql contains a SELECT statement

Not caught:
  - Whether source credentials / connections actually work
  - Whether output schema matches downstream expectations
  - Pipeline correctness (idempotency, schema drift, PII handling)
"""

from __future__ import annotations

import re
from pathlib import Path

from ._probe_common import result, read_text as _read, scan_markers as _scan


_ENTRY_CANDIDATES = (
    "pipeline.py", "etl.py", "ingest.py", "transform.py", "load.py",
    "main.py", "run.py",
    "src/pipeline.py", "src/etl.py", "src/ingest.py", "src/main.py",
    "scripts/pipeline.py", "scripts/etl.py", "scripts/ingest.py",
    "pipelines/main.py", "pipelines/run.py",
)

_DATA_LIBS = (
    "pandas", "polars", "pyarrow", "sqlalchemy", "duckdb", "pyspark",
    "apache_beam", "dask", "snowflake.connector", "snowflake_connector",
    "google.cloud", "psycopg2", "psycopg", "pymongo", "boto3",
    "sqlite3",
)

_SOURCE_MARKERS = (
    "read_csv(", "read_parquet(", "read_json(", "read_sql(",
    "read_excel(", "read_feather(", "read_orc(",
    "from_csv(", "from_parquet(",
    "pd.read_", "pl.read_", "duckdb.read_",
    "client.query(", "bq_client.query", ".table(",
    "SELECT ", "select ",  # SQL query presence
    "extract(", "extract_",
)

_SINK_MARKERS = (
    "to_csv(", "to_parquet(", "to_json(", "to_sql(", "to_excel(",
    "to_feather(", "to_orc(", "write_csv(", "write_parquet(",
    ".write.", ".saveAsTable(", "write_to_parquet",
    "INSERT INTO", "insert into", "COPY INTO", "copy into",
    "upload_file(", "upload_blob(", "put_object(", "upload(",
    "load_table(", "load_", "bulk_insert", "to_gbq(",
    "s3_put", "blob.upload",
)


def _find_entry(project_dir: Path) -> Path | None:
    for rel in _ENTRY_CANDIDATES:
        p = project_dir / rel
        if p.is_file():
            return p
    return None


def _is_dbt_project(project_dir: Path) -> bool:
    return (project_dir / "dbt_project.yml").is_file()


def _check_dbt(project_dir: Path) -> dict:
    """dbt_project.yml + models/ with ≥1 .sql containing SELECT."""
    proj_file = project_dir / "dbt_project.yml"
    try:
        import yaml
        data = yaml.safe_load(_read(proj_file))
        if not isinstance(data, dict) or "name" not in data:
            return result(False, "dbt: dbt_project.yml missing `name` key")
    except ImportError:
        # pyyaml missing — accept presence as sufficient
        pass
    except Exception as e:
        return result(False, f"dbt: dbt_project.yml parse error: {e}")

    models_dir = project_dir / "models"
    if not models_dir.is_dir():
        return result(False, "dbt: models/ directory not found")

    sql_files = list(models_dir.rglob("*.sql"))
    if not sql_files:
        return result(False, "dbt: models/ has no .sql files")

    has_select = False
    for sf in sql_files:
        text = _read(sf)
        # Strip SQL comments — placeholder models often mention "SELECT"
        # in a comment ("TODO: add SELECT statement") without actually
        # defining one. Must check against de-commented text.
        text = re.sub(r"--[^\n]*", "", text)
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
        # Real SELECT is followed by identifier / star / quote / paren,
        # not an English word continuing a sentence.
        if re.search(r"(?im)^\s*select\s+(\*|\w+|`|\"|\()", text):
            has_select = True
            break
    if not has_select:
        return result(
            False,
            f"dbt: {len(sql_files)} SQL file(s) in models/ but none "
            "contain a SELECT statement",
        )

    rel_models = models_dir.relative_to(project_dir)
    return result(
        True, "",
        raw=f"shape=dbt\nmodels={rel_models}/ ({len(sql_files)} .sql)",
    )


def _check_script(project_dir: Path, entry: Path) -> dict:
    """Script ETL: data-lib import + source marker + sink marker."""
    text = _read(entry)
    if not text:
        return result(False, f"data-pipeline: cannot read {entry.name}")

    libs = [lib for lib in _DATA_LIBS
            if f"import {lib}" in text or f"from {lib}" in text]
    if not libs:
        # Cross-scan sibling files — pipelines sometimes split modules
        py_sibs = list(project_dir.rglob("*.py"))
        cross = set()
        for p in py_sibs[:50]:
            if p == entry:
                continue
            t = _read(p)
            cross.update(
                lib for lib in _DATA_LIBS
                if f"import {lib}" in t or f"from {lib}" in t
            )
        libs = list(cross)
    if not libs:
        return result(
            False,
            f"data-pipeline: {entry.name} (and siblings) import no data "
            f"library. Expected one of: {', '.join(_DATA_LIBS[:8])}…",
        )

    src_hits = _scan(text, _SOURCE_MARKERS)
    sink_hits = _scan(text, _SINK_MARKERS)

    # Like libs — also scan the whole project so multi-file pipelines
    # (extract.py + transform.py + load.py) still fingerprint correctly.
    if not src_hits or not sink_hits:
        for p in list(project_dir.rglob("*.py"))[:50]:
            if p == entry:
                continue
            t = _read(p)
            if not src_hits:
                src_hits = _scan(t, _SOURCE_MARKERS)
            if not sink_hits:
                sink_hits = _scan(t, _SINK_MARKERS)
            if src_hits and sink_hits:
                break

    if not src_hits:
        return result(
            False,
            f"data-pipeline: no source/extract marker found. Expected "
            "one of: read_csv(, read_parquet(, read_sql(, SELECT ..., "
            "client.query(, ...",
        )
    if not sink_hits:
        return result(
            False,
            f"data-pipeline: no sink/load marker found. Expected one "
            "of: to_csv(, to_parquet(, to_sql(, INSERT INTO, "
            "upload_file(, put_object(, ...",
        )

    rel = entry.relative_to(project_dir) if entry.is_relative_to(project_dir) else entry
    return result(
        True, "",
        raw=(f"shape=script\nentry={rel}\n"
             f"libs={', '.join(libs[:3])}\n"
             f"source={', '.join(src_hits[:2])}\n"
             f"sink={', '.join(sink_hits[:2])}"),
    )


async def data_pipeline_probe(
    project_dir: Path,
    task_text: str = "",
) -> dict:
    """Dispatch to dbt or script check based on fingerprint."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    if _is_dbt_project(project_dir):
        return _check_dbt(project_dir)

    entry = _find_entry(project_dir)
    if entry is None:
        return result(
            False,
            "data-pipeline: no pipeline entry found. Checked "
            f"{', '.join(_ENTRY_CANDIDATES[:4])}… and dbt_project.yml.",
        )
    return _check_script(project_dir, entry)


__all__ = ["data_pipeline_probe"]
