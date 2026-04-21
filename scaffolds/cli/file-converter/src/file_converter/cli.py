"""Click entrypoint for file-converter."""
from __future__ import annotations

import sys

import click

from . import formats


@click.command()
@click.version_option()
@click.option("-i", "--input", "input_path", default="-", show_default=True,
              help="Input path, or '-' for stdin.")
@click.option("-o", "--output", "output_path", default="-", show_default=True,
              help="Output path, or '-' for stdout.")
@click.option("--from", "src_fmt", default="",
              help=f"Input format ({'/'.join(sorted(formats.REGISTRY))}). "
                   "Default: infer from --input extension.")
@click.option("--to", "dst_fmt", default="",
              help=f"Output format ({'/'.join(sorted(formats.REGISTRY))}). "
                   "Default: infer from --output extension.")
def main(input_path: str, output_path: str, src_fmt: str, dst_fmt: str) -> None:
    """Convert tabular data between csv/tsv/jsonl/json/yaml."""
    if not src_fmt:
        if input_path == "-":
            raise click.UsageError("--from required when reading from stdin")
        src_fmt = formats.infer(input_path)
        if not src_fmt:
            raise click.UsageError(f"can't infer input format from {input_path!r}; pass --from")
    if src_fmt not in formats.REGISTRY:
        raise click.BadParameter(f"--from {src_fmt!r} not one of {sorted(formats.REGISTRY)}")

    if not dst_fmt:
        if output_path == "-":
            raise click.UsageError("--to required when writing to stdout")
        dst_fmt = formats.infer(output_path)
        if not dst_fmt:
            raise click.UsageError(f"can't infer output format from {output_path!r}; pass --to")
    if dst_fmt not in formats.REGISTRY:
        raise click.BadParameter(f"--to {dst_fmt!r} not one of {sorted(formats.REGISTRY)}")

    reader, _ = formats.REGISTRY[src_fmt]
    _, writer = formats.REGISTRY[dst_fmt]

    if input_path == "-":
        rows = reader(sys.stdin)
    else:
        with open(input_path, "r", encoding="utf-8", newline="") as fh:
            rows = list(reader(fh))

    if output_path == "-":
        writer(rows, sys.stdout)
    else:
        with open(output_path, "w", encoding="utf-8", newline="") as fh:
            writer(rows, fh)


if __name__ == "__main__":
    sys.exit(main())
