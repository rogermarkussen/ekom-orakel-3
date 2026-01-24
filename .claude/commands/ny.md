# Opprett nytt uttrekk

Du skal hjelpe brukeren med å lage et nytt uttrekk-script. Bruk AskUserQuestion-verktøyet for å samle inn nødvendig informasjon.

## Steg 0: Finn lignende spørringer

Før du starter, søk etter lignende spørringer i kunnskapsbasen:

```python
from library import QueryMatcher

matcher = QueryMatcher()
suggestions = matcher.suggest_for_question("brukerens beskrivelse")

if suggestions:
    print("Lignende tidligere spørringer:")
    for q in suggestions:
        print(f"  - Q:{q.id}: {q.question[:60]}...")
```

Hvis det finnes lignende spørringer, vis dem til brukeren og spør om de vil:
1. Gjenbruke eksisterende spørring
2. Bruke som utgangspunkt
3. Lage helt nytt uttrekk

## Steg 1: Samle informasjon

Still følgende spørsmål til brukeren (bruk AskUserQuestion):

### Spørsmål 1: Hva ønsker du å finne ut?
Be brukeren beskrive uttrekket med egne ord. F.eks:
- "Fiberdekning i spredtbygde områder"
- "5G-dekning per fylke"
- "Antall fiber-abonnementer"

### Spørsmål 2: Hvilket år?
Alternativer:
- **2024** (nyeste data, 15 fylker)
- **2023** (11 fylker, første år med mobildekning)
- **2022** (11 fylker, ingen mobildekning)
- **Flere år** (historisk sammenligning)

**Merk:** mob.parquet finnes kun fra 2023. Fylkesinndelingen endret seg i 2024.

### Spørsmål 3: Hvilken datakilde?
Alternativer:
- **fbb** (fastbredbånd dekning) - for dekningsdata
- **mob** (mobildekning) - for 4G/5G dekning (kun 2023+)
- **ab** (abonnementer) - for abonnementsdata

### Spørsmål 4: Hvilke filtre trengs?
Still oppfølgingsspørsmål basert på datakilde:

For **fbb**:
- Teknologi? (fiber, ftb, kabel, radio, alle)
- Hastighet? (ingen, 100 Mbit, 1 Gbit)
- Homes Connected (HC) eller Homes Passed (HP)?
- Egen infrastruktur?

For **mob**:
- Teknologi? (4g, 5g, begge)
- Tilbyder? (telenor, telia, ice, alle)

For **ab**:
- Teknologi? (fiber, kabel, etc.)
- Privat eller bedrift?
- MDU eller SDU?

### Spørsmål 5: Populasjon
- Tettsted
- Spredtbygd
- Alle

### Spørsmål 6: Aggregeringsnivå
- Per fylke
- Per kommune
- Kun nasjonalt

**Ved historisk sammenligning med fylkesfordeling:** Vær obs på at fylkesinndelingen er ulik mellom 2022-2023 (11 fylker) og 2024 (15 fylker). Nasjonalt nivå anbefales for tidsserier.

## Steg 2: Lag scriptet

Når du har all informasjon:

1. Bruk `get_script_paths()` fra library for å finne riktig filnavn
2. Skriv scriptet til `uttrekk/YYYY-MM-DD/XX_navn.py`
3. Følg mønsteret fra CLAUDE.md og examples/
4. Bruk library-funksjonene (filter_teknologi, filter_hastighet, etc.)
5. Bruk `load_data(år)` med riktig årsparameter
6. Inkluder alltid:
   - Docstring med beskrivelse, kriterier og årstall
   - Nasjonal aggregering
   - validate_and_save() for lagring

### Eksempel med årsparameter:
```python
# Last data for 2023
adr, fbb, mob, ab = load_data(2023)

# For historisk sammenligning, last flere år:
adr_22, fbb_22, _, ab_22 = load_data(2022)
adr_23, fbb_23, mob_23, ab_23 = load_data(2023)
adr_24, fbb_24, mob_24, ab_24 = load_data(2024)
```

## Steg 3: Valider SQL før kjøring

Før du kjører spørringen, valider den mot kjente feil:

```python
from library import validate_pre_execution

issues = validate_pre_execution(sql)
for issue in issues:
    if issue.level == "error":
        print(f"FEIL: {issue.message}")
        print(f"Løsning: {issue.suggestion}")
    elif issue.level == "warning":
        print(f"ADVARSEL: {issue.message}")
```

## Steg 4: Kjør og valider resultat

1. Kjør scriptet med `uv run python uttrekk/YYYY-MM-DD/XX_navn.py`
2. Valider resultatet:
   ```python
   from library import validate_result

   issues = validate_result(df, "metrikk_col", "total_col")
   for issue in issues:
       print(f"{issue.level}: {issue.message}")
   ```
3. Sjekk at resultatene gir mening (se sanity checks i CLAUDE.md)
4. Vis resultatene til brukeren

## Alternativ 1: Bruk Malloy Query Engine (Raskest)

For standard dekningsspørringer, sjekk om Malloy har en ferdig query:

```python
from library import execute_malloy, get_available_queries

# Se tilgjengelige queries
print(get_available_queries())
# ['fiber_fylke', 'fiber_spredtbygd', 'g5_fylke', 'ftb_fylke', ...]

# Kjør direkte
df = execute_malloy("fiber_fylke")
df = execute_malloy("fiber_spredtbygd")
df = execute_malloy("g5_spredtbygd")
```

Tilgjengelige Malloy-queries:
| Query | Beskrivelse |
|-------|-------------|
| `fiber_fylke` | Fiberdekning per fylke |
| `fiber_spredtbygd` | Fiber i spredtbygd per fylke |
| `fiber_tettsted` | Fiber i tettsted per fylke |
| `fiber_hc_fylke` | Fiber HC per fylke |
| `g5_fylke` | 5G-dekning per fylke |
| `g5_spredtbygd` | 5G i spredtbygd per fylke |
| `g4_fylke` | 4G-dekning per fylke |
| `ftb_fylke` | FTB-dekning per fylke |
| `hoyhastighet_fylke` | >=100 Mbit per fylke |
| `konkurranse_fylke` | Fibertilbydere per fylke |

Fordeler:
- Cachet (1 times TTL)
- Validerte definisjoner
- Raskeste alternativ

## Alternativ 2: Bruk Query Builder

For tilpassede spørringer, bruk Query Builder:

```python
from library import CoverageQuery

query = CoverageQuery(
    year=2024,
    teknologi=["fiber"],
    populasjon="spredtbygd",
    group_by="fylke",
    kun_hc=True,
)

print(query.describe())  # Beskrivelse på norsk
result = query.execute()
print(result)
```

Fordeler:
- Eliminerer vanlige feil automatisk
- Håndterer fylkesendringer
- Konsistent output-format

## Viktig

- ALDRI gjett på definisjoner - spør brukeren
- Bruk ALLTID library-funksjonene
- Valider at tallene gir mening før du presenterer dem
- Sjekk mot kjente feil med `validate_pre_execution()`
