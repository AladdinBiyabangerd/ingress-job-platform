"""market-fit-v9: country-restriction scope (time zones, HQ), conditional visa, truncation
authority (code vs AI hint), prompt / schema / example order = FLAGS."""

from __future__ import annotations

import json
import unittest

from worker.fit_mapping import AI_FLAGS, FLAGS, TRUNCATION_HINT, staff_percent, visa_strength
from worker.market_fit import (
    PROMPT_VERSION,
    _JSON_SCHEMA,
    _SYSTEM,
    check_quote,
    conditional_visa_sentence,
    fit_detail,
    prompt_ad_text,
    source_text_truncated,
    truncation_source,
    verdict_from_ai,
)

BAND = 85
ANTHROPIC = (
    "Visa sponsorship: We do sponsor visas! However, we aren't able to successfully sponsor visas for every role "
    "and every candidate. But if we make you an offer, we will make every reasonable effort to get you a visa."
)


def _ai(**on):
    out = {name: {"value": False, "quotes": []} for name in AI_FLAGS}
    for name, quotes in on.items():
        out[name] = {"value": True, "quotes": [quotes] if isinstance(quotes, str) else list(quotes)}
    out["reason"] = ""
    return out


def _v(text, truncated=False, **on):
    return verdict_from_ai(_ai(**on), ad_text=text, truncated=truncated)


class CountryRestrictionScopeTest(unittest.TestCase):
    def test_prompt_examples(self):
        self.assertNotIn('"US-based")', _SYSTEM)
        self.assertNotIn('"US-based", "LATAM"', _SYSTEM)
        for ex in ('"Remote within Germany"', '"Remote — US residents only"', '"Must be based in the EU"'):
            self.assertIn(ex, _SYSTEM)
        self.assertIn('not for a statement about the company itself ("US-based company", "headquartered in London")', _SYSTEM)

    def test_restriction_quotes_accepted(self):
        for q in ("Remote within Germany", "Remote — US residents only", "Must be based in the EU",
                  "Candidates must be located between UTC-5 and UTC-8.", "Only candidates in UTC-5..UTC-8",
                  "REMOTE (CET ±2h)"):
            with self.subTest(q=q):
                self.assertEqual(check_quote("remote_country_restricted", q, q), "")

    def test_overlap_hq_and_az_including_range_rejected(self):
        cases = {
            "You will need 4 hours overlap with CET.": "üst-üstə",
            "We are a US-based company building payroll tools.": "HQ",
            "We are headquartered in London.": "HQ",
            "Must be located between UTC+2 and UTC+6.": "UTC+4",
        }
        for q, word in cases.items():
            with self.subTest(q=q):
                self.assertIn(word, check_quote("remote_country_restricted", q, q))

    def test_hq_statement_does_not_block_worldwide(self):
        text = "We are a US-based company. This role is remote and open to candidates anywhere in the world."
        v = _v(text, remote_worldwide="This role is remote and open to candidates anywhere in the world.",
               remote_country_restricted="We are a US-based company.")
        self.assertFalse(v["flags"]["remote_country_restricted"])
        self.assertEqual(v["ai_score"], 90)
        self.assertTrue(any("HQ" in n for n in v["validation_notes"]))

    def test_overlap_does_not_block_worldwide(self):
        text = "Work from anywhere in the world. You will need 4 hours overlap with CET."
        v = _v(text, remote_worldwide="Work from anywhere in the world.",
               remote_country_restricted="You will need 4 hours overlap with CET.")
        self.assertFalse(v["flags"]["remote_country_restricted"])
        self.assertEqual(v["ai_score"], 90)

    def test_explicit_tz_restriction_blocks(self):
        text = "Fully remote, anywhere in the world. Candidates must be located between UTC-5 and UTC-8."
        v = _v(text, remote_worldwide="Fully remote, anywhere in the world.",
               remote_country_restricted="Candidates must be located between UTC-5 and UTC-8.")
        self.assertTrue(v["flags"]["remote_country_restricted"])
        self.assertEqual(v["ai_score"], 15)
        self.assertIn("remote_vs_restriction", v["conflicts"])

    def test_company_statement_is_not_worldwide(self):
        q = "Fingerprint is a globally dispersed, 100% remote company."
        self.assertIn("şirkət", check_quote("remote_worldwide", q, q))


class ConditionalVisaTest(unittest.TestCase):
    def test_mapping_strength(self):
        base = {name: False for name in FLAGS}
        strong = {**base, "relocation": True, "visa_support": True}
        weak = {**strong, "visa_support_conditional": True}
        self.assertEqual(staff_percent(strong), (88, "relocation+visa_support"))
        self.assertEqual(staff_percent(weak), (70, "relocation+visa_conditional"))
        self.assertEqual(staff_percent({**base, "visa_support": True, "visa_support_conditional": True}),
                         (70, "visa_conditional"))
        self.assertEqual(visa_strength(weak), "weak")
        self.assertEqual(visa_strength(strong), "strong")
        self.assertEqual(visa_strength({**base, "visa_support_conditional": True}), "")

    def test_weak_visa_never_reaches_band(self):
        for i in range(1 << len(FLAGS)):
            f = {name: bool(i >> k & 1) for k, name in enumerate(FLAGS)}
            if not f["visa_support_conditional"]:
                continue
            score, route = staff_percent(f)
            if score >= BAND:
                self.assertTrue(route.startswith("remote_"), (f, score, route))
            self.assertNotEqual(route, "relocation+visa_support")

    def test_code_finds_anthropic_condition_when_model_misses_it(self):
        self.assertEqual(
            conditional_visa_sentence(ANTHROPIC),
            "However, we aren't able to successfully sponsor visas for every role and every candidate.",
        )
        text = ANTHROPIC + " We offer relocation support to London."
        v = _v(text, visa_support="We do sponsor visas!", relocation="We offer relocation support to London.")
        self.assertTrue(v["flags"]["visa_support_conditional"])
        self.assertEqual(v["quotes"]["visa_support_conditional"],
                         ["However, we aren't able to successfully sponsor visas for every role and every candidate."])
        self.assertEqual((v["ai_score"], v["route"]), (70, "relocation+visa_conditional"))
        self.assertEqual(v["visa_strength"], "weak")
        self.assertIn("visa_support_conditional", v["reason"])
        names = [f["name"] for f in fit_detail(v)["flags"]]
        self.assertIn("visa_support_conditional", names)

    def test_model_conditional_quote_kept(self):
        text = "Relocation package to Lisbon. Visa sponsorship may be possible on a case by case basis."
        v = _v(text, relocation="Relocation package to Lisbon.",
               visa_support="Visa sponsorship may be possible on a case by case basis.",
               visa_support_conditional="Visa sponsorship may be possible on a case by case basis.")
        self.assertTrue(v["flags"]["visa_support_conditional"])
        self.assertEqual(v["ai_score"], 70)

    def test_unconditional_role_sponsorship_plus_relocation_is_88(self):
        text = "We provide full visa sponsorship and relocation support to Berlin for this role."
        q = "We provide full visa sponsorship and relocation support to Berlin for this role."
        v = _v(text, relocation=q, visa_support=q)
        self.assertFalse(v["flags"]["visa_support_conditional"])
        self.assertEqual((v["ai_score"], v["route"]), (88, "relocation+visa_support"))

    def test_conditional_without_visa_is_dropped(self):
        text = "Sponsorship is decided case by case."
        v = _v(text, visa_support_conditional=text)
        self.assertFalse(v["flags"]["visa_support_conditional"])

    def test_negations_are_not_conditions(self):
        for t in ("We do not sponsor visas.", "Visa sponsorship is not available.",
                  "We sponsor visas for all employees."):
            with self.subTest(t=t):
                self.assertEqual(conditional_visa_sentence(t), "")


class TruncationAuthorityTest(unittest.TestCase):
    def test_source_snippet_detection(self):
        self.assertTrue(source_text_truncated("Role: Sr. DevOps Engineer. Wants Platform-focused..."))
        self.assertTrue(source_text_truncated("...Hi, Role: DevOps Engineer. Location: Plano, TX"))
        self.assertFalse(source_text_truncated("7. 2 Extra Salaries Per Year\n8. And Much More..."))
        self.assertFalse(source_text_truncated("We hire. Great team."))
        text = "Senior engineer for our platform team, remote across Europe and the wider region with flexible..."
        self.assertEqual(truncation_source(text), "source_snippet")
        self.assertEqual(prompt_ad_text(text)[1], True)
        self.assertEqual(truncation_source("x" * 50, limit=10), "prompt_limit")

    def test_code_true_wins_over_ai_false(self):
        text = "Work from anywhere in the world."
        data = _ai(remote_worldwide=text)
        v = verdict_from_ai(data, ad_text=text, truncated=True, truncation_source="source_snippet")
        self.assertTrue(v["flags"]["text_truncated"])
        self.assertFalse(v["text_truncated_ai_hint"])
        self.assertEqual(v["ai_score"], 84)
        d = fit_detail(v)["text_truncated"]
        self.assertEqual(d, {"code": True, "ai_hint": False, "source": "source_snippet"})

    def test_ai_hint_alone_is_soft_capped(self):
        text = "Work from anywhere in the world."
        v = verdict_from_ai(_ai(remote_worldwide=text, text_truncated=[]), ad_text=text, truncated=False)
        self.assertFalse(v["flags"]["text_truncated"])
        self.assertTrue(v["text_truncated_ai_hint"])
        self.assertEqual(v["ai_score"], 84)
        self.assertTrue(any(n.startswith("text_truncated: AI") for n in v["validation_notes"]))
        self.assertEqual(fit_detail(v)["text_truncated"], {"code": False, "ai_hint": True, "source": ""})
        base = {name: False for name in FLAGS}
        self.assertEqual(staff_percent({**base, "remote_worldwide": True, TRUNCATION_HINT: True})[0], 84)

    def test_prompt_definition(self):
        self.assertIn("- text_truncated: a hint only.", _SYSTEM)
        self.assertIn("your false never overrides a cut the code knows about", _SYSTEM)


class OrderTest(unittest.TestCase):
    def test_version(self):
        self.assertEqual(PROMPT_VERSION, "market-fit-v9")

    def test_flags_order_everywhere(self):
        self.assertEqual(FLAGS[0], "remote_worldwide")
        defs = [line[2:].split(":", 1)[0] for line in _SYSTEM.splitlines()
                if line.startswith("- ") and line[2:].split(":", 1)[0] in FLAGS]
        self.assertEqual(defs, list(FLAGS))
        start = _SYSTEM.index("\n{\n")
        example = json.loads(_SYSTEM[start:_SYSTEM.index("\n}\n", start) + 2])
        self.assertEqual(list(example), [*FLAGS, "reason"])
        self.assertEqual(_JSON_SCHEMA["required"], [*FLAGS, "reason"])
        self.assertEqual(list(_JSON_SCHEMA["properties"]), [*FLAGS, "reason"])
        self.assertIn("exactly these keys in this order: " + ", ".join([*FLAGS, "reason"]) + ".", _SYSTEM)


if __name__ == "__main__":
    unittest.main()


class CompanyStatementRoleBenefitTest(unittest.TestCase):
    def test_role_benefit_mentioning_office_is_not_company_statement(self):
        from worker.market_fit import _company_statement_only
        self.assertFalse(_company_statement_only(
            "Opportunity to work anywhere in the world (remote work or Lisbon office)"))
        self.assertTrue(_company_statement_only("Fingerprint is a globally dispersed, 100% remote company."))

