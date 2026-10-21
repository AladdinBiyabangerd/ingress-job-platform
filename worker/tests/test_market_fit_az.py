"""market-fit-v9 (post-review): Azerbaijan / Baku evidence and visa_support_conditional combinations.

Positive and negative AZ quotes run through the code's quote validation and mapping
(``verdict_from_ai`` + ``fit_detail``); the AI answer is simulated so the code's
interpretation and final % are asserted, not the model.

Decision (documented in fit_mapping): hybrid / on-site work in Baku is the same
``remote_az_explicit`` route (95) because a candidate living in Azerbaijan can do it.
"""

from __future__ import annotations

import itertools
import unittest

from worker.fit_mapping import FLAGS, staff_percent, visa_note
from worker.market_fit import fit_detail, verdict_from_ai


def _answer(**flags):
    data = {name: {"value": False, "quotes": []} for name in FLAGS}
    for name, quotes in flags.items():
        data[name] = {"value": True, "quotes": list(quotes) if isinstance(quotes, (list, tuple)) else []}
    data["reason"] = "test"
    return data


def _verdict(ad_text, title="Backend Engineer", place="", **flags):
    return verdict_from_ai(_answer(**flags), ad_text=f"{title}\n{place}\n{ad_text}", truncated=False)


class AzPositiveTest(unittest.TestCase):
    CASES = [
        # (title, location field, ad text, quote)
        ("Backend Engineer", "", "Remote (Azerbaijan, Georgia). Python, Django.", "Remote (Azerbaijan, Georgia)"),
        ("Backend Engineer", "", "Location: Baku, Azerbaijan (remote). Python.", "Location: Baku, Azerbaijan (remote)"),
        ("Backend Engineer", "", "We hire in Azerbaijan and Georgia. Python.", "We hire in Azerbaijan"),
        # country list in the title (Djinni style), the N-iX shape without the company
        ("Senior DataOps Engineer (Europe, Georgia, Turkey, Azerbaijan, Ukraine)", "",
         "Flexible working format - remote, office-based or flexible.", "(Europe, Georgia, Turkey, Azerbaijan, Ukraine)"),
        # country list in the location field
        (".NET Developer", "Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan", "Full Remote.",
         "Armenia, Azerbaijan, Georgia, Kazakhstan, Kyrgyzstan"),
        # Cyrillic allowed-countries list
        ("Infrastructure Engineer", "", "🟢 Дозволені країни: Киргизстан, Азербайджан, Грузія.",
         "Дозволені країни: Киргизстан, Азербайджан, Грузія."),
        # on-site / hybrid in Baku: same route (decision above)
        ("Backend Engineer", "Baku", "Baku office, on-site only. Python.", "Baku office, on-site only"),
        ("Backend Engineer", "", "Hybrid: 3 days a week in our Baku office.", "Hybrid: 3 days a week in our Baku office."),
    ]

    def test_positive_quotes_give_95(self):
        for title, place, text, quote in self.CASES:
            with self.subTest(quote=quote):
                v = _verdict(text, title=title, place=place, remote_az_explicit=[quote], work_location_unspecified=[])
                self.assertTrue(v["flags"]["remote_az_explicit"], v["validation_notes"])
                self.assertEqual(v["quotes"]["remote_az_explicit"], [quote])
                # a quoted work place contradicts "work location unspecified": code clears it
                self.assertFalse(v["flags"]["work_location_unspecified"])
                self.assertEqual((v["route"], v["ai_score"]), ("remote_az_explicit", 95))
                d = fit_detail(v)
                self.assertEqual(d["route"], "remote_az_explicit")
                self.assertIn(quote, d["flags"][0]["quotes"])


class AzNegativeTest(unittest.TestCase):
    CASES = [
        ("Remote for Europe. We do not hire from Azerbaijan.", "We do not hire from Azerbaijan"),
        ("Remote across the CIS, excluding Azerbaijan.", "Remote across the CIS, excluding Azerbaijan."),
        ("Payroll: Azerbaijan is not supported.", "Azerbaijan is not supported"),
        ("This role is not available in Azerbaijan.", "This role is not available in Azerbaijan."),
        ("Remote in Europe; unfortunately we cannot employ people in Azerbaijan.",
         "unfortunately we cannot employ people in Azerbaijan"),
        ("Країни, з яких кандидати не розглядаються: Азербайджан, Росія.",
         "Країни, з яких кандидати не розглядаються: Азербайджан, Росія."),
        # company / client / team statements: not a work allowance
        ("Our client is based in Baku. Python.", "Our client is based in Baku"),
        ("Our client is an Azerbaijani telecommunications company, the largest mobile network operator in Azerbaijan.",
         "Our client is an Azerbaijani telecommunications company, the largest mobile network operator in Azerbaijan."),
        ("The team is international (Ukraine, Azerbaijan, South Africa).",
         "The team is international (Ukraine, Azerbaijan, South Africa)."),
        ("Our Baku office is our largest hub.", "Our Baku office is our largest hub."),
    ]

    def test_negated_or_company_az_never_sets_flag(self):
        for text, quote in self.CASES:
            with self.subTest(quote=quote):
                v = _verdict(text, remote_az_explicit=[quote])
                self.assertFalse(v["flags"]["remote_az_explicit"])
                self.assertEqual(v["route"], "no_evidence")
                self.assertEqual(v["ai_score"], 40)
                self.assertTrue(any(n.startswith("remote_az_explicit:") for n in v["validation_notes"]))

    def test_negated_az_with_restriction_is_restricted_15(self):
        v = _verdict(
            "Remote for Europe. We do not hire from Azerbaijan.",
            remote_az_explicit=["We do not hire from Azerbaijan"],
            remote_country_restricted=["Remote for Europe"],
        )
        self.assertFalse(v["flags"]["remote_az_explicit"])
        self.assertEqual((v["route"], v["ai_score"]), ("restricted", 15))


class AzConflictTest(unittest.TestCase):
    def test_location_field_lists_az_but_text_list_leaves_it_out(self):
        # shape of real ad 1243: location field names Azerbaijan, text list does not
        v = _verdict(
            "Fully remote cooperation. Open for candidates from countries as follows: Armenia, Georgia, Moldova",
            title="VoIP Engineer",
            place="Azerbaijan, Armenia, Georgia, Moldova",
            remote_az_explicit=["Azerbaijan, Armenia, Georgia, Moldova"],
            candidate_location_restricted=["Open for candidates from countries as follows: Armenia, Georgia, Moldova"],
        )
        self.assertTrue(v["flags"]["remote_az_explicit"])
        self.assertIn("remote_vs_restriction", v["conflicts"])
        self.assertEqual((v["route"], v["ai_score"]), ("remote_az_explicit", 84))

    def test_az_explicit_with_any_block_never_reaches_band(self):
        blocks = ("remote_country_restricted", "candidate_location_restricted", "temporary_abroad_only",
                  "work_authorization_required")
        for n in range(1, len(blocks) + 1):
            for combo in itertools.combinations(blocks, n):
                f = {name: False for name in FLAGS}
                f["remote_az_explicit"] = True
                f.update({b: True for b in combo})
                with self.subTest(combo=combo):
                    self.assertEqual(staff_percent(f), (84, "remote_az_explicit"))


class ConditionalVisaCombinationTest(unittest.TestCase):
    AD = (
        "We offer relocation support to London. We do sponsor visas! However, we aren't able to successfully "
        "sponsor visas for every role and every candidate. Remote from anywhere in the world. "
        "We do not sponsor visas. Candidates must reside in the UK."
    )
    VISA = dict(
        visa_support=["We do sponsor visas!"],
        visa_support_conditional=["we aren't able to successfully sponsor visas for every role and every candidate"],
    )
    # (name, extra flags, expected route, expected %, visa_strength, visa_note, conflicts)
    COMBOS = [
        ("conditional visa alone", {}, "visa_conditional", 70, "weak", "weak", []),
        ("conditional visa + relocation", {"relocation": ["We offer relocation support to London."]},
         "relocation+visa_conditional", 70, "weak", "weak", []),
        ("conditional visa + remote_worldwide", {"remote_worldwide": ["Remote from anywhere in the world."]},
         "remote_worldwide", 90, "weak", "remote_route", []),
        ("conditional visa + no_sponsorship", {"no_sponsorship_stated": ["We do not sponsor visas."]},
         "no_evidence", 40, "", "no_sponsorship", ["visa_vs_no_sponsorship"]),
        ("conditional visa + candidate_location_restricted",
         {"candidate_location_restricted": ["Candidates must reside in the UK."]},
         "restricted", 15, "", "candidate_location", ["move_vs_candidate_location"]),
    ]

    def test_combinations(self):
        for name, extra, route, pct, strength, note, confl in self.COMBOS:
            with self.subTest(name):
                v = _verdict(self.AD, **self.VISA, **extra)
                self.assertTrue(v["flags"]["visa_support_conditional"])
                self.assertEqual((v["route"], v["ai_score"]), (route, pct))
                self.assertEqual(v["visa_strength"], strength)
                self.assertEqual(v["visa_note"], note)
                self.assertEqual(v["conflicts"], confl)
                # popover detail carries the route, %, visa note (with its label) and conflicts
                d = fit_detail(v)
                self.assertEqual((d["route"], d["ai_score"]), (route, pct))
                self.assertEqual(d["visa_note"]["key"], note)
                self.assertTrue(d["visa_note"]["label"])
                self.assertEqual([c["key"] for c in d["conflicts"]], confl)
                self.assertIn(d["visa_note"]["label"], v["reason"])
                cond = next(f for f in d["flags"] if f["name"] == "visa_support_conditional")
                self.assertTrue(cond["quotes"])

    def test_visa_note_pure(self):
        f = {name: False for name in FLAGS}
        self.assertEqual(visa_note(f), "")
        f.update(visa_support=True)
        self.assertEqual(visa_note(f, "visa_support"), "")
        f.update(visa_support_conditional=True)
        self.assertEqual(visa_note(f, "visa_conditional"), "weak")
        self.assertEqual(visa_note(f, "remote_az_explicit"), "remote_route")
        self.assertEqual(visa_note({**f, "work_authorization_required": True}, "restricted"), "work_authorization")


if __name__ == "__main__":
    unittest.main()
