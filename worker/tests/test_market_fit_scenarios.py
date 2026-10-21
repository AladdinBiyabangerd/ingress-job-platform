"""The 8 review scenarios on real (or clearly marked synthetic) eval ads: for an AI answer
of the kind the model gives, check the code's interpretation — accepted / rejected quotes,
conflicts, mapping rule and final % band (after the eligibility cap)."""

from __future__ import annotations

import unittest

from worker.fit_mapping import AI_FLAGS
from worker.market_fit_eval import load_fixtures, replay_score

ADS = {a["key"]: a for a in load_fixtures()}


def _answer(**on):
    out = {name: {"value": False, "quotes": []} for name in AI_FLAGS}
    for name, quotes in on.items():
        out[name] = {"value": True, "quotes": [quotes] if isinstance(quotes, str) else list(quotes)}
    out["reason"] = "Test."
    return out


def _band(score: int) -> str:
    return "approve" if score >= 85 else ("manual" if score >= 60 else "low")


SCENARIOS = {
    1: dict(
        key="690",
        answer=_answer(remote_worldwide="Work remotely from anywhere in the world"),
        flags={"remote_worldwide"}, rejected=[], conflicts=[], route="remote_worldwide", score=90,
    ),
    2: dict(
        key="1",
        answer=_answer(
            remote_country_restricted=[
                "For this role, we can hire candidates based in the UK, Ireland, Germany, Portugal, Spain or The Netherlands",
                "Headquarters: Germany (Remote) ; Ireland (Remote); Netherlands (Remote) ; Portugal (Remote) ; "
                "Spain (Remote) ; United Kingdom (Remote)",
            ],
            remote_worldwide="Typeform is fully remote by design.",
        ),
        flags={"remote_country_restricted"},
        rejected=["remote_worldwide", "remote_country_restricted: alternativ: şirkətin özü haqqında"],
        conflicts=[], route="restricted", score=15,
    ),
    3: dict(
        key="synthetic-worldwide-vs-residents",
        answer=_answer(
            remote_worldwide="This role is remote and open to candidates worldwide.",
            candidate_location_restricted="Applicants must be residents of the United States or Canada.",
        ),
        flags={"remote_worldwide", "candidate_location_restricted"}, rejected=[],
        conflicts=["remote_vs_restriction"], route="restricted", score=15,
    ),
    4: dict(
        key="1729",
        answer=_answer(visa_support="We do sponsor visas!"),  # the model misses the condition
        flags={"visa_support", "visa_support_conditional"}, rejected=[], conflicts=[],
        route="visa_conditional", score=70,
        quotes={"visa_support_conditional": [
            "However, we aren't able to successfully sponsor visas for every role and every candidate."]},
    ),
    5: dict(
        key="961",
        answer=_answer(
            relocation="Relocation support to Auckland, New Zealand.",
            remote_region_includes_az="Remote work from time zones between GMT+4 - GMT+12.",
        ),
        flags={"relocation"}, rejected=["remote_region_includes_az"], conflicts=[], route="relocation", score=60,
    ),
    6: dict(
        key="203",
        answer=_answer(temporary_abroad_only="Work from anywhere in the world for 30 days per year"),
        flags=set(), rejected=[], conflicts=[], route="eligibility_reject", score=10,  # locked before AI
    ),
    7: dict(
        key="332#limit800",
        answer=_answer(remote_worldwide="Fingerprint is a globally dispersed, 100% remote company."),
        flags={"text_truncated"}, rejected=["remote_worldwide: şirkət"], conflicts=[], route="no_evidence", score=40,
    ),
    8: dict(
        key="960",
        answer=_answer(work_location_unspecified=[], no_sponsorship_stated="Visa Sponsorship: Not at this time",
                       remote_worldwide="Work from anywhere."),
        flags={"work_location_unspecified", "no_sponsorship_stated"}, rejected=["remote_worldwide: sitat elanda tapılmadı"],
        conflicts=[], route="no_evidence", score=40,  # no sponsorship alone is not a location rule
    ),
}


class ScenarioTest(unittest.TestCase):
    def test_every_scenario_is_in_the_eval_set(self):
        marked = {a["scenario"]["id"]: a["key"] for a in ADS.values() if a.get("scenario")}
        self.assertEqual(sorted(marked), list(range(1, 9)))
        for n, spec in SCENARIOS.items():
            self.assertEqual(marked[n], spec["key"], n)
        self.assertTrue(ADS["synthetic-worldwide-vs-residents"]["company"] == "SYNTHETIC EXAMPLE")

    def test_code_interpretation(self):
        for n, spec in SCENARIOS.items():
            ad = ADS[spec["key"]]
            with self.subTest(scenario=n, key=spec["key"]):
                res = replay_score(ad, spec["answer"])
                self.assertIsNotNone(res)
                self.assertEqual(res["route"], spec["route"])
                self.assertEqual(res["score"], spec["score"])
                self.assertEqual(_band(res["score"]), _band(spec["score"]))
                if spec["route"] == "eligibility_reject":
                    continue
                got = {name for name, on in res["flags"].items() if on}
                self.assertEqual(got, spec["flags"])
                self.assertEqual(res["conflicts"], spec["conflicts"])
                for want in spec["rejected"]:
                    self.assertTrue(any(note.startswith(want) for note in res["notes"]), (want, res["notes"]))
                for name, quotes in (spec.get("quotes") or {}).items():
                    self.assertEqual(res["quotes"][name], quotes)

    def test_expected_label_matches_band(self):
        for n, spec in SCENARIOS.items():
            ad = ADS[spec["key"]]
            band = _band(spec["score"])
            with self.subTest(scenario=n):
                if ad["expected"] == "eligible":
                    self.assertEqual(band, "approve")
                elif ad["expected"] == "manual":
                    self.assertEqual(band, "manual")
                else:
                    self.assertNotEqual(band, "approve")


if __name__ == "__main__":
    unittest.main()
