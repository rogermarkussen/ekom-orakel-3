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
9. **Lær av feil.** Les `CORRECTIONS.md` FØR du skriver SQL eller Polars-kode. Gjelder både DuckDB-spørringer og uttrekk.
10. **Ikke logg underveis.** Ikke oppdater QUERY_LOG.md eller CORRECTIONS.md underveis i sesjonen. Samle opp og logg alt når brukeren kjører `/loggpush`.
11. **Påminn om logging.** Etter hvert svar der brukeren bekrefter et resultat, gi en kort påminnelse: "Husk `/loggpush` for å lagre sesjonen."
12. **Fylkesvis fordeling = tabell først.** "Fylkesvis fordeling" betyr ALLTID en tabell med Fylke som første kolonne, sortert alfabetisk med NASJONALT nederst. Vis DuckDB-tabellen direkte - ikke erstatt den med bullet points eller annen formatering. En kort oppsummering etter tabellen er OK.

---

## Slash-kommandoer

| Kommando | Beskrivelse |
|----------|-------------|
| `/ny` | Start nytt uttrekk. Samler inn krav og lager script. **Påkrevd for alle nye uttrekk.** |
| `/loggpush` | Logg, commit og push. Logger alle verifiserte spørringer og korreksjoner fra sesjonen, deretter committer og pusher. |
| `/listhist [nr]` | Vis historiske spørringer, eller kjør spørring nummer N direkte. |
| `/tilxl [spørring]` | Eksporter til Excel. Uten argument: forrige spørring. Med argument: kjør, vis, bekreft, eksporter. |
| `/tilbilde [spørring]` | Eksporter til PNG-bilde. Samme logikk som `/tilxl`. |
| `/graf` | Analyser forrige datasett og lag passende graf. Spør om graf-type og preferanser. |

---

## Mappestruktur

```
auto-uttrekk/
  CLAUDE.md         # Regler og instruksjoner
  CORRECTIONS.md    # Dokumenterte feil og korreksjoner
  QUERY_LOG.md      # Verifiserte spørringer for konsistens
  lib/              # Parquet-data (IKKE endre)
    adr.parquet     # Adresseregister (adresse-nivå)
    fbb.parquet     # Fastbredbånd dekning (adresse-nivå)
    mob.parquet     # Mobildekning (adresse-nivå)
    ab.parquet      # Abonnementer (adresse-nivå)
    ekom.parquet    # Ekommarkedsstatistikk (nasjonalt nivå)
  library/          # Python-bibliotek
    loader.py       # Datalasting og stier
    filters.py      # Filterfunksjoner
    validation.py   # Validering og lagring
  uttrekk/          # Dine scripts og resultater
    2026-01-10/
      01_fiber_dekning.py
      01_fiber_dekning.xlsx
```

---

## Library-funksjoner

```python
from library import (
    # Lasting
    load_data,          # -> (adr, fbb, mob, ab) som LazyFrames
    load_dataset,       # -> én LazyFrame
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
)
```

---

## Data Dictionary

### adr.parquet - Adresseregister

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| adrid | Int64 | Unik adresse-ID (primary key) |
| fylke | String | Fylkesnavn |
| komnavn | String | Kommunenavn |
| ertett | Boolean | True = tettsted, False = spredtbygd |
| hus | Int16 | Antall husstander |
| pers | Int16 | Antall personer |
| fritid | Int16 | Antall fritidsboliger |

### fbb.parquet - Fastbredbånd

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| adrid | Int64 | Adresse-ID (foreign key) |
| tilb | String | Tilbydernavn |
| tek | String | "fiber", "ftb", "kabel", "radio", "satellitt", "annet" |
| ned | Int64 | Maks nedlasting i **kbps** |
| opp | Int64 | Maks opplasting i **kbps** |
| hc | Boolean | True = Homes Connected, False = Homes Passed |
| egen | Boolean | True = eier egen infrastruktur |

### mob.parquet - Mobildekning

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| adrid | Int64 | Adresse-ID |
| tilb | String | "telenor", "telia", "ice" |
| tek | String | "4g", "5g" |
| ned | Int32 | Maks nedlasting i **kbps** |

### ab.parquet - Abonnementer

| Kolonne | Type | Beskrivelse |
|---------|------|-------------|
| adrid | Int64 | Adresse-ID (0 = ingen direkte kobling) |
| fylke | String | Fylkesnavn |
| komnavn | String | Kommunenavn |
| tilb | String | Tilbyder |
| tek | String | Teknologi |
| ned | Int64 | Abonnert hastighet i **kbps** |
| privat | Boolean | True = privat, False = bedrift |
| kol | Boolean | True = MDU (kollektiv), False = SDU |
| egen | Boolean | Egen infrastruktur |

**Viktig for ab:** Tell rader for antall abonnementer. Ikke join med adr - bruk fylke/komnavn direkte.

### ekom.parquet - Ekommarkedsstatistikk (nasjonalt nivå)

Aggregert markedsstatistikk per tilbyder og rapporteringsperiode (2000-2025).

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

#### KRITISKE REGLER FOR EKOM

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

#### Enheter

| hg | Enhet |
|----|-------|
| Abonnement | Antall (stk) |
| Inntekter | NOK 1000 (tusen kroner) |
| Trafikk (tale) | 1000 minutter |
| Trafikk (SMS) | 1000 meldinger |
| Trafikk (data) | Gigabyte |

#### Hovedkategorier (hk)

- Fast bredbånd
- Mobiltjenester
- TV-tjenester
- Fasttelefoni
- Datakommunikasjon (VPN, alltid bedrift)
- Overføringskapasitet
- Investeringer
- Antall årsverk

---

## Hastighetskonvertering

Data lagres i **kbps**. Brukere sier **Mbit/s**.

| Bruker sier | Filter |
|-------------|--------|
| "over 100 Mbit" | `ned >= 100_000` |
| "over 1 Gbit" | `ned >= 1_000_000` |

Bruk `filter_hastighet(df, 100)` - konverterer automatisk.

---

## Terminologi

| Term | Betydning | Filter |
|------|-----------|--------|
| fiber | Fiberoptisk | `tek == "fiber"` |
| ftb | Fast trådløst bredbånd | `tek == "ftb"` |
| HC | Homes Connected | `hc == true` |
| HP | Homes Passed | `hc == false` |
| MDU | Multi-Dwelling Unit | `kol == true` |
| SDU | Single-Dwelling Unit | `kol == false` |
| tettsted | Urbant område | `ertett == true` |
| spredtbygd | Ruralt område | `ertett == false` |

---

## Vanlige Feil å Unngå

| Feil | Riktig |
|------|--------|
| `> 100_000` for "over 100" | `>= 100_000` |
| Forveksle "ftb" med "fbb" | ftb = teknologi, fbb = datafil |
| Sjekke `adrid.is_not_null()` etter join | Legg til markør-kolonne før join |
| Summere `hus` fra ab | Tell rader for ab |
| Joine ab med adr | Bruk ab.fylke direkte |

---

## Selvkorrigering

Når du gjør en feil (oppdaget selv eller påpekt av bruker):

1. **Rett feilen** og fortsett
2. **Husk feilen** for logging ved `/loggpush`
3. **Ikke logg underveis** - dette gjøres samlet til slutt

### Ved /loggpush - dokumenter feilen i CORRECTIONS.md

Legg til en ny seksjon med:
- Dato og kort beskrivelse
- Kontekst: hva prøvde du å gjøre?
- Hva ble gjort feil
- Hva er riktig fremgangsmåte
- Hvorfor dette er riktig

### Vurder promotering til CLAUDE.md

Hvis feilen:
- Er en vanlig fallgruve
- Gjentar seg
- Er lett å gjøre igjen

→ Legg den til i "Vanlige Feil å Unngå"-tabellen og merk korreksjonen som "Promotert: Ja"

### Før nye uttrekk

Les alltid gjennom CORRECTIONS.md for å unngå å gjenta tidligere feil.

---

## Spørringslogging

For å sikre konsistens over tid, logg vellykkede DuckDB-spørringer.

### Når logge?

**IKKE logg underveis i sesjonen.** Hold styr på verifiserte spørringer og feil mentalt, og logg alt samlet når brukeren kjører `/loggpush`.

Under sesjonen:
1. Spør brukeren: "Er dette resultatet korrekt?"
2. Hvis ja: Husk spørringen for logging senere
3. Gi påminnelse: "Husk `/loggpush` for å lagre sesjonen."

### Hva logges (ved /loggpush)?

- Brukerens opprinnelige spørsmål (naturlig språk)
- Den verifiserte SQL-spørringen
- Kort oppsummering av resultatet
- Eventuelle viktige notater om tolkning
- Korreksjoner (feil som ble gjort og rettet)

### Før nye spørringer

Sjekk `QUERY_LOG.md` for lignende spørsmål. Hvis du finner en match:
- Bruk den verifiserte SQL-en som utgangspunkt
- Tilpass kun det som er nødvendig for det nye spørsmålet

### Promotering til CLAUDE.md

Hvis en spørring:
- Representerer et vanlig mønster
- Brukes gjentatte ganger
- Illustrerer en viktig teknikk

→ Promoter den til "DuckDB Query Patterns"-seksjonen og merk som "Promotert: Ja"

---

## Workflow-eksempel

Bruker: "Finn fiberdekning i spredtbygd per fylke"

```python
"""
Uttrekk: Fiberdekning i spredtbygd

Kriterier:
- Kilde: fbb
- Teknologi: fiber
- Populasjon: spredtbygd (ertett=false)
- Aggregering: fylke + nasjonalt
- Metrikk: husstander
"""

import polars as pl
from library import (
    load_data,
    get_script_paths,
    filter_teknologi,
    filter_populasjon,
    add_national_aggregate,
    validate_and_save,
)

# Stier
_, excel_path = get_script_paths("fiber_spredtbygd")

# 1. Last data
adr, fbb, _, _ = load_data()

# 2. Finn adresser med fiber
fiber_adrid = (
    filter_teknologi(fbb, ["fiber"])
    .select("adrid")
    .unique()
    .with_columns(pl.lit(True).alias("har_fiber"))
)

# 3. Filtrer til spredtbygd og join
adr_spredtbygd = filter_populasjon(adr, "spredtbygd")

per_fylke = (
    adr_spredtbygd
    .join(fiber_adrid, on="adrid", how="left")
    .group_by("fylke")
    .agg(
        pl.col("hus").filter(pl.col("har_fiber") == True).sum().alias("hus_fiber"),
        pl.col("hus").sum().alias("totalt_hus"),
    )
    .with_columns(
        (pl.col("hus_fiber") / pl.col("totalt_hus") * 100).round(1).alias("prosent")
    )
    .sort("fylke")
    .collect()
)

# 4. Legg til nasjonalt
resultat = add_national_aggregate(per_fylke, "hus_fiber", "totalt_hus")

# 5. Valider og lagre
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
| Abonnementer nasjonalt | ~2-3 millioner |

---

## DuckDB Query Patterns

For direkte spørsmål (uten `/ny`), bruk DuckDB CLI. Her er vanlige mønstre:

### Enkle aggregeringer

```sql
-- Totalt husstander
SELECT SUM(hus) FROM 'lib/adr.parquet'

-- Tell abonnementer per teknologi
SELECT tek, COUNT(*) as antall
FROM 'lib/ab.parquet'
GROUP BY tek ORDER BY antall DESC

-- Tilbydere i en kommune
SELECT DISTINCT tilb FROM 'lib/fbb.parquet' f
JOIN 'lib/adr.parquet' a ON f.adrid = a.adrid
WHERE a.komnavn = 'HATTFJELLDAL'
```

### Dekning per område

```sql
-- Dekning (f.eks. 5G) per fylke/kommune
SELECT
    a.fylke,
    SUM(CASE WHEN har_dekning THEN a.hus ELSE 0 END) as hus_dekning,
    SUM(a.hus) as totalt_hus,
    ROUND(SUM(CASE WHEN har_dekning THEN a.hus ELSE 0 END) * 100.0 / SUM(a.hus), 1) as prosent
FROM (
    SELECT a.adrid, a.fylke, a.hus,
           EXISTS(SELECT 1 FROM 'lib/mob.parquet' m
                  WHERE m.adrid = a.adrid AND m.tek = '5g') as har_dekning
    FROM 'lib/adr.parquet' a
) a
GROUP BY a.fylke
ORDER BY prosent DESC
```

### Dekning med hastighetsfilter

```sql
-- 5G med minst 100 Mbit (husk: data er i kbps)
SELECT ...
EXISTS(SELECT 1 FROM 'lib/mob.parquet' m
       WHERE m.adrid = a.adrid AND m.tek = '5g' AND m.ned >= 100000) as har_5g_100
```

### Konkurranse (flere tilbydere)

```sql
-- Adresser med fiber fra minst 2 tilbydere
WITH fiber_tilbydere AS (
    SELECT adrid, COUNT(DISTINCT tilb) as antall_tilbydere
    FROM 'lib/fbb.parquet'
    WHERE tek = 'fiber'
    GROUP BY adrid
)
SELECT
    a.fylke,
    SUM(CASE WHEN ft.antall_tilbydere >= 2 THEN a.hus ELSE 0 END) as hus_konkurranse,
    SUM(a.hus) as totalt_hus
FROM 'lib/adr.parquet' a
LEFT JOIN fiber_tilbydere ft ON a.adrid = ft.adrid
GROUP BY a.fylke
```

### Penetrasjon (dekning vs abonnement)

```sql
-- Sammenlign dekning og abonnementer per tilbyder
WITH dekning AS (
    SELECT tilb, SUM(a.hus) as hus_dekning
    FROM 'lib/fbb.parquet' f
    JOIN 'lib/adr.parquet' a ON f.adrid = a.adrid
    WHERE f.tek = 'fiber'
    GROUP BY tilb
),
abonnement AS (
    SELECT tilb, COUNT(*) as antall_ab
    FROM 'lib/ab.parquet'
    WHERE tek = 'fiber'
    GROUP BY tilb
)
SELECT
    COALESCE(d.tilb, ab.tilb) as tilbyder,
    COALESCE(d.hus_dekning, 0) as hus_dekning,
    COALESCE(ab.antall_ab, 0) as antall_ab,
    ROUND(ab.antall_ab * 100.0 / d.hus_dekning, 1) as penetrasjon_pct
FROM dekning d
FULL OUTER JOIN abonnement ab ON d.tilb = ab.tilb
ORDER BY hus_dekning DESC
```

### Adresser uten dekning

```sql
-- Husstander uten verken fbb eller mobil
WITH fbb_adr AS (SELECT DISTINCT adrid FROM 'lib/fbb.parquet'),
     mob_adr AS (SELECT DISTINCT adrid FROM 'lib/mob.parquet')
SELECT a.fylke, a.komnavn, SUM(a.hus) as hus_uten_dekning
FROM 'lib/adr.parquet' a
WHERE NOT EXISTS (SELECT 1 FROM fbb_adr WHERE adrid = a.adrid)
  AND NOT EXISTS (SELECT 1 FROM mob_adr WHERE adrid = a.adrid)
GROUP BY a.fylke, a.komnavn
HAVING SUM(a.hus) > 0
ORDER BY hus_uten_dekning DESC
```

### Sanity check: Abonnement uten dekning

```sql
-- Finn adresser med abonnement men uten registrert dekning
WITH fbb_adr AS (SELECT DISTINCT adrid FROM 'lib/fbb.parquet')
SELECT ab.tek, ab.tilb, COUNT(*) as antall_ab
FROM 'lib/ab.parquet' ab
WHERE ab.adrid > 0
  AND NOT EXISTS (SELECT 1 FROM fbb_adr WHERE adrid = ab.adrid)
GROUP BY ab.tek, ab.tilb
ORDER BY antall_ab DESC
```

### Tips

- Bruk alltid `duckdb -c "..."` for å kjøre queries
- Husk hastighetskonvertering: 100 Mbit = 100000 kbps
- For ab: filtrer på `adrid > 0` for å unngå ukoblede abonnementer
- Bruk `EXISTS`/`NOT EXISTS` for effektive dekningssjekker

---

## Ekom Query Patterns

Spørringer mot ekom.parquet (nasjonal markedsstatistikk).

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

### Ekom Tips

- **ALLTID** filtrer på `tp = 'Sum'` for totaler (unntak: fylkesdata som alltid er `tp = 'Herav'`)
- **ALLTID** filtrer på `sk IN ('Sluttbruker', 'Ingen')` med mindre grossist spørres
- For millioner: del på 1000000
- For milliarder NOK (inntekter): del på 1000000 (siden data er i 1000 NOK)
- Sorter på `rapport` for kronologisk rekkefølge
- **Fylkesdata:** Kun tilgjengelig for mobilabonnement fra 2025-Halvår, ligger i `n1`-kolonnen

---

## Tidligere Uttrekk

Før du skriver nytt script, sjekk disse mappene:

```bash
# Fullførte uttrekk
ls uttrekk/*/

# Eksempel-scripts
ls examples/
```

Bruk eksisterende scripts som utgangspunkt.
