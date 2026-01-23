# CLAUDE.md

## Din Rolle

Du er en autonom dataanalytiker. Din jobb er å besvare brukerens spørsmål om bredbåndsdekning ved å skrive og kjøre Polars-scripts.

## Regler

1. **Bruk `/ny` for nye uttrekk.** ALDRI lag nye filer under `uttrekk/` uten å kjøre `/ny` først.
2. **Direkte spørsmål = DuckDB.** Spørsmål uten `/ny` besvares direkte med DuckDB. Ingen filer lagres.
3. **Ikke gjett.** Hvis du er usikker på definisjoner, spør brukeren.
4. **Bruk biblioteket.** Importer fra `library` i stedet for å hardkode.
5. **Valider alltid.** Sjekk at resultatene gir mening før du svarer.
6. **Lagre scripts.** Alle scripts lagres i `uttrekk/YYYY-MM-DD/`.
7. **Kjør med uv.** Bruk alltid `uv run python script.py`.
8. **HC/HP kun for fiber.** Spør BARE om HC/HP-filter når fiber er inkludert i uttrekket.
9. **Lær av feil.** Korreksjoner lagres i SQLite (`lib/knowledge.db`) og valideres automatisk via `validate_pre_execution()`.
10. **Ikke logg underveis.** Samle opp og logg alt når brukeren kjører `/loggpush`.
11. **Spør om verifisering.** Etter hvert svar, spør: "Er resultatet korrekt?" Når bekreftet, gi påminnelse: "Husk `/loggpush` for å lagre sesjonen."
12. **Fylkesvis fordeling = tabell først.** Tabell med Fylke sortert alfabetisk, NASJONALT nederst.
13. **Spør om år når relevant.** Tilgjengelige år: 2022, 2023, 2024. Standard er 2024. mob kun fra 2023.
14. **Bruk riktig adr-fil.** Ved fylkesfordeling, bruk adr fra samme år. Fylker endret seg i 2024.
15. **Historiske spørsmål → bruk dekning_tek/dekning_hast.** Les `docs/DEKNING.md` for detaljer.
16. **Ekom-spørsmål → les docs/EKOM.md først.** Ekom har komplekse regler for å unngå dobbeltelling.
17. **Detaljerte kolonnedefinisjoner → les docs/DATA_DICT.md.** For adr, fbb, mob, ab og DuckDB-mønstre.
18. **Tidsserier på fylkesnivå → bruk fylke24.** Bruk `fylke24` for 2022/2023 og `fylke` for 2024. Alle har nå konsistent 2024-inndeling (15 fylker).

---

## Dokumentasjon

| Fil | Innhold | Les når... |
|-----|---------|------------|
| `docs/EKOM.md` | ekom.parquet kolonner, regler, query patterns | Spørsmål om markedsstatistikk, abonnement, inntekter |
| `docs/DEKNING.md` | Historiske data, konsoliderte filer, 2021-data | Spørsmål om dekning over tid (2007-2024) |
| `docs/DATA_DICT.md` | adr/fbb/mob/ab kolonner, DuckDB patterns | Detaljerte kolonnedefinisjoner, query-mønstre |

---

## Slash-kommandoer

| Kommando | Beskrivelse |
|----------|-------------|
| `/ny` | Start nytt uttrekk. Foreslår lignende spørringer fra KB. |
| `/loggpush` | Logg til SQLite + markdown, commit og push. |
| `/listhist [nr\|søk]` | Vis spørringer, kjør nr N, eller søk med FTS5. |
| `/tilxl [spørring]` | Eksporter til Excel. |
| `/tilbilde [spørring]` | Eksporter til PNG-bilde. |
| `/graf` | Lag graf av forrige datasett. |

**Eksempler:**
- `/listhist` - Vis alle spørringer
- `/listhist 7` - Kjør spørring 7
- `/listhist fiber spredtbygd` - Søk etter fiber + spredtbygd

---

## Mappestruktur

```
ekom-orakel-2/
  CLAUDE.md           # Regler (denne filen)
  historie.md         # Kontekst for data 2007-2011
  docs/               # Detaljert dokumentasjon
    EKOM.md           # ekom.parquet dokumentasjon
    DEKNING.md        # Historiske dekningsdata
    DATA_DICT.md      # Kolonnedefinisjoner, DuckDB patterns
  lib/                # Data (IKKE endre)
    knowledge.db      # SQLite kunnskapsbase (spørringer + korreksjoner)
    knowledge/        # JSON backup (queries.json, corrections.json)
    ekom.parquet      # Markedsstatistikk 2000-2025
    dekning_tek.parquet   # Teknologidekning 2013-2024
    dekning_hast.parquet  # Hastighetsdekning 2010-2024
    2022/, 2023/, 2024/   # Årlige dekningsdata
  library/            # Python-bibliotek
    knowledge.py      # SQLite CRUD + FTS5 søk
    query_matcher.py  # Keyword-søk med synonymer
    query_builder.py  # Query DSL for dekning
    validators.py     # Pre/post-execution validering
    cache.py          # DuckDB caching
    fylker.py         # Fylkesnormalisering 2020↔2024
  uttrekk/            # Dine scripts og resultater
```

### Tilgjengelige år

| År | adr | fbb | mob | ab |
|----|-----|-----|-----|-----|
| 2022 | ✓ | ✓ | ✗ | ✓ |
| 2023 | ✓ | ✓ | ✓ | ✓ |
| 2024 | ✓ | ✓ | ✓ | ✓ |

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

    # Query Builder (anbefalt for standard spørringer)
    CoverageQuery,      # DSL for dekningsspørringer
    CompetitionQuery,   # DSL for tilbyderkonkurranse
    quick_coverage,     # quick_coverage("fiber") -> DataFrame

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

### Query Builder (anbefalt)

For standard dekningsspørringer, bruk Query Builder i stedet for manuell SQL:

```python
from library import CoverageQuery

query = CoverageQuery(
    year=2024,
    teknologi=["fiber"],
    populasjon="spredtbygd",
    group_by="fylke",
    kun_hc=True,
)
result = query.execute()  # Returnerer DataFrame
```

---

## Hastighetskonvertering

Data lagres i **kbps**. Brukere sier **Mbit/s**.

| Bruker sier | Filter |
|-------------|--------|
| "over 100 Mbit" | `ned >= 100_000` |
| "over 1 Gbit" | `ned >= 1_000_000` |

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

Dette gir konsistent fylkesinndeling gjennom hele tidsserien uten behov for mapping.

---

## Vanlige Feil å Unngå

| Feil | Riktig |
|------|--------|
| `> 100_000` for "over 100" | `>= 100_000` |
| Forveksle "ftb" med "fbb" | ftb = teknologi, fbb = datafil |
| Sjekke `adrid.is_not_null()` etter join | Legg til markør-kolonne før join |
| Summere `hus` fra ab | Tell rader for ab |
| Joine ab med adr | Bruk ab.fylke direkte |
| Blande fylker fra ulike år | Bruk samme års adr-fil |

---

## Selvkorrigering

### Automatisk validering

Bruk `validate_pre_execution(sql)` for å fange kjente feil FØR kjøring:
- Ekom-query uten `tp='Sum'`
- Hastighetsfilter med `>` i stedet for `>=`
- `SUM(ab.hus)` (skal telle rader, ikke summere)

### Ved feil

1. **Rett feilen** og fortsett
2. **Husk feilen** for logging ved `/loggpush`
3. **Ikke logg underveis**

Ved `/loggpush`: lagre i SQLite Knowledge Base med pattern for fremtidig matching.

---

## Spørringslogging

**IKKE logg underveis.** Husk verifiserte spørringer og logg samlet ved `/loggpush`.

### Verifiseringsworkflow

Etter hver spørring:
1. Vis resultatet
2. Spør: **"Er resultatet korrekt?"**
3. Hvis ja → Husk spørringen for logging
4. Gi påminnelse: **"Husk `/loggpush` for å lagre sesjonen."**

### Ved `/loggpush` lagres til:

**SQLite Knowledge Base**:
```python
kb = KnowledgeBase()
kb.add_query(question, sql, result_summary, category, tags)
```

---

## Workflow-eksempel

Bruker: "Finn fiberdekning i spredtbygd per fylke"

```python
"""
Uttrekk: Fiberdekning i spredtbygd

Kriterier:
- Teknologi: fiber
- Populasjon: spredtbygd
- Aggregering: fylke + nasjonalt
"""

import polars as pl
from library import (
    load_data, get_script_paths, filter_teknologi,
    filter_populasjon, add_national_aggregate, validate_and_save,
)

_, excel_path = get_script_paths("fiber_spredtbygd")
adr, fbb, _, _ = load_data()

fiber_adrid = (
    filter_teknologi(fbb, ["fiber"])
    .select("adrid").unique()
    .with_columns(pl.lit(True).alias("har_fiber"))
)

per_fylke = (
    filter_populasjon(adr, "spredtbygd")
    .join(fiber_adrid, on="adrid", how="left")
    .group_by("fylke")
    .agg(
        pl.col("hus").filter(pl.col("har_fiber") == True).sum().alias("hus_fiber"),
        pl.col("hus").sum().alias("totalt_hus"),
    )
    .with_columns((pl.col("hus_fiber") / pl.col("totalt_hus") * 100).round(1).alias("prosent"))
    .sort("fylke")
    .collect()
)

resultat = add_national_aggregate(per_fylke, "hus_fiber", "totalt_hus")
validate_and_save(resultat, excel_path, "hus_fiber", "totalt_hus")
```

---

## Sanity Checks

| Sjekk | Forventet |
|-------|-----------|
| Nasjonal fiberdekning | ~85-95% |
| 5G-dekning nasjonalt | ~70-90% |
| Husstander spredtbygd | ~15-20% av total |
| Totalt husstander | ~2.5-2.6 millioner |

---

## Tidligere Uttrekk

Før du skriver nytt script, sjekk `uttrekk/*/` for eksisterende scripts.
