"""Re-crawl of a staff-approved ad: changed content goes back to pending."""

import tempfile
import unittest
from pathlib import Path

from worker.db import Store

URL = "https://boards.example.com/jobs/1"


def _item(title="Backend Engineer", text="Build APIs in Python. Remote worldwide."):
    return {
        "title": title, "company": "Acme", "city": "Remote", "text": text,
        "source_url": URL, "source_name": "greenhouse:acme", "remote": True,
    }


class ApprovedRecrawlTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        self.store.upsert(_item())
        self.job_id = self.store.conn.execute("SELECT id FROM jobs").fetchone()["id"]
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET status = 'published' WHERE id = ?", (self.job_id,))

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def _row(self):
        return self.store.conn.execute(
            "SELECT status, title, text FROM jobs WHERE id = ?", (self.job_id,)
        ).fetchone()

    def test_changed_title_goes_back_to_pending(self):
        self.store.upsert(_item(title="Backend Engineer, US only"))
        row = self._row()
        self.assertEqual(row["status"], "pending")
        self.assertEqual(row["title"], "Backend Engineer, US only")

    def test_changed_text_goes_back_to_pending(self):
        self.store.upsert(_item(text="Build APIs in Python. Must live in the US."))
        self.assertEqual(self._row()["status"], "pending")

    def test_unchanged_content_stays_approved(self):
        self.store.upsert(_item())
        self.assertEqual(self._row()["status"], "published")

    def test_whitespace_and_case_noise_stays_approved(self):
        self.store.upsert(_item(title="  backend   engineer ", text="Build APIs in Python.\n\n Remote worldwide.  "))
        self.assertEqual(self._row()["status"], "published")

    def test_hidden_ad_untouched(self):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET hidden = 1 WHERE id = ?", (self.job_id,))
        self.store.upsert(_item(title="Something else"))
        row = self._row()
        self.assertEqual((row["status"], row["title"]), ("published", "Backend Engineer"))

    def test_locked_ad_untouched(self):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET content_locked = 1 WHERE id = ?", (self.job_id,))
        self.store.upsert(_item(title="Something else"))
        row = self._row()
        self.assertEqual((row["status"], row["title"]), ("published", "Backend Engineer"))

    def test_pending_ad_stays_pending(self):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET status = 'pending' WHERE id = ?", (self.job_id,))
        self.store.upsert(_item(title="Changed"))
        self.assertEqual(self._row()["status"], "pending")


if __name__ == "__main__":
    unittest.main()
