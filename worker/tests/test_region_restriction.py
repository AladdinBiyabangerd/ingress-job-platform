"""Remote restricted to a region that excludes Azerbaijan must not count as remote."""

from __future__ import annotations

import unittest

from worker.techstack import (
    apply_relocation_override,
    az_market_relevant,
    foreign_locked_remote,
    neighbour_region_eligible,
    region_restriction_reason,
    relocation_overrides_lock,
)


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

    def test_timezone_is_not_a_rejection_reason(self):
        for text in ("Working hours must overlap with CEST for at least 20 hours/week.",
                     "Hours must overlap with EST for at least 20 hours/week.",
                     "You must be available in US time zones.",
                     "Sourcegraph: overlap with CEST/EST at least 20 hours per week."):
            self.assertEqual(r(text=text), "", text)
            self.assertFalse(foreign_locked_remote("Dev", "Remote", text), text)
            self.assertTrue(az_market_relevant("Dev", "Remote", text + " Work from anywhere.",
                                               remote=True, relocation=False), text)

    def test_country_and_us_only_still_rejected(self):
        self.assertTrue(foreign_locked_remote("Dev", "Remote (Germany)", "Build APIs."))
        self.assertTrue(foreign_locked_remote("Dev", "Remote", "This role is US only."))
        self.assertFalse(az_market_relevant("Dev", "Remote (Germany)", "Build APIs.",
                                            remote=True, relocation=False))
        self.assertFalse(az_market_relevant("Dev", "Remote", "US only role.",
                                            remote=True, relocation=False))

    def test_relocation_overrides_region_lock(self):
        for place, text in (
            ("Remote (Europe)", "EU only. We offer relocation support."),
            ("Remote (Germany)", "Visa sponsorship available for non-EU candidates."),
            ("Remote - Greece", "We provide a relocation package."),
        ):
            item = {"title": "Dev", "city": place, "text": text, "remote": True, "relocation": False}
            self.assertTrue(az_market_relevant("Dev", place, text, remote=True, relocation=False), place)
            apply_relocation_override(item)
            self.assertFalse(item["remote"], place)
            self.assertTrue(item["relocation"], place)

    def test_relocation_flag_alone_does_not_save_us_h1b(self):
        item = {"title": "Dev", "city": "Remote (US)", "text": "H-1B sponsorship.",
                "remote": True, "relocation": True}
        apply_relocation_override(item)
        self.assertTrue(item["remote"])

    def test_structured_relocation_flag(self):
        item = {"title": "Dev", "city": "Remote (Europe)", "text": "EU only.",
                "remote": True, "relocation": True}
        apply_relocation_override(item, structured_relocation=True)
        self.assertEqual((item["remote"], item["relocation"]), (False, True))
        self.assertTrue(az_market_relevant("Dev", "Remote (Europe)", "EU only.", remote=True,
                                           relocation=True, structured_relocation=True))

    def test_worldwide_remote_untouched_by_override(self):
        item = {"title": "Dev", "city": "Remote", "text": "Work from anywhere. Relocation help.",
                "remote": True, "relocation": True}
        apply_relocation_override(item)
        self.assertTrue(item["remote"])

    def test_neighbour_regions(self):
        # Not eligible without explicit text: still rejected.
        for place in ("Remote (Asia)", "Remote - Turkey", "Remote, Georgia"):
            self.assertTrue(foreign_locked_remote("Dev", place, "Build APIs."), place)
        # Eligible only when the text opens it to Azerbaijan.
        for place, text in (
            ("Remote (Asia)", "Candidates from Azerbaijan are welcome."),
            ("Remote - Turkey", "We also hire in Baku and the Caucasus."),
            ("Remote (Asia)", "Open to candidates anywhere in Asia."),
            ("Remote (Georgia)", "Hiring across CIS countries."),
            ("Remote (Asia)", "This is a worldwide remote role."),
        ):
            self.assertFalse(foreign_locked_remote("Dev", place, text), (place, text))
            self.assertTrue(neighbour_region_eligible("Dev", place, text))
        # A non-neighbour geo keeps the lock even if Baku is named.
        self.assertTrue(foreign_locked_remote("Dev", "Remote (Germany)", "Baku office visits."))
        self.assertFalse(neighbour_region_eligible("Dev", "Remote (Germany, Turkey)", "Azerbaijan ok."))

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
        text = "This role is EU only. We offer visa sponsorship and a relocation package."
        self.assertTrue(foreign_locked_remote("Dev", "Remote", text))  # still region-locked...
        self.assertTrue(relocation_overrides_lock("Dev", "Remote", text))  # ...but offer overrides
        self.assertTrue(az_market_relevant("Dev", "Remote", text, remote=True, relocation=True))
        self.assertTrue(foreign_locked_remote("Dev", "Remote", "This role is EU only."))

    def test_market_gate_uses_source(self):
        self.assertFalse(az_market_relevant("Dev", "Remote", "Build APIs.", remote=True,
                                            relocation=False, source="Get on Board (Latin America)"))
        self.assertTrue(az_market_relevant("Dev", "Remote", "Build APIs. Work from anywhere.",
                                           remote=True, relocation=False))


if __name__ == "__main__":
    unittest.main()
