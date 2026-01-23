# auto-uttrekk

Automatisert dataanalyse av bredbånds- og mobildekning i Norge med Claude Code.

## Hva er dette?

Et AI-assistert analyseverktøy som besvarer spørsmål om norsk telekomdekning. Claude fungerer som en autonom dataanalytiker som skriver og kjører Polars/DuckDB-scripts basert på naturlig språk.

## Datakilder

| Fil | Beskrivelse | Nivå |
|-----|-------------|------|
| `adr.parquet` | Adresseregister med husstander/personer | Adresse |
| `fbb.parquet` | Fastbredbåndsdekning (fiber, FTB, kabel, etc.) | Adresse |
| `mob.parquet` | Mobildekning (4G/5G) | Adresse |
| `ab.parquet` | Bredbåndsabonnementer | Adresse |
| `ekom.parquet` | Ekommarkedsstatistikk (2000-2025) | Nasjonalt |

## Systemkrav

```bash
# Installer DuckDB (CLI)
# macOS:
brew install duckdb

# Linux:
curl -LO https://github.com/duckdb/duckdb/releases/latest/download/duckdb_cli-linux-amd64.zip
unzip duckdb_cli-linux-amd64.zip -d ~/.local/bin

# Windows (PowerShell):
winget install DuckDB.cli

# Installer spatial extension (for Excel-export)
duckdb -c "INSTALL spatial;"
```

Extensions installeres kun én gang - de lagres globalt.

## Bruk

```bash
# Installer avhengigheter
uv sync

# Start Claude Code
claude

# Eksempler på spørringer:
# "Hvor mange husstander har fiberdekning i Nordland?"
# "Vis 5G-dekning per fylke"
# "Markedsandeler for mobilabonnement"

# For å lage et nytt uttrekk med script og Excel-fil:
/ny
```

## Slash-kommandoer

| Kommando | Beskrivelse |
|----------|-------------|
| `/ny` | Start nytt uttrekk. Samler inn krav via dialog og genererer Polars-script med Excel-output. |
| `/loggpush` | Logg verifiserte spørringer til SQLite, commit og push til git. |
| `/listhist [nr]` | Vis alle historiske spørringer, eller kjør spørring nummer N direkte. |
| `/tilxl [spørring]` | Eksporter til Excel. Uten argument: eksporter forrige resultat. Med argument: kjør spørring, vis resultat, bekreft, eksporter. |
| `/tilbilde [spørring]` | Eksporter til PNG-bilde. Samme logikk som `/tilxl`. |
| `/graf` | Analyser forrige datasett og lag passende graf med oppfølgingsspørsmål om preferanser. |

## Mappestruktur

```
lib/           # Parquet-datafiler (ikke endre)
library/       # Python-hjelpefunksjoner
uttrekk/       # Genererte scripts og resultater (YYYY-MM-DD/)
examples/      # Eksempel-scripts
```

## Teknologi

- **Claude Code** - AI-assistent for dataanalyse
- **Polars** - Rask databehandling i Python
- **DuckDB** - SQL-spørringer direkte mot Parquet
- **uv** - Python-pakkehåndtering
