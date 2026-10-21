"""Offline real-data eval: labelled flags through mapping + eligibility caps (no AI)."""

from __future__ import annotations

import unittest
from collections import Counter

from worker.market_fit_eval import load_fixtures, offline_score, outcome


class OfflineEvalTest(unittest.TestCase):
    def test_fixture_mix(self):
        ads = load_fixtures()
        self.assertGreaterEqual(len(ads), 40)
        labels = Counter(a["expected"] for a in ads)
        for label in ("eligible", "manual", "not_eligible", "unclear", "truncated"):
            self.assertGreater(labels[label], 0, label)
        self.assertEqual(len({a["key"] for a in ads}), len(ads))
        for a in ads:
            self.assertTrue(a["evidence"], a["key"])

    def test_no_false_positive_or_negative(self):
        bad = []
        for ad in load_fixtures():
            res = offline_score(ad)
            if outcome(ad["expected"], res["score"]) != "ok":
                bad.append((ad["key"], ad["expected"], res["score"], res["route"]))
        self.assertEqual(bad, [])

    def test_outcome_bands(self):
        self.assertEqual(outcome("eligible", 85), "ok")
        self.assertEqual(outcome("eligible", 84), "FN")
        self.assertEqual(outcome("unclear", 85), "FP")
        self.assertEqual(outcome("manual", 80), "ok")
        self.assertEqual(outcome("manual", 40), "FN")
        self.assertEqual(outcome("manual", 88), "FP")


if __name__ == "__main__":
    unittest.main()
