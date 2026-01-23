# DESIGNMAL.md

Retningslinjer for datavisualisering i ekom-orakel.

---

## Grunnprinsipper

1. **Klarhet over estetikk.** Grafen skal formidle data, ikke imponere.
2. **Minimer "chart junk".** Fjern alt som ikke representerer data.
3. **Konsistente farger.** Samme kategori = samme farge, alltid.
4. **Tilgjengelighet.** Unngå rød/grønn-kombinasjoner. Bruk mønstre som backup.
5. **Maks 5-7 kategorier.** Flere enn dette krever splitting eller annen tilnærming.

---

## Fargepaletter

### Hovedpalett (kategorisk)

Fargeblind-sikker palett basert på ColorBrewer "Set2" og "Dark2":

| Kategori | Hex | Bruk |
|----------|-----|------|
| Primær | `#4472C4` | Hovedfarge, enkle stolpediagram |
| Sekundær | `#56B4E9` | Lyseblå, sekundære verdier |
| Suksess | `#009E73` | Grønn, positive verdier |
| Advarsel | `#E69F00` | Oransje, mellomverdier |
| Fremhevet | `#D55E00` | Rødoransje, viktige verdier |
| Nøytral | `#999999` | Grå, referanselinjer |
| NASJONALT | `#1B4F72` | Mørkeblå, alltid for nasjonale tall |

### Hastighetsklasser (fast bredbånd)

Konsistent fargekoding for hastighetsklasser:

| Hastighet | Hex | Navn |
|-----------|-----|------|
| 30 Mbit | `#1B4F72` | Mørkeblå |
| 100 Mbit | `#4472C4` | Blå |
| 500 Mbit | `#2E8B57` | Grønn |
| 1000 Mbit | `#E69F00` | Gul/oransje |

```python
HASTIGHETSFARGER = {
    '30 Mbit': '#1B4F72',
    '100 Mbit': '#4472C4',
    '500 Mbit': '#2E8B57',
    '1000 Mbit': '#E69F00',
}
```

### Teknologier (bredbånd)

| Teknologi | Hex | Beskrivelse |
|-----------|-----|-------------|
| Fiber | `#4472C4` | Blå (hovedteknologi) |
| FTB | `#56B4E9` | Lyseblå (trådløs) |
| Kabel | `#009E73` | Grønn |
| DSL | `#E69F00` | Oransje |
| Annet | `#999999` | Grå |

```python
TEKNOLOGIFARGER = {
    'fiber': '#4472C4',
    'ftb': '#56B4E9',
    'kabel': '#009E73',
    'dsl': '#E69F00',
    'radio': '#CC79A7',
    'satellitt': '#999999',
    'annet': '#999999',
}
```

### Mobiloperatører

| Tilbyder | Hex | Merknad |
|----------|-----|---------|
| Telenor | `#4472C4` | Blå |
| Telia | `#9B59B6` | Lilla |
| Ice | `#E69F00` | Oransje |

```python
MOBILFARGER = {
    'telenor': '#4472C4',
    'telia': '#9B59B6',
    'ice': '#E69F00',
}
```

### Markedssegment

| Segment | Hex |
|---------|-----|
| Privat | `#4472C4` |
| Bedrift | `#2E8B57` |
| Samlet | `#1B4F72` |

```python
SEGMENTFARGER = {
    'Privat': '#4472C4',
    'Bedrift': '#2E8B57',
    'Samlet': '#1B4F72',
}
```

### Sekvensielle paletter (for heatmaps etc.)

For verdier fra lav til høy, bruk `viridis` eller `cividis` (fargeblind-sikre):

```python
# Matplotlib
import matplotlib.pyplot as plt
plt.cm.viridis  # Lav → høy
plt.cm.cividis  # Alternativ, også fargeblind-sikker

# Seaborn
import seaborn as sns
sns.color_palette("viridis", as_cmap=True)
sns.color_palette("cividis", as_cmap=True)
```

### Seaborn innebygde paletter

Seaborn har flere fargeblind-sikre paletter:

```python
import seaborn as sns

# Fargeblind-sikker kategorisk palett (anbefalt)
sns.color_palette("colorblind")

# Andre nyttige paletter
sns.color_palette("deep")      # Mettede farger
sns.color_palette("muted")     # Dempede farger
sns.color_palette("dark")      # Mørke farger
sns.color_palette("pastel")    # Pastellfarger
```

---

## Typografi

| Element | Størrelse | Vekt |
|---------|-----------|------|
| Tittel | 14pt | Bold |
| Undertittel | 11pt | Normal |
| Aksetitler | 11pt | Normal |
| Akselabels | 10pt | Normal |
| Legend | 10pt | Normal |
| Dataetiketter | 9pt | Normal |

### Tittelformat

- **Deklarativ:** Beskriv hovedfunnet, ikke bare datatypen
- **Metrikk i parentes:** "(andel husstander)", "(antall abonnement)", "(mill. NOK)"

Eksempler:
- "Fiberdekning per fylke (andel husstander)"
- "5G-dekning øker mest i Nordland (endring 2024-2025)"

---

## Graftyper og bruksområder

| Datatype | Anbefalt graf | Unngå |
|----------|---------------|-------|
| Fylkesfordeling (én verdi) | Horisontalt stolpediagram | Kakediagram |
| Fylkesfordeling (flere verdier) | Gruppert stolpediagram | Stablet 100% |
| Tidsserie | Linjediagram | Stolpediagram |
| Andeler av helhet | Stablet stolpediagram, kakediagram (maks 5) | Mer enn 5 kakestykker |
| Sammenligning få kategorier | Vertikalt stolpediagram | Linjediagram |
| Korrelasjon | Spredningsdiagram | Stolpediagram |

---

## Layout og elementer

### Påkrevde elementer

1. **Tittel** - Deklarativ, venstrejustert
2. **Aksetitler** - Med enheter (%, antall, mill. NOK)
3. **Datakilde** - Nederst til venstre eller i undertittel

### Legend

- **Plassering:** Utenfor grafen (under eller til høyre)
- **Bruk `bbox_to_anchor`** for konsistent plassering
- **Direkte labeling** foretrukket over legend når mulig

```python
ax.legend(
    loc='upper center',
    bbox_to_anchor=(0.5, -0.15),
    ncol=4,
    frameon=False
)
```

### NASJONALT-markering

NASJONALT skal alltid skille seg ut:
- Egen farge (`#1B4F72` mørkeblå)
- Fet skrift på label
- Plasseres øverst eller nederst (ikke midt i)

```python
for i, label in enumerate(labels):
    if label == 'NASJONALT':
        bars[i].set_color('#1B4F72')
        ax.get_yticklabels()[i].set_fontweight('bold')
```

---

## Tilgjengelighet

### Fargeblindhet

- Unngå rød + grønn sammen
- Test med simuleringsverktøy
- Bruk mønstre/skraveringer som backup

```python
# Legg til skravering for fargeblind-sikkerhet
hatches = ['', '///', '...', 'xxx', '\\\\\\']
for bar, hatch in zip(bars, hatches):
    bar.set_hatch(hatch)
```

### Kontrast

- Tekst: minimum 4.5:1 kontrast mot bakgrunn
- Grafiske elementer: minimum 3:1

### Alt-tekst

Beskriv alltid grafen i tre deler:
1. Graftype og hva den viser
2. Hoveddataene/trenden
3. Hovedfunnet

Eksempel: "Horisontalt stolpediagram som viser fiberdekning per fylke. Oslo har høyest dekning med 98%, mens Nordland har lavest med 78%. Nasjonalt snitt er 89%."

---

## Seaborn-oppsett (anbefalt)

Seaborn gir penere grafer med mindre kode. Bruk seaborn som standard.

### Standardoppsett

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import pandas as pd

# Sett tema én gang (whitegrid er rent og profesjonelt)
sns.set_theme(style="whitegrid", palette="colorblind")

# Figur
fig, ax = plt.subplots(figsize=(10, 8))

# Fjern unødvendige spines (seaborn beholder noen)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Lagre med god oppløsning
plt.tight_layout()
plt.savefig('filnavn.png', dpi=150, facecolor='white', bbox_inches='tight')
plt.close()
```

### Horisontalt stolpediagram (fylkesfordeling)

```python
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt

def lag_fylkesdiagram_sns(df, verdikolonne, tittel, enhet='%'):
    """Lag fylkesdiagram med seaborn."""
    sns.set_theme(style="whitegrid")

    # Sorter: NASJONALT nederst, deretter etter verdi
    df = df.copy()
    df['_sort'] = df['fylke'].apply(lambda x: 1 if x == 'NASJONALT' else 0)
    df = df.sort_values(['_sort', verdikolonne], ascending=[True, True])

    # Farger: NASJONALT får egen farge
    farger = ['#1B4F72' if f == 'NASJONALT' else '#4472C4' for f in df['fylke']]

    fig, ax = plt.subplots(figsize=(10, 8))

    # Seaborn barplot
    sns.barplot(data=df, y='fylke', x=verdikolonne, palette=farger, ax=ax)

    # Styling
    ax.set_xlabel(enhet)
    ax.set_ylabel('')
    ax.set_title(tittel, fontweight='bold', loc='left', fontsize=14)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Uthev NASJONALT-label
    for label in ax.get_yticklabels():
        if label.get_text() == 'NASJONALT':
            label.set_fontweight('bold')

    plt.tight_layout()
    return fig, ax
```

### Linjediagram (tidsserie)

```python
def lag_tidsserie_sns(df, x_kolonne, y_kolonne, tittel, gruppe_kolonne=None):
    """Lag linjediagram med seaborn."""
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(10, 6))

    if gruppe_kolonne:
        # Flere linjer
        sns.lineplot(data=df, x=x_kolonne, y=y_kolonne,
                     hue=gruppe_kolonne, marker='o', ax=ax)
        ax.legend(title='', frameon=False)
    else:
        # Én linje
        sns.lineplot(data=df, x=x_kolonne, y=y_kolonne,
                     marker='o', linewidth=2.5, ax=ax)

        # Legg til verdier på punktene
        for x, y in zip(df[x_kolonne], df[y_kolonne]):
            ax.annotate(f'{y:.0f}', (x, y), textcoords="offset points",
                        xytext=(0, 10), ha='center', fontsize=10)

    ax.set_title(tittel, fontweight='bold', loc='left', fontsize=14)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    return fig, ax
```

### Heatmap

```python
def lag_heatmap_sns(df, tittel, fmt='.1f'):
    """Lag heatmap med seaborn."""
    sns.set_theme(style="white")

    fig, ax = plt.subplots(figsize=(12, 8))

    sns.heatmap(df, annot=True, fmt=fmt, cmap='viridis',
                linewidths=0.5, ax=ax, cbar_kws={'label': 'Verdi'})

    ax.set_title(tittel, fontweight='bold', loc='left', fontsize=14)

    plt.tight_layout()
    return fig, ax
```

### Stablet stolpediagram

```python
def lag_stablet_stolpe_sns(df, kategorier, verdier_dict, tittel):
    """Lag stablet horisontalt stolpediagram."""
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(12, 9))

    # Bruk pandas plotting for stablet
    df_plot = pd.DataFrame(verdier_dict, index=kategorier)
    df_plot.plot(kind='barh', stacked=True, ax=ax,
                 color=['#1B4F72', '#4472C4', '#2E8B57'])

    ax.set_xlabel('Andel (%)')
    ax.set_title(tittel, fontweight='bold', loc='left', fontsize=14)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.08),
              ncol=3, frameon=False)

    plt.tight_layout()
    return fig, ax
```

---

## Matplotlib-oppsett (alternativ)

Bruk ren matplotlib når seaborn ikke passer eller for mer kontroll.

### Standardoppsett

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# Figur
fig, ax = plt.subplots(figsize=(10, 8))

# Fjern unødvendige elementer
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Grid (kun horisontalt for stolpediagram)
ax.xaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True)

# Bakgrunn
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

# Tight layout
plt.tight_layout()

# Lagre med god oppløsning
plt.savefig('filnavn.png', dpi=150, facecolor='white', bbox_inches='tight')
```

### Horisontalt stolpediagram (fylkesfordeling)

```python
def lag_fylkesdiagram(df, verdikolonne, tittel, enhet='%'):
    fig, ax = plt.subplots(figsize=(10, 8))

    # Sorter: NASJONALT nederst, deretter etter verdi
    df_sortert = df.sort_values(verdikolonne, ascending=True)
    nasjonalt = df_sortert[df_sortert['fylke'] == 'NASJONALT']
    andre = df_sortert[df_sortert['fylke'] != 'NASJONALT']
    df_sortert = pd.concat([andre, nasjonalt])

    # Farger
    farger = ['#1B4F72' if f == 'NASJONALT' else '#4472C4'
              for f in df_sortert['fylke']]

    # Plot
    bars = ax.barh(df_sortert['fylke'], df_sortert[verdikolonne], color=farger)

    # Styling
    ax.set_xlabel(f'{enhet}')
    ax.set_title(tittel, fontweight='bold', loc='left')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.xaxis.grid(True, linestyle='--', alpha=0.7)

    # Uthev NASJONALT
    for label in ax.get_yticklabels():
        if label.get_text() == 'NASJONALT':
            label.set_fontweight('bold')

    plt.tight_layout()
    return fig, ax
```

---

## Sjekkliste før levering

- [ ] Tittel er deklarativ og inkluderer metrikk
- [ ] Akser har titler med enheter
- [ ] NASJONALT er uthevet og plassert konsistent
- [ ] Farger følger designmalen
- [ ] Legend er utenfor grafen
- [ ] Ingen rød/grønn-kombinasjon
- [ ] Maks 5-7 kategorier
- [ ] Grid er subtilt (---, alpha=0.7)
- [ ] Bakgrunn er hvit
- [ ] DPI er minst 150

---

## Endringslogg

| Dato | Endring | Grunn |
|------|---------|-------|
| 2026-01-19 | Opprettet | Etablere konsistente retningslinjer |
| 2026-01-19 | Lagt til seaborn | Penere grafer med mindre kode |

---

## Kilder

- [ColorBrewer](https://colorbrewer2.org/) - Fargepaletter
- [CFPB Design System](https://cfpb.github.io/design-system/guidelines/data-visualization-guidelines) - Retningslinjer
- [Urban Institute Style Guide](http://urbaninstitute.github.io/graphics-styleguide/) - Typografi og layout
- [Seaborn Color Palettes](https://seaborn.pydata.org/tutorial/color_palettes.html) - Matplotlib-integrasjon
