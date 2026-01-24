"""
Library-pakke for bredbåndsuttrekk.

Bruk:
    from library import load_data, get_script_paths, filter_hastighet, validate_and_save

    # Nytt: Knowledge base
    from library import KnowledgeBase, QueryMatcher

    # Nytt: Query Builder
    from library import CoverageQuery, quick_coverage

    # Nytt: Cache
    from library import get_db, execute_sql

    # Nytt: Validering
    from library import validate_pre_execution, validate_result
"""

from library.loader import (
    DATA_DIR,
    UTTREKK_DIR,
    get_script_paths,
    get_today_dir,
    load_data,
    load_dataset,
)
from library.filters import (
    filter_egen,
    filter_hastighet,
    filter_hc,
    filter_populasjon,
    filter_teknologi,
    filter_tilbyder,
)
from library.validation import (
    add_national_aggregate,
    validate_and_save,
    validate_extraction,
)

# Nye moduler
from library.fylker import (
    FYLKER_2024 as FYLKER,
    FYLKER_2020,
    FYLKER_2024,
    get_fylker,
    normalize_fylke,
    map_fylke_2020_to_2024,
    map_fylke_2024_to_2020,
    is_same_region,
)
from library.knowledge import (
    KnowledgeBase,
    Query,
    Correction,
    SessionTracker,
    get_session,
)
from library.query_matcher import (
    QueryMatcher,
    MatchResult,
    extract_keywords,
    DOMAIN_SYNONYMS,
)
from library.validators import (
    SQLValidator,
    ResultValidator,
    ValidationIssue,
    validate_pre_execution,
    validate_result,
)
from library.cache import (
    DuckDBCache,
    QueryCache,
    PrecomputedAggregates,
    get_db,
    execute_sql,
)
from library.query_builder import (
    CoverageQuery,
    CompetitionQuery,
    HistoricalQuery,
    quick_coverage,
)
from library.ekom_query import (
    EkomQuery,
    quick_ekom,
    MOBIL_FYLKER,
)
from library.doc_checker import (
    DocumentChecker,
    NumberFinding,
    DataSourceMatch,
    LearnedPattern,
    parse_norwegian_number,
    find_document,
)
from library.engine import (
    execute_malloy,
    execute_sql_cached,
    execute_coverage,
    execute_ekom,
    get_available_queries,
    get_query_info,
    invalidate_cache,
    get_cache_stats,
    MALLOY_QUERIES,
)
from library.error_handler import (
    with_error_learning,
    auto_learn_from_error,
)

__all__ = [
    # Loader
    "DATA_DIR",
    "UTTREKK_DIR",
    "load_data",
    "load_dataset",
    "get_script_paths",
    "get_today_dir",
    # Filters
    "filter_hastighet",
    "filter_teknologi",
    "filter_tilbyder",
    "filter_populasjon",
    "filter_hc",
    "filter_egen",
    # Legacy validation
    "add_national_aggregate",
    "validate_extraction",
    "validate_and_save",
    # Fylker
    "FYLKER",
    "FYLKER_2020",
    "FYLKER_2024",
    "get_fylker",
    "normalize_fylke",
    "map_fylke_2020_to_2024",
    "map_fylke_2024_to_2020",
    "is_same_region",
    # Knowledge Base
    "KnowledgeBase",
    "Query",
    "Correction",
    "SessionTracker",
    "get_session",
    # Query Matcher
    "QueryMatcher",
    "MatchResult",
    "extract_keywords",
    "DOMAIN_SYNONYMS",
    # Validators
    "SQLValidator",
    "ResultValidator",
    "ValidationIssue",
    "validate_pre_execution",
    "validate_result",
    # Cache
    "DuckDBCache",
    "QueryCache",
    "PrecomputedAggregates",
    "get_db",
    "execute_sql",
    # Query Builder
    "CoverageQuery",
    "CompetitionQuery",
    "HistoricalQuery",
    "quick_coverage",
    # Ekom Query Builder
    "EkomQuery",
    "quick_ekom",
    "MOBIL_FYLKER",
    # Document Checker
    "DocumentChecker",
    "NumberFinding",
    "DataSourceMatch",
    "LearnedPattern",
    "parse_norwegian_number",
    "find_document",
    # Query Engine
    "execute_malloy",
    "execute_sql_cached",
    "execute_coverage",
    "execute_ekom",
    "get_available_queries",
    "get_query_info",
    "invalidate_cache",
    "get_cache_stats",
    "MALLOY_QUERIES",
    # Error Handler
    "with_error_learning",
    "auto_learn_from_error",
]
