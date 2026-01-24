"""
Query Engine - Unified interface for Malloy and SQL queries with caching.

Eksempel:
    from library.engine import execute_malloy, execute_coverage

    # Kjør Malloy-query
    df = execute_malloy("fiber_fylke")

    # Kjør med filtre
    df = execute_malloy("fiber_fylke", filters={"fylke": "OSLO"})

    # Høynivå convenience
    df = execute_coverage(teknologi="fiber", populasjon="spredtbygd")
"""

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Optional

import polars as pl

from library.cache import QueryCache, get_db
from library.error_handler import with_error_learning

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
MODEL_PATH = PROJECT_ROOT / "model" / "ekom.malloy"
CACHE_DIR = PROJECT_ROOT / "lib" / "cache"

# Available Malloy queries (parsed from ekom.malloy)
MALLOY_QUERIES = {
    # Fiber
    "fiber_fylke": {
        "source": "dekning_fiber",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_fiber", "antall_husstander", "fiber_pct"],
        "description": "Fiberdekning per fylke",
    },
    "fiber_spredtbygd": {
        "source": "dekning_fiber",
        "view": "spredtbygd_fylke",
        "columns": ["fylke_navn", "hus_fiber", "antall_husstander", "fiber_pct"],
        "description": "Fiberdekning i spredtbygd per fylke",
    },
    "fiber_tettsted": {
        "source": "dekning_fiber",
        "view": "tettsted_fylke",
        "columns": ["fylke_navn", "hus_fiber", "antall_husstander", "fiber_pct"],
        "description": "Fiberdekning i tettsted per fylke",
    },
    "fiber_hc_fylke": {
        "source": "dekning_fiber_hc",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_fiber_hc", "antall_husstander", "fiber_hc_pct"],
        "description": "Fiber Homes Connected per fylke",
    },
    "hoyhastighet_fylke": {
        "source": "dekning_hoyhast",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_hoyhast", "antall_husstander", "hoyhast_pct"],
        "description": "Høyhastighet (>=100 Mbit) per fylke",
    },
    # Mobildekning
    "g5_fylke": {
        "source": "dekning_5g",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_5g", "antall_husstander", "g5_pct"],
        "description": "5G-dekning per fylke",
    },
    "g5_spredtbygd": {
        "source": "dekning_5g",
        "view": "spredtbygd_fylke",
        "columns": ["fylke_navn", "hus_5g", "antall_husstander", "g5_pct"],
        "description": "5G-dekning i spredtbygd per fylke",
    },
    "g4_fylke": {
        "source": "dekning_4g",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_4g", "antall_husstander", "g4_pct"],
        "description": "4G-dekning per fylke",
    },
    # FTB
    "ftb_fylke": {
        "source": "dekning_ftb",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_ftb", "antall_husstander", "ftb_pct"],
        "description": "FTB-dekning per fylke",
    },
    # Konkurranse
    "konkurranse_fylke": {
        "source": "dekning_konkurranse",
        "view": "per_fylke",
        "columns": ["fylke_navn", "hus_1_tilb", "hus_2_tilb", "hus_3_tilb", "antall_husstander"],
        "description": "Fibertilbydere per fylke",
    },
}


class MalloyEngine:
    """
    Singleton for Malloy Runtime med connection pooling.

    Gjenbruker Runtime og DuckDB connection for raskere kjøring.
    """

    _instance: Optional["MalloyEngine"] = None
    _runtime = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _ensure_initialized(self):
        """Lazy initialization av Malloy Runtime."""
        if self._initialized:
            return

        try:
            from malloy import Runtime
            from malloy.data.duckdb import DuckDbConnection

            self._runtime_class = Runtime
            self._connection_class = DuckDbConnection
            self._initialized = True
        except ImportError:
            raise ImportError(
                "Malloy er ikke installert. Kjør: pip install malloy"
            )

    async def _run_query_async(self, query_name: str) -> pl.DataFrame:
        """Kjør Malloy-query asynkront."""
        self._ensure_initialized()

        with self._runtime_class() as runtime:
            runtime.add_connection(
                self._connection_class(home_dir=str(PROJECT_ROOT))
            )
            runtime.load_file(str(MODEL_PATH))
            result = await runtime.run(named_query=query_name)
            return pl.from_pandas(result.to_dataframe())

    def run_query(self, query_name: str) -> pl.DataFrame:
        """Kjør Malloy-query synkront."""
        return asyncio.run(self._run_query_async(query_name))


# Singleton instance
_malloy_engine: Optional[MalloyEngine] = None
_query_cache: Optional[QueryCache] = None
_compiled_cache: dict[str, str] = {}  # In-memory cache for compiled SQL


def _get_malloy_engine() -> MalloyEngine:
    """Hent global MalloyEngine instance."""
    global _malloy_engine
    if _malloy_engine is None:
        _malloy_engine = MalloyEngine()
    return _malloy_engine


def _get_query_cache() -> QueryCache:
    """Hent global QueryCache instance med 1 times TTL."""
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache(
            cache_dir=CACHE_DIR,
            ttl_seconds=3600,  # 1 time
            max_cache_size_mb=100,
        )
    return _query_cache


def _make_cache_key(query_name: str, filters: Optional[dict] = None) -> str:
    """Generer cache-nøkkel fra query + filters."""
    data = {"query": query_name, "filters": filters or {}}
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def get_available_queries() -> list[str]:
    """
    List alle tilgjengelige Malloy-queries.

    Returns:
        Liste med query-navn
    """
    return list(MALLOY_QUERIES.keys())


def get_query_info(query_name: str) -> Optional[dict]:
    """
    Hent metadata for en query.

    Returns:
        Dict med columns, description, source, view
    """
    return MALLOY_QUERIES.get(query_name)


def execute_malloy(
    query_name: str,
    filters: Optional[dict] = None,
    output: Literal["dataframe", "json", "csv"] = "dataframe",
    force_refresh: bool = False,
) -> pl.DataFrame | str:
    """
    Kjør en navngitt Malloy-query.

    Args:
        query_name: Navn på query (f.eks. "fiber_fylke")
        filters: Dict med post-execution filtre (f.eks. {"fylke": "OSLO"})
        output: Returformat ("dataframe", "json", "csv")
        force_refresh: Ignorer cache og kjør ny query

    Returns:
        DataFrame eller serialisert string

    Raises:
        ValueError: Hvis query_name ikke finnes
    """
    if query_name not in MALLOY_QUERIES:
        available = ", ".join(MALLOY_QUERIES.keys())
        raise ValueError(
            f"Ukjent query: '{query_name}'. Tilgjengelige: {available}"
        )

    cache = _get_query_cache()
    cache_key = _make_cache_key(query_name, filters)

    # Sjekk cache (uten filtre først, så appliserer vi filtre etterpå)
    base_cache_key = _make_cache_key(query_name, None)

    if not force_refresh:
        # Prøv å hente fra cache
        # Vi cacher base-resultatet (uten filtre) for gjenbruk
        cached = cache.get(f"malloy_{base_cache_key}")
        if cached is not None:
            df = cached
        else:
            df = None
    else:
        df = None

    # Hvis ikke i cache, kjør Malloy
    if df is None:
        engine = _get_malloy_engine()
        df = engine.run_query(query_name)

        # Cache base-resultatet
        cache.set(f"malloy_{base_cache_key}", df)

    # Appliser post-execution filtre
    if filters:
        for col, value in filters.items():
            if col in df.columns:
                if isinstance(value, list):
                    df = df.filter(pl.col(col).is_in(value))
                else:
                    df = df.filter(pl.col(col) == value)

    # Konverter til ønsket format
    if output == "json":
        return df.write_json()
    elif output == "csv":
        return df.write_csv()
    else:
        return df


@with_error_learning
def execute_sql_cached(
    sql: str,
    force_refresh: bool = False,
) -> pl.DataFrame:
    """
    Kjør SQL med caching og auto-learning feilhåndtering.

    Ved feil registreres korreksjonen automatisk til knowledge base
    slik at samme feil ikke gjentas (CLAUDE.md regel 9).

    Args:
        sql: SQL-query
        force_refresh: Ignorer cache og kjør ny query

    Returns:
        DataFrame med resultat

    Raises:
        RuntimeError: Ved feil, med løsningsforslag hvis tilgjengelig
    """
    cache = _get_query_cache()
    db = get_db()

    return cache.get_or_execute(sql, db.execute, force_refresh=force_refresh)


def invalidate_cache(query_name: Optional[str] = None):
    """
    Invalidér cache.

    Args:
        query_name: Spesifikk query å invalidere, eller None for all cache
    """
    cache = _get_query_cache()

    if query_name:
        cache_key = _make_cache_key(query_name, None)
        cache.invalidate(f"malloy_{cache_key}")
    else:
        cache.invalidate()


def execute_coverage(
    teknologi: str | list[str] = "fiber",
    populasjon: Optional[Literal["tettsted", "spredtbygd"]] = None,
    group_by: Literal["fylke", "kommune", "nasjonal"] = "fylke",
    year: int = 2024,
) -> pl.DataFrame:
    """
    Høynivå convenience for dekningsspørringer.

    Auto-ruter til Malloy hvis mulig, ellers fallback til SQL.

    Args:
        teknologi: Teknologi(er) å filtrere på
        populasjon: "tettsted", "spredtbygd", eller None for begge
        group_by: Aggregeringsnivå
        year: Årstall

    Returns:
        DataFrame med dekning
    """
    # Normaliser teknologi til liste
    if isinstance(teknologi, str):
        teknologi = [teknologi]

    # Prøv å mappe til Malloy-query
    if teknologi == ["fiber"] and year == 2024 and group_by == "fylke":
        if populasjon == "spredtbygd":
            return execute_malloy("fiber_spredtbygd")
        elif populasjon == "tettsted":
            return execute_malloy("fiber_tettsted")
        elif populasjon is None:
            return execute_malloy("fiber_fylke")

    # Fallback til CoverageQuery
    from library.query_builder import CoverageQuery

    query = CoverageQuery(
        year=year,
        teknologi=teknologi,
        populasjon=populasjon,
        group_by=group_by,
    )
    return query.execute()


def get_cache_stats() -> dict:
    """Hent cache-statistikk."""
    cache = _get_query_cache()
    return cache.get_stats()
