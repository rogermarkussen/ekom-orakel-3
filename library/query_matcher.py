"""
Keyword-basert query matching med domenespesifikke synonymer.

Utvider søkeord med synonymer for bedre treff uten å bruke embeddings.

Eksempel:
    from library.query_matcher import QueryMatcher

    matcher = QueryMatcher()

    # Søk med automatisk synonym-utvidelse
    expanded = matcher.expand_query("fiber i utkantstrøk")
    # -> "fiber OR ftth OR fiberoptisk spredtbygd OR rural OR distrikt"

    # Finn lignende spørringer
    results = matcher.find_similar("fiberdekning på landet")
"""

import re
from dataclasses import dataclass
from typing import Optional

from library.knowledge import KnowledgeBase, Query


# Domenespesifikke synonymer
DOMAIN_SYNONYMS = {
    # Teknologier
    "fiber": ["ftth", "fiberoptisk", "glassfib"],
    "ftb": ["fast trådløst", "fwa", "fixed wireless"],
    "kabel": ["hfc", "kabel-tv", "coax"],
    "dsl": ["adsl", "vdsl", "kobber"],
    "5g": ["femte generasjon", "5g-nett"],
    "4g": ["lte", "fjerde generasjon"],
    "mobil": ["mob", "mobilnett", "mobildekning"],

    # Geografiske områder
    "spredtbygd": ["rural", "distrikt", "grisgrendt", "utkant", "landet", "bygd"],
    "tettsted": ["urban", "by", "tettbygd", "sentrum"],
    "fylke": ["region", "fylkesvis", "per fylke"],
    "kommune": ["kommunevis", "per kommune"],
    "nasjonal": ["nasjonalt", "hele landet", "norge", "totalt"],

    # Metrikker
    "dekning": ["dekningsgrad", "coverage", "tilgang"],
    "hastighet": ["speed", "mbit", "kapasitet", "båndbredde"],
    "husstander": ["husholdninger", "boliger", "hjem", "hus"],
    "fritidsboliger": ["hytter", "fritid", "feriehus"],

    # Konkurranse
    "tilbyder": ["operatør", "leverandør", "aktør"],
    "konkurranse": ["konkurransesituasjon", "markedsandel", "overlapping"],
    "monopol": ["enetilbyder", "én tilbyder", "kun en"],

    # HC/HP
    "hc": ["homes connected", "tilkoblet", "aktivt"],
    "hp": ["homes passed", "potensielt", "tilgjengelig"],

    # Tidsserie
    "utvikling": ["trend", "endring", "over tid", "historisk"],
    "sammenligning": ["versus", "vs", "mot", "forskjell"],

    # Ekom-spesifikt
    "abonnement": ["ab", "abonnenter", "kunder"],
    "kontantkort": ["prepaid", "forhåndsbetalt"],
    "inntekt": ["omsetning", "revenue", "arpu"],
}

# Inverse mapping for å finne kanonisk term
SYNONYM_TO_CANONICAL = {}
for canonical, synonyms in DOMAIN_SYNONYMS.items():
    for syn in synonyms:
        SYNONYM_TO_CANONICAL[syn.lower()] = canonical
    SYNONYM_TO_CANONICAL[canonical.lower()] = canonical


@dataclass
class MatchResult:
    """Resultat fra query matching."""
    query: Query
    score: float
    matched_terms: list[str]

    def __repr__(self):
        return f"MatchResult(id={self.query.id}, score={self.score:.2f}, terms={self.matched_terms})"


class QueryMatcher:
    """Keyword-basert matcher med synonym-utvidelse."""

    def __init__(self, kb: Optional[KnowledgeBase] = None):
        self.kb = kb or KnowledgeBase()

    def normalize(self, text: str) -> list[str]:
        """Normaliser tekst til tokens."""
        # Lowercase og fjern spesialtegn
        text = text.lower()
        text = re.sub(r'[^\wæøå\s]', ' ', text)
        tokens = text.split()
        return [t for t in tokens if len(t) > 1]

    def get_canonical(self, term: str) -> Optional[str]:
        """Finn kanonisk form av et begrep."""
        return SYNONYM_TO_CANONICAL.get(term.lower())

    def expand_term(self, term: str) -> list[str]:
        """Utvid et begrep med synonymer."""
        term_lower = term.lower()

        # Finn kanonisk form
        canonical = self.get_canonical(term_lower)
        if canonical:
            # Returner kanonisk + alle synonymer
            result = [canonical] + DOMAIN_SYNONYMS.get(canonical, [])
            return list(set(result))

        # Ingen match, returner som den er
        return [term_lower]

    def expand_query(self, query: str) -> str:
        """
        Utvid søkestreng med synonymer for FTS5.

        Eksempel:
            "fiber rural" -> "(fiber OR ftth OR fiberoptisk) (spredtbygd OR rural OR distrikt)"
        """
        tokens = self.normalize(query)
        expanded_groups = []

        for token in tokens:
            expanded = self.expand_term(token)
            if len(expanded) > 1:
                # Gruppe med OR
                group = " OR ".join(expanded)
                expanded_groups.append(f"({group})")
            else:
                expanded_groups.append(expanded[0])

        return " ".join(expanded_groups)

    def calculate_score(self, query: Query, search_tokens: list[str]) -> tuple[float, list[str]]:
        """
        Beregn relevans-score mellom spørring og søkeord.

        Returnerer (score, matched_terms).
        """
        # Kombiner all tekst fra query
        query_text = " ".join([
            query.question,
            query.sql,
            query.result_summary or "",
            query.category,
            " ".join(query.tags),
            query.notes or "",
        ]).lower()

        query_tokens = set(self.normalize(query_text))

        matched_terms = []
        score = 0.0

        for search_token in search_tokens:
            expanded = self.expand_term(search_token)

            for exp_term in expanded:
                if exp_term in query_tokens:
                    # Eksakt match
                    score += 1.0
                    matched_terms.append(exp_term)
                    break
                else:
                    # Partial match (prefix)
                    for qt in query_tokens:
                        if qt.startswith(exp_term) or exp_term.startswith(qt):
                            score += 0.5
                            matched_terms.append(f"{exp_term}~{qt}")
                            break

        # Bonus for tag-match
        search_set = set(search_tokens)
        for tag in query.tags:
            if tag.lower() in search_set:
                score += 0.5
                if tag not in matched_terms:
                    matched_terms.append(f"tag:{tag}")

        # Normaliser basert på antall søkeord
        if search_tokens:
            score = score / len(search_tokens)

        return score, matched_terms

    def find_similar(
        self,
        search_query: str,
        limit: int = 5,
        min_score: float = 0.3,
    ) -> list[MatchResult]:
        """
        Finn lignende spørringer basert på keyword matching.

        Kombinerer:
        1. FTS5 søk med synonym-utvidelse
        2. Ekstra scoring basert på domenekunnskap
        """
        search_tokens = self.normalize(search_query)

        if not search_tokens:
            return []

        # Prøv FTS5 først med utvidet query
        expanded = self.expand_query(search_query)
        try:
            fts_results = self.kb.search_queries(expanded, limit=limit * 2)
        except Exception:
            # FTS kan feile på komplekse queries, fall back til list
            fts_results = self.kb.list_queries(limit=100)

        # Scorer alle resultater
        scored = []
        for query in fts_results:
            score, matched = self.calculate_score(query, search_tokens)
            if score >= min_score:
                scored.append(MatchResult(query, score, matched))

        # Sorter etter score
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored[:limit]

    def suggest_for_question(self, question: str) -> list[Query]:
        """
        Foreslå relevante spørringer for et nytt spørsmål.

        Brukes i /ny for å vise lignende tidligere spørringer.
        """
        results = self.find_similar(question, limit=3)
        return [r.query for r in results]

    def get_categories(self) -> list[str]:
        """Hent alle unike kategorier."""
        queries = self.kb.list_queries(limit=1000)
        categories = set(q.category for q in queries)
        return sorted(categories)

    def get_tags(self) -> list[str]:
        """Hent alle unike tags."""
        queries = self.kb.list_queries(limit=1000)
        tags = set()
        for q in queries:
            tags.update(q.tags)
        return sorted(tags)


def extract_keywords(text: str) -> list[str]:
    """
    Ekstraher nøkkelord fra tekst.

    Nyttig for automatisk tagging.
    """
    tokens = QueryMatcher().normalize(text)
    keywords = []

    for token in tokens:
        canonical = SYNONYM_TO_CANONICAL.get(token)
        if canonical:
            keywords.append(canonical)

    return list(set(keywords))
