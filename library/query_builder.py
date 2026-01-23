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
    Builder for historiske trender.
    """

    start_year: int = 2016
    end_year: int = 2024
    teknologi: list[str] = field(default_factory=lambda: ["fiber"])
    geo: str = "totalt"  # "totalt", "tettsted", "spredtbygd"
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
