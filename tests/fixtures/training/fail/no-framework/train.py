"""Claims to train but imports no ML framework."""
import argparse
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()

    for epoch in range(args.epochs):
        print(f"epoch {epoch}")
    # No model. No framework. No checkpoint. Just a print loop.


if __name__ == "__main__":
    main()
