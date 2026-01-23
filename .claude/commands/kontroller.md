# Kvalitetskontroll av dokument

Verifiser tall i et dokument (Word eller PDF) mot datakildene i systemet.

## Bruk

```
/kontroller
```

Dokumentet hentes automatisk fra `data/`-mappen. Det skal kun være ett dokument der.

## Steg 0: Opprett kontrollrapport

Opprett `kontroll/rapport.md` for løpende oppdatering:

```python
from pathlib import Path

kontroll_dir = Path("kontroll")
kontroll_dir.mkdir(exist_ok=True)
rapport_path = kontroll_dir / "rapport.md"

# Initialiser rapporten
rapport_path.write_text("# Kontrollrapport\n\nKontroll pågår...\n")
```

## Steg 1: Finn og parse dokumentet

Finn dokumentet i data-mappen og ekstraher alle tall med kontekst:

```python
from pathlib import Path
from library.doc_checker import DocumentChecker, find_document

checker = DocumentChecker()
path = find_document()  # Finner automatisk dokumentet i data/

findings = checker.parse_document(path)
print(f"Fant {len(findings)} tall i dokumentet: {path.name}")

# Oppdater rapporten
with open("kontroll/rapport.md", "w") as f:
    f.write(f"# Kontrollrapport: {path.name}\n\n")
    f.write(f"Fant **{len(findings)}** tall å verifisere.\n\n")
    f.write("## Status\n\n")
    f.write("| # | Tall | Status | Kommentar |\n")
    f.write("|---|------|--------|----------|\n")
```

## Steg 2: Interaktiv verifisering

For hvert tall i dokumentet, gå gjennom følgende loop:

### 2.1 Vis tall og kontekst

```
Tall N/TOTALT: "91,2"
Kontekst: "Fiberdekningen i Norge er 91,2 prosent"
Plassering: Avsnitt 5
```

### 2.2 Forsøk auto-match

```python
matches = checker.suggest_match(finding)

if matches and matches[0].confidence >= 0.7:
    match = matches[0]
    print(f"Forslag: {match.description}")
    print(f"SQL: {match.sql}")
    print(f"Forventet: {match.expected_value}")
```

### 2.3 Vis alternativer til bruker

Bruk AskUserQuestion med følgende alternativer basert på situasjonen:

**Høy confidence (>=0.7) med match:**
- **OK** - Tallet er korrekt
- **Avvik** - Tallet avviker fra forventet verdi
- **Juster filter** - Endre filtre i SQL
- **Hopp over** - Ikke verifiser dette tallet

**Lav confidence (<0.7) eller ingen match:**
- **dekning_tek** - Teknologidekning (fiber, 5G, etc.)
- **dekning_hast** - Hastighetsdekning (100/100, etc.)
- **ekom** - Markedsstatistikk (abonnement, inntekter)
- **adr** - Husstander
- **Hopp over** - Ikke verifiser dette tallet

### 2.4 Lær fra svar

Når brukeren velger datakilde eller justerer filter, lær mønsteret:

```python
if user_selected_source:
    checker.learn_pattern(
        context=finding.context,
        source=user_selected_source,
        filters=user_filters
    )
```

### 2.5 Ved "Juster filter"

Spør om spesifikke justeringer:

For **dekning_tek**:
- Teknologi (fiber, 5g, 4g, kabel, ftb)
- Geografi (totalt, tettbygd, spredtbygd)
- År (2013-2024)

For **ekom**:
- Hovedkategori (Fast bredbånd, Mobiltjenester)
- Hovedgruppe (Abonnement, Inntekter)
- Teknologi (Fiber, DSL, etc.)
- Markedssegment (Privat, Bedrift)
- Rapport (2024-Helår, etc.)

## Steg 3: Oppdater rapport løpende

Etter hvert tall som verifiseres, oppdater `kontroll/rapport.md`:

```python
def update_rapport(findings, results, rapport_path="kontroll/rapport.md"):
    with open(rapport_path, "w") as f:
        f.write(f"# Kontrollrapport\n\n")
        f.write(f"Totalt **{len(findings)}** tall funnet.\n\n")

        # Statistikk
        verified = sum(1 for r in results if r.get("status") == "OK")
        avvik = sum(1 for r in results if r.get("status") == "Avvik")
        skipped = sum(1 for r in results if r.get("status") == "Hoppet over")
        pending = len(findings) - len(results)

        f.write("## Oppsummering\n\n")
        f.write(f"- ✅ Verifisert OK: {verified}\n")
        f.write(f"- ⚠️ Avvik: {avvik}\n")
        f.write(f"- ⏭️ Hoppet over: {skipped}\n")
        f.write(f"- ⏳ Gjenstår: {pending}\n\n")

        # Detaljert tabell
        f.write("## Detaljer\n\n")
        f.write("| # | Tall | Kontekst | Status | Forventet | Kilde |\n")
        f.write("|---|------|----------|--------|-----------|-------|\n")

        for i, finding in enumerate(findings):
            result = results[i] if i < len(results) else {}
            status = result.get("status", "⏳")
            expected = result.get("expected", "-")
            source = result.get("source", "-")
            context_short = finding.context[:40] + "..." if len(finding.context) > 40 else finding.context
            f.write(f"| {i+1} | {finding.raw_text} | {context_short} | {status} | {expected} | {source} |\n")
```

## Steg 4: Oppsummering

Etter å ha gått gjennom alle tall, vis oppsummering og skriv ferdig rapport:

```python
summary = checker.get_verification_summary(findings, results)

print(f"""
Oppsummering:
- Totalt tall funnet: {summary['totalt']}
- Verifisert OK: {summary['verifisert']}
- Avvik funnet: {summary['avvik']}
- Hoppet over: {summary['hoppet_over']}
- Ingen match: {summary['ingen_match']}

Verifiseringsgrad: {summary['prosent_verifisert']}%
""")

# Marker rapporten som ferdig
print("Kontrollrapport ferdig: kontroll/rapport.md")
```

## Eksempel på output

```
=== Kvalitetskontroll: rapport.docx ===
Fant 47 tall i dokumentet

Tall 1/47: "91,2"
Kontekst: "Fiberdekningen i Norge er 91,2 prosent"
Plassering: Avsnitt 3

Forslag: dekning_tek WHERE tek='fiber' AND geo='totalt' AND ar=2024
Forventet: 91.2%
Confidence: 90%

[OK] Verifisert → Oppdaterer kontroll/rapport.md

---

...

=== Oppsummering ===
Totalt: 47
Verifisert: 38
Avvik: 5
Hoppet over: 4

Verifiseringsgrad: 80.9%
Kontrollrapport: kontroll/rapport.md
```

## Tips

- Start med de første 10-15 tallene for å lære opp matchingen
- Etter hvert vil flere tall auto-matches med høy confidence
- Mønstrene lagres kun i sesjonen - de forsvinner når du avslutter
- Bruk "Hopp over" for tall som ikke er fra våre datakilder (f.eks. budsjett, prognoser)
- Sjekk `kontroll/rapport.md` underveis for å se fremgang

## Feilhåndtering

Hvis dokumentet ikke kan leses:
- For Word: Sjekk at python-docx er installert: `uv add python-docx`
- For PDF: Sjekk at pdfplumber er installert: `uv add pdfplumber`

Hvis ingen dokument finnes i data/:
- Legg dokumentet (Word eller PDF) i `data/`-mappen
- Det skal kun være ett dokument der

Hvis ingen tall finnes:
- Dokumentet kan være skannet bilde (PDF uten OCR)
- Prøv et annet dokument
