import unittest

import polars as pl

from library import execute_coverage, execute_ekom, execute_mobilabonnement_fylke
from library.ekom_query import EkomQuery
from library.query_builder import CoverageQuery, HistoricalSpeedQuery


class OracleGuardrailTests(unittest.TestCase):
    def test_coverage_query_supports_kommune(self):
        df = CoverageQuery(teknologi=["fiber"], group_by="kommune").execute()

        self.assertIn("kommune", df.columns)
        self.assertGreater(df.height, 100)
        self.assertEqual(df[-1, "kommune"], "NASJONALT")

    def test_execute_coverage_5g_uses_mobile_data(self):
        df = execute_coverage(teknologi="5g", group_by="fylke", year=2024)

        non_national = df.filter(pl.col("fylke_navn") != "NASJONALT") if "fylke_navn" in df.columns else df
        pct_col = "g5_pct" if "g5_pct" in df.columns else "prosent"
        self.assertEqual(non_national.select(pl.col(pct_col).null_count()).item(), 0)

    def test_execute_coverage_5g_kommune_works(self):
        df = execute_coverage(teknologi="5g", group_by="kommune", year=2024)

        self.assertIn("kommune", df.columns)
        self.assertGreater(df.select(pl.col("prosent").is_not_null().sum()).item(), 100)

    def test_mobile_abonnement_fylke_returns_actual_counties(self):
        df = execute_mobilabonnement_fylke(rapport="2025-Halvår", ms="Privat")

        self.assertIn("fylke", df.columns)
        values = set(df["fylke"].to_list())
        self.assertIn("Agder", values)
        self.assertNotIn("Fakturert", values)
        self.assertNotIn("Kontantkort", values)

    def test_mobile_abonnement_fylke_requires_supported_period(self):
        with self.assertRaises(ValueError):
            execute_mobilabonnement_fylke(rapport="2024-Helår", ms="Privat")

    def test_mobile_filters_reject_hc(self):
        with self.assertRaises(ValueError):
            CoverageQuery(teknologi=["5g"], kun_hc=True)


class OracleGoldenQuestionTests(unittest.TestCase):
    def test_fiber_national_2024(self):
        df = execute_coverage(teknologi="fiber", group_by="nasjonal", year=2024)
        self.assertEqual(df["prosent"][0], 91.0)

    def test_fiber_spredtbygd_national_2024(self):
        df = execute_coverage(
            teknologi="fiber",
            group_by="nasjonal",
            year=2024,
            populasjon="spredtbygd",
        )
        self.assertEqual(df["prosent"][0], 82.3)

    def test_5g_national_2024(self):
        df = execute_coverage(teknologi="5g", group_by="nasjonal", year=2024)
        self.assertEqual(df["prosent"][0], 99.7)

    def test_historical_speed_100_100_2024(self):
        df = HistoricalSpeedQuery(
            start_year=2024,
            end_year=2024,
            ned=100,
            opp=100,
        ).execute()
        self.assertEqual(df["prosent"][0], 95.1)

    def test_mobile_fakturert_2024_helaar(self):
        df = EkomQuery(
            hk="Mobiltjenester",
            dk="Mobiltelefoni",
            hg="Abonnement",
            n1="Fakturert",
            rapport="2024-Helår",
            pivot_years=False,
        ).execute()
        self.assertEqual(df["svar"][0], 5696716.0)

    def test_fast_bredband_bedrift_includes_datakom_2024(self):
        df = execute_ekom(
            hk="Fast bredbånd",
            hg="Abonnement",
            ms="Bedrift",
            rapport="2024-Helår",
            pivot_years=False,
        )
        self.assertEqual(df["svar"][0], 165531.0)

    def test_mobile_agder_2025_halvaar_privat(self):
        df = execute_mobilabonnement_fylke(
            rapport="2025-Halvår",
            ms="Privat",
            fylke="Agder",
        )
        self.assertEqual(df["svar"][0], 271171.0)


if __name__ == "__main__":
    unittest.main()
