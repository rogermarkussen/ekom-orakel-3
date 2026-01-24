"""
Query Builder DSL for dekningsuttrekk.

Standardisert måte å bygge SQL-spørringer som eliminerer vanlige feil.

Eksempel:
    from library.query_builder import CoverageQuery

    query = CoverageQuery(
        year=2024,
        teknologi=["fiber"],
        populasjon="spredtbygd",
        group_by="fylke"
    )
    sql = query.to_sql()
    result = query.execute()
"""

from dataclasses import dataclass, field
from typing import Literal, Optional

import polars as pl

from library.cache import get_db
from library.fylker import FYLKER_2024, get_fylker


PopulasjonsType = Literal["alle", "tettsted", "spredtbygd"]
GroupByType = Literal["nasjonal", "fylke", "kommune"]
MetrikkType = Literal["husstander", "fritidsboliger", "adresser"]


@dataclass
class CoverageQuery:
    """
    Builder for dekningsspørringer.

    Attributes:
        year: Dataår (2022, 2023, 2024)
        teknologi: Liste med teknologier å inkludere
        hastighet_min: Minimum hastighet i Mbit/s
        populasjon: "alle", "tettsted", eller "spredtbygd"
        group_by: "nasjonal", "fylke", eller "kommune"
        metrikk: "husstander", "fritidsboliger", eller "adresser"
        kun_hc: True for kun Homes Connected (gjelder fiber)
        kun_egen: True for kun egen infrastruktur
        tilbydere: Liste med spesifikke tilbydere
        fylker: Liste med spesifikke fylker
    """

    year: int = 2024
    teknologi: list[str] = field(default_factory=list)
    hastighet_min: Optional[int] = None  # Mbit/s
    populasjon: PopulasjonsType = "alle"
    group_by: GroupByType = "fylke"
    metrikk: MetrikkType = "husstander"
    kun_hc: Optional[bool] = None
    kun_egen: bool = False
    tilbydere: list[str] = field(default_factory=list)
    fylker: list[str] = field(default_factory=list)

    def _metrikk_kolonne(self) -> str:
        """Hent kolonnenavn for metrikk."""
        return {
            "husstander": "hus",
            "fritidsboliger": "fritid",
            "adresser": "1",  # COUNT(*)
        }[self.metrikk]

    def _metrikk_aggregat(self) -> str:
        """Hent aggregat-uttrykk for metrikk."""
        if self.metrikk == "adresser":
            return "COUNT(DISTINCT a.adrid)"
        return f"SUM(a.{self._metrikk_kolonne()})"

    def _build_fbb_filter(self) -> str:
        """Bygg WHERE-klausul for fbb-tabell."""
        conditions = []

        if self.teknologi:
            tek_list = ", ".join(f"'{t}'" for t in self.teknologi)
            conditions.append(f"f.tek IN ({tek_list})")

        if self.hastighet_min:
            kbps = self.hastighet_min * 1000
            conditions.append(f"f.ned >= {kbps}")

        if self.kun_hc is not None:
            conditions.append(f"f.hc = {'true' if self.kun_hc else 'false'}")

        if self.kun_egen:
            conditions.append("f.egen = true")

        if self.tilbydere:
            tilb_list = ", ".join(f"'{t}'" for t in self.tilbydere)
            conditions.append(f"f.tilb IN ({tilb_list})")

        return " AND ".join(conditions) if conditions else "1=1"

    def _build_adr_filter(self) -> str:
        """Bygg WHERE-klausul for adr-tabell."""
        conditions = []

        if self.populasjon == "tettsted":
            conditions.append("a.ertett = true")
        elif self.populasjon == "spredtbygd":
            conditions.append("a.ertett = false")

        if self.fylker:
            fylke_list = ", ".join(f"'{f.upper()}'" for f in self.fylker)
            conditions.append(f"a.fylke IN ({fylke_list})")

        return " AND ".join(conditions) if conditions else "1=1"

    def _build_group_by(self) -> tuple[str, str]:
        """Bygg GROUP BY og SELECT kolonner."""
        if self.group_by == "nasjonal":
            return "'NASJONALT'", ""
        elif self.group_by == "fylke":
            return "a.fylke", "GROUP BY a.fylke"
        else:  # kommune
            return "a.kommune", "GROUP BY a.kommune"

    def to_sql(self) -> str:
        """Generer SQL for spørringen."""
        adr_table = f"'lib/{self.year}/adr.parquet'"
        fbb_table = f"'lib/{self.year}/fbb.parquet'"

        group_col, group_by = self._build_group_by()
        metrikk_agg = self._metrikk_aggregat()
        fbb_filter = self._build_fbb_filter()
        adr_filter = self._build_adr_filter()

        # Bygg CTE for dekning
        cte = f"""
WITH dekket AS (
    SELECT DISTINCT f.adrid
    FROM {fbb_table} f
    WHERE {fbb_filter}
)"""

        # Hovedspørring
        if self.group_by == "nasjonal":
            main_query = f"""
SELECT
    {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) as med_dekning,
    {metrikk_agg} as totalt,
    ROUND(
        {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) * 100.0 / {metrikk_agg},
        1
    ) as prosent
FROM {adr_table} a
LEFT JOIN dekket d ON a.adrid = d.adrid
WHERE {adr_filter}"""
        else:
            # Fylke eller kommune - bruk subquery for å sortere etter UNION
            main_query = f"""
SELECT * FROM (
    SELECT
        {group_col} as {self.group_by},
        {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) as med_dekning,
        {metrikk_agg} as totalt,
        ROUND(
            {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) * 100.0 / {metrikk_agg},
            1
        ) as prosent,
        0 as sort_order
    FROM {adr_table} a
    LEFT JOIN dekket d ON a.adrid = d.adrid
    WHERE {adr_filter}
    {group_by}

    UNION ALL

    SELECT
        'NASJONALT' as {self.group_by},
        {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) as med_dekning,
        {metrikk_agg} as totalt,
        ROUND(
            {metrikk_agg} FILTER (WHERE d.adrid IS NOT NULL) * 100.0 / {metrikk_agg},
            1
        ) as prosent,
        1 as sort_order
    FROM {adr_table} a
    LEFT JOIN dekket d ON a.adrid = d.adrid
    WHERE {adr_filter}
) sub
ORDER BY sort_order, {self.group_by}"""

        return cte + main_query

    def execute(self) -> pl.DataFrame:
        """Kjør spørringen og returner resultat."""
        sql = self.to_sql()
        result = get_db().execute(sql)
        # Fjern intern sort_order kolonne hvis den finnes
        if "sort_order" in result.columns:
            result = result.drop("sort_order")
        return result

    def describe(self) -> str:
        """Beskriv spørringen på norsk."""
        parts = []

        # Metrikk
        parts.append(self.metrikk.capitalize())

        # Teknologi
        if self.teknologi:
            parts.append(f"med {'/'.join(self.teknologi)}")

        # Hastighet
        if self.hastighet_min:
            parts.append(f"≥{self.hastighet_min} Mbit/s")

        # HC/HP
        if self.kun_hc is True:
            parts.append("(kun HC)")
        elif self.kun_hc is False:
            parts.append("(kun HP)")

        # Populasjon
        if self.populasjon != "alle":
            parts.append(f"i {self.populasjon}")

        # Gruppering
        parts.append(f"per {self.group_by}")

        # År
        parts.append(f"({self.year})")

        return " ".join(parts)


@dataclass
class CompetitionQuery:
    """
    Builder for konkurransespørringer (antall tilbydere).
    """

    year: int = 2024
    teknologi: list[str] = field(default_factory=lambda: ["fiber"])
    populasjon: PopulasjonsType = "alle"
    group_by: GroupByType = "fylke"
    metrikk: MetrikkType = "husstander"
    kun_hc: Optional[bool] = None

    def to_sql(self) -> str:
        """Generer SQL for tilbyderkonkurranse."""
        adr_table = f"'lib/{self.year}/adr.parquet'"
        fbb_table = f"'lib/{self.year}/fbb.parquet'"

        tek_filter = ""
        if self.teknologi:
            tek_list = ", ".join(f"'{t}'" for t in self.teknologi)
            tek_filter = f"WHERE tek IN ({tek_list})"
            if self.kun_hc is not None:
                tek_filter += f" AND hc = {'true' if self.kun_hc else 'false'}"

        pop_filter = ""
        if self.populasjon == "tettsted":
            pop_filter = "WHERE a.ertett = true"
        elif self.populasjon == "spredtbygd":
            pop_filter = "WHERE a.ertett = false"

        metrikk_col = "hus" if self.metrikk == "husstander" else "fritid"

        return f"""
WITH tilbydere_per_adresse AS (
    SELECT adrid, COUNT(DISTINCT tilb) as antall_tilb
    FROM {fbb_table}
    {tek_filter}
    GROUP BY adrid
),
kategorisert AS (
    SELECT
        a.fylke,
        a.{metrikk_col},
        CASE
            WHEN t.antall_tilb = 1 THEN '1 tilbyder'
            WHEN t.antall_tilb = 2 THEN '2 tilbydere'
            ELSE '3+ tilbydere'
        END as kategori
    FROM {adr_table} a
    INNER JOIN tilbydere_per_adresse t ON a.adrid = t.adrid
    {pop_filter}
)
SELECT
    fylke as Fylke,
    SUM(CASE WHEN kategori = '1 tilbyder' THEN {metrikk_col} ELSE 0 END) as "1 tilbyder",
    SUM(CASE WHEN kategori = '2 tilbydere' THEN {metrikk_col} ELSE 0 END) as "2 tilbydere",
    SUM(CASE WHEN kategori = '3+ tilbydere' THEN {metrikk_col} ELSE 0 END) as "3+ tilbydere",
    SUM({metrikk_col}) as totalt
FROM kategorisert
GROUP BY fylke

UNION ALL

SELECT
    'NASJONALT',
    SUM(CASE WHEN kategori = '1 tilbyder' THEN {metrikk_col} ELSE 0 END),
    SUM(CASE WHEN kategori = '2 tilbydere' THEN {metrikk_col} ELSE 0 END),
    SUM(CASE WHEN kategori = '3+ tilbydere' THEN {metrikk_col} ELSE 0 END),
    SUM({metrikk_col})
FROM kategorisert

ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
"""

    def execute(self) -> pl.DataFrame:
        """Kjør spørringen."""
        return get_db().execute(self.to_sql())


@dataclass
class HistoricalQuery:
    """
    Builder for historiske trender (teknologi).

    Bruker dekning_tek.parquet med data fra 2013-2024.
    """

    start_year: int = 2016
    end_year: int = 2024
    teknologi: list[str] = field(default_factory=lambda: ["fiber"])
    geo: str = "totalt"  # "totalt", "tettbygd", "spredtbygd"
    fylke: str = "NASJONALT"

    def to_sql(self) -> str:
        """Generer SQL for historisk trend."""
        tek_list = ", ".join(f"'{t}'" for t in self.teknologi)

        return f"""
SELECT
    ar as år,
    tek as teknologi,
    ROUND(dekning * 100, 1) as prosent
FROM 'lib/dekning_tek.parquet'
WHERE fylke = '{self.fylke}'
  AND geo = '{self.geo}'
  AND ar BETWEEN {self.start_year} AND {self.end_year}
  AND tek IN ({tek_list})
ORDER BY ar, tek
"""

    def execute(self) -> pl.DataFrame:
        """Kjør spørringen."""
        return get_db().execute(self.to_sql())


@dataclass
class HistoricalSpeedQuery:
    """
    Builder for historiske hastighetsdata (dekning_hast.parquet).

    Støtter år 2010-2024 med hastighetsklasser (ned/opp i Mbit/s).

    Attributes:
        start_year: Første år (default 2010)
        end_year: Siste år (default 2024)
        ned: Nedlastingshastighet i Mbit/s (default 100)
        opp: Opplastingshastighet i Mbit/s (default 100)
        geo: "totalt", "tettbygd", eller "spredtbygd"
        fylke: Fylkesnavn eller "NASJONALT"
    """

    start_year: int = 2010
    end_year: int = 2024
    ned: int = 100  # Nedlastingshastighet i Mbit/s
    opp: int = 100  # Opplastingshastighet i Mbit/s
    geo: str = "totalt"  # "totalt", "tettbygd", "spredtbygd"
    fylke: str = "NASJONALT"

    def to_sql(self) -> str:
        """Generer SQL for historisk hastighetsdata."""
        return f"""
SELECT
    ar as år,
    ROUND(dekning * 100, 1) as prosent
FROM 'lib/dekning_hast.parquet'
WHERE fylke = '{self.fylke}'
  AND geo = '{self.geo}'
  AND ned = {self.ned}
  AND opp = {self.opp}
  AND ar BETWEEN {self.start_year} AND {self.end_year}
ORDER BY ar
"""

    def execute(self) -> pl.DataFrame:
        """Kjør spørringen og returner resultat."""
        return get_db().execute(self.to_sql())

    def describe(self) -> str:
        """Beskriv spørringen på norsk."""
        parts = [f"Hastighet ≥{self.ned}/{self.opp} Mbit/s"]

        if self.geo != "totalt":
            parts.append(f"i {self.geo}")

        if self.fylke != "NASJONALT":
            parts.append(f"for {self.fylke}")

        parts.append(f"({self.start_year}-{self.end_year})")

        return " ".join(parts)


def quick_coverage(
    teknologi: str | list[str],
    year: int = 2024,
    populasjon: PopulasjonsType = "alle",
    hc_only: bool = False,
) -> pl.DataFrame:
    """
    Rask dekningssjekk for én teknologi.

    Eksempel:
        quick_coverage("fiber")
        quick_coverage("5g", populasjon="spredtbygd")
    """
    if isinstance(teknologi, str):
        teknologi = [teknologi]

    query = CoverageQuery(
        year=year,
        teknologi=teknologi,
        populasjon=populasjon,
        kun_hc=True if hc_only else None,
    )

    return query.execute()


# --- Abonnementspørringer (ab.parquet) ---


SubscriptionGroupByType = Literal["nasjonal", "fylke", "kommune", "tilbyder"]


@dataclass
class SubscriptionQuery:
    """
    Query builder for ab.parquet - teller rader (abonnementer), ikke husstander.

    VIKTIG: ab.parquet skal IKKE joines med adr - bruk fylke/komnavn direkte.
    Tell COUNT(*) rader, IKKE SUM(hus).

    Attributes:
        year: Dataår (2022, 2023, 2024)
        teknologi: Liste med teknologier å inkludere
        privat: True=privat, False=bedrift, None=begge
        kol: True=MDU (kollektiv), False=SDU (enkeltbolig), None=begge
        kun_koblet: Kun adresser med adrid > 0
        group_by: "nasjonal", "fylke", "kommune", eller "tilbyder"
        tilbydere: Liste med spesifikke tilbydere
        fylker: Liste med spesifikke fylker
    """

    year: int = 2024
    teknologi: list[str] = field(default_factory=list)
    privat: Optional[bool] = None  # True=privat, False=bedrift, None=begge
    kol: Optional[bool] = None  # True=MDU, False=SDU, None=begge
    kun_koblet: bool = False  # Kun adrid > 0
    group_by: SubscriptionGroupByType = "fylke"
    tilbydere: list[str] = field(default_factory=list)
    fylker: list[str] = field(default_factory=list)

    def _build_filter(self) -> str:
        """Bygg WHERE-klausul."""
        conditions = []

        if self.teknologi:
            tek_list = ", ".join(f"'{t}'" for t in self.teknologi)
            conditions.append(f"tek IN ({tek_list})")

        if self.privat is not None:
            conditions.append(f"privat = {'true' if self.privat else 'false'}")

        if self.kol is not None:
            conditions.append(f"kol = {'true' if self.kol else 'false'}")

        if self.kun_koblet:
            conditions.append("adrid > 0")

        if self.tilbydere:
            tilb_list = ", ".join(f"'{t}'" for t in self.tilbydere)
            conditions.append(f"tilb IN ({tilb_list})")

        if self.fylker:
            fylke_list = ", ".join(f"'{f.upper()}'" for f in self.fylker)
            conditions.append(f"fylke IN ({fylke_list})")

        return " AND ".join(conditions) if conditions else "1=1"

    def _build_group_col(self) -> str:
        """Hent kolonne for gruppering."""
        return {
            "nasjonal": "'NASJONALT'",
            "fylke": "fylke",
            "kommune": "komnavn",
            "tilbyder": "tilb",
        }[self.group_by]

    def to_sql(self) -> str:
        """Generer SQL for spørringen."""
        ab_table = f"'lib/{self.year}/ab.parquet'"
        filter_clause = self._build_filter()
        group_col = self._build_group_col()

        if self.group_by == "nasjonal":
            return f"""
SELECT
    'NASJONALT' as gruppe,
    COUNT(*) as antall_ab
FROM {ab_table}
WHERE {filter_clause}
"""
        else:
            return f"""
SELECT * FROM (
    SELECT
        {group_col} as {self.group_by},
        COUNT(*) as antall_ab,
        0 as sort_order
    FROM {ab_table}
    WHERE {filter_clause}
    GROUP BY {group_col}

    UNION ALL

    SELECT
        'NASJONALT' as {self.group_by},
        COUNT(*) as antall_ab,
        1 as sort_order
    FROM {ab_table}
    WHERE {filter_clause}
) sub
ORDER BY sort_order, {self.group_by}
"""

    def execute(self) -> pl.DataFrame:
        """Kjør spørringen og returner resultat."""
        sql = self.to_sql()
        result = get_db().execute(sql)
        # Fjern intern sort_order kolonne hvis den finnes
        if "sort_order" in result.columns:
            result = result.drop("sort_order")
        return result

    def describe(self) -> str:
        """Beskriv spørringen på norsk."""
        parts = ["Abonnementer"]

        if self.teknologi:
            parts.append(f"({'/'.join(self.teknologi)})")

        if self.privat is True:
            parts.append("privat")
        elif self.privat is False:
            parts.append("bedrift")

        if self.kol is True:
            parts.append("kollektiv (MDU)")
        elif self.kol is False:
            parts.append("enkeltbolig (SDU)")

        parts.append(f"per {self.group_by}")
        parts.append(f"({self.year})")

        return " ".join(parts)


def quick_ab(
    teknologi: str | list[str] | None = None,
    year: int = 2024,
    privat: Optional[bool] = None,
    group_by: SubscriptionGroupByType = "fylke",
) -> pl.DataFrame:
    """
    Rask abonnementssjekk.

    Eksempel:
        quick_ab("fiber")
        quick_ab("fiber", privat=True)
        quick_ab(group_by="tilbyder")
    """
    tek_list = []
    if teknologi:
        tek_list = [teknologi] if isinstance(teknologi, str) else teknologi

    query = SubscriptionQuery(
        year=year,
        teknologi=tek_list,
        privat=privat,
        group_by=group_by,
    )

    return query.execute()
