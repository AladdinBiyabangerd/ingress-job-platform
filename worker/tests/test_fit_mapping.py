"""Exhaustive tests for the deterministic staff-% mapping (worker.fit_mapping)."""

from __future__ import annotations

import itertools
import unittest

from worker import fit_mapping as fm
from worker.fit_mapping import FLAGS, staff_percent

BAND = 85


def _combos():
    for bits in itertools.product((False, True), repeat=len(FLAGS)):
        yield dict(zip(FLAGS, bits))


class TableTest(unittest.TestCase):
    CASES = [
        ({"remote_az_explicit": True}, 95, "remote_az_explicit"),
        ({"remote_worldwide": True}, 90, "remote_worldwide"),
        ({"remote_region_includes_az": True}, 88, "remote_region_includes_az"),
        ({"relocation": True, "visa_support": True}, 88, "relocation+visa_support"),
        ({"relocation": True}, 70, "relocation"),
        ({"visa_support": True}, 70, "visa_support"),
        ({"country_restricted": True}, 15, "restricted"),
        ({"temporary_abroad_only": True}, 15, "restricted"),
        ({}, 40, "no_evidence"),
        ({"no_sponsorship_stated": True}, 40, "no_evidence"),
        # restriction beats weaker positive
        ({"remote_worldwide": True, "country_restricted": True}, 15, "restricted"),
        ({"remote_region_includes_az": True, "temporary_abroad_only": True}, 15, "restricted"),
        ({"remote_worldwide": True, "country_restricted": True, "relocation": True}, 70, "relocation"),
        # no-sponsorship contradicts visa
        ({"relocation": True, "visa_support": True, "no_sponsorship_stated": True}, 70, "relocation"),
        ({"visa_support": True, "no_sponsorship_stated": True}, 40, "no_evidence"),
        ({"visa_support": True, "no_sponsorship_stated": True, "country_restricted": True}, 15, "restricted"),
        # truncation caps below the band
        ({"remote_worldwide": True, "text_truncated_or_missing_location": True}, 84, "remote_worldwide"),
        ({"text_truncated_or_missing_location": True}, 40, "no_evidence"),
        # explicit AZ wins over a restriction (AZ named = AZ allowed)
        ({"remote_az_explicit": True, "country_restricted": True}, 95, "remote_az_explicit"),
    ]

    def test_table(self):
        for flags, score, route in self.CASES:
            with self.subTest(flags=flags):
                self.assertEqual(staff_percent(flags), (score, route))


class ExhaustiveTest(unittest.TestCase):
    def test_all_512_combinations(self):
        seen = 0
        for f in _combos():
            seen += 1
            score, route = staff_percent(f)
            restricted = f["country_restricted"] or f["temporary_abroad_only"]
            visa = f["visa_support"] and not f["no_sponsorship_stated"]
            with self.subTest(flags={k for k, v in f.items() if v}):
                self.assertIn(score, {95, 90, 88, 84, 70, 40, 15})
                # 85+ only with real evidence of a route.
                if score >= BAND:
                    self.assertFalse(f["text_truncated_or_missing_location"])
                    self.assertTrue(
                        f["remote_az_explicit"]
                        or (f["remote_worldwide"] and not restricted)
                        or (f["remote_region_includes_az"] and not restricted)
                        or (f["relocation"] and visa)
                    )
                # No positive flag at all -> never above 40.
                if not any(f[k] for k in fm.POSITIVE_FLAGS):
                    self.assertLessEqual(score, 40)
                    self.assertEqual(score, 15 if restricted else 40)
                # Restriction with no relocation/visa/AZ route -> 15.
                if restricted and not (f["remote_az_explicit"] or f["relocation"] or visa):
                    self.assertEqual(score, 15)
                # Single relocation or visa route never reaches the band.
                if not (f["remote_az_explicit"] or f["remote_worldwide"] or f["remote_region_includes_az"]) and not (
                    f["relocation"] and visa
                ):
                    self.assertLess(score, BAND)
                self.assertEqual(fm.is_suitable(route), route not in ("restricted", "no_evidence"))
        self.assertEqual(seen, 2 ** len(FLAGS))

    def test_monotonic_in_restrictions(self):
        """Adding a restrictive flag never raises the score."""
        for f in _combos():
            base, _ = staff_percent(f)
            for flag in fm.RESTRICTIVE_FLAGS + fm.INFO_FLAGS:
                if not f[flag]:
                    more, _ = staff_percent({**f, flag: True})
                    self.assertLessEqual(more, base, (f, flag))

    def test_constants_order(self):
        self.assertGreater(fm.SCORE_AZ_EXPLICIT, fm.SCORE_WORLDWIDE)
        self.assertGreaterEqual(fm.SCORE_WORLDWIDE, fm.SCORE_REGION_INCL_AZ)
        self.assertLess(fm.SCORE_SINGLE_ROUTE, BAND)
        self.assertLess(fm.TRUNCATED_CAP, BAND)
        self.assertLess(fm.SCORE_RESTRICTED, fm.SCORE_NO_EVIDENCE)


if __name__ == "__main__":
    unittest.main()
