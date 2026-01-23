# List historiske spørringer

Vis verifiserte spørringer fra kunnskapsbasen, eller kjør en spesifikk spørring.

## Bruk

- `/listhist` - Vis siste 20 spørringer
- `/listhist 3` - Kjør spørring nummer 3
- `/listhist fiber` - Søk etter spørringer om fiber
- `/listhist filter=ekom` - Vis kun Ekom-spørringer (siste 20)
- `/listhist filter=konkurranse, historikk` - Vis flere kategorier
- `/listhist filter=!ekom` - Vis alt utenom Ekom

## Instruksjoner

### Uten argument: Vis siste 20

Kjør Python for å hente siste 20 spørringer:
```python
from library import KnowledgeBase
kb = KnowledgeBase()
queries = kb.list_queries(limit=20)
```

Vis som tabell med kolonner: #, Kategori, Beskrivelse (trunkert til 45 tegn), Verifisert.

### Med filter: Filtrer på kategori

Parse filter-argumentet og kall `list_queries()`:

```python
from library import KnowledgeBase
kb = KnowledgeBase()

# filter=ekom → én kategori
queries = kb.list_queries(categories=["ekom"])

# filter=konkurranse, historikk → flere kategorier (OR)
queries = kb.list_queries(categories=["konkurranse", "historikk"])

# filter=!ekom → ekskluder kategori
queries = kb.list_queries(exclude_categories=["ekom"])

# filter=!ekom, !dekning → ekskluder flere
queries = kb.list_queries(exclude_categories=["ekom", "dekning"])
```

Vis som tabell. Filteret begrenser også til siste 20.

### Med nummer: Kjør spørring N

1. Hent spørring fra database:
   ```python
   from library import KnowledgeBase
   kb = KnowledgeBase()
   query = kb.get_query(N)
   ```

2. Vis spørringens SQL

3. Kjør SQL med DuckDB:
   ```python
   from library import execute_sql
   result = execute_sql(query.sql)
   print(result)
   ```

4. Vis resultatet (husk regel 12: tabell først for fylkesfordeling)

### Med søkeord: Finn lignende spørringer

1. Bruk QueryMatcher for semantisk søk:
   ```python
   from library import QueryMatcher
   matcher = QueryMatcher()
   results = matcher.find_similar("fiber rural dekning")
   ```

2. Vis topp 5 resultater med score:
   ```
   | # | Score | Kategori | Beskrivelse |
   |---|-------|----------|-------------|
   | 3 | 0.85  | Dekning  | Fiberdekning spredtbygd |
   ```

3. Spør om brukeren vil kjøre en av dem

## Eksempler

```
/listhist
→ Viser siste 20 spørringer (nyeste først)

/listhist 7
→ Kjører spørring 7 (Nasjonal teknologidekning 2016-2024)

/listhist filter=ekom
→ Viser kun Ekom-spørringer (siste 20)

/listhist filter=konkurranse, historikk
→ Viser Konkurranse og Historikk (siste 20)

/listhist filter=!ekom
→ Viser alt utenom Ekom (siste 20)

/listhist fiber spredtbygd
→ Søker og finner Q:3, Q:6 som handler om fiber i spredtbygd
```

## Viktig

- **Default:** Siste 20 spørringer, nyeste først
- **Filter:** Case-insensitive, komma-separert for flere kategorier
- **Negasjon:** Bruk `!` foran kategori for å ekskludere
- Ved søk: utvid med synonymer (rural→spredtbygd, ftth→fiber)
