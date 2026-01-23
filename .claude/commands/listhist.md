# List historiske spørringer

Vis alle verifiserte spørringer fra QUERY_LOG.md, eller kjør en spesifikk spørring.

## Bruk

- `/listhist` - Vis alle spørringer som tabell
- `/listhist 3` - Kjør spørring nummer 3

## Instruksjoner

### Uten argument: Vis indeks

1. Finn linjenummeret for `<!-- INDEKS-SLUTT -->`:
   ```bash
   grep -n "INDEKS-SLUTT" QUERY_LOG.md
   ```
2. Les QUERY_LOG.md fra start til det linjenummeret (bruk `limit` parameter)
3. Vis tabellen under "## Indeks" direkte til brukeren

### Med argument: Kjør spørring N

**Effektiv navigering med markører:**

1. Finn linjenummer for start og slutt av spørringen:
   ```bash
   grep -n "<!-- Q:" QUERY_LOG.md | grep -E "Q:N -->|Q:$((N+1)) -->|LOGG-SLUTT"
   ```
   Dette gir deg:
   - Linjenummer for `<!-- Q:N -->` (start)
   - Linjenummer for `<!-- Q:N+1 -->` eller `<!-- LOGG-SLUTT -->` (slutt)

2. Les fra startlinje til sluttlinje med Read-verktøyet:
   - `offset` = startlinjenummer
   - `limit` = sluttlinje - startlinje

3. Finn SQL-spørringen i ```sql ... ``` blokken

4. Kjør SQL-spørringen med DuckDB

5. Vis resultatet (husk regel 12: tabell først for fylkesfordeling)

**Eksempel for spørring 7:**
```bash
grep -n "<!-- Q:" QUERY_LOG.md | grep -E "Q:7 -->|Q:8 -->|LOGG-SLUTT"
# Output: 365:<!-- Q:7 -->
#         392:<!-- Q:8 -->
# Les linje 365-391 (offset=365, limit=27)
```

## Viktig

- Les kun toppen av filen for `/listhist` uten argument (effektivitet)
- Bruk markører `<!-- Q:N -->` for å navigere direkte til spørringer
- Les alltid til neste markør for å få hele spørringen
- Indeksen er sannhetskilden for oversikten
- `<!-- INDEKS-SLUTT -->` markerer hvor indeksen slutter
- `<!-- LOGG-SLUTT -->` markerer hvor logg-seksjonen slutter
