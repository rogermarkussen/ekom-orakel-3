"""
Flerlagsvalidering for SQL og resultater.

Lag 1: Pre-execution (statisk analyse av SQL)
Lag 2: Post-execution (sanity checks på resultater)
Lag 3: Error pattern detection (match mot kjente feil)

Eksempel:
    from library.validators import SQLValidator, ResultValidator

    # Pre-execution
    validator = SQLValidator()
    warnings = validator.check_sql(sql)

    # Post-execution
    result_validator = ResultValidator()
    issues = result_validator.check_coverage_result(df)
"""

import re
from dataclasses import dataclass
from typing import Optional

import polars as pl

from library.fylker import FYLKER_2024


@dataclass
class ValidationIssue:
    """Valideringsproblem."""
    level: str  # "error", "warning", "info"
    message: str
    suggestion: Optional[str] = None
    pattern: Optional[str] = None  # For pattern matching


class SQLValidator:
    """Pre-execution SQL validering."""

    # Kjente anti-patterns
    ANTI_PATTERNS = [
        # Ekom-spesifikke
        {
            "pattern": r"FROM\s+['\"]?lib/ekom\.parquet['\"]?(?!.*tp\s*=\s*['\"]Sum['\"])",
            "message": "Ekom-query uten tp='Sum' filter",
            "suggestion": "Legg til 'tp = \"Sum\"' for å unngå dobbeltelling",
            "level": "warning",
        },
        # FBB Bedrift uten Datakommunikasjon
        {
            "pattern": r"hk\s*=\s*['\"]Fast bredb[aå]nd['\"].*ms\s*=\s*['\"]Bedrift['\"](?!.*Datakommunikasjon)",
            "message": "FBB Bedrift uten Datakommunikasjon",
            "suggestion": "Bruk hk IN ('Fast bredbånd', 'Datakommunikasjon') for bedriftsmarkedet",
            "level": "error",
        },
        # Mobilfylke med feil tp
        {
            "pattern": r"n1\s*(?:=|IN).*(?:Agder|Oslo|Vestland|Akershus|Buskerud|Finnmark|Innlandet|Nordland|Rogaland|Telemark|Troms|Trøndelag|Vestfold|Østfold|Møre og Romsdal).*tp\s*=\s*['\"]Sum['\"]",
            "message": "Mobilfylke med tp='Sum' (skal være 'Herav')",
            "suggestion": "Fylkesfordeling for mobil bruker tp='Herav', ikke tp='Sum'",
            "level": "error",
        },
        # Hastighetsfilter feil
        {
            "pattern": r"ned\s*>\s*\d+(?!000)",
            "message": "Hastighetsfilter bruker > i stedet for >=",
            "suggestion": "Bruk >= for å inkludere eksakt grense",
            "level": "warning",
        },
        {
            "pattern": r"ned\s*>=?\s*\d{1,3}(?!\d|_)",
            "message": "Hastighet ser ut til å være i Mbit, ikke kbps",
            "suggestion": "Konverter til kbps: 100 Mbit = 100000 kbps",
            "level": "warning",
        },
        # ORDER BY etter UNION
        {
            "pattern": r"UNION\s+ALL\s+SELECT[^)]+ORDER\s+BY",
            "message": "ORDER BY inne i UNION kan gi feil",
            "suggestion": "Flytt ORDER BY til slutten av hele UNION",
            "level": "error",
        },
        # Sum av hus fra ab
        {
            "pattern": r"SUM\s*\(\s*(?:ab\.)?hus\s*\)",
            "message": "Summerer hus fra ab-tabell",
            "suggestion": "Tell rader i ab, ikke summer hus (ab har én rad per abonnent)",
            "level": "error",
        },
        # Manglende alias i subquery
        {
            "pattern": r"\)\s+(?:LEFT\s+)?JOIN",
            "message": "Subquery uten alias",
            "suggestion": "Gi subquery et alias: (...) AS subquery_name",
            "level": "warning",
        },
        # Hardkodet årstall i sti
        {
            "pattern": r"lib/\d{4}/",
            "message": "Hardkodet årstall i filsti",
            "suggestion": "Bruk variabel for år eller load_data(year)",
            "level": "info",
        },
        # Manglende GROUP BY med aggregat
        {
            "pattern": r"SELECT[^;]+(?:SUM|COUNT|AVG|MAX|MIN)\s*\([^)]+\)[^;]+(?!GROUP\s+BY)",
            "message": "Aggregatfunksjon uten GROUP BY",
            "suggestion": "Sjekk at GROUP BY er med for alle ikke-aggregerte kolonner",
            "level": "warning",
        },
    ]

    def check_sql(self, sql: str) -> list[ValidationIssue]:
        """
        Sjekk SQL mot kjente anti-patterns.

        Returnerer liste med valideringsproblemer.
        """
        issues = []

        for pattern_info in self.ANTI_PATTERNS:
            if re.search(pattern_info["pattern"], sql, re.IGNORECASE | re.DOTALL):
                issues.append(ValidationIssue(
                    level=pattern_info["level"],
                    message=pattern_info["message"],
                    suggestion=pattern_info.get("suggestion"),
                    pattern=pattern_info["pattern"],
                ))

        return issues

    def check_sql_with_kb(self, sql: str) -> list[ValidationIssue]:
        """
        Sjekk SQL mot både anti-patterns og kjente korreksjoner.
        """
        issues = self.check_sql(sql)

        # Sjekk mot kjente korreksjoner i kunnskapsbasen
        try:
            from library.knowledge import KnowledgeBase
            kb = KnowledgeBase()
            corrections = kb.find_matching_corrections(sql)

            for corr in corrections:
                issues.append(ValidationIssue(
                    level="warning",
                    message=f"Kjent feil: {corr.error}",
                    suggestion=corr.solution,
                    pattern=corr.pattern,
                ))
        except Exception:
            pass  # KB ikke tilgjengelig

        return issues


class ResultValidator:
    """Post-execution resultatvalidering."""

    # Sanity check grenser
    SANITY_CHECKS = {
        "fiber_dekning_nasjonal": {
            "min": 85.0,
            "max": 98.0,
            "message": "Nasjonal fiberdekning",
        },
        "5g_dekning_nasjonal": {
            "min": 70.0,
            "max": 100.0,
            "message": "Nasjonal 5G-dekning",
        },
        "totalt_husstander": {
            "min": 2_400_000,
            "max": 2_800_000,
            "message": "Totalt antall husstander",
        },
        "spredtbygd_andel": {
            "min": 12.0,
            "max": 25.0,
            "message": "Andel spredtbygd",
        },
    }

    def check_coverage_result(
        self,
        df: pl.DataFrame,
        coverage_type: Optional[str] = None,
    ) -> list[ValidationIssue]:
        """
        Valider dekningsresultat.

        Args:
            df: DataFrame med resultat
            coverage_type: Type dekning for spesifikke sjekker
        """
        issues = []

        # 1. Prosenter mellom 0-100
        for col in df.columns:
            if "prosent" in col.lower() or col.endswith("_pct"):
                invalid = df.filter(
                    (pl.col(col) < 0) | (pl.col(col) > 100)
                )
                if invalid.height > 0:
                    issues.append(ValidationIssue(
                        level="error",
                        message=f"Ugyldig prosent i {col}",
                        suggestion=f"Verdier utenfor 0-100: {invalid.select(col).to_series().to_list()[:5]}",
                    ))

        # 2. Nasjonal rad finnes
        if "fylke" in df.columns:
            national = df.filter(pl.col("fylke") == "NASJONALT")
            if national.height == 0:
                issues.append(ValidationIssue(
                    level="warning",
                    message="Mangler NASJONALT-rad",
                    suggestion="Bruk add_national_aggregate() for å legge til",
                ))

        # 3. Alle fylker representert
        if "fylke" in df.columns:
            fylker_i_data = set(
                df.filter(pl.col("fylke") != "NASJONALT")
                .select("fylke")
                .to_series()
                .to_list()
            )
            manglende = set(FYLKER_2024) - fylker_i_data
            ekstra = fylker_i_data - set(FYLKER_2024)

            if manglende:
                issues.append(ValidationIssue(
                    level="warning",
                    message=f"Manglende fylker: {sorted(manglende)}",
                ))
            if ekstra:
                issues.append(ValidationIssue(
                    level="warning",
                    message=f"Ukjente/gamle fylker: {sorted(ekstra)}",
                    suggestion="Sjekk fylkesmapping (2020 vs 2024)",
                ))

        # 4. Spesifikke sanity checks
        if coverage_type and coverage_type in self.SANITY_CHECKS:
            check = self.SANITY_CHECKS[coverage_type]
            # Finn nasjonal verdi
            for col in df.columns:
                if "prosent" in col.lower():
                    nat = df.filter(pl.col("fylke") == "NASJONALT")
                    if nat.height > 0:
                        val = nat.select(col).item()
                        if val < check["min"] or val > check["max"]:
                            issues.append(ValidationIssue(
                                level="warning",
                                message=f"{check['message']} ({val:.1f}%) utenfor forventet {check['min']}-{check['max']}%",
                                suggestion="Verifiser filtere og datakilder",
                            ))
                    break

        return issues

    def check_totals_match(
        self,
        df: pl.DataFrame,
        metric_col: str,
        total_col: str,
        group_col: str = "fylke",
    ) -> list[ValidationIssue]:
        """Sjekk at sum av regioner = nasjonalt."""
        issues = []

        non_national = df.filter(pl.col(group_col) != "NASJONALT")
        national = df.filter(pl.col(group_col) == "NASJONALT")

        if national.height == 0:
            return issues

        for col in [metric_col, total_col]:
            if col not in df.columns:
                continue

            region_sum = non_national.select(pl.col(col).sum()).item()
            national_val = national.select(col).item()

            if abs(region_sum - national_val) > 1:  # Tillat avrundingsfeil
                issues.append(ValidationIssue(
                    level="error",
                    message=f"{col}: sum regioner ({region_sum:,}) != nasjonalt ({national_val:,})",
                    suggestion="Sjekk aggregeringlogikk",
                ))

        return issues

    def check_husstander_total(self, total: int) -> list[ValidationIssue]:
        """Sjekk at totalt antall husstander er rimelig."""
        issues = []
        check = self.SANITY_CHECKS["totalt_husstander"]

        if total < check["min"]:
            issues.append(ValidationIssue(
                level="warning",
                message=f"Totalt husstander ({total:,}) lavere enn forventet ({check['min']:,})",
                suggestion="Sjekk filtre - kan mangle data",
            ))
        elif total > check["max"]:
            issues.append(ValidationIssue(
                level="warning",
                message=f"Totalt husstander ({total:,}) høyere enn forventet ({check['max']:,})",
                suggestion="Sjekk for dobbeltelling",
            ))

        return issues


class ErrorPatternMatcher:
    """Match feilmeldinger mot kjente mønstre."""

    KNOWN_ERRORS = [
        {
            "pattern": r"column.*not found",
            "suggestion": "Sjekk kolonnenavn - bruk check_values() for å se tilgjengelige kolonner",
        },
        {
            "pattern": r"no such table",
            "suggestion": "Sjekk filsti - bruk load_dataset() for korrekte stier",
        },
        {
            "pattern": r"divide by zero",
            "suggestion": "Legg til NULLIF eller CASE for å håndtere null-verdier",
        },
        {
            "pattern": r"join.*ambiguous",
            "suggestion": "Bruk tabellalias for å disambiguere kolonner",
        },
        {
            "pattern": r"GROUP BY.*not in.*select",
            "suggestion": "Alle ikke-aggregerte kolonner må være i GROUP BY",
        },
    ]

    def match_error(self, error_msg: str) -> Optional[str]:
        """
        Finn forslag basert på feilmelding.

        Returnerer forslag eller None.
        """
        error_lower = error_msg.lower()

        for known in self.KNOWN_ERRORS:
            if re.search(known["pattern"], error_lower, re.IGNORECASE):
                return known["suggestion"]

        return None


def validate_pre_execution(sql: str) -> list[ValidationIssue]:
    """Convenience-funksjon for pre-execution validering."""
    validator = SQLValidator()
    return validator.check_sql_with_kb(sql)


def validate_result(
    df: pl.DataFrame,
    metric_col: str,
    total_col: str,
    coverage_type: Optional[str] = None,
) -> list[ValidationIssue]:
    """Convenience-funksjon for resultatvalidering."""
    validator = ResultValidator()

    issues = []
    issues.extend(validator.check_coverage_result(df, coverage_type))
    issues.extend(validator.check_totals_match(df, metric_col, total_col))

    # Sjekk total husstander
    if "totalt_hus" in total_col or total_col == "totalt_hus":
        total = df.filter(pl.col("fylke") == "NASJONALT")
        if total.height > 0:
            issues.extend(validator.check_husstander_total(total.select(total_col).item()))

    return issues
