"""
Auto-learning error handler.

Fanger feil under query-kjøring og registrerer korreksjoner automatisk
slik at samme feil ikke gjentas (CLAUDE.md regel 9).

Eksempel:
    from library.error_handler import with_error_learning

    @with_error_learning
    def execute_sql(sql: str) -> pl.DataFrame:
        # ...
"""

import re
from functools import wraps
from typing import Optional

from library.knowledge import KnowledgeBase

# Kjente feilmønstre som skal auto-registreres
AUTO_CORRECTION_PATTERNS = [
    {
        "pattern": r"column \"(\w+)\" not found",
        "context": "Ukjent kolonne",
        "solution": "Sjekk kolonnenavn med DESCRIBE tabell",
        "auto_pattern": r"column.*not found",
    },
    {
        "pattern": r"table \"(\w+)\" does not exist",
        "context": "Ukjent tabell",
        "solution": "Bruk views: adr, fbb, mob, ab, dekning_tek, ekom",
        "auto_pattern": r"table.*does not exist",
    },
    {
        "pattern": r"Catalog Error: Table.*does not exist",
        "context": "Ukjent tabell i DuckDB",
        "solution": "Bruk views: adr, fbb, mob, ab, dekning_tek, dekning_hast, ekom",
        "auto_pattern": r"Catalog Error.*Table.*does not exist",
    },
    {
        "pattern": r"Parser Error.*syntax error",
        "context": "SQL syntaksfeil",
        "solution": "Sjekk SQL-syntaks. Vanlige feil: manglende komma, feil aliasing",
        "auto_pattern": r"Parser Error.*syntax error",
    },
    {
        "pattern": r"Binder Error.*column.*must appear in.*GROUP BY",
        "context": "Ugyldig GROUP BY",
        "solution": "Alle ikke-aggregerte kolonner må være i GROUP BY",
        "auto_pattern": r"must appear in.*GROUP BY",
    },
    {
        "pattern": r"Conversion Error.*Could not convert",
        "context": "Type konverteringsfeil",
        "solution": "Sjekk datatyper. Bruk CAST() for eksplisitt konvertering",
        "auto_pattern": r"Conversion Error.*Could not convert",
    },
]


def auto_learn_from_error(sql: str, error: Exception) -> Optional[str]:
    """
    Analyser feil og registrer korreksjon hvis relevant.

    Args:
        sql: SQL-query som feilet
        error: Exception som ble kastet

    Returns:
        Løsningsforslag hvis funnet, ellers None
    """
    kb = KnowledgeBase()
    error_msg = str(error)

    # Sjekk eksisterende korreksjoner først
    existing = kb.find_matching_corrections(sql)
    if existing:
        return existing[0].solution

    # Match mot kjente mønstre og registrer ny korreksjon
    for p in AUTO_CORRECTION_PATTERNS:
        if re.search(p["pattern"], error_msg, re.IGNORECASE):
            kb.add_correction(
                context=p["context"],
                error=error_msg[:200],
                solution=p["solution"],
                pattern=p["auto_pattern"],
            )
            return p["solution"]

    return None


def with_error_learning(func):
    """
    Decorator som wrapper execute-funksjoner med auto-learning.

    Ved feil:
    1. Logger feilen til knowledge base
    2. Legger til løsningsforslag i feilmeldingen

    Eksempel:
        @with_error_learning
        def execute_sql_cached(sql: str, ...) -> pl.DataFrame:
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Hent SQL fra args eller kwargs
        sql = args[0] if args else kwargs.get("sql", "")

        try:
            return func(*args, **kwargs)
        except Exception as e:
            suggestion = auto_learn_from_error(sql, e)
            if suggestion:
                raise RuntimeError(f"{e}\n\nForslag: {suggestion}") from e
            raise

    return wrapper
