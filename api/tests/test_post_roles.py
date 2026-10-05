"""Who may post and moderate: the API enforces the same rules as the navbar.

Roles are Academy token scopes. job:employer or job:staff may use the cabinet;
a candidate-only account (job:candidate, possibly with student) gets 403 on
every cabinet route, and only job:staff reaches moderation.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import save_profile

AUTH = {"Authorization": "Bearer test"}
AD = {
    "title": "Backend muhendisi",
    "company": "Ingress MMC",
    "city": "Baki",
    "remote": False,
    "text": "Komanda ucun aciq rol.",
    "language": "az",
    "salary": "",
    "job_type": "hibrid",
}


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class PostRoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", Path(self.tmp.name) / "jobs.sqlite")
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("roles-dual", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _as(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def test_candidate_only_is_rejected_on_every_cabinet_route(self):
        for scopes in ("job:candidate", "job:candidate student", "student"):
            with self.subTest(scopes=scopes), self._as(scopes, "roles-candidate"):
                calls = [
                    self.client.get("/api/v1/cabinet/jobs", headers=AUTH),
                    self.client.post("/api/v1/cabinet/jobs", headers=AUTH, json=AD),
                    self.client.patch("/api/v1/cabinet/jobs/1", headers=AUTH, json=AD),
                    self.client.post("/api/v1/cabinet/jobs/1/close", headers=AUTH),
                    self.client.get("/api/v1/cabinet/applications", headers=AUTH),
                    self.client.patch(
                        "/api/v1/cabinet/applications/1", headers=AUTH, json={"status": "accepted"}
                    ),
                    self.client.get("/api/v1/admin/jobs", headers=AUTH),
                ]
                self.assertEqual([call.status_code for call in calls], [403] * len(calls))
                me = self.client.get("/api/v1/me", headers=AUTH).json()
                self.assertFalse(me["employer"])
                self.assertFalse(me["staff"])

    def test_employer_with_candidate_role_may_post_but_not_moderate(self):
        with self._as("job:employer job:candidate student", "roles-dual"):
            created = self.client.post("/api/v1/cabinet/jobs", headers=AUTH, json=AD)
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(self.client.get("/api/v1/admin/jobs", headers=AUTH).status_code, 403)
            me = self.client.get("/api/v1/me", headers=AUTH).json()
            self.assertTrue(me["employer"])
            self.assertTrue(me["candidate"])

    def test_staff_may_post_and_moderate(self):
        with self._as("job:staff", "roles-staff"):
            self.assertEqual(
                self.client.post("/api/v1/cabinet/jobs", headers=AUTH, json=AD).status_code, 201
            )
            self.assertEqual(self.client.get("/api/v1/admin/jobs", headers=AUTH).status_code, 200)

    def test_guest_gets_401(self):
        self.assertEqual(self.client.post("/api/v1/cabinet/jobs", json=AD).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/admin/jobs").status_code, 401)


if __name__ == "__main__":
    unittest.main()
