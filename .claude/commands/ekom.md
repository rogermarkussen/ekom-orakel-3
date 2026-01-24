# Rask ekom-spørring

Kjør ekom-spørringer direkte uten å skrive script. Bruker `EkomQuery` for å automatisk håndtere alle komplekse regler.

## Bruk

- `/ekom [kategori] [metrikk] [år/periode] [modifikatorer]`

### Eksempler

```
/ekom fiber abonnement 2024
/ekom mobil inntekter 2020-2024 pivot
/ekom fbb bedrift tilbyder
/ekom kabel trafikk 2023
/ekom fiber privat 2022-2024
```

## Instruksjoner

### Steg 1: Parse brukerens input

Tolk argumentene og identifiser følgende:

**Kategori (hk):**
| Input | hk-verdi |
|-------|----------|
| fiber | Fast bredbånd + tek=Fiber |
| fbb | Fast bredbånd |
| mobil | Mobiltjenester |
| ftb | Fast bredbånd + tek=FTB |
| kabel | Fast bredbånd + tek=Kabel |
| dsl | Fast bredbånd + tek=DSL |

**Metrikk (hg):**
| Input | hg-verdi |
|-------|----------|
| abonnement, abo, ab | Abonnement |
| inntekter, innt | Inntekter |
| trafikk, traf | Trafikk |

**Periode:**
- Enkelår: `2024` → `rapport="2024-Helår"`
- Range: `2020-2024` → `rapport=["2020-Helår", "2021-Helår", "2022-Helår", "2023-Helår", "2024-Helår"]`
- Halvår: `2024h1` → `rapport="2024-Halvår"`

**Modifikatorer:**
| Input | Effekt |
|-------|--------|
| bedrift | ms="Bedrift" |
| privat | ms="Privat" |
| tilbyder | group_by=["fusnavn"] |
| pivot | pivot_years=True (default) |

### Steg 2: Bygg og kjør spørringen

```python
from library import EkomQuery

# Eksempel: /ekom fiber abonnement 2022-2024
query = EkomQuery(
    hk="Fast bredbånd",
    hg="Abonnement",
    tek="Fiber",
    rapport=["2022-Helår", "2023-Helår", "2024-Helår"],
    pivot_years=True
)

print(query.describe())  # Vis beskrivelse
df = query.execute()
print(df)
```

### Steg 3: Vis resultat

1. Vis tabellen med resultater
2. For tall over 1000, formater med mellomrom (1 234 567)
3. For inntekter, angi at tall er i MNOK eller tusen kr

### Steg 4: Tilby eksport

Spør brukeren:
- Vil du eksportere til Excel? (`/tilxl`)
- Vil du lage en graf? (`/graf`)

## Interaktiv modus

Hvis brukeren bare skriver `/ekom` uten argumenter, spør om:

1. **Kategori:** Fiber, FBB, Mobil, FTB, Kabel, DSL?
2. **Metrikk:** Abonnement, Inntekter, eller Trafikk?
3. **Periode:** Hvilket år eller årsrange?
4. **Segment:** Privat, Bedrift, eller Samlet?

Bruk AskUserQuestion for å samle inn svarene.

## Viktige regler

1. **Datakommunikasjon:** For FBB Bedrift legges Datakommunikasjon til automatisk
2. **tp='Sum':** Håndteres automatisk av EkomQuery
3. **sk-filter:** Kun sluttbrukerdata (automatisk)

## Eksempel-output

```
/ekom fiber abonnement 2022-2024

Spørring: Fast bredbånd (Abonnement) - Fiber [2022-Helår - 2024-Helår]

┌───────────┬───────────┬───────────┐
│ 2022-Helår│ 2023-Helår│ 2024-Helår│
├───────────┼───────────┼───────────┤
│ 1 654 321 │ 1 789 012 │ 1 923 456 │
└───────────┴───────────┴───────────┘

Vekst 2022→2024: +16.3%

Vil du eksportere til Excel eller lage graf?
```

## Feilhåndtering

- Hvis kategorien ikke gjenkjennes, vis tilgjengelige alternativer
- Hvis årstallet er utenfor 2000-2025, gi feilmelding
- Ved tomme resultater, sjekk om filtrene er for restriktive
