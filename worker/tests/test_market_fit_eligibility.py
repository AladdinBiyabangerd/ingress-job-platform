"""Azerbaijan eligibility caps for the staff-queue % (real public fixtures, see fixtures/market_fit)."""

from __future__ import annotations

import html
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from worker.connectors.apis import WorkableAggregatorConnector
from worker.db import Store
from worker.eligibility import APPROVE_BAND, RULE_MAX, assess, place_from_source_url, summary
from worker.market_fit import (
    apply_eligibility_to_pending,
    build_user_prompt,
    is_rejected,
    prompt_ad_text,
    score_pending_without_ai,
    verdict_from_ai,
)
from worker.runner import finish_item

FX = Path(__file__).resolve().parent / "fixtures" / "market_fit"
EMP_TEXT = (FX / "emerchantpay_senior_java.txt").read_text(encoding="utf-8")
JB_TEXT = (FX / "jetbrains_qa_build_tools.txt").read_text(encoding="utf-8")
EMP_URL = (
    "https://jobs.workable.com/view/wVHpqJy8KCCPuKqZnvEGay/"
    "remote-senior-java-developer-in-sofia-at-emerchantpay"
)


def _workable_rows(name: str) -> list[dict]:
    return json.loads((FX / name).read_text(encoding="utf-8"))["jobs"]


def _workable_text(job: dict) -> str:
    raw = " ".join(str(job.get(k) or "") for k in ("description", "requirementsSection", "benefitsSection"))
    return html.unescape(re.sub(r"<[^>]+>", " ", raw))


class _Conn:
    store = None
    remote_default = False
    relocation_default = False
    require_remote_or_relocation = True
    credit_note = ""
    name = "Workable jobs"


class EmerchantpayTest(unittest.TestCase):
    """Job 2530: Workable 'remote' row pinned to Sofia, Bulgaria; text has no remote/relocation line."""

    def test_slug_place(self):
        self.assertEqual(place_from_source_url(EMP_URL), "sofia")

    def test_bulgaria_only_remote_is_locked(self):
        e = assess("Senior Java Developer", "Remote", EMP_TEXT, source_remote=True, source_url=EMP_URL)
        self.assertEqual(e["works_from_az"], "no")
        self.assertEqual(e["remote_scope"], "country_locked")
        self.assertLessEqual(e["cap"], 10)
        line = summary(e)
        self.assertIn("Bolqarıstan", line)
        self.assertIn("UIC 175117520", line)

    def test_workable_row_country(self):
        job = [j for j in _workable_rows("workable_country_locked.json") if "merchant" in j["company"]["title"]][0]
        e = assess(job["title"], "Remote", _workable_text(job), countries=["Bulgaria"], source_remote=True)
        self.assertEqual(e["works_from_az"], "no")
        self.assertIn("Yalnız Bolqarıstan daxilində remote", summary(e))

    def test_without_location_pin_is_unclear_low(self):
        e = assess("Senior Java Developer", "Remote", EMP_TEXT, source_remote=True)
        self.assertEqual(e["works_from_az"], "unclear")
        self.assertLess(e["cap"], APPROVE_BAND)
        self.assertLessEqual(e["cap"], 40)
        self.assertIn("mənbə metadata", summary(e))
        self.assertIn("Yerli şirkət", summary(e))

    def test_finish_item_rejects_before_ai(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        conn = _Conn()
        conn.store = store
        item = {
            "title": "Senior Java Developer", "company": "emerchantpay", "city": "Remote",
            "text": EMP_TEXT, "source_url": EMP_URL, "remote": True, "relocation": None,
            "tags": [], "category": [], "geo_countries": ["Bulgaria"],
        }
        with patch("worker.acceptance.clarify_market_fit") as ai:
            self.assertIsNone(finish_item(conn, item))
        ai.assert_not_called()
        self.assertTrue(is_rejected(store.conn, EMP_URL))
        reason = store.conn.execute(
            "SELECT reason FROM crawl_rejects WHERE source_url = ?", (EMP_URL,)
        ).fetchone()[0]
        self.assertIn("Bolqarıstan", reason)


class JetBrainsTest(unittest.TestCase):
    """Flexible location + 30 days abroad + relocation support with no target country."""

    def test_pasted_text(self):
        e = assess("QA Automation Engineer (IntelliJ IDEA Java Build Tools)", "", JB_TEXT)
        self.assertEqual(e["remote_scope"], "home_country_hybrid")
        self.assertIn(e["works_from_az"], ("no", "unclear"))
        self.assertEqual(e["relocation"], "yes")
        self.assertEqual(e["relocation_target"], "")
        self.assertEqual(e["visa"], "no")
        self.assertLess(e["cap"], APPROVE_BAND)
        line = summary(e)
        self.assertIn("30 days per year", line)
        self.assertIn("hədəf ölkə", line)
        self.assertIn("yoxlayın", line)

    def test_greenhouse_offices(self):
        job = json.loads((FX / "greenhouse_jetbrains_4777935101.json").read_text(encoding="utf-8"))["job"]
        body = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape(job["content"])))
        e = assess(job["title"], job["location"]["name"], body)
        self.assertEqual(e["relocation"], "yes")
        self.assertIn("Berlin", e["relocation_target"])
        self.assertLess(e["cap"], APPROVE_BAND)

    def test_rule_score_capped(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        conn = _Conn()
        conn.name = "Greenhouse boards"
        conn.require_remote_or_relocation = False
        conn.store = store
        item = {
            "title": "QA Automation Engineer (IntelliJ IDEA Java Build Tools)", "company": "JetBrains",
            "city": "", "text": JB_TEXT, "source_url": "https://job-boards.eu.greenhouse.io/jetbrains/jobs/4777935101",
            "remote": None, "relocation": None, "tags": [], "category": [],
        }
        out = finish_item(conn, item)
        if out is not None:  # kept as a relocation ad: never in the approve band
            self.assertLess(out["rule_confidence"] or 0, APPROVE_BAND)
            self.assertIn("Relocation", out["market_fit_reason"])


class WorkableRowsTest(unittest.TestCase):
    def test_country_locked_rows(self):
        for name in ("workable_country_locked.json", "workable_anywhere_locked.json"):
            for job in _workable_rows(name):
                e = assess(job["title"], "Remote", _workable_text(job),
                           countries=[job["location"].get("countryName")], source_remote=True)
                self.assertEqual(e["works_from_az"], "no", job["company"]["title"])
                self.assertLess(e["cap"], APPROVE_BAND)

    def test_anywhere_in_country_is_a_lock(self):
        houst = [j for j in _workable_rows("workable_anywhere_locked.json") if j["company"]["title"] == "Houst"][0]
        e = assess(houst["title"], "Remote", _workable_text(houst))
        self.assertIn("Gürcüstan", summary(e))
        funnel = [j for j in _workable_rows("workable_anywhere_locked.json") if j["company"]["title"] == "Funnel Leasing"][0]
        self.assertEqual(assess(funnel["title"], "Remote", _workable_text(funnel))["works_from_az"], "no")

    def test_worldwide_row_open(self):
        job = _workable_rows("workable_worldwide_open.json")[0]
        e = assess(job["title"], "Remote", _workable_text(job), countries=[job["location"].get("countryName")])
        self.assertEqual(e["works_from_az"], "yes")
        self.assertEqual(e["cap"], 100)

    def test_connector_keeps_countries(self):
        rows = _workable_rows("workable_anywhere_locked.json")
        client = MagicMock()
        client.get_json.return_value = {"jobs": rows}
        store = MagicMock()
        store.has_source_url.return_value = False
        conn = WorkableAggregatorConnector(client, store)
        conn.queries = (("software engineer", "&workplace=remote"),)
        items = {i["company"]: i for i in conn.feed_items()}
        self.assertEqual(items["Triptease"]["geo_countries"], ["Portugal", "Spain", "United Kingdom"])
        self.assertEqual(items["Houst"]["city"], "Remote")


def _ai(reason="", **on):
    from worker.fit_mapping import FLAGS

    out = {name: {"value": False, "quotes": []} for name in FLAGS if name != "text_truncated"}
    for name, quote in on.items():
        out[name] = {"value": True, "quotes": [quote] if quote else []}
    out["reason"] = reason
    return out


class AiVerdictTest(unittest.TestCase):
    """The AI returns flags + quotes only; the % comes from worker.fit_mapping."""

    def test_emerchantpay_expected_answer_below_band(self):
        v = verdict_from_ai(_ai(
            "Remote yeri göstərilməyib; Bolqarıstan şirkəti; Azərbaycandan iş təsdiqlənmir.",
            work_location_unspecified="",
        ), ad_text=EMP_TEXT)
        self.assertEqual(v["confidence"], 40)
        self.assertTrue(v["unclear"])

    def test_emerchantpay_hallucinated_remote_is_dropped(self):
        v = verdict_from_ai(_ai(remote_worldwide="Fully remote, work from anywhere in the world."), ad_text=EMP_TEXT)
        self.assertFalse(v["flags"]["remote_worldwide"])
        self.assertLess(v["confidence"], 85)
        self.assertIn("remote_worldwide", v["reason"])  # listed as dropped

    def test_jetbrains_expected_answer_below_band(self):
        reloc = "Relocation support. We help make your move as smooth and stress-free as possible."
        abroad = "Spend up to 30 days per year working remotely from abroad."
        for quote in (reloc, abroad):
            self.assertTrue(_norm_in(quote, JB_TEXT), quote)
        v = verdict_from_ai(_ai(
            "Yalnız ofis/ev, ildə 30 gün xaricdən; relocation var, hədəf ölkə yazılmayıb.",
            relocation=reloc, temporary_abroad_only=abroad,
        ), ad_text=JB_TEXT)
        self.assertEqual(v["confidence"], 70)
        self.assertTrue(v["suitable"])
        self.assertIn("relocation", v["reason"])
        self.assertIn("temporary_abroad_only", v["reason"])

    def test_jetbrains_worldwide_claim_overridden_by_restriction(self):
        v = verdict_from_ai(_ai(
            remote_worldwide="Flexible work location",
            temporary_abroad_only="Spend up to 30 days per year working remotely from abroad.",
        ), ad_text="Flexible work location. Spend up to 30 days per year working remotely from abroad.")
        self.assertEqual(v["confidence"], 15)

    def test_open_remote_with_quote_reaches_band(self):
        text = "Location: Remote, accepting worldwide candidates."
        v = verdict_from_ai(_ai(remote_worldwide="Remote, accepting worldwide candidates"), ad_text=text)
        self.assertEqual(v["confidence"], 90)

    def test_positive_without_quote_ignored(self):
        v = verdict_from_ai(_ai(remote_az_explicit=""), ad_text="anything")
        self.assertEqual(v["confidence"], 40)


def _norm_in(quote: str, text: str) -> bool:
    from worker.market_fit import _quote_in_ad

    return _quote_in_ad(quote, text)


class PromptTest(unittest.TestCase):
    def test_full_text_and_meta_label(self):
        user = build_user_prompt(title="T", company="C", place="Remote", text=JB_TEXT,
                                 source_meta="remote_flag=True; countries=Bulgaria")
        self.assertIn("Ad text: complete as provided by the source.", user)
        self.assertIn("Source metadata (clue, may be wrong): remote_flag=True; countries=Bulgaria", user)
        self.assertIn("Relocation support", user)

    def test_truncation_keeps_eligibility_paragraphs(self):
        filler = "\n\n".join(f"Paragraph {i} about the product roadmap and team rituals." * 5 for i in range(400))
        text = "Intro.\n\n" + filler + "\n\nRelocation support to Berlin, Germany.\n\nVisa sponsorship available."
        body, truncated = prompt_ad_text(text, limit=4000)
        self.assertTrue(truncated)
        self.assertIn("Relocation support to Berlin", body)
        self.assertIn("Visa sponsorship available", body)
        self.assertIn("[… omitted …]", body)
        user = build_user_prompt(title="T", company="C", place="", text=text)
        self.assertNotIn("TRUNCATED", build_user_prompt(title="T", company="C", place="", text="short"))
        self.assertIn("TRUNCATED", user)


class PendingRescoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _add(self, url, *, text, rule, ai, reason):
        self.store.upsert({
            "title": "Senior Java Developer", "company": "emerchantpay", "city": "Remote", "text": text,
            "source_url": url, "source_name": "Workable jobs", "remote": True,
            "rule_confidence": rule, "ai_confidence": ai, "market_fit_reason": reason,
        })
        return int(self.store.conn.execute("SELECT MAX(id) FROM jobs").fetchone()[0])

    def test_rescore_caps_and_explains(self):
        job_id = self._add(EMP_URL, text=EMP_TEXT, rule=95, ai=88, reason="open remote place (worldwide/EMEA)")
        dry = apply_eligibility_to_pending(self.store.conn, dry_run=True)
        self.assertEqual(dry["changed"], 1)
        row = self.store.conn.execute("SELECT rule_confidence FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(row[0], 95)  # dry run writes nothing
        stats = apply_eligibility_to_pending(self.store.conn)
        self.assertEqual(stats["locked"], 1)
        row = self.store.conn.execute(
            "SELECT status, rule_confidence, ai_confidence, market_fit_reason FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["rule_confidence"], 10)
        self.assertEqual(row["ai_confidence"], 10)
        self.assertTrue(row["market_fit_reason"].startswith("Qayda: "))
        self.assertIn("Bolqarıstan", row["market_fit_reason"])
        # Idempotent.
        self.assertEqual(apply_eligibility_to_pending(self.store.conn)["changed"], 0)

    def test_rule_scores_capped_and_old_ai_reset(self):
        job_id = self._add("https://example.com/open", text="Location: Remote, accepting worldwide candidates.",
                           rule=95, ai=91, reason="worldwide remote (v4)")
        apply_eligibility_to_pending(self.store.conn, reset_ai=True)
        row = self.store.conn.execute(
            "SELECT rule_confidence, ai_confidence FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        self.assertEqual(row["rule_confidence"], RULE_MAX)
        self.assertIsNone(row["ai_confidence"])

    def test_locked_rows_not_sent_to_ai(self):
        self._add(EMP_URL, text=EMP_TEXT, rule=95, ai=None, reason="x")
        apply_eligibility_to_pending(self.store.conn)
        with patch("worker.market_fit.feature_on", return_value=True), patch(
            "worker.market_fit.clarify_market_fit"
        ) as ai:
            stats = score_pending_without_ai(self.store.conn, limit=10)
        ai.assert_not_called()
        self.assertEqual(stats["planned"], 0)


if __name__ == "__main__":
    unittest.main()
