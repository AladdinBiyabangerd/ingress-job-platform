"""GET /api/v1/me/matches + feedback — structured scoring (Phase 2)."""

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
from app.matching import detect_job_seniority, seniority_score


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
        {"name": "Kafka", "years": 2, "level": "", "source": "cv"},
    ],
    "languages": [{"code": "en", "name": "English"}],
    "education": [],
    "desired_roles": [],
    "preferences": {"remote": True, "relocation": True, "relocation_countries": [], "needs_visa_sponsorship": None},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class MatchingTests(unittest.TestCase):
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
                    INSERT INTO skill_dictionary (canonical_name, synonyms, category_hint, academy_course_ids, updated_at)
                    VALUES (?, '[]', '', '[]', '2026-10-05T12:00:00+00:00')
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

    def _seed_profile(self, subject: str, *, skills=None, prefs=None, status: str = "confirmed"):
        data = dict(SAMPLE)
        if skills is not None:
            data["skills"] = skills
        if prefs is not None:
            data["preferences"] = prefs
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

    def _insert_job(self, *, title, skills, remote=1, relocation=1, language="en", created_at="2026-10-01T12:00:00+00:00"):
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
                    "Java Spring Kafka role",
                    created_at,
                    f"norm-{title}-{created_at}",
                    remote,
                    relocation,
                    language,
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

    def test_detect_seniority_from_title(self):
        self.assertEqual(detect_job_seniority("Senior Java Developer"), "senior")
        self.assertEqual(detect_job_seniority("Junior React Engineer"), "junior")
        self.assertEqual(seniority_score("middle", "senior"), 0.6)
        self.assertEqual(seniority_score("senior", "senior"), 1.0)

    def test_ranks_overlapping_job_higher(self):
        subject = "match-1"
        self._seed_profile(subject)
        java_id = self._insert_job(title="Senior Java Developer", skills=["Java", "Spring", "Kafka"])
        react_id = self._insert_job(title="React Developer", skills=["React", "TypeScript"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/matches?lang=en&limit=10", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["matching_consent"])
        self.assertFalse(body["ai_rerank"])
        ids = [item["job_id"] for item in body["matches"]]
        self.assertIn(java_id, ids)
        self.assertNotIn(react_id, ids)  # zero skill overlap skipped
        top = body["matches"][0]
        self.assertEqual(top["job_id"], java_id)
        self.assertGreater(top["score"], 0.4)
        self.assertIn("Java", top["have"])
        self.assertIn("skills match", top["explanation"])
        self.assertIn("Remote", top["explanation"])

    def test_no_matching_consent_returns_empty(self):
        subject = "match-2"
        self._seed_profile(subject)
        self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/matches", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["matching_consent"])
        self.assertEqual(body["matches"], [])

    def test_feedback_up_and_down(self):
        subject = "match-fb"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            up = self.client.post(
                f"/api/v1/me/matches/{job_id}/feedback",
                headers=self.headers,
                json={"vote": "up"},
            )
            self.assertEqual(up.status_code, 200, up.text)
            self.assertEqual(up.json()["vote"], "up")
            down = self.client.post(
                f"/api/v1/me/matches/{job_id}/feedback",
                headers=self.headers,
                json={"vote": "down", "reason": "location"},
            )
            self.assertEqual(down.status_code, 200, down.text)
            self.assertEqual(down.json()["reason"], "location")
            listed = self.client.get("/api/v1/me/matches", headers=self.headers)
        self.assertEqual(listed.status_code, 200, listed.text)
        # Down-vote ×0.4 often pushes below For-you MIN_SCORE — job leaves the list.
        listed_ids = {item["job_id"] for item in listed.json()["matches"]}
        self.assertNotIn(job_id, listed_ids)

    def test_feedback_requires_consent(self):
        subject = "match-fb-consent"
        self._seed_profile(subject)
        job_id = self._insert_job(title="Java Developer", skills=["Java"])
        with self._auth("job:candidate", subject):
            res = self.client.post(
                f"/api/v1/me/matches/{job_id}/feedback",
                headers=self.headers,
                json={"vote": "up"},
            )
        self.assertEqual(res.status_code, 403)

    def test_employer_forbidden(self):
        with self._auth("job:employer", "match-emp"):
            res = self.client.get("/api/v1/me/matches", headers=self.headers)
        self.assertEqual(res.status_code, 403)

    def test_skill_gap_for_role(self):
        subject = "gap-1"
        self._seed_profile(
            subject,
            skills=[
                {"name": "Java", "years": 5, "level": "", "source": "cv"},
                {"name": "Spring", "years": 3, "level": "", "source": "cv"},
            ],
        )
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('Java Developer', 'Backend', '[]', '2026-10-05T12:00:00+00:00')
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
        self.assertEqual(body["role"], "Java Developer")
        self.assertEqual([x["name"] for x in body["have"]], ["Java", "Spring"])
        self.assertEqual([x["name"] for x in body["missing"]], ["Kafka"])
        self.assertIn("Learn next: Kafka", body["explanation"])

    def test_ensure_match_tables_is_cached(self):
        from app.matching import _MATCH_ENSURED, ensure_match_tables

        with sqlite3.connect(self.db) as conn:
            ensure_match_tables(conn)
            self.assertIn(str(self.db), _MATCH_ENSURED)
            before = len(_MATCH_ENSURED)
            ensure_match_tables(conn)
            self.assertEqual(len(_MATCH_ENSURED), before)

    def test_matches_reuse_catalog_until_jobs_change(self):
        from app.matching import _MATCH_JOBS_MEMO, _load_match_catalog

        subject = "match-cache"
        self._seed_profile(subject)
        first_id = self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        self._grant_matching(subject)
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            jobs, _skills = _load_match_catalog(conn)
            self.assertEqual({job["id"] for job in jobs}, {first_id})
            memo = _MATCH_JOBS_MEMO
            self.assertIsNotNone(memo)
            again, _skills = _load_match_catalog(conn)
            self.assertIs(_MATCH_JOBS_MEMO, memo)
            self.assertEqual([job["id"] for job in again], [job["id"] for job in jobs])
        second_id = self._insert_job(title="Kafka Engineer", skills=["Java", "Kafka"])
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            refreshed, _skills = _load_match_catalog(conn)
        self.assertEqual({job["id"] for job in refreshed}, {first_id, second_id})

    def test_skill_gap_resolves_role_synonym(self):
        subject = "gap-syn"
        self._seed_profile(
            subject,
            skills=[{"name": "Java", "years": 5, "level": "", "source": "cv"}],
        )
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('Java Developer', 'Backend', ?, '2026-10-05T12:00:00+00:00')
                """,
                (json.dumps(["Java Dev"]),),
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Java Developer'"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, 1.0)",
                (role_id, ids["Java"]),
            )
            conn.commit()
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get(
                "/api/v1/me/skill-gap?role=Java%20Dev&lang=en",
                headers=self.headers,
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["role"], "Java Developer")
        self.assertEqual([x["name"] for x in res.json()["have"]], ["Java"])

    def test_matches_role_scopes_to_signature_skills(self):
        subject = "match-role"
        # Kafka years high enough that a Kafka-only ad clears the 0.33 floor.
        self._seed_profile(
            subject,
            skills=[
                {"name": "Java", "years": 5, "level": "advanced", "source": "cv"},
                {"name": "Spring", "years": 4, "level": "advanced", "source": "cv"},
                {"name": "Kafka", "years": 5, "level": "", "source": "cv"},
            ],
        )
        java_id = self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        # Profile overlap (Kafka) but outside role signature — drop when role=.
        kafka_id = self._insert_job(title="Kafka Engineer", skills=["Kafka"])
        ids = self._skill_ids()
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('Java Developer', 'Backend', '[]', '2026-10-05T12:00:00+00:00')
                """
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Java Developer'"
            ).fetchone()[0]
            for name, weight in (("Java", 1.0), ("Spring", 0.8)):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (role_id, ids[name], weight),
                )
            conn.commit()
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            plain = self.client.get(
                "/api/v1/me/matches?lang=en&limit=10", headers=self.headers
            )
            scoped = self.client.get(
                "/api/v1/me/matches?lang=en&limit=10&role=Java%20Developer",
                headers=self.headers,
            )
        self.assertEqual(plain.status_code, 200, plain.text)
        self.assertEqual(scoped.status_code, 200, scoped.text)
        plain_ids = {item["job_id"] for item in plain.json()["matches"]}
        scoped_body = scoped.json()
        scoped_ids = {item["job_id"] for item in scoped_body["matches"]}
        self.assertEqual(scoped_body.get("role"), "Java Developer")
        self.assertIn(java_id, plain_ids)
        self.assertIn(kafka_id, plain_ids)
        self.assertIn(java_id, scoped_ids)
        self.assertNotIn(kafka_id, scoped_ids)
        top = scoped_body["matches"][0]
        self.assertEqual(top["job_id"], java_id)
        self.assertGreaterEqual(int(top.get("role_skill_hits") or 0), 1)

    def test_matches_independent_of_recommendations_hub(self):
        subject = "match-ungate"
        self._seed_profile(subject)
        self._insert_job(title="Java Developer", skills=["Java", "Spring"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            with patch("app.product_features.recommendations_enabled", return_value=False):
                res = self.client.get("/api/v1/me/matches?lang=en", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertGreaterEqual(len(res.json()["matches"]), 1)

    def test_hunt_unknown_salary_and_visa_do_not_inflate(self):
        from app.hunt_scoring import compute_score, salary_fit, work_authorization_fit

        self.assertIsNone(salary_fit({}, "45,000–55,000 GBP per annum"))
        self.assertIsNone(salary_fit({"min": 50000, "currency": "GBP", "period": "year"}, ""))
        self.assertIsNone(work_authorization_fit({"needs_visa_sponsorship": None}, relocation=True))
        self.assertIsNone(work_authorization_fit({"needs_visa_sponsorship": False}, relocation=True))
        hunt = compute_score(
            {
                "tech_skill_fit": 1.0,
                "role_seniority_fit": None,
                "preference_fit": None,
                "salary_fit": None,
                "work_authorization_fit": None,
                "freshness": 1.0,
                "data_completeness": 1.0,
                "experience_fit": None,
            }
        )
        # Only 35+5+5 known → confidence 0.45; salary/visa add nothing.
        self.assertEqual(hunt["confidence"], 0.45)
        self.assertAlmostEqual(hunt["score"], 0.45, places=4)
        by_name = {d["name"]: d for d in hunt["dimensions"]}
        self.assertEqual(by_name["salary_fit"]["status"], "unknown")
        self.assertEqual(by_name["work_authorization_fit"]["status"], "unknown")

    def test_hunt_arithmetic_parity(self):
        from app.hunt_scoring import SCORING_VERSION, compute_score

        hunt = compute_score(
            {
                "tech_skill_fit": 1.0,
                "role_seniority_fit": 0.6,
                "preference_fit": 1.0,
                "salary_fit": None,
                "work_authorization_fit": None,
                "freshness": 0.7,
                "data_completeness": 0.875,
                "experience_fit": None,
            }
        )
        # (35 + 9 + 10 + 3.5 + 4.375) / 100
        self.assertAlmostEqual(hunt["score"], 0.6188, places=4)
        self.assertEqual(hunt["confidence"], 0.7)
        self.assertEqual(hunt["scoring_version"], SCORING_VERSION)
        self.assertEqual(SCORING_VERSION, "hunt-ingress-v3")

    def test_list_floor_and_confidence_guard(self):
        from app.hunt_scoring import MIN_CONFIDENCE, MIN_SCORE, passes_list_gates

        self.assertTrue(passes_list_gates(MIN_SCORE, MIN_CONFIDENCE))
        self.assertFalse(passes_list_gates(MIN_SCORE - 0.01, 0.9))
        self.assertFalse(passes_list_gates(0.9, MIN_CONFIDENCE - 0.01))

    def test_matches_expose_hunt_fields_and_respect_floor(self):
        subject = "match-hunt"
        self._seed_profile(subject)
        good_id = self._insert_job(title="Senior Java Developer", skills=["Java", "Spring", "Kafka"])
        # Partial skill overlap + junior title → lower Hunt score; still may pass.
        self._insert_job(title="Intern Kafka Helper", skills=["Kafka"], remote=0, relocation=0)
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/matches?lang=en&limit=20", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body.get("scoring_version"), "hunt-ingress-v3")
        self.assertEqual(body.get("min_score"), 0.33)
        self.assertEqual(body.get("min_confidence"), 0.35)
        self.assertTrue(body["matches"])
        for item in body["matches"]:
            self.assertGreaterEqual(item["score"], 0.33)
            self.assertGreaterEqual(item["confidence"], 0.35)
            self.assertEqual(item["score_pct"], int(round(float(item["score"]) * 100)))
            self.assertIn("dimensions", item)
            salary_dim = next(d for d in item["dimensions"] if d["name"] == "salary_fit")
            self.assertEqual(salary_dim["status"], "unknown")
        ids = [item["job_id"] for item in body["matches"]]
        self.assertIn(good_id, ids)

    def test_soft_skip_below_half_skill_overlap(self):
        subject = "match-soft-half"
        self._seed_profile(subject)
        # Candidate has Java/Spring/Kafka — 1/3 overlap (< 0.5) must not list.
        weak_id = self._insert_job(title="React Kafka Mix", skills=["React", "TypeScript", "Kafka"])
        strong_id = self._insert_job(title="Java Spring Dev", skills=["Java", "Spring"])
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/matches?lang=en&limit=20", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        ids = [item["job_id"] for item in res.json()["matches"]]
        self.assertNotIn(weak_id, ids)
        self.assertIn(strong_id, ids)

    def test_single_skill_match_fails_floor_without_other_dims(self):
        """1 matched skill is half-weighted; skills+fresh+complete alone < 0.33."""
        from app.hunt_scoring import MIN_SCORE, compute_score, passes_list_gates

        # effective tech = 1.0 * 0.5 = 0.5 after dampen
        hunt = compute_score(
            {
                "tech_skill_fit": 0.5,
                "role_seniority_fit": None,
                "preference_fit": None,
                "salary_fit": None,
                "work_authorization_fit": None,
                "freshness": 1.0,
                "data_completeness": 1.0,
                "experience_fit": None,
            }
        )
        self.assertAlmostEqual(hunt["score"], 0.275, places=4)
        self.assertLess(hunt["score"], MIN_SCORE)
        self.assertFalse(passes_list_gates(hunt["score"], hunt["confidence"]))

    def test_two_skill_full_overlap_clears_higher_pct(self):
        subject = "match-two-skill"
        self._seed_profile(subject)
        job_id = self._insert_job(
            title="Java Spring Developer",
            skills=["Java", "Spring"],
            created_at="2026-10-10T12:00:00+00:00",
        )
        self._grant_matching(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/matches?lang=en&limit=20", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        matches = res.json()["matches"]
        hit = next(m for m in matches if m["job_id"] == job_id)
        # v3: strong skill overlap should land well above the old ~33% floor.
        self.assertGreaterEqual(hit["score_pct"], 45)
        self.assertEqual(hit["score_pct"], int(round(float(hit["score"]) * 100)))


if __name__ == "__main__":
    unittest.main()
