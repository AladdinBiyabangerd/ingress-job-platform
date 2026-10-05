"""Ads collected from the retired domestic sources are hidden once, not deleted."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import HIDE_RETIRED_STEP, ensure_schema, hide_retired_local
from app.crawled_admin import list_crawled, set_crawled_hidden
from app.main import app


class RetiredSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        conn = sqlite3.connect(self.db)
        # The schema step already ran on the empty database; forget it so the
        # rows below look like a database from before the change.
        conn.execute("DELETE FROM maintenance_steps WHERE name = ?", (HIDE_RETIRED_STEP,))
        self.busy = self._job(conn, "Satici", "", [("busy.az", "https://busy.example/1")])
        self.boss = self._job(conn, "Muhasib", "", [("Boss.az", "https://boss.example/2")])
        self.both = self._job(
            conn, "Backend Engineer", "",
            [("HelloJob", "https://hellojob.example/3"), ("Remote OK", "https://remoteok.example/3")],
        )
        self.foreign = self._job(conn, "Go Developer", "", [("Remote OK", "https://remoteok.example/4")])
        self.cabinet = self._job(conn, "Kabinet elani", "employer-1", [("Busy.az", "https://busy.example/5")])
        conn.commit()
        conn.close()

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _job(self, conn, title, owner, sources):
        cur = conn.execute(
            """
            INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject)
            VALUES (?, 'Sirket', 'Baki', 'Metn', 'published', '2026-10-04T12:00:00+04:00', ?, ?)
            """,
            (title, f"key-{title}", owner),
        )
        job_id = int(cur.lastrowid)
        for name, url in sources:
            conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                VALUES (?, ?, ?, '', '2026-10-04T12:00:00+04:00')
                """,
                (job_id, name, url),
            )
        return job_id

    def _hide(self):
        conn = sqlite3.connect(self.db)
        try:
            hidden = hide_retired_local(conn)
            conn.commit()
        finally:
            conn.close()
        return hidden

    def _hidden(self):
        conn = sqlite3.connect(self.db)
        try:
            return {int(r[0]): int(r[1] or 0) for r in conn.execute("SELECT id, hidden FROM jobs")}
        finally:
            conn.close()

    def test_hides_only_collected_ads_from_retired_sources(self):
        self.assertEqual(self._hide(), 2)
        flags = self._hidden()
        self.assertEqual(len(flags), 5)  # nothing deleted
        self.assertEqual(flags[self.busy], 1)
        self.assertEqual(flags[self.boss], 1)
        self.assertEqual(flags[self.both], 0)  # also on a current source
        self.assertEqual(flags[self.foreign], 0)
        self.assertEqual(flags[self.cabinet], 0)  # cabinet ads are never touched

        public_ids = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertNotIn(self.busy, public_ids)
        self.assertNotIn(self.boss, public_ids)
        self.assertIn(self.foreign, public_ids)
        self.assertEqual(self.client.get(f"/api/v1/jobs/{self.busy}").status_code, 404)

        admin = {item["id"]: item for item in list_crawled()}
        self.assertTrue(admin[self.busy]["hidden"])

    def test_runs_once_so_staff_unhide_sticks(self):
        self._hide()
        set_crawled_hidden(self.busy, False)
        self.assertEqual(self._hide(), 0)
        self.assertEqual(self._hidden()[self.busy], 0)
        public_ids = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertIn(self.busy, public_ids)


if __name__ == "__main__":
    unittest.main()
