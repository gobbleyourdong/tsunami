"""Canary — scaffolds/infra/docker-compose.

Structural + semantic checks on the compose file. We avoid actually
invoking `docker compose config` because docker may not be installed
in CI; instead we parse the YAML ourselves and assert the structural
invariants the scaffold promises:

- All four services present (web, db, cache, proxy)
- depends_on uses the health-aware long-form for db
- Healthchecks defined on the stateful services
- Named volumes declared for each stateful service's data dir
- env_file reference exists (.env.example) so the pattern works
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCAFFOLD = REPO_ROOT / "scaffolds" / "infra" / "docker-compose"


def test_scaffold_tree_exists() -> None:
    assert SCAFFOLD.is_dir()
    for rel in (
        "docker-compose.yml",
        ".env.example",
        ".gitignore",
        "README.md",
        "web/Dockerfile",
        "web/server.js",
        "web/package.json",
        "db/init.sql",
        "proxy/Caddyfile",
    ):
        assert (SCAFFOLD / rel).exists(), rel


def _load_compose() -> dict:
    return yaml.safe_load((SCAFFOLD / "docker-compose.yml").read_text())


def test_compose_yaml_parses() -> None:
    data = _load_compose()
    assert isinstance(data, dict)
    assert "services" in data


def test_all_four_services_present() -> None:
    services = _load_compose()["services"]
    for name in ("web", "db", "cache", "proxy"):
        assert name in services, f"missing service: {name}"


def test_web_depends_on_db_healthy() -> None:
    web = _load_compose()["services"]["web"]
    dep = web.get("depends_on", {})
    assert isinstance(dep, dict), "depends_on should use long-form for health gating"
    assert dep.get("db", {}).get("condition") == "service_healthy", (
        "web must wait for db to pass its healthcheck, not just start"
    )


def test_stateful_services_have_healthchecks() -> None:
    services = _load_compose()["services"]
    for name in ("web", "db", "cache"):
        hc = services[name].get("healthcheck")
        assert hc is not None, f"{name}: missing healthcheck"
        assert isinstance(hc.get("test"), list), f"{name}: healthcheck.test must be a list"


def test_named_volumes_for_stateful() -> None:
    data = _load_compose()
    volumes = data.get("volumes", {})
    for name in ("db_data", "cache_data"):
        assert name in volumes, f"missing named volume: {name}"
    db_mount = data["services"]["db"]["volumes"][0]
    assert db_mount.startswith("db_data:"), (
        "db service first volume should mount db_data, not a bind mount"
    )


def test_env_file_pattern() -> None:
    services = _load_compose()["services"]
    for name in ("web", "db"):
        env_files = services[name].get("env_file", [])
        assert ".env" in env_files, f"{name}: env_file pattern should reference .env"
    example = (SCAFFOLD / ".env.example").read_text()
    for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        assert key in example, f"missing key in .env.example: {key}"


def test_gitignore_excludes_dotenv() -> None:
    gi = (SCAFFOLD / ".gitignore").read_text()
    assert ".env" in gi, ".env must be gitignored"


def test_dockerfile_multistage() -> None:
    df = (SCAFFOLD / "web" / "Dockerfile").read_text()
    assert df.count("FROM ") >= 3, "expected multi-stage build (base, deps/build, runtime)"
    assert "CMD " in df, "missing CMD"


def test_caddyfile_reverse_proxies_web() -> None:
    cf = (SCAFFOLD / "proxy" / "Caddyfile").read_text()
    assert "reverse_proxy web:3000" in cf, (
        "Caddyfile should reverse-proxy to the compose-internal web:3000"
    )
