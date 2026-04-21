"""Click entrypoint.

Default verb is ``process`` — read, chain operators, write. Other verbs
(``count``, ``group``) are convenience shortcuts for the most common
terminal operators. Each verb is pipe-friendly: input defaults to
stdin, output defaults to stdout.
"""
from __future__ import annotations

import sys

import click

from . import operators as ops
from .io import read_records, write_records


_IN = click.option("-i", "--input", "input_path", default="-", show_default=True,
                   help="Input file path, or '-' for stdin.")
_OUT = click.option("-o", "--output", "output_path", default="-", show_default=True,
                    help="Output file path, or '-' for stdout.")
_IFMT = click.option("--input-format", type=click.Choice(["auto", "jsonl", "json", "csv"]),
                     default="auto", show_default=True)
_OFMT = click.option("--output-format", type=click.Choice(["jsonl", "json", "csv", "plain"]),
                     default="jsonl", show_default=True)


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def main(ctx: click.Context) -> None:
    """data-processor — filter / map / count record streams."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command("process")
@_IN
@_OUT
@_IFMT
@_OFMT
@click.option("--filter", "filters", multiple=True,
              help="Predicate expr like 'status==active' or 'score>=0.8'. Repeatable.")
@click.option("--select", "select_fields", default="",
              help="Comma-separated fields to keep (dotted paths OK).")
@click.option("--rename", "renames", multiple=True,
              help="old=new rename spec. Repeatable.")
def process_cmd(input_path: str, output_path: str, input_format: str, output_format: str,
                filters: tuple[str, ...], select_fields: str, renames: tuple[str, ...]) -> None:
    """Filter, project, and rename fields in a record stream."""
    records = read_records(input_path, input_format)
    for f in filters:
        records = ops.filter_op(records, ops.parse_predicate(f))
    if select_fields:
        records = ops.project(records, [f.strip() for f in select_fields.split(",") if f.strip()])
    if renames:
        pairs: dict[str, str] = {}
        for spec in renames:
            if "=" not in spec:
                raise click.BadParameter(f"--rename expects old=new, got {spec!r}")
            old, new = spec.split("=", 1)
            pairs[old.strip()] = new.strip()
        records = ops.map_rename(records, pairs)
    n = write_records(records, output_path, output_format)
    click.echo(f"wrote {n} records", err=True)


@main.command("count")
@_IN
@_IFMT
@click.option("--group-by", "group_by", default="",
              help="Field to group by. Empty = total count.")
def count_cmd(input_path: str, input_format: str, group_by: str) -> None:
    """Count records, optionally grouped by a field."""
    records = read_records(input_path, input_format)
    if group_by:
        rows = ops.group_count(records, group_by)
    else:
        rows = ops.count(records)
    write_records(rows, "-", "jsonl")


if __name__ == "__main__":
    sys.exit(main())
