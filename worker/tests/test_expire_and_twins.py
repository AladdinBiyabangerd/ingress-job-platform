"""Expiry of ads no board lists any more, and merging remote-place twins."""

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from worker.db import EXPIRE_REASON, Store, like_prefix
from worker.parsing import norm_key

SRC = "Test Board"


def _item(url="https://board.example.com/jobs/1", city="Remote", text="Build APIs in Python.", **kw):
    item = {
        "title": "Backend Engineer", "company": "Acme", "city": city, "text": text,
        "source_url": url, "source_name": SRC, "remote": True,
    }
    item.update(kw)
    return item


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        c = self.store.conn
        with c:
            cur = c.execute(
                "INSERT INTO crawl_sources (name, homepage, connector, entry_url) VALUES (?, '', 'x', '')",
                (SRC,),
            )
            self.source_id = int(cur.lastrowid)

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def _run(self, when, found=5, status="ok", error=None, complete=1, source_id=None):
        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO crawl_runs (source_id, started_at, status, found_count, error, complete_listing) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (source_id or self.source_id, when.isoformat(), status, found, error, complete),
            )

    def _seen(self, job_id, when):
        with self.store.conn:
            self.store.conn.execute(
                "UPDATE job_sources SET last_seen = ? WHERE job_id = ?", (when.isoformat(), job_id)
            )

    def _job(self, job_id):
        return self.store.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def _publish(self, job_id):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET status = 'published' WHERE id = ?", (job_id,))


class ExpireTest(_Base):
    def setUp(self):
        super().setUp()
        self.store.upsert(_item())
        self.job_id = int(self.store.conn.execute("SELECT id FROM jobs").fetchone()["id"])
        self._publish(self.job_id)
        self.now = datetime.now(timezone.utc)
        self._seen(self.job_id, self.now - timedelta(days=9))

    def test_hidden_when_unseen_and_source_crawled_since(self):
        self._run(self.now - timedelta(days=1))
        self.assertEqual(self.store.expire_unseen(now=self.now), 1)
        row = self._job(self.job_id)
        self.assertEqual(row["hidden"], 1)
        self.assertEqual(row["reject_reason"], EXPIRE_REASON)
        self.assertEqual(row["status"], "published")

    def test_kept_when_seen_recently(self):
        self._seen(self.job_id, self.now - timedelta(days=3))
        self._run(self.now - timedelta(days=1))
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_kept_when_source_never_crawled_cleanly_since(self):
        self._run(self.now - timedelta(days=12))
        self._run(self.now - timedelta(days=1), status="error", error="boom")
        self._run(self.now - timedelta(days=1), complete=0)
        self._run(self.now - timedelta(days=1), error="stopped: time budget")
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_partial_listing_run_not_trusted(self):
        # Capped / rotated / budget-stopped runs record complete_listing=0.
        self._run(self.now - timedelta(days=1), complete=0)
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_complete_run_with_no_new_candidates_counts(self):
        self._run(self.now - timedelta(days=1), found=0)
        self.assertEqual(self.store.expire_unseen(now=self.now), 1)

    def test_exempt_source_never_expires(self):
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO crawl_sources (name, homepage, connector, entry_url) VALUES ('Himalayas X', '', 'x', '')"
            )
            self.store.conn.execute(
                "UPDATE job_sources SET source_name = 'Himalayas X' WHERE job_id = ?", (self.job_id,)
            )
        self._run(self.now - timedelta(days=1), source_id=int(cur.lastrowid))
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_finish_run_records_flag(self):
        run = self.store.start_run(self.source_id)
        self.store.finish_run(run, status="ok", found=0, created=0, updated=0, error=None, complete_listing=True)
        row = self.store.conn.execute("SELECT complete_listing FROM crawl_runs WHERE id = ?", (run,)).fetchone()
        self.assertEqual(row[0], 1)

    def test_mixed_offsets_compare_as_time(self):
        # last_seen 9 days ago in +04:00; run 8.95 days ago written in UTC.
        local = (self.now - timedelta(days=9)).astimezone(timezone(timedelta(hours=4)))
        self._seen(self.job_id, local)
        self._run(self.now - timedelta(days=8, hours=23))
        self.assertEqual(self.store.expire_unseen(now=self.now), 1)

    def test_owner_and_locked_rows_skipped(self):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET content_locked = 1 WHERE id = ?", (self.job_id,))
        self._run(self.now - timedelta(days=1))
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)
        with self.store.conn:
            self.store.conn.execute(
                "UPDATE jobs SET content_locked = 0, owner_subject = 'u1' WHERE id = ?", (self.job_id,)
            )
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_every_source_must_be_crawled_since(self):
        self._run(self.now - timedelta(days=1))
        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO job_sources (job_id, source_name, source_url, last_seen) VALUES (?, 'Other Board', 'https://o.example/1', ?)",
                (self.job_id, (self.now - timedelta(days=9)).isoformat()),
            )
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)

    def test_reappearing_unchanged_unhides_without_review(self):
        self._run(self.now - timedelta(days=1))
        self.store.expire_unseen(now=self.now)
        self.store.upsert(_item())
        row = self._job(self.job_id)
        self.assertEqual(row["hidden"], 0)
        self.assertEqual(row["reject_reason"], "")
        self.assertEqual(row["status"], "published")

    def test_reappearing_changed_goes_to_review(self):
        self._run(self.now - timedelta(days=1))
        self.store.expire_unseen(now=self.now)
        self.store.upsert(_item(text="Build APIs in Python. US only now."))
        row = self._job(self.job_id)
        self.assertEqual(row["hidden"], 0)
        self.assertEqual(row["status"], "pending")

    def test_staff_hide_not_undone(self):
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET hidden = 1, reject_reason = 'staff' WHERE id = ?", (self.job_id,))
        self.store.upsert(_item())
        self.assertEqual(self._job(self.job_id)["hidden"], 1)

    def test_touch_seen_refreshes_listed_urls(self):
        self.assertEqual(self.store.touch_seen(["https://board.example.com/jobs/1", "https://x/none"]), 1)
        self._run(self.now + timedelta(seconds=5))
        self.assertEqual(self.store.expire_unseen(now=self.now), 0)


class TwinTest(_Base):
    def test_norm_key_ignores_remote_labels(self):
        base = norm_key("Backend Engineer", "Acme", "")
        for city in ("Remote", "remote worldwide", "remote remote worldwide", "Anywhere"):
            self.assertEqual(norm_key("Backend Engineer", "Acme", city), base)
        self.assertNotEqual(norm_key("Backend Engineer", "Acme", "Berlin"), base)

    def test_remote_label_and_empty_city_are_one_ad(self):
        self.store.upsert(_item(url="https://a.example/1", city=""))
        self.store.upsert(_item(url="https://b.example/1", city="remote worldwide"))
        live = self.store.conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE COALESCE(merged_into, 0) = 0"
        ).fetchone()[0]
        self.assertEqual(live, 1)
        self.assertEqual(self.store.conn.execute("SELECT COUNT(*) FROM job_sources").fetchone()[0], 2)

    def _legacy(self, city, key_city, created, status="pending", url="https://a.example/1"):
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO jobs (title, company, city, text, status, created_at, norm_key) VALUES (?, ?, ?, 't', ?, ?, ?)",
                ("Backend Engineer", "Acme", city, status, created, f"backend engineer|acme|{key_city}"),
            )
            jid = int(cur.lastrowid)
            self.store.conn.execute(
                "INSERT INTO job_sources (job_id, source_name, source_url, last_seen) VALUES (?, ?, ?, ?)",
                (jid, SRC, url, created),
            )
        return jid

    def test_one_time_merge_keeps_published_and_moves_sources(self):
        older = self._legacy("remote worldwide", "remote worldwide", "2026-10-01T10:00:00+04:00")
        newer = self._legacy("", "", "2026-10-05T10:00:00+04:00", status="published", url="https://b.example/1")
        other = self._legacy("Berlin", "berlin", "2026-10-01T10:00:00+04:00", url="https://c.example/1")
        self.assertEqual(self.store.merge_remote_twins(), 1)
        self.assertEqual(self._job(older)["merged_into"], newer)
        self.assertEqual(self._job(older)["hidden"], 1)
        self.assertEqual(self._job(newer)["hidden"], 0)
        self.assertIsNone(self._job(other)["merged_into"])
        n = self.store.conn.execute("SELECT COUNT(*) FROM job_sources WHERE job_id = ?", (newer,)).fetchone()[0]
        self.assertEqual(n, 2)
        self.assertEqual(
            self.store.conn.execute("SELECT kept_id FROM job_merges WHERE hidden_id = ?", (older,)).fetchone()[0],
            newer,
        )
        self.assertEqual(self.store.merge_remote_twins(), 0)  # one-time

    def test_one_time_merge_keeps_oldest_when_none_published(self):
        a = self._legacy("remote", "remote", "2026-10-01T10:00:00+04:00")
        b = self._legacy("", "", "2026-10-05T10:00:00+04:00", url="https://b.example/1")
        self.store.merge_remote_twins()
        self.assertEqual(self._job(b)["merged_into"], a)

    def test_owner_rows_never_merged(self):
        a = self._legacy("remote", "remote", "2026-10-01T10:00:00+04:00")
        b = self._legacy("", "", "2026-10-05T10:00:00+04:00", url="https://b.example/1")
        with self.store.conn:
            self.store.conn.execute("UPDATE jobs SET owner_subject = 'u1' WHERE id = ?", (b,))
        self.assertEqual(self.store.merge_remote_twins(), 0)
        self.assertIsNone(self._job(a)["merged_into"])

    def test_like_prefix_escapes_wildcards(self):
        self.assertEqual(like_prefix("a_b%c\\"), "a\\_b\\%c\\\\%")
        self._legacy("", "", "2026-10-01T10:00:00+04:00")
        rows = self.store.conn.execute(
            "SELECT id FROM jobs WHERE norm_key LIKE ? ESCAPE ?", (like_prefix("backend_engineer|"), "\\")
        ).fetchall()
        self.assertEqual(rows, [])


class _Client:
    def allowed(self, url):
        return True


class _Feed:
    def __init__(self, rows, full):
        from worker.connectors.feed import FeedConnector

        class F(FeedConnector):
            name = "F"
            entry_url = "https://f.example/feed"
            full_listing = full

            def feed_items(inner):
                return [dict(r) for r in rows]

        self.cls = F


class ListingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        self.store.upsert(_item(url="https://f.example/known"))

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def _rows(self):
        return [
            {"title": "Backend Engineer", "source_url": "https://f.example/known"},
            {"title": "Python Developer", "source_url": "https://f.example/new"},
        ]

    def test_known_urls_are_listed_for_last_seen(self):
        conn = _Feed(self._rows(), True).cls(_Client(), self.store)
        urls = conn.discover()
        self.assertEqual(urls, ["https://f.example/new"])  # candidates: new only
        self.assertIn("https://f.example/known", conn.listed_urls)
        self.assertTrue(conn.listing_complete)
        self.assertEqual(self.store.touch_seen(conn.listed_urls), 1)

    def test_unknown_feed_is_partial(self):
        conn = _Feed(self._rows(), False).cls(_Client(), self.store)
        conn.discover()
        self.assertFalse(conn.listing_complete)

    def test_empty_listing_is_partial(self):
        conn = _Feed([], True).cls(_Client(), self.store)
        conn.discover()
        self.assertFalse(conn.listing_complete)

    def test_ats_truncation(self):
        from worker.connectors import ats

        class G(ats.AtsConnector):
            name = "G"
            entry_url = "https://g.example/"
            boards = ("a", "b")
            sizes = {"a": 2, "b": 2}

            def board_items(inner, slug):
                return [{"title": "Backend Engineer", "source_url": f"https://g.example/{slug}/{i}"}
                        for i in range(inner.sizes[slug])]

        full = G(_Client(), self.store)
        full.discover()
        self.assertTrue(full.listing_complete)
        G.sizes = {"a": ats.PER_BOARD + 1, "b": 1}
        cut = G(_Client(), self.store)
        cut.discover()
        self.assertFalse(cut.listing_complete)
        G.sizes = {"a": 1, "b": 1}
        G.max_boards = 1
        rotated = G(_Client(), self.store)
        rotated.discover()
        self.assertFalse(rotated.listing_complete)


if __name__ == "__main__":
    unittest.main()
