"""Free-text salary parse for trend aggregates."""

from __future__ import annotations

import unittest

from worker.salary_parse import parse_salary_annual, pick_currency_values, salary_stats


class SalaryParseTest(unittest.TestCase):
    def test_annual_gbp_range(self):
        parsed = parse_salary_annual("45,000–55,000 GBP per annum")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["currency"], "GBP")
        self.assertEqual(parsed["period"], "YEAR")
        self.assertAlmostEqual(parsed["annual"], 50000.0)

    def test_monthly_azn(self):
        parsed = parse_salary_annual("1500-2000 AZN aylıq")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["currency"], "AZN")
        self.assertEqual(parsed["period"], "MONTH")
        self.assertAlmostEqual(parsed["annual"], 1750.0 * 12)

    def test_rejects_ambiguous(self):
        self.assertIsNone(parse_salary_annual("$120k"))
        self.assertIsNone(parse_salary_annual("negotiable"))
        self.assertIsNone(parse_salary_annual("50000"))

    def test_salary_stats_and_currency_pick(self):
        parsed = [
            parse_salary_annual("40,000 GBP per year"),
            parse_salary_annual("60,000 GBP per year"),
            parse_salary_annual("3000 EUR per month"),
        ]
        parsed = [p for p in parsed if p]
        currency, values = pick_currency_values(parsed)
        self.assertEqual(currency, "GBP")
        self.assertEqual(len(values), 2)
        stats = salary_stats(values, currency)
        self.assertEqual(stats["n"], 2)
        self.assertEqual(stats["median"], 50000.0)
        self.assertEqual(stats["low"], 40000.0)
        self.assertEqual(stats["high"], 60000.0)


if __name__ == "__main__":
    unittest.main()
