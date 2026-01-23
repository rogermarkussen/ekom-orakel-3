# List historiske spørringer

Vis alle verifiserte spørringer fra kunnskapsbasen, eller kjør en spesifikk spørring.

## Bruk

- `/listhist` - Vis alle spørringer som tabell
- `/listhist 3` - Kjør spørring nummer 3
- `/listhist fiber` - Søk etter spørringer om fiber
- `/listhist --category Dekning` - Filtrer på kategori

## Instruksjoner

### Uten argument: Vis indeks

**RASK METODE:** Les `lib/knowledge/INDEX.md` direkte med Read-verktøyet:
```
Read lib/knowledge/INDEX.md
```

Vis innholdet til brukeren. Ikke kjør Python for enkel indeksvisning.

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
→ Viser tabell med alle 12 spørringer

/listhist 7
→ Kjører spørring 7 (Nasjonal teknologidekning 2016-2024)

/listhist fiber spredtbygd
→ Søker og finner Q:3, Q:6 som handler om fiber i spredtbygd

/listhist --category Konkurranse
→ Viser kun spørringer i kategorien "Konkurranse"
```

## Viktig

- **Enkel visning:** Les `lib/knowledge/INDEX.md` direkte (raskest)
- **Med argument:** Bruk Python for å hente/kjøre spesifikk spørring
- Ved søk: utvid med synonymer (rural→spredtbygd, ftth→fiber)
- INDEX.md oppdateres automatisk ved `/loggpush`
