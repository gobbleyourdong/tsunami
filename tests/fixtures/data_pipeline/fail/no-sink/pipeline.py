"""Pipeline reads + transforms but never writes — result lost on exit."""
import pandas as pd


def main():
    df = pd.read_csv("input.csv")
    df = df.dropna()
    df["total"] = df["price"] * df["quantity"]
    print(df.head())  # printing is not a sink


if __name__ == "__main__":
    main()
