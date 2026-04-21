"""Click entrypoint."""
from __future__ import annotations

import logging
import sys

import click

from .config import load_config


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def main(ctx: click.Context) -> None:
    """LoRA fine-tune recipe — run with a YAML config."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command("validate")
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False))
def validate_cmd(config_path: str) -> None:
    """Parse + typecheck a config file. Does not load model / data."""
    cfg = load_config(config_path)
    click.echo(f"ok — model={cfg.model.name} r={cfg.lora.r} "
               f"alpha={cfg.lora.alpha} lr={cfg.train.lr} "
               f"epochs={cfg.train.epochs}")


@main.command("train")
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False))
def train_cmd(config_path: str) -> None:
    """Run the training recipe. Requires torch/transformers/peft."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = load_config(config_path)
    from .recipe import train
    train(cfg)


if __name__ == "__main__":
    sys.exit(main())
