"""Free-text salary parse for trend aggregates."""

from __future__ import annotations

import unittest

from worker.salary_parse import (
    parse_salary_annual,
    pick_currency_values,
    salary_stats,
    stats_by_currency,
)


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

    def test_stats_by_currency_keeps_groups_separate(self):
        parsed = [
            parse_salary_annual("40,000 GBP per year"),
            parse_salary_annual("60,000 GBP per year"),
            parse_salary_annual("3000 EUR per month"),
            parse_salary_annual("3500 EUR per month"),
            parse_salary_annual("100000 RUB per month"),
        ]
        parsed = [p for p in parsed if p]
        groups = stats_by_currency(parsed)
        by_code = {g["currency"]: g for g in groups}
        self.assertEqual(set(by_code), {"EUR", "GBP", "RUB"})
        self.assertEqual(by_code["GBP"]["n"], 2)
        self.assertEqual(by_code["GBP"]["median"], 50000.0)
        self.assertEqual(by_code["EUR"]["n"], 2)
        self.assertEqual(by_code["EUR"]["median"], 3250.0 * 12)
        self.assertEqual(by_code["RUB"]["n"], 1)
        # Majority currency first.
        self.assertIn(groups[0]["currency"], {"EUR", "GBP"})


if __name__ == "__main__":
    unittest.main()
