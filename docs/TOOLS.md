# TOOLS.md - Teknisk Referanse

## Malloy Queries

### Fiber
| Query | Beskrivelse | Kolonner |
|-------|-------------|----------|
| `fiber_fylke` | Fiberdekning per fylke | fylke_navn, hus_fiber, antall_husstander, fiber_pct |
| `fiber_spredtbygd` | Fiber i spredtbygd per fylke | fylke_navn, hus_fiber, antall_husstander, fiber_pct |
| `fiber_tettsted` | Fiber i tettsted per fylke | fylke_navn, hus_fiber, antall_husstander, fiber_pct |
| `fiber_hc_fylke` | Fiber HC per fylke | fylke_navn, hus_fiber_hc, antall_husstander, fiber_hc_pct |
| `hoyhastighet_fylke` | >=100 Mbit per fylke | fylke_navn, hus_hoyhast, antall_husstander, hoyhast_pct |

### Mobildekning
| Query | Beskrivelse | Kolonner |
|-------|-------------|----------|
| `g5_fylke` | 5G-dekning per fylke | fylke_navn, hus_5g, antall_husstander, g5_pct |
| `g5_spredtbygd` | 5G i spredtbygd per fylke | fylke_navn, hus_5g, antall_husstander, g5_pct |
| `g4_fylke` | 4G-dekning per fylke | fylke_navn, hus_4g, antall_husstander, g4_pct |

### FTB og konkurranse
| Query | Beskrivelse | Kolonner |
|-------|-------------|----------|
| `ftb_fylke` | FTB-dekning per fylke | fylke_navn, hus_ftb, antall_husstander, ftb_pct |
| `konkurranse_fylke` | Fibertilbydere per fylke | fylke_navn, hus_1_tilb, hus_2_tilb, hus_3_tilb, antall_husstander |

---

## Engine API

```python
from library import (
    execute_malloy,
    execute_coverage,
    execute_ekom,
    execute_mobilabonnement_fylke,
    execute_sql_cached,
)

# Kjør Malloy-query (cachet, 1t TTL)
df = execute_malloy("fiber_fylke")
df = execute_malloy("fiber_spredtbygd", filters={"fylke_navn": "OSLO"})

# Høynivå convenience (auto-ruter til Malloy eller SQL)
df = execute_coverage(teknologi="fiber", populasjon="spredtbygd")
df = execute_coverage(teknologi=["fiber", "ftb"], group_by="fylke")
df = execute_coverage(teknologi="5g", group_by="kommune", year=2024)

# Ekom convenience
df = execute_ekom("Fast bredbånd", hg="Abonnement", ms="Bedrift", rapport="2024-Helår")
df = execute_mobilabonnement_fylke(rapport="2025-Halvår", ms="Privat")

# SQL med caching
df = execute_sql_cached("SELECT * FROM adr WHERE fylke = 'OSLO'")

# Hjelpefunksjoner
get_available_queries()  # -> ["fiber_fylke", "fiber_spredtbygd", ...]
get_query_info("fiber_fylke")  # -> {"columns": [...], "description": "..."}
invalidate_cache("fiber_fylke")  # Invalidér spesifikk
invalidate_cache()  # Invalidér all cache
get_cache_stats()  # -> {"entries": 5, "total_size_mb": 0.3, ...}
```

## Guardrails I API-ene

- `execute_coverage()` bruker `mob.parquet` for rene mobilspørringer og `fbb.parquet` for fastbredbånd.
- `CoverageQuery(group_by="kommune")` grupperer på `komnavn`.
- `CoverageQuery` avviser mobil + HC/HP og blanding av mobil og fastbredbånd i samme spørring.
- `execute_mobilabonnement_fylke()` koder inn reglene for `tp='Herav'`, `dk='Mobiltelefoni'`, `hg='Abonnement'` og periode fra og med `2025-Halvår`.

## CLI-notater

- `/sammenlign` støtter `fiber`, `kabel`, `ftb`, `4g`, `5g`, `100mbit` og `1gbit`.
- `100mbit` og `1gbit` tolkes som nedhastighet `>= 100` og `>= 1000 Mbit/s`, uavhengig av teknologi.
- `/graf` bruker automatisk grafvalg:
  - horisontale stolper for fordelinger
  - linjer for tidsserier
  - endringsstolper for sammenligninger med `endring_pp`
- `/graf` følger fargene i `docs/v1/DESIGNMAL.md` og fremhever `NASJONALT` i mørkeblått.

---

## Query Builders

```python
from library import (
    CoverageQuery,
    EkomQuery,
    HistoricalQuery,
    HistoricalSpeedQuery,
    quick_coverage,
)

# Quick one-liner
df = quick_coverage("fiber")  # Nasjonal fiberdekning

# Full kontroll
query = CoverageQuery(
    year=2024,
    teknologi=["fiber"],
    populasjon="spredtbygd",  # eller "tettsted" eller None
    group_by="fylke",  # eller "kommune" eller "nasjonal"
    kun_hc=True,  # Kun Homes Connected
)
df = query.execute()

# Historisk tidsserie
query = HistoricalQuery(
    teknologi=["fiber"],
    start_year=2022,
    end_year=2024,
)
df = query.execute()

# Ekom med full kontroll
query = EkomQuery(
    hk="Mobiltjenester",
    dk="Mobiltelefoni",
    hg="Abonnement",
    rapport="2024-Helår",
    group_by=["rapport"],
    pivot_years=False,
)
df = query.execute()

# Historisk hastighetsserie
df = HistoricalSpeedQuery(
    start_year=2021,
    end_year=2024,
    ned=100,
    opp=100,
).execute()
```

---

## Library-funksjoner

```python
from library import (
    # Lasting
    load_data,          # load_data(år) -> (adr, fbb, mob, ab)
    load_dataset,       # load_dataset(navn, år) -> én LazyFrame
    get_script_paths,   # -> (script_path, excel_path)

    # Filtre
    filter_hastighet,   # filter_hastighet(fbb, 100) = ned >= 100 Mbit
    filter_teknologi,   # filter_teknologi(fbb, ["fiber", "ftb"])
    filter_populasjon,  # filter_populasjon(adr, "spredtbygd")
    filter_hc,          # filter_hc(fbb, kun_hc=True)
    filter_egen,        # filter_egen(fbb) = egen infrastruktur

    # Validering
    add_national_aggregate,  # Legg til NASJONALT-rad
    validate_and_save,       # Print, valider, lagre Excel
    validate_pre_execution,  # Sjekk SQL mot kjente feil
    validate_result,         # Sjekk resultat (sanity checks)

    # Query Builder
    CoverageQuery,      # DSL for dekningsspørringer
    CompetitionQuery,   # DSL for tilbyderkonkurranse
    quick_coverage,     # quick_coverage("fiber") -> DataFrame
    EkomQuery,          # DSL for ekom-spørringer
    execute_ekom,       # Ekom convenience
    execute_mobilabonnement_fylke,  # Sikker helper for mobilabonnement per fylke

    # Knowledge Base
    KnowledgeBase,      # SQLite CRUD + FTS5 søk
    QueryMatcher,       # Finn lignende spørringer

    # Cache
    get_db,             # DuckDB med registrerte views
    execute_sql,        # Kjør SQL direkte

    # Fylker
    FYLKER,             # Liste med 15 fylker (2024)
    normalize_fylke,    # "viken" -> "VIKEN"
    map_fylke_2020_to_2024,  # "VIKEN" -> ["AKERSHUS", ...]
)
```

---

## DuckDB Views

| View | Beskrivelse |
|------|-------------|
| `adr` | Adresser 2024 (default) |
| `adr_2022`, `adr_2023`, `adr_2024` | Årsspesifikke adresser |
| `fbb` | Fast bredbånd 2024 |
| `fbb_2022`, `fbb_2023`, `fbb_2024` | Årsspesifikt FBB |
| `mob` | Mobil 2024 |
| `mob_2023`, `mob_2024` | Årsspesifikk mobil |
| `ab` | Abonnement 2024 |
| `dekning_tek` | Historisk teknologidekning 2013-2024 |
| `dekning_hast` | Historisk hastighetsdekning 2010-2024 |
| `ekom` | Markedsstatistikk 2000-2025 |

```python
from library import get_db, execute_sql

db = get_db()
views = db.get_view_names()  # Liste alle views

# Direkte SQL
df = execute_sql("SELECT fylke, COUNT(*) FROM adr GROUP BY fylke")
```

---

## Cache API

| Funksjon | Beskrivelse |
|----------|-------------|
| `execute_malloy(name)` | Automatisk 1t cache |
| `execute_sql_cached(sql)` | Automatisk 24t cache |
| `invalidate_cache(name)` | Slett spesifikk cache |
| `invalidate_cache()` | Slett all cache |

Cache lagres i `lib/cache/*.parquet`.

---

## Filters (Polars)

```python
from library import filter_teknologi, filter_populasjon, filter_hastighet, filter_hc

fbb_fiber = filter_teknologi(fbb, ["fiber"])
adr_rural = filter_populasjon(adr, "spredtbygd")
fbb_100 = filter_hastighet(fbb, 100)  # >=100 Mbit
fbb_hc = filter_hc(fbb, kun_hc=True)
```

---

## Terminologi

| Term | Betydning | Filter |
|------|-----------|--------|
| fiber | Fiberoptisk | `tek == "fiber"` |
| ftb | Fast trådløst bredbånd | `tek == "ftb"` |
| kabel | Kabel-TV nett (HFC) | `tek == "kabel"` |
| HC | Homes Connected | `hc == true` |
| HP | Homes Passed | `hc == false` |
| tettsted | Urbant område | `ertett == true` |
| spredtbygd | Ruralt område | `ertett == false` |

---

## Fylkesendringer 2020→2024

| 2020-2023 (11 fylker) | 2024+ (15 fylker) |
|-----------------------|-------------------|
| VIKEN | AKERSHUS, BUSKERUD, ØSTFOLD |
| VESTFOLD OG TELEMARK | VESTFOLD, TELEMARK |
| TROMS OG FINNMARK | TROMS, FINNMARK |

**For tidsserier:**
- 2022/2023: Bruk `fylke24`-kolonnen (inneholder 2024-fylker)
- 2024: Bruk `fylke`-kolonnen (er allerede 2024-inndeling)

---

## Sanity Checks

| Sjekk | Forventet |
|-------|-----------|
| Nasjonal fiberdekning | ~85-95% |
| 5G-dekning nasjonalt | ~70-90% |
| Husstander spredtbygd | ~15-20% av total |
| Totalt husstander | ~2.5-2.6 millioner |

---

## Tilgjengelige år

| År | adr | fbb | mob | ab |
|----|-----|-----|-----|-----|
| 2022 | ✓ | ✓ | ✗ | ✓ |
| 2023 | ✓ | ✓ | ✓ | ✓ |
| 2024 | ✓ | ✓ | ✓ | ✓ |

---

## Vanlige mønstre

### Fiberdekning per fylke (raskest)
```python
df = execute_malloy("fiber_fylke")
```

### Fiberdekning spredtbygd (raskest)
```python
df = execute_malloy("fiber_spredtbygd")
```

### 5G-dekning
```python
df = execute_malloy("g5_fylke")
df = execute_malloy("g5_spredtbygd")
df = execute_coverage(teknologi="5g", group_by="kommune", year=2024)
```

### 4G/LTE-dekning
```python
df = execute_malloy("g4_fylke")
```

### FTB-dekning
```python
df = execute_malloy("ftb_fylke")
```

### Konkurranse (fibertilbydere)
```python
df = execute_malloy("konkurranse_fylke")
```

### Mobilabonnement per fylke (fra 2025-Halvår)
```python
df = execute_mobilabonnement_fylke(rapport="2025-Halvår", ms="Privat")
df = execute_mobilabonnement_fylke(
    rapport="2025-Halvår",
    ms="Privat",
    fylke="Agder",
)
# Kolonner: hus_1_tilb, hus_2_tilb, hus_3_tilb
```

### Tilpasset dekning
```python
df = execute_coverage(teknologi="ftb", populasjon="spredtbygd", group_by="fylke")
```

### Rå SQL
```python
df = execute_sql_cached("""
    SELECT fylke, SUM(hus) as hus
    FROM adr WHERE NOT ertett
    GROUP BY fylke
""")
```
