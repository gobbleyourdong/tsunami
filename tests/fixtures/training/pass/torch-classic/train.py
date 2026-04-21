"""Classic PyTorch training loop — manual optimizer step, torch.save."""
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--output", default="./checkpoints")
    args = parser.parse_args()

    model = nn.Linear(10, 2)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    for epoch in range(args.epochs):
        for batch_x, batch_y in []:
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        print(f"epoch {epoch} done")

    torch.save(model.state_dict(), f"{args.output}/model.pt")


if __name__ == "__main__":
    main()
