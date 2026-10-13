import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.db import Store
from worker.posted import latin_title, parse_posted


class ParsePostedTests(unittest.TestCase):
    def test_formats(self):
        now = datetime.now(timezone.utc)
        iso = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.assertTrue(parse_posted(iso))
        self.assertTrue(parse_posted((now - timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S +0000")))
        self.assertTrue(parse_posted(int((now - timedelta(days=3)).timestamp())))
        self.assertTrue(parse_posted(str(int((now - timedelta(days=3)).timestamp() * 1000))))

    def test_sanity(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(parse_posted((now + timedelta(days=3)).isoformat()), "")
        self.assertEqual(parse_posted((now - timedelta(days=500)).isoformat()), "")
        self.assertEqual(parse_posted("000000000000000"), "")
        self.assertEqual(parse_posted("not a date"), "")
        self.assertEqual(parse_posted(None), "")


class LatinTitleTests(unittest.TestCase):
    def test_mixed(self):
        self.assertEqual(latin_title("Product Manager / プロダクトマネージャー"), "Product Manager")
        self.assertEqual(latin_title("クラウドエンジニア / Cloud Engineer"), "Cloud Engineer")
        self.assertEqual(
            latin_title("Backend Engineer / バックエンドエンジニア (Core Banking System)"),
            "Backend Engineer (Core Banking System)",
        )

    def test_unchanged(self):
        for title in ("Go / Rust Engineer", "Backend Engineer", "バックエンドエンジニア"):
            self.assertEqual(latin_title(title), title)


class UpsertPostedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "jobs.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def item(self, **extra):
        base = {
            "title": "Backend Engineer", "company": "Acme", "city": "Berlin",
            "text": "Python", "source_url": "https://example.com/1", "source_name": "Test",
        }
        base.update(extra)
        return base

    def test_fill_does_not_touch_status_or_updated_at(self):
        self.store.upsert(self.item())
        self.store.conn.execute("UPDATE jobs SET status = 'published', updated_at = 'X'")
        self.store.conn.commit()
        posted = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        self.store.upsert(self.item(posted_at=posted))
        row = self.store.conn.execute("SELECT status, updated_at, posted_at FROM jobs").fetchone()
        self.assertEqual(row["status"], "published")
        self.assertEqual(row["updated_at"], "X")
        self.assertTrue(row["posted_at"])

    def test_mixed_title_does_not_requeue(self):
        self.store.upsert(self.item(title="Product Manager / プロダクトマネージャー"))
        self.store.conn.execute("UPDATE jobs SET status = 'published'")
        self.store.conn.commit()
        self.store.upsert(self.item(title="Product Manager / プロダクトマネージャー"))
        row = self.store.conn.execute("SELECT status, title FROM jobs").fetchone()
        self.assertEqual(row["title"], "Product Manager")
        self.assertEqual(row["status"], "published")

    def test_one_shot_titles(self):
        self.store.upsert(self.item())
        self.store.conn.execute(
            "UPDATE jobs SET title = 'Product Manager / プロダクトマネージャー', status = 'published'"
        )
        self.store.conn.commit()
        self.assertEqual(self.store.latin_titles(), 1)
        self.assertEqual(self.store.latin_titles(), 0)
        row = self.store.conn.execute("SELECT status, title FROM jobs").fetchone()
        self.assertEqual((row["status"], row["title"]), ("published", "Product Manager"))


if __name__ == "__main__":
    unittest.main()
