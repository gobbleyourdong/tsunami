#!/usr/bin/env python3
"""Minimal argparse CLI — just enough to pass the probe."""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="minimal",
        description="A minimal CLI that proves invokability.",
    )
    parser.add_argument("--name", default="world", help="who to greet")
    args = parser.parse_args()
    print(f"Hello, {args.name}!")


if __name__ == "__main__":
    main()
