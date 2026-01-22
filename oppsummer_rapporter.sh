#!/bin/bash
# Script for å oppsummere alle PDF-rapporter i historie.md
# Kjør med: ./oppsummer_rapporter.sh
# Krever: claude CLI med --dangerously-skip-permissions

set -e

HISTORIE_FIL="historie.md"
LOG_FIL="oppsummering_log.txt"

# Liste over hovedrapporter (ikke vedlegg) i kronologisk rekkefølge
RAPPORTER=(
    "lib/eldre/Eldre/2001_11_bredbånd.pdf|2001"
    "lib/eldre/Eldre/2002_09_bredbånd.pdf|2002"
    "lib/eldre/Eldre/2004_08_Bredbånd dekning og tilknytning.pdf|2004"
    "lib/eldre/Eldre/2005_08_bredbånd_ver1.04.pdf|2005"
    "lib/eldre/Eldre/Bredband_2007_Teleplan.pdf|2007"
    "lib/eldre/Eldre/Bredbandsdekning08_Teleplan.pdf|2008"
    "lib/eldre/2010/dekningsundersokelsen_2010_jan11.pdf|2010"
    "lib/eldre/2011/bredbandsdekning_2011.pdf|2011"
    "lib/eldre/2012/bredbandsdekning_2012.pdf|2012"
    "lib/eldre/2013/bredbandsdekning_2013.pdf|2013"
    "lib/eldre/2014/sluttrapport-dekning-2014-v2.0.pdf|2014"
    "lib/eldre/2015/Sluttrapport-Dekning-2015-endelig.pdf|2015"
    "lib/eldre/2016/Bredbåndsdekning i Norge 2016 v1.2.pdf|2016"
    "lib/eldre/2017/Bredbåndsdekning i Norge 2017.pdf|2017"
    "lib/eldre/2018/Dekningsrapport v1.0.pdf|2018"
    "lib/eldre/2019/26-09-Dekning-2019-final.pdf|2019"
    "lib/eldre/2020/Bredbåndsdekning i Norge 2020.pdf|2020"
)

echo "=== Starter oppsummering av bredbåndsrapporter ===" | tee -a "$LOG_FIL"
echo "Tidspunkt: $(date)" | tee -a "$LOG_FIL"
echo "" | tee -a "$LOG_FIL"

# Funksjon for å sjekke om et år allerede er oppsummert
er_oppsummert() {
    local aar=$1
    # Søker etter "## ÅÅÅÅ:" mønster i historie.md
    if grep -qE "^## ${aar}:" "$HISTORIE_FIL" 2>/dev/null; then
        return 0  # true - er oppsummert
    else
        return 1  # false - ikke oppsummert
    fi
}

# Tell totalt og ferdig
TOTALT=${#RAPPORTER[@]}
FERDIG=0
HOPPET_OVER=0

for rapport_info in "${RAPPORTER[@]}"; do
    # Split på |
    IFS='|' read -r PDF_STI AAR <<< "$rapport_info"

    echo "----------------------------------------" | tee -a "$LOG_FIL"
    echo "Sjekker rapport for år $AAR..." | tee -a "$LOG_FIL"

    if er_oppsummert "$AAR"; then
        echo "  -> Allerede oppsummert, hopper over." | tee -a "$LOG_FIL"
        ((HOPPET_OVER++)) || true
        ((FERDIG++)) || true
        continue
    fi

    # Sjekk at PDF-filen eksisterer
    if [[ ! -f "$PDF_STI" ]]; then
        echo "  -> ADVARSEL: Filen finnes ikke: $PDF_STI" | tee -a "$LOG_FIL"
        continue
    fi

    echo "  -> Starter oppsummering av: $PDF_STI" | tee -a "$LOG_FIL"
    echo "  -> Tidspunkt: $(date)" | tee -a "$LOG_FIL"

    # Lag prompt for Claude
    PROMPT="Les PDF-rapporten '$PDF_STI' bit for bit (bruk pdftotext og les i chunks på ~200 linjer om gangen).

Lag en oppsummering med:
- Relevante teknologier og deres dekning
- Viktige funn og tall
- Metodiske endringer fra tidligere år
- Andre viktige observasjoner

Oppdater historie.md ved å legge til en ny seksjon for år $AAR rett etter forrige års seksjon (eller etter 2002-seksjonen hvis det er 2004+).

Følg samme format som eksisterende seksjoner i historie.md. Bruk tabeller der det gir mening.

Når du er ferdig, si 'FERDIG MED $AAR' så scriptet vet at du er klar for neste rapport."

    # Kjør Claude
    if claude --dangerously-skip-permissions -p "$PROMPT" 2>&1 | tee -a "$LOG_FIL"; then
        echo "  -> Fullført oppsummering for $AAR" | tee -a "$LOG_FIL"
        ((FERDIG++)) || true
    else
        echo "  -> FEIL ved oppsummering av $AAR" | tee -a "$LOG_FIL"
    fi

    echo "" | tee -a "$LOG_FIL"

    # Kort pause mellom rapporter
    sleep 2
done

echo "========================================" | tee -a "$LOG_FIL"
echo "OPPSUMMERING FULLFØRT" | tee -a "$LOG_FIL"
echo "Totalt rapporter: $TOTALT" | tee -a "$LOG_FIL"
echo "Allerede oppsummert (hoppet over): $HOPPET_OVER" | tee -a "$LOG_FIL"
echo "Ferdig nå: $((FERDIG - HOPPET_OVER))" | tee -a "$LOG_FIL"
echo "Tidspunkt: $(date)" | tee -a "$LOG_FIL"
