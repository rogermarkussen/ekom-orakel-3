# Ekom-dokumentasjon

Detaljert dokumentasjon for `lib/ekom.parquet` - aggregert markedsstatistikk per tilbyder og rapporteringsperiode (2000-2025).

## Kolonner

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| fusnavn | String | **Tilbydernavn** (bruk denne for tilbyder-spørringer) |
| grnavn | String | Gruppenavn (kun når eksplisitt spurt) |
| levnavn | String | Leverandørnavn |
| hk | String | Hovedkategori (Fast bredbånd, Mobiltjenester, TV-tjenester, etc.) |
| dk | String | Delkategori (Mobiltelefoni, M2M, Hastighetsklasser, etc.) |
| hg | String | Hovedgruppe/metrikk (Abonnement, Inntekter, Trafikk, etc.) |
| tek | String | Teknologi (Fiber, DSL, Kabel-TV, LTE, 5G, FWA, etc.) |
| n1-n4 | String | Hierarkiske nivåer for ytterligere splitt |
| sk | String | Sluttbruker/Grossist |
| ms | String | Markedssegment (Privat, Bedrift, Ingen) |
| tp | String | **Sum** eller **Herav** - KRITISK for å unngå dobbeltelling! |
| ar | Integer | År |
| delar | String | Halvår eller Helår |
| rapport | String | Rapportperiode (f.eks. "2024-Helår") |
| svar | Double | **Verdien** som skal summeres |

---

## Kritiske regler

**0. Still oppfølgingsspørsmål når nødvendig!**

Ekom-data har mange dimensjoner. Spør brukeren hvis noe er uklart:

| Uklart | Spør om |
|--------|---------|
| "utvikling av fast bredbånd" | Abonnement eller inntekter? |
| "fast bredbånd" uten ms | Privat, bedrift, eller samlet? (Bedrift inkluderer Datakommunikasjon) |
| "mobilabonnement" | Fakturert, kontantkort, eller begge? |
| Ingen tidsperiode | Hvilken rapport/periode? Utvikling over tid? |
| "markedsandeler" | Basert på abonnement eller inntekter? |

1. **tp-kolonnen (VIKTIGST!):**
   - `tp = 'Sum'` → Kan summeres trygt, ingen dobbeltelling
   - `tp = 'Herav'` → Del av noe annet, IKKE inkluder i totaler!

2. **sk-filter (standard):**
   - Bruk ALLTID `sk IN ('Sluttbruker', 'Ingen')` med mindre grossist eksplisitt etterspørres

3. **Tilbyder:**
   - Bruk `fusnavn` for tilbyder (ikke grnavn med mindre eksplisitt spurt om gruppenavn)

4. **Tidsserier:**
   - ALDRI summer på tvers av rapporteringsperioder!
   - For utvikling over tid: vis per `rapport` (sortert alfabetisk)
   - For kun halvår eller helår: filtrer på `delar`, bruk `ar` som kolonner

5. **Ingen filtrering = total:**
   - Ikke filtrere på tek → total alle teknologier
   - Ikke filtrere på ms → total privat + bedrift
   - Ikke filtrere på n1-n4 → total uten splitt

6. **hg må være én verdi:**
   - ALDRI summer Abonnement + Inntekter eller Inntekter + Trafikk

7. **Null-verdier:** `'Ingen'` betyr null/ikke relevant

8. **Fast bredbånd bedrift:**
   - Inkluder BÅDE `hk = 'Fast bredbånd'` OG `hk = 'Datakommunikasjon'` (VPN-aksesser)
   - Datakommunikasjon er alltid bedrift

9. **Fylkesfordeling for mobilabonnement (UNNTAK fra nasjonale tall):**
   - Fra og med 2025-Halvår har mobilabonnement fylkesfordeling
   - Fylke ligger i `n1`-kolonnen (f.eks. `n1 = 'Agder'`)
   - Fylkesdata har `tp = 'Herav'` (delfordeling av tilbyders nasjonale tall)
   - Tilgjengelige fylker: Agder, Akershus, Buskerud, Finnmark, Innlandet, Møre og Romsdal, Nordland, Oslo, Rogaland, Telemark, Troms, Trøndelag, Vestfold, Vestland, Østfold
   - I kode: foretrekk `execute_mobilabonnement_fylke()` eller `EkomQuery(..., group_by=['fylke'])` fremfor rå `n1`

---

## Enheter

| hg | Enhet |
|----|-------|
| Abonnement | Antall (stk) |
| Inntekter | NOK 1000 (tusen kroner) |
| Trafikk (tale) | 1000 minutter |
| Trafikk (SMS) | 1000 meldinger |
| Trafikk (data) | Gigabyte |

---

## Hovedkategorier (hk)

- Fast bredbånd
- Mobiltjenester
- TV-tjenester
- Fasttelefoni
- Datakommunikasjon (VPN, alltid bedrift)
- Overføringskapasitet
- Investeringer
- Antall årsverk

---

## Query Patterns

### Total per rapporteringsperiode

```sql
-- Antall mobilabonnement (fakturert) over tid
SELECT
    rapport,
    ROUND(SUM(svar) / 1000000, 2) as mill_ab
FROM 'lib/ekom.parquet'
WHERE hk = 'Mobiltjenester'
  AND dk = 'Mobiltelefoni'
  AND hg = 'Abonnement'
  AND n1 = 'Fakturert'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
GROUP BY rapport
ORDER BY rapport
```

### Privat vs Bedrift utvikling

```sql
-- Mobilabonnement fordelt på privat/bedrift (kun helår)
SELECT
    ar,
    ms,
    ROUND(SUM(svar) / 1000000, 2) as mill_ab
FROM 'lib/ekom.parquet'
WHERE hk = 'Mobiltjenester'
  AND dk = 'Mobiltelefoni'
  AND hg = 'Abonnement'
  AND n1 = 'Fakturert'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND delar = 'Helår'
  AND ar >= 2018
GROUP BY ar, ms
ORDER BY ar, ms
```

### Markedsandeler per tilbyder

```sql
-- Markedsandeler fiber-inntekter privatmarkedet
SELECT
    fusnavn as tilbyder,
    ROUND(SUM(svar) / 1000000, 2) as mrd_nok,
    ROUND(SUM(svar) * 100.0 / SUM(SUM(svar)) OVER(), 1) as markedsandel_pct
FROM 'lib/ekom.parquet'
WHERE hk = 'Fast bredbånd'
  AND hg = 'Inntekter'
  AND tek = 'Fiber'
  AND ms = 'Privat'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND rapport = '2024-Helår'
GROUP BY fusnavn
ORDER BY mrd_nok DESC
LIMIT 10
```

### Fast bredbånd bedrift (inkl. Datakommunikasjon)

```sql
-- Bredbånd bedrift = Fast bredbånd + Datakommunikasjon
SELECT
    rapport,
    ROUND(SUM(svar) / 1000, 0) as antall_ab
FROM 'lib/ekom.parquet'
WHERE hk IN ('Fast bredbånd', 'Datakommunikasjon')
  AND hg = 'Abonnement'
  AND ms = 'Bedrift'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND delar = 'Helår'
GROUP BY rapport
ORDER BY rapport
```

### Teknologifordeling

```sql
-- Bredbåndsabonnement per teknologi
SELECT
    tek,
    ROUND(SUM(svar) / 1000000, 2) as mill_ab,
    ROUND(SUM(svar) * 100.0 / SUM(SUM(svar)) OVER(), 1) as andel_pct
FROM 'lib/ekom.parquet'
WHERE hk = 'Fast bredbånd'
  AND hg = 'Abonnement'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND rapport = '2024-Helår'
GROUP BY tek
ORDER BY mill_ab DESC
```

### Inntekter i milliarder

```sql
-- Total mobilinntekter i milliarder NOK
SELECT
    rapport,
    ROUND(SUM(svar) / 1000000, 2) as mrd_nok  -- svar er i 1000 NOK
FROM 'lib/ekom.parquet'
WHERE hk = 'Mobiltjenester'
  AND dk = 'Mobiltelefoni'
  AND hg = 'Inntekter'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND delar = 'Helår'
GROUP BY rapport
ORDER BY rapport
```

### Mobilabonnement per fylke (fra 2025-Halvår)

Tryggeste API:

```python
from library import execute_mobilabonnement_fylke

df = execute_mobilabonnement_fylke(rapport="2025-Halvår", ms="Privat")
df = execute_mobilabonnement_fylke(
    rapport="2025-Halvår",
    ms="Privat",
    fylke="Agder",
)
```

```sql
-- Mobilabonnement per fylke (privat)
SELECT
    n1 as fylke,
    fusnavn as tilbyder,
    ROUND(SUM(svar), 0) as antall_ab
FROM 'lib/ekom.parquet'
WHERE hk = 'Mobiltjenester'
  AND dk = 'Mobiltelefoni'
  AND hg = 'Abonnement'
  AND n1 IN ('Agder', 'Akershus', 'Buskerud', 'Finnmark', 'Innlandet',
             'Møre og Romsdal', 'Nordland', 'Oslo', 'Rogaland', 'Telemark',
             'Troms', 'Trøndelag', 'Vestfold', 'Vestland', 'Østfold')
  AND ms = 'Privat'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND rapport = '2025-Halvår'
GROUP BY n1, fusnavn
ORDER BY n1, antall_ab DESC
```

---

## Tips

- **ALLTID** filtrer på `tp = 'Sum'` for totaler (unntak: fylkesdata som alltid er `tp = 'Herav'`)
- **ALLTID** filtrer på `sk IN ('Sluttbruker', 'Ingen')` med mindre grossist spørres
- For fylkesfordeling i kode: bruk `group_by=['fylke']`, ikke rå `n1`, når du vil ha faktiske fylker
- For millioner: del på 1000000
- For milliarder NOK (inntekter): del på 1000000 (siden data er i 1000 NOK)
- Sorter på `rapport` for kronologisk rekkefølge
- **Fylkesdata:** Kun tilgjengelig for mobilabonnement fra 2025-Halvår, ligger i `n1`-kolonnen
