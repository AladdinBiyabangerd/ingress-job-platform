"""GET/PUT /api/v1/profile — CV profile review (Phase 1)."""

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


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


SAMPLE = {
    "contact": {"full_name": "Aysel", "email": "aysel@example.com", "phone": "", "city": "", "country": ""},
    "headline": "Backend Developer",
    "seniority": "middle",
    "total_years": 5.5,
    "work_history": [
        {
            "title": "Backend Developer",
            "company": "Acme",
            "start": "2021-03",
            "end": None,
            "location": "",
            "summary": "",
            "skills": ["Java"],
        }
    ],
    "skills": [{"name": "Java", "years": 5, "level": "advanced", "source": "cv"}],
    "languages": [{"code": "en", "level": "B2"}],
    "education": [{"degree": "BSc", "field": "CS", "school": "ADA", "year": 2018}],
    "desired_roles": [],
    "preferences": {
        "remote": None,
        "relocation": None,
        "relocation_countries": [],
        "needs_visa_sponsorship": None,
    },
    "salary_expectation": {"min": None, "currency": None, "period": "year"},
    "parse_meta": {"method": "rules", "confidence": 0.82, "parser_version": "1.0", "source": "upload"},
}


class CvProfileTests(unittest.TestCase):
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

    def _seed_draft(self, subject: str, *, confidence: float = 0.82, status: str = "draft"):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            ensure_cv_queue_tables(conn)
            data = dict(SAMPLE)
            data["parse_meta"] = {**SAMPLE["parse_meta"], "confidence": confidence}
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'anonymous', ?)
                """,
                (
                    subject,
                    "cvs/aysel.pdf",
                    json.dumps(data, ensure_ascii=False),
                    data["headline"],
                    data["seniority"],
                    data["total_years"],
                    status,
                    "rules",
                    confidence,
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.commit()

    def test_empty_profile_for_candidate(self):
        with self._auth("job:candidate", "person-1"):
            res = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["status"], "empty")
        self.assertEqual(body["parse_status"], "none")
        self.assertTrue(body["low_confidence"])

    def test_get_returns_draft_and_low_confidence_fields(self):
        self._seed_draft("person-2", confidence=0.3)
        with self._auth("job:candidate", "person-2"):
            res = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["exists"])
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["headline"], "Backend Developer")
        self.assertEqual(body["profile"]["skills"][0]["name"], "Java")
        self.assertTrue(body["low_confidence"])
        self.assertIn("headline", body["low_confidence_fields"])
        self.assertIn("skills", body["low_confidence_fields"])

    def test_put_edits_skills_and_logs(self):
        self._seed_draft("person-3")
        with self._auth("job:candidate", "person-3"):
            saved = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={
                    "headline": "Senior Backend Developer",
                    "seniority": "senior",
                    "total_years": 6,
                    "profile": {
                        "skills": [
                            {"name": "Java", "years": 6, "level": "advanced", "source": "user"},
                            {"name": "Kafka", "years": 3, "source": "user"},
                        ]
                    },
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        body = saved.json()
        self.assertEqual(body["headline"], "Senior Backend Developer")
        self.assertEqual(body["seniority"], "senior")
        self.assertEqual(body["total_years"], 6)
        self.assertEqual(body["status"], "draft")
        names = [item["name"] for item in body["profile"]["skills"]]
        self.assertEqual(names, ["Java", "Kafka"])

        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute(
                "SELECT action, before_status, after_status FROM profile_edit_log WHERE user_id = ?",
                ("person-3",),
            ).fetchone()
        self.assertIsNotNone(log)
        self.assertEqual(log["action"], "save")
        self.assertEqual(log["before_status"], "draft")
        self.assertEqual(log["after_status"], "draft")

    def test_confirm_sets_status(self):
        self._seed_draft("person-4")
        with self._auth("job:candidate", "person-4"):
            confirmed = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={"confirm": True, "headline": "Backend Developer"},
            )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        with self._auth("job:candidate", "person-4"):
            again = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(again.json()["status"], "confirmed")

        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute(
                "SELECT action, after_status FROM profile_edit_log WHERE user_id = ? ORDER BY id DESC",
                ("person-4",),
            ).fetchone()
        self.assertEqual(log["action"], "confirm")
        self.assertEqual(log["after_status"], "confirmed")

    def test_employer_forbidden_and_guest_unauthorized(self):
        with self._auth("job:employer", "hr-1"):
            denied = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/profile").status_code, 401)

    def test_invalid_seniority_rejected(self):
        self._seed_draft("person-5")
        with self._auth("job:candidate", "person-5"):
            bad = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={"seniority": "god"},
            )
        self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
