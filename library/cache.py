"""
Caching-lag for spørringer og DuckDB views.

Nivå 1: DuckDB views (registrer parquet som views ved oppstart)
Nivå 2: Query result cache (hash SQL -> parquet)
Nivå 3: Precomputed aggregates (vanlige aggregeringer)

Eksempel:
    from library.cache import DuckDBCache, QueryCache

    # DuckDB med registrerte views
    db = DuckDBCache()
    result = db.execute("SELECT * FROM adr_2024 WHERE fylke = 'OSLO'")

    # Query caching
    cache = QueryCache()
    result = cache.get_or_execute(sql, db.execute)
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

import duckdb
import polars as pl

# Paths
LIB_DIR = Path(__file__).parent.parent / "lib"
CACHE_DIR = LIB_DIR / "cache"


class DuckDBCache:
    """
    DuckDB connection med pre-registrerte views.

    Unngår gjentatt fil-parsing ved å bruke views.
    """

    def __init__(self):
        self.conn = duckdb.connect(":memory:")
        self._register_views()

    def _register_views(self):
        """Registrer parquet-filer som views."""
        # Årlige filer
        for year in [2022, 2023, 2024]:
            year_dir = LIB_DIR / str(year)
            if not year_dir.exists():
                continue

            for dataset in ["adr", "fbb", "ab"]:
                path = year_dir / f"{dataset}.parquet"
                if path.exists():
                    view_name = f"{dataset}_{year}"
                    self.conn.execute(f"""
                        CREATE OR REPLACE VIEW {view_name} AS
                        SELECT * FROM read_parquet('{path}')
                    """)

            # mob kun fra 2023
            if year >= 2023:
                mob_path = year_dir / "mob.parquet"
                if mob_path.exists():
                    self.conn.execute(f"""
                        CREATE OR REPLACE VIEW mob_{year} AS
                        SELECT * FROM read_parquet('{mob_path}')
                    """)

        # Globale filer (symlinks til siste år)
        for dataset in ["adr", "fbb", "mob", "ab"]:
            path = LIB_DIR / f"{dataset}.parquet"
            if path.exists():
                self.conn.execute(f"""
                    CREATE OR REPLACE VIEW {dataset} AS
                    SELECT * FROM read_parquet('{path}')
                """)

        # Konsoliderte historiske filer
        for hist_file in ["dekning_tek", "dekning_hast", "ekom"]:
            path = LIB_DIR / f"{hist_file}.parquet"
            if path.exists():
                self.conn.execute(f"""
                    CREATE OR REPLACE VIEW {hist_file} AS
                    SELECT * FROM read_parquet('{path}')
                """)

    def execute(self, sql: str) -> pl.DataFrame:
        """Kjør SQL og returner Polars DataFrame."""
        result = self.conn.execute(sql).fetchdf()
        return pl.from_pandas(result)

    def execute_raw(self, sql: str):
        """Kjør SQL og returner DuckDB result."""
        return self.conn.execute(sql)

    def get_view_names(self) -> list[str]:
        """List alle registrerte views."""
        result = self.conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_type = 'VIEW'
            ORDER BY table_name
        """).fetchall()
        return [r[0] for r in result]


class QueryCache:
    """
    Cache for SQL query-resultater.

    Lagrer resultater som parquet-filer basert på SQL-hash.
    """

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        ttl_seconds: int = 86400,  # 24 timer
        max_cache_size_mb: int = 100,
    ):
        self.cache_dir = cache_dir or CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds
        self.max_size = max_cache_size_mb * 1024 * 1024
        self._index_path = self.cache_dir / "index.json"
        self._load_index()

    def _load_index(self):
        """Last cache-indeks fra disk."""
        if self._index_path.exists():
            with open(self._index_path) as f:
                self._index = json.load(f)
        else:
            self._index = {}

    def _save_index(self):
        """Lagre cache-indeks til disk."""
        with open(self._index_path, "w") as f:
            json.dump(self._index, f)

    def _hash_sql(self, sql: str) -> str:
        """Generer hash for SQL query."""
        # Normaliser whitespace
        normalized = " ".join(sql.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def _get_cache_path(self, sql_hash: str) -> Path:
        """Hent filsti for cache-entry."""
        return self.cache_dir / f"{sql_hash}.parquet"

    def _is_valid(self, sql_hash: str) -> bool:
        """Sjekk om cache-entry er gyldig (ikke utløpt)."""
        if sql_hash not in self._index:
            return False

        entry = self._index[sql_hash]
        age = time.time() - entry["timestamp"]
        return age < self.ttl

    def get(self, sql: str) -> Optional[pl.DataFrame]:
        """Hent cachet resultat hvis tilgjengelig."""
        sql_hash = self._hash_sql(sql)

        if not self._is_valid(sql_hash):
            return None

        cache_path = self._get_cache_path(sql_hash)
        if not cache_path.exists():
            return None

        return pl.read_parquet(cache_path)

    def set(self, sql: str, result: pl.DataFrame):
        """Lagre resultat i cache."""
        sql_hash = self._hash_sql(sql)
        cache_path = self._get_cache_path(sql_hash)

        # Lagre parquet
        result.write_parquet(cache_path)

        # Oppdater indeks
        self._index[sql_hash] = {
            "timestamp": time.time(),
            "sql_preview": sql[:100],
            "rows": result.height,
            "size": cache_path.stat().st_size,
        }
        self._save_index()

        # Rydd opp hvis cache er for stor
        self._cleanup_if_needed()

    def get_or_execute(
        self,
        sql: str,
        executor: Callable[[str], pl.DataFrame],
        force_refresh: bool = False,
    ) -> pl.DataFrame:
        """
        Hent fra cache eller kjør query.

        Args:
            sql: SQL query
            executor: Funksjon som kjører SQL og returnerer DataFrame
            force_refresh: Ignorer cache og kjør ny query
        """
        if not force_refresh:
            cached = self.get(sql)
            if cached is not None:
                return cached

        result = executor(sql)
        self.set(sql, result)
        return result

    def _cleanup_if_needed(self):
        """Rydd opp gamle cache-entries hvis størrelsen overstiger grensen."""
        total_size = sum(
            entry.get("size", 0) for entry in self._index.values()
        )

        if total_size <= self.max_size:
            return

        # Sorter etter timestamp (eldste først)
        sorted_entries = sorted(
            self._index.items(),
            key=lambda x: x[1]["timestamp"]
        )

        # Slett til vi er under grensen
        for sql_hash, entry in sorted_entries:
            if total_size <= self.max_size * 0.8:  # 80% av max
                break

            cache_path = self._get_cache_path(sql_hash)
            if cache_path.exists():
                total_size -= entry.get("size", 0)
                cache_path.unlink()

            del self._index[sql_hash]

        self._save_index()

    def invalidate(self, sql: Optional[str] = None):
        """
        Invalidér cache.

        Args:
            sql: Spesifikk SQL å invalidere, eller None for all cache
        """
        if sql:
            sql_hash = self._hash_sql(sql)
            cache_path = self._get_cache_path(sql_hash)
            if cache_path.exists():
                cache_path.unlink()
            if sql_hash in self._index:
                del self._index[sql_hash]
        else:
            # Slett all cache
            for sql_hash in list(self._index.keys()):
                cache_path = self._get_cache_path(sql_hash)
                if cache_path.exists():
                    cache_path.unlink()
            self._index = {}

        self._save_index()

    def get_stats(self) -> dict:
        """Hent cache-statistikk."""
        total_size = sum(entry.get("size", 0) for entry in self._index.values())
        total_rows = sum(entry.get("rows", 0) for entry in self._index.values())

        return {
            "entries": len(self._index),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "total_rows": total_rows,
            "max_size_mb": self.max_size / 1024 / 1024,
        }


class PrecomputedAggregates:
    """
    Håndterer precomputed aggregater for vanlige spørringer.

    Kjør nattlig script for å regenerere.
    """

    AGGREGATES = {
        "fbb_tek_fylke": """
            SELECT
                fylke,
                tek,
                SUM(hus) as hus_dekning,
                COUNT(DISTINCT adrid) as adresser
            FROM adr a
            JOIN fbb f ON a.adrid = f.adrid
            GROUP BY fylke, tek
        """,
        "fbb_hast_fylke": """
            SELECT
                fylke,
                CASE
                    WHEN ned >= 1000000 THEN '1000+'
                    WHEN ned >= 500000 THEN '500-999'
                    WHEN ned >= 100000 THEN '100-499'
                    WHEN ned >= 30000 THEN '30-99'
                    ELSE '<30'
                END as hastighet_klasse,
                SUM(hus) as hus_dekning
            FROM adr a
            LEFT JOIN (
                SELECT adrid, MAX(ned) as ned
                FROM fbb GROUP BY adrid
            ) f ON a.adrid = f.adrid
            GROUP BY fylke, hastighet_klasse
        """,
        "husstander_geo": """
            SELECT
                fylke,
                SUM(hus) as totalt_hus,
                SUM(CASE WHEN ertett THEN hus ELSE 0 END) as hus_tettsted,
                SUM(CASE WHEN NOT ertett THEN hus ELSE 0 END) as hus_spredtbygd
            FROM adr
            GROUP BY fylke
        """,
    }

    def __init__(self, db: Optional[DuckDBCache] = None):
        self.db = db or DuckDBCache()
        self.cache_dir = CACHE_DIR / "precomputed"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, name: str) -> pl.DataFrame:
        """Generer et precomputed aggregat."""
        if name not in self.AGGREGATES:
            raise ValueError(f"Ukjent aggregat: {name}")

        sql = self.AGGREGATES[name]
        result = self.db.execute(sql)

        # Lagre
        path = self.cache_dir / f"{name}.parquet"
        result.write_parquet(path)

        return result

    def generate_all(self):
        """Generer alle precomputed aggregater."""
        for name in self.AGGREGATES:
            print(f"Genererer {name}...")
            self.generate(name)
        print("Ferdig!")

    def get(self, name: str) -> Optional[pl.DataFrame]:
        """Hent precomputed aggregat."""
        path = self.cache_dir / f"{name}.parquet"
        if path.exists():
            return pl.read_parquet(path)
        return None


# Singleton for enkel tilgang
_db_cache: Optional[DuckDBCache] = None


def get_db() -> DuckDBCache:
    """Hent global DuckDB cache instance."""
    global _db_cache
    if _db_cache is None:
        _db_cache = DuckDBCache()
    return _db_cache


def execute_sql(sql: str) -> pl.DataFrame:
    """Convenience-funksjon for å kjøre SQL."""
    return get_db().execute(sql)
