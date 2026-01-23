# Kvalitetskontroll av dokument

Verifiser tall i et dokument (Word eller PDF) mot datakildene i systemet.

## Bruk

```
/kontroller
```

Dokumentet hentes automatisk fra `data/`-mappen. Det skal kun være ett dokument der.

## Steg 0: Opprett Excel-rapport

Opprett `kontroll/rapport.xlsx` for løpende oppdatering:

```python
from pathlib import Path
import polars as pl

kontroll_dir = Path("kontroll")
kontroll_dir.mkdir(exist_ok=True)
rapport_path = kontroll_dir / "rapport.xlsx"

# Initialiser tom Excel-fil med kolonner
df = pl.DataFrame({
    "Nr": pl.Series([], dtype=pl.Int64),
    "Side": pl.Series([], dtype=pl.Int64),
    "Tall": pl.Series([], dtype=pl.Utf8),
    "Kontekst": pl.Series([], dtype=pl.Utf8),
    "Status": pl.Series([], dtype=pl.Utf8),
    "Beregnet": pl.Series([], dtype=pl.Utf8),
    "Kilde": pl.Series([], dtype=pl.Utf8),
})
df.write_excel(rapport_path)
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
```

## Steg 2: Verifisering med auto-godkjenning

For hvert tall i dokumentet:

### 2.1 Beregn verdi fra datakilde

Basert på konteksten, kjør passende query mot ekom/dekning_tek/etc.

### 2.2 Sammenlign med automatisk avrunding

```python
def values_match(doc_value: str, calculated_value: float) -> bool:
    """
    Sjekk om beregnet verdi matcher dokumentet når avrundet til samme nøyaktighet.

    Eksempler:
    - doc="20,7", calc=20.70 → True (avrundet til 1 desimal)
    - doc="58", calc=58.2 → True (avrundet til heltall)
    - doc="33,4", calc=33.7 → False (avvik på 0.3)
    - doc="925", calc=941 → False (avvik på 16)
    """
    import re

    # Parse dokumentverdi
    doc_clean = doc_value.replace(",", ".").replace(" ", "")
    doc_clean = re.sub(r"[^\d.]", "", doc_clean)

    try:
        doc_num = float(doc_clean)
    except:
        return False

    # Finn antall desimaler i dokumentet
    if "." in doc_clean:
        decimals = len(doc_clean.split(".")[1])
    else:
        decimals = 0

    # Avrund beregnet verdi til samme nøyaktighet
    rounded = round(calculated_value, decimals)

    return rounded == doc_num
```

### 2.3 Auto-godkjenn eller spør bruker

**Hvis verdiene matcher (etter avrunding):**
- Logg automatisk som OK i Excel
- Vis kort bekreftelse: `"✓ Side X: 20,7 mrd = 20,70 mrd"`
- Fortsett til neste tall uten å spørre

**Hvis verdiene IKKE matcher:**
- Vis avviket til bruker
- Spør med AskUserQuestion:
  - **OK** - Godkjenn likevel (f.eks. kjent avrundingsforskjell)
  - **Avvik** - Marker som avvik i rapporten
  - **Juster filter** - Endre query-parametere
  - **Hopp over** - Ikke verifiser dette tallet

### 2.4 Oppdater Excel etter hvert tall

```python
import polars as pl

def append_to_excel(rapport_path: str, row: dict):
    """Legg til ny rad i Excel-rapporten."""
    # Les eksisterende
    try:
        existing = pl.read_excel(rapport_path)
    except:
        existing = pl.DataFrame()

    # Legg til ny rad
    new_row = pl.DataFrame([row])
    updated = pl.concat([existing, new_row])

    # Lagre
    updated.write_excel(rapport_path)

# Eksempel bruk:
append_to_excel("kontroll/rapport.xlsx", {
    "Nr": 1,
    "Side": 2,
    "Tall": "20,7 mrd",
    "Kontekst": "Samlet omsetning",
    "Status": "OK",
    "Beregnet": "20,70 mrd",
    "Kilde": "ekom: sk=Sluttbruker",
})
```

## Steg 3: Vis løpende status

Etter hver batch (f.eks. 10 tall), vis oppsummering:

```
Kontrollert: 25/535
- OK: 22
- Avvik: 2
- Hoppet over: 1
```

## Steg 4: Avslutning

Når ferdig, vis:
```
Kontroll fullført!
- Totalt: 535
- OK: 480
- Avvik: 12
- Hoppet over: 43

Rapport: kontroll/rapport.xlsx
```

## Eksempel på flyten

```
Starter kontroll av: Ekomstatistikken_halvår_2025.pdf
Fant 535 tall

✓ Side 2: 20,7 mrd = 20,70 mrd (samlet omsetning)
✓ Side 2: 58% = 58,2% (mobil andel)
✓ Side 2: 38% = 38,0% (FBB andel)

⚠ Side 2: 925 mill ≠ 941 mill (økning omsetning)
  → Avvik: 16 mill
  [Spør bruker: OK / Avvik / Juster / Hopp]

✓ Side 2: 6,1 mill = 6,11 mill (mobilab.)
...

Kontrollert: 50/535 | OK: 45 | Avvik: 3 | Hopp: 2
```

## Tips

- Tall som matcher automatisk krever ingen brukerinteraksjon
- Kun avvik stopper flyten for manuell vurdering
- Excel-rapporten oppdateres kontinuerlig - kan åpnes underveis
- Ved "Juster filter" kan du prøve andre query-parametere

## Feilhåndtering

Hvis dokumentet ikke kan leses:
- For Word: `uv add python-docx`
- For PDF: `uv add pdfplumber`

Hvis ingen dokument finnes i data/:
- Legg dokumentet (Word eller PDF) i `data/`-mappen
- Det skal kun være ett dokument der
