# Markedsandel - Tilbyderanalyse

Beregn markedsandeler per tilbyder med automatisk rangering og konsentrasjonsanalyse.

## Bruk

- `/markedsandel [kategori] [segment] [år] [modifikatorer]`

### Eksempler

```
/markedsandel fiber privat 2024
/markedsandel mobil inntekter 2024
/markedsandel fbb bedrift topp5
/markedsandel fiber 2020-2024
```

## Instruksjoner

### Steg 1: Parse brukerens input

**Kategori (hk):**
| Input | hk-verdi |
|-------|----------|
| fiber | Fast bredbånd + tek=Fiber |
| fbb | Fast bredbånd |
| mobil | Mobiltjenester |
| ftb | Fast bredbånd + tek=FTB |

**Metrikk:**
- `abonnement` (default)
- `inntekter`
- `trafikk`

**Segment:**
- `privat` → ms="Privat"
- `bedrift` → ms="Bedrift"
- `samlet` → ingen ms-filter (default)

**Modifikatorer:**
- `topp5` → Vis kun topp 5 tilbydere + "Andre"
- `topp10` → Vis kun topp 10 tilbydere + "Andre"
- `hhi` → Inkluder Herfindahl-Hirschman Index

### Steg 2: Hent data per tilbyder

```python
from library import EkomQuery
import polars as pl

# Eksempel: /markedsandel fiber privat 2024
query = EkomQuery(
    hk="Fast bredbånd",
    hg="Abonnement",
    tek="Fiber",
    ms="Privat",
    rapport="2024-Helår",
    group_by=["fusnavn"],  # Grupper per tilbyder
    pivot_years=False
)

df = query.execute()
```

### Steg 3: Beregn markedsandeler

```python
# Beregn total
total = df["svar"].sum()

# Beregn andel
df = df.with_columns([
    (pl.col("svar") / total * 100).round(2).alias("andel_pst")
])

# Sorter etter størrelse
df = df.sort("svar", descending=True)

# For topp N: Samle resten i "Andre"
if topp_n:
    topp = df.head(topp_n)
    andre = df.tail(-topp_n)
    andre_sum = andre["svar"].sum()
    andre_pst = andre["andel_pst"].sum()

    andre_row = pl.DataFrame({
        "fusnavn": ["Andre"],
        "svar": [andre_sum],
        "andel_pst": [andre_pst]
    })

    df = pl.concat([topp, andre_row])
```

### Steg 4: Beregn HHI (valgfritt)

Herfindahl-Hirschman Index måler markedskonsentrasjon:
- HHI < 1500: Lav konsentrasjon (konkurransedyktig marked)
- HHI 1500-2500: Moderat konsentrasjon
- HHI > 2500: Høy konsentrasjon

```python
# HHI = sum av kvadrerte markedsandeler
hhi = (df["andel_pst"] ** 2).sum()

if hhi < 1500:
    konsentrasjon = "Lav (konkurransedyktig)"
elif hhi < 2500:
    konsentrasjon = "Moderat"
else:
    konsentrasjon = "Høy (konsentrert)"
```

### Steg 5: Vis resultat

```
Markedsandeler: Fiber Privat 2024

┌──────────────────────┬─────────────┬───────────┐
│ Tilbyder             │ Abonnement  │ Andel (%) │
├──────────────────────┼─────────────┼───────────┤
│ Telenor Norge AS     │     623 456 │     32.4  │
│ Telia Norge AS       │     412 789 │     21.5  │
│ Altibox AS           │     298 123 │     15.5  │
│ GlobalConnect AS     │     189 456 │      9.9  │
│ Lyse Tele AS         │     134 567 │      7.0  │
│ Andre                │     264 321 │     13.7  │
├──────────────────────┼─────────────┼───────────┤
│ TOTALT               │   1 922 712 │    100.0  │
└──────────────────────┴─────────────┴───────────┘

HHI: 1 847 (Moderat konsentrasjon)
CR3: 69.4% (Topp 3 tilbyderes andel)
```

## Interaktiv modus

Hvis argumenter mangler, spør via AskUserQuestion:

1. **Kategori:** Fiber, FBB samlet, Mobil?
2. **Metrikk:** Abonnement, Inntekter, eller Trafikk?
3. **Segment:** Privat, Bedrift, eller Samlet?
4. **År:** Hvilket år?
5. **Antall tilbydere:** Alle, Topp 5, eller Topp 10?

## Tidsserieanalyse

For å se utvikling over tid:

```
/markedsandel fiber privat 2020-2024

Utvikling markedsandeler: Fiber Privat

┌──────────────────┬────────┬────────┬────────┬────────┬────────┐
│ Tilbyder         │   2020 │   2021 │   2022 │   2023 │   2024 │
├──────────────────┼────────┼────────┼────────┼────────┼────────┤
│ Telenor Norge AS │  38.2% │  36.5% │  34.8% │  33.2% │  32.4% │
│ Telia Norge AS   │  18.3% │  19.2% │  20.1% │  20.8% │  21.5% │
│ Altibox AS       │  14.1% │  14.5% │  14.9% │  15.2% │  15.5% │
│ ...              │        │        │        │        │        │
└──────────────────┴────────┴────────┴────────┴────────┴────────┘

Trend: Telenor mister markedsandeler (-5.8 pp), Telia øker (+3.2 pp)
```

## Viktige regler

1. **Datakommunikasjon:** For FBB Bedrift inkluderes Datakommunikasjon automatisk
2. **Fusjonsnavn:** Bruk `fusnavn` for konsistente tilbydergrupper
3. **Runding:** Andeler rundes til 2 desimaler

## Sammenligning med konkurrenter

For å sammenligne to spesifikke tilbydere:

```
/markedsandel fiber telenor telia 2020-2024

Telenor vs Telia: Fiberabonnement

┌─────────────────┬────────────┬────────────┐
│ År              │ Telenor    │ Telia      │
├─────────────────┼────────────┼────────────┤
│ 2020            │     38.2%  │     18.3%  │
│ 2024            │     32.4%  │     21.5%  │
├─────────────────┼────────────┼────────────┤
│ Endring         │     -5.8pp │     +3.2pp │
└─────────────────┴────────────┴────────────┘
```

## Eksport og visualisering

Etter visning, tilby:
- `/tilxl` - Eksporter til Excel
- `/graf` - Lag kakediagram eller søylediagram
- `/tilbilde` - Lagre som PNG

## Feilhåndtering

- Ukjent tilbyder: Vis liste over tilgjengelige tilbydere
- Tomt resultat: Sjekk at kategori/segment-kombinasjonen er gyldig
- For mange tilbydere: Anbefal topp10 eller topp5 filter
