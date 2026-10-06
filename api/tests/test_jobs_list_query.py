"""Paginated public job list: page/per_page, filters, facets envelope."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.main import app


class JobsListQueryTests(unittest.TestCase):
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

    def _seed(self, n: int, *, remote: bool = False, title_prefix: str = "Role") -> list[int]:
        conn = sqlite3.connect(self.db)
        ids: list[int] = []
        for i in range(n):
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key,
                    language, remote, tech_stack, category
                )
                VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{title_prefix} {i}",
                    "Acme" if i % 2 == 0 else "Beta",
                    "Baku",
                    "Python backend work.",
                    f"2026-10-0{(i % 5) + 1}T09:00:00+04:00",
                    f"list-query-{title_prefix}-{i}",
                    "en",
                    1 if remote else 0,
                    '["Python","AWS"]' if i % 3 == 0 else '["React"]',
                    "Backend" if i % 2 == 0 else "Frontend",
                ),
            )
            ids.append(int(cur.lastrowid))
        conn.commit()
        conn.close()
        return ids

    def test_default_page_size_and_envelope(self):
        self._seed(25)
        res = self.client.get("/api/v1/jobs")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(len(body["items"]), 20)
        self.assertEqual(body["total"], 25)
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["per_page"], 20)
        self.assertEqual(body["pages"], 2)
        self.assertEqual(body["catalog_total"], 25)
        self.assertIn("facets", body)
        self.assertTrue(body["facets"]["languages"])
        self.assertTrue(body["facets"]["categories"])
        self.assertTrue(body["facets"]["stacks"])
        self.assertNotIn("text", body["items"][0])

    def test_page_two(self):
        self._seed(25)
        body = self.client.get("/api/v1/jobs", params={"page": 2}).json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(len(body["items"]), 5)
        self.assertEqual(body["total"], 25)

    def test_q_filter(self):
        self._seed(10, title_prefix="Engineer")
        self._seed(5, title_prefix="Designer")
        body = self.client.get("/api/v1/jobs", params={"q": "Designer"}).json()
        self.assertEqual(body["total"], 5)
        self.assertEqual(body["catalog_total"], 15)
        self.assertTrue(all("Designer" in item["title"] for item in body["items"]))

    def test_remote_filter(self):
        self._seed(5, remote=False)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE jobs SET remote = 1 WHERE id = (SELECT MIN(id) FROM jobs)")
        conn.commit()
        conn.close()
        body = self.client.get("/api/v1/jobs", params={"remote": "true"}).json()
        self.assertEqual(body["total"], 1)
        self.assertTrue(body["items"][0]["remote"])

    def test_language_filter_uses_python_path(self):
        self._seed(8)
        body = self.client.get("/api/v1/jobs", params={"language": "en"}).json()
        self.assertEqual(body["total"], 8)
        self.assertEqual(len(body["items"]), 8)

    def test_per_page_cap(self):
        self._seed(5)
        self.assertEqual(self.client.get("/api/v1/jobs", params={"per_page": 0}).status_code, 422)
        self.assertEqual(self.client.get("/api/v1/jobs", params={"per_page": 61}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
