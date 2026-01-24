#!/usr/bin/env python3
"""Demo: Malloy som semantisk lag for ekom-orakel."""
import asyncio
from pathlib import Path

from malloy import Runtime
from malloy.data.duckdb import DuckDbConnection
import polars as pl

PROJECT_ROOT = Path(__file__).parent
MODEL_PATH = PROJECT_ROOT / "model" / "ekom.malloy"


def run_named_query(query_name: str) -> pl.DataFrame:
    """Kjør en navngitt Malloy-query og returner som Polars DataFrame."""

    async def _run():
        with Runtime() as runtime:
            runtime.add_connection(DuckDbConnection(home_dir=str(PROJECT_ROOT)))
            runtime.load_file(str(MODEL_PATH))
            result = await runtime.run(named_query=query_name)
            return pl.from_pandas(result.to_dataframe())

    return asyncio.run(_run())


def fiber_per_fylke() -> pl.DataFrame:
    """Fiberdekning per fylke fra Malloy."""
    return run_named_query("fiber_fylke")


def fiber_spredtbygd() -> pl.DataFrame:
    """Fiberdekning i spredtbygd per fylke fra Malloy."""
    return run_named_query("fiber_spredtbygd")


def hoyhastighet_per_fylke() -> pl.DataFrame:
    """Høyhastighetsdekning (>=100 Mbit) per fylke fra Malloy."""
    return run_named_query("hoyhastighet_fylke")


def main():
    """Demonstrer Malloy som semantisk lag."""
    print("=" * 60)
    print("MALLOY SEMANTISK LAG - DEMO")
    print("=" * 60)

    print("\n1. Fiberdekning per fylke:")
    print("-" * 40)
    df = fiber_per_fylke()
    print(df)

    print("\n2. Fiberdekning i spredtbygd per fylke:")
    print("-" * 40)
    df_spredtbygd = fiber_spredtbygd()
    print(df_spredtbygd)

    print("\n3. Høyhastighetsdekning (>=100 Mbit) per fylke:")
    print("-" * 40)
    df_hoy = hoyhastighet_per_fylke()
    print(df_hoy)


if __name__ == "__main__":
    main()
