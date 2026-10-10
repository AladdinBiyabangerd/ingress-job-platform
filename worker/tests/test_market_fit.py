import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.ai_gateway.gateway import GatewayResult
from worker.db import Store
from worker.market_fit import (
    clarify_market_fit,
    has_clear_market_signal,
    is_rejected,
    mark_rejected,
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
        }
        with patch("worker.runner.clarify_market_fit", return_value=verdict):
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
        }
        with patch("worker.runner.clarify_market_fit", return_value=verdict):
            out = finish_item(self.conn, item)
        self.assertIsNotNone(out)
        self.assertTrue(out["relocation"])
        self.assertFalse(is_rejected(self.store.conn, url))

    def test_clarify_uses_complete_json(self):
        result = GatewayResult(ok=True, prompt_version="market-fit-v1", model="x")
        result.data = {
            "suitable": True,
            "remote": True,
            "relocation": False,
            "visa_support": False,
            "reason": "worldwide remote",
        }
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
        self.assertTrue(out["suitable"])
        self.assertTrue(out["remote"])


if __name__ == "__main__":
    unittest.main()
