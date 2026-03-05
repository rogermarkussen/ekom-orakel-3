#!/usr/bin/env python3
"""
Query Router - Map naturlig språk til execute_malloy-kall.

Bruk:
    uv run python main.py "Fiber i spredtbygd"
    uv run python main.py "5G-dekning per fylke"
    uv run python main.py "Høyhastighet over 100 Mbit"
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Optional

import polars as pl

from library.clarification import AmbiguousQueryError, assess_query_clarity
from library.engine import (
    execute_coverage,
    execute_malloy,
    get_available_queries,
)
from library.fylker import FYLKE_ALIASES
from library.query_matcher import SYNONYM_TO_CANONICAL


@dataclass
class ParsedQuery:
    """Strukturert representasjon av en brukerquery."""

    teknologi: Optional[list[str]] = None
    populasjon: Optional[str] = None
    hastighet_min: Optional[int] = None
    year: int = 2024
    group_by: str = "fylke"
    fylker: list[str] = field(default_factory=list)
    kun_hc: Optional[bool] = None


class QueryParser:
    """Parser for naturlig språk-spørringer om dekning."""

    SPEED_PATTERNS = [
        (r"\bgigabit(?:dekning)?\b", lambda _: 1000),
        (r"(\d+)\s*gbit", lambda m: int(m.group(1)) * 1000),
        (r"(\d+)\s*mbit", lambda m: int(m.group(1))),
        (r">=?\s*(\d+)", lambda m: int(m.group(1))),
        (r"over\s+(\d+)", lambda m: int(m.group(1))),
    ]

    YEAR_PATTERNS = [
        (r"\b(2022|2023|2024)\b", lambda m: int(m.group(1))),
        (r"i fjor", lambda _: 2023),
    ]

    def __init__(self):
        # Bygg teknologi-mapping fra SYNONYM_TO_CANONICAL
        self.tech_terms = {
            k: v
            for k, v in SYNONYM_TO_CANONICAL.items()
            if v in ["fiber", "ftb", "kabel", "dsl", "5g", "4g", "mobil"]
        }
        self.pop_terms = {
            k: v
            for k, v in SYNONYM_TO_CANONICAL.items()
            if v in ["spredtbygd", "tettsted"]
        }

    def extract_hastighet(self, text: str) -> Optional[int]:
        """Ekstraher hastighetsgrense fra tekst."""
        for pattern, extractor in self.SPEED_PATTERNS:
            match = re.search(pattern, text.lower())
            if match:
                return extractor(match)
        return None

    def extract_year(self, text: str) -> int:
        """Ekstraher årstall fra tekst."""
        for pattern, extractor in self.YEAR_PATTERNS:
            match = re.search(pattern, text.lower())
            if match:
                return extractor(match)
        return 2024

    def extract_fylker(self, text: str) -> list[str]:
        """Ekstraher fylkesnavn fra tekst."""
        fylker = []
        text_lower = text.lower()
        for alias, fylke in FYLKE_ALIASES.items():
            if alias in text_lower and fylke not in fylker:
                fylker.append(fylke)
        return fylker

    def extract_group_by(self, text: str) -> str:
        """Ekstraher grupperingsnivå fra tekst."""
        text_lower = text.lower()
        if "kommune" in text_lower:
            return "kommune"
        if any(term in text_lower for term in ["nasjonal", "nasjonalt", "hele landet", "norge totalt"]):
            return "nasjonal"
        return "fylke"

    def extract_teknologi(self, text: str) -> Optional[list[str]]:
        """Ekstraher teknologier fra tekst."""
        teknologier = []
        text_lower = text.lower()
        for term, canonical in self.tech_terms.items():
            if term in text_lower and canonical not in teknologier:
                teknologier.append(canonical)
        return teknologier if teknologier else None

    def extract_populasjon(self, text: str) -> Optional[str]:
        """Ekstraher populasjonstype fra tekst."""
        text_lower = text.lower()
        for term, canonical in self.pop_terms.items():
            if term in text_lower:
                return canonical
        return None

    def extract_hc(self, text: str) -> Optional[bool]:
        """Ekstraher HC/HP-filter fra tekst."""
        text_lower = text.lower()
        if any(t in text_lower for t in ["hc", "homes connected", "tilkoblet"]):
            return True
        return None

    def parse(self, user_input: str) -> ParsedQuery:
        """Parse brukerinput til strukturert query."""
        return ParsedQuery(
            teknologi=self.extract_teknologi(user_input),
            populasjon=self.extract_populasjon(user_input),
            hastighet_min=self.extract_hastighet(user_input),
            year=self.extract_year(user_input),
            group_by=self.extract_group_by(user_input),
            fylker=self.extract_fylker(user_input),
            kun_hc=self.extract_hc(user_input),
        )


def route_query(user_input: str) -> pl.DataFrame:
    """
    Map naturlig språk til execute_malloy-kall.

    Args:
        user_input: Brukerens spørring på naturlig språk

    Returns:
        DataFrame med resultat
    """
    parser = QueryParser()
    clarification = assess_query_clarity(user_input)
    if clarification.needs_clarification:
        raise AmbiguousQueryError(clarification.to_user_prompt())

    parsed = parser.parse(user_input)

    # Høyhastighet
    if (
        parsed.hastighet_min
        and parsed.hastighet_min >= 100
        and parsed.group_by == "fylke"
        and parsed.year == 2024
        and not parsed.fylker
    ):
        return execute_malloy("hoyhastighet_fylke")

    # 5G
    if (
        parsed.teknologi
        and "5g" in parsed.teknologi
        and parsed.group_by == "fylke"
        and parsed.year == 2024
        and not parsed.fylker
    ):
        if parsed.populasjon == "spredtbygd":
            return execute_malloy("g5_spredtbygd")
        return execute_malloy("g5_fylke")

    # 4G
    if (
        parsed.teknologi
        and "4g" in parsed.teknologi
        and parsed.group_by == "fylke"
        and parsed.year == 2024
        and not parsed.fylker
    ):
        return execute_malloy("g4_fylke")

    # FTB
    if (
        parsed.teknologi
        and "ftb" in parsed.teknologi
        and parsed.group_by == "fylke"
        and parsed.year == 2024
        and not parsed.fylker
        and parsed.hastighet_min is None
    ):
        return execute_malloy("ftb_fylke")

    # Fiber
    if (
        parsed.teknologi
        and "fiber" in parsed.teknologi
        and parsed.group_by == "fylke"
        and parsed.year == 2024
        and not parsed.fylker
        and parsed.hastighet_min is None
    ):
        if parsed.kun_hc:
            return execute_malloy("fiber_hc_fylke")
        elif parsed.populasjon == "spredtbygd":
            return execute_malloy("fiber_spredtbygd")
        elif parsed.populasjon == "tettsted":
            return execute_malloy("fiber_tettsted")
        return execute_malloy("fiber_fylke")

    # Fallback til execute_coverage
    return execute_coverage(
        teknologi=parsed.teknologi or [],
        populasjon=parsed.populasjon,
        group_by=parsed.group_by,
        year=parsed.year,
        hastighet_min=parsed.hastighet_min,
    )


def main():
    """CLI-grensesnitt for query router."""
    if len(sys.argv) < 2:
        print('Bruk: uv run python main.py "<spørring>"')
        print()
        print("Eksempler:")
        print('  uv run python main.py "Fiber per fylke"')
        print('  uv run python main.py "5G i spredtbygd"')
        print('  uv run python main.py "Høyhastighet over 100 Mbit"')
        print('  uv run python main.py "LTE-dekning per fylke"')
        print()
        print("Tilgjengelige Malloy-queries:")
        for q in get_available_queries():
            print(f"  - {q}")
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])
    clarification = assess_query_clarity(user_input)

    print(f"Spørring: {user_input}")
    print("-" * 50)

    if clarification.needs_clarification:
        print(clarification.to_user_prompt())
        sys.exit(2)

    # Parse og vis info
    parser = QueryParser()
    parsed = parser.parse(user_input)
    print(f"Parsed: teknologi={parsed.teknologi}, pop={parsed.populasjon}, år={parsed.year}")

    try:
        df = route_query(user_input)
    except AmbiguousQueryError as exc:
        print(exc)
        sys.exit(2)
    print(df)


if __name__ == "__main__":
    main()
