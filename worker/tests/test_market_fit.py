import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway.gateway import GatewayResult
from worker.db import Store
from worker.market_fit import (
    auto_score_limit,
    clarify_market_fit,
    fit_score,
    has_clear_market_signal,
    is_rejected,
    mark_rejected,
    rule_fit_confidence,
    score_pending_without_ai,
)
from worker.runner import finish_item


class _Conn:
    store = None
    remote_default = False
    relocation_default = False
    require_remote_or_relocation = True
    credit_note = ""
    name = "Test"


class MarketFitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        self.conn = _Conn()
        self.conn.store = self.store

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_clear_signal_from_keywords(self):
        self.assertTrue(
            has_clear_market_signal(
                "Remote Backend",
                "Worldwide",
                "Fully remote role.",
                pre_remote=None,
                pre_relocation=None,
                remote_default=False,
                relocation_default=False,
            )
        )

    def test_tokyo_onsite_needs_ai(self):
        self.assertFalse(
            has_clear_market_signal(
                "Product Engineer",
                "Tokyo",
                "Build web products in our Tokyo office. 5+ years experience.",
                pre_remote=None,
                pre_relocation=None,
                remote_default=False,
                relocation_default=False,
            )
        )

    def test_reject_persists_and_skips_finish(self):
        url = "https://japan-dev.com/jobs/blued/product-engineer"
        mark_rejected(self.store.conn, url, "onsite tokyo", via_ai=True)
        self.assertTrue(is_rejected(self.store.conn, url))
        item = {
            "title": "Product Engineer",
            "company": "Blued",
            "city": "Tokyo",
            "text": "Build web products. 5+ years full-stack.",
            "source_url": url,
            "remote": None,
            "relocation": None,
            "tags": ["Python", "React"],
            "category": "Engineering",
        }
        self.assertIsNone(finish_item(self.conn, item))

    def test_ai_unsuitable_marks_reject(self):
        url = "https://japan-dev.com/jobs/blued/product-engineer-2"
        item = {
            "title": "Product Engineer",
            "company": "Blued",
            "city": "Tokyo",
            "text": "Build web products used by students. Office in Tokyo. Rails and React.",
            "source_url": url,
            "remote": None,
            "relocation": None,
            "tags": ["Ruby on Rails", "React", "TypeScript"],
            "category": "Engineering",
        }
        verdict = {
            "suitable": False,
            "remote": False,
            "relocation": False,
            "visa_support": False,
            "reason": "onsite Tokyo, no visa",
            "confidence": 88,
        }
        with patch("worker.acceptance.clarify_market_fit", return_value=verdict):
            self.assertIsNone(finish_item(self.conn, item))
        self.assertTrue(is_rejected(self.store.conn, url))

    def test_ai_suitable_keeps_relocation(self):
        url = "https://japan-dev.com/jobs/acme/visa-role"
        item = {
            "title": "Backend Engineer",
            "company": "Acme",
            "city": "Tokyo",
            "text": "Join our Tokyo team. We sponsor work visas for overseas engineers.",
            "source_url": url,
            "remote": None,
            "relocation": None,
            "tags": ["Python"],
            "category": "Engineering",
        }
        verdict = {
            "suitable": True,
            "remote": False,
            "relocation": True,
            "visa_support": True,
            "reason": "visa sponsorship",
            "confidence": 76,
        }
        with patch("worker.acceptance.rule_fit_confidence", return_value=None):
            with patch("worker.acceptance.clarify_market_fit", return_value=verdict):
                out = finish_item(self.conn, item)
        self.assertIsNotNone(out)
        self.assertTrue(out["relocation"])
        self.assertEqual(out["ai_confidence"], 76)
        self.assertIsNone(out["rule_confidence"])
        self.assertFalse(is_rejected(self.store.conn, url))

    def test_clear_signal_sets_rule_confidence(self):
        item = {
            "title": "Remote Backend Engineer",
            "company": "Acme",
            "city": "Worldwide",
            "text": "Fully remote role. Work from anywhere.",
            "source_url": "https://example.com/remote-backend",
            "remote": None,
            "relocation": None,
            "tags": ["Python"],
            "category": "Engineering",
        }
        out = finish_item(self.conn, item)
        self.assertIsNotNone(out)
        # Graded, and rules alone never reach the 85 approve band.
        self.assertGreaterEqual(out["rule_confidence"], 70)
        self.assertLessEqual(out["rule_confidence"], 80)
        self.assertIsNone(out["ai_confidence"])
        self.assertIn("open", (out.get("market_fit_reason") or "").lower())

    def test_rule_fit_grades_signal_strength(self):
        weak = rule_fit_confidence(
            "Backend Engineer",
            "Berlin",
            "Join our team. Nice benefits.",
            pre_remote=None,
            pre_relocation=None,
            remote_default=True,
            relocation_default=False,
        )
        mid = rule_fit_confidence(
            "Remote Backend Engineer",
            "Europe",
            "This is a remote role across our offices.",
            pre_remote=None,
            pre_relocation=None,
            remote_default=False,
            relocation_default=False,
        )
        strong = rule_fit_confidence(
            "Backend Engineer",
            "Remote - Worldwide",
            "Work from anywhere. Hiring globally.",
            pre_remote=None,
            pre_relocation=None,
            remote_default=False,
            relocation_default=False,
        )
        az = rule_fit_confidence(
            "Backend Engineer",
            "Remote",
            "Open to candidates in Azerbaijan and CIS.",
            pre_remote=True,
            pre_relocation=None,
            remote_default=False,
            relocation_default=False,
        )
        self.assertIsNotNone(weak)
        self.assertIsNotNone(mid)
        self.assertIsNotNone(strong)
        self.assertIsNotNone(az)
        self.assertLess(weak["confidence"], mid["confidence"])
        self.assertLessEqual(mid["confidence"], strong["confidence"])
        self.assertGreaterEqual(az["confidence"], strong["confidence"])
        self.assertLessEqual(az["confidence"], 100)
        # Not a binary 0/100 switch: weak board-default stays well below open-market.
        self.assertLessEqual(weak["confidence"], 70)
        self.assertGreaterEqual(strong["confidence"], 78)
        for row in (weak, mid, strong, az):
            self.assertLessEqual(row["confidence"], 80)

    def test_fit_score_unsuitable_never_looks_like_full_match(self):
        # Model "100% sure unsuitable" must not display as 100% rule-fit.
        self.assertEqual(fit_score(suitable=False, confidence=100), 0)
        self.assertLessEqual(fit_score(suitable=False, confidence=88), 35)
        self.assertEqual(fit_score(suitable=True, confidence=91), 91)

    @staticmethod
    def _flags(**on):
        from worker.fit_mapping import FLAGS

        out = {name: {"value": False, "quotes": []} for name in FLAGS if name != "text_truncated"}
        for name, quote in on.items():
            out[name] = {"value": True, "quotes": [quote]}
        return out

    def test_clarify_uses_complete_json(self):
        result = GatewayResult(ok=True, prompt_version="market-fit-v9", model="x")
        result.data = {**self._flags(remote_worldwide="Work from anywhere."), "reason": "İstənilən ölkədən remote."}
        with patch("worker.market_fit.feature_on", return_value=True):
            with patch("worker.market_fit.complete_json", return_value=result) as call:
                out = clarify_market_fit(
                    title="Engineer",
                    company="X",
                    place="Remote",
                    text="Work from anywhere.",
                    conn=self.store.conn,
                )
        call.assert_called_once()
        self.assertEqual(call.call_args.kwargs["prompt_version"], "market-fit-v9")
        self.assertNotIn("confidence", call.call_args.kwargs["schema"]["properties"])
        self.assertTrue(out["suitable"])
        self.assertTrue(out["remote"])
        self.assertEqual(out["confidence"], 90)  # computed by fit_mapping, not by the AI
        self.assertIn("remote_worldwide", out["reason"])
        self.assertIn("Work from anywhere.", out["reason"])

    def test_clarify_unsuitable_stores_low_fit(self):
        result = GatewayResult(ok=True, prompt_version="market-fit-v9", model="x")
        result.data = {
            **self._flags(candidate_location_restricted="US residency 3 of 5 years.", no_sponsorship_stated="No visa sponsorship."),
            "reason": "Yalnız ABŞ rezidentləri.",
        }
        with patch("worker.market_fit.feature_on", return_value=True):
            with patch("worker.market_fit.complete_json", return_value=result):
                out = clarify_market_fit(
                    title="Senior Test Engineer",
                    company="GDIT",
                    place="Remote",
                    text="US residency 3 of 5 years. No visa sponsorship.",
                    conn=self.store.conn,
                )
        self.assertFalse(out["suitable"])
        self.assertFalse(out["unclear"])
        self.assertEqual(out["confidence"], 15)

    def _pending_rule_only(self, *, url: str, title: str = "Remote Backend"):
        self.store.upsert(
            {
                "title": title,
                "company": "Acme",
                "city": "Worldwide",
                "text": "Fully remote. Work from anywhere.",
                "source_url": url,
                "source_name": "test",
                "remote": True,
                "rule_confidence": 90,
                "ai_confidence": None,
                "market_fit_reason": "open place",
            }
        )
        return int(self.store.conn.execute("SELECT id FROM jobs WHERE id = (SELECT MAX(id) FROM jobs)").fetchone()["id"])

    def test_score_pending_without_ai_fills_and_rejects(self):
        ok_id = self._pending_rule_only(url="https://example.com/ok")
        bad_id = self._pending_rule_only(url="https://example.com/bad", title="Remote US only")
        # Already scored — must be skipped.
        self.store.upsert(
            {
                "title": "Remote Backend",
                "company": "Acme",
                "city": "Worldwide",
                "text": "Fully remote.",
                "source_url": "https://example.com/scored",
                "source_name": "test",
                "remote": True,
                "rule_confidence": 90,
                "ai_confidence": 88,
                "market_fit_reason": "prior ai",
            }
        )

        def fake_clarify(*, title, company, place, text, conn, **_kw):
            if "US only" in title:
                return {
                    "suitable": False,
                    "remote": True,
                    "relocation": False,
                    "visa_support": False,
                    "reason": "US locked",
                    "confidence": 10,
                }
            return {
                "suitable": True,
                "remote": True,
                "relocation": False,
                "visa_support": False,
                "reason": "worldwide remote",
                "confidence": 91,
            }

        with patch("worker.market_fit.feature_on", return_value=True):
            with patch("worker.market_fit.clarify_market_fit", side_effect=fake_clarify):
                stats = score_pending_without_ai(self.store.conn, limit=10)

        self.assertEqual(stats["planned"], 2)
        self.assertEqual(stats["checked"], 2)
        self.assertEqual(stats["rejected"], 1)
        ok = self.store.conn.execute(
            "SELECT status, ai_confidence, rule_confidence FROM jobs WHERE id = ?",
            (ok_id,),
        ).fetchone()
        bad = self.store.conn.execute(
            "SELECT status, ai_confidence, rule_confidence FROM jobs WHERE id = ?",
            (bad_id,),
        ).fetchone()
        self.assertEqual(ok["status"], "pending")
        self.assertEqual(ok["ai_confidence"], 91)
        self.assertEqual(ok["rule_confidence"], 90)
        self.assertEqual(bad["status"], "rejected")
        self.assertEqual(bad["ai_confidence"], 10)
        self.assertIsNone(bad["rule_confidence"])

    def test_score_pending_without_ai_noop_when_off(self):
        self._pending_rule_only(url="https://example.com/off")
        with patch("worker.market_fit.feature_on", return_value=False):
            stats = score_pending_without_ai(self.store.conn, limit=10)
        self.assertEqual(stats["planned"], 0)
        row = self.store.conn.execute(
            "SELECT ai_confidence FROM jobs WHERE status = 'pending'"
        ).fetchone()
        self.assertIsNone(row["ai_confidence"])

    def test_auto_score_limit_env(self):
        with patch.dict("os.environ", {"AI_MARKET_FIT_AUTO_SCORE_LIMIT": "7"}):
            self.assertEqual(auto_score_limit(), 7)
        with patch.dict("os.environ", {"AI_MARKET_FIT_AUTO_SCORE_LIMIT": "999"}):
            self.assertEqual(auto_score_limit(), 200)


if __name__ == "__main__":
    unittest.main()
