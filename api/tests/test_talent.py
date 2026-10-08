"""Employer talent search (browse-only)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.main import app
from app.profiles import save_candidate_profile, save_profile


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


SAMPLE = {
    "headline": "Backend engineer",
    "seniority": "middle",
    "total_years": 4,
    "contact": {"city": "Baki", "country": "AZ"},
    "skills": [{"name": "Python"}, {"name": "FastAPI"}],
}


class TalentTests(unittest.TestCase):
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
        save_profile("talent-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_candidate(
        self,
        subject: str,
        *,
        visibility: str = "anonymous",
        status: str = "confirmed",
        consent: bool = True,
        headline: str = "Backend engineer",
    ):
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            data = dict(SAMPLE)
            data["headline"] = headline
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, '', ?, ?, ?, ?, ?, 'rules', 0.8, ?, ?)
                """,
                (
                    subject,
                    json.dumps(data, ensure_ascii=False),
                    headline,
                    data["seniority"],
                    data["total_years"],
                    status,
                    visibility,
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.commit()
        if consent:
            with self._auth("job:candidate", subject):
                res = self.client.put(
                    "/api/v1/consents",
                    headers=self.headers,
                    json={"recruiter_visibility": True, "visibility": visibility},
                )
            self.assertEqual(res.status_code, 200, res.text)
        save_candidate_profile(subject, "Aysel Test", "+994501112233", "aysel@example.com")

    def test_guest_and_candidate_forbidden(self):
        guest = self.client.get("/api/v1/talent")
        self.assertEqual(guest.status_code, 401)
        with self._auth("job:candidate", "cand-only"):
            denied = self.client.get("/api/v1/talent", headers=self.headers)
        self.assertEqual(denied.status_code, 403)

    def test_employer_needs_company_profile(self):
        with self._auth("job:employer", "bare-employer"):
            denied = self.client.get("/api/v1/talent", headers=self.headers)
        self.assertEqual(denied.status_code, 403)

    def test_search_respects_consent_visibility_and_redaction(self):
        self._seed_candidate("vis-anon", visibility="anonymous", consent=True)
        self._seed_candidate("vis-public", visibility="public", consent=True, headline="Public Python")
        self._seed_candidate("vis-hidden", visibility="hidden", consent=True)
        self._seed_candidate("no-consent", visibility="anonymous", consent=False)
        self._seed_candidate("draft-only", visibility="anonymous", consent=True, status="draft")

        with self._auth("job:employer", "talent-employer"):
            res = self.client.get("/api/v1/talent", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        headlines = {item["headline"] for item in body["items"]}
        self.assertIn("Backend engineer", headlines)
        self.assertIn("Public Python", headlines)
        self.assertNotIn("hidden", {item["visibility"] for item in body["items"]})
        self.assertEqual(body["total"], 2)

        anon = next(item for item in body["items"] if item["visibility"] == "anonymous")
        self.assertNotIn("display_name", anon)
        self.assertIn("Python", anon["skills"])
        self.assertEqual(anon["city"], "Baki")

        public = next(item for item in body["items"] if item["visibility"] == "public")
        self.assertEqual(public["display_name"], "Aysel Test")
        self.assertNotIn("phone", public)
        self.assertNotIn("email", public)
        self.assertNotIn("user_id", public)

        with self._auth("job:employer", "talent-employer"):
            filtered = self.client.get("/api/v1/talent?q=Public", headers=self.headers)
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()["total"], 1)
        self.assertEqual(filtered.json()["items"][0]["headline"], "Public Python")


if __name__ == "__main__":
    unittest.main()
