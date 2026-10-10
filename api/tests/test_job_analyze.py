"""GET /api/v1/me/jobs/{id}/analyze — deterministic fit + AI soft-fail."""

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
        "city": "",
        "country": "",
    },
    "headline": "Backend Developer",
    "seniority": "middle",
    "total_years": 5.0,
    "work_history": [
        {"title": "Backend Engineer", "company": "Fintech Co"},
    ],
    "skills": [
        {"name": "Java", "years": 5, "level": "advanced", "source": "cv"},
        {"name": "Spring", "years": 4, "level": "advanced", "source": "cv"},
        {"name": "Kafka", "years": 2, "level": "", "source": "cv"},
    ],
    "languages": [{"code": "en", "name": "English"}],
    "education": [],
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


class JobAnalyzeTests(unittest.TestCase):
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
            for name in ("Java", "Spring", "Kafka", "React", "TypeScript"):
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

    def _insert_job(self, *, title, skills, remote=1, relocation=1):
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key,
                    remote, relocation, language, category, tech_stack
                ) VALUES (?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, 'Backend', ?)
                """,
                (
                    title,
                    "Acme",
                    "Berlin",
                    "Looking for Java Spring Kafka. Salary 80k. Remote ok.",
                    "2026-10-01T12:00:00+00:00",
                    f"norm-{title}",
                    remote,
                    relocation,
                    "en",
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
            res = self.client.get(
                f"/api/v1/me/jobs/{job_id}/analyze",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 403)

    def test_consent_gate(self):
        subject = "analyze-consent"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java", "Spring"])
        with self._auth("job:candidate", subject):
            res = self.client.get(
                f"/api/v1/me/jobs/{job_id}/analyze?lang=en",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["gate"], "consent_required")
        self.assertIsNone(body["fit"])

    def test_skills_gate(self):
        subject = "analyze-skills"
        self._seed_profile(subject, skills=[])
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get(
                f"/api/v1/me/jobs/{job_id}/analyze?lang=az",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["gate"], "skills_required")

    def test_job_not_found(self):
        subject = "analyze-404"
        self._seed_profile(subject)
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get(
                "/api/v1/me/jobs/999999/analyze",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 404)

    def test_strong_fit_ok(self):
        subject = "analyze-ok"
        self._seed_profile(subject)
        job_id = self._insert_job(
            title="Senior Java Developer",
            skills=["Java", "Spring", "Kafka"],
        )
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.job_analyze.analyze_enabled", return_value=False):
                res = self.client.get(
                    f"/api/v1/me/jobs/{job_id}/analyze?lang=en",
                    headers=self.headers,
                )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertIsNone(body["gate"])
        self.assertGreater(body["fit"]["score"], 0.4)
        self.assertIn("Java", body["fit"]["have"])
        self.assertEqual(body["ai_error"], "job_analyze_disabled")
        self.assertFalse(body["ai_report"])

    def test_weak_fit_still_ok(self):
        subject = "analyze-weak"
        self._seed_profile(subject)
        job_id = self._insert_job(
            title="React Developer",
            skills=["React", "TypeScript"],
            remote=0,
            relocation=0,
        )
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.job_analyze.analyze_enabled", return_value=False):
                res = self.client.get(
                    f"/api/v1/me/jobs/{job_id}/analyze?lang=en",
                    headers=self.headers,
                )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["fit"]["have"], [])
        self.assertIn("React", body["fit"]["missing"])
        self.assertGreaterEqual(body["fit"]["score"], 0.0)

    def test_ai_pending_schedules_warm(self):
        subject = "analyze-pending"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        self._grant_matching(subject)

        class FakeResult:
            ok = False
            data = None
            error = "ai_pending"

        with self._auth("job:candidate", subject):
            with patch("app.job_analyze.analyze_enabled", return_value=True):
                with patch("app.job_analyze.complete_json", return_value=FakeResult()):
                    with patch(
                        "app.ai_warm.schedule_job_analyze_ai_warm", return_value=True
                    ) as warm:
                        res = self.client.get(
                            f"/api/v1/me/jobs/{job_id}/analyze?lang=az",
                            headers=self.headers,
                        )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["ai_pending"])
        self.assertEqual(body["ai_error"], "ai_pending")
        warm.assert_called_once()

    def test_ai_report_from_cache(self):
        subject = "analyze-ai"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        self._grant_matching(subject)

        class FakeResult:
            ok = True
            data = {
                "summary": "You match the core backend stack for this role well.",
                "skills_matching": ["Java", "Spring"],
                "skills_missing": [],
                "skills_unverified": [],
                "requirements_matching": ["Backend experience"],
                "requirements_missing": ["Kubernetes"],
                "requirements_unverified": [],
                "salary": "80k",
                "location": "Berlin",
                "remote": "yes",
                "visa": "Not stated",
                "relocation": "yes",
                "experiences_to_emphasize": ["Backend Engineer @ Fintech Co"],
                "cv_adapt": ["Lead with Java/Spring projects"],
                "apply_tip": "Mention Kafka production use in the first paragraph.",
            }
            error = ""

        with self._auth("job:candidate", subject):
            with patch("app.job_analyze.analyze_enabled", return_value=True):
                with patch("app.job_analyze.complete_json", return_value=FakeResult()):
                    res = self.client.get(
                        f"/api/v1/me/jobs/{job_id}/analyze?lang=en",
                        headers=self.headers,
                    )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["ai_report"])
        self.assertIn("match the core", body["report"]["summary"])
        self.assertEqual(body["report"]["skills"]["matching"], ["Java", "Spring"])
        # Job seed defaults remote=1, relocation=1 → localized Yes/Yes, not raw "yes".
        self.assertEqual(body["report"]["facts"]["remote"], "Yes")
        self.assertEqual(body["report"]["facts"]["relocation"], "Yes")
        self.assertFalse(body["ai_pending"])

    def test_az_facts_yes_no_localized(self):
        from app.job_analyze import _validate_report

        report = _validate_report(
            {
                "summary": "Sizin AWS bacarığınız bu uzaqdan vəzifəyə uyğundur və əlavə bulud təcrübəsi faydalıdır.",
                "skills_matching": ["AWS"],
                "skills_missing": [],
                "skills_unverified": [],
                "requirements_matching": [],
                "requirements_missing": [],
                "requirements_unverified": [],
                "salary": "",
                "location": "",
                "remote": "yes",
                "visa": "",
                "relocation": "no",
                "experiences_to_emphasize": [],
                "cv_adapt": [],
                "apply_tip": "AWS layihələrinizi vurğulayın.",
            },
            have=["AWS"],
            missing=["Azure"],
            lang="az",
            remote=True,
            relocation=False,
        )
        self.assertIsNotNone(report)
        self.assertEqual(report["facts"]["remote"], "Bəli")
        self.assertEqual(report["facts"]["relocation"], "Xeyr")
        self.assertEqual(report["facts"]["salary"], "Qeyd edilməyib")

    def test_independent_of_recommendations_flag(self):
        subject = "analyze-flag"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Dev", skills=["Java"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.product_features.recommendations_enabled", return_value=False):
                with patch("app.job_analyze.analyze_enabled", return_value=False):
                    res = self.client.get(
                        f"/api/v1/me/jobs/{job_id}/analyze",
                        headers=self.headers,
                    )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["ok"])

    def test_az_user_prompt_requires_orthography(self):
        from app.job_analyze import PROMPT_VERSION, _SYSTEM, _build_ai_user

        self.assertEqual(PROMPT_VERSION, "job-analyze-v3")
        self.assertIn("bacarığınız", _SYSTEM)
        self.assertIn("YesToken", _SYSTEM)
        job = {
            "id": 1,
            "title": "Java Dev",
            "company": "Acme",
            "city": "",
            "salary": "",
            "remote": True,
            "relocation": False,
            "text": "Java",
        }
        fit = {
            "score": 0.5,
            "confidence": 0.5,
            "have": ["Java"],
            "missing": ["Kafka"],
            "components": {"skills": 0.5},
            "job_seniority": "middle",
        }
        az = _build_ai_user(
            lang="az",
            profile_version="v1",
            job=job,
            fit=fit,
            profile={"preferences": {}},
        )
        en = _build_ai_user(
            lang="en",
            profile_version="v1",
            job=job,
            fit=fit,
            profile={"preferences": {}},
        )
        self.assertIn("YesToken: Bəli", az)
        self.assertIn("bacarığınız", az)
        self.assertIn("Siz … sizə", az)
        self.assertIn("YesToken: Yes", en)
        self.assertNotIn("bacarığınız", en)


if __name__ == "__main__":
    unittest.main()
