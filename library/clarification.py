"""
Regler for når agenten må be om presisering i stedet for å gjette.

Målet er konservativ tolkning: hvis et spørsmål har flere rimelige
fortolkninger, skal løsningen be om oppfølging før query bygges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal


DomainType = Literal["coverage", "ekom", "unknown"]

COVERAGE_TERMS = {
    "dekning", "dekningen", "bredbåndsdekning", "gigabit", "gigabitdekning",
    "høyhastighet", "fiber", "fiberdekning", "ftb", "kabel", "dsl", "4g", "5g", "mobildekning",
}
EKOM_TERMS = {
    "ekom", "abonnement", "abonnenter", "inntekt", "inntekter", "trafikk",
    "markedsandel", "markedsandeler", "omsetning", "mobilabonnement",
    "fakturert", "kontantkort", "sluttbruker", "fast bredbånd", "mobiltjenester",
}
MOBILE_WORDS = {"mobil", "mobildekning", "mobilabonnement", "mobilnett"}
MOBILE_GENERATIONS = {"4g", "5g", "lte"}
FAST_TECHS = {"fiber", "ftb", "kabel", "dsl", "radio", "satellitt"}
PERIOD_WORDS = {"2022", "2023", "2024", "2025", "helår", "halvår", "i fjor"}
MARKET_SEGMENTS = {"privat", "bedrift", "samlet"}
METRIC_WORDS = {"abonnement", "inntekt", "inntekter", "trafikk"}
MOBILE_SUBTYPES = {"fakturert", "kontantkort", "begge", "samlet"}


@dataclass
class ClarificationIssue:
    field: str
    reason: str
    prompt: str


@dataclass
class ClarificationResult:
    domain: DomainType
    issues: list[ClarificationIssue] = field(default_factory=list)

    @property
    def needs_clarification(self) -> bool:
        return bool(self.issues)

    def to_user_prompt(self) -> str:
        if not self.issues:
            return ""
        prompts = []
        seen = set()
        for issue in self.issues:
            if issue.prompt not in seen:
                prompts.append(issue.prompt)
                seen.add(issue.prompt)
        return "Spørsmålet kan tolkes på flere måter. " + " ".join(prompts)


class AmbiguousQueryError(ValueError):
    """Spørsmålet er for uklart til å kjøres uten presisering."""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\wæøå/\-]+", _normalize(text)))


def _has_year_or_period(text: str) -> bool:
    return bool(re.search(r"\b(20\d{2})(\s*[-–]\s*20\d{2})?\b", text.lower())) or any(
        word in text.lower() for word in ["helår", "halvår", "i fjor"]
    )


def _has_time_range(text: str) -> bool:
    return bool(
        re.search(r"\b20\d{2}\s*[-–]\s*20\d{2}\b", text.lower())
        or re.search(r"\bfra\s+20\d{2}\s+til\s+20\d{2}\b", text.lower())
        or any(term in text.lower() for term in ["utvikling", "over tid", "historisk", "tidsserie"])
    )


def _has_speed_definition(text: str) -> bool:
    text_lower = text.lower()
    return bool(
        re.search(r"\b\d+\s*(gbit|mbit)\b", text_lower)
        or re.search(r"\b\d+\s*/\s*\d+\b", text_lower)
        or any(term in text_lower for term in ["gigabit", "høyhastighet", "100/100", "1000/100", "1000/1000"])
    )


def _detect_techs(text: str) -> set[str]:
    text_lower = text.lower()
    techs = set()
    for tech in FAST_TECHS | MOBILE_GENERATIONS:
        if tech in text_lower:
            techs.add(tech)
    if "mobil" in text_lower and not techs:
        techs.add("mobil")
    return techs


def infer_domain(text: str) -> DomainType:
    text_lower = _normalize(text)
    toks = _tokens(text)
    coverage_hits = sum(1 for term in COVERAGE_TERMS if term in text_lower)
    ekom_hits = sum(1 for term in EKOM_TERMS if term in text_lower)

    if _has_speed_definition(text_lower) or _detect_techs(text_lower):
        coverage_hits += 1

    if coverage_hits == 0 and ekom_hits == 0:
        return "unknown"
    if coverage_hits > 0 and ekom_hits == 0:
        return "coverage"
    if ekom_hits > 0 and coverage_hits == 0:
        return "ekom"

    # Ved blandet språk prioriterer vi eksplisitt dekningsord eller ekom-ord.
    if any(term in toks for term in {"dekning", "gigabit", "fiber", "5g", "4g"}):
        return "coverage"
    if any(term in toks for term in {"abonnement", "inntekter", "trafikk", "markedsandel"}):
        return "ekom"
    return "unknown"


def assess_query_clarity(text: str) -> ClarificationResult:
    text_lower = _normalize(text)
    domain = infer_domain(text)
    issues: list[ClarificationIssue] = []
    techs = _detect_techs(text_lower)
    has_year = _has_year_or_period(text_lower)
    has_speed = _has_speed_definition(text_lower)
    has_range = _has_time_range(text_lower)

    if domain == "unknown":
        issues.append(
            ClarificationIssue(
                field="domain",
                reason="Spørsmålet mangler tydelige signaler om dekning eller ekomstatistikk.",
                prompt="Mener du dekningsdata eller ekomstatistikk?",
            )
        )
        return ClarificationResult(domain=domain, issues=issues)

    if domain == "coverage":
        if "i fjor" in text_lower:
            issues.append(
                ClarificationIssue(
                    field="relative_year",
                    reason="Relative år som 'i fjor' er ustabile og kan peke på år uten data.",
                    prompt="Hvilket eksakt år mener du?",
                )
            )

        if has_range:
            issues.append(
                ClarificationIssue(
                    field="time_range",
                    reason="Spørsmålet gjelder flere år og skal ikke presses inn i en ettårs-rute.",
                    prompt="Vil du ha en tidsserie med ett resultat per år, eller gjelder det ett bestemt år?",
                )
            )

        if not has_year:
            issues.append(
                ClarificationIssue(
                    field="year",
                    reason="Dekningsdata finnes for flere år, og løsningen skal ikke gjette år.",
                    prompt="Hvilket år eller hvilken periode gjelder det?",
                )
            )

        if "høyhastighet" in text_lower and not has_speed:
            issues.append(
                ClarificationIssue(
                    field="speed",
                    reason="Høyhastighet kan bety ulike terskler.",
                    prompt="Hvilken hastighetsgrense mener du, for eksempel 100 Mbit eller gigabit?",
                )
            )

        if not techs and not has_speed:
            issues.append(
                ClarificationIssue(
                    field="coverage_type",
                    reason="Dekning kan bety teknologi-dekning eller hastighetsdekning.",
                    prompt="Mener du en bestemt teknologi, for eksempel fiber eller 5G, eller en hastighetsdekning som 100 Mbit eller gigabit?",
                )
            )

        if "mobil" in text_lower and not (techs & MOBILE_GENERATIONS):
            issues.append(
                ClarificationIssue(
                    field="mobile_generation",
                    reason="Mobildekning kan bety 4G, 5G eller begge.",
                    prompt="Mener du 4G, 5G eller begge deler?",
                )
            )

        if "målt etter" in text_lower and not any(term in text_lower for term in ["hus", "husstand", "fritid", "hytte", "adresse"]):
            issues.append(
                ClarificationIssue(
                    field="metric",
                    reason="Målt etter kan vise til ulike enheter.",
                    prompt="Mener du husstander, fritidsboliger eller adresser?",
                )
            )

    if domain == "ekom":
        if has_range:
            issues.append(
                ClarificationIssue(
                    field="time_range",
                    reason="Ekom-spørsmålet gjelder flere perioder og trenger eksplisitt tidsoppsett.",
                    prompt="Vil du ha utvikling per rapportperiode, eller en enkelt periode?",
                )
            )

        if not has_year:
            issues.append(
                ClarificationIssue(
                    field="period",
                    reason="Ekom-statistikk må avgrenses til rapportperiode eller tidsserie.",
                    prompt="Hvilken rapportperiode eller hvilket tidsrom gjelder det?",
                )
            )

        if "markedsandel" in text_lower and not any(term in text_lower for term in METRIC_WORDS):
            issues.append(
                ClarificationIssue(
                    field="share_basis",
                    reason="Markedsandel kan være basert på abonnement, inntekter eller trafikk.",
                    prompt="Mener du markedsandeler basert på abonnement, inntekter eller trafikk?",
                )
            )

        if "mobilabonnement" in text_lower and not any(term in text_lower for term in MOBILE_SUBTYPES):
            issues.append(
                ClarificationIssue(
                    field="mobile_subtype",
                    reason="Mobilabonnement kan være fakturert, kontantkort eller begge.",
                    prompt="Mener du fakturert, kontantkort eller begge deler?",
                )
            )

        if any(term in text_lower for term in ["fast bredbånd", "fiber", "dsl", "kabel"]) and not any(term in text_lower for term in MARKET_SEGMENTS):
            issues.append(
                ClarificationIssue(
                    field="market_segment",
                    reason="Fast bredbånd i ekom kan være privat, bedrift eller samlet.",
                    prompt="Gjelder det privat, bedrift eller samlet marked?",
                )
            )

        if not any(term in text_lower for term in METRIC_WORDS) and any(term in text_lower for term in ["utvikling", "nivå", "marked", "fast bredbånd", "mobiltjenester"]):
            issues.append(
                ClarificationIssue(
                    field="metric",
                    reason="Ekom-spørsmål uten metrikk kan sikte mot abonnement, inntekter eller trafikk.",
                    prompt="Mener du abonnement, inntekter eller trafikk?",
                )
            )

    return ClarificationResult(domain=domain, issues=issues)
