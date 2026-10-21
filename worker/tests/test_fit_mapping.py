"""Exhaustive tests for the deterministic staff-% mapping (worker.fit_mapping, market-fit-v8)."""

from __future__ import annotations

import itertools
import unittest

from worker import fit_mapping as fm
from worker.fit_mapping import FLAGS, has_conflict, staff_percent, upgrade_legacy

BAND = 85


def _combos():
    for bits in itertools.product((False, True), repeat=len(FLAGS)):
        yield dict(zip(FLAGS, bits))


def _on(*names):
    return {n: True for n in names}


class TableTest(unittest.TestCase):
    CASES = [
        (_on("remote_az_explicit"), 95, "remote_az_explicit"),
        (_on("remote_worldwide"), 90, "remote_worldwide"),
        (_on("remote_region_includes_az"), 88, "remote_region_includes_az"),
        (_on("relocation", "visa_support"), 88, "relocation+visa_support"),
        (_on("relocation"), 70, "relocation"),
        (_on("visa_support"), 70, "visa_support"),
        (_on("remote_country_restricted"), 15, "restricted"),
        (_on("candidate_location_restricted"), 15, "restricted"),
        (_on("work_authorization_required"), 15, "restricted"),
        (_on("temporary_abroad_only"), 15, "restricted"),
        ({}, 40, "no_evidence"),
        (_on("no_sponsorship_stated"), 40, "no_evidence"),
        # conflict: remote worldwide + "US and Canada residents only" -> restriction wins
        (_on("remote_worldwide", "remote_country_restricted"), 15, "restricted"),
        (_on("remote_worldwide", "candidate_location_restricted"), 15, "restricted"),
        (_on("remote_region_includes_az", "temporary_abroad_only"), 15, "restricted"),
        # a remote-only restriction leaves relocation as a (manual) route
        (_on("remote_worldwide", "remote_country_restricted", "relocation"), 70, "relocation"),
        # remote worldwide + "right to work in <country>": staff check, below the band
        (_on("remote_worldwide", "work_authorization_required"), 84, "remote_worldwide"),
        # no sponsorship does not touch a valid remote-from-AZ route
        (_on("remote_az_explicit", "no_sponsorship_stated"), 95, "remote_az_explicit"),
        (_on("remote_worldwide", "no_sponsorship_stated"), 90, "remote_worldwide"),
        # no sponsorship / existing work authorization contradict visa
        (_on("relocation", "visa_support", "no_sponsorship_stated"), 70, "relocation"),
        (_on("relocation", "visa_support", "work_authorization_required"), 70, "relocation"),
        (_on("visa_support", "no_sponsorship_stated"), 40, "no_evidence"),
        (_on("visa_support", "no_sponsorship_stated", "remote_country_restricted"), 15, "restricted"),
        # "open to candidates who currently live in the EU" kills relocation + visa too
        (_on("relocation", "visa_support", "candidate_location_restricted"), 15, "restricted"),
        # on-site work-auth requirement alone does not kill a relocation route
        (_on("relocation", "work_authorization_required"), 70, "relocation"),
        # truncation / unknown work location cap below the band
        (_on("remote_worldwide", "text_truncated"), 84, "remote_worldwide"),
        (_on("remote_worldwide", "work_location_unspecified"), 84, "remote_worldwide"),
        (_on("relocation", "visa_support", "work_location_unspecified"), 84, "relocation+visa_support"),
        (_on("text_truncated"), 40, "no_evidence"),
        (_on("work_location_unspecified"), 40, "no_evidence"),
        # truncated + conflicting evidence never reaches the band
        (_on("remote_worldwide", "remote_country_restricted", "text_truncated"), 15, "restricted"),
        (_on("remote_az_explicit", "remote_country_restricted", "text_truncated"), 84, "remote_az_explicit"),
        # explicit AZ wins over a restriction (AZ named = AZ allowed)
        (_on("remote_az_explicit", "remote_country_restricted"), 95, "remote_az_explicit"),
    ]

    def test_table(self):
        for flags, score, route in self.CASES:
            with self.subTest(flags=sorted(flags)):
                self.assertEqual(staff_percent(flags), (score, route))


class ExhaustiveTest(unittest.TestCase):
    def test_all_combinations(self):
        seen = 0
        for f in _combos():
            seen += 1
            score, route = staff_percent(f)
            blocked = f["remote_country_restricted"] or f["candidate_location_restricted"] or f["temporary_abroad_only"]
            restricted = blocked or f["work_authorization_required"]
            visa = f["visa_support"] and not (f["no_sponsorship_stated"] or f["work_authorization_required"])
            movable = not f["candidate_location_restricted"]
            with self.subTest(flags=sorted(k for k, v in f.items() if v)):
                self.assertIn(score, {95, 90, 88, 84, 70, 40, 15})
                # 85+ only with real evidence of a route, on a complete ad with a location.
                if score >= BAND:
                    self.assertFalse(f["text_truncated"])
                    self.assertFalse(f["work_location_unspecified"])
                    self.assertTrue(
                        f["remote_az_explicit"]
                        or ((f["remote_worldwide"] or f["remote_region_includes_az"]) and not restricted)
                        or (f["relocation"] and visa and movable)
                    )
                # Truncated + conflicting evidence never auto-yields the band.
                if f["text_truncated"] and has_conflict(f):
                    self.assertLess(score, BAND)
                # No positive flag at all -> never above 40.
                if not any(f[k] for k in fm.POSITIVE_FLAGS):
                    self.assertEqual(score, 15 if restricted else 40)
                # no_sponsorship_stated never lowers a valid remote route.
                if f["no_sponsorship_stated"]:
                    self.assertEqual(score, staff_percent({**f, "no_sponsorship_stated": False})[0]
                                     if (f["remote_az_explicit"] or f["remote_worldwide"] or f["remote_region_includes_az"])
                                     and not f["visa_support"] else score)
                # Single relocation or visa route never reaches the band.
                if not (f["remote_az_explicit"] or f["remote_worldwide"] or f["remote_region_includes_az"]) and not (
                    f["relocation"] and visa
                ):
                    self.assertLess(score, BAND)
                self.assertEqual(fm.is_suitable(route), route not in ("restricted", "no_evidence"))
        self.assertEqual(seen, 2 ** len(FLAGS))

    def test_monotonic_in_restrictions(self):
        """Adding a restrictive or info flag never raises the score."""
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
        self.assertLess(fm.INFO_CAP, BAND)
        self.assertLess(fm.AUTH_CONFLICT_CAP, BAND)
        self.assertLess(fm.SCORE_RESTRICTED, fm.SCORE_NO_EVIDENCE)
        self.assertEqual(len(FLAGS), 13)
        self.assertEqual(fm.AI_FLAGS, fm.FLAGS)  # v8: the model may answer text_truncated; code wins


class LegacyTest(unittest.TestCase):
    def test_v6_names_upgraded(self):
        up = upgrade_legacy({"country_restricted": True, "text_truncated_or_missing_location": True})
        self.assertTrue(up["remote_country_restricted"])
        self.assertTrue(up["candidate_location_restricted"])
        self.assertTrue(up["work_location_unspecified"])
        self.assertNotIn("country_restricted", up)
        self.assertEqual(staff_percent(up)[0], 15)

    def test_v6_worldwide_with_old_truncation_flag_stays_below_band(self):
        up = upgrade_legacy({"remote_worldwide": True, "text_truncated_or_missing_location": True})
        self.assertEqual(staff_percent(up), (84, "remote_worldwide"))


if __name__ == "__main__":
    unittest.main()
