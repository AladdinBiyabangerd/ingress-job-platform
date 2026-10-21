"""rescore-eligibility --limit / --source: staged rollout of a new market-fit prompt."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.db import Store
from worker.market_fit import apply_eligibility_to_pending


class StagedRescoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        for i, src in enumerate(["Djinni", "Djinni", "Workable jobs", "Djinni"]):
            self.store.upsert({
                "title": f"Engineer {i}", "company": f"C{i}", "city": "Remote",
                "text": "Location: Remote, accepting worldwide candidates.",
                "source_url": f"https://example.com/{i}", "source_name": src, "remote": True,
                "rule_confidence": 70, "ai_confidence": 90, "market_fit_reason": "AI: 90% (market-fit-v8) old",
            })

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _ai(self):
        return [r[0] for r in self.store.conn.execute("SELECT ai_confidence FROM jobs ORDER BY id")]

    def test_limit_and_source(self):
        dry = apply_eligibility_to_pending(self.store.conn, dry_run=True, reset_ai=True, limit=2)
        self.assertEqual((dry["scanned"], dry["ai_reset"]), (2, 2))
        self.assertEqual(self._ai(), [90, 90, 90, 90])  # dry run writes nothing
        stats = apply_eligibility_to_pending(self.store.conn, reset_ai=True, source="Djinni", limit=2)
        self.assertEqual((stats["scanned"], stats["ai_reset"]), (2, 2))
        self.assertEqual(self._ai(), [None, None, 90, 90])
        stats = apply_eligibility_to_pending(self.store.conn, reset_ai=True, source="Workable jobs")
        self.assertEqual(stats["scanned"], 1)
        self.assertEqual(self._ai(), [None, None, None, 90])

    def test_cli_parses_limit_and_source(self):
        from worker import runner

        with patch("worker.runner.Store", return_value=self.store), patch.object(self.store, "close"), patch(
            "worker.runner.apply_eligibility_to_pending", return_value={"scanned": 0, "changes": []}
        ) as apply:
            self.assertEqual(
                runner._rescore_eligibility(["--dry-run", "--reset-ai", "--limit", "5", "--source", "Djinni"]), 0
            )
        apply.assert_called_once_with(self.store.conn, dry_run=True, reset_ai=True, limit=5, source="Djinni")
        self.assertEqual(runner._rescore_eligibility(["--limit", "x"]), 2)
        self.assertEqual(runner._rescore_eligibility(["--limit"]), 2)
        self.assertEqual(runner._rescore_eligibility(["--bogus"]), 2)


if __name__ == "__main__":
    unittest.main()
