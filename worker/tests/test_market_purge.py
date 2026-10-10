import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.market_purge import off_market_reason, purge_off_market


class MarketPurgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _insert(self, *, title, city, text, remote=0, relocation=0, url=""):
        cur = self.store.conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                tech_stack, remote, relocation, category, hidden
            ) VALUES (?, 'Co', ?, ?, 'published', datetime('now'), ?, '[]', ?, ?, 'Backend', 0)
            """,
            (title, city, text, f"nk-{title}-{city}-{remote}", remote, relocation),
        )
        job_id = int(cur.lastrowid)
        if url:
            self.store.conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                VALUES (?, 'Test', ?, '', datetime('now'))
                """,
                (job_id, url),
            )
        self.store.conn.commit()
        return job_id

    def test_germany_wide_reason(self):
        reason = off_market_reason(
            "Designer",
            "Remote",
            "You work remotely (Germany-wide), with offices in Hamburg.",
            remote=True,
            relocation=False,
        )
        self.assertEqual(reason, "foreign_locked_remote")

    def test_purge_hides_and_rejects_url(self):
        bad = self._insert(
            title="Staff Security US",
            city="Remote - California",
            text="US based candidates only. Organizations worldwide love us.",
            remote=1,
            url="https://example.com/jobs/us-only",
        )
        good = self._insert(
            title="Backend Remote",
            city="Remote",
            text="Fully remote. Work from anywhere worldwide.",
            remote=1,
            url="https://example.com/jobs/worldwide",
        )
        office = self._insert(
            title="Engineer Tel Aviv",
            city="Tel Aviv",
            text="Join our office.\n#LI-Hybrid\n",
            remote=0,
            url="https://example.com/jobs/tlv",
        )
        stats = purge_off_market(self.store.conn)
        self.assertGreaterEqual(stats["hidden"], 2)
        hidden = {
            int(r["id"]): int(r["hidden"])
            for r in self.store.conn.execute("SELECT id, hidden FROM jobs").fetchall()
        }
        self.assertEqual(hidden[bad], 1)
        self.assertEqual(hidden[office], 1)
        self.assertEqual(hidden[good], 0)
        rejected = self.store.conn.execute(
            "SELECT source_url FROM crawl_rejects ORDER BY source_url"
        ).fetchall()
        urls = {r["source_url"] for r in rejected}
        self.assertIn("https://example.com/jobs/us-only", urls)
        self.assertIn("https://example.com/jobs/tlv", urls)
        self.assertNotIn("https://example.com/jobs/worldwide", urls)


if __name__ == "__main__":
    unittest.main()
