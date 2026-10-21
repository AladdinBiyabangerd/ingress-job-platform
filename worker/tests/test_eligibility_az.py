"""Eligibility pre-check: Azerbaijan / Baku in positive, negative and company contexts.

The same phrases also run through the AI quote check (market_fit.check_quote) so both layers
agree (shared helpers in worker.az_context).
"""

from __future__ import annotations

import unittest

from worker.az_context import quote_az_context
from worker.eligibility import CAP_AZ_CONFLICT, CAP_AZ_EXCLUDED, CAP_LOCKED, assess, is_hard_reject, summary
from worker.market_fit import check_quote

POSITIVE = [
    ("Backend Engineer", "", "Remote (Azerbaijan, Georgia). Python."),
    ("Backend Engineer", "", "Location: Baku, Azerbaijan (remote). Python."),
    ("Backend Engineer", "", "We hire in Azerbaijan and Georgia."),
    ("Senior DataOps Engineer (Europe, Georgia, Turkey, Azerbaijan, Ukraine)", "", "Flexible working format - remote."),
    (".NET Developer", "Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan", "Full Remote."),
    ("Infrastructure Engineer", "", "🟢 Дозволені країни: Киргизстан, Азербайджан, Грузія."),
    ("Backend Engineer", "Baku, Azerbaijan", "Baku office, on-site only. Python."),
    ("QA Engineer", "Bakı", "Manual testing."),
]
NEGATIVE = [
    "Remote for Europe. We do not hire from Azerbaijan.",
    "Remote worldwide, excluding Azerbaijan.",
    "Payroll: Azerbaijan is not supported.",
    "This role is not available in Azerbaijan.",
    "Remote in Europe; unfortunately we cannot employ people in Azerbaijan.",
    "Країни, з яких кандидати не розглядаються: Азербайджан, Росія.",
    "Azerbaijan excluded.",
]
COMPANY = [
    "Our client is based in Baku. The position is fully remote.",
    "Our client is an Azerbaijani telecommunications company, the largest mobile network operator in Azerbaijan.",
    "The team is international (Ukraine, Azerbaijan, South Africa).",
    "Our Baku office is our largest hub.",
]


class PositiveContextTest(unittest.TestCase):
    def test_candidate_only_cap_100(self):
        for title, place, text in POSITIVE:
            with self.subTest(title=title, place=place, text=text):
                e = assess(title, place, text)
                self.assertEqual((e["works_from_az"], e["remote_scope"], e["cap"]), ("yes", "az_listed", 100))
                line = summary(e)
                self.assertIn("Azərbaycan iş yeri kimi göstərilib", line)
                self.assertIn("mümkün uyğunluq", line)  # a candidate, not a decision
                self.assertIn("Sübut:", line)

    def test_region_mention_keeps_region_scope(self):
        e = assess("Backend Engineer", "", "Remote across the CIS and the Caucasus.")
        self.assertEqual((e["remote_scope"], e["works_from_az"], e["cap"]), ("region_incl_az", "yes", 100))

    def test_except_other_country_is_still_positive(self):
        e = assess("Backend Engineer", "", "Remote from Azerbaijan, Georgia (except Russia).")
        self.assertEqual(e["works_from_az"], "yes")


class NegativeContextTest(unittest.TestCase):
    def test_restriction_evidence_low_cap_never_hard_reject(self):
        for text in NEGATIVE:
            with self.subTest(text=text):
                e = assess("Backend Engineer", "", text)
                self.assertEqual((e["works_from_az"], e["remote_scope"]), ("no", "country_locked"))
                self.assertEqual(e["cap"], CAP_AZ_EXCLUDED)
                self.assertGreater(e["cap"], CAP_LOCKED)
                self.assertFalse(is_hard_reject(e))  # the AI still checks the ad
                line = summary(e)
                self.assertIn("inkar/istisna kontekstində", line)
                self.assertNotIn("Azərbaycan iş yeri kimi göstərilib", line)
                self.assertNotIn("Mətndə remote və ya relocation açıq yazılmayıb", line)

    def test_negation_about_something_else(self):
        e = assess("Backend Engineer", "", "Remote across Europe, Azerbaijan, Georgia — no relocation offered.")
        self.assertEqual(e["works_from_az"], "yes")
        e = assess("Backend Engineer", "", "No matter if you are in Baku or Berlin, you can work remotely.")
        self.assertEqual(e["works_from_az"], "yes")

    def test_other_lock_still_hard_rejects(self):
        # a lock found by another rule keeps its own cap; the AZ negation is not the only reason
        e = assess("Backend Engineer", "Sofia, Bulgaria", "Remote within Bulgaria only. Not available in Azerbaijan.")
        self.assertEqual(e["works_from_az"], "no")
        self.assertLessEqual(e["cap"], CAP_AZ_EXCLUDED)


class ConflictContextTest(unittest.TestCase):
    def test_allowed_and_excluded_goes_to_moderator(self):
        e = assess("VoIP Engineer", "Azerbaijan, Armenia, Georgia",
                   "Fully remote. Unfortunately we cannot employ people in Azerbaijan.")
        self.assertEqual((e["works_from_az"], e["cap"]), ("unclear", CAP_AZ_CONFLICT))
        self.assertIn("moderator yoxlasın", summary(e))


class CompanyContextTest(unittest.TestCase):
    def test_company_statement_is_neutral(self):
        for text in COMPANY:
            with self.subTest(text=text):
                e = assess("Backend Engineer", "", text)
                self.assertNotEqual(e["works_from_az"], "yes")
                self.assertNotIn(e["remote_scope"], ("az_listed", "region_incl_az", "country_locked"))
                self.assertIn("şirkət/müştəri/komanda haqqında", summary(e))

    def test_company_sentence_does_not_hide_title_list(self):
        e = assess("Senior DataOps Engineer (Europe, Georgia, Turkey, Azerbaijan, Ukraine)", "",
                   "Our client is an Azerbaijani telecommunications company. Remote, office-based or flexible.")
        self.assertEqual((e["works_from_az"], e["cap"]), ("yes", 100))


class LayersAgreeTest(unittest.TestCase):
    """Pre-check context == AI quote check for the same sentence."""

    def test_same_reading(self):
        for _title, _place, text in POSITIVE[:3] + POSITIVE[5:7]:
            q = text.split(". ")[0].rstrip(".")
            self.assertEqual(quote_az_context(q), "positive", q)
            self.assertEqual(check_quote("remote_az_explicit", q), "", q)
        for text in NEGATIVE:
            q = text.split(". ")[-1]
            self.assertEqual(quote_az_context(q), "negative", q)
            self.assertNotEqual(check_quote("remote_az_explicit", q), "", q)
        for text in COMPANY:
            q = text.split(". ")[0]
            self.assertEqual(quote_az_context(q), "company", q)
            self.assertNotEqual(check_quote("remote_az_explicit", q), "", q)


if __name__ == "__main__":
    unittest.main()
