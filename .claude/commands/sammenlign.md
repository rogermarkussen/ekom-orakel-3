# Sammenlign dekning over tid

Sammenlign dekning mellom to år med automatisk fylkesmapping og beregning av endring.

## Bruk

- `/sammenlign [teknologi] [år1] [år2] [aggregering] [populasjon]`

### Eksempler

```
/sammenlign fiber 2022 2024 fylke
/sammenlign 5g 2023 2024 nasjonal
/sammenlign fiber spredtbygd 2022 2024
/sammenlign 100mbit 2022 2024 fylke
/sammenlign fiber 2016 2024 nasjonal   # Historisk (bruker dekning_tek)
/sammenlign 100mbit 2010 2024 nasjonal # Hastighet historisk (bruker dekning_hast)
```

## Instruksjoner

### Steg 1: Parse brukerens input

**Teknologi:**
| Input | Teknologi-filter |
|-------|------------------|
| fiber | ["fiber"] |
| 5g, g5 | ["5g"] (bruker mob.parquet) |
| 4g, g4 | ["4g"] (bruker mob.parquet) |
| ftb | ["ftb"] |
| kabel | ["kabel"] |
| 100mbit | hastighet_min=100 |
| 1gbit | hastighet_min=1000 |

**År:**
- Detaljerte data (CoverageQuery): 2022, 2023, 2024
- Historisk teknologi (HistoricalQuery): 2013-2024
- Historisk hastighet (HistoricalSpeedQuery): 2010-2024
- For mobil (5g/4g): kun 2023 og 2024

**Aggregering:**
- `fylke` (default)
- `nasjonal`
- `kommune`

**Populasjon:**
- `alle` (default)
- `spredtbygd`
- `tettsted`

### Steg 2: Velg riktig query-type

| År-range | Teknologi | Query-type | Datakilde |
|----------|-----------|------------|-----------|
| 2022-2024 | fiber/ftb/5g | CoverageQuery | Detaljert (adr/fbb/mob) |
| 2013-2024 | fiber/kabel/5g | HistoricalQuery | dekning_tek.parquet |
| 2010-2024 | hastighet (100mbit) | HistoricalSpeedQuery | dekning_hast.parquet |

**Valg av query-type:**
- Hvis begge år er i 2022-2024: Bruk `CoverageQuery` (mer detaljert, fylkesnivå)
- Hvis ett eller begge år er før 2022: Bruk `HistoricalQuery` eller `HistoricalSpeedQuery`
- For hastighetssammenligninger med år før 2022: Bruk `HistoricalSpeedQuery`

### Steg 2a: CoverageQuery (2022-2024)

```python
from library import CoverageQuery
import polars as pl

# Parse argumenter
tek = ["fiber"]  # Fra input
år1, år2 = 2022, 2024
pop = "alle"

# VIKTIG: For 2022/2023 brukes fylke24-kolonnen for konsistent fylkesinndeling
# CoverageQuery håndterer dette automatisk

# Hent data fra år 1
query1 = CoverageQuery(
    year=år1,
    teknologi=tek,
    populasjon=pop,
    group_by="fylke"
)
df1 = query1.execute()

# Hent data fra år 2
query2 = CoverageQuery(
    year=år2,
    teknologi=tek,
    populasjon=pop,
    group_by="fylke"
)
df2 = query2.execute()
```

### Steg 2b: HistoricalQuery (2013-2024, teknologi)

Bruk når ett eller begge år er før 2022:

```python
from library import HistoricalQuery
import polars as pl

# Historisk sammenligning av fiberdekning
år1, år2 = 2016, 2024
tek = ["fiber"]
pop = "totalt"  # "totalt", "tettbygd", "spredtbygd"

query = HistoricalQuery(
    start_year=år1,
    end_year=år2,
    teknologi=tek,
    geo=pop,
    fylke="NASJONALT"  # Kun nasjonalt nivå tilgjengelig
)
df = query.execute()

# Resultat: år, teknologi, prosent
# Filtrer for å få bare start- og sluttår
df_comparison = df.filter(pl.col("år").is_in([år1, år2]))
```

### Steg 2c: HistoricalSpeedQuery (2010-2024, hastighet)

Bruk for hastighetssammenligninger med år før 2022:

```python
from library import HistoricalSpeedQuery
import polars as pl

# Historisk sammenligning av >=100 Mbit/s dekning
år1, år2 = 2010, 2024

query = HistoricalSpeedQuery(
    start_year=år1,
    end_year=år2,
    ned=100,  # Mbit/s ned
    opp=100,  # Mbit/s opp (symmetrisk)
    geo="totalt",  # "totalt", "tettbygd", "spredtbygd"
    fylke="NASJONALT"
)
df = query.execute()

# Resultat: år, prosent
# Filtrer for å få bare start- og sluttår
df_comparison = df.filter(pl.col("år").is_in([år1, år2]))
```

### Steg 3: Merge og beregn endring

```python
# Rename kolonner for klarhet
df1 = df1.rename({
    "prosent": f"prosent_{år1}",
    "med_dekning": f"dekning_{år1}",
    "totalt": f"totalt_{år1}"
})

df2 = df2.rename({
    "prosent": f"prosent_{år2}",
    "med_dekning": f"dekning_{år2}",
    "totalt": f"totalt_{år2}"
})

# Merge på fylke
merged = df1.join(df2, on="fylke", how="outer")

# Beregn endring i prosentpoeng
merged = merged.with_columns([
    (pl.col(f"prosent_{år2}") - pl.col(f"prosent_{år1}")).round(1).alias("endring_pp")
])

# Sorter: Fylker alfabetisk, NASJONALT sist
merged = merged.sort(
    pl.when(pl.col("fylke") == "NASJONALT").then(1).otherwise(0),
    pl.col("fylke")
)
```

### Steg 4: Vis resultat

Vis tabell med:
- Fylke
- Prosent år1
- Prosent år2
- Endring (prosentpoeng)

Marker endringer:
- Positiv endring: grønn/+
- Negativ endring: rød/-

```
Sammenligning: Fiberdekning 2022 → 2024

┌────────────┬────────────┬────────────┬───────────┐
│ Fylke      │ 2022 (%)   │ 2024 (%)   │ Endring   │
├────────────┼────────────┼────────────┼───────────┤
│ AGDER      │     82.3   │     87.1   │    +4.8   │
│ AKERSHUS   │     89.1   │     92.4   │    +3.3   │
│ ...        │            │            │           │
│ NASJONALT  │     85.2   │     89.7   │    +4.5   │
└────────────┴────────────┴────────────┴───────────┘
```

### Steg 5: Tilby visualisering

Spør brukeren:
- Vil du se dette som graf? (`/graf`)
- Eksportere til Excel? (`/tilxl`)

## Interaktiv modus

Hvis argumenter mangler, spør via AskUserQuestion:

1. **Teknologi:** Fiber, FTB, 5G, 4G, >=100 Mbit?
2. **År 1:** 2022, 2023?
3. **År 2:** 2023, 2024?
4. **Aggregering:** Per fylke eller kun nasjonalt?
5. **Populasjon:** Alle, tettsted, eller spredtbygd?

## Viktige regler

1. **Fylkesmapping:** Data fra 2022/2023 bruker `fylke24`-kolonnen som allerede inneholder 2024-fylker
2. **Mobil-begrensning:** 5G/4G-data finnes kun fra 2023
3. **HC-filter:** For fiber, spør om brukeren vil se HC eller HP+HC samlet

## Feilhåndtering

- Hvis mobildata etterspørres for 2022: "Mobildekning finnes kun fra 2023"
- Hvis år1 > år2: Bytt rekkefølge automatisk
- Ved store negative endringer (>5pp): Gi advarsel og verifiser data
- Hvis år er før 2013 for teknologi: "Teknologidata (fiber/kabel) finnes kun fra 2013"
- Hvis år er før 2010 for hastighet: "Hastighetsdata finnes kun fra 2010"
- Historiske data (før 2022) har kun nasjonalt nivå - informer brukeren hvis fylkesnivå ønskes

## Eksempel komplett

### Eksempel 1: Fylkesvis sammenligning (2022-2024)

```
/sammenlign fiber 2022 2024 fylke

Sammenligning: Fiberdekning (HC+HP) 2022 → 2024

┌─────────────────┬───────────┬───────────┬──────────┐
│ Fylke           │ 2022 (%)  │ 2024 (%)  │ Endring  │
├─────────────────┼───────────┼───────────┼──────────┤
│ AGDER           │     82.3  │     87.1  │    +4.8  │
│ AKERSHUS        │     89.1  │     92.4  │    +3.3  │
│ BUSKERUD        │     78.5  │     84.2  │    +5.7  │
│ FINNMARK        │     65.2  │     72.1  │    +6.9  │
│ INNLANDET       │     71.4  │     78.3  │    +6.9  │
│ MØRE OG ROMSDAL │     76.8  │     82.5  │    +5.7  │
│ NORDLAND        │     68.9  │     75.4  │    +6.5  │
│ OSLO            │     95.2  │     96.8  │    +1.6  │
│ ROGALAND        │     85.6  │     90.1  │    +4.5  │
│ TELEMARK        │     74.3  │     80.9  │    +6.6  │
│ TROMS           │     72.1  │     78.8  │    +6.7  │
│ TRØNDELAG       │     80.5  │     86.2  │    +5.7  │
│ VESTFOLD        │     88.7  │     92.1  │    +3.4  │
│ VESTLAND        │     83.4  │     88.6  │    +5.2  │
│ ØSTFOLD         │     86.2  │     90.5  │    +4.3  │
│ NASJONALT       │     85.2  │     89.7  │    +4.5  │
└─────────────────┴───────────┴───────────┴──────────┘

Største økning: FINNMARK og INNLANDET (+6.9 pp)
Minste økning: OSLO (+1.6 pp)

Vil du lage graf over utviklingen?
```

### Eksempel 2: Historisk sammenligning (2016-2024)

```
/sammenlign fiber 2016 2024 nasjonal

Sammenligning: Fiberdekning (nasjonalt) 2016 → 2024
(Bruker historisk data fra dekning_tek.parquet)

┌───────┬──────────────┐
│ År    │ Prosent (%)  │
├───────┼──────────────┤
│ 2016  │        62.3  │
│ 2024  │        89.7  │
└───────┴──────────────┘

Endring: +27.4 prosentpoeng over 8 år
Gjennomsnittlig årlig økning: +3.4 pp/år
```

### Eksempel 3: Hastighetssammenligning (2010-2024)

```
/sammenlign 100mbit 2010 2024 nasjonal

Sammenligning: ≥100/100 Mbit/s dekning (nasjonalt) 2010 → 2024
(Bruker historisk data fra dekning_hast.parquet)

┌───────┬──────────────┐
│ År    │ Prosent (%)  │
├───────┼──────────────┤
│ 2010  │         5.2  │
│ 2024  │        88.3  │
└───────┴──────────────┘

Endring: +83.1 prosentpoeng over 14 år
Gjennomsnittlig årlig økning: +5.9 pp/år
```
