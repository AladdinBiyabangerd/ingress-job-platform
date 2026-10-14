"""Viewed jobs + original listing open counts."""

import sqlite3
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


class ViewedAndOpensTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self._seed_external_job()

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_external_job(self):
        conn = sqlite3.connect(self.db)
        try:
            cur = conn.execute(
                """
                INSERT INTO jobs (title, company, city, text, status, created_at, remote, norm_key)
                VALUES (?, ?, ?, ?, 'published', '2026-01-01T00:00:00+00:00', 1, ?)
                """,
                ("Backend", "Acme", "Remote", "Role body", "viewed-opens-1"),
            )
            self.job_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, last_seen)
                VALUES (?, 'TestBoard', ?, '2026-01-01T00:00:00+00:00')
                """,
                (self.job_id, "https://example.com/jobs/1"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_mark_viewed_and_filter(self):
        with self._auth("job:candidate", "viewer-1"):
            headers = {"Authorization": "Bearer test"}
            marked = self.client.post(
                f"/api/v1/me/viewed-jobs/{self.job_id}", headers=headers
            )
            self.assertEqual(marked.status_code, 201, marked.text)
            again = self.client.post(
                f"/api/v1/me/viewed-jobs/{self.job_id}", headers=headers
            )
            self.assertEqual(again.status_code, 200, again.text)

            ids = self.client.get("/api/v1/me/viewed-jobs/ids", headers=headers)
            self.assertEqual(ids.status_code, 200)
            self.assertEqual(ids.json()["ids"], [self.job_id])

            filtered = self.client.get(
                "/api/v1/jobs?viewed=true", headers=headers
            )
            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(filtered.json()["total"], 1)
            self.assertEqual(filtered.json()["items"][0]["id"], self.job_id)

        guest = self.client.get("/api/v1/jobs?viewed=true")
        self.assertEqual(guest.status_code, 200)
        self.assertEqual(guest.json()["total"], 0)

    def test_original_open_counted_once_per_user(self):
        with self._auth("job:candidate", "opener-1"):
            headers = {"Authorization": "Bearer test"}
            for _ in range(5):
                res = self.client.get(
                    f"/api/v1/jobs/{self.job_id}/original", headers=headers
                )
                self.assertEqual(res.status_code, 200, res.text)
                self.assertTrue(res.json()["url"])
            # Same person also hits apply → still one opener.
            apply_again = self.client.post(
                f"/api/v1/jobs/{self.job_id}/apply", headers=headers
            )
            self.assertEqual(apply_again.status_code, 200, apply_again.text)

        mid = self.client.get(f"/api/v1/jobs/{self.job_id}")
        self.assertEqual(mid.json()["original_opens"], 1)

        with self._auth("job:candidate", "opener-2"):
            headers = {"Authorization": "Bearer test"}
            other = self.client.post(
                f"/api/v1/jobs/{self.job_id}/apply", headers=headers
            )
            self.assertEqual(other.status_code, 200, other.text)
            self.assertTrue(other.json().get("url"))

        detail = self.client.get(f"/api/v1/jobs/{self.job_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["original_opens"], 2)

        listed = self.client.get("/api/v1/jobs")
        self.assertEqual(listed.status_code, 200)
        item = listed.json()["items"][0]
        self.assertEqual(item["original_opens"], 2)


if __name__ == "__main__":
    unittest.main()
