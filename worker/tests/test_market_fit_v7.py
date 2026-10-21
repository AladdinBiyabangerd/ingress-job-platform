"""market-fit v7+v8: quote validation (negation / length / stitching), conflicts, truncation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.fit_mapping import AI_FLAGS, FLAGS
from worker.market_fit import (
    OMITTED,
    PROMPT_VERSION,
    _JSON_SCHEMA,
    _SYSTEM,
    apply_eligibility_to_pending,
    build_user_prompt,
    check_quote,
    is_current_ai_reason,
    prompt_ad_text,
    verdict_from_ai,
)

BAND = 85


def _ai(reason="", **on):
    out = {name: {"value": False, "quotes": []} for name in AI_FLAGS}
    for name, quotes in on.items():
        if isinstance(quotes, str):
            quotes = [quotes] if quotes else []
        out[name] = {"value": True, "quotes": list(quotes)}
    out["reason"] = reason
    return out


def _v(text, truncated=False, **on):
    return verdict_from_ai(_ai(**on), ad_text=text, truncated=truncated)


class QuotePerFlagTest(unittest.TestCase):
    """For every positive flag: a supporting quote passes, a negated one is rejected."""

    CASES = {
        "remote_worldwide": (
            "This is a remote position available anywhere in the world!",
            "Unfortunately we cannot hire remotely anywhere in the world.",
        ),
        "remote_region_includes_az": (
            "Remote across EMEA.",
            "Remote work is not available anywhere in EMEA.",
        ),
        "remote_az_explicit": (
            "You can work remotely from Baku, Azerbaijan.",
            "We cannot employ people based in Azerbaijan.",
        ),
        "relocation": (
            "Relocation support to Auckland, New Zealand.",
            "We're not able to offer relocation for this role.",
        ),
        "visa_support": (
            "If you need a work permit to work in the Netherlands, we can sponsor it.",
            "We do not offer visa sponsorship.",
        ),
    }

    def test_positive_and_negative_examples(self):
        for flag, (good, bad) in self.CASES.items():
            with self.subTest(flag=flag):
                self.assertEqual(check_quote(flag, good, good), "")
                self.assertIn("inkar", check_quote(flag, bad, bad))
                v = _v(bad, **{flag: bad})
                self.assertFalse(v["flags"][flag])
                self.assertTrue(any(flag in n for n in v["validation_notes"]))
                self.assertIn("rədd edilən", v["reason"])

    def test_negation_variants_for_visa(self):
        for quote in (
            "Visa sponsorship: Not available for this role",
            "Visa sponsorship is not available for this position.",
            "We are unable to provide or take over visa sponsorship.",
            "We don't sponsor visas for this role.",
            "Candidates must be authorized to work without employer sponsorship.",
            "Visa Sponsorship: Not at this time",
        ):
            with self.subTest(quote=quote):
                self.assertNotEqual(check_quote("visa_support", quote, quote), "")

    def test_positive_phrases_with_negation_words_kept(self):
        for flag, quote in (
            ("remote_worldwide", "Work from anywhere, no matter where you live."),
            ("remote_worldwide", "We hire globally regardless of timezone."),
            ("remote_worldwide", "Fully remote, not limited to any country."),
            ("remote_worldwide", "Fully remote collaboration from anywhere in the world (except Russia)."),
        ):
            with self.subTest(quote=quote):
                self.assertEqual(check_quote(flag, quote, quote), "")

    def test_exclusions_touching_az_or_vague_rejected(self):
        for quote in (
            "Remote worldwide, excluding Azerbaijan and Armenia.",
            "Remote anywhere except sanctioned countries.",
            "Remote worldwide except a few countries where we cannot hire.",
        ):
            with self.subTest(quote=quote):
                self.assertIn("istisna", check_quote("remote_worldwide", quote, quote))

    def test_restriction_quotes_with_negation_are_fine(self):
        q = "We do not offer visa sponsorship."
        self.assertEqual(check_quote("no_sponsorship_stated", q, q), "")
        v = _v(q, no_sponsorship_stated=q)
        self.assertTrue(v["flags"]["no_sponsorship_stated"])
        self.assertEqual(v["quotes"]["no_sponsorship_stated"], [q])

    def test_length_and_stitching(self):
        long_q = "Remote anywhere in the world " + "and more words " * 12
        self.assertIn("160", check_quote("remote_worldwide", long_q, long_q))
        text = "Remote position. Lots of text. Available anywhere in the world."
        self.assertIn("yığılıb", check_quote("remote_worldwide", "Remote position … anywhere in the world", text))
        self.assertIn("tapılmadı", check_quote("remote_worldwide", "Remote position available anywhere in the world", text))

    def test_one_good_quote_is_enough(self):
        text = "We do not offer visa sponsorship for contractors. Visa sponsorship for employees."
        v = _v(text, relocation=[], visa_support=["We do not offer visa sponsorship for contractors.",
                                                  "Visa sponsorship for employees."])
        self.assertTrue(v["flags"]["visa_support"])
        self.assertEqual(v["quotes"]["visa_support"], ["Visa sponsorship for employees."])


class RealAdRulesTest(unittest.TestCase):
    """Code-side rules found by the live eval on real ads (eval_real_ads.json)."""

    def test_hedged_worldwide_rejected(self):
        for q in ("REMOTE ALMOST ANYWHERE IN THE WORLD", "can hire remotely in most countries",
                  "people can join our workforce from almost any country"):
            with self.subTest(q=q):
                self.assertIn("qeyd-şərtli", check_quote("remote_worldwide", q, q))
        text = "REMOTE ALMOST ANYWHERE IN THE WORLD. Remote, anywhere with reasonable timezone overlap."
        v = _v(text, remote_worldwide=["REMOTE ALMOST ANYWHERE IN THE WORLD",
                                       "Remote, anywhere with reasonable timezone overlap"])
        self.assertFalse(v["flags"]["remote_worldwide"])
        self.assertLess(v["confidence"], BAND)

    def test_region_must_clearly_include_az(self):
        bad = "We're especially interested in candidates located in Eastern European or Central Asian regions."
        self.assertIn("region", check_quote("remote_region_includes_az", bad, bad))
        for good in ("Remote across EMEA.", "Remote within the South Caucasus.", "Remote for CIS-based engineers."):
            with self.subTest(q=good):
                self.assertEqual(check_quote("remote_region_includes_az", good, good), "")
        # v8: a time-zone range or UTC offset alone is not geographic evidence
        for tz in ("Remote work from time zones between GMT+4 - GMT+12.", "Remote, between UTC-4 and UTC+4",
                   "Remote with 4 hours overlap with GMT+4"):
            with self.subTest(tz=tz):
                self.assertNotEqual(check_quote("remote_region_includes_az", tz, tz), "")
        self.assertNotEqual(check_quote("remote_region_includes_az", "Remote (CET ±2h)", "Remote (CET ±2h)"), "")

    def test_based_in_or_relocate_is_not_a_restriction(self):
        q = "Based in Munich or open to relocate - we support relocation and visa sponsorship"
        v = _v(q, relocation=q, visa_support=q, candidate_location_restricted=q)
        self.assertFalse(v["flags"]["candidate_location_restricted"])
        self.assertEqual(v["route"], "relocation+visa_support")

    def test_long_quote_falls_back_to_one_sentence_or_clause(self):
        text = ("We hire globally. We believe you can do your best work from anywhere. There are no offices, "
                "but we provide a WeWork membership or co-working allowance you can use anywhere in the world.")
        v = _v(text, remote_worldwide=text)
        self.assertTrue(v["flags"]["remote_worldwide"])
        self.assertLessEqual(len(v["quotes"]["remote_worldwide"][0]), 160)
        long_one = ("We can provide a relocation package, including moving assistance, temporary accommodation, "
                    "and full support to ensure a smooth transition to your new environment and city.")
        v = _v(long_one, relocation=long_one)
        self.assertTrue(v["flags"]["relocation"])
        self.assertTrue(v["quotes"]["relocation"][0].startswith("We can provide a relocation package"))


class ConflictTest(unittest.TestCase):
    def test_worldwide_vs_us_canada_only(self):
        text = "Remote worldwide. This role is open to US and Canada residents only."
        v = _v(text, remote_worldwide="Remote worldwide.",
               candidate_location_restricted="This role is open to US and Canada residents only.")
        self.assertEqual(v["confidence"], 15)
        self.assertTrue(v["conflict"])
        self.assertIn("ziddiyyətli", v["reason"])
        self.assertFalse(v["remote"])

    def test_truncated_conflict_below_band(self):
        text = "Remote worldwide. Remote within the EU only."
        v = _v(text, truncated=True, remote_worldwide="Remote worldwide.",
               remote_country_restricted="Remote within the EU only.")
        self.assertLess(v["confidence"], BAND)
        self.assertTrue(v["flags"]["text_truncated"])

    def test_truncated_clean_worldwide_below_band(self):
        v = _v("Remote worldwide.", truncated=True, remote_worldwide="Remote worldwide.")
        self.assertEqual(v["confidence"], 84)

    def test_code_truncation_wins_over_ai(self):
        data = _ai(remote_worldwide="Remote worldwide.")
        data["text_truncated"] = {"value": True, "quotes": []}  # AI claim ignored
        v = verdict_from_ai(data, ad_text="Remote worldwide.", truncated=False)
        self.assertFalse(v["flags"]["text_truncated"])
        self.assertEqual(v["confidence"], 90)

    def test_no_sponsorship_with_az_explicit_still_high(self):
        text = "Remote from Azerbaijan, Georgia or Turkey. We do not sponsor visas."
        v = _v(text, remote_az_explicit="Remote from Azerbaijan, Georgia or Turkey.",
               no_sponsorship_stated="We do not sponsor visas.")
        self.assertEqual(v["confidence"], 95)
        self.assertTrue(v["suitable"])
        self.assertFalse(v["visa_support"])

    def test_onsite_work_auth_keeps_relocation_route(self):
        text = "Relocation package to Berlin. Applicants must have the right to work in Germany."
        v = _v(text, relocation="Relocation package to Berlin.",
               work_authorization_required="Applicants must have the right to work in Germany.")
        self.assertEqual(v["confidence"], 70)
        self.assertEqual(v["route"], "relocation")

    def test_eu_residents_kill_relocation_and_visa(self):
        text = ("We're open to candidates who currently live in the EU and are willing to relocate. "
                "If you need a work permit to work in the Netherlands, we can sponsor it. "
                "If you're moving to the Netherlands, we offer a relocation package.")
        v = _v(text, relocation="If you're moving to the Netherlands, we offer a relocation package.",
               visa_support="If you need a work permit to work in the Netherlands, we can sponsor it.",
               candidate_location_restricted="We're open to candidates who currently live in the EU")
        self.assertEqual(v["confidence"], 15)
        self.assertTrue(v["conflict"])

    def test_legacy_v6_answer(self):
        data = {"remote_worldwide": {"value": True, "quote": "Remote worldwide."},
                "country_restricted": {"value": True, "quote": "US only."}, "reason": ""}
        v = verdict_from_ai(data, ad_text="Remote worldwide. US only.")
        self.assertEqual(v["confidence"], 15)
        self.assertTrue(v["flags"]["remote_country_restricted"])


class PromptTest(unittest.TestCase):
    def test_schema_and_prompt(self):
        self.assertEqual(PROMPT_VERSION, "market-fit-v8")
        self.assertIn("text_truncated", _JSON_SCHEMA["properties"])
        self.assertIn("work_location_unspecified", _JSON_SCHEMA["properties"])
        self.assertEqual(_JSON_SCHEMA["properties"]["relocation"]["properties"]["quotes"]["type"], "array")
        self.assertNotIn("text_truncated_or_missing_location", _SYSTEM)
        self.assertNotIn("country_restricted:", _SYSTEM.replace("remote_country_restricted:", ""))
        self.assertIn("Evidence extraction and conflict handling", _SYSTEM)
        for i in range(1, 11):
            self.assertIn(f"\n{i}. ", _SYSTEM)
        self.assertNotIn("EMEA, Europe + Caucasus", _SYSTEM)
        for name in AI_FLAGS:
            self.assertIn(f"- {name}:", _SYSTEM)
        self.assertEqual(set(FLAGS), set(AI_FLAGS))

    def test_truncation_keeps_exclusion_paragraphs(self):
        filler = "\n\n".join(f"Paragraph {i} about the product roadmap and team rituals." * 5 for i in range(400))
        text = ("Intro.\n\nRemote worldwide for this role.\n\n" + filler +
                "\n\nCandidates based in Azerbaijan or Iran cannot be hired.\n\n" + filler + "\n\nEnd.")
        body, truncated = prompt_ad_text(text, limit=4000)
        self.assertTrue(truncated)
        self.assertIn("cannot be hired", body)
        self.assertIn(OMITTED, body)
        self.assertIn("TRUNCATED", build_user_prompt(title="T", company="C", place="", text=text * 3))


class WorldwideExceptTest(unittest.TestCase):
    def test_worldwide_except_named_country_is_not_a_country_restriction(self):
        text = "Location: Remote, worldwide (except Russia). Fully remote collaboration."
        v = _v(text, remote_worldwide="Location: Remote, worldwide (except Russia)",
               remote_country_restricted="Location: Remote, worldwide (except Russia)")
        self.assertFalse(v["flags"]["remote_country_restricted"])
        self.assertEqual(v["ai_score"], 90)

    def test_worldwide_except_azerbaijan_stays_restricted(self):
        text = "Remote worldwide except Azerbaijan and Iran."
        v = _v(text, remote_worldwide="Remote worldwide except Azerbaijan and Iran.",
               remote_country_restricted="Remote worldwide except Azerbaijan and Iran.")
        self.assertTrue(v["flags"]["remote_country_restricted"])
        self.assertLess(v["ai_score"], 85)


class FitDetailTest(unittest.TestCase):
    def test_detail_for_popover_is_stored(self):
        import json

        from worker.market_fit import fit_detail, store_fit_detail

        text = "Remote worldwide. We do not offer visa sponsorship."
        v = _v(text, remote_worldwide="Remote worldwide.", visa_support="We do not offer visa sponsorship.",
               no_sponsorship_stated="We do not offer visa sponsorship.")
        v["eligibility_cap"] = 100
        d = fit_detail(v)
        self.assertEqual(d["prompt_version"], PROMPT_VERSION)
        self.assertEqual(d["score"], 90)
        self.assertEqual(d["route"], "remote_worldwide")
        names = [f["name"] for f in d["flags"]]
        self.assertEqual(names, ["remote_worldwide", "no_sponsorship_stated"])
        self.assertEqual(d["flags"][0]["label"], "istənilən ölkədən remote")
        self.assertTrue(any("visa_support" in n for n in d["notes"]))
        self.assertTrue(d["checked_at"])
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        store.upsert({"title": "Backend", "company": "Acme", "city": "", "text": text,
                      "source_url": "https://example.com/d", "source_name": "test"})
        job_id = int(store.conn.execute("SELECT MAX(id) FROM jobs").fetchone()[0])
        store_fit_detail(store.conn, job_id, v)
        raw = store.conn.execute("SELECT market_fit_detail FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
        self.assertEqual(json.loads(raw)["route"], "remote_worldwide")


class ResetOldPromptTest(unittest.TestCase):
    def test_v6_ai_rows_reset_v7_kept(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        ids = []
        for n, reason in enumerate((
            "AI: 90% AI-nın bəli/xeyr yoxlamalarından hesablanıb · remote_worldwide",
            f"AI: 90% ({PROMPT_VERSION}) AI-nın bəli/xeyr yoxlamalarından hesablanıb · remote_worldwide",
        )):
            store.upsert({
                "title": f"Backend {n}", "company": f"Acme {n}", "city": "Worldwide",
                "text": f"Location: Remote, accepting worldwide candidates. Team {n}.",
                "source_url": f"https://example.com/{n}", "source_name": "test", "remote": True,
                "rule_confidence": 70, "ai_confidence": 90, "market_fit_reason": reason,
            })
            ids.append(int(store.conn.execute("SELECT MAX(id) FROM jobs").fetchone()[0]))
        self.assertFalse(is_current_ai_reason("AI: 90% AI-nın"))
        stats = apply_eligibility_to_pending(store.conn, reset_ai=True)
        self.assertEqual(stats["ai_reset"], 1)
        rows = {r["id"]: r["ai_confidence"] for r in store.conn.execute("SELECT id, ai_confidence FROM jobs")}
        self.assertIsNone(rows[ids[0]])
        self.assertEqual(rows[ids[1]], 90)


if __name__ == "__main__":
    unittest.main()
