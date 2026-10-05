"""Academy career-path column on role_taxonomy + skill-gap field."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.academy_paths import academy_career_path_url
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
    "skills": [{"name": "Java", "years": 5, "level": "advanced", "source": "cv"}],
    "languages": [],
    "education": [],
    "desired_roles": [],
    "preferences": {"remote": True, "relocation": True, "relocation_countries": [], "needs_visa_sponsorship": None},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class AcademyPathsUnitTests(unittest.TestCase):
    def test_career_path_url(self):
        href = academy_career_path_url("devops-engineer-path", utm_medium="digest")
        self.assertTrue(
            href.startswith("https://ingress.academy/career-paths/devops-engineer-path/?")
        )
        self.assertIn("utm_source=ingress_job", href)
        self.assertIn("utm_medium=digest", href)
        self.assertIn("utm_campaign=academy_cross_sell", href)
        self.assertEqual(academy_career_path_url(""), "")


class SkillGapCareerPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        with sqlite3.connect(self.db) as conn:
            for name in ("Java", "Spring", "Kafka"):
                conn.execute(
                    """
                    INSERT INTO skill_dictionary
                      (canonical_name, synonyms, category_hint, academy_course_ids, updated_at)
                    VALUES (?, '[]', '', '[]', '2026-10-05T12:00:00+00:00')
                    """,
                    (name,),
                )
            conn.commit()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _skill_ids(self):
        with sqlite3.connect(self.db) as conn:
            return {
                row[0]: row[1]
                for row in conn.execute("SELECT canonical_name, id FROM skill_dictionary")
            }

    def _seed_profile(self, subject: str):
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
                    json.dumps(SAMPLE, ensure_ascii=False),
                    SAMPLE["headline"],
                    SAMPLE["seniority"],
                    SAMPLE["total_years"],
                    "confirmed",
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

    def test_skill_gap_reads_career_path_from_db(self):
        subject = "path-1"
        self._seed_profile(subject)
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO role_taxonomy (
                    canonical_name, category, synonyms, academy_career_path_id, updated_at
                ) VALUES ('Java Developer', 'Backend', '[]', 'ai-native-java-muhendisi', 't')
                """
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Java Developer'"
            ).fetchone()[0]
            for name, weight in (("Java", 1.0), ("Spring", 0.8), ("Kafka", 0.4)):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (role_id, ids[name], weight),
                )
            conn.commit()
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get(
                "/api/v1/me/skill-gap?role=Java%20Developer&lang=en",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["academy_career_path"], "ai-native-java-muhendisi")


if __name__ == "__main__":
    unittest.main()
