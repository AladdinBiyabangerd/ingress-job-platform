"""Academy-first learning roadmap builder."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.cabinet_store import _connect, ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.learning_roadmap import build_learning_roadmap, legacy_roadmap_steps


class LearningRoadmapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.accounts = root / "accounts.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.accounts_patch = patch("app.profiles.DATA_PATH", self.accounts)
        self.path_patch.start()
        self.accounts_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self._seed_skills()

    def tearDown(self):
        self.accounts_patch.stop()
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _seed_skills(self):
        with sqlite3.connect(self.db) as conn:
            for name, courses in (
                ("Kubernetes", '["k8s-fundamentals"]'),
                ("Java", '["java-se-oca-az"]'),
                ("Spark", "[]"),
                ("Kafka", "[]"),
            ):
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, '[]', '', ?, '2026-10-08T12:00:00+00:00')
                    """,
                    (name, courses),
                )
            conn.execute(
                """
                INSERT INTO role_taxonomy (
                    canonical_name, category, synonyms, academy_career_path_id, updated_at
                ) VALUES (?, 'engineering', '[]', ?, '2026-10-08T12:00:00+00:00')
                """,
                ("Java Developer", "ai-native-java-muhendisi"),
            )
            conn.commit()

    def _seed_profile(self, subject: str):
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            data = {
                "skills": [
                    {"name": "Java", "years": 3},
                    {"name": "SQL", "years": 2},
                ],
                "headline": "Java Developer",
            }
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, '', ?, 'Java Developer', 'middle', 3, 'confirmed', 'rules', 0.8, 'anonymous', ?)
                """,
                (subject, json.dumps(data), "2026-10-08T12:00:00+00:00"),
            )
            conn.commit()

    def test_academy_course_and_path_together(self):
        subject = "java-dev"
        self._seed_profile(subject)
        conn = _connect()
        try:
            with patch("app.learning_roadmap.complete_json") as ai:
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(ok=False, error="disabled")
                rich = build_learning_roadmap(
                    conn,
                    user_id=subject,
                    missing_skills=["Kubernetes", "Kafka"],
                    have_skills=["Java", "SQL"],
                    role="Java Developer",
                    lang="en",
                    allow_ai_provider=False,
                    week_key="2026-W41",
                )
            courses = rich.get("academy_courses") or []
            self.assertTrue(courses)
            self.assertEqual(courses[0]["slug"], "k8s-fundamentals")
            self.assertTrue(rich.get("academy_career_path") or rich.get("career_path"))
            kinds = {m.get("kind") for m in (rich.get("milestones") or [])}
            self.assertIn("academy_course", kinds)
            self.assertIn("academy_path", kinds)
            # Unmapped Kafka still filled (template) → hybrid.
            self.assertEqual(rich.get("source"), "hybrid")
            self.assertEqual(rich.get("status"), "ready")
            self.assertTrue(rich.get("hero", {}).get("title"))
            self.assertTrue(rich.get("this_week", {}).get("items"))
            legacy = legacy_roadmap_steps(
                rich.get("milestones") or [],
                locale="en",
                missing=["Kafka"],
            )
            self.assertTrue(any(r.get("skill") == "Kafka" for r in legacy))
        finally:
            conn.close()

    def test_unmapped_ai_template_fallback(self):
        subject = "spark-user"
        self._seed_profile(subject)
        conn = _connect()
        try:
            with patch("app.learning_roadmap.complete_json") as ai:
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(ok=False, error="no_key")
                rich = build_learning_roadmap(
                    conn,
                    user_id=subject,
                    missing_skills=["Spark"],
                    have_skills=["Java"],
                    role="",
                    lang="az",
                    allow_ai_provider=False,
                )
            self.assertFalse(rich.get("academy_courses"))
            self.assertEqual(rich.get("source"), "ai")
            self.assertTrue(rich.get("milestones"))
            self.assertEqual(rich["milestones"][0]["skill"], "Spark")
            self.assertTrue(rich["milestones"][0].get("coming_soon"))
            self.assertTrue(rich.get("hero", {}).get("skill") == "Spark")
        finally:
            conn.close()

    def test_path_only_fills_week_and_next(self):
        """Career path without missing skills must not look empty."""
        subject = "path-only"
        self._seed_profile(subject)
        conn = _connect()
        try:
            with patch("app.learning_roadmap.complete_json") as ai:
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(ok=False, error="disabled")
                rich = build_learning_roadmap(
                    conn,
                    user_id=subject,
                    missing_skills=[],
                    have_skills=["Java"],
                    role="Java Developer",
                    lang="az",
                    allow_ai_provider=False,
                    week_key="2026-W41",
                )
            self.assertEqual(rich.get("status"), "ready")
            self.assertTrue(rich.get("academy_career_path") or rich.get("career_path"))
            hero = rich.get("hero") or {}
            self.assertTrue(hero.get("title"))
            self.assertNotIn("təsdiqləyin", (hero.get("lede") or "").lower())
            self.assertNotIn("confirm", (hero.get("lede") or "").lower())
            week = (rich.get("this_week") or {}).get("items") or []
            nxt = (rich.get("next") or {}).get("items") or []
            self.assertTrue(week, "this_week should have path starter steps")
            self.assertTrue(nxt, "next should have follow-up steps")
            path = rich.get("academy_path") or {}
            self.assertTrue(path.get("steps"))
            self.assertTrue((path.get("cta") or {}).get("href"))
        finally:
            conn.close()

    def test_ai_applied_milestones(self):
        subject = "ai-user"
        self._seed_profile(subject)
        conn = _connect()
        try:
            with (
                patch("app.learning_roadmap.roadmap_enabled", return_value=True),
                patch("app.learning_roadmap.complete_json") as ai,
            ):
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(
                    ok=True,
                    data={
                        "hero": {
                            "title": "This week’s step: Spark",
                            "lede": "Close the Spark gap with a focused lab.",
                            "motivation": "One concrete practice block.",
                        },
                        "milestones": [
                            {
                                "skill": "Spark",
                                "kind": "practice",
                                "title": "Spark batch lab",
                                "body": "Run a small ETL notebook this week.",
                                "why_now": "Near-miss jobs ask for Spark.",
                            },
                            {
                                "skill": "Spark",
                                "kind": "apply",
                                "title": "Apply to a near-miss",
                                "body": "Use the lab result in your next application.",
                                "why_now": "Show proof, not only theory.",
                            },
                            {
                                "kind": "practice",
                                "skill": "Kafka",
                                "title": "Kafka basics",
                                "body": "Should be dropped — Kafka not in missing/have.",
                                "why_now": "invalid",
                            },
                        ],
                    },
                )
                rich = build_learning_roadmap(
                    conn,
                    user_id=subject,
                    missing_skills=["Spark"],
                    have_skills=["Java"],
                    role="Backend Engineer",
                    lang="en",
                    allow_ai_provider=True,
                )
            self.assertEqual(rich.get("ai_status"), "applied")
            titles = [m.get("title") for m in rich.get("milestones") or []]
            self.assertIn("Spark batch lab", titles)
            self.assertNotIn("Kafka basics", titles)
            self.assertIn("Spark", rich.get("hero", {}).get("title", ""))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
