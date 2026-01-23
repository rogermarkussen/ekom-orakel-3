"""
Fylkesnormalisering og historisk mapping.

Håndterer fylkesendringer mellom 2020 og 2024.

Eksempel:
    from library.fylker import normalize_fylke, map_fylke_2020_to_2024

    # Normaliser fylkesnavn
    normalize_fylke("oslo") -> "OSLO"

    # Map fra 2020-inndeling til 2024
    map_fylke_2020_to_2024("VIKEN") -> ["AKERSHUS", "BUSKERUD", "ØSTFOLD"]
"""

from typing import Optional

# Fylker per 2024 (etter reversering av fylkessammenslåinger)
FYLKER_2024 = [
    "AGDER",
    "AKERSHUS",
    "BUSKERUD",
    "FINNMARK",
    "INNLANDET",
    "MØRE OG ROMSDAL",
    "NORDLAND",
    "OSLO",
    "ROGALAND",
    "TELEMARK",
    "TROMS",
    "TRØNDELAG",
    "VESTFOLD",
    "VESTLAND",
    "ØSTFOLD",
]

# Fylker i 2020-2023 (etter sammenslåinger)
FYLKER_2020 = [
    "AGDER",
    "INNLANDET",
    "MØRE OG ROMSDAL",
    "NORDLAND",
    "OSLO",
    "ROGALAND",
    "TROMS OG FINNMARK",
    "TRØNDELAG",
    "VESTFOLD OG TELEMARK",
    "VESTLAND",
    "VIKEN",
]

# Mapping fra 2020-fylker til 2024-fylker
FYLKE_2020_TO_2024 = {
    "VIKEN": ["AKERSHUS", "BUSKERUD", "ØSTFOLD"],
    "VESTFOLD OG TELEMARK": ["VESTFOLD", "TELEMARK"],
    "TROMS OG FINNMARK": ["TROMS", "FINNMARK"],
    # Uendrede fylker
    "AGDER": ["AGDER"],
    "INNLANDET": ["INNLANDET"],
    "MØRE OG ROMSDAL": ["MØRE OG ROMSDAL"],
    "NORDLAND": ["NORDLAND"],
    "OSLO": ["OSLO"],
    "ROGALAND": ["ROGALAND"],
    "TRØNDELAG": ["TRØNDELAG"],
    "VESTLAND": ["VESTLAND"],
}

# Reverse mapping: 2024 -> 2020
FYLKE_2024_TO_2020 = {
    "AKERSHUS": "VIKEN",
    "BUSKERUD": "VIKEN",
    "ØSTFOLD": "VIKEN",
    "VESTFOLD": "VESTFOLD OG TELEMARK",
    "TELEMARK": "VESTFOLD OG TELEMARK",
    "TROMS": "TROMS OG FINNMARK",
    "FINNMARK": "TROMS OG FINNMARK",
    # Uendrede
    "AGDER": "AGDER",
    "INNLANDET": "INNLANDET",
    "MØRE OG ROMSDAL": "MØRE OG ROMSDAL",
    "NORDLAND": "NORDLAND",
    "OSLO": "OSLO",
    "ROGALAND": "ROGALAND",
    "TRØNDELAG": "TRØNDELAG",
    "VESTLAND": "VESTLAND",
}

# Aliaser og varianter
FYLKE_ALIASES = {
    # Lowercase varianter
    "oslo": "OSLO",
    "rogaland": "ROGALAND",
    "agder": "AGDER",
    "innlandet": "INNLANDET",
    "nordland": "NORDLAND",
    "trøndelag": "TRØNDELAG",
    "vestland": "VESTLAND",
    "møre og romsdal": "MØRE OG ROMSDAL",
    # Med og uten bindestrek
    "møre-og-romsdal": "MØRE OG ROMSDAL",
    "more og romsdal": "MØRE OG ROMSDAL",
    # 2024-fylker
    "akershus": "AKERSHUS",
    "buskerud": "BUSKERUD",
    "østfold": "ØSTFOLD",
    "ostfold": "ØSTFOLD",
    "vestfold": "VESTFOLD",
    "telemark": "TELEMARK",
    "troms": "TROMS",
    "finnmark": "FINNMARK",
    # 2020-fylker
    "viken": "VIKEN",
    "vestfold og telemark": "VESTFOLD OG TELEMARK",
    "troms og finnmark": "TROMS OG FINNMARK",
    # Gamle navn
    "aust-agder": "AGDER",
    "vest-agder": "AGDER",
    "hedmark": "INNLANDET",
    "oppland": "INNLANDET",
    "hordaland": "VESTLAND",
    "sogn og fjordane": "VESTLAND",
    "sør-trøndelag": "TRØNDELAG",
    "nord-trøndelag": "TRØNDELAG",
}


def normalize_fylke(fylke: str) -> str:
    """
    Normaliser fylkesnavn til standard format (uppercase).

    Args:
        fylke: Fylkesnavn i vilkårlig format

    Returns:
        Normalisert fylkesnavn i uppercase

    Raises:
        ValueError: Hvis fylkesnavn ikke gjenkjennes
    """
    fylke_lower = fylke.strip().lower()

    # Sjekk aliaser
    if fylke_lower in FYLKE_ALIASES:
        return FYLKE_ALIASES[fylke_lower]

    # Sjekk direkte match med uppercase
    fylke_upper = fylke.strip().upper()
    if fylke_upper in FYLKER_2024 or fylke_upper in FYLKER_2020:
        return fylke_upper

    raise ValueError(f"Ukjent fylke: {fylke}")


def get_fylker(year: int = 2024) -> list[str]:
    """
    Hent liste over fylker for et gitt år.

    Args:
        year: Årstall

    Returns:
        Liste med fylkesnavn
    """
    if year >= 2024:
        return FYLKER_2024.copy()
    elif year >= 2020:
        return FYLKER_2020.copy()
    else:
        # Før 2020 - returner 2020-listen (eller implementer eldre mapping)
        return FYLKER_2020.copy()


def map_fylke_2020_to_2024(fylke: str) -> list[str]:
    """
    Map fylke fra 2020-inndeling til 2024-inndeling.

    Args:
        fylke: Fylkesnavn i 2020-format

    Returns:
        Liste med tilsvarende 2024-fylker
    """
    fylke = normalize_fylke(fylke)

    if fylke in FYLKE_2020_TO_2024:
        return FYLKE_2020_TO_2024[fylke]

    # Allerede 2024-fylke
    if fylke in FYLKER_2024:
        return [fylke]

    raise ValueError(f"Kan ikke mappe fylke: {fylke}")


def map_fylke_2024_to_2020(fylke: str) -> str:
    """
    Map fylke fra 2024-inndeling til 2020-inndeling.

    Args:
        fylke: Fylkesnavn i 2024-format

    Returns:
        Tilsvarende 2020-fylke
    """
    fylke = normalize_fylke(fylke)

    if fylke in FYLKE_2024_TO_2020:
        return FYLKE_2024_TO_2020[fylke]

    # Allerede 2020-fylke
    if fylke in FYLKER_2020:
        return fylke

    raise ValueError(f"Kan ikke mappe fylke: {fylke}")


def is_same_region(fylke1: str, fylke2: str) -> bool:
    """
    Sjekk om to fylker er samme region (på tvers av tid).

    Eksempel:
        is_same_region("AKERSHUS", "VIKEN") -> True
        is_same_region("OSLO", "VIKEN") -> False
    """
    try:
        norm1 = normalize_fylke(fylke1)
        norm2 = normalize_fylke(fylke2)
    except ValueError:
        return False

    # Samme fylke
    if norm1 == norm2:
        return True

    # Sjekk 2020 -> 2024 mapping
    if norm1 in FYLKE_2020_TO_2024:
        if norm2 in FYLKE_2020_TO_2024[norm1]:
            return True

    if norm2 in FYLKE_2020_TO_2024:
        if norm1 in FYLKE_2020_TO_2024[norm2]:
            return True

    return False


def get_year_for_data(year: int) -> int:
    """
    Finn riktig dataår for et spesifikt år.

    For historiske sammenligninger må man bruke riktig datakilde.
    """
    available_years = [2022, 2023, 2024]

    if year in available_years:
        return year

    # Finn nærmeste år
    if year < min(available_years):
        return min(available_years)
    if year > max(available_years):
        return max(available_years)

    # Finn nærmeste
    return min(available_years, key=lambda x: abs(x - year))


def create_fylke_mapping_sql(from_year: int, to_year: int) -> Optional[str]:
    """
    Generer SQL CASE-statement for fylkesmapping.

    Nyttig for historiske sammenligninger.
    """
    if from_year >= 2024 and to_year >= 2024:
        return None  # Ingen mapping nødvendig
    if from_year < 2024 and to_year < 2024:
        return None  # Samme periode

    if from_year < 2024 and to_year >= 2024:
        # Map fra 2020-inndeling til 2024
        cases = []
        for old_fylke, new_fylker in FYLKE_2020_TO_2024.items():
            if len(new_fylker) > 1:
                for new in new_fylker:
                    cases.append(f"WHEN fylke = '{old_fylke}' THEN '{new}'")
            else:
                cases.append(f"WHEN fylke = '{old_fylke}' THEN '{new_fylker[0]}'")

        return "CASE\n    " + "\n    ".join(cases) + "\n    ELSE fylke\nEND"

    if from_year >= 2024 and to_year < 2024:
        # Map fra 2024-inndeling til 2020
        cases = []
        for new_fylke, old_fylke in FYLKE_2024_TO_2020.items():
            cases.append(f"WHEN fylke = '{new_fylke}' THEN '{old_fylke}'")

        return "CASE\n    " + "\n    ".join(cases) + "\n    ELSE fylke\nEND"

    return None


# For bakoverkompatibilitet
FYLKER = FYLKER_2024
