"""Public job list is slim; detail keeps description and apply form."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.main import app


class JobsListDtoTests(unittest.TestCase):
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

    def _seed(self) -> int:
        form = (
            '{"message":{"enabled":true,"required":true},'
            '"phone":{"enabled":false,"required":false},'
            '"email":{"enabled":false,"required":false},'
            '"cv":{"enabled":true,"required":false},"questions":[]}'
        )
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                owner_subject, language, apply_form, remote, tech_stack, category
            )
            VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                "Backend developer",
                "Acme",
                "Baku",
                "Komanda ucun aciq rol. Python ve AWS.",
                "2026-10-05T09:00:00+04:00",
                "list-dto-1",
                "employer-1",
                "az",
                form,
                '["Python","AWS"]',
                "Backend",
            ),
        )
        job_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        return job_id

    def test_list_omits_text_and_form_detail_keeps_them(self):
        job_id = self._seed()
        listed = self.client.get("/api/v1/jobs")
        self.assertEqual(listed.status_code, 200)
        items = listed.json()["items"]
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["id"], job_id)
        self.assertEqual(item["title"], "Backend developer")
        self.assertEqual(item["company"], "Acme")
        self.assertEqual(item["tech_stack"], ["Python", "AWS"])
        self.assertEqual(item["category"], "Backend")
        self.assertEqual(item["language"], "az")
        self.assertTrue(item["onsite"])
        self.assertNotIn("text", item)
        self.assertNotIn("form", item)
        self.assertNotIn("source_homepage", item)
        self.assertNotIn("Komanda ucun aciq rol", listed.text)

        detail = self.client.get(f"/api/v1/jobs/{job_id}")
        self.assertEqual(detail.status_code, 200)
        body = detail.json()
        self.assertEqual(body["text"], "Komanda ucun aciq rol. Python ve AWS.")
        self.assertEqual(body["form"]["message"], {"enabled": True, "required": True})
        self.assertEqual(body["form"]["cv"], {"enabled": True, "required": False})
        self.assertNotIn("apply_form", body)


if __name__ == "__main__":
    unittest.main()
