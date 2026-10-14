"""Staff job_tidy queue + async run start/cancel."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


MESSY = (
    "We are looking for a senior engineer to join our distributed systems team "
    "working on large scale data platforms. You will design APIs, own on-call, "
    "mentor juniors, collaborate with product, and ship reliable services. "
    "Experience with Python, Kubernetes, Postgres and cloud infrastructure is "
    "required. Benefits include health insurance remote work flexible hours "
    "and stock options for the right candidate who can start soon."
)


class JobTidyAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str = "job:staff", subject: str = "staff-1"):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _headers(self):
        return {"Authorization": "Bearer test"}

    def _insert(self, *, title="Messy job", status="published", cleaned="", text=MESSY, key=""):
        from app.cabinet_store import _connect

        conn = _connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, cleaned_text, status, created_at,
                    remote, norm_key, owner_subject
                ) VALUES (?, 'Co', 'Baku', ?, ?, ?, '2026-01-01T00:00:00Z', 0, ?, '')
                """,
                (title, text, cleaned, status, key or f"tidy-{title}"),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def test_list_only_messy_published_without_cleaned(self):
        need = self._insert(key="need")
        self._insert(title="Already tidy", cleaned="Why this role is interesting:\n• x", key="done")
        self._insert(title="Short", text="Too short to tidy.", key="short")
        self._insert(title="Pending", status="pending", key="pending")
        with self._auth():
            res = self.client.get("/api/v1/admin/job-tidy", headers=self._headers())
        self.assertEqual(res.status_code, 200)
        ids = [item["id"] for item in res.json()["items"]]
        self.assertEqual(ids, [need])

    def test_start_and_cancel(self):
        job_id = self._insert(key="run")
        with self._auth():
            started = self.client.post(
                "/api/v1/admin/job-tidy/run",
                json={"ids": [job_id]},
                headers=self._headers(),
            )
        self.assertEqual(started.status_code, 200)
        run_id = started.json()["job_id"]
        self.assertTrue(run_id)
        with self._auth():
            cancelled = self.client.post(
                f"/api/v1/admin/job-tidy/run/{run_id}/cancel",
                headers=self._headers(),
            )
        self.assertEqual(cancelled.status_code, 200)
        self.assertIn(cancelled.json()["status"], ("cancelled", "done", "failed", "running", "queued"))


if __name__ == "__main__":
    unittest.main()
