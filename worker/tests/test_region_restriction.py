"""Remote restricted to a region that excludes Azerbaijan must not count as remote."""

from __future__ import annotations

import unittest

from worker.techstack import az_market_relevant, foreign_locked_remote, region_restriction_reason


def r(title="Backend Engineer", place="Remote", text="", source=""):
    return region_restriction_reason(title, place, text, source)


class RegionRestrictionTest(unittest.TestCase):
    def test_region_only_phrases_blocked(self):
        for text in (
            "This role is EU only.", "Remote, EEA only.", "Open to Europe only candidates.",
            "UK only role.", "Candidates must be located in the European Union.",
            "We are hiring only in North America.", "Hiring in LATAM only.",
            "Must be based in Canada.", "Remote within Africa.",
            "Candidates must reside in Latin America.",
        ):
            self.assertEqual(r(text=text), "region_only", text)

    def test_title_and_place_pins(self):
        self.assertEqual(r(title="Product Manager - Brokerage - EU"), "region_only")
        self.assertEqual(r(place="Remote - Europe"), "region_only")
        self.assertEqual(r(place="Remote (North America)"), "region_only")

    def test_work_authorization(self):
        for text in ("You must be authorized to work in the US.",
                     "Applicants must be legally authorized to work in the UK.",
                     "Must have the right to work in the EU."):
            self.assertEqual(r(text=text), "work_authorization", text)

    def test_timezone_overlap_explicit(self):
        self.assertEqual(r(text="Working hours must overlap with CEST for at least 20 hours/week."),
                         "timezone_overlap")
        self.assertEqual(r(text="Hours must overlap with EST for at least 20 hours/week."),
                         "timezone_overlap")
        self.assertEqual(r(text="You must be available in US time zones."), "timezone_overlap")

    def test_soft_phrases_not_rejected(self):
        for text in ("We are async friendly and work across time zones.",
                     "Candidates from the EU should review the applicant privacy notice.",
                     "We have customers across Europe and North America.",
                     "Availability to work EU hours.",
                     "Reasonable overlap with European business hours (CET/CEST).",
                     "Join us. Fingerprint teammates need to be authorized to work from their home location.",
                     "Implement CIS Benchmarks hardening. 401k match (US only)."):
            self.assertEqual(r(text=text), "", text)

    def test_worldwide_and_azerbaijan_open(self):
        self.assertEqual(r(place="Remote - Worldwide", text="EU only teams exist."), "")
        self.assertEqual(r(place="Remote EMEA"), "")
        self.assertEqual(r(text="Open to candidates in Azerbaijan, EU only otherwise."), "")
        self.assertFalse(foreign_locked_remote("Dev", "Remote", "We hire globally. Work from anywhere."))

    def test_regional_source(self):
        self.assertEqual(r(source="Get on Board (Latin America)", text="Build APIs."), "source_region_latam")
        self.assertEqual(r(source="Get on Board (Latin America)", text="Work from anywhere in the world."), "")
        self.assertEqual(r(source="Greenhouse boards (Canada)", text="Build APIs."), "")

    def test_relocation_offer_is_exception(self):
        text = ("Hours must overlap with EST for at least 20 hours/week. "
                "We offer visa sponsorship and a relocation package.")
        self.assertFalse(foreign_locked_remote("Dev", "Remote", text))
        self.assertTrue(foreign_locked_remote(
            "Dev", "Remote", "Hours must overlap with EST for at least 20 hours/week."))

    def test_market_gate_uses_source(self):
        self.assertFalse(az_market_relevant("Dev", "Remote", "Build APIs.", remote=True,
                                            relocation=False, source="Get on Board (Latin America)"))
        self.assertTrue(az_market_relevant("Dev", "Remote", "Build APIs. Work from anywhere.",
                                           remote=True, relocation=False))


if __name__ == "__main__":
    unittest.main()
