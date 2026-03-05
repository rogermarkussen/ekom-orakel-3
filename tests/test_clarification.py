import unittest

from library.clarification import AmbiguousQueryError, assess_query_clarity
from main import route_query


class ClarificationTests(unittest.TestCase):
    def test_coverage_question_without_year_and_definition_requires_clarification(self):
        result = assess_query_clarity("Hva er dekningen i Agder?")
        self.assertTrue(result.needs_clarification)
        prompt = result.to_user_prompt()
        self.assertIn("Hvilket år", prompt)
        self.assertIn("teknologi", prompt)

    def test_mobildekning_requires_generation(self):
        result = assess_query_clarity("Hva er mobildekningen i Nordland i 2024?")
        self.assertTrue(result.needs_clarification)
        self.assertIn("4G, 5G eller begge", result.to_user_prompt())

    def test_ekom_question_requires_metric_and_period(self):
        result = assess_query_clarity("Hvordan går det med fast bredbånd?")
        self.assertTrue(result.needs_clarification)
        prompt = result.to_user_prompt()
        self.assertIn("rapportperiode", prompt)
        self.assertIn("abonnement, inntekter eller trafikk", prompt)

    def test_explicit_gigabit_question_is_not_flagged(self):
        result = assess_query_clarity("Hva er gigabitdekningen nasjonalt i 2024?")
        self.assertFalse(result.needs_clarification)

    def test_route_query_raises_before_guessing(self):
        with self.assertRaises(AmbiguousQueryError):
            route_query("Hva er dekningen i Agder?")


if __name__ == "__main__":
    unittest.main()
