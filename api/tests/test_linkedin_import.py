"""LinkedIn extension import: token auth, same acceptance rules as the crawler."""

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

    def _job(self, lid="4300000001", **extra):
        job = {
            "linkedin_id": lid,
            "title": "Senior Site Reliability Engineer / Kubernetes (Remote)",
            "company": "Pragmatike",
            "location": "Worldwide",
            "description": "Run Kubernetes clusters on AWS. Fully remote, work from anywhere.",
            "apply_url": "https://jobs.ashbyhq.com/pragmatike/4cc505dc",
            "remote": True,
        }
        job.update(extra)
        return job

    def _post(self, jobs, token="secret"):
        with patch.dict("os.environ", {"JOB_IMPORT_TOKEN": "secret", "AI_MARKET_FIT_ENABLED": "0"}):
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

    def test_crawler_rules_apply(self):
        sales = self._job("4300000002", title="Sales Manager", description="Sell things. Remote.", apply_url="https://x.example/2")
        r = self._post([self._job(), sales, self._job()])
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual((body["created"], body["rejected"], body["duplicates"]), (1, 1, 1), body)
        again = self._post([self._job()]).json()
        self.assertEqual((again["created"], again["duplicates"]), (0, 1))
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT s.source_name, s.source_url, j.status FROM job_sources s JOIN jobs j ON j.id = s.job_id"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row[0], "linkedin-extension")
        self.assertEqual(row[1], "https://jobs.ashbyhq.com/pragmatike/4cc505dc")
        self.assertEqual(row[2], "published")


if __name__ == "__main__":
    unittest.main()
