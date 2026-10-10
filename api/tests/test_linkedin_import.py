"""LinkedIn extension import: token auth, create, dedupe."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import _connect, ensure_schema
from app.main import app


class LinkedInImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", Path(self.tmp.name) / "jobs.sqlite")
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _job(self, lid="1234567890", **extra):
        job = {
            "linkedin_id": lid,
            "title": "Python Developer",
            "company": "Acme",
            "location": "Baku",
            "description": "Build APIs.",
            "apply_url": "https://acme.example/apply/1",
        }
        job.update(extra)
        return job

    def _post(self, jobs, token="secret"):
        with patch.dict("os.environ", {"JOB_IMPORT_TOKEN": "secret"}):
            return self.client.post(
                "/api/v1/import/linkedin-jobs",
                headers={"X-Import-Token": token},
                json={"jobs": jobs},
            )

    def test_requires_token(self):
        self.assertEqual(self._post([self._job()], token="bad").status_code, 401)
        with patch.dict("os.environ", {"JOB_IMPORT_TOKEN": ""}):
            r = self.client.post("/api/v1/import/linkedin-jobs", json={"jobs": []})
        self.assertEqual(r.status_code, 503)

    def test_create_then_duplicate(self):
        r = self._post([self._job(), self._job(), self._job("999999999", title="")])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["created"], body["duplicates"], body["errors"]), (1, 1, 1))
        again = self._post([self._job()]).json()
        self.assertEqual((again["created"], again["duplicates"]), (0, 1))
        conn = _connect()
        try:
            row = conn.execute("SELECT source_name, source_url FROM job_sources").fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "linkedin-extension")
        self.assertEqual(row[1], "https://acme.example/apply/1")


if __name__ == "__main__":
    unittest.main()
