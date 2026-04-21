"""Click entrypoint for config-generator."""
from __future__ import annotations

import sys

import click

from . import params as _params
from . import render as _render


_FORMATS = ("yaml", "json", "toml", "ini", "env", "text")


@click.command()
@click.version_option()
@click.argument("template", type=str)
@click.option("-o", "--output", "output_path", default="-", show_default=True,
              help="Output path, or '-' for stdout.")
@click.option("--format", "fmt", type=click.Choice(_FORMATS),
              default="text", show_default=True,
              help="Target format — rendered output is parsed to validate shape.")
@click.option("--params", "params_path", default="",
              help="YAML/JSON/TOML file with parameter values.")
@click.option("--env-prefix", "env_prefix", default="",
              help="Pick up env vars with this prefix; strips prefix + lowercases.")
@click.option("--set", "sets", multiple=True,
              help="Inline key=value override. Dotted keys descend (db.host=...). Repeatable.")
def main(template: str, output_path: str, fmt: str, params_path: str,
         env_prefix: str, sets: tuple[str, ...]) -> None:
    """Render TEMPLATE (a bundled name like 'nginx.conf.j2' or a path)
    using the merged parameter set, validate the result, and write it."""
    sources: list[dict] = []
    if params_path:
        sources.append(_params.load_param_file(params_path))
    if env_prefix:
        sources.append(_params.load_env_prefix(env_prefix))
    merged = _params.merge(*sources) if sources else {}
    if sets:
        merged = _params.apply_sets(merged, list(sets))

    text = _render.load_template(template)
    rendered = _render.render(text, merged)

    try:
        _render.validate(rendered, fmt)
    except Exception as exc:
        raise click.ClickException(
            f"rendered output failed {fmt!r} validation: {exc}"
        ) from exc

    if output_path == "-":
        sys.stdout.write(rendered)
    else:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write(rendered)


if __name__ == "__main__":
    sys.exit(main())
