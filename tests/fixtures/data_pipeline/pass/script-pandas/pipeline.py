"""Classic pandas ETL — read CSV, transform, write parquet."""
import argparse
import pandas as pd


def extract(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna()
    df["total"] = df["price"] * df["quantity"]
    return df.groupby("customer").agg({"total": "sum"}).reset_index()


def load(df: pd.DataFrame, out: str) -> None:
    df.to_parquet(out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    df = extract(args.input)
    df = transform(df)
    load(df, args.output)


if __name__ == "__main__":
    main()
