"""Jinja2 rendering + post-render validation.

The renderer is StrictUndefined so a missing param fails loudly instead
of emitting an empty string — caught in the canary. After render, the
output is parsed in its target format; if parsing fails, the error
wraps the original line number so the scaffold user sees where their
template produced invalid output.
"""
from __future__ import annotations

import configparser
import io
import json
from importlib import resources
from pathlib import Path

import jinja2
import yaml


OutputFormat = str  # "yaml" | "json" | "toml" | "ini" | "env" | "text"


def load_template(name_or_path: str) -> str:
    """Load a template. Bare names (``nginx.conf.j2``) resolve to the
    packaged ``templates/`` directory; anything with a slash or ending
    ``.j2`` that exists on disk is read verbatim."""
    p = Path(name_or_path)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    pkg_templates = resources.files("config_generator").joinpath("templates")
    for candidate in (name_or_path, name_or_path + ".j2"):
        tpl_file = pkg_templates.joinpath(candidate)
        try:
            if tpl_file.is_file():
                return tpl_file.read_text(encoding="utf-8")
        except (FileNotFoundError, NotADirectoryError):
            pass
    raise FileNotFoundError(f"template not found: {name_or_path!r}")


def render(template_text: str, params: dict) -> str:
    env = jinja2.Environment(
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        autoescape=False,
    )
    tpl = env.from_string(template_text)
    return tpl.render(**params)


def validate(text: str, fmt: OutputFormat) -> None:
    """Parse the rendered text in its target format — raise on failure."""
    if fmt == "yaml":
        yaml.safe_load(text)
    elif fmt == "json":
        json.loads(text)
    elif fmt == "toml":
        import tomllib
        tomllib.loads(text)
    elif fmt == "ini":
        cp = configparser.ConfigParser()
        cp.read_string(text)
    elif fmt == "env":
        for ln, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            if "=" not in s:
                raise ValueError(f"env line {ln}: missing '=': {s!r}")
    elif fmt == "text":
        return
    else:
        raise ValueError(f"unknown output format: {fmt!r}")
