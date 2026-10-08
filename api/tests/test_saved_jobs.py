"""Saved / favorited jobs for signed-in users."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import save_profile


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class SavedJobsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("save-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _published_ad(self):
        with self._auth("job:employer", "save-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json={
                    "title": "Frontend muhendisi",
                    "company": "Ingress MMC",
                    "city": "Baki",
                    "remote": False,
                    "text": "Komanda ucun aciq rol.",
                    "language": "az",
                    "salary": "",
                    "job_type": "ofis",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad_id = created.json()["id"]
        with self._auth("job:staff", "save-staff"):
            approved = self.client.post(
                f"/api/v1/admin/jobs/{ad_id}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
        return ad_id

    def test_guest_cannot_save(self):
        ad_id = self._published_ad()
        res = self.client.post(f"/api/v1/me/saved-jobs/{ad_id}")
        self.assertEqual(res.status_code, 401)

    def test_save_list_unsave_idempotent(self):
        ad_id = self._published_ad()
        with self._auth("job:candidate", "save-candidate"):
            headers = {"Authorization": "Bearer test"}
            created = self.client.post(f"/api/v1/me/saved-jobs/{ad_id}", headers=headers)
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["job_id"], ad_id)

            again = self.client.post(f"/api/v1/me/saved-jobs/{ad_id}", headers=headers)
            self.assertEqual(again.status_code, 200, again.text)

            ids = self.client.get("/api/v1/me/saved-jobs/ids", headers=headers)
            self.assertEqual(ids.status_code, 200)
            self.assertEqual(ids.json()["ids"], [ad_id])

            listed = self.client.get("/api/v1/me/saved-jobs", headers=headers)
            self.assertEqual(listed.status_code, 200)
            body = listed.json()
            self.assertEqual(body["total"], 1)
            self.assertEqual(body["items"][0]["id"], ad_id)
            self.assertEqual(body["items"][0]["title"], "Frontend muhendisi")
            self.assertIn("saved_at", body["items"][0])

            deleted = self.client.delete(f"/api/v1/me/saved-jobs/{ad_id}", headers=headers)
            self.assertEqual(deleted.status_code, 204)

            deleted_again = self.client.delete(f"/api/v1/me/saved-jobs/{ad_id}", headers=headers)
            self.assertEqual(deleted_again.status_code, 204)

            empty = self.client.get("/api/v1/me/saved-jobs/ids", headers=headers)
            self.assertEqual(empty.json()["ids"], [])

    def test_cannot_save_missing_job(self):
        with self._auth("job:candidate", "save-candidate"):
            res = self.client.post(
                "/api/v1/me/saved-jobs/999999",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(res.status_code, 404)

    def test_employer_can_save_too(self):
        ad_id = self._published_ad()
        with self._auth("job:employer", "save-employer"):
            res = self.client.post(
                f"/api/v1/me/saved-jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(res.status_code, 201, res.text)


if __name__ == "__main__":
    unittest.main()
