from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
import seaborn as sns

from library import (
    DocumentChecker,
    EkomQuery,
    HistoricalQuery,
    HistoricalSpeedQuery,
    KnowledgeBase,
    QueryMatcher,
    execute_coverage,
    execute_ekom,
    execute_mobilabonnement_fylke,
    execute_sql_cached,
    get_script_paths,
    get_session,
)

STATE_DIR = Path('.orakel_cli')
LAST_RESULT_PATH = STATE_DIR / 'last_result.parquet'
LAST_META_PATH = STATE_DIR / 'last_meta.json'

CATEGORY_MAP = {
    'fiber': ('Fast bredbånd', 'Fiber'),
    'fbb': ('Fast bredbånd', None),
    'mobil': ('Mobiltjenester', None),
    'ftb': ('Fast bredbånd', 'FTB'),
    'kabel': ('Fast bredbånd', 'Kabel'),
    'dsl': ('Fast bredbånd', 'DSL'),
}

METRIC_MAP = {
    'abonnement': 'Abonnement',
    'abo': 'Abonnement',
    'ab': 'Abonnement',
    'inntekter': 'Inntekter',
    'innt': 'Inntekter',
    'trafikk': 'Trafikk',
    'traf': 'Trafikk',
}

COVERAGE_TECH_MAP = {
    'fiber': ['fiber'],
    'ftb': ['ftb'],
    'kabel': ['kabel'],
    '5g': ['5g'],
    'g5': ['5g'],
    '4g': ['4g'],
    'g4': ['4g'],
}

PRIMARY_COLOR = '#4472C4'
SECONDARY_COLOR = '#56B4E9'
SUCCESS_COLOR = '#009E73'
WARNING_COLOR = '#E69F00'
HIGHLIGHT_COLOR = '#D55E00'
NATIONAL_COLOR = '#1B4F72'


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(exist_ok=True)


def save_last_result(df: pl.DataFrame, meta: dict[str, Any]) -> None:
    ensure_state_dir()
    df.write_parquet(LAST_RESULT_PATH)
    LAST_META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))


def load_last_result() -> tuple[pl.DataFrame, dict[str, Any]]:
    if not LAST_RESULT_PATH.exists():
        raise FileNotFoundError('Ingen forrige resultater funnet. Kjør en kommando først.')
    meta = {}
    if LAST_META_PATH.exists():
        meta = json.loads(LAST_META_PATH.read_text())
    return pl.read_parquet(LAST_RESULT_PATH), meta


def print_df(df: pl.DataFrame) -> None:
    print(render_table(df))


def maybe_format_numeric(df: pl.DataFrame) -> pl.DataFrame:
    exprs = []
    for col, dtype in zip(df.columns, df.dtypes):
        if dtype.is_integer():
            exprs.append(pl.col(col).map_elements(lambda v: f'{v:,}'.replace(',', ' ') if v is not None else None, return_dtype=pl.String).alias(col))
        elif dtype.is_float():
            exprs.append(pl.col(col).map_elements(lambda v: f'{v:,.1f}'.replace(',', ' ').replace('.0', '') if v is not None else None, return_dtype=pl.String).alias(col))
    return df.with_columns(exprs) if exprs else df


def _fit_column_widths(widths: list[int], terminal_width: int) -> list[int]:
    if not widths:
        return widths

    min_width = 6
    border_width = 3 * len(widths) + 1
    available = max(terminal_width - border_width, len(widths) * min_width)
    adjusted = widths[:]

    while sum(adjusted) > available and any(width > min_width for width in adjusted):
        widest_idx = max(range(len(adjusted)), key=lambda i: adjusted[i])
        adjusted[widest_idx] -= 1

    return adjusted


def _style_line(text: str, style: str | None, enabled: bool) -> str:
    if not enabled or not style:
        return text
    return f'{style}{text}\033[0m'


def _color_enabled(colorize: bool | None) -> bool:
    if colorize is not None:
        return colorize
    if os.environ.get('FORCE_COLOR'):
        return True
    return sys.stdout.isatty() and 'NO_COLOR' not in os.environ


def _wrap_cell(text: str, width: int) -> list[str]:
    if width <= 0:
        return ['']
    if not text:
        return ['']
    return textwrap.wrap(
        text,
        width=width,
        break_long_words=True,
        break_on_hyphens=False,
        drop_whitespace=False,
    ) or ['']


def _is_total_row(row: list[str]) -> bool:
    markers = {'NASJONALT', 'TOTALT', 'SUM', 'SUMMER'}
    return any(value.strip().upper() in markers for value in row)


def render_table(df: pl.DataFrame, *, colorize: bool | None = None) -> str:
    if df.is_empty():
        return '(ingen rader)'

    display_df = maybe_format_numeric(df)
    rows = [['' if value is None else str(value) for value in row] for row in display_df.rows()]
    headers = [str(col) for col in display_df.columns]
    numeric_cols = {col for col, dtype in zip(df.columns, df.dtypes) if dtype.is_numeric()}
    use_color = _color_enabled(colorize)

    widths = []
    for idx, header in enumerate(headers):
        cell_width = max((len(row[idx]) for row in rows), default=0)
        widths.append(max(len(header), cell_width))

    terminal_width = shutil.get_terminal_size((120, 20)).columns
    widths = _fit_column_widths(widths, terminal_width)

    def render_row(values: list[str], is_header: bool = False) -> list[str]:
        wrapped_cells = [_wrap_cell(value, widths[idx]) for idx, value in enumerate(values)]
        row_height = max(len(cell) for cell in wrapped_cells)
        rendered_lines = []

        for line_idx in range(row_height):
            cells = []
            for idx, lines_for_cell in enumerate(wrapped_cells):
                value = lines_for_cell[line_idx] if line_idx < len(lines_for_cell) else ''
                align = str.ljust
                if not is_header and headers[idx] in numeric_cols:
                    align = str.rjust
                cells.append(align(value, widths[idx]))
            rendered_lines.append('| ' + ' | '.join(cells) + ' |')
        return rendered_lines

    separator = '+-' + '-+-'.join('-' * width for width in widths) + '-+'
    header_style = '\033[1;37;44m'
    total_style = '\033[1;36m'

    lines = [separator]
    lines.extend(_style_line(line, header_style, use_color) for line in render_row(headers, is_header=True))
    lines.append(separator)
    for row in rows:
        style = total_style if _is_total_row(row) else None
        lines.extend(_style_line(line, style, use_color) for line in render_row(row))
    lines.append(separator)
    return '\n'.join(lines)


LEGACY_PATH_RE = re.compile(
    r"""(?P<quote>['"])(?P<path>lib(?:/(?P<year>\d{4}))?/(?P<dataset>adr|fbb|mob|ab|dekning_tek|dekning_hast|ekom)\.parquet)(?P=quote)"""
)


def normalize_legacy_sql_paths(sql: str) -> tuple[str, list[str]]:
    replacements: list[str] = []

    def replace(match: re.Match[str]) -> str:
        year = match.group('year')
        dataset = match.group('dataset')

        if year:
            view_name = f'{dataset}_{year}'
        else:
            global_path = Path('lib') / f'{dataset}.parquet'
            if global_path.exists():
                view_name = dataset
            else:
                latest_year = next(
                    (candidate for candidate in ['2024', '2023', '2022', '2021'] if (Path('lib') / candidate / f'{dataset}.parquet').exists()),
                    None,
                )
                view_name = f'{dataset}_{latest_year}' if latest_year else dataset

        replacements.append(f"{match.group('path')} -> {view_name}")
        return view_name

    normalized = LEGACY_PATH_RE.sub(replace, sql)
    unique_replacements = list(dict.fromkeys(replacements))
    return normalized, unique_replacements


def infer_numeric_columns(df: pl.DataFrame) -> list[str]:
    return [col for col, dtype in zip(df.columns, df.dtypes) if dtype.is_numeric()]


def infer_time_column(df: pl.DataFrame) -> str | None:
    for col in ['år', 'ar', 'rapport']:
        if col in df.columns:
            return col
    return None


def infer_category_column(df: pl.DataFrame, exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    for col, dtype in zip(df.columns, df.dtypes):
        if col in exclude:
            continue
        if dtype == pl.String:
            return col
    return None


def as_pandas(df: pl.DataFrame) -> pd.DataFrame:
    # Avoid a hard dependency on pyarrow for simple plotting/export paths.
    return pd.DataFrame(df.to_dicts())


def parse_period(token: str) -> str | list[str]:
    token = token.strip().lower()
    if '-' in token and token.count('-') == 1 and token.replace('-', '').isdigit():
        start, end = [int(x) for x in token.split('-')]
        return [f'{year}-Helår' for year in range(start, end + 1)]
    if token.endswith('h1') and token[:-2].isdigit():
        return f'{token[:-2]}-Halvår'
    if token.endswith('h2') and token[:-2].isdigit():
        return f'{token[:-2]}-Helår'
    if token.isdigit():
        return f'{token}-Helår'
    raise ValueError(f'Ukjent periodeformat: {token}')


def _normalize_geo(pop: str) -> str:
    return 'totalt' if pop == 'alle' else pop


def _load_speed_frame(speed: int, year: int, group_by: str, pop: str) -> pl.DataFrame:
    if year >= 2022:
        from library.query_builder import CoverageQuery

        return CoverageQuery(
            year=year,
            teknologi=[],
            hastighet_min=speed,
            populasjon=pop,
            group_by=group_by,
        ).execute()

    if group_by != 'nasjonal':
        raise SystemExit('Historiske hastighetssammenligninger før 2022 støttes foreløpig bare nasjonalt.')

    geo = _normalize_geo(pop)
    sql = f"""
SELECT
    ar as år,
    ROUND(MAX(dekning) * 100, 1) as prosent
FROM 'lib/dekning_hast.parquet'
WHERE ar = {year}
  AND fylke = 'NASJONALT'
  AND geo = '{geo}'
  AND ned >= {speed}
GROUP BY ar
ORDER BY ar
"""
    return execute_sql_cached(sql)


def _coverage_comparison_frame(df1: pl.DataFrame, df2: pl.DataFrame, year1: int, year2: int) -> pl.DataFrame:
    reserved = {
        'med_dekning', 'totalt', 'prosent',
        'hus_fiber', 'hus_5g', 'hus_4g', 'hus_ftb',
        'antall_husstander', 'fiber_pct', 'g5_pct', 'g4_pct', 'ftb_pct',
    }
    label_col = next((c for c in df1.columns if c not in reserved), df1.columns[0])
    value_col1 = next((c for c in df1.columns if c.endswith('_pct')), 'prosent')
    value_col2 = next((c for c in df2.columns if c.endswith('_pct')), 'prosent')
    left = df1.select(pl.col(label_col).alias('område'), pl.col(value_col1).alias(str(year1)))
    right = df2.select(pl.col(label_col).alias('område'), pl.col(value_col2).alias(str(year2)))
    merged = left.join(right, on='område', how='inner').with_columns(
        (pl.col(str(year2)) - pl.col(str(year1))).round(1).alias('endring_pp')
    )
    return merged.sort(
        pl.when(pl.col('område') == 'NASJONALT').then(1).otherwise(0),
        pl.col('område'),
    )


def _build_graph_title(df: pl.DataFrame, meta: dict[str, Any]) -> str:
    command = meta.get('command', 'graf')
    args = [str(arg).lower() for arg in meta.get('args', [])]
    if command == 'sammenlign' and len(args) >= 3:
        start, end = args[1], args[2]
        if meta.get('speed_mbit') == 100:
            return f'Endring i 100 Mbit-dekning {start}-{end} (prosentpoeng)'
        if meta.get('speed_mbit') == 1000:
            return f'Endring i gigabitdekning {start}-{end} (prosentpoeng)'
        if args[0] in {'fiber', 'kabel', 'ftb', '4g', '5g'}:
            return f'Endring i {args[0].upper()}-dekning {start}-{end} (prosentpoeng)'
    if command == 'sammenlign' and 'endring_pp' in df.columns:
        return 'Endring mellom to tidspunkt'
    if command == 'markedsandel':
        return 'Markedsandeler per tilbyder'
    if command == 'ekom':
        return 'Ekomstatistikk'
    if infer_time_column(df):
        return 'Utvikling over tid'
    return 'Resultat'


def _build_graph_subtitle(df: pl.DataFrame, meta: dict[str, Any]) -> str:
    command = meta.get('command', 'graf')
    if 'endring_pp' in df.columns:
        return 'Kilde: Nkom-data via ekom-orakel. NASJONALT er fremhevet.'
    if command == 'markedsandel':
        return 'Kilde: ekom.parquet. Andeler beregnet fra siste uttrekk.'
    if infer_time_column(df):
        return 'Kilde: Nkom-data via ekom-orakel.'
    return 'Kilde: siste resultat i ekom-orakel.'


def _metric_label(df: pl.DataFrame) -> str:
    if 'endring_pp' in df.columns:
        return 'Prosentpoeng'
    pct_cols = [col for col in df.columns if col.endswith('_pct') or col == 'prosent' or col == 'andel_pct']
    if pct_cols:
        return 'Prosent'
    return 'Verdi'


def _style_axes(ax: plt.Axes) -> None:
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', alpha=0.3)


def _plot_comparison_change(df: pl.DataFrame, ax: plt.Axes) -> None:
    plot_df = df.sort('endring_pp')
    colors = [
        NATIONAL_COLOR if area == 'NASJONALT' else SUCCESS_COLOR if value >= 0 else HIGHLIGHT_COLOR
        for area, value in zip(plot_df['område'], plot_df['endring_pp'])
    ]
    ax.barh(plot_df['område'].to_list(), plot_df['endring_pp'].to_list(), color=colors)
    ax.set_xlabel('Endring (prosentpoeng)')
    ax.set_ylabel('')
    for label in ax.get_yticklabels():
        if label.get_text() == 'NASJONALT':
            label.set_fontweight('bold')


def _plot_time_series(df: pl.DataFrame, ax: plt.Axes) -> None:
    time_col = infer_time_column(df)
    if time_col is None:
        raise SystemExit('Fant ingen tidskolonne i forrige resultat.')

    numeric_cols = [col for col in infer_numeric_columns(df) if col != time_col]
    category_col = infer_category_column(df, exclude={time_col, *numeric_cols})

    if category_col and len(numeric_cols) == 1:
        pdf = as_pandas(df)
        sns.lineplot(data=pdf, x=time_col, y=numeric_cols[0], hue=category_col, marker='o', ax=ax)
        ax.legend(title='', frameon=False, bbox_to_anchor=(0.5, -0.15), loc='upper center', ncol=3)
    elif len(numeric_cols) >= 1:
        y_col = numeric_cols[0]
        sns.lineplot(data=as_pandas(df), x=time_col, y=y_col, marker='o', color=PRIMARY_COLOR, ax=ax)
    else:
        raise SystemExit('Fant ingen numeriske verdier å tegne.')
    ax.set_xlabel('')
    ax.set_ylabel('')


def _plot_category_bars(df: pl.DataFrame, ax: plt.Axes) -> None:
    numeric_cols = infer_numeric_columns(df)
    category_col = infer_category_column(df, exclude=set(numeric_cols))
    if category_col is None or not numeric_cols:
        raise SystemExit('Fant ikke et kategorisk datasett å visualisere.')

    if len(numeric_cols) == 1:
        value_col = numeric_cols[0]
        plot_df = df.sort(value_col, descending=True)
        palette = [NATIONAL_COLOR if item == 'NASJONALT' else PRIMARY_COLOR for item in plot_df[category_col]]
        sns.barplot(data=as_pandas(plot_df), y=category_col, x=value_col, palette=palette, ax=ax)
        ax.set_xlabel('')
        ax.set_ylabel('')
        for label in ax.get_yticklabels():
            if label.get_text() == 'NASJONALT':
                label.set_fontweight('bold')
        return

    limited = numeric_cols[:3]
    pdf = as_pandas(df.select(category_col, *limited)).melt(id_vars=[category_col], var_name='serie', value_name='verdi')
    sns.barplot(data=pdf, y=category_col, x='verdi', hue='serie', orient='h', palette=[PRIMARY_COLOR, SECONDARY_COLOR, SUCCESS_COLOR], ax=ax)
    ax.legend(title='', frameon=False, bbox_to_anchor=(0.5, -0.15), loc='upper center', ncol=len(limited))
    ax.set_xlabel('')
    ax.set_ylabel('')


@dataclass
class CommandContext:
    command: str
    args: list[str]


def parse_command(argv: list[str]) -> CommandContext:
    if not argv:
        raise SystemExit('Bruk: uv run orakel /kommando [argumenter]')
    command = argv[0]
    if command.startswith('/'):
        command = command[1:]
    return CommandContext(command=command, args=argv[1:])


def command_ekom(args: list[str]) -> int:
    if not args:
        raise SystemExit('Bruk: uv run orakel /ekom <kategori> <metrikk> <periode> [modifikatorer]')

    category_token = args[0].lower()
    if category_token not in CATEGORY_MAP:
        raise SystemExit(f'Ukjent kategori: {category_token}')
    hk, tek = CATEGORY_MAP[category_token]

    metric = None
    period = None
    ms = None
    group_by: list[str] = []
    pivot_years = True
    tilbyder = None
    fylke_mode = False
    fylke = None

    remaining = []
    for token in args[1:]:
        t = token.lower()
        if t in METRIC_MAP:
            metric = METRIC_MAP[t]
        elif t in {'privat', 'bedrift'}:
            ms = t.capitalize()
        elif t == 'tilbyder':
            group_by = ['fusnavn']
        elif t == 'pivot':
            pivot_years = True
        elif t == 'tabell':
            pivot_years = False
        elif t == 'fylke':
            fylke_mode = True
            group_by = ['fylke']
        elif t[:4].isdigit():
            period = parse_period(t)
        else:
            remaining.append(token)

    if remaining and fylke_mode:
        fylke = ' '.join(remaining)
        if fylke:
            fylke = fylke.title()
    elif remaining:
        tilbyder = ' '.join(remaining)

    if hk == 'Mobiltjenester' and metric == 'Abonnement' and fylke_mode:
        if not isinstance(period, str):
            raise SystemExit('Spørsmålet er tvetydig. Presiser én eksplisitt rapport/periode for mobilabonnement per fylke.')
        df = execute_mobilabonnement_fylke(
            rapport=period,
            ms=ms,
            tilbyder=tilbyder,
            fylke=fylke,
            group_by=group_by,
        )
    else:
        if metric is None:
            raise SystemExit('Spørsmålet er tvetydig. Presiser metrikk: abonnement, inntekter eller trafikk.')
        if period is None:
            raise SystemExit('Spørsmålet er tvetydig. Presiser rapport/periode, for eksempel 2024 eller 2025-H1.')
        query = EkomQuery(
            hk=hk,
            hg=metric,
            tek=tek,
            ms=ms,
            tilbyder=tilbyder,
            rapport=period,
            group_by=group_by,
            pivot_years=pivot_years,
        )
        df = query.execute()

    print_df(df)
    save_last_result(df, {'command': 'ekom', 'args': args})
    return 0


def command_listhist(args: list[str]) -> int:
    kb = KnowledgeBase()
    if not args:
        queries = kb.list_queries(limit=20)
        rows = [{'id': q.id, 'kategori': q.category, 'spørsmål': q.question, 'verifisert': q.verified_date} for q in queries]
        df = pl.DataFrame(rows)
        print_df(df)
        save_last_result(df, {'command': 'listhist'})
        return 0

    arg = ' '.join(args)
    if arg.isdigit():
        query = kb.get_query(int(arg))
        if not query:
            raise SystemExit(f'Fant ikke spørring {arg}')
        print(f'Q:{query.id} | {query.category} | {query.question}')
        sql, replacements = normalize_legacy_sql_paths(query.sql)
        if replacements:
            print(f"Normaliserte legacy-baner: {', '.join(replacements)}")
        print(sql)
        df = execute_sql_cached(sql)
        print_df(df)
        save_last_result(df, {'command': 'listhist', 'query_id': query.id})
        return 0

    if arg.startswith('filter='):
        filters = [f.strip() for f in arg.split('=', 1)[1].split(',') if f.strip()]
        exclude = [f[1:] for f in filters if f.startswith('!')]
        include = [f for f in filters if not f.startswith('!')]
        queries = kb.list_queries(categories=include or None, exclude_categories=exclude or None, limit=20)
        rows = [{'id': q.id, 'kategori': q.category, 'spørsmål': q.question, 'verifisert': q.verified_date} for q in queries]
        df = pl.DataFrame(rows)
        print_df(df)
        save_last_result(df, {'command': 'listhist', 'filter': arg})
        return 0

    matcher = QueryMatcher()
    results = matcher.find_similar(arg, limit=5)
    rows = [{'id': r.query.id, 'score': round(r.score, 2), 'kategori': r.query.category, 'spørsmål': r.query.question} for r in results]
    df = pl.DataFrame(rows)
    print_df(df)
    save_last_result(df, {'command': 'listhist', 'search': arg})
    return 0


def command_sammenlign(args: list[str]) -> int:
    if len(args) < 3:
        raise SystemExit('Bruk: uv run orakel /sammenlign <teknologi|100mbit|1gbit> <år1> <år2> [fylke|nasjonal|kommune] [alle|spredtbygd|tettsted]')

    metric_token = args[0].lower()
    year1 = int(args[1])
    year2 = int(args[2])
    group_by = 'fylke'
    pop = 'alle'
    for token in args[3:]:
        t = token.lower()
        if t in {'fylke', 'nasjonal', 'kommune'}:
            group_by = t
        elif t in {'alle', 'spredtbygd', 'tettsted'}:
            pop = t

    if metric_token in {'100mbit', '1gbit'}:
        speed = 100 if metric_token == '100mbit' else 1000
        df1 = _load_speed_frame(speed=speed, year=year1, group_by=group_by, pop=pop)
        df2 = _load_speed_frame(speed=speed, year=year2, group_by=group_by, pop=pop)
        if year1 < 2022 or year2 < 2022:
            left = df1.select(pl.lit('NASJONALT').alias('område'), pl.col('prosent').alias(str(year1)))
            right = df2.select(pl.lit('NASJONALT').alias('område'), pl.col('prosent').alias(str(year2)))
            df = left.join(right, on='område', how='inner').with_columns(
                (pl.col(str(year2)) - pl.col(str(year1))).round(1).alias('endring_pp')
            )
        else:
            df = _coverage_comparison_frame(df1, df2, year1, year2)
        print_df(df)
        save_last_result(df, {'command': 'sammenlign', 'args': args, 'speed_mbit': speed})
        return 0

    teknologi = COVERAGE_TECH_MAP.get(metric_token)
    if not teknologi:
        raise SystemExit(f'Ukjent teknologi: {metric_token}')

    if year1 >= 2022 and year2 >= 2022:
        df1 = execute_coverage(teknologi=teknologi, group_by=group_by, year=year1, populasjon=None if pop == 'alle' else pop)
        df2 = execute_coverage(teknologi=teknologi, group_by=group_by, year=year2, populasjon=None if pop == 'alle' else pop)
        merged = _coverage_comparison_frame(df1, df2, year1, year2)
        print_df(merged)
        save_last_result(merged, {'command': 'sammenlign', 'args': args})
        return 0

    if group_by != 'nasjonal':
        raise SystemExit('Historiske sammenligninger før 2022 støttes foreløpig bare nasjonalt i CLI.')
    geo = 'totalt' if pop == 'alle' else pop
    df = HistoricalQuery(start_year=year1, end_year=year2, teknologi=teknologi, geo=geo).execute()
    print_df(df)
    save_last_result(df, {'command': 'sammenlign', 'args': args})
    return 0


def command_markedsandel(args: list[str]) -> int:
    if len(args) < 2:
        raise SystemExit('Bruk: uv run orakel /markedsandel <kategori> <segment?> <år> [abonnement|inntekter|trafikk] [topp5|topp10]')

    category_token = args[0].lower()
    if category_token not in CATEGORY_MAP:
        raise SystemExit(f'Ukjent kategori: {category_token}')
    hk, tek = CATEGORY_MAP[category_token]
    ms = None
    metric = 'Abonnement'
    rapport = '2024-Helår'
    top_n = None

    for token in args[1:]:
        t = token.lower()
        if t in {'privat', 'bedrift'}:
            ms = t.capitalize()
        elif t in METRIC_MAP:
            metric = METRIC_MAP[t]
        elif t.startswith('topp') and t[4:].isdigit():
            top_n = int(t[4:])
        elif t[:4].isdigit():
            parsed = parse_period(t)
            if isinstance(parsed, list):
                raise SystemExit('Tidsserier for /markedsandel er ikke implementert i CLI ennå. Bruk ett år/periode.')
            rapport = parsed

    df = EkomQuery(
        hk=hk,
        hg=metric,
        tek=tek,
        ms=ms,
        rapport=rapport,
        group_by=['fusnavn'],
        pivot_years=False,
    ).execute()
    total = df['svar'].sum()
    df = df.with_columns((pl.col('svar') * 100 / total).round(2).alias('andel_pct')).sort('svar', descending=True)
    if top_n and df.height > top_n:
        top = df.head(top_n)
        rest = df.slice(top_n)
        other = pl.DataFrame({'fusnavn': ['Andre'], 'svar': [rest['svar'].sum()], 'andel_pct': [round(rest['andel_pct'].sum(), 2)], 'rapport': [rapport]})
        df = pl.concat([top, other], how='diagonal')
    print_df(df)
    save_last_result(df, {'command': 'markedsandel', 'args': args})
    return 0


def export_excel(path: Path) -> int:
    df, meta = load_last_result()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_excel(path)
    print(f'Eksportert til {path}')
    return 0


def export_png(path: Path) -> int:
    df, meta = load_last_result()
    display_df = maybe_format_numeric(df)
    rows = display_df.rows()
    cols = display_df.columns
    fig_h = max(2, len(rows) * 0.35 + 1)
    fig, ax = plt.subplots(figsize=(max(8, len(cols) * 2), fig_h))
    ax.axis('off')
    table = ax.table(cellText=rows, colLabels=cols, loc='center', cellLoc='left')
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.1, 1.3)
    for j in range(len(cols)):
        table[(0, j)].set_facecolor('#4472C4')
        table[(0, j)].set_text_props(color='white', weight='bold')
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'Eksportert til {path}')
    return 0


def default_export_path(ext: str) -> Path:
    today = date.today().isoformat()
    ensure_state_dir()
    return Path('uttrekk') / today / f'eksport{ext}'


def command_tilxl(args: list[str]) -> int:
    if args:
        dispatch(args)
    return export_excel(default_export_path('.xlsx'))


def command_tilbilde(args: list[str]) -> int:
    if args:
        dispatch(args)
    return export_png(default_export_path('.png'))


def command_graf(args: list[str]) -> int:
    df, meta = load_last_result()
    path = default_export_path('_graf.png')
    sns.set_theme(
        style='whitegrid',
        palette=[PRIMARY_COLOR, SECONDARY_COLOR, SUCCESS_COLOR, WARNING_COLOR],
        rc={
            'axes.titlesize': 14,
            'axes.labelsize': 11,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
        },
    )
    fig, ax = plt.subplots(figsize=(11, 7))

    comparison_plot = {'område', 'endring_pp'} <= set(df.columns)
    time_plot = False

    if comparison_plot:
        _plot_comparison_change(df, ax)
    elif infer_time_column(df):
        time_plot = True
        _plot_time_series(df, ax)
    else:
        _plot_category_bars(df, ax)

    ax.set_title(_build_graph_title(df, meta), loc='left', fontweight='bold')
    fig.text(0.125, 0.92, _build_graph_subtitle(df, meta), ha='left', va='top', fontsize=11)
    if time_plot:
        ax.set_ylabel(_metric_label(df))
    else:
        ax.set_xlabel(_metric_label(df))
    if comparison_plot:
        ax.axvline(0, color='#999999', linewidth=1, alpha=0.8)
    _style_axes(ax)
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'Eksportert graf til {path}')
    return 0


def command_kontroller(args: list[str]) -> int:
    checker = DocumentChecker()
    path = checker.find_document() if hasattr(checker, 'find_document') else None
    if path is None:
        from library.doc_checker import find_document
        path = find_document()
    findings = checker.parse_document(path)
    rows = []
    for finding in findings[:50]:
        rows.append({'posisjon': finding.position, 'tekst': finding.raw_text, 'sted': finding.location, 'kontekst': finding.context[:80]})
    df = pl.DataFrame(rows)
    print(f'Fant {len(findings)} tall i {path.name}')
    print_df(df)
    save_last_result(df, {'command': 'kontroller', 'document': path.name})
    return 0


def command_loggpush(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog='/loggpush', add_help=False)
    parser.add_argument('--message')
    parser.add_argument('--push', action='store_true')
    ns = parser.parse_args(args)
    session = get_session()
    count = session.flush_to_kb()
    print(f'Lagret {count} elementer til knowledge base')
    if ns.message:
        subprocess.run(['git', 'add', '-A'], check=True)
        subprocess.run(['git', 'commit', '-m', ns.message], check=True)
        if ns.push:
            subprocess.run(['git', 'push'], check=True)
    return 0


def command_oppdater(args: list[str]) -> int:
    kb = KnowledgeBase()
    if not args or args[0] == 'vis':
        defs = kb.list_definitions()
        rows = [{'navn': d.name, 'gjelder': d.applies_to, 'filtre': json.dumps(d.filters, ensure_ascii=False)} for d in defs]
        df = pl.DataFrame(rows) if rows else pl.DataFrame({'navn': [], 'gjelder': [], 'filtre': []})
        print_df(df)
        save_last_result(df, {'command': 'oppdater'})
        return 0

    mode = args[0]
    if mode == 'slett' and len(args) >= 2:
        ok = kb.delete_definition(args[1])
        print('Slettet' if ok else 'Fant ikke definisjonen')
        return 0

    if mode in {'ny', 'rediger'} and len(args) >= 2:
        name = args[1]
        parser = argparse.ArgumentParser(prog=f'/oppdater {mode}', add_help=False)
        parser.add_argument('--description', required=True)
        parser.add_argument('--applies-to', required=True)
        parser.add_argument('--filter', action='append', default=[])
        parser.add_argument('--notes')
        ns = parser.parse_args(args[2:])
        filters: dict[str, Any] = {}
        for item in ns.filter:
            if '=' not in item:
                raise SystemExit(f'Ugyldig filter: {item}. Bruk nøkkel=verdi')
            key, value = item.split('=', 1)
            filters[key] = value
        if mode == 'ny':
            kb.add_definition(name=name, description=ns.description, filters=filters, applies_to=ns.applies_to, notes=ns.notes)
            print(f'Opprettet definisjon {name}')
        else:
            kb.update_definition(name=name, description=ns.description, filters=filters, applies_to=ns.applies_to, notes=ns.notes)
            print(f'Oppdatert definisjon {name}')
        return 0

    raise SystemExit('Bruk: /oppdater vis | /oppdater slett <navn> | /oppdater ny <navn> --description ... --applies-to ekom --filter tp=Sum')


def command_ny(args: list[str]) -> int:
    if not args:
        raise SystemExit('Bruk: uv run orakel /ny <navn> [beskrivelse ...]')
    name = args[0].lower().replace('-', '_')
    description = ' '.join(args[1:]) or 'Nytt uttrekk'
    script_path, excel_path = get_script_paths(name)
    template = f'''#!/usr/bin/env python3\n"""{description}."""\n\nfrom library import execute_coverage\n\n\ndef main():\n    df = execute_coverage(teknologi="fiber", group_by="fylke", year=2024)\n    print(df)\n    df.write_excel(r"{excel_path}")\n\n\nif __name__ == "__main__":\n    main()\n'''
    script_path.write_text(template)
    print(f'Opprettet {script_path}')
    return 0


def dispatch(argv: list[str]) -> int:
    ctx = parse_command(argv)
    handlers = {
        'ekom': command_ekom,
        'listhist': command_listhist,
        'sammenlign': command_sammenlign,
        'markedsandel': command_markedsandel,
        'tilxl': command_tilxl,
        'tilbilde': command_tilbilde,
        'graf': command_graf,
        'kontroller': command_kontroller,
        'loggpush': command_loggpush,
        'oppdater': command_oppdater,
        'ny': command_ny,
    }
    if ctx.command not in handlers:
        raise SystemExit(f'Ukjent kommando: /{ctx.command}')
    return handlers[ctx.command](ctx.args)


def main() -> int:
    try:
        return dispatch(sys.argv[1:])
    except BrokenPipeError:
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
