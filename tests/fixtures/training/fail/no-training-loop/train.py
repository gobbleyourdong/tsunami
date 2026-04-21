"""Imports torch + transformers but has no training loop — just model init + save.

Real-world failure mode: a "fine-tuning recipe" that actually just loads
a pretrained model and saves it back unchanged. Probe should catch the
absence of an actual training step.
"""
import argparse
import torch
from transformers import AutoModelForSequenceClassification


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", default="bert-base-uncased")
    parser.add_argument("--output", default="./ckpts")
    args = parser.parse_args()

    model = AutoModelForSequenceClassification.from_pretrained(args.model_name)
    model.save_pretrained(args.output)
    print("done — no training happened")


if __name__ == "__main__":
    main()
