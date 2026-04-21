"""Typical Python CLI wired via pyproject.toml [project.scripts]."""
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="typical",
        description="Process a file and emit results.",
    )
    parser.add_argument("input", help="input file path")
    parser.add_argument("-o", "--output", help="output file path")
    parser.add_argument("--verbose", action="store_true")
    parser.parse_args()


if __name__ == "__main__":
    main()
