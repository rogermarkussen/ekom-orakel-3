# Verifiserte Spørringer

Denne filen logger DuckDB-spørringer som brukeren har bekreftet gir korrekte resultater.

---

## Indeks

| # | Kategori | Beskrivelse | Verifisert |
|---|----------|-------------|------------|
| 1 | Ekom | Kontantkort-utvikling 2018-2024 | 2026-01-19 |
| 2 | Abonnement | Fordeling etter adressetype | 2026-01-19 |
| 3 | Dekning | Fastbredbånd per hastighetsklasse per fylke | 2026-01-19 |
| 4 | Dekning | Alle teknologier per fylke (fbb + mob) | 2026-01-19 |
| 5 | Konkurranse | Fiberdekning fordelt på antall tilbydere | 2026-01-19 |
| 6 | Dekning | Husstander med både kabel og fiber-HC | 2026-01-19 |
| 7 | Historikk | Nasjonal teknologidekning 2016-2024 | 2026-01-23 |
| 8 | Konkurranse | Fritidsboliger med fiber fra ≥2 tilbydere (Innlandet) | 2026-01-23 |
| 9 | Konkurranse | Dominerende fibertilbydere i Innlandet | 2026-01-23 |
| 10 | Tilbydere | fbb-tilbydere uten ab-rapportering 2023 | 2026-01-23 |
| 11 | Tilbydere | fbb-tilbydere uten ab-rapportering 2024 | 2026-01-23 |
| 12 | Tilbydere | fbb-tilbydere uten ab-rapportering 2022 | 2026-01-23 |

<!-- INDEKS-SLUTT - Ikke fjern denne linjen -->

---

## Format

```
## Kategori: Kort beskrivelse

**Spørsmål:** Brukerens opprinnelige spørsmål
**Verifisert:** YYYY-MM-DD
**Promotert:** Nei

​```sql
-- SQL-spørringen som ga korrekt svar
SELECT ...
​```

**Resultat:** Kort oppsummering av hva spørringen returnerte
**Notater:** Eventuelle viktige detaljer om tolkning eller begrensninger
```

---

## Logg

### Ekom: Kontantkort-utvikling over tid

**Spørsmål:** "Gi meg utviklingen av kontantkort fra 2018 - 2024 på helårsbasis"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
SELECT
    ar as år,
    ROUND(SUM(svar) / 1000, 0) as tusen_ab
FROM 'lib/ekom.parquet'
WHERE hk = 'Mobiltjenester'
  AND dk = 'Mobiltelefoni'
  AND hg = 'Abonnement'
  AND n1 = 'Kontantkort'
  AND tp = 'Sum'
  AND sk IN ('Sluttbruker', 'Ingen')
  AND delar = 'Helår'
  AND ar BETWEEN 2018 AND 2024
GROUP BY ar
ORDER BY ar
```

**Resultat:** Nedgang fra 755k (2018) til 401k (2024), -47% over perioden
**Notater:** n1 = 'Kontantkort' for kontantkort, n1 = 'Fakturert' for fakturerte abonnement

---

### Abonnement: Fordeling etter adressetype

**Spørsmål:** "Kan du gi meg antall ab som du finner på adresser med hus"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
-- Hovedspørring: Antall ab på adresser med hus
SELECT COUNT(*) as antall_ab
FROM 'lib/ab.parquet' ab
JOIN 'lib/adr.parquet' a ON ab.adrid = a.adrid
WHERE ab.adrid > 0 AND a.hus > 0

-- Utvidet: Fordeling per kategori
SELECT
    CASE
        WHEN ab.adrid = 0 THEN 'Ikke koblet (adrid=0)'
        WHEN a.hus > 0 THEN 'Adresse med hus'
        ELSE 'Adresse uten hus'
    END as kategori,
    COUNT(*) as antall_ab
FROM 'lib/ab.parquet' ab
LEFT JOIN 'lib/adr.parquet' a ON ab.adrid = a.adrid
GROUP BY kategori
ORDER BY antall_ab DESC
```

**Resultat:** 2 207 941 ab på adresser med hus (87%), 315 817 på adresser uten hus, 12 460 ikke koblet
**Notater:** Filtrer på adrid > 0 for koblede ab. Adresser uten hus kan være næringsbygg, fritidsboliger, etc.

---

### Dekning: Fastbredbånd per hastighetsklasse per fylke

**Spørsmål:** "gi meg nå en tabell som har fylker og nasjonalt i første kolonne og de andre kolonnene skal være hastighet 30, 100, 500, 1000. Dette skal være basert på dekningen for alle tek og det skal være basert på husstander"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
WITH dekning AS (
    SELECT
        adrid,
        MAX(ned) as maks_ned
    FROM 'lib/fbb.parquet'
    GROUP BY adrid
),
per_adresse AS (
    SELECT
        a.fylke,
        a.hus,
        COALESCE(d.maks_ned, 0) as maks_ned
    FROM 'lib/adr.parquet' a
    LEFT JOIN dekning d ON a.adrid = d.adrid
),
per_fylke AS (
    SELECT
        fylke,
        SUM(CASE WHEN maks_ned >= 30000 THEN hus ELSE 0 END) as hus_30,
        SUM(CASE WHEN maks_ned >= 100000 THEN hus ELSE 0 END) as hus_100,
        SUM(CASE WHEN maks_ned >= 500000 THEN hus ELSE 0 END) as hus_500,
        SUM(CASE WHEN maks_ned >= 1000000 THEN hus ELSE 0 END) as hus_1000,
        SUM(hus) as totalt_hus
    FROM per_adresse
    GROUP BY fylke
),
resultat AS (
    SELECT
        fylke as Fylke,
        ROUND(hus_30 * 100.0 / totalt_hus, 1) as "30 Mbit",
        ROUND(hus_100 * 100.0 / totalt_hus, 1) as "100 Mbit",
        ROUND(hus_500 * 100.0 / totalt_hus, 1) as "500 Mbit",
        ROUND(hus_1000 * 100.0 / totalt_hus, 1) as "1000 Mbit"
    FROM per_fylke

    UNION ALL

    SELECT
        'NASJONALT' as Fylke,
        ROUND(SUM(hus_30) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_100) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_500) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_1000) * 100.0 / SUM(totalt_hus), 1)
    FROM per_fylke
)
SELECT * FROM resultat
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```

**Resultat:** Nasjonal dekning: 30 Mbit 99.7%, 100 Mbit 99.1%, 500 Mbit 97.1%, 1000 Mbit 96.2%. Oslo høyest, Nordland lavest.
**Notater:** Bruker MAX(ned) per adresse for å finne beste tilgjengelige hastighet. Hastigheter i kbps (30 Mbit = 30000 kbps).

### Dekning: Alle teknologier per fylke (fbb + mob)

**Spørsmål:** "Kan du gi meg den fylkesfordelte dekning på alle teknologier (inkludert mob) - en tek pr kolonne - basert på husstander"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
WITH tek_per_adresse AS (
    SELECT adrid, tek FROM 'lib/fbb.parquet'
    UNION
    SELECT adrid, tek FROM 'lib/mob.parquet'
),
dekning AS (
    SELECT
        a.fylke,
        a.adrid,
        a.hus,
        MAX(CASE WHEN t.tek = 'fiber' THEN 1 ELSE 0 END) as har_fiber,
        MAX(CASE WHEN t.tek = 'ftb' THEN 1 ELSE 0 END) as har_ftb,
        MAX(CASE WHEN t.tek = 'kabel' THEN 1 ELSE 0 END) as har_kabel,
        MAX(CASE WHEN t.tek = 'radio' THEN 1 ELSE 0 END) as har_radio,
        MAX(CASE WHEN t.tek = 'satellitt' THEN 1 ELSE 0 END) as har_satellitt,
        MAX(CASE WHEN t.tek = '4g' THEN 1 ELSE 0 END) as har_4g,
        MAX(CASE WHEN t.tek = '5g' THEN 1 ELSE 0 END) as har_5g
    FROM 'lib/adr.parquet' a
    LEFT JOIN tek_per_adresse t ON a.adrid = t.adrid
    GROUP BY a.fylke, a.adrid, a.hus
),
per_fylke AS (
    SELECT
        fylke,
        SUM(har_fiber * hus) as hus_fiber,
        SUM(har_ftb * hus) as hus_ftb,
        SUM(har_kabel * hus) as hus_kabel,
        SUM(har_radio * hus) as hus_radio,
        SUM(har_satellitt * hus) as hus_satellitt,
        SUM(har_4g * hus) as hus_4g,
        SUM(har_5g * hus) as hus_5g,
        SUM(hus) as totalt_hus
    FROM dekning
    GROUP BY fylke
),
resultat AS (
    SELECT
        fylke as Fylke,
        ROUND(hus_fiber * 100.0 / totalt_hus, 1) as Fiber,
        ROUND(hus_ftb * 100.0 / totalt_hus, 1) as FTB,
        ROUND(hus_kabel * 100.0 / totalt_hus, 1) as Kabel,
        ROUND(hus_radio * 100.0 / totalt_hus, 1) as Radio,
        ROUND(hus_satellitt * 100.0 / totalt_hus, 1) as Satellitt,
        ROUND(hus_4g * 100.0 / totalt_hus, 1) as "4G",
        ROUND(hus_5g * 100.0 / totalt_hus, 1) as "5G"
    FROM per_fylke

    UNION ALL

    SELECT
        'NASJONALT',
        ROUND(SUM(hus_fiber) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_ftb) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_kabel) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_radio) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_satellitt) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_4g) * 100.0 / SUM(totalt_hus), 1),
        ROUND(SUM(hus_5g) * 100.0 / SUM(totalt_hus), 1)
    FROM per_fylke
)
SELECT * FROM resultat
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```

**Resultat:** Nasjonalt: Fiber 91.0%, FTB 96.1%, Kabel 34.1%, Radio 0.0%, Satellitt 55.5%, 4G 100.0%, 5G 99.7%
**Notater:** Kombinerer fbb og mob teknologier. Satellitt-tallene varierer mye mellom fylker (0-100%) pga. rapporteringsforskjeller.

---

### Konkurranse: Fiberdekning fordelt på antall tilbydere per fylke

**Spørsmål:** "Gi meg en fylkesvis fordeling av dekningen for de som har dekning fra flere tilbydere på fiber. Jeg ønsker å vite andelen med kun 1, 2 og 3+. hus"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
WITH fiber_tilbydere AS (
    SELECT adrid, COUNT(DISTINCT tilb) as antall_tilb
    FROM 'lib/fbb.parquet'
    WHERE tek = 'fiber'
    GROUP BY adrid
),
per_adresse AS (
    SELECT
        a.fylke,
        a.hus,
        CASE
            WHEN ft.antall_tilb = 1 THEN '1 tilbyder'
            WHEN ft.antall_tilb = 2 THEN '2 tilbydere'
            ELSE '3+ tilbydere'
        END as kategori
    FROM 'lib/adr.parquet' a
    INNER JOIN fiber_tilbydere ft ON a.adrid = ft.adrid
),
per_fylke AS (
    SELECT
        fylke as Fylke,
        SUM(CASE WHEN kategori = '1 tilbyder' THEN hus ELSE 0 END) as hus_1,
        SUM(CASE WHEN kategori = '2 tilbydere' THEN hus ELSE 0 END) as hus_2,
        SUM(CASE WHEN kategori = '3+ tilbydere' THEN hus ELSE 0 END) as hus_3pluss,
        SUM(hus) as totalt
    FROM per_adresse
    GROUP BY fylke
),
med_andeler AS (
    SELECT
        Fylke,
        hus_1,
        ROUND(hus_1 * 100.0 / totalt, 1) as andel_1,
        hus_2,
        ROUND(hus_2 * 100.0 / totalt, 1) as andel_2,
        hus_3pluss,
        ROUND(hus_3pluss * 100.0 / totalt, 1) as andel_3pluss,
        totalt
    FROM per_fylke
),
nasjonalt AS (
    SELECT
        'NASJONALT' as Fylke,
        SUM(hus_1) as hus_1,
        ROUND(SUM(hus_1) * 100.0 / SUM(totalt), 1) as andel_1,
        SUM(hus_2) as hus_2,
        ROUND(SUM(hus_2) * 100.0 / SUM(totalt), 1) as andel_2,
        SUM(hus_3pluss) as hus_3pluss,
        ROUND(SUM(hus_3pluss) * 100.0 / SUM(totalt), 1) as andel_3pluss,
        SUM(totalt) as totalt
    FROM med_andeler
),
resultat AS (
    SELECT * FROM med_andeler
    UNION ALL
    SELECT * FROM nasjonalt
)
SELECT * FROM resultat
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```

**Resultat:** Nasjonalt: 1 tilbyder 61.6%, 2 tilbydere 26.5%, 3+ tilbydere 11.9%. Agder har høyest konkurranse (31.5% med 3+), Rogaland lavest (80.6% med kun 1).
**Notater:** Basert på husstander med fiberdekning. INNER JOIN sikrer at kun adresser med fiber inkluderes.

---

### Dekning: Husstander med både kabel og fiber-HC

**Spørsmål:** "gi meg fylkesfordelt dekning på adresser med både kabel og fiber-hc. hus"
**Verifisert:** 2026-01-19
**Promotert:** Nei

```sql
WITH kabel_adr AS (
    SELECT DISTINCT adrid
    FROM 'lib/fbb.parquet'
    WHERE tek = 'kabel'
),
fiber_hc_adr AS (
    SELECT DISTINCT adrid
    FROM 'lib/fbb.parquet'
    WHERE tek = 'fiber' AND hc = true
),
begge AS (
    SELECT adrid
    FROM kabel_adr
    INTERSECT
    SELECT adrid
    FROM fiber_hc_adr
),
per_fylke AS (
    SELECT
        a.fylke,
        SUM(CASE WHEN b.adrid IS NOT NULL THEN a.hus ELSE 0 END) as hus_begge,
        SUM(a.hus) as totalt_hus
    FROM 'lib/adr.parquet' a
    LEFT JOIN begge b ON a.adrid = b.adrid
    GROUP BY a.fylke
),
resultat AS (
    SELECT
        fylke as Fylke,
        hus_begge as "Hus med begge",
        totalt_hus as "Totalt hus",
        ROUND(hus_begge * 100.0 / totalt_hus, 1) as "Prosent"
    FROM per_fylke

    UNION ALL

    SELECT
        'NASJONALT',
        SUM(hus_begge),
        SUM(totalt_hus),
        ROUND(SUM(hus_begge) * 100.0 / SUM(totalt_hus), 1)
    FROM per_fylke
)
SELECT * FROM resultat
ORDER BY CASE WHEN Fylke = 'NASJONALT' THEN 1 ELSE 0 END, Fylke
```

**Resultat:** 21.4% nasjonalt (551k hus). Oslo høyest (38.7%), Finnmark lavest (1.6%).
**Notater:** Bruker INTERSECT for å finne adresser med begge teknologier. fiber-HC betyr hc = true.

---

### Historikk: Nasjonal teknologidekning 2016-2024

**Spørsmål:** "Kan du gi meg den nasjonale dekningen for alle teknologier fra 2016 - 2024"
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
-- Faste bredbåndsteknologier
PIVOT (
    SELECT ar, tek, ROUND(dekning * 100, 1) as prosent
    FROM 'lib/dekning_tek.parquet'
    WHERE fylke = 'NASJONALT'
      AND geo = 'totalt'
      AND ar BETWEEN 2016 AND 2024
      AND tek IN ('fiber', 'kabel', 'dsl', 'ftb', 'fiber_kabel', '4g', '5g')
)
ON tek
USING FIRST(prosent)
ORDER BY ar
```

**Resultat:** Fiber økte fra 46.1% (2016) til 91.0% (2024). Kabel sank fra 52.5% til 34.1%. 5G gikk fra 5.4% (2020) til 99.7% (2024).
**Notater:** Bruker dekning_tek.parquet for historiske data. Dekningsverdier er desimaltall (0-1), multipliser med 100 for prosent.

---

### Konkurranse: Fritidsboliger med fiber fra ≥2 tilbydere (Innlandet)

**Spørsmål:** "Hvor stor andel av fritidsboliger i Innlandet fylke har tilbud om fiber fra minst to tilbydere"
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
WITH fiber_tilbydere AS (
    SELECT adrid, COUNT(DISTINCT tilb) as antall_tilbydere
    FROM 'lib/2024/fbb.parquet'
    WHERE tek = 'fiber'
    GROUP BY adrid
)
SELECT
    SUM(CASE WHEN ft.antall_tilbydere >= 2 THEN a.fritid ELSE 0 END) as fritid_2_tilbydere,
    SUM(CASE WHEN ft.antall_tilbydere >= 1 THEN a.fritid ELSE 0 END) as fritid_fiber_totalt,
    SUM(a.fritid) as totalt_fritid,
    ROUND(SUM(CASE WHEN ft.antall_tilbydere >= 2 THEN a.fritid ELSE 0 END) * 100.0 / SUM(a.fritid), 1) as prosent_2_tilbydere
FROM 'lib/2024/adr.parquet' a
LEFT JOIN fiber_tilbydere ft ON a.adrid = ft.adrid
WHERE a.fylke = 'INNLANDET'
```

**Resultat:** 1.2% (1 123 av 92 282 fritidsboliger). 27.7% har fiber fra minst én tilbyder.
**Notater:** Bruker fritid-kolonnen i adr.parquet. Svært begrenset konkurranse for fritidsboliger.

---

### Konkurranse: Dominerende fibertilbydere i Innlandet

**Spørsmål:** "Hvilke tilbydere er det som dominerer i Innlandet"
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
SELECT
    f.tilb,
    SUM(a.hus) as husstander,
    SUM(a.fritid) as fritidsboliger,
    ROUND(SUM(a.hus) * 100.0 / SUM(SUM(a.hus)) OVER (), 1) as andel_hus_pct,
    ROUND(SUM(a.fritid) * 100.0 / SUM(SUM(a.fritid)) OVER (), 1) as andel_fritid_pct
FROM 'lib/2024/fbb.parquet' f
JOIN 'lib/2024/adr.parquet' a ON f.adrid = a.adrid
WHERE a.fylke = 'INNLANDET' AND f.tek = 'fiber'
GROUP BY f.tilb
ORDER BY husstander DESC
LIMIT 15
```

**Resultat:** Eidsiva Bredbånd dominerer med 56.4% av husstander og 78.6% av fritidsboliger. Telenor nr. 2 med 23.0%/11.5%.
**Notater:** Bruker window function for å beregne markedsandeler. Eidsiva har nær monopol på fritidsboliger.

---

### Tilbydere: fbb-tilbydere uten ab-rapportering 2023

**Spørsmål:** "List opp alle tilbydere som har levert data på fast bredbånd (fbb), men som ikke har rapportert ab på adressenivå" (2023)
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
WITH fbb_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2023/fbb.parquet'
),
ab_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2023/ab.parquet'
)
SELECT f.tilb AS tilbyder
FROM fbb_tilbydere f
LEFT JOIN ab_tilbydere a ON f.tilb = a.tilb
WHERE a.tilb IS NULL
ORDER BY f.tilb
```

**Resultat:** 17 tilbydere: avur, bredbåndsfylket, bykle breiband, dragefossen, eltele, fri sikt, hvaler bredbånd, ice, indre salten energi, kraftia, nettstar, nordix data, obos opennet, radiolink telemark, sogn service drift, starlink, øvre eiker fibernett
**Notater:** Tilbydere som rapporterer dekning men ikke abonnenter på adressenivå.

---

### Tilbydere: fbb-tilbydere uten ab-rapportering 2024

**Spørsmål:** "Kan du gjøre det samme for 2024" (tilbydere med fbb men ikke ab)
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
WITH fbb_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2024/fbb.parquet'
),
ab_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2024/ab.parquet'
)
SELECT f.tilb AS tilbyder
FROM fbb_tilbydere f
LEFT JOIN ab_tilbydere a ON f.tilb = a.tilb
WHERE a.tilb IS NULL
ORDER BY f.tilb
```

**Resultat:** 9 tilbydere: altibox bedrift, avur, eiker fibernett, gigafib holding, hvaler bredbånd, lyse tele, lysvatn, nettstar, obos opennet
**Notater:** Reduksjon fra 17 (2023) til 9 (2024) - flere tilbydere har begynt å rapportere ab-data.

---

### Tilbydere: fbb-tilbydere uten ab-rapportering 2022

**Spørsmål:** "Kan du se på 2022 også" (tilbydere med fbb men ikke ab)
**Verifisert:** 2026-01-23
**Promotert:** Nei

```sql
WITH fbb_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2022/fbb.parquet'
),
ab_tilbydere AS (
    SELECT DISTINCT tilb FROM 'lib/2022/ab.parquet'
)
SELECT f.tilb AS tilbyder
FROM fbb_tilbydere f
LEFT JOIN ab_tilbydere a ON f.tilb = a.tilb
WHERE a.tilb IS NULL
ORDER BY f.tilb
```

**Resultat:** 28 tilbydere: austevoll breiband, avur, bardufoss kabel-tv, berger ikt, bitpro, brdy, eltele, eviny breiband, gigafib bredbånd, gp nett, hardangernett, hesbynett, hundeidvik fibernett, hvaler bredbånd, iaksess, kinsarvik breiband, kragerø bredbånd, kvinnherad breiband, net2you, nettstar, numedal fiber, okapi, radiolink telemark, stordal breiband, tinn energi, tranøy telecom, verdal kabel tv, øvre eiker fibernett
**Notater:** Utvikling: 28 (2022) → 17 (2023) → 9 (2024). Klar forbedring i ab-rapportering over tid.

---

<!--
Eksempel på fremtidig loggføring:

## Dekning: Fiberdekning per fylke

**Spørsmål:** "Hvor mange husstander har fiber i hvert fylke?"
**Verifisert:** 2026-01-19
**Promotert:** Ja - finnes i DuckDB Query Patterns

```sql
SELECT
    a.fylke,
    SUM(CASE WHEN har_fiber THEN a.hus ELSE 0 END) as hus_fiber,
    SUM(a.hus) as totalt_hus,
    ROUND(SUM(CASE WHEN har_fiber THEN a.hus ELSE 0 END) * 100.0 / SUM(a.hus), 1) as prosent
FROM (
    SELECT a.adrid, a.fylke, a.hus,
           EXISTS(SELECT 1 FROM 'lib/fbb.parquet' f
                  WHERE f.adrid = a.adrid AND f.tek = 'fiber') as har_fiber
    FROM 'lib/adr.parquet' a
) a
GROUP BY a.fylke
ORDER BY prosent DESC
```

**Resultat:** 15 fylker med fiberdekning fra 87% til 97%
**Notater:** Inkluderer både HC og HP. For kun HC, legg til `AND f.hc = true`
-->
