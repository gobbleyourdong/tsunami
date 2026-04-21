"""DuckDB ETL — query source, aggregate, write to parquet."""
import duckdb


def main():
    con = duckdb.connect()
    df = con.execute("""
        SELECT date_trunc('day', ts) AS day, count(*) AS events
        FROM read_parquet('events/*.parquet')
        GROUP BY 1
    """).df()
    df.to_parquet("out/daily.parquet")


if __name__ == "__main__":
    main()
