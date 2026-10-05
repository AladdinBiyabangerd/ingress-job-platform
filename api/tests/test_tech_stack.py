"""Collected ads expose their tech stack, remote and relocation flags."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.main import app


class TechStackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _crawled(self, tech_stack: str) -> int:
        conn = sqlite3.connect(self.db)
        conn.execute(
            """
            INSERT INTO crawl_sources (name, homepage, connector, entry_url, enabled)
            VALUES ('Himalayas', 'https://himalayas.app', 'himalayas', 'https://himalayas.app/jobs/api', 1)
            """
        )
        cur = conn.execute(
            """
            INSERT INTO jobs (title, company, city, text, status, created_at, norm_key,
                              owner_subject, remote, relocation, tech_stack)
            VALUES ('Backend Engineer', 'Acme', '', 'Python and AWS', 'published',
                    '2026-10-05T09:00:00+04:00', 'tech-1', '', 1, 1, ?)
            """,
            (tech_stack,),
        )
        job_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
            VALUES (?, 'Himalayas', 'https://himalayas.app/companies/acme/jobs/1', '', '2026-10-05T09:00:00+04:00')
            """,
            (job_id,),
        )
        conn.commit()
        conn.close()
        return job_id

    def test_list_and_detail_carry_stack_and_flags(self):
        job_id = self._crawled('["Python", "AWS", "PostgreSQL"]')
        items = self.client.get("/api/v1/jobs").json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tech_stack"], ["Python", "AWS", "PostgreSQL"])
        self.assertTrue(items[0]["remote"])
        self.assertTrue(items[0]["relocation"])
        detail = self.client.get(f"/api/v1/jobs/{job_id}").json()
        self.assertEqual(detail["tech_stack"], ["Python", "AWS", "PostgreSQL"])
        self.assertEqual(detail["source_homepage"], "https://himalayas.app")
        self.assertNotIn("companies/acme/jobs/1", str(detail))

    def test_bad_stack_value_is_an_empty_list(self):
        job_id = self._crawled("not json")
        detail = self.client.get(f"/api/v1/jobs/{job_id}").json()
        self.assertEqual(detail["tech_stack"], [])


if __name__ == "__main__":
    unittest.main()
