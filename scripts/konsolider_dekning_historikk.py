"""
Konsoliderer all dekningshistorikk til to filer:
- lib/dekning_tek.parquet (teknologidekning)
- lib/dekning_hast.parquet (hastighetsdekning)

Datakilder:
- 2007-2011: eldre_nasjonal_2007_2011.parquet (begrenset)
- 2010: eldre_fylke_2010.parquet, eldre_speed_2010.parquet
- 2012-2020: historikk_speed_nasjonalt.parquet
- 2013-2020: historikk_tek_nasjonalt.parquet
- 2016-2017: eldre_tek_fylke_2016_2017.parquet, eldre_speed_fylke_2016_2017.parquet
- 2016-2020: historikk_tek_geo_nasjonalt.parquet
- 2018-2020: historikk_tek_fylke.parquet, eldre_fylke_2018_2020.parquet
- 2021: 2021/dekning_fylke.parquet
- 2022-2024: Beregnet fra fbb.parquet + adr.parquet
"""

import polars as pl
from pathlib import Path

LIB = Path("lib")


def normalize_fylke(fylke: str) -> str:
    """Normaliser fylkesnavn til konsistent format."""
    if fylke is None:
        return "NASJONALT"
    # Fjern non-breaking spaces og andre unicode-spaces
    fylke = fylke.replace("\u00a0", " ")  # Non-breaking space
    fylke = " ".join(fylke.split())  # Normaliser alle whitespace
    fylke = fylke.upper().strip()
    # Nasjonale tall
    if fylke in ("NORGE TOTALT", "HELE NORGE", "NORGE", "NASJONALT"):
        return "NASJONALT"
    # Avkortede navn fra kildedata
    truncated = {
        "MØRE OG ROMSD": "MØRE OG ROMSDAL",
        "SOGN OG FJORDA": "SOGN OG FJORDANE",
    }
    return truncated.get(fylke, fylke)


def normalize_geo(geo: str) -> str:
    """Normaliser geo-verdier."""
    if geo is None:
        return "totalt"
    geo = geo.lower().strip()
    if geo in ("tettsted", "tettbygd"):
        return "tettbygd"
    if geo in ("utkant", "spredtbygd"):
        return "spredtbygd"
    return "totalt"


def normalize_tek(tek: str) -> str:
    """Normaliser teknologinavn."""
    mapping = {
        "FTTH": "fiber",
        "fiber": "fiber",
        "HFC": "kabel",
        "hfc": "kabel",
        "kabel": "kabel",
        "FTTH + HFC": "fiber_kabel",
        "fiber_hfc": "fiber_kabel",
        "FTTH + HFC + VDSL": "fiber_kabel_dsl",
        "FWA": "ftb",
        "ftb": "ftb",
        "VDSL": "dsl",
        "xDSL": "dsl",
        "VDSL + ADSL": "dsl",
        "dsl": "dsl",
        "LTE inne": "4g_inne",
        "LTE ute": "4g_ute",
        "LTE ute med antenne": "4g_antenne",
        "lte_inne": "4g_inne",
        "lte_ute": "4g_ute",
        "lte_antenne": "4g_antenne",
        "5G": "5g",
        "g5_inne": "5g_inne",
        "g5_ute": "5g_ute",
        "g5_antenne": "5g_antenne",
        "kabelbasert": "kabelbasert",
        "wifi": "wifi",
    }
    return mapping.get(tek, tek.lower() if tek else tek)


# =============================================================================
# TEKNOLOGIDEKNING
# =============================================================================


def load_tek_nasjonalt_2013_2020() -> pl.DataFrame:
    """historikk_tek_nasjonalt.parquet - Nasjonalt 2013-2020."""
    df = pl.read_parquet(LIB / "historikk_tek_nasjonalt.parquet")
    return df.select(
        pl.col("ar").cast(pl.Int32),
        pl.lit("NASJONALT").alias("fylke"),
        pl.lit("totalt").alias("geo"),
        pl.col("tek").map_elements(normalize_tek, return_dtype=pl.Utf8).alias("tek"),
        pl.col("dekning"),
    )


def load_tek_geo_nasjonalt_2016_2020() -> pl.DataFrame:
    """historikk_tek_geo_nasjonalt.parquet - Tettsted/Utkant 2016-2020."""
    df = pl.read_parquet(LIB / "historikk_tek_geo_nasjonalt.parquet")
    return df.select(
        pl.col("ar").cast(pl.Int32),
        pl.lit("NASJONALT").alias("fylke"),
        pl.col("geo").map_elements(normalize_geo, return_dtype=pl.Utf8).alias("geo"),
        pl.col("tek").map_elements(normalize_tek, return_dtype=pl.Utf8).alias("tek"),
        pl.col("dekning"),
    )


def load_tek_fylke_2016_2017() -> pl.DataFrame:
    """eldre_tek_fylke_2016_2017.parquet - Per fylke 2016-2017."""
    df = pl.read_parquet(LIB / "eldre_tek_fylke_2016_2017.parquet")
    # Filen har wide format: fylke, ar, vdsl, hfc, fiber, fiber_hfc
    # Melt til long format
    rows = []
    for row in df.iter_rows(named=True):
        fylke = normalize_fylke(row["fylke"])
        ar = int(row["ar"])
        for tek, val in [
            ("dsl", row.get("vdsl")),
            ("kabel", row.get("hfc")),
            ("fiber", row.get("fiber")),
            ("fiber_kabel", row.get("fiber_hfc")),
        ]:
            if val is not None:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": fylke,
                        "geo": "totalt",
                        "tek": tek,
                        "dekning": val / 100.0 if val > 1 else val,
                    }
                )
    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


def load_tek_fylke_2018_2020_historikk() -> pl.DataFrame:
    """historikk_tek_fylke.parquet - Per fylke 2018-2020."""
    df = pl.read_parquet(LIB / "historikk_tek_fylke.parquet")
    return df.select(
        pl.col("ar").cast(pl.Int32),
        pl.col("fylke").map_elements(normalize_fylke, return_dtype=pl.Utf8).alias("fylke"),
        pl.lit("totalt").alias("geo"),
        pl.col("tek").map_elements(normalize_tek, return_dtype=pl.Utf8).alias("tek"),
        pl.col("dekning"),
    )


def load_tek_fylke_2018_2020_eldre() -> pl.DataFrame:
    """eldre_fylke_2018_2020.parquet - Fiber/HFC per fylke."""
    df = pl.read_parquet(LIB / "eldre_fylke_2018_2020.parquet")
    rows = []
    for row in df.iter_rows(named=True):
        fylke = normalize_fylke(row["fylke"])
        ar = int(row["ar"])
        for tek, val in [
            ("fiber", row.get("fiber")),
            ("kabel", row.get("hfc")),
            ("kabelbasert", row.get("kabelbasert")),
        ]:
            if val is not None:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": fylke,
                        "geo": "totalt",
                        "tek": tek,
                        "dekning": val / 100.0 if val > 1 else val,
                    }
                )
    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


def load_tek_2021() -> pl.DataFrame:
    """2021/dekning_fylke.parquet - Full dekning 2021."""
    df = pl.read_parquet(LIB / "2021/dekning_fylke.parquet")
    rows = []
    tek_cols = [
        ("fiber", "fiber"),
        ("hfc", "kabel"),
        ("fiber_hfc", "fiber_kabel"),
        ("dsl", "dsl"),
        ("ftb", "ftb"),
        ("lte_inne", "4g_inne"),
        ("lte_ute", "4g_ute"),
        ("lte_antenne", "4g_antenne"),
        ("g5_inne", "5g_inne"),
        ("g5_ute", "5g_ute"),
        ("g5_antenne", "5g_antenne"),
        ("kabelbasert", "kabelbasert"),
        ("wifi", "wifi"),
    ]
    for row in df.iter_rows(named=True):
        fylke = normalize_fylke(row["fylke"])
        geo = normalize_geo(row["geo"])
        for col, tek in tek_cols:
            val = row.get(col)
            if val is not None:
                rows.append(
                    {"ar": 2021, "fylke": fylke, "geo": geo, "tek": tek, "dekning": val}
                )
    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


def beregn_tek_2022_2024() -> pl.DataFrame:
    """Beregn teknologidekning fra fbb + adr for 2022-2024."""
    rows = []
    teknologier = ["fiber", "ftb", "kabel", "radio", "satellitt"]

    for ar in [2022, 2023, 2024]:
        print(f"  Beregner tek-dekning for {ar}...")
        adr = pl.read_parquet(LIB / str(ar) / "adr.parquet")
        fbb = pl.read_parquet(LIB / str(ar) / "fbb.parquet")

        # Total husstander per fylke og geo
        totaler = (
            adr.group_by(["fylke", "ertett"])
            .agg(pl.col("hus").sum().alias("totalt_hus"))
            .collect()
            if isinstance(adr, pl.LazyFrame)
            else adr.group_by(["fylke", "ertett"]).agg(
                pl.col("hus").sum().alias("totalt_hus")
            )
        )

        # Nasjonal total
        nasjonalt_total = adr.select(pl.col("hus").sum()).item()
        nasjonalt_tett = (
            adr.filter(pl.col("ertett") == True).select(pl.col("hus").sum()).item()
        )
        nasjonalt_spredt = (
            adr.filter(pl.col("ertett") == False).select(pl.col("hus").sum()).item()
        )

        for tek in teknologier:
            # Finn adresser med denne teknologien
            tek_adrid = fbb.filter(pl.col("tek") == tek).select("adrid").unique()

            # Join med adr for å få hus-telling
            adr_med_tek = adr.join(tek_adrid, on="adrid", how="semi")

            # Nasjonalt totalt
            hus_tek = adr_med_tek.select(pl.col("hus").sum()).item()
            if hus_tek and nasjonalt_total:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "totalt",
                        "tek": tek,
                        "dekning": hus_tek / nasjonalt_total,
                    }
                )

            # Nasjonalt tettbygd
            hus_tett = (
                adr_med_tek.filter(pl.col("ertett") == True)
                .select(pl.col("hus").sum())
                .item()
            )
            if hus_tett and nasjonalt_tett:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "tettbygd",
                        "tek": tek,
                        "dekning": hus_tett / nasjonalt_tett,
                    }
                )

            # Nasjonalt spredtbygd
            hus_spredt = (
                adr_med_tek.filter(pl.col("ertett") == False)
                .select(pl.col("hus").sum())
                .item()
            )
            if hus_spredt and nasjonalt_spredt:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "spredtbygd",
                        "tek": tek,
                        "dekning": hus_spredt / nasjonalt_spredt,
                    }
                )

            # Per fylke (kun totalt for å holde størrelsen nede)
            fylke_tek = (
                adr_med_tek.group_by("fylke").agg(pl.col("hus").sum().alias("hus_tek"))
            )
            fylke_total = adr.group_by("fylke").agg(
                pl.col("hus").sum().alias("totalt_hus")
            )
            fylke_dekning = fylke_tek.join(fylke_total, on="fylke")

            for row in fylke_dekning.iter_rows(named=True):
                if row["totalt_hus"] and row["totalt_hus"] > 0:
                    rows.append(
                        {
                            "ar": ar,
                            "fylke": row["fylke"],
                            "geo": "totalt",
                            "tek": tek,
                            "dekning": row["hus_tek"] / row["totalt_hus"],
                        }
                    )

        # Mobildekning (kun 2023-2024)
        if ar >= 2023:
            mob = pl.read_parquet(LIB / str(ar) / "mob.parquet")
            for tek_mob in ["4g", "5g"]:
                mob_adrid = mob.filter(pl.col("tek") == tek_mob).select("adrid").unique()
                adr_med_mob = adr.join(mob_adrid, on="adrid", how="semi")

                # Nasjonalt
                hus_mob = adr_med_mob.select(pl.col("hus").sum()).item()
                if hus_mob and nasjonalt_total:
                    rows.append(
                        {
                            "ar": ar,
                            "fylke": "NASJONALT",
                            "geo": "totalt",
                            "tek": tek_mob,
                            "dekning": hus_mob / nasjonalt_total,
                        }
                    )

                # Tettbygd/spredtbygd
                hus_tett = (
                    adr_med_mob.filter(pl.col("ertett") == True)
                    .select(pl.col("hus").sum())
                    .item()
                )
                hus_spredt = (
                    adr_med_mob.filter(pl.col("ertett") == False)
                    .select(pl.col("hus").sum())
                    .item()
                )
                if hus_tett and nasjonalt_tett:
                    rows.append(
                        {
                            "ar": ar,
                            "fylke": "NASJONALT",
                            "geo": "tettbygd",
                            "tek": tek_mob,
                            "dekning": hus_tett / nasjonalt_tett,
                        }
                    )
                if hus_spredt and nasjonalt_spredt:
                    rows.append(
                        {
                            "ar": ar,
                            "fylke": "NASJONALT",
                            "geo": "spredtbygd",
                            "tek": tek_mob,
                            "dekning": hus_spredt / nasjonalt_spredt,
                        }
                    )

                # Per fylke
                fylke_mob = (
                    adr_med_mob.group_by("fylke").agg(
                        pl.col("hus").sum().alias("hus_mob")
                    )
                )
                fylke_dekning = fylke_mob.join(fylke_total, on="fylke")
                for row in fylke_dekning.iter_rows(named=True):
                    if row["totalt_hus"] and row["totalt_hus"] > 0:
                        rows.append(
                            {
                                "ar": ar,
                                "fylke": row["fylke"],
                                "geo": "totalt",
                                "tek": tek_mob,
                                "dekning": row["hus_mob"] / row["totalt_hus"],
                            }
                        )

    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


# =============================================================================
# HASTIGHETSDEKNING
# =============================================================================


def load_hast_nasjonalt_2010() -> pl.DataFrame:
    """eldre_speed_2010.parquet - Hastighet nasjonalt 2010."""
    df = pl.read_parquet(LIB / "eldre_speed_2010.parquet")
    return df.select(
        pl.col("ar").cast(pl.Int32),
        pl.lit("NASJONALT").alias("fylke"),
        pl.lit("totalt").alias("geo"),
        pl.col("ned").cast(pl.Float64),
        pl.col("opp").cast(pl.Float64),
        (pl.col("dekning") / 100.0).alias("dekning"),  # Konverter fra prosent
    )


def load_hast_nasjonalt_2012_2020() -> pl.DataFrame:
    """historikk_speed_nasjonalt.parquet - Hastighet nasjonalt 2012-2020."""
    df = pl.read_parquet(LIB / "historikk_speed_nasjonalt.parquet")
    return df.select(
        pl.col("ar").cast(pl.Int32),
        pl.lit("NASJONALT").alias("fylke"),
        pl.lit("totalt").alias("geo"),
        pl.col("ned").cast(pl.Float64),
        pl.col("opp").cast(pl.Float64),
        pl.col("dekning"),
    )


def load_hast_fylke_2017() -> pl.DataFrame:
    """eldre_speed_fylke_2016_2017.parquet - Hastighet per fylke 2017."""
    df = pl.read_parquet(LIB / "eldre_speed_fylke_2016_2017.parquet")
    # Wide format: fylke, ar, h4_0.5, h12_0.8, h25_5, h30_5, h50_10, h100_10, h50_50, h100_100
    hast_mapping = {
        "h4_0.5": (4.0, 0.5),
        "h12_0.8": (12.0, 0.8),
        "h25_5": (25.0, 5.0),
        "h30_5": (30.0, 5.0),
        "h50_10": (50.0, 10.0),
        "h100_10": (100.0, 10.0),
        "h50_50": (50.0, 50.0),
        "h100_100": (100.0, 100.0),
    }
    rows = []
    for row in df.iter_rows(named=True):
        fylke = normalize_fylke(row["fylke"])
        ar = int(row["ar"])
        for col, (ned, opp) in hast_mapping.items():
            val = row.get(col)
            if val is not None:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": fylke,
                        "geo": "totalt",
                        "ned": ned,
                        "opp": opp,
                        "dekning": val / 100.0 if val > 1 else val,
                    }
                )
    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


def load_hast_2021() -> pl.DataFrame:
    """2021/dekning_fylke.parquet - Hastighet 2021."""
    df = pl.read_parquet(LIB / "2021/dekning_fylke.parquet")
    hast_cols = [
        ("h10", 10.0, 0.8),
        ("h30", 30.0, 5.0),
        ("h50", 50.0, 10.0),
        ("h100", 100.0, 10.0),
        ("h100_100", 100.0, 100.0),
        ("h1000", 1000.0, 100.0),
        ("h1000_1000", 1000.0, 1000.0),
    ]
    rows = []
    for row in df.iter_rows(named=True):
        fylke = normalize_fylke(row["fylke"])
        geo = normalize_geo(row["geo"])
        for col, ned, opp in hast_cols:
            val = row.get(col)
            if val is not None:
                rows.append(
                    {
                        "ar": 2021,
                        "fylke": fylke,
                        "geo": geo,
                        "ned": ned,
                        "opp": opp,
                        "dekning": val,
                    }
                )
    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


def beregn_hast_2022_2024() -> pl.DataFrame:
    """Beregn hastighetsdekning fra fbb + adr for 2022-2024."""
    rows = []
    # Hastighetsklasser (ned, opp) i Mbit/s - threshold i kbps
    hastigheter = [
        (10, 1, 10_000, 1_000),
        (30, 5, 30_000, 5_000),
        (50, 10, 50_000, 10_000),
        (100, 10, 100_000, 10_000),
        (100, 100, 100_000, 100_000),
        (1000, 100, 1_000_000, 100_000),
        (1000, 1000, 1_000_000, 1_000_000),
    ]

    for ar in [2022, 2023, 2024]:
        print(f"  Beregner hast-dekning for {ar}...")
        adr = pl.read_parquet(LIB / str(ar) / "adr.parquet")
        fbb = pl.read_parquet(LIB / str(ar) / "fbb.parquet")

        nasjonalt_total = adr.select(pl.col("hus").sum()).item()
        nasjonalt_tett = (
            adr.filter(pl.col("ertett") == True).select(pl.col("hus").sum()).item()
        )
        nasjonalt_spredt = (
            adr.filter(pl.col("ertett") == False).select(pl.col("hus").sum()).item()
        )

        fylke_total = adr.group_by("fylke").agg(pl.col("hus").sum().alias("totalt_hus"))

        for ned_mbit, opp_mbit, ned_kbps, opp_kbps in hastigheter:
            # Finn adresser med denne hastigheten
            hast_adrid = (
                fbb.filter((pl.col("ned") >= ned_kbps) & (pl.col("opp") >= opp_kbps))
                .select("adrid")
                .unique()
            )

            adr_med_hast = adr.join(hast_adrid, on="adrid", how="semi")

            # Nasjonalt totalt
            hus_hast = adr_med_hast.select(pl.col("hus").sum()).item()
            if hus_hast and nasjonalt_total:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "totalt",
                        "ned": float(ned_mbit),
                        "opp": float(opp_mbit),
                        "dekning": hus_hast / nasjonalt_total,
                    }
                )

            # Tettbygd/spredtbygd
            hus_tett = (
                adr_med_hast.filter(pl.col("ertett") == True)
                .select(pl.col("hus").sum())
                .item()
            )
            hus_spredt = (
                adr_med_hast.filter(pl.col("ertett") == False)
                .select(pl.col("hus").sum())
                .item()
            )
            if hus_tett and nasjonalt_tett:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "tettbygd",
                        "ned": float(ned_mbit),
                        "opp": float(opp_mbit),
                        "dekning": hus_tett / nasjonalt_tett,
                    }
                )
            if hus_spredt and nasjonalt_spredt:
                rows.append(
                    {
                        "ar": ar,
                        "fylke": "NASJONALT",
                        "geo": "spredtbygd",
                        "ned": float(ned_mbit),
                        "opp": float(opp_mbit),
                        "dekning": hus_spredt / nasjonalt_spredt,
                    }
                )

            # Per fylke
            fylke_hast = adr_med_hast.group_by("fylke").agg(
                pl.col("hus").sum().alias("hus_hast")
            )
            fylke_dekning = fylke_hast.join(fylke_total, on="fylke")
            for row in fylke_dekning.iter_rows(named=True):
                if row["totalt_hus"] and row["totalt_hus"] > 0:
                    rows.append(
                        {
                            "ar": ar,
                            "fylke": row["fylke"],
                            "geo": "totalt",
                            "ned": float(ned_mbit),
                            "opp": float(opp_mbit),
                            "dekning": row["hus_hast"] / row["totalt_hus"],
                        }
                    )

    result = pl.DataFrame(rows)
    return result.cast({"ar": pl.Int32})


# =============================================================================
# HOVEDPROGRAM
# =============================================================================


def main():
    print("=" * 60)
    print("KONSOLIDERER DEKNINGSHISTORIKK")
    print("=" * 60)

    # =========================================================================
    # TEKNOLOGIDEKNING
    # =========================================================================
    print("\n[1/2] Samler teknologidekning...")

    tek_dfs = []

    print("  - historikk_tek_nasjonalt (2013-2020)")
    tek_dfs.append(load_tek_nasjonalt_2013_2020())

    print("  - historikk_tek_geo_nasjonalt (2016-2020)")
    tek_dfs.append(load_tek_geo_nasjonalt_2016_2020())

    print("  - eldre_tek_fylke (2016-2017)")
    tek_dfs.append(load_tek_fylke_2016_2017())

    print("  - historikk_tek_fylke (2018-2020)")
    tek_dfs.append(load_tek_fylke_2018_2020_historikk())

    print("  - eldre_fylke (2018-2020)")
    tek_dfs.append(load_tek_fylke_2018_2020_eldre())

    print("  - 2021/dekning_fylke")
    tek_dfs.append(load_tek_2021())

    print("  - Beregner 2022-2024...")
    tek_dfs.append(beregn_tek_2022_2024())

    # Kombiner og dedupliker
    tek_all = pl.concat(tek_dfs)

    # Cast kolonner til riktig type
    tek_all = tek_all.select(
        pl.col("ar").cast(pl.Int32),
        pl.col("fylke").cast(pl.Utf8),
        pl.col("geo").cast(pl.Utf8),
        pl.col("tek").cast(pl.Utf8),
        pl.col("dekning").cast(pl.Float64),
    )

    # Fjern duplikater (behold første)
    tek_all = tek_all.unique(subset=["ar", "fylke", "geo", "tek"], keep="first")

    # Sorter
    tek_all = tek_all.sort(["ar", "fylke", "geo", "tek"])

    print(f"  Totalt {len(tek_all)} rader teknologidekning")

    # Lagre
    tek_path = LIB / "dekning_tek.parquet"
    tek_all.write_parquet(tek_path)
    print(f"  Lagret: {tek_path}")

    # =========================================================================
    # HASTIGHETSDEKNING
    # =========================================================================
    print("\n[2/2] Samler hastighetsdekning...")

    hast_dfs = []

    print("  - eldre_speed_2010")
    hast_dfs.append(load_hast_nasjonalt_2010())

    print("  - historikk_speed_nasjonalt (2012-2020)")
    hast_dfs.append(load_hast_nasjonalt_2012_2020())

    print("  - eldre_speed_fylke (2017)")
    hast_dfs.append(load_hast_fylke_2017())

    print("  - 2021/dekning_fylke")
    hast_dfs.append(load_hast_2021())

    print("  - Beregner 2022-2024...")
    hast_dfs.append(beregn_hast_2022_2024())

    # Kombiner
    hast_all = pl.concat(hast_dfs)

    # Cast kolonner
    hast_all = hast_all.select(
        pl.col("ar").cast(pl.Int32),
        pl.col("fylke").cast(pl.Utf8),
        pl.col("geo").cast(pl.Utf8),
        pl.col("ned").cast(pl.Float64),
        pl.col("opp").cast(pl.Float64),
        pl.col("dekning").cast(pl.Float64),
    )

    # Fjern duplikater
    hast_all = hast_all.unique(subset=["ar", "fylke", "geo", "ned", "opp"], keep="first")

    # Sorter
    hast_all = hast_all.sort(["ar", "fylke", "geo", "ned", "opp"])

    print(f"  Totalt {len(hast_all)} rader hastighetsdekning")

    # Lagre
    hast_path = LIB / "dekning_hast.parquet"
    hast_all.write_parquet(hast_path)
    print(f"  Lagret: {hast_path}")

    # =========================================================================
    # OPPSUMMERING
    # =========================================================================
    print("\n" + "=" * 60)
    print("OPPSUMMERING")
    print("=" * 60)

    # Teknologi
    print("\nTeknologidekning (dekning_tek.parquet):")
    print(f"  År: {tek_all['ar'].min()} - {tek_all['ar'].max()}")
    print(f"  Fylker: {tek_all['fylke'].n_unique()}")
    print(f"  Teknologier: {sorted(tek_all['tek'].unique().to_list())}")
    print(f"  Geo-typer: {sorted(tek_all['geo'].unique().to_list())}")

    # Hastighet
    print("\nHastighetsdekning (dekning_hast.parquet):")
    print(f"  År: {hast_all['ar'].min()} - {hast_all['ar'].max()}")
    print(f"  Fylker: {hast_all['fylke'].n_unique()}")
    print(
        f"  Hastigheter: {sorted(set(zip(hast_all['ned'].to_list(), hast_all['opp'].to_list())))}"
    )
    print(f"  Geo-typer: {sorted(hast_all['geo'].unique().to_list())}")

    print("\nFerdig!")


if __name__ == "__main__":
    main()
