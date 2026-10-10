"""POST /api/v1/me/jobs/{id}/tailored-cv — AI tailored CV gates + soft-fail."""

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
    "contact": {
        "full_name": "Aysel",
        "email": "aysel@example.com",
        "phone": "",
        "city": "Baku",
        "country": "AZ",
    },
    "headline": "Backend Developer",
    "summary": "Backend engineer focused on Java APIs.",
    "seniority": "middle",
    "total_years": 5.0,
    "work_history": [
        {
            "title": "Backend Engineer",
            "company": "Fintech Co",
            "start": "2021-01",
            "end": None,
            "summary": "Built Spring payment APIs.",
        },
    ],
    "skills": [
        {"name": "Java", "years": 5, "level": "advanced", "source": "cv"},
        {"name": "Spring", "years": 4, "level": "advanced", "source": "cv"},
    ],
    "languages": [{"code": "en", "name": "English", "level": "fluent"}],
    "education": [{"school": "BSU", "degree": "BSc CS", "year": 2018}],
    "desired_roles": [],
    "preferences": {
        "remote": True,
        "relocation": True,
        "relocation_countries": [],
        "needs_visa_sponsorship": None,
    },
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}

CV_AI = {
    "headline": "Backend Engineer — Java / Spring",
    "summary": "Backend engineer with Java and Spring experience in payments.",
    "skills": ["Java", "Spring"],
    "experience": [
        {
            "title": "Backend Engineer",
            "company": "Fintech Co",
            "dates": "2021-01–present",
            "bullets": ["Built Spring payment APIs."],
        }
    ],
    "education": [{"school": "BSU", "degree": "BSc CS", "dates": "2018"}],
    "languages": ["en (fluent)"],
    "language": "en",
}


class JobTailoredCvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self._seed_skills()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_skills(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            for name in ("Java", "Spring", "React"):
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, '[]', '', '[]', '2026-10-05T12:00:00+00:00')
                    """,
                    (name,),
                )
            conn.commit()

    def _skill_ids(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            return {
                row["canonical_name"]: row["id"]
                for row in conn.execute("SELECT id, canonical_name FROM skill_dictionary")
            }

    def _seed_profile(self, subject: str, *, skills=None, status: str = "confirmed"):
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

    def _insert_job(self, *, title, skills):
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key,
                    remote, relocation, language, category, tech_stack
                ) VALUES (?, ?, ?, ?, 'published', ?, ?, 1, 1, 'en', 'Backend', ?)
                """,
                (
                    title,
                    "Acme",
                    "Berlin",
                    "Looking for Java Spring engineers. Remote ok.",
                    "2026-10-01T12:00:00+00:00",
                    f"norm-{title}",
                    json.dumps(skills),
                ),
            )
            job_id = int(cur.lastrowid)
            for name in skills:
                conn.execute(
                    "INSERT INTO job_skill (job_id, skill_id, source) VALUES (?, ?, 'tech_stack')",
                    (job_id, ids[name]),
                )
            conn.commit()
        return job_id

    def _grant_matching(self, subject: str):
        with self._auth("job:candidate", subject):
            res = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"matching": True},
            )
        self.assertEqual(res.status_code, 200, res.text)

    def test_requires_candidate(self):
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        with self._auth("job:employer", "emp-1"):
            res = self.client.post(
                f"/api/v1/me/jobs/{job_id}/tailored-cv",
                headers=self.headers,
                json={},
            )
        self.assertEqual(res.status_code, 403)

    def test_consent_gate(self):
        subject = "tcv-consent"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        with self._auth("job:candidate", subject):
            res = self.client.post(
                f"/api/v1/me/jobs/{job_id}/tailored-cv?lang=en",
                headers=self.headers,
                json={},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "needs_consent")
        self.assertIsNone(body["cv"])

    def test_skills_gate(self):
        subject = "tcv-skills"
        self._seed_profile(subject, skills=[])
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.post(
                f"/api/v1/me/jobs/{job_id}/tailored-cv?lang=az",
                headers=self.headers,
                json={},
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["status"], "needs_profile")

    def test_job_not_found(self):
        subject = "tcv-404"
        self._seed_profile(subject)
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.post(
                "/api/v1/me/jobs/999999/tailored-cv",
                headers=self.headers,
                json={},
            )
        self.assertEqual(res.status_code, 404)

    def test_flag_off_soft_fail(self):
        subject = "tcv-off"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.job_tailored_cv.tailored_cv_enabled", return_value=False):
                res = self.client.post(
                    f"/api/v1/me/jobs/{job_id}/tailored-cv?lang=en",
                    headers=self.headers,
                    json={},
                )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertIsNone(body["cv"])
        self.assertEqual(body["ai_error"], "job_tailored_cv_disabled")

    def test_ai_pending_schedules_warm(self):
        subject = "tcv-pending"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java", "Spring"])
        self._grant_matching(subject)

        class FakeResult:
            ok = False
            data = None
            error = "ai_pending"

        with self._auth("job:candidate", subject):
            with patch("app.job_tailored_cv.tailored_cv_enabled", return_value=True):
                with patch("app.job_tailored_cv.complete_json", return_value=FakeResult()):
                    with patch(
                        "app.ai_warm.schedule_job_tailored_cv_ai_warm", return_value=True
                    ) as warm:
                        res = self.client.post(
                            f"/api/v1/me/jobs/{job_id}/tailored-cv?lang=az",
                            headers=self.headers,
                            json={},
                        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["ai_pending"])
        warm.assert_called_once()

    def test_cv_from_ai_overlays_contact(self):
        subject = "tcv-ai"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java", "Spring"])
        self._grant_matching(subject)

        class FakeResult:
            ok = True
            data = dict(CV_AI)
            error = ""

        with self._auth("job:candidate", subject):
            with patch("app.job_tailored_cv.tailored_cv_enabled", return_value=True):
                with patch("app.job_tailored_cv.complete_json", return_value=FakeResult()):
                    res = self.client.post(
                        f"/api/v1/me/jobs/{job_id}/tailored-cv?lang=en",
                        headers=self.headers,
                        json={},
                    )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        cv = body["cv"]
        self.assertEqual(cv["full_name"], "Aysel")
        self.assertEqual(cv["contact"]["email"], "aysel@example.com")
        self.assertEqual(cv["contact"]["city"], "Baku")
        self.assertIn("Java", cv["skills"])
        self.assertEqual(cv["experience"][0]["company"], "Fintech Co")
        self.assertFalse(body["ai_pending"])

    def test_prompt_version(self):
        from app.job_tailored_cv import PROMPT_VERSION, _SYSTEM, _build_user, _normalize_cv

        self.assertEqual(PROMPT_VERSION, "job-tailored-cv-v4")
        self.assertIn("Do not invent", _SYSTEM)
        self.assertIn("süni intellekt", _SYSTEM)
        self.assertIn("arxa uç→backend", _SYSTEM)
        self.assertIn("no hollow", _SYSTEM)
        self.assertIn("empty experience", _SYSTEM)
        az = _build_user(
            lang="az",
            profile_version="v1",
            job={
                "id": 1,
                "title": "Java Dev",
                "company": "Acme",
                "city": "",
                "remote": True,
                "relocation": False,
                "text": "Java",
            },
            profile={"preferences": {}},
            have=["Java"],
            missing=[],
        )
        self.assertIn("kunstiq intellekt", az)
        self.assertIn("mentorluq", az)
        dup = _normalize_cv(
            {
                "headline": "Backend",
                "summary": "Test",
                "skills": ["Java"],
                "experience": [],
                "education": [
                    {"school": "HS", "degree": "Bachelor", "dates": "2025"},
                    {"school": "HS", "degree": "Bachelor", "dates": "2025"},
                ],
                "languages": ["az"],
                "language": "az",
            },
            locale="az",
            contact={"full_name": "A", "email": "", "phone": "", "city": "", "country": ""},
        )
        self.assertIsNotNone(dup)
        self.assertEqual(len(dup["education"]), 1)

    def test_independent_of_recommendations_flag(self):
        subject = "tcv-flag"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.product_features.recommendations_enabled", return_value=False):
                with patch("app.job_tailored_cv.tailored_cv_enabled", return_value=False):
                    res = self.client.post(
                        f"/api/v1/me/jobs/{job_id}/tailored-cv",
                        headers=self.headers,
                        json={},
                    )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
