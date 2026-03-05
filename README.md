# auto-uttrekk

Automatisert dataanalyse av bredbånds- og mobildekning i Norge for kodeagenter som GPT-5.4 og Claude Code.

## Hva er dette?

Et AI-assistert analyseverktøy som besvarer spørsmål om norsk telekomdekning og ekomstatistikk. Repoet inneholder domenedokumentasjon, query-builders, guardrails og tester slik at agenten kan svare konsistent på naturlig språk.

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

# Start valgfri kodeagent i repoet

# Eksempler på spørringer:
# "Hvor mange husstander har fiberdekning i Nordland?"
# "Vis 5G-dekning per fylke"
# "Markedsandeler for mobilabonnement"

# Kjør tilsvarende CLI-kommandoer i terminalen:
uv run orakel /ekom fiber abonnement 2024
uv run orakel /listhist
uv run orakel /markedsandel fiber privat 2024 topp5
uv run orakel /sammenlign fiber 2022 2024 fylke
uv run orakel /sammenlign 100mbit 2022 2024 fylke
uv run orakel /sammenlign 1gbit 2021 2024 nasjonal
uv run orakel /tilxl /ekom fiber abonnement 2024
uv run orakel /graf

# For å lage et nytt uttrekk med script og Excel-fil:
/ny
```

## Anbefalt Arbeidsflyt

1. Les [AGENTS.md](/home/rmarkussen/dev/ekom-orakel-3/AGENTS.md#L1) for modellnøytrale regler.
2. Bruk `execute_malloy()` for raske dekningsspørringer per fylke i 2024.
3. Bruk `CoverageQuery` eller `execute_coverage()` for øvrige dekningsspørringer.
4. Bruk `EkomQuery` eller `execute_ekom()` for ekomstatistikk.
5. Bruk `execute_mobilabonnement_fylke()` for fylkesfordelt mobilabonnement fra og med `2025-Halvår`.
6. Bruk `uv run orakel /...` når du vil kjøre repoets CLI-kommandoer direkte fra terminalen.

## Guardrails

- Mobildekning går automatisk mot `mob.parquet`, ikke `fbb.parquet`.
- Kommunegruppering i dekning bruker `komnavn`.
- Mobilteknologi kan ikke kombineres med HC/HP-filter.
- Mobilabonnement per fylke krever eksplisitt periode og er bare tilgjengelig fra `2025-Halvår`.
- `ab.parquet` skal telles som rader, ikke joins mot `adr.parquet`.

## Slash-kommandoer

| Kommando | Beskrivelse |
|----------|-------------|
| `/ny` | Start nytt uttrekk. Samler inn krav via dialog og genererer Polars-script med Excel-output. |
| `/loggpush` | Logg verifiserte spørringer til SQLite, commit og push til git. |
| `/listhist [nr]` | Vis alle historiske spørringer, eller kjør spørring nummer N direkte. |
| `/tilxl [spørring]` | Eksporter til Excel. Uten argument: eksporter forrige resultat. Med argument: kjør spørring, vis resultat, bekreft, eksporter. |
| `/tilbilde [spørring]` | Eksporter til PNG-bilde. Samme logikk som `/tilxl`. |
| `/graf` | Analyser forrige datasett og lag passende graf automatisk. Bruker horisontale stolper for fordelinger, linjer for tidsserier og fremhever `NASJONALT`. |

## CLI-notater

- `/sammenlign` støtter både teknologier og generiske terskler som `100mbit` og `1gbit`.
- Historiske hastighetsammenligninger før `2022` støttes foreløpig nasjonalt.
- `/graf` følger fargene og prioriteringene i `docs/v1/DESIGNMAL.md` med tydelig tittel, undertittel og kildehint.

## Mappestruktur

```
AGENTS.md      # Modellnøytral instruks for kodeagenter
lib/           # Parquet-datafiler (ikke endre)
library/       # Python-hjelpefunksjoner
tests/         # Guardrails og gullspørsmål
uttrekk/       # Genererte scripts og resultater (YYYY-MM-DD/)
examples/      # Eksempel-scripts
```

## Teknologi

- **GPT-5.4 / Claude Code** - AI-assistenter for dataanalyse
- **Polars** - Rask databehandling i Python
- **DuckDB** - SQL-spørringer direkte mot Parquet
- **uv** - Python-pakkehåndtering

## Test

```bash
uv run python -m unittest discover -s tests -v
```
