"""GET /api/v1/me/roles — deterministic role suggestions (Phase 1)."""

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
    "total_years": 5.0,
    "work_history": [],
    "skills": [
        {"name": "Java", "years": 5, "level": "advanced", "source": "cv"},
        {"name": "Spring", "years": 4, "level": "advanced", "source": "cv"},
    ],
    "languages": [],
    "education": [],
    "desired_roles": [],
    "preferences": {},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class RoleSuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self._seed_taxonomy()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_taxonomy(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            skills = [
                ("Java", '["java"]'),
                ("Spring", '["spring boot"]'),
                ("SQL", "[]"),
                ("Kafka", "[]"),
                ("PostgreSQL", "[]"),
                ("React", "[]"),
                ("TypeScript", "[]"),
            ]
            for name, synonyms in skills:
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (canonical_name, synonyms, category_hint, academy_course_ids, updated_at)
                    VALUES (?, ?, '', '[]', '2026-10-05T12:00:00+00:00')
                    """,
                    (name, synonyms),
                )
            ids = {
                row["canonical_name"]: row["id"]
                for row in conn.execute("SELECT id, canonical_name FROM skill_dictionary")
            }
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES (?, ?, '[]', '2026-10-05T12:00:00+00:00')
                """,
                ("Java Developer", "Backend"),
            )
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES (?, ?, '[]', '2026-10-05T12:00:00+00:00')
                """,
                ("React Developer", "Frontend"),
            )
            java_role = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = ?",
                ("Java Developer",),
            ).fetchone()["id"]
            react_role = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = ?",
                ("React Developer",),
            ).fetchone()["id"]
            for skill, weight in (
                ("Java", 1.0),
                ("Spring", 0.8),
                ("SQL", 0.4),
                ("Kafka", 0.4),
                ("PostgreSQL", 0.3),
            ):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (java_role, ids[skill], weight),
                )
            for skill, weight in (("React", 1.0), ("TypeScript", 0.8)):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (react_role, ids[skill], weight),
                )
            conn.commit()

    def _seed_profile(self, subject: str, *, skills=None, status: str = "draft"):
        data = dict(SAMPLE)
        if skills is not None:
            data["skills"] = skills
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
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
                    0.8,
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.commit()

    def _grant_matching(self, subject: str):
        with self._auth("job:candidate", subject):
            res = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"matching": True},
            )
        self.assertEqual(res.status_code, 200, res.text)

    def test_suggests_java_developer_above_react(self):
        subject = "roles-1"
        self._seed_profile(subject)
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/roles?lang=en", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["matching_consent"])
        self.assertEqual(body["skill_count"], 2)
        self.assertEqual(body["profile_status"], "draft")
        names = [item["canonical_name"] for item in body["roles"]]
        self.assertEqual(names[0], "Java Developer")
        self.assertNotIn("React Developer", names)
        top = body["roles"][0]
        self.assertGreater(top["score"], 0.5)
        self.assertEqual(top["have"], ["Java", "Spring"])
        self.assertIn("Kafka", top["missing"])
        self.assertIn("You have: Java, Spring", top["explanation"])
        self.assertIn("Missing:", top["explanation"])

    def test_synonym_resolves_to_canonical(self):
        subject = "roles-syn"
        self._seed_profile(
            subject,
            skills=[{"name": "spring boot", "years": 3, "level": "", "source": "user"}],
        )
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/roles", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        roles = res.json()["roles"]
        self.assertTrue(roles)
        self.assertEqual(roles[0]["canonical_name"], "Java Developer")
        self.assertEqual(roles[0]["have"], ["Spring"])

    def test_no_matching_consent_returns_empty(self):
        subject = "roles-2"
        self._seed_profile(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/roles", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["matching_consent"])
        self.assertEqual(body["roles"], [])
        self.assertEqual(body["skill_count"], 2)

    def test_no_profile_returns_empty(self):
        subject = "roles-empty"
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/roles", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["matching_consent"])
        self.assertEqual(body["roles"], [])
        self.assertEqual(body["profile_status"], "empty")

    def test_empty_skills_returns_empty(self):
        subject = "roles-noskills"
        self._seed_profile(subject, skills=[])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/roles", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["roles"], [])

    def test_employer_forbidden(self):
        with self._auth("job:employer", "roles-emp"):
            res = self.client.get("/api/v1/me/roles", headers=self.headers)
        self.assertEqual(res.status_code, 403)


if __name__ == "__main__":
    unittest.main()
