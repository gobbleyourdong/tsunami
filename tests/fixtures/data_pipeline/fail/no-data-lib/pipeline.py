"""Pipeline file with no data library imported."""
import argparse
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    args = parser.parse_args()
    with open(args.input) as f:
        for line in f:
            print(line.strip())


if __name__ == "__main__":
    main()
