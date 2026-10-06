"""GET/PUT /api/v1/consents (Phase 1.3)."""

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


class ConsentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def test_defaults_are_off_and_copy_is_localized(self):
        with self._auth("job:candidate", "person-1"):
            res = self.client.get("/api/v1/consents?lang=en", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["lang"], "en")
        self.assertEqual(body["version"], "1.0")
        self.assertIn("not legal advice", body["legal_disclaimer"].lower())
        self.assertEqual(body["visibility"], "anonymous")
        kinds = {item["kind"]: item for item in body["consents"]}
        self.assertEqual(set(kinds), {"matching", "emails", "recruiter_visibility"})
        for item in kinds.values():
            self.assertFalse(item["granted"])
            self.assertFalse(item["default_granted"])
            self.assertTrue(item["checkbox_label"])
            self.assertTrue(item["short_help"])
        self.assertEqual(
            {level["id"] for level in body["visibility_levels"]},
            {"hidden", "anonymous", "public"},
        )

    def test_put_persists_grants_visibility_and_audit_fields(self):
        with self._auth("job:candidate", "person-2"):
            saved = self.client.put(
                "/api/v1/consents?lang=az",
                headers={**self.headers, "User-Agent": "consent-test/1"},
                json={
                    "matching": True,
                    "emails": False,
                    "recruiter_visibility": True,
                    "visibility": "public",
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        body = saved.json()
        grants = {item["kind"]: item for item in body["consents"]}
        self.assertTrue(grants["matching"]["granted"])
        self.assertFalse(grants["emails"]["granted"])
        self.assertTrue(grants["recruiter_visibility"]["granted"])
        self.assertEqual(body["visibility"], "public")
        self.assertEqual(grants["matching"]["version"], "1.0")
        self.assertTrue(grants["matching"]["ts"])

        with self._auth("job:candidate", "person-2"):
            again = self.client.get("/api/v1/consents?lang=az", headers=self.headers)
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()["visibility"], "public")
        self.assertTrue(
            {item["kind"]: item["granted"] for item in again.json()["consents"]}["matching"]
        )

        import sqlite3

        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT granted, version, ip, ua FROM consent WHERE user_id = ? AND kind = ?",
                ("person-2", "matching"),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row["granted"]), 1)
            self.assertEqual(row["version"], "1.0")
            self.assertEqual(row["ua"], "consent-test/1")
            vis = conn.execute(
                "SELECT visibility FROM candidate_profile WHERE user_id = ?",
                ("person-2",),
            ).fetchone()
            self.assertEqual(vis["visibility"], "public")

    def test_employer_cannot_read_or_write(self):
        with self._auth("job:employer", "hr-1"):
            denied_get = self.client.get("/api/v1/consents", headers=self.headers)
            denied_put = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"matching": True},
            )
        self.assertEqual(denied_get.status_code, 403)
        self.assertEqual(denied_put.status_code, 403)

    def test_guest_is_unauthorized(self):
        self.assertEqual(self.client.get("/api/v1/consents").status_code, 401)

    def test_me_includes_localized_consents(self):
        with self._auth("job:candidate", "person-me"):
            res = self.client.get("/api/v1/me?lang=en", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        consents = body["consents"]
        self.assertEqual(consents["lang"], "en")
        self.assertEqual(
            {item["kind"] for item in consents["consents"]},
            {"matching", "emails", "recruiter_visibility"},
        )

    def test_invalid_visibility_rejected(self):
        with self._auth("job:candidate", "person-3"):
            bad = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"visibility": "everyone"},
            )
        self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
