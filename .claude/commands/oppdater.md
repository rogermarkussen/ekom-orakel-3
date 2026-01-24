# /oppdater - Administrer forretningsdefinisjoner

Administrer varige forretningsdefinisjoner som automatisk appliseres i spørringer.

## Moduser

Parse argumentene for å bestemme modus:

| Argument | Modus | Eksempel |
|----------|-------|----------|
| `ny <navn>` | Opprett ny definisjon | `/oppdater ny samlet_omsetning` |
| `vis` | Vis alle definisjoner | `/oppdater vis` |
| `rediger <navn>` | Rediger definisjon | `/oppdater rediger samlet_omsetning` |
| `slett <navn>` | Slett definisjon | `/oppdater slett samlet_omsetning` |
| (ingen) | Vis hjelp | `/oppdater` |

## Modus: `ny`

1. Spør om **beskrivelse** (norsk forklaring)
2. Spør om **applies_to** (ekom / coverage / begge)
3. Bygg filtre interaktivt:
   - Vis tilgjengelige filtertyper: `tp`, `sk`, `hk_not`, `ms`, `dk`, `tek`
   - La bruker legge til filtre ett om gangen
   - Vis oppsummering og bekreft

```python
from library import KnowledgeBase

kb = KnowledgeBase()
kb.add_definition(
    name="<navn>",
    description="<brukerens beskrivelse>",
    filters={...},
    applies_to="ekom",
    notes="<valgfrie notater>"
)
```

## Modus: `vis`

List alle definisjoner i en pen tabell:

```python
from library import KnowledgeBase

kb = KnowledgeBase()
definitions = kb.list_definitions()

for defn in definitions:
    print(f"**{defn.name}**: {defn.description}")
    print(f"  Gjelder: {defn.applies_to}")
    print(f"  Filtre: {defn.filters}")
```

## Modus: `rediger`

1. Hent eksisterende definisjon
2. Vis nåværende verdier
3. Spør hva bruker vil endre
4. Oppdater med `kb.update_definition()`

## Modus: `slett`

1. Vis definisjonen som skal slettes
2. Be om bekreftelse
3. Slett med `kb.delete_definition()`

## Tilgjengelige filtertyper

| Filter | Beskrivelse | Eksempel |
|--------|-------------|----------|
| `tp` | Tellerpunkt | `"Sum"`, `"Herav"` |
| `sk` | Salgskanal | `"Sluttbruker"`, `"Grossist"` |
| `hk_not` | Ekskluder hovedkategori | `"TV-tjenester"` |
| `ms` | Markedssegment | `"Privat"`, `"Bedrift"` |
| `dk` | Delkategori | `"Mobiltelefoni"` |
| `tek` | Teknologi | `"Fiber"`, `"DSL"` |

## Eksempel: Opprett "samlet_omsetning"

```
Bruker: /oppdater ny samlet_omsetning

Claude: Oppretter definisjon "samlet_omsetning".

Beskriv hva dette begrepet betyr:

Bruker: Total omsetning fra fast bredbånd, ekskludert TV-tjenester

Claude: Gjelder for: (1) ekom, (2) coverage, (3) begge?

Bruker: 1

Claude: Legg til filtre. Tilgjengelige: tp, sk, hk_not, ms, dk, tek
        Skriv "ferdig" når du er klar.

        Filter 1:

Bruker: tp = Sum

Claude: ✓ tp = 'Sum'
        Filter 2:

Bruker: hk_not = TV-tjenester

Claude: ✓ hk != 'TV-tjenester'
        Filter 3:

Bruker: sk = Sluttbruker

Claude: ✓ sk = 'Sluttbruker'
        Filter 4:

Bruker: ferdig

Claude: Oppsummering:
        - Navn: samlet_omsetning
        - Beskrivelse: Total omsetning fra fast bredbånd, ekskludert TV-tjenester
        - Gjelder: ekom
        - Filtre:
          - tp = 'Sum'
          - hk != 'TV-tjenester'
          - sk = 'Sluttbruker'

        Lagre? (ja/nei)

Bruker: ja

Claude: ✓ Definisjon "samlet_omsetning" lagret!

        Bruk: Skriv "samlet omsetning" i spørsmål, så appliseres filtrene automatisk.
```

## Auto-deteksjon

Når definisjoner er lagret, oppdages de automatisk i brukerens input via `detect_definitions()` i QueryMatcher.

Eksempel:
- Bruker: "Hva er samlet omsetning for fiber i 2024?"
- Claude oppdager "samlet omsetning" → appliserer definisjonens filtre
