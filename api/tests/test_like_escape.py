"""User search text is literal inside LIKE: % and _ are not wildcards."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.main import app
from app.sql_like import escape_like, like_contains


class LikeEscapeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        conn = sqlite3.connect(self.db)
        for i, (title, company) in enumerate([
            ("Backend Engineer", "Acme"), ("100% Remote Python Dev", "Beta"),
            ("Data_Engineer", "Gamma"), ("Frontend Dev", "Delta\\Labs"),
        ]):
            conn.execute(
                "INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, language) "
                "VALUES (?, ?, 'Baku', 'Python work.', 'published', '2026-10-01T09:00:00+04:00', ?, 'en')",
                (title, company, f"like-{i}"),
            )
        conn.commit()
        conn.close()
        self.client = TestClient(app)

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _titles(self, **params):
        res = self.client.get("/api/v1/jobs", params=params)
        self.assertEqual(res.status_code, 200)
        return sorted(item["title"] for item in res.json()["items"])

    def test_helpers(self):
        self.assertEqual(escape_like("a%b_c\\"), "a\\%b\\_c\\\\")
        self.assertEqual(like_contains("x_"), "%x\\_%")

    def test_percent_and_underscore_match_only_literally(self):
        self.assertEqual(self._titles(q="%"), ["100% Remote Python Dev"])
        self.assertEqual(self._titles(q="_"), ["Data_Engineer"])
        self.assertEqual(self._titles(q="%%"), [])
        self.assertEqual(self._titles(q="__"), [])

    def test_backslash_and_company_filter(self):
        self.assertEqual(self._titles(q="\\"), ["Frontend Dev"])
        self.assertEqual(self._titles(company="%"), [])
        self.assertEqual(self._titles(company="delta\\"), ["Frontend Dev"])

    def test_plain_search_still_works(self):
        self.assertEqual(self._titles(q="engineer"), ["Backend Engineer", "Data_Engineer"])


if __name__ == "__main__":
    unittest.main()
