# List historiske spørringer

Vis alle verifiserte spørringer fra QUERY_LOG.md, eller kjør en spesifikk spørring.

## Bruk

- `/listhist` - Vis alle spørringer som tabell
- `/listhist 3` - Kjør spørring nummer 3

## Instruksjoner

### Uten argument: Vis indeks

1. Les **kun de første 30 linjene** av QUERY_LOG.md (indeksen ligger øverst)
2. Finn tabellen under "## Indeks"
3. Vis tabellen direkte til brukeren

Indeksen har formatet:
```
| # | Kategori | Beskrivelse | Verifisert |
|---|----------|-------------|------------|
| 1 | Ekom | Kontantkort-utvikling 2018-2024 | 2026-01-19 |
...
```

### Med argument: Kjør spørring N

**Effektiv navigering med markører:**

1. Bruk Grep for å finne linjenummeret til markøren `<!-- Q:N -->`:
   ```bash
   grep -n "<!-- Q:N -->" QUERY_LOG.md
   ```

2. Les ~40 linjer fra det linjenummeret med Read-verktøyet (offset + limit)

3. Finn SQL-spørringen i ```sql ... ``` blokken

4. Kjør SQL-spørringen med DuckDB

5. Vis resultatet (husk regel 12: tabell først for fylkesfordeling)

**Eksempel for spørring 7:**
```
grep -n "<!-- Q:7 -->" QUERY_LOG.md  # → f.eks. linje 365
Read QUERY_LOG.md med offset=365, limit=40
```

## Viktig

- Les kun toppen av filen for `/listhist` uten argument (effektivitet)
- Bruk markører `<!-- Q:N -->` for å navigere direkte til spørringer
- Indeksen er sannhetskilden for oversikten
- `<!-- INDEKS-SLUTT -->` markerer hvor indeksen slutter
- `<!-- LOGG-SLUTT -->` markerer hvor nye spørringer skal legges til
