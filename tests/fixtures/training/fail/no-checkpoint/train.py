"""Trains forever without saving — classic "run is lost on exit" bug."""
import argparse
import torch
import torch.nn as nn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    model = nn.Linear(10, 2)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(args.epochs):
        for batch in []:
            optimizer.zero_grad()
            loss = model(batch).sum()
            loss.backward()
            optimizer.step()

    print("done")
    # No torch.save, no save_pretrained, no save_model — run lost.


if __name__ == "__main__":
    main()
