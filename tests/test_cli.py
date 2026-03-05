import shutil
import subprocess
import sys
import unittest
import re
from datetime import date
from pathlib import Path

import polars as pl

from library.cli import LAST_RESULT_PATH, STATE_DIR, dispatch, normalize_legacy_sql_paths, render_table


ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


class OrakelCliTests(unittest.TestCase):
    def _cleanup_outputs(self):
        today_dir = Path('uttrekk') / date.today().isoformat()
        for path in [today_dir / 'eksport.xlsx', today_dir / 'eksport_graf.png', *today_dir.glob('*_test_cli.py')]:
            if path.exists():
                path.unlink()
        if today_dir.exists() and not any(today_dir.iterdir()):
            today_dir.rmdir()

    def setUp(self):
        if STATE_DIR.exists():
            shutil.rmtree(STATE_DIR)
        self._cleanup_outputs()

    def tearDown(self):
        if STATE_DIR.exists():
            shutil.rmtree(STATE_DIR)
        self._cleanup_outputs()

    def test_ekom_command_runs(self):
        rc = dispatch(['/ekom', 'fiber', 'abonnement', '2024'])
        self.assertEqual(rc, 0)
        self.assertTrue(LAST_RESULT_PATH.exists())

    def test_render_table_uses_fixed_width_rows(self):
        df = pl.DataFrame(
            {
                'id': [1, 22],
                'kategori': ['Historikk', 'Dekning'],
                'spørsmål': ['Kort spørsmål', 'Et mye lengre spørsmål som skal wrappe pent i terminalen uten å ødelegge tabellen'],
            }
        )
        table = render_table(df, colorize=False)
        lines = table.splitlines()
        self.assertGreaterEqual(len(lines), 5)
        self.assertEqual(len({len(line) for line in lines}), 1)
        self.assertIn('ødelegge tabellen', table)
        self.assertIn('uten å', table)

    def test_render_table_can_color_header_and_total_rows(self):
        df = pl.DataFrame(
            {
                'område': ['AGDER', 'NASJONALT'],
                'prosent': [97.4, 96.2],
            }
        )
        table = render_table(df, colorize=True)
        self.assertIn('\033[1;37;44m', table)
        self.assertIn('\033[1;36m', table)
        stripped_lines = [ANSI_RE.sub('', line) for line in table.splitlines()]
        self.assertEqual(len({len(line) for line in stripped_lines}), 1)

    def test_listhist_command_runs(self):
        rc = dispatch(['/listhist'])
        self.assertEqual(rc, 0)
        self.assertTrue(LAST_RESULT_PATH.exists())

    def test_normalize_legacy_sql_paths_maps_root_files_to_views(self):
        sql = "SELECT * FROM 'lib/fbb.parquet' f JOIN 'lib/adr.parquet' a ON f.adrid = a.adrid"
        normalized, replacements = normalize_legacy_sql_paths(sql)
        self.assertIn('fbb_2024', normalized)
        self.assertIn('adr_2024', normalized)
        self.assertIn('lib/fbb.parquet -> fbb_2024', replacements)

    def test_listhist_specific_query_runs_with_legacy_path_normalization(self):
        rc = dispatch(['/listhist', '5'])
        self.assertEqual(rc, 0)
        self.assertTrue(LAST_RESULT_PATH.exists())

    def test_tilxl_exports_previous_result(self):
        dispatch(['/ekom', 'fiber', 'abonnement', '2024'])
        rc = dispatch(['/tilxl'])
        self.assertEqual(rc, 0)
        export_path = Path('uttrekk') / date.today().isoformat() / 'eksport.xlsx'
        self.assertTrue(export_path.exists())

    def test_ekom_requires_explicit_metric_and_period(self):
        with self.assertRaises(SystemExit) as exc:
            dispatch(['/ekom', 'fiber'])
        self.assertIn('Presiser metrikk', str(exc.exception))

    def test_ekom_mobile_fylke_requires_explicit_single_period(self):
        with self.assertRaises(SystemExit) as exc:
            dispatch(['/ekom', 'mobil', 'abonnement', 'fylke'])
        self.assertIn('Presiser én eksplisitt rapport/periode', str(exc.exception))

    def test_sammenlign_supports_speed_thresholds(self):
        rc = dispatch(['/sammenlign', '100mbit', '2022', '2024', 'fylke'])
        self.assertEqual(rc, 0)
        self.assertTrue(LAST_RESULT_PATH.exists())

    def test_graf_exports_chart_from_speed_comparison(self):
        dispatch(['/sammenlign', '1gbit', '2022', '2024', 'fylke'])
        rc = dispatch(['/graf'])
        self.assertEqual(rc, 0)
        export_path = Path('uttrekk') / date.today().isoformat() / 'eksport_graf.png'
        self.assertTrue(export_path.exists())

    def test_cli_persists_last_result_across_processes(self):
        result = subprocess.run(
            [sys.executable, '-m', 'library.cli', '/sammenlign', '100mbit', '2022', '2024', 'fylke'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        graph = subprocess.run(
            [sys.executable, '-m', 'library.cli', '/graf'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(graph.returncode, 0, msg=graph.stderr)
        export_path = Path('uttrekk') / date.today().isoformat() / 'eksport_graf.png'
        self.assertTrue(export_path.exists())

    def test_ny_creates_script(self):
        rc = dispatch(['/ny', 'test_cli', 'CLI', 'template'])
        self.assertEqual(rc, 0)
        created = sorted((Path('uttrekk') / date.today().isoformat()).glob('*_test_cli.py'))
        self.assertTrue(created)


if __name__ == '__main__':
    unittest.main()
