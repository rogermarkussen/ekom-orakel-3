"""
EkomQuery Builder - DSL for ekom.parquet-spørringer.

Håndterer automatisk:
- tp='Sum' filter (med unntak for fylkesdata)
- sk IN ('Sluttbruker', 'Ingen') filter
- Datakommunikasjon for FBB Bedrift
- Pivot-transformasjon (år på kolonner)
- Fylkesfordeling for mobil (2025+)

Eksempel:
    from library.ekom_query import EkomQuery

    # Enkel spørring
    query = EkomQuery(
        hk="Fast bredbånd",
        hg="Abonnement",
        tek="Fiber",
        rapport=["2022-Helår", "2023-Helår", "2024-Helår"],
        pivot_years=True
    )
    df = query.execute()

    # FBB Bedrift (auto-inkluderer Datakommunikasjon)
    query = EkomQuery(hk="Fast bredbånd", ms="Bedrift", hg="Abonnement")
    sql = query.to_sql()  # hk IN ('Fast bredbånd', 'Datakommunikasjon')
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

import polars as pl

from library.cache import get_db
from library.knowledge import KnowledgeBase


# Tilgjengelige fylker for mobilabonnement (fra 2025-Halvår)
MOBIL_FYLKER = [
    "Agder", "Akershus", "Buskerud", "Finnmark", "Innlandet",
    "Møre og Romsdal", "Nordland", "Oslo", "Rogaland", "Telemark",
    "Troms", "Trøndelag", "Vestfold", "Vestland", "Østfold"
]

HgType = Literal["Abonnement", "Inntekter", "Trafikk"]
DelarType = Literal["Halvår", "Helår"]


@dataclass
class EkomQuery:
    """
    Builder for ekom-spørringer med innebygde regler.

    Attributes:
        hk: Hovedkategori ('Fast bredbånd', 'Mobiltjenester', etc.)
        hg: Hovedgruppe/metrikk ('Abonnement', 'Inntekter', 'Trafikk')
        dk: Delkategori (valgfri, f.eks. 'Mobiltelefoni')
        ms: Markedssegment ('Privat', 'Bedrift', None for begge)
        tek: Teknologi (valgfri, f.eks. 'Fiber', 'DSL')
        tilbyder: Tilbydernavn (fusnavn)
        n1: Første nivåsplitt (valgfri)
        rapport: Rapportperiode(r) (f.eks. '2024-Helår' eller liste)
        delar: 'Halvår' eller 'Helår'
        ar: År eller liste med år
        fylke: For mobilabonnement fylkesfordeling (2025+)

        # Formatering
        pivot_years: True for år på kolonner (standard True)
        group_by: Kolonner for gruppering/rader

        # Auto-regler
        include_datakom: Auto for FBB Bedrift (standard True)
        include_grossist: Inkluder grossist-tall (standard False)
    """

    # Hovedfiltre
    hk: str | list[str]
    hg: HgType = "Abonnement"
    dk: Optional[str] = None
    ms: Optional[str] = None
    tek: Optional[str] = None
    tilbyder: Optional[str] = None
    n1: Optional[str] = None

    # Tidsfiltre
    rapport: Optional[str | list[str]] = None
    delar: Optional[DelarType] = None
    ar: Optional[int | list[int]] = None

    # Fylkesfordeling (mobil 2025+)
    fylke: Optional[str] = None

    # Formatering
    pivot_years: bool = True
    group_by: list[str] = field(default_factory=list)

    # Auto-regler
    include_datakom: bool = True  # Auto for FBB Bedrift
    include_grossist: bool = False

    # Forretningsdefinisjon
    definition: Optional[str] = None  # Navn på forretningsdefinisjon fra KB

    def __post_init__(self):
        """Normaliser input og stopp kjente feilmønstre tidlig."""
        self.group_by = list(self.group_by)
        self._validate_query()

    def _is_mobilabonnement_fylkesfordeling(self) -> bool:
        """Semantisk fylkesfordeling for mobilabonnement."""
        return self.fylke is not None or "fylke" in self.group_by

    def _parse_report_period(self) -> tuple[int, str] | None:
        """Hent (år, delar) fra eksplisitt rapport, hvis mulig."""
        if isinstance(self.rapport, str):
            year_str, _, delar = self.rapport.partition("-")
            if year_str.isdigit() and delar in {"Halvår", "Helår"}:
                return int(year_str), delar
        if isinstance(self.ar, int) and self.delar:
            return self.ar, self.delar
        return None

    def _validate_query(self):
        """Valider kombinasjoner som ellers lett gir misvisende tall."""
        if not self._is_mobilabonnement_fylkesfordeling():
            return

        hk_list = [self.hk] if isinstance(self.hk, str) else list(self.hk)
        if hk_list != ["Mobiltjenester"]:
            raise ValueError("Fylkesfordeling støttes bare for mobilabonnement under hk='Mobiltjenester'.")

        if self.dk != "Mobiltelefoni" or self.hg != "Abonnement":
            raise ValueError(
                "Fylkesfordeling krever dk='Mobiltelefoni' og hg='Abonnement'."
            )

        if self.n1 is not None:
            raise ValueError(
                "Bruk 'fylke' eller group_by=['fylke'] for mobil fylkesfordeling, ikke rå n1."
            )

        parsed_period = self._parse_report_period()
        if parsed_period is None:
            raise ValueError(
                "Mobilabonnement per fylke krever en eksplisitt rapportperiode fra og med 2025-Halvår."
            )

        year, delar = parsed_period
        if year < 2025:
            raise ValueError(
                "Mobilabonnement per fylke er bare tilgjengelig fra og med 2025-Halvår."
            )

    def _should_include_datakom(self) -> bool:
        """Sjekk om Datakommunikasjon skal inkluderes automatisk."""
        if not self.include_datakom:
            return False

        # Kun for Fast bredbånd
        hk_list = [self.hk] if isinstance(self.hk, str) else self.hk
        if "Fast bredbånd" not in hk_list:
            return False

        # Kun for Bedrift eller samlet (ikke eksplisitt Privat)
        if self.ms == "Privat":
            return False

        return True

    def _get_definition_filters(self) -> dict:
        """Hent filtre fra forretningsdefinisjon."""
        if not self.definition:
            return {}

        kb = KnowledgeBase()
        defn = kb.get_definition(self.definition)
        if not defn:
            return {}

        # Sjekk at definisjonen gjelder for ekom
        if defn.applies_to not in ("ekom", "both"):
            return {}

        return defn.filters

    def _is_fylke_query(self) -> bool:
        """Sjekk om dette er en fylkesfordeling-query."""
        return self._is_mobilabonnement_fylkesfordeling()

    def _resolve_group_by_column(self, column: str) -> tuple[str, str, str]:
        """Map semantiske grupperinger til faktiske kolonner."""
        if column == "fylke":
            return "n1 as fylke", "n1", "n1"
        return column, column, column

    def _get_tp_filter(self) -> str:
        """Hent riktig tp-filter basert på query-type."""
        if self._is_fylke_query():
            # Fylkesdata har alltid tp='Herav'
            return "tp = 'Herav'"
        return "tp = 'Sum'"

    def _get_sk_filter(self) -> str:
        """Hent sk-filter."""
        if self.include_grossist:
            return "1=1"  # Ingen filter
        return "sk IN ('Sluttbruker', 'Ingen')"

    def _build_hk_filter(self) -> str:
        """Bygg hk-filter med Datakommunikasjon hvis relevant."""
        hk_list = [self.hk] if isinstance(self.hk, str) else list(self.hk)

        if self._should_include_datakom() and "Datakommunikasjon" not in hk_list:
            hk_list.append("Datakommunikasjon")

        if len(hk_list) == 1:
            return f"hk = '{hk_list[0]}'"
        else:
            hk_str = ", ".join(f"'{h}'" for h in hk_list)
            return f"hk IN ({hk_str})"

    def _build_rapport_filter(self) -> str:
        """Bygg rapport-filter."""
        if self.rapport is None:
            return ""

        if isinstance(self.rapport, str):
            return f"rapport = '{self.rapport}'"
        else:
            rapport_str = ", ".join(f"'{r}'" for r in self.rapport)
            return f"rapport IN ({rapport_str})"

    def _build_ar_filter(self) -> str:
        """Bygg år-filter."""
        if self.ar is None:
            return ""

        if isinstance(self.ar, int):
            return f"ar = {self.ar}"
        else:
            ar_str = ", ".join(str(a) for a in self.ar)
            return f"ar IN ({ar_str})"

    def _build_where_clause(self) -> str:
        """Bygg komplett WHERE-klausul."""
        # Hent definisjonsfiltre først
        def_filters = self._get_definition_filters()

        # Bruk definisjonens tp/sk hvis de finnes, ellers standard
        tp_filter = f"tp = '{def_filters['tp']}'" if 'tp' in def_filters else self._get_tp_filter()
        sk_filter = f"sk = '{def_filters['sk']}'" if 'sk' in def_filters else self._get_sk_filter()

        conditions = [
            self._build_hk_filter(),
            f"hg = '{self.hg}'",
            tp_filter,
            sk_filter,
        ]

        # Ekskluder hk-verdier fra definisjon (f.eks. hk_not: "TV-tjenester")
        if 'hk_not' in def_filters:
            hk_not = def_filters['hk_not']
            if isinstance(hk_not, list):
                hk_not_str = ", ".join(f"'{h}'" for h in hk_not)
                conditions.append(f"hk NOT IN ({hk_not_str})")
            else:
                conditions.append(f"hk != '{hk_not}'")

        # Valgfrie filtre (eksplisitte parametere overskriver definisjon)
        dk = self.dk or def_filters.get('dk')
        if dk:
            conditions.append(f"dk = '{dk}'")

        ms = self.ms or def_filters.get('ms')
        if ms:
            conditions.append(f"ms = '{ms}'")

        tek = self.tek or def_filters.get('tek')
        if tek:
            conditions.append(f"tek = '{tek}'")

        if self.tilbyder:
            conditions.append(f"fusnavn = '{self.tilbyder}'")

        if self.n1:
            conditions.append(f"n1 = '{self.n1}'")

        # Fylkesfilter (for mobil)
        if self.fylke is not None:
            conditions.append(f"n1 = '{self.fylke}'")
        elif self._is_mobilabonnement_fylkesfordeling():
            fylker = ", ".join(f"'{f}'" for f in MOBIL_FYLKER)
            conditions.append(f"n1 IN ({fylker})")

        # Tidsfiltre
        rapport_filter = self._build_rapport_filter()
        if rapport_filter:
            conditions.append(rapport_filter)

        ar_filter = self._build_ar_filter()
        if ar_filter:
            conditions.append(ar_filter)

        if self.delar:
            conditions.append(f"delar = '{self.delar}'")

        return " AND ".join(conditions)

    def _build_select_columns(self) -> list[str]:
        """Bestem hvilke kolonner som skal selekteres."""
        # Standard: rapport/ar + verdi
        columns = []

        # Tidskolonne
        if self.delar and not self.rapport:
            columns.append("ar")
        else:
            columns.append("rapport")

        # Brukerdefinerte grupperinger
        for col in self.group_by:
            select_expr, _, _ = self._resolve_group_by_column(col)
            if select_expr not in columns:
                columns.append(select_expr)

        # Verdi
        columns.append("ROUND(SUM(svar), 0) as svar")

        return columns

    def _build_group_by(self) -> str:
        """Bygg GROUP BY-klausul."""
        group_cols = []

        # Tidskolonne
        if self.delar and not self.rapport:
            group_cols.append("ar")
        else:
            group_cols.append("rapport")

        # Brukerdefinerte grupperinger
        for col in self.group_by:
            _, group_expr, _ = self._resolve_group_by_column(col)
            if group_expr not in group_cols:
                group_cols.append(group_expr)

        return "GROUP BY " + ", ".join(group_cols)

    def _build_order_by(self) -> str:
        """Bygg ORDER BY-klausul."""
        order_cols = []

        # Tidskolonne først
        if self.delar and not self.rapport:
            order_cols.append("ar")
        else:
            order_cols.append("rapport")

        # Andre kolonner
        for col in self.group_by:
            _, _, order_expr = self._resolve_group_by_column(col)
            if order_expr not in order_cols:
                order_cols.append(order_expr)

        return "ORDER BY " + ", ".join(order_cols)

    def to_sql(self) -> str:
        """
        Generer SQL for spørringen.

        Returns:
            SQL-streng klar til kjøring
        """
        select_cols = self._build_select_columns()
        where_clause = self._build_where_clause()
        group_by = self._build_group_by()
        order_by = self._build_order_by()

        sql = f"""
SELECT
    {', '.join(select_cols)}
FROM 'lib/ekom.parquet'
WHERE {where_clause}
{group_by}
{order_by}
"""
        return sql.strip()

    def _pivot_result(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Transformer til år/rapport på kolonner.

        Args:
            df: DataFrame med resultat

        Returns:
            Pivotet DataFrame med tidsperioder som kolonner
        """
        if df.height == 0:
            return df

        # Finn tidskolonnen
        time_col = "ar" if "ar" in df.columns else "rapport"

        # Finn indekskolonner (alt unntatt tid og svar)
        index_cols = [c for c in df.columns if c not in [time_col, "svar"]]

        if not index_cols:
            # Ingen grupperinger - manuell transponer til én rad
            # Konverter fra lange format til brede
            result_dict = {}
            for row in df.iter_rows(named=True):
                result_dict[str(row[time_col])] = row["svar"]
            return pl.DataFrame([result_dict])

        return df.pivot(
            on=time_col,
            index=index_cols,
            values="svar"
        ).sort(index_cols)

    def execute(self) -> pl.DataFrame:
        """
        Kjør spørringen og returner resultat.

        Returns:
            DataFrame med resultat (pivotet hvis pivot_years=True)
        """
        sql = self.to_sql()
        db = get_db()
        df = db.execute(sql)

        # Pivot hvis ønsket
        if self.pivot_years and (
            (isinstance(self.rapport, list) and len(self.rapport) > 1) or
            (isinstance(self.ar, list) and len(self.ar) > 1) or
            (self.delar and not self.rapport and not isinstance(self.ar, int))
        ):
            df = self._pivot_result(df)

        return df

    def describe(self) -> str:
        """Beskriv spørringen på norsk."""
        parts = []

        # Hovedkategori
        hk_list = [self.hk] if isinstance(self.hk, str) else self.hk
        parts.append(" + ".join(hk_list))

        # Metrikk
        parts.append(f"({self.hg})")

        # Markedssegment
        if self.ms:
            parts.append(f"- {self.ms}")

        # Teknologi
        if self.tek:
            parts.append(f"- {self.tek}")

        # Tidsperiode
        if self.rapport:
            if isinstance(self.rapport, list):
                parts.append(f"[{self.rapport[0]} - {self.rapport[-1]}]")
            else:
                parts.append(f"[{self.rapport}]")
        elif self.delar:
            parts.append(f"[{self.delar}]")

        # Fylke
        if self.fylke:
            parts.append(f"(fylke: {self.fylke})")

        return " ".join(parts)


def quick_ekom(
    hk: str,
    hg: HgType = "Abonnement",
    rapport: Optional[str] = None,
    **kwargs
) -> pl.DataFrame:
    """
    Rask ekom-spørring for enkle tilfeller.

    Args:
        hk: Hovedkategori
        hg: Hovedgruppe (default: Abonnement)
        rapport: Rapportperiode (default: siste tilgjengelige)
        **kwargs: Andre EkomQuery-parametre

    Returns:
        DataFrame med resultat

    Eksempel:
        quick_ekom("Mobiltjenester", rapport="2024-Helår")
    """
    query = EkomQuery(hk=hk, hg=hg, rapport=rapport, **kwargs)
    return query.execute()
