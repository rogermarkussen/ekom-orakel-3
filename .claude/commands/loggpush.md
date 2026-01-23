# Logg, commit og push

Logg alle verifiserte spørringer og korreksjoner fra sesjonen, deretter commit og push.

## Steg 1: Logg sesjonen

Gå gjennom samtalen og identifiser:

1. **Verifiserte spørringer** - DuckDB-spørringer der brukeren bekreftet at resultatet var korrekt
2. **Korreksjoner** - Feil som ble gjort og rettet (f.eks. exit code 1, feil resultat)

Ikke logg noe som allerede er logget tidligere i sesjonen.

### Lagre til SQLite Knowledge Base (Foretrukket)

```python
from library import KnowledgeBase, extract_keywords

kb = KnowledgeBase()

# Legg til spørring
kb.add_query(
    question="Brukerens spørsmål",
    sql="SELECT ...",
    result_summary="Kort oppsummering av resultat",
    category="Dekning",  # Dekning, Konkurranse, Historikk, Ekom, Tilbydere, Abonnement
    tags=extract_keywords("fiber spredtbygd fylke"),  # Eller manuell liste
    notes="Viktige detaljer",
)

# Legg til korreksjon
kb.add_correction(
    context="Hva som ble forsøkt",
    error="Hva som gikk galt",
    solution="Riktig løsning",
    pattern=r"regex for å matche lignende feil",  # Valgfritt
)
```

### Oppdater også markdown (for backward-kompatibilitet)

**1. Oppdater indeksen i QUERY_LOG.md** (øverst i filen):
```markdown
| N | Kategori | Kort beskrivelse | YYYY-MM-DD |
```

**2. Legg til spørringen** (før `<!-- LOGG-SLUTT -->`):
```markdown
<!-- Q:N -->
### Kategori: Beskrivelse

**Spørsmål:** "Brukerens spørsmål"
**Verifisert:** YYYY-MM-DD
**Promotert:** Nei

```sql
-- SQL-spørringen
SELECT ...
```

**Resultat:** Kort oppsummering
**Notater:** Viktige detaljer

---
```

**VIKTIG:**
- Markøren `<!-- Q:N -->` MÅ være på egen linje rett før `###`
- N må matche nummeret i indeksen
- Nye spørringer legges til rett FØR `<!-- LOGG-SLUTT -->`

### Kategorier

| Kategori | Beskrivelse |
|----------|-------------|
| Dekning | Dekningsgrad for teknologier |
| Konkurranse | Tilbyderkonkurranse, markedsandeler |
| Historikk | Trender over tid |
| Ekom | Markedsstatistikk fra ekom.parquet |
| Tilbydere | Spørringer om spesifikke tilbydere |
| Abonnement | Abonnements-data |

### Tags

Bruk `extract_keywords()` for automatisk tagging, eller velg manuelt:

- Teknologi: `fiber`, `ftb`, `kabel`, `dsl`, `5g`, `4g`, `mobil`
- Geografi: `fylke`, `kommune`, `spredtbygd`, `tettsted`
- Metrikk: `dekning`, `hastighet`, `konkurranse`
- Annet: `hc`, `fritidsboliger`, `tilbydere`, `historikk`

## Steg 2: Analyser endringene

```bash
git status
git diff --staged
git diff
```

## Steg 3: Stage endringer

```bash
git add -A
```

## Steg 4: Lag commit-melding

Basert på endringene, lag en kort og forklarende commit-melding på norsk:

- Første linje: Kort oppsummering (maks 50 tegn)
- Bruk imperativ form ("Legg til", "Fiks", "Oppdater", "Fjern")
- Hvis nødvendig, legg til en blank linje og mer kontekst

Eksempler:
- "Legg til spørring om fiberdekning i spredtbygd"
- "Fiks feil i hastighetsfilter"
- "Oppdater knowledge base med nye korreksjoner"

## Steg 5: Commit og push

```bash
git commit -m "Din melding"
git push
```

## Viktig

- Ikke inkluder filer som inneholder sensitiv informasjon
- Sjekk at alle tester/validering passerer før push
- Hvis push feiler pga. remote-endringer, kjør `git pull --rebase` først
- Eksporter JSON backup etter store endringer: `kb.export_json()`
