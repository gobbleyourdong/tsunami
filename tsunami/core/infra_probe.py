"""Infrastructure delivery gate — Dockerfile + docker-compose shape.

The infra vertical covers deployable stacks shipped as Docker/Compose
recipes. Probe is offline — we don't `docker build` (takes minutes,
needs daemon). Static checks on what's in the tree:

  1. At least one of: Dockerfile / docker-compose.yml / compose.yaml
     at project root (or common subpaths like docker/).
  2. Dockerfile starts with a `FROM` instruction (catches stub files).
  3. docker-compose.yml parses as YAML AND has a `services:` top-level
     key with ≥1 service defined.
  4. Every service has either `image:` or `build:`.
  5. `build:` paths resolve to a directory on disk that contains a
     Dockerfile (catches dangling references).
  6. No obvious plaintext secrets (literal `PASSWORD: admin` /
     `API_KEY: "sk-..."` in service env blocks).

Not caught:
  - Whether the image actually builds (needs docker daemon)
  - Whether services reach each other at runtime (needs compose up)
  - Kubernetes manifests, Terraform, Pulumi (future probes)
"""

from __future__ import annotations

import re
from pathlib import Path

from ._probe_common import result


_COMPOSE_CANDIDATES = (
    "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml",
    "docker/docker-compose.yml", "deploy/docker-compose.yml",
)

_DOCKERFILE_CANDIDATES = (
    "Dockerfile", "docker/Dockerfile",
    "deploy/Dockerfile", "app/Dockerfile",
)

# Regexes for plaintext-secret heuristic. Matches `KEY: "literal_value"`
# or `KEY=literal_value` where the value is neither a $VAR reference nor
# a ${VAR} expansion. Env-var refs (PASSWORD=${DB_PASSWORD}) are the
# correct pattern and should NOT flag.
_SECRET_KEYS = (
    "PASSWORD", "PASSWD", "SECRET", "API_KEY", "APIKEY", "TOKEN",
    "PRIVATE_KEY", "AWS_SECRET_ACCESS_KEY", "STRIPE_SECRET_KEY",
)


def _iter_compose_paths(project_dir: Path) -> list[Path]:
    return [project_dir / p for p in _COMPOSE_CANDIDATES
            if (project_dir / p).is_file()]


def _iter_dockerfile_paths(project_dir: Path) -> list[Path]:
    return [project_dir / p for p in _DOCKERFILE_CANDIDATES
            if (project_dir / p).is_file()]


def _load_yaml(text: str) -> tuple[dict | None, str]:
    """Parse YAML; return (data, error_message). pyyaml is stdlib-ish but
    not strictly guaranteed — fall back to a minimal parser if missing.
    """
    try:
        import yaml  # type: ignore
    except ImportError:
        return None, "pyyaml not installed; cannot validate compose shape"
    try:
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            return None, "compose root must be a mapping (services/volumes/...)"
        return data, ""
    except yaml.YAMLError as e:
        return None, f"yaml parse error: {e}"


def _check_dockerfile(path: Path) -> str:
    """Return '' if Dockerfile looks valid, else an error string."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"cannot read {path.name}: {e}"
    # Skip blank + comment lines before the first instruction
    first_instr = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        first_instr = stripped
        break
    if first_instr is None:
        return f"{path.name} is empty / comments-only"
    if not re.match(r'^(FROM|ARG)\s+', first_instr, re.IGNORECASE):
        return (f"{path.name} first instruction is not FROM/ARG: "
                f"`{first_instr[:80]}`")
    # Require at least one FROM somewhere (ARG-only = stub)
    if not re.search(r'(?im)^\s*FROM\s+\S+', text):
        return f"{path.name} has no FROM instruction (build would fail)"
    return ""


def _check_compose(project_dir: Path, path: Path) -> str:
    """Return '' if compose looks valid, else an error string."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"cannot read {path.name}: {e}"

    data, err = _load_yaml(text)
    if err:
        return f"{path.name}: {err}"

    services = data.get("services")
    if not isinstance(services, dict) or not services:
        return (f"{path.name}: no `services:` key with ≥1 service "
                "(compose root needs a services mapping)")

    for name, svc in services.items():
        if not isinstance(svc, dict):
            return f"{path.name}: service `{name}` is not a mapping"
        has_image = "image" in svc
        has_build = "build" in svc
        if not (has_image or has_build):
            return (f"{path.name}: service `{name}` has neither "
                    "`image:` nor `build:`")
        if has_build:
            build_val = svc["build"]
            build_ctx = (build_val if isinstance(build_val, str)
                         else build_val.get("context") if isinstance(build_val, dict)
                         else None)
            if isinstance(build_ctx, str):
                ctx_path = (project_dir / build_ctx).resolve()
                if not ctx_path.is_dir():
                    return (f"{path.name}: service `{name}` build context "
                            f"`{build_ctx}` is not a directory")
                # dockerfile override or conventional Dockerfile
                df_override = (build_val.get("dockerfile")
                               if isinstance(build_val, dict) else None)
                df_path = (ctx_path / df_override if df_override
                           else ctx_path / "Dockerfile")
                if not df_path.is_file():
                    return (f"{path.name}: service `{name}` build context "
                            f"`{build_ctx}` has no Dockerfile")

        # Plaintext-secret sniff in env block
        env = svc.get("environment")
        sec = _find_plaintext_secret(env)
        if sec:
            return (f"{path.name}: service `{name}` has plaintext "
                    f"secret `{sec}` in environment — use "
                    "${ENV_VAR} reference or secrets:")

    return ""


def _find_plaintext_secret(env) -> str | None:
    """Return the offending key name if a literal secret is set, else None.

    Accepts compose's two env shapes: dict or list of `KEY=value` strings.
    """
    def _matches(key: str) -> bool:
        u = key.upper()
        # Substring match — catches POSTGRES_PASSWORD, DB_API_KEY, etc.
        return any(sk in u for sk in _SECRET_KEYS)

    if isinstance(env, dict):
        for k, v in env.items():
            if _matches(str(k)) and isinstance(v, str) and v.strip():
                if "$" not in v:  # $VAR or ${VAR} is fine
                    return str(k)
    elif isinstance(env, list):
        for item in env:
            if not isinstance(item, str) or "=" not in item:
                continue
            k, _, v = item.partition("=")
            if _matches(k.strip()) and v.strip() and "$" not in v:
                return k.strip()
    return None


async def infra_probe(
    project_dir: Path,
    task_text: str = "",
) -> dict:
    """Dockerfile valid AND/OR compose valid; at least one present."""
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        return result(False, f"project dir not found: {project_dir}")

    dockerfiles = _iter_dockerfile_paths(project_dir)
    composefiles = _iter_compose_paths(project_dir)

    if not dockerfiles and not composefiles:
        return result(
            False,
            "infra: no Dockerfile or compose file found. Checked "
            f"{', '.join(_DOCKERFILE_CANDIDATES[:3])} and "
            f"{', '.join(_COMPOSE_CANDIDATES[:3])}.",
        )

    issues: list[str] = []
    for df in dockerfiles:
        err = _check_dockerfile(df)
        if err:
            issues.append(err)
    for cf in composefiles:
        err = _check_compose(project_dir, cf)
        if err:
            issues.append(err)

    if issues:
        return result(
            False,
            "infra: " + "; ".join(issues[:3]),
        )

    found = []
    if dockerfiles:
        found.append(f"dockerfiles: {', '.join(d.name for d in dockerfiles)}")
    if composefiles:
        found.append(f"compose: {', '.join(c.name for c in composefiles)}")
    return result(True, "", raw="\n".join(found))


__all__ = ["infra_probe"]
