"""
Filterfunksjoner for bredbåndsdata.

Standardiserte filtre som håndterer konvertering og validering.

Eksempel:
    from library.filters import filter_hastighet, filter_teknologi

    fbb = pl.scan_parquet("lib/fbb.parquet")

    # Filter på hastighet (Mbit/s -> kbps automatisk)
    over_100 = filter_hastighet(fbb, 100)

    # Filter på teknologi
    fiber = filter_teknologi(fbb, ["fiber"])
"""

import polars as pl


def filter_hastighet(lf: pl.LazyFrame, mbit: int, kolonne: str = "ned") -> pl.LazyFrame:
    """
    Filtrer på hastighet.

    Konverterer automatisk fra Mbit/s til kbps.

    Args:
        lf: LazyFrame å filtrere
        mbit: Minimum hastighet i Mbit/s
        kolonne: Kolonnenavn (default "ned" for nedlasting)

    Returns:
        Filtrert LazyFrame
    """
    kbps = mbit * 1000
    return lf.filter(pl.col(kolonne) >= kbps)


def filter_teknologi(lf: pl.LazyFrame, teknologier: list[str]) -> pl.LazyFrame:
    """
    Filtrer på teknologi.

    Args:
        lf: LazyFrame å filtrere
        teknologier: Liste med teknologier ["fiber", "ftb", "kabel", etc.]

    Returns:
        Filtrert LazyFrame
    """
    return lf.filter(pl.col("tek").is_in(teknologier))


def filter_tilbyder(lf: pl.LazyFrame, tilbydere: list[str]) -> pl.LazyFrame:
    """
    Filtrer på tilbyder.

    Args:
        lf: LazyFrame å filtrere
        tilbydere: Liste med tilbydernavn

    Returns:
        Filtrert LazyFrame
    """
    return lf.filter(pl.col("tilb").is_in(tilbydere))


def filter_populasjon(
    adr: pl.LazyFrame, populasjon: str
) -> pl.LazyFrame:
    """
    Filtrer adresser på populasjonstype.

    Args:
        adr: Adresse-LazyFrame
        populasjon: "alle", "tettsted" eller "spredtbygd"

    Returns:
        Filtrert LazyFrame
    """
    if populasjon == "tettsted":
        return adr.filter(pl.col("ertett") == True)  # noqa: E712
    elif populasjon == "spredtbygd":
        return adr.filter(pl.col("ertett") == False)  # noqa: E712
    return adr  # "alle"


def filter_hc(lf: pl.LazyFrame, kun_hc: bool = True) -> pl.LazyFrame:
    """
    Filtrer på Homes Connected status.

    Args:
        lf: LazyFrame å filtrere
        kun_hc: True for kun HC, False for kun HP

    Returns:
        Filtrert LazyFrame
    """
    return lf.filter(pl.col("hc") == kun_hc)


def filter_egen(lf: pl.LazyFrame) -> pl.LazyFrame:
    """
    Filtrer på egen infrastruktur.

    Returns:
        LazyFrame med kun tilbydere som eier egen infrastruktur
    """
    return lf.filter(pl.col("egen") == True)  # noqa: E712


# --- ab.parquet-spesifikke filtre ---


def filter_privat(lf: pl.LazyFrame, privat: bool = True) -> pl.LazyFrame:
    """
    Filtrer ab på privat/bedrift.

    Args:
        lf: LazyFrame fra ab.parquet
        privat: True for privatmarkedet, False for bedriftsmarkedet

    Returns:
        Filtrert LazyFrame
    """
    return lf.filter(pl.col("privat") == privat)


def filter_kol(lf: pl.LazyFrame, kol: bool = True) -> pl.LazyFrame:
    """
    Filtrer ab på kollektiv (MDU) / enkeltbolig (SDU).

    Args:
        lf: LazyFrame fra ab.parquet
        kol: True for kollektiv (flermannsbolig), False for enkeltbolig

    Returns:
        Filtrert LazyFrame
    """
    return lf.filter(pl.col("kol") == kol)


def filter_adrid_koblet(lf: pl.LazyFrame) -> pl.LazyFrame:
    """
    Filtrer ab til kun koblede adresser (adrid > 0).

    Abonnementer med adrid = 0 er ikke koblet til en adresse.

    Returns:
        LazyFrame med kun koblede adresser
    """
    return lf.filter(pl.col("adrid") > 0)
