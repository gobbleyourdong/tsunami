"""Pick the right delivery-gate probe for a given deliverable.

The wave knows which scaffold it picked (`project_init` return value),
but at delivery time it's convenient to derive the probe purely from
the on-disk fingerprint — so the dispatcher works whether the caller
threads the scaffold name through or not.

Usage from agent.py:

    from .core.dispatch import probe_for_delivery
    result = await probe_for_delivery(project_dir, task_text)
    # result has the same shape as vision_check: {passed, issues, raw}

`result["passed"] is True` when either:
  - the matched probe passed, OR
  - no probe matched (scaffold not in our probe set) — fall-through.

Explicit `scaffold` kwarg short-circuits the fingerprint detection.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ._probe_common import result as _result, skip as _skip
from .cli_probe import cli_probe
from .data_pipeline_probe import data_pipeline_probe
from .docs_probe import docs_probe
from .electron_probe import electron_probe
from .extension_probe import extension_probe
from .gamedev_probe import gamedev_probe
from .gamedev_scaffold_probe import gamedev_probe_dispatch
from .infra_probe import infra_probe
from .mobile_probe import mobile_probe
from .openapi_probe import openapi_probe
from .server_probe import server_probe
from .sse_probe import sse_probe
from .training_probe import training_probe
from .ws_probe import ws_probe

log = logging.getLogger("tsunami.core.dispatch")


# Scaffold name → probe entrypoint (async). Kept as a module-level map
# so tests and callers can introspect the set of wired gates.
_PROBES = {
    "chrome-extension": extension_probe,
    "electron-app":     electron_probe,
    "api-only":         openapi_probe,
    "realtime":         ws_probe,
    "auth-app":         server_probe,
    "fullstack":        server_probe,
    "ai-app":           sse_probe,
    # F-B5 — gamedev has two delivery shapes:
    #   - legacy: public/game_definition.json (handled by gamedev_probe)
    #   - new:    data/*.json + src/scenes/*.ts (handled by
    #             gamedev_scaffold_probe)
    # gamedev_probe_dispatch picks at call time based on on-disk markers.
    "gamedev":          gamedev_probe_dispatch,
    # Tide 001 — CLI tools (python click/argparse/typer, node commander,
    # POSIX shebang scripts). Fingerprinted by package.json.bin,
    # pyproject.toml [project.scripts], or conventional bin/ + cli.py.
    "cli":              cli_probe,
    # Tide 002 — Mobile (Expo/React Native native + PWA). Fingerprinted
    # by expo/react-native deps OR public/manifest.json without
    # manifest_version (chrome-extension uses that key; PWA doesn't).
    "mobile":           mobile_probe,
    # Tide 003 — ML training-recipe (fine-tune, pretrain, eval).
    # Fingerprinted by pyproject with train*/finetune* console script,
    # or conventional train.py/finetune.py/main.py at root with ML
    # framework imports. Probe is static — doesn't run training.
    "training":         training_probe,
    # Tide 004 — Infrastructure (Dockerfile + docker-compose). Static
    # validation; doesn't run `docker build`. Fingerprint: Dockerfile
    # or compose.yml at root / docker/ / deploy/.
    "infra":            infra_probe,
    # Tide 005 — Data pipeline (ETL scripts + DBT projects). Offline
    # static check: entry + data-lib import + source marker + sink
    # marker, OR dbt_project.yml + models/*.sql with SELECT.
    "data-pipeline":    data_pipeline_probe,
    # Tide 006 — Docs site (MkDocs, Docusaurus, VitePress, Sphinx,
    # Hugo, Astro, Jekyll, bare markdown). Static check — doesn't
    # build. Requires config OR docs/ tree + content pages + homepage.
    "docs":             docs_probe,
}
# Direct handle to the legacy probe for callers that want to bypass the
# scaffold router (introspection + tests).
_gamedev_probe_legacy = gamedev_probe


def detect_scaffold(project_dir: Path) -> str | None:
    """Fingerprint the deliverable. Returns the scaffold name or None.

    Priority order — most specific markers first:
      1. chrome-extension: dist/manifest.json exists with manifest_version=3
      2. electron-app:     package.json has `electron` dep or `main` points at electron entry
      3. api-only:         package.json has no `react` dep and has an openapi file
      4. realtime:         server file imports a ws library
      5. ai-app:           client code references `VITE_MODEL_ENDPOINT` or an SSE EventSource
      6. auth-app:         `server/` sibling dir with an auth route
      7. fullstack:        `server/` sibling dir without auth
    """
    project_dir = Path(project_dir)
    pkg_path = project_dir / "package.json"
    pkg: dict = {}
    if pkg_path.is_file():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pkg = {}

    deps = {**(pkg.get("dependencies") or {}),
            **(pkg.get("devDependencies") or {})}

    # 1. chrome-extension
    ext_manifest = project_dir / "dist" / "manifest.json"
    if ext_manifest.is_file():
        try:
            if json.loads(ext_manifest.read_text(encoding="utf-8")).get("manifest_version") == 3:
                return "chrome-extension"
        except json.JSONDecodeError:
            pass
    # Source manifest also counts (pre-build detection)
    src_manifest = project_dir / "public" / "manifest.json"
    if src_manifest.is_file():
        try:
            if json.loads(src_manifest.read_text(encoding="utf-8")).get("manifest_version") == 3:
                return "chrome-extension"
        except json.JSONDecodeError:
            pass

    # 2. mobile — expo / react-native in deps beats generic react
    # routing because RN apps usually also pull react. Checked BEFORE
    # electron (RN apps sometimes pull electron-for-desktop side-builds).
    if "expo" in deps or "react-native" in deps:
        return "mobile"

    # 3. electron-app
    if "electron" in deps or "electron-builder" in deps:
        return "electron-app"

    # 3. api-only — no react, has openapi source file or npm script
    has_react = "react" in deps or "react-dom" in deps
    openapi_src = any((project_dir / p).is_file()
                      for p in ("src/openapi.ts", "src/openapi.js",
                                "openapi.json", "openapi.yaml"))
    if not has_react and openapi_src:
        return "api-only"
    if not has_react and pkg.get("scripts", {}).get("openapi"):
        return "api-only"

    # 4. realtime — ws dependency
    if "ws" in deps or "socket.io" in deps or "socket.io-client" in deps:
        return "realtime"

    # 5. ai-app — SSE markers in client env or code
    env_file = project_dir / ".env"
    if env_file.is_file():
        try:
            txt = env_file.read_text(encoding="utf-8", errors="replace")
            if "VITE_MODEL_ENDPOINT" in txt or "VITE_OPENAI_ENDPOINT" in txt:
                return "ai-app"
        except OSError:
            pass

    # 6 / 7. auth-app vs fullstack — both have server/
    server_dir = project_dir / "server"
    if server_dir.is_dir():
        auth_markers = ("login", "signup", "jwt", "bcrypt", "passport", "auth")
        for py in server_dir.rglob("*.ts"):
            try:
                s = py.read_text(encoding="utf-8", errors="replace")[:8000].lower()
            except OSError:
                continue
            if any(m in s for m in auth_markers):
                return "auth-app"
        return "fullstack"

    # 8. gamedev — two shapes:
    #   - new scaffold flow: package.json name `gamedev-*-scaffold` +
    #     a populated data/ dir with *.json (scaffold deliverable)
    #   - legacy flow: public/game_definition.json emitted by the
    #     wave's emit_design tool
    pkg_name = (pkg.get("name") or "") if isinstance(pkg, dict) else ""
    data_dir = project_dir / "data"
    if pkg_name.startswith("gamedev-") and data_dir.is_dir() and any(data_dir.glob("*.json")):
        return "gamedev"
    # Scaffold-first projects retain the seed package.json's description
    # + src/scenes/ layout + data/mechanics.json even after the project
    # name is customized. Detect by structural signature rather than
    # package name, which `project_init_gamedev` rewrites to the
    # deliverable's slug (breaks the startswith check above).
    mechanics_json = data_dir / "mechanics.json"
    scenes_dir = project_dir / "src" / "scenes"
    if mechanics_json.is_file() and scenes_dir.is_dir():
        return "gamedev"
    if (project_dir / "public" / "game_definition.json").is_file():
        return "gamedev"
    if (project_dir / "game_definition.json").is_file():
        return "gamedev"

    # 9. mobile (PWA variant) — public/manifest.json without
    # manifest_version (chrome-ext uses that key) + a service worker.
    # Service-worker requirement filters out generic react apps that
    # just happen to ship a manifest.json; a dedicated PWA ships both.
    pwa_manifest = None
    for mp in (project_dir / "public" / "manifest.json",
               project_dir / "manifest.json"):
        if mp.is_file():
            try:
                md = json.loads(mp.read_text(encoding="utf-8"))
                if not md.get("manifest_version"):
                    pwa_manifest = mp
                    break
            except json.JSONDecodeError:
                pass
    if pwa_manifest is not None:
        has_sw = any((project_dir / p).is_file() for p in (
            "public/sw.js", "public/service-worker.js",
            "public/workbox-sw.js", "src/sw.ts", "src/service-worker.ts",
            "sw.js", "service-worker.js",
        ))
        if has_sw:
            return "mobile"

    # 10. training — ML training-recipe. Checked BEFORE cli because
    # a training repo often ships a `train.py` entry that would
    # otherwise route to cli_probe (which would pass it on --help
    # but miss the framework / checkpoint / config requirements).
    # Fingerprint: conventional training entry + ML framework import,
    # OR pyproject [project.scripts] with a train*/finetune*/pretrain*
    # named script.
    _training_entries = ("train.py", "finetune.py", "fine_tune.py",
                         "pretrain.py", "src/train.py", "src/finetune.py",
                         "scripts/train.py", "scripts/finetune.py")
    for rel in _training_entries:
        p = project_dir / rel
        if not p.is_file():
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        ml_imports = ("torch", "transformers", "pytorch_lightning", "lightning",
                      "tensorflow", "keras", "jax", "flax", "accelerate",
                      "peft", "unsloth", "trl")
        if any(f"import {m}" in head or f"from {m}" in head for m in ml_imports):
            return "training"
    # pyproject script hint
    pyproj = project_dir / "pyproject.toml"
    if pyproj.is_file():
        try:
            t = pyproj.read_text(encoding="utf-8", errors="replace")
            if any(
                re.search(rf"(?m)^\s*{name}\w*\s*=\s*['\"]", t)
                for name in ("train", "finetune", "fine_tune", "pretrain")
            ):
                # Only promote if the project also imports an ML framework
                # somewhere (prevents a 'train' script that's actually a
                # model-training cli for e.g. a shell game from misrouting).
                if any(m in t for m in ("torch", "transformers", "lightning")):
                    return "training"
        except OSError:
            pass

    # 11. data-pipeline — DBT project OR pipeline-named entry with
    # a data library imported. Checked BEFORE cli because pipeline.py
    # would otherwise route to cli_probe (which would --help-pass
    # but miss source/sink/data-lib requirements). Distinguished
    # from training by data-lib imports (pandas/polars/sqlalchemy)
    # vs ML frameworks (torch/transformers).
    if (project_dir / "dbt_project.yml").is_file():
        return "data-pipeline"
    _pipeline_entries = ("pipeline.py", "etl.py", "ingest.py",
                         "transform.py", "src/pipeline.py",
                         "src/etl.py", "scripts/pipeline.py",
                         "pipelines/main.py")
    for rel in _pipeline_entries:
        p = project_dir / rel
        if not p.is_file():
            continue
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        data_libs = ("pandas", "polars", "pyarrow", "sqlalchemy",
                     "duckdb", "pyspark", "apache_beam", "boto3",
                     "snowflake", "psycopg", "pymongo", "sqlite3")
        if any(f"import {m}" in head or f"from {m}" in head for m in data_libs):
            return "data-pipeline"

    # 12. cli — has CLI entry-point markers. Checked AFTER web/server
    # fingerprints so a fullstack app with a helper bin/ script doesn't
    # misroute to cli_probe. A pure CLI tool (no react, no server/ dir,
    # no openapi) with any of:
    #   - package.json "bin" field
    #   - pyproject.toml [project.scripts] or [tool.poetry.scripts]
    #   - conventional bin/cli* / src/cli.* / cli.py / main.py at root
    if isinstance(pkg, dict) and pkg.get("bin"):
        return "cli"
    pyproj = project_dir / "pyproject.toml"
    if pyproj.is_file():
        try:
            t = pyproj.read_text(encoding="utf-8", errors="replace")
            if "[project.scripts]" in t or "[tool.poetry.scripts]" in t:
                return "cli"
        except OSError:
            pass
    # conventional root-level cli entry files
    for rel in ("bin/cli", "bin/cli.py", "bin/main", "bin/main.py",
                "src/cli.py", "cli.py", "main.py"):
        if (project_dir / rel).is_file():
            return "cli"

    # 12. docs — SSG config OR a bare docs/ tree with ≥2 .md files.
    # Ordered BEFORE infra because a docs site can trivially ship with
    # a Dockerfile for hosting, and we want docs to win that routing.
    for rel in ("mkdocs.yml", "docusaurus.config.js", "docusaurus.config.ts",
                ".vitepress/config.js", ".vitepress/config.ts",
                ".vitepress/config.mjs", "astro.config.mjs", "astro.config.js",
                "astro.config.ts", "hugo.toml", "hugo.yaml"):
        if (project_dir / rel).is_file():
            return "docs"
    # conf.py is ambiguous (Sphinx vs. generic Python config) — require
    # index.rst alongside to claim docs.
    if (project_dir / "conf.py").is_file() and (
        (project_dir / "index.rst").is_file()
        or (project_dir / "docs" / "index.rst").is_file()
        or (project_dir / "source" / "index.rst").is_file()
    ):
        return "docs"
    # _config.yml + _posts/ indicates jekyll; _config.yml alone is too
    # weak (many projects use it for other tooling).
    if (project_dir / "_config.yml").is_file() and (project_dir / "_posts").is_dir():
        return "docs"
    # Bare docs: docs/ or content/ with ≥3 .md files and an index/README
    for content_root in ("docs", "content"):
        d = project_dir / content_root
        if not d.is_dir():
            continue
        mds = list(d.rglob("*.md"))
        if len(mds) >= 3 and any(
            m.name.lower() in ("index.md", "readme.md", "intro.md") for m in mds
        ):
            return "docs"

    # 13. infra — Dockerfile or docker-compose at root / docker/ / deploy/.
    # Last in priority order because an infra deliverable can piggy-back
    # on any web/cli/training project (dockerizing an existing app).
    # We only claim "infra" when THE PRIMARY shipping artifact is the
    # stack definition — no other fingerprint matched. This means: an
    # existing web app with a Dockerfile routes to its web probe; a
    # standalone "deploy the stack" deliverable routes here.
    for rel in ("Dockerfile", "docker/Dockerfile", "deploy/Dockerfile",
                "docker-compose.yml", "docker-compose.yaml",
                "compose.yml", "compose.yaml"):
        if (project_dir / rel).is_file():
            return "infra"

    return None


async def probe_for_delivery(
    project_dir: Path,
    task_text: str = "",
    scaffold: str | None = None,
) -> dict:
    """Dispatch to the right probe. Returns `vision_check`-shaped dict.

    `scaffold` may be passed if the wave already knows it (from
    `project_init` return). Otherwise we fingerprint on-disk.

    SECURITY (sev-5 patch, 2026-04-21): fail CLOSED on every
    can't-verify path. The previous contract ("passed=True with skip
    marker when no probe matches — don't let an unconfigured scaffold
    block delivery") converted "I don't know" into "yes this is fine,"
    which Current's 2026-04-20 finding showed allowed any
    unclassifiable deliverable to ship. Post-patch: no fingerprint,
    no registered probe, and probe exceptions all return
    passed=False with an explicit issue string. Missing project dir
    stays a skip (caller bug, not a deliverable-verification call).
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        # Caller supplied a bogus path — not a verification question.
        # Skip (passed=True) preserves the ability to run the probe
        # pipeline without a deliverable for introspection/tests.
        return _skip(f"no project dir: {project_dir}")

    picked = scaffold or detect_scaffold(project_dir)
    if picked is None:
        return _result(
            False,
            "delivery-gate: no scaffold fingerprint on the deliverable. "
            "The dispatcher could not classify this project against any "
            "known vertical (chrome-extension/electron/api-only/realtime/"
            "auth-app/fullstack/ai-app/gamedev/cli/mobile/training/"
            "data-pipeline/docs/infra). Either provision via project_init* "
            "first, or add a fingerprint for this new vertical to "
            "detect_scaffold() before shipping.",
        )

    probe = _PROBES.get(picked)
    if probe is None:
        return _result(
            False,
            f"delivery-gate: scaffold '{picked}' has no registered "
            "probe in _PROBES. Add one or rename the scaffold "
            "fingerprint to match an existing probe.",
        )

    log.info(f"[gate-dispatch] scaffold={picked} probe={probe.__name__} dir={project_dir}")
    try:
        return await probe(project_dir)
    except Exception as e:
        # Probe crashes are deliverable-verification failures, NOT
        # skip markers. A probe that can't complete cannot certify.
        log.warning(f"[gate-dispatch] probe threw: {e}")
        return _result(
            False,
            f"delivery-gate: probe '{probe.__name__}' raised "
            f"{type(e).__name__}: {e}. A crashing probe cannot certify a "
            "deliverable; fix the probe or the deliverable before retry.",
        )


__all__ = ["probe_for_delivery", "detect_scaffold"]
