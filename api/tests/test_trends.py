"""GET /api/v1/trends + skill-gap share enrichment (plan §7.1 / §7.2)."""

from __future__ import annotations

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
from app.trends import (
    MIN_ADS_FOR_GROWTH,
    MIN_PAIR_BASE_ADS,
    MIN_SALARY_SAMPLES,
    combine_salary_days,
    ensure_trend_tables,
    growth_wow,
    trends_payload,
)


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


PROFILE = {
    "contact": {},
    "links": {},
    "headline": "Backend",
    "seniority": "middle",
    "total_years": 5.0,
    "work_history": [],
    "skills": [{"name": "Java", "years": 5, "level": "", "source": "cv"}],
    "languages": [],
    "education": [],
    "desired_roles": [],
    "preferences": {},
    "salary_expectation": {},
    "parse_meta": {},
}


class TrendsTests(unittest.TestCase):
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
            for name in ("Java", "Spring", "Kafka", "React"):
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, '[]', '', '[]', '2026-10-05T12:00:00+00:00')
                    """,
                    (name,),
                )
            conn.commit()

    def _skill_ids(self) -> dict[str, int]:
        with sqlite3.connect(self.db) as conn:
            return {
                row[0]: int(row[1])
                for row in conn.execute(
                    "SELECT canonical_name, id FROM skill_dictionary"
                )
            }

    def _insert_job(self, *, title: str, day: str, category: str = "Backend") -> int:
        with sqlite3.connect(self.db) as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key,
                    category, remote, relocation, hidden
                ) VALUES (?, 'Co', '', '', 'published', ?, ?, ?, 1, 0, 0)
                """,
                (title, f"{day}T10:00:00+00:00", f"{title}-{day}", category),
            )
            job_id = int(cur.lastrowid)
            conn.commit()
            return job_id

    def _seed_trend_rows(self):
        ids = self._skill_ids()
        for i in range(40):
            day = "2026-10-05" if i < 30 else "2026-09-28"
            self._insert_job(title=f"Job{i}", day=day)
        with sqlite3.connect(self.db) as conn:
            rows = [
                ("2026-10-05", ids["Java"], "Backend", 30),
                ("2026-10-05", ids["Kafka"], "Backend", 12),
                ("2026-09-28", ids["Java"], "Backend", 20),
                ("2026-09-28", ids["Kafka"], "Backend", 10),
                ("2026-10-05", ids["React"], "Frontend", 8),
            ]
            for day, skill_id, category, ad_count in rows:
                conn.execute(
                    """
                    INSERT INTO skill_trend_daily (
                        day, skill_id, category, region, remote, relocation, ad_count
                    ) VALUES (?, ?, ?, '', 1, 0, ?)
                    """,
                    (day, skill_id, category, ad_count),
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

    def test_growth_wow_suppressed_below_min_ads(self):
        self.assertIsNone(growth_wow(0.5, 0.4, ad_count=MIN_ADS_FOR_GROWTH - 1))
        value = growth_wow(0.5, 0.4, ad_count=MIN_ADS_FOR_GROWTH)
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, (0.5 - 0.4) / 0.4, places=3)

    def test_combine_salary_days_requires_min_samples(self):
        few = [
            {"median": 50000, "currency": "GBP", "n": MIN_SALARY_SAMPLES - 1, "low": 40_000, "high": 60_000}
        ]
        self.assertIsNone(combine_salary_days(few))
        enough = [
            {
                "median": 50000,
                "currency": "GBP",
                "n": MIN_SALARY_SAMPLES,
                "low": 40_000,
                "high": 60_000,
            }
        ]
        combined = combine_salary_days(enough)
        self.assertIsNotNone(combined)
        self.assertEqual(combined["currency"], "GBP")
        self.assertEqual(combined["n"], MIN_SALARY_SAMPLES)
        self.assertEqual(combined["median"], 50000.0)

    def test_public_trends_endpoint(self):
        self._seed_trend_rows()
        res = self.client.get("/api/v1/trends?category=Backend&lang=en&window_days=7")
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["items"])
        self.assertIn("disclaimer", body)
        self.assertIn("Ingress Job", body["disclaimer"])
        names = [item["name"] for item in body["items"]]
        self.assertIn("Java", names)
        self.assertNotIn("React", names)  # filtered by category
        java = next(item for item in body["items"] if item["name"] == "Java")
        self.assertGreater(java["share"], 0)
        self.assertIsNotNone(java["growth_wow"])  # ad_count 30 >= 20
        kafka = next(item for item in body["items"] if item["name"] == "Kafka")
        self.assertIsNone(kafka["growth_wow"])  # ad_count 12 < 20

    def test_trends_payload_share_math(self):
        self._seed_trend_rows()
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            payload = trends_payload(
                conn, category="Backend", window_days=7, lang="en"
            )
        java = next(item for item in payload["items"] if item["name"] == "Java")
        # 30 skill ads / 30 Backend jobs on 2026-10-05 in the 7d window
        self.assertGreater(java["share"], 0.5)

    def test_trends_payload_salary_signal(self):
        ids = self._skill_ids()
        self._insert_job(title="SalJob", day="2026-10-05", category="Backend")
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO skill_trend_daily (
                    day, skill_id, category, region, remote, relocation, ad_count,
                    salary_median, salary_currency, salary_n, salary_low, salary_high
                ) VALUES (?, ?, 'Backend', '', 1, 0, 10, 55000, 'GBP', ?, 40000, 70000)
                """,
                ("2026-10-05", ids["Java"], MIN_SALARY_SAMPLES),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            payload = trends_payload(
                conn, category="Backend", window_days=7, lang="en"
            )
        java = next(item for item in payload["items"] if item["name"] == "Java")
        self.assertIsNotNone(java["salary"])
        self.assertEqual(java["salary"]["currency"], "GBP")
        self.assertEqual(java["salary"]["n"], MIN_SALARY_SAMPLES)
        self.assertEqual(java["salary"]["median"], 55000.0)
        self.assertEqual(java["salary"]["period"], "year")

    def test_trends_often_with_companions(self):
        ids = self._skill_ids()
        # Seed enough Java ads in the window for MIN_PAIR_BASE_ADS.
        for i in range(MIN_PAIR_BASE_ADS):
            self._insert_job(title=f"PairJob{i}", day="2026-10-05", category="Backend")
        with sqlite3.connect(self.db) as conn:
            ensure_trend_tables(conn)
            conn.execute(
                """
                INSERT INTO skill_trend_daily (
                    day, skill_id, category, region, remote, relocation, ad_count
                ) VALUES ('2026-10-05', ?, 'Backend', '', 1, 0, ?)
                """,
                (ids["Java"], MIN_PAIR_BASE_ADS),
            )
            # 6 of those Java ads also want Kafka → share 0.6
            conn.execute(
                """
                INSERT INTO skill_pair_daily (
                    day, base_skill_id, pair_skill_id, category, co_ad_count
                ) VALUES ('2026-10-05', ?, ?, 'Backend', 6)
                """,
                (ids["Java"], ids["Kafka"]),
            )
            conn.commit()
            conn.row_factory = sqlite3.Row
            payload = trends_payload(
                conn, category="Backend", window_days=7, lang="en"
            )
        java = next(item for item in payload["items"] if item["name"] == "Java")
        self.assertTrue(java["often_with"])
        top = java["often_with"][0]
        self.assertEqual(top["name"], "Kafka")
        self.assertAlmostEqual(top["share"], 0.6, places=3)
        self.assertEqual(top["co_ad_count"], 6)

    def test_skill_gap_gets_share_when_trends_present(self):
        ids = self._skill_ids()
        subject = "gap-trends"
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, 'Backend', 'middle', 5, 'confirmed', 'rules', 0.9, 'anonymous', ?)
                """,
                (
                    subject,
                    "cvs/gap.pdf",
                    json.dumps(PROFILE, ensure_ascii=False),
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('Java Developer', 'Backend', '[]', '2026-10-05T12:00:00+00:00')
                """
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Java Developer'"
            ).fetchone()[0]
            for name, weight in (("Java", 1.0), ("Kafka", 0.5)):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (role_id, ids[name], weight),
                )
            conn.execute(
                """
                INSERT INTO skill_trend_daily (
                    day, skill_id, category, region, remote, relocation, ad_count
                ) VALUES ('2026-10-05', ?, 'Backend', '', 1, 0, 25)
                """,
                (ids["Kafka"],),
            )
            conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, category, hidden
                ) VALUES (
                    'Backend', 'Co', '', '', 'published', '2026-10-05T10:00:00+00:00',
                    'b1', 'Backend', 0
                )
                """
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
        self.assertEqual(body["source"], "role_skill_weight+skill_trend_daily")
        missing = {item["name"]: item for item in body["missing"]}
        self.assertIn("Kafka", missing)
        self.assertIsNotNone(missing["Kafka"]["share"])
        self.assertGreater(missing["Kafka"]["share"], 0)

    def test_skill_gap_often_with_from_pairs(self):
        ids = self._skill_ids()
        subject = "gap-pairs"
        for i in range(MIN_PAIR_BASE_ADS):
            self._insert_job(title=f"GapPair{i}", day="2026-10-05", category="Backend")
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            ensure_trend_tables(conn)
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, 'Backend', 'middle', 5, 'confirmed', 'rules', 0.9, 'anonymous', ?)
                """,
                (
                    subject,
                    "cvs/gap-pairs.pdf",
                    json.dumps(PROFILE, ensure_ascii=False),
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('Java Developer', 'Backend', '[]', '2026-10-05T12:00:00+00:00')
                """
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Java Developer'"
            ).fetchone()[0]
            for name, weight in (("Java", 1.0), ("Kafka", 0.5)):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (role_id, ids[name], weight),
                )
            conn.execute(
                """
                INSERT INTO skill_trend_daily (
                    day, skill_id, category, region, remote, relocation, ad_count
                ) VALUES
                    ('2026-10-05', ?, 'Backend', '', 1, 0, ?),
                    ('2026-10-05', ?, 'Backend', '', 1, 0, 4)
                """,
                (ids["Java"], MIN_PAIR_BASE_ADS, ids["Kafka"]),
            )
            conn.execute(
                """
                INSERT INTO skill_pair_daily (
                    day, base_skill_id, pair_skill_id, category, co_ad_count
                ) VALUES ('2026-10-05', ?, ?, 'Backend', 4)
                """,
                (ids["Java"], ids["Kafka"]),
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
        missing = {item["name"]: item for item in body["missing"]}
        self.assertIn("Kafka", missing)
        often = missing["Kafka"].get("often_with")
        self.assertIsNotNone(often)
        self.assertEqual(often["base_name"], "Java")
        self.assertAlmostEqual(often["share"], 4 / MIN_PAIR_BASE_ADS, places=3)


if __name__ == "__main__":
    unittest.main()
