# Korreksjoner

Denne filen dokumenterer feil som er gjort og hva som er riktig. Les denne før du starter nye uttrekk.

Når et mønster gjentar seg eller er spesielt viktig, bør det promoteres til en permanent regel i CLAUDE.md.

---

## Format

Hver korreksjon følger dette formatet:

```
## YYYY-MM-DD: Kort beskrivelse av feilen

**Kontekst:** Hva prøvde agenten å gjøre?
**Hva ble gjort:** Den faktiske feilen
**Hva er riktig:** Korrekt fremgangsmåte
**Hvorfor:** Forklaring på hvorfor dette er riktig
**Promotert:** Ja/Nei (om regelen er lagt til i CLAUDE.md)
```

---

## Korreksjoner

### 2026-01-19: ORDER BY på UNION-spørringer i DuckDB

**Kontekst:** Lage tabell med fylker + nasjonalt rad, sortert med NASJONALT nederst
**Hva ble gjort:** Prøvde å bruke ORDER BY direkte etter UNION ALL:
```sql
SELECT fylke, ... FROM per_fylke
UNION ALL
SELECT 'NASJONALT', ... FROM per_fylke
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```
**Hva er riktig:** Wrap UNION i en CTE eller subquery før ORDER BY:
```sql
resultat AS (
    SELECT ... UNION ALL SELECT ...
)
SELECT * FROM resultat
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```
**Hvorfor:** DuckDB (og standard SQL) krever at ORDER BY refererer til kolonner i den ytterste SELECT. Ved UNION må hele resultatet wrappes først.
**Promotert:** Nei
**Merknad:** Feilen gjentok seg 2026-01-19. Vurder promotering til CLAUDE.md.

---

### 2026-01-19: Antok at Python-pakker var tilgjengelige

**Kontekst:** Lese Excel-fil for å hente data til graf
**Hva ble gjort:** Prøvde å importere pandas, deretter openpyxl, deretter polars med fastexcel - alle feilet med ModuleNotFoundError
**Hva er riktig:** Bruk DuckDB direkte for å lese data, eller sjekk tilgjengelige pakker først. DuckDB kan lese Excel indirekte via CSV-eksport, men parquet-filer er alltid tilgjengelige.
**Hvorfor:** Miljøet har ikke pandas, openpyxl eller fastexcel installert. DuckDB og polars (uten Excel-støtte) er de primære verktøyene.
**Promotert:** Nei

<!--
Eksempel på fremtidig korreksjon:

## 2026-01-18: Feil hastighetsfilter

**Kontekst:** Lage uttrekk for dekning over 100 Mbit
**Hva ble gjort:** Brukte `> 100_000` (streng større enn)
**Hva er riktig:** `>= 100_000` (større enn eller lik)
**Hvorfor:** "Over 100 Mbit" tolkes som "100 Mbit eller mer" i dekningssammenheng
**Promotert:** Ja - lagt til i "Vanlige Feil å Unngå"
-->
