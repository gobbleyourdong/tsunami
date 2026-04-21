"""Pipeline imports pandas + writes output, but never reads a source."""
import pandas as pd


def main():
    df = pd.DataFrame({"a": [1, 2, 3]})  # hardcoded, not a source
    df.to_parquet("out.parquet")


if __name__ == "__main__":
    main()
