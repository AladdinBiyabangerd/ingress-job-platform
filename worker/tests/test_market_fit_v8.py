"""market-fit-v8: no time-zone geography, candidate-location scope, surfaced conflicts,
per-flag quote relevance, full JSON example in the prompt."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from worker.eligibility import CAP_RELOC_UNCONFIRMED, assess
from worker.fit_mapping import AI_FLAGS, CONFLICTS_AZ, FLAGS, conflicts, staff_percent
from worker.market_fit import (
    OMITTED,
    PROMPT_VERSION,
    _JSON_SCHEMA,
    _SYSTEM,
    check_quote,
    checked_verdict,
    fit_detail,
    prompt_ad_text,
    verdict_from_ai,
)

BAND = 85


def _ai(reason="", **on):
    out = {name: {"value": False, "quotes": []} for name in AI_FLAGS}
    for name, quotes in on.items():
        out[name] = {"value": True, "quotes": [quotes] if isinstance(quotes, str) else list(quotes)}
    out["reason"] = reason
    return out


def _v(text, truncated=False, **on):
    return verdict_from_ai(_ai(**on), ad_text=text, truncated=truncated)


class TimeZoneIsNotGeographyTest(unittest.TestCase):
    def test_tz_range_is_not_region_including_az(self):
        text = "Remote work from time zones between GMT+4 - GMT+12."
        v = _v(text, remote_region_includes_az=text)
        self.assertFalse(v["flags"]["remote_region_includes_az"])
        self.assertEqual(v["ai_score"], 40)
        self.assertTrue(any("saat qurşağı" in n for n in v["validation_notes"]))

    def test_named_region_still_counts(self):
        text = "Fully remote across EMEA."
        self.assertEqual(_v(text, remote_region_includes_az=text)["ai_score"], 88)

    def test_eligibility_no_longer_opens_on_tz_range(self):
        for text in ("Remote work from time zones between GMT+4 - GMT+12.", "Remote, between UTC-4 and UTC+4."):
            with self.subTest(text=text):
                e = assess("Backend Engineer", "", text)
                self.assertNotEqual(e["remote_scope"], "region_incl_az")
                self.assertLess(e["cap"], BAND)

    def test_hire_globally_regardless_of_time_zones_is_worldwide(self):
        text = "We hire globally regardless of time zones. Fully remote."
        self.assertEqual(assess("Backend Engineer", "", text)["remote_scope"], "anywhere")
        self.assertEqual(_v(text, remote_worldwide="We hire globally regardless of time zones.")["ai_score"], 90)

    def test_prompt_route_a_and_region_definition(self):
        self.assertIn(
            "A. Remote from Azerbaijan: the ad explicitly allows Azerbaijan or Baku, allows work from anywhere in "
            "the world, or names a geographic region that clearly includes Azerbaijan. A time-zone overlap or UTC "
            "offset alone is not evidence of geographic eligibility.",
            _SYSTEM,
        )
        self.assertNotIn("(UTC+4)", _SYSTEM)
        self.assertIn("A time-zone range or UTC offset alone does not count.", _SYSTEM)


class CandidateLocationTest(unittest.TestCase):
    def test_prompt_definition(self):
        self.assertIn(
            "- candidate_location_restricted: the ad explicitly requires applicants to already reside in, be "
            "citizens or residents of, or have a specified history of residence in a named country or region that "
            "excludes Azerbaijan. Do not set this flag solely because the job is based in that country, or when the "
            "ad explicitly accepts applicants willing to relocate there as an alternative.",
            _SYSTEM,
        )

    def test_remote_germany_with_relocation_keeps_relocation_route(self):
        text = "Remote in Germany; relocation to Germany available."
        v = _v(text, remote_country_restricted="Remote in Germany", relocation="relocation to Germany available")
        self.assertTrue(v["flags"]["remote_country_restricted"])
        self.assertTrue(v["flags"]["relocation"])
        self.assertFalse(v["flags"]["candidate_location_restricted"])
        self.assertEqual((v["ai_score"], v["route"]), (70, "relocation"))
        fake = {**_ai(remote_country_restricted="Remote in Germany", relocation="relocation to Germany available")}
        with mock.patch("worker.market_fit.clarify_market_fit", return_value=verdict_from_ai(fake, ad_text=text)):
            cv = checked_verdict(title="Backend Engineer", company="Acme", place="", text=text, conn=None)
        self.assertEqual(cv["confidence"], CAP_RELOC_UNCONFIRMED)  # 70 capped by eligibility (60)
        self.assertTrue(cv["suitable"])

    def test_must_currently_reside_in_us_is_candidate_restricted(self):
        text = "Must currently reside in the US."
        self.assertEqual(check_quote("candidate_location_restricted", text, text), "")
        v = _v(text, candidate_location_restricted=text, relocation=[])
        self.assertTrue(v["flags"]["candidate_location_restricted"])
        self.assertEqual(v["ai_score"], 15)

    def test_us_office_worldwide_may_relocate_is_not_candidate_restricted(self):
        text = "US office; candidates worldwide may relocate."
        v = _v(text, candidate_location_restricted=text, relocation="candidates worldwide may relocate")
        self.assertFalse(v["flags"]["candidate_location_restricted"])
        self.assertTrue(v["flags"]["relocation"])
        self.assertEqual(v["ai_score"], 70)

    def test_job_based_in_country_is_not_candidate_restricted(self):
        text = "This position is based in our Berlin office."
        v = _v(text, candidate_location_restricted=text)
        self.assertFalse(v["flags"]["candidate_location_restricted"])

    def test_reside_or_willing_to_relocate_is_not_restricted(self):
        text = "Candidates must reside in Germany or be willing to relocate."
        v = _v(text, candidate_location_restricted=text, relocation=[])
        self.assertFalse(v["flags"]["candidate_location_restricted"])


class SurfacedConflictTest(unittest.TestCase):
    def test_visa_and_no_sponsorship_both_kept_and_shown(self):
        text = "We sponsor work visas for our Berlin office. Relocation to Berlin is supported. We do not sponsor visas for contractors."
        v = _v(
            text,
            visa_support="We sponsor work visas for our Berlin office.",
            relocation="Relocation to Berlin is supported.",
            no_sponsorship_stated="We do not sponsor visas for contractors.",
        )
        self.assertTrue(v["flags"]["visa_support"])
        self.assertTrue(v["flags"]["no_sponsorship_stated"])
        self.assertEqual(v["quotes"]["visa_support"], ["We sponsor work visas for our Berlin office."])
        self.assertEqual(v["quotes"]["no_sponsorship_stated"], ["We do not sponsor visas for contractors."])
        self.assertIn("visa_vs_no_sponsorship", v["conflicts"])
        self.assertIn(CONFLICTS_AZ["visa_vs_no_sponsorship"], v["reason"])
        self.assertLess(v["ai_score"], BAND)  # visa route not counted: relocation only
        self.assertEqual(v["route"], "relocation")
        d = fit_detail(v)
        self.assertIn("visa_vs_no_sponsorship", [c["key"] for c in d["conflicts"]])
        self.assertIn("visa_support", [f["name"] for f in d["flags"]])
        self.assertIn("no_sponsorship_stated", [f["name"] for f in d["flags"]])

    def test_visa_and_work_authorization_conflict(self):
        text = "Visa sponsorship available. You must be authorized to work in Canada."
        v = _v(text, visa_support="Visa sponsorship available.",
               work_authorization_required="You must be authorized to work in Canada.")
        self.assertTrue(v["flags"]["visa_support"])
        self.assertEqual(v["conflicts"], ["visa_vs_work_authorization"])
        self.assertLess(v["ai_score"], BAND)
        self.assertIn(CONFLICTS_AZ["visa_vs_work_authorization"], v["reason"])

    def test_conflict_never_reaches_band_without_independent_route(self):
        for i in range(1 << len(FLAGS)):
            f = {name: bool(i >> k & 1) for k, name in enumerate(FLAGS)}
            if not (f["visa_support"] and (f["no_sponsorship_stated"] or f["work_authorization_required"])):
                continue
            score, route = staff_percent(f)
            self.assertNotIn("visa_support", route)
            if score >= BAND:
                self.assertTrue(route.startswith("remote_"), (f, score, route))

    def test_remote_az_with_no_sponsorship_is_not_a_conflict(self):
        text = "Remote from Baku, Azerbaijan is fine. We do not sponsor visas."
        v = _v(text, remote_az_explicit="Remote from Baku, Azerbaijan is fine.",
               no_sponsorship_stated="We do not sponsor visas.")
        self.assertEqual(v["ai_score"], 95)
        self.assertEqual(conflicts(v["flags"]), [])


class QuoteValidationTest(unittest.TestCase):
    AD = (
        "Remote worldwide. Relocation package to Amsterdam. We sponsor work permits. "
        "We do not sponsor visas for interns. Must currently reside in the EU."
    )

    def test_quote_must_exist_in_ad(self):
        self.assertEqual(check_quote("relocation", "Relocation package to Lisbon.", self.AD), "sitat elanda tapılmadı")
        self.assertEqual(check_quote("relocation", "Relocation package to Amsterdam.", self.AD), "")

    def test_at_most_160_characters(self):
        long = "Remote worldwide " + "and more " * 20
        self.assertIn("160", check_quote("remote_worldwide", long, long))
        ok = "Remote worldwide " + "x" * (160 - 17)
        self.assertEqual(len(ok), 160)
        self.assertEqual(check_quote("remote_worldwide", ok, ok), "")

    def test_quote_must_be_about_its_flag(self):
        off_topic = {
            "visa_support": "Relocation package to Amsterdam.",
            "relocation": "We sponsor work permits.",
            "remote_worldwide": "We sponsor work permits.",
            "remote_az_explicit": "Remote worldwide.",
            "no_sponsorship_stated": "Relocation package to Amsterdam.",
            "candidate_location_restricted": "Relocation package to Amsterdam.",
        }
        for flag, quote in off_topic.items():
            with self.subTest(flag=flag):
                self.assertIn("aid deyil", check_quote(flag, quote, self.AD))
        on_topic = {
            "visa_support": "We sponsor work permits.",
            "relocation": "Relocation package to Amsterdam.",
            "remote_worldwide": "Remote worldwide.",
            "no_sponsorship_stated": "We do not sponsor visas for interns.",
            "candidate_location_restricted": "Must currently reside in the EU.",
        }
        for flag, quote in on_topic.items():
            with self.subTest(flag=flag):
                self.assertEqual(check_quote(flag, quote, self.AD), "")

    def test_relevance_on_real_phrasings(self):
        move = "Are you moving from abroad? We support you with your move to Germany, getting settled."
        self.assertEqual(check_quote("relocation", move, move), "")
        for bare in ("100% Remote", "Remote First Culture - We’re a 100% distributed team!", "Fully remote role."):
            with self.subTest(bare=bare):
                self.assertNotEqual(check_quote("remote_worldwide", bare, bare), "")
        q = "This is a full-time, fully remote position for candidates based in the US."
        self.assertEqual(check_quote("candidate_location_restricted", q, q), "")
        q = "We require that all candidates have an existing Right to Work in the UK at the time of application."
        self.assertIn("aid deyil", check_quote("candidate_location_restricted", q, q))  # work authorization, not residence
        self.assertEqual(check_quote("work_authorization_required", q, q), "")

    def test_off_topic_positive_quote_does_not_count(self):
        v = _v(self.AD, visa_support="Relocation package to Amsterdam.")
        self.assertFalse(v["flags"]["visa_support"])

    def test_negation_is_not_positive_evidence(self):
        q = "We do not sponsor visas."
        self.assertEqual(check_quote("no_sponsorship_stated", q, q), "")
        self.assertIn("inkar", check_quote("visa_support", q, q))
        v = _v(q, visa_support=q, no_sponsorship_stated=q)
        self.assertFalse(v["flags"]["visa_support"])
        self.assertTrue(v["flags"]["no_sponsorship_stated"])
        self.assertEqual(v["conflicts"], [])  # one negated sentence is not a real conflict

    def test_truncated_text_gives_no_inference_from_missing_parts(self):
        filler = "\n\n".join(f"Team ritual {i} description and product roadmap notes." * 6 for i in range(40))
        claim = "We hire people from anywhere in the world."
        text, truncated = prompt_ad_text(f"Backend Engineer at Acme.\n\n{filler}\n\n{claim}\n\n{filler}", limit=2000)
        self.assertTrue(truncated)
        self.assertIn(OMITTED, text)
        self.assertNotIn(claim, text)  # the claim sat in an omitted part
        self.assertEqual(check_quote("remote_worldwide", claim, text), "sitat elanda tapılmadı")
        v = verdict_from_ai(_ai(remote_worldwide=claim), ad_text=text, truncated=truncated)
        self.assertFalse(v["flags"]["remote_worldwide"])  # no inference from the missing part
        self.assertTrue(v["flags"]["text_truncated"])
        self.assertFalse(v["flags"]["work_location_unspecified"])  # separate question
        self.assertEqual(v["ai_score"], 40)
        v = verdict_from_ai(_ai(), ad_text=text, truncated=truncated)
        self.assertEqual(v["ai_score"], 40)  # missing text is unknown, not negative either

    def test_code_value_of_text_truncated_wins(self):
        text = "Remote worldwide."
        data = _ai(remote_worldwide=text, text_truncated=[])
        self.assertFalse(verdict_from_ai(data, ad_text=text, truncated=False)["flags"]["text_truncated"])
        data = _ai(remote_worldwide=text)
        self.assertTrue(verdict_from_ai(data, ad_text=text, truncated=True)["flags"]["text_truncated"])


class PromptSchemaV8Test(unittest.TestCase):
    def test_version(self):
        self.assertEqual(PROMPT_VERSION, "market-fit-v10")

    def test_full_json_example_in_prompt(self):
        start = _SYSTEM.index("\n{\n")
        end = _SYSTEM.index("\n}\n", start) + 2
        example = json.loads(_SYSTEM[start:end])
        self.assertEqual(list(example), [*FLAGS, "reason"])
        self.assertEqual(len(FLAGS), 13)
        for name in FLAGS:
            self.assertEqual(set(example[name]), {"value", "quotes"})
        self.assertRegex(example["reason"], "[əğıöüçş]")  # Azerbaijani
        self.assertEqual(set(_JSON_SCHEMA["required"]), {*FLAGS, "reason"})
        self.assertIn("- text_truncated:", _SYSTEM)
        self.assertIn("Separate from work_location_unspecified.", _SYSTEM)


if __name__ == "__main__":
    unittest.main()
