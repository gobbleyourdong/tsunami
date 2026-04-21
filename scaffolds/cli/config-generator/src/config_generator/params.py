"""Parameter loading + merging.

Sources (applied in this order, later overrides earlier):

1. Defaults baked into the template registry.
2. A parameter file (``--params path.yaml`` / ``.json`` / ``.toml``).
3. Env vars with a prefix (``--env-prefix CFG_`` picks up ``CFG_HOST=…``).
4. CLI ``--set key=value`` (repeatable; value parsed as JSON if it
   looks like JSON, else treated as a string).

Dotted keys descend into nested maps: ``--set db.host=localhost``
becomes ``{"db": {"host": "localhost"}}``.
"""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path

import yaml


Params = dict[str, object]


def load_param_file(path: str) -> Params:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower().lstrip(".")
    if suffix in ("yaml", "yml"):
        data = yaml.safe_load(text) or {}
    elif suffix == "json":
        data = json.loads(text)
    elif suffix == "toml":
        data = tomllib.loads(text)
    else:
        raise ValueError(f"unknown param file format: {suffix!r} (expected yaml/json/toml)")
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level must be a mapping")
    return data


def load_env_prefix(prefix: str) -> Params:
    out: Params = {}
    for k, v in os.environ.items():
        if k.startswith(prefix):
            key = k[len(prefix):].lower()
            out[key] = v
    return out


def _coerce_scalar(raw: str) -> object:
    """Parse a --set value. JSON-shaped → JSON, else string."""
    s = raw.strip()
    if not s:
        return ""
    if s[0] in "{[\"" or s in ("true", "false", "null") or _looks_numeric(s):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return raw
    return raw


def _looks_numeric(s: str) -> bool:
    if not s:
        return False
    try:
        float(s)
        return True
    except ValueError:
        return False


def set_dotted(dst: Params, key: str, value: object) -> None:
    parts = key.split(".")
    cur: dict = dst  # type: ignore[assignment]
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def apply_sets(base: Params, sets: list[str]) -> Params:
    out: Params = _deep_copy(base)
    for spec in sets:
        if "=" not in spec:
            raise ValueError(f"--set expects key=value, got {spec!r}")
        k, v = spec.split("=", 1)
        set_dotted(out, k.strip(), _coerce_scalar(v))
    return out


def _deep_copy(d: Params) -> Params:
    return json.loads(json.dumps(d, default=str))


def merge(*sources: Params) -> Params:
    """Deep-merge in order; later sources override earlier ones.

    Sub-mappings are merged recursively; lists and scalars are replaced.
    """
    out: Params = {}
    for s in sources:
        _merge_into(out, s)
    return out


def _merge_into(dst: Params, src: Params) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge_into(dst[k], v)  # type: ignore[arg-type]
        else:
            dst[k] = v
