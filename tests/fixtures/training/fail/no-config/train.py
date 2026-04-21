"""Training loop with hardcoded hyperparams — no argparse, no config file."""
import torch
import torch.nn as nn

EPOCHS = 3
LR = 1e-3


def main():
    model = nn.Linear(10, 2)
    optimizer = torch.optim.Adam(model.parameters(), lr=LR)

    for epoch in range(EPOCHS):
        for batch in []:
            loss = model(batch).sum()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    torch.save(model.state_dict(), "model.pt")


if __name__ == "__main__":
    main()
