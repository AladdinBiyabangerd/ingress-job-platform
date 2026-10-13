"""GET /api/v1/skills/related — family + pair + role companions (filtered)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.main import app
from app.skill_reco import clear_catalog_memo
from app.skill_related import categories_compatible, related_skills_for_conn
from app.trends import _TRENDS_ENSURED, ensure_trend_tables


class SkillRelatedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store
        from app import role_suggestions

        cabinet_store._ENSURED.clear()
        _TRENDS_ENSURED.clear()
        role_suggestions._SKILL_LOOKUP_MEMO = None
        clear_catalog_memo()
        ensure_schema(create=True)
        self._seed()
        self.client = TestClient(app)

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store
        from app import role_suggestions

        cabinet_store._ENSURED.clear()
        _TRENDS_ENSURED.clear()
        role_suggestions._SKILL_LOOKUP_MEMO = None
        clear_catalog_memo()
        self.tmp.cleanup()

    def _seed(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            skills = [
                ("Spring", '["spring boot"]', "backend"),
                ("Spring Security Framework", "[]", "backend"),
                ("Spring MVC", "[]", "backend"),
                ("Java", "[]", "language"),
                ("CI/CD", "[]", "devops"),
                ("Docker", "[]", "devops"),
                ("Kubernetes", "[]", "devops"),
                ("Terraform", "[]", "devops"),
                ("Git", "[]", "devops"),
                ("Git Flow", "[]", "devops"),
                ("Git Hooks", "[]", "devops"),
                ("Git Rebase", "[]", "devops"),
                ("Git Submodules", "[]", "devops"),
                ("GitHub Actions", "[]", "devops"),
                ("GitLab CI", "[]", "devops"),
                ("React", "[]", "frontend"),
                ("CSS", "[]", "frontend"),
                ("JavaScript", "[]", "language"),
            ]
            for name, synonyms, category in skills:
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, ?, ?, '[]', '2026-10-05T12:00:00+00:00')
                    """,
                    (name, synonyms, category),
                )
            ids = {
                row["canonical_name"]: int(row["id"])
                for row in conn.execute("SELECT id, canonical_name FROM skill_dictionary")
            }
            # DevOps role: CI/CD is a signature skill.
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('DevOps Engineer', 'DevOps/Cloud', '[]', '2026-10-05T12:00:00+00:00')
                """
            )
            devops_id = int(
                conn.execute(
                    "SELECT id FROM role_taxonomy WHERE canonical_name = ?",
                    ("DevOps Engineer",),
                ).fetchone()["id"]
            )
            for skill, weight in (
                ("CI/CD", 0.85),
                ("Docker", 0.65),
                ("Kubernetes", 1.0),
                ("Terraform", 0.8),
                ("Git", 0.25),
            ):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (devops_id, ids[skill], weight),
                )
            # Frontend role also lists Git lightly + React/CSS — hub noise.
            conn.execute(
                """
                INSERT INTO role_taxonomy (canonical_name, category, synonyms, updated_at)
                VALUES ('React Developer', 'Frontend', '[]', '2026-10-05T12:00:00+00:00')
                """
            )
            react_role = int(
                conn.execute(
                    "SELECT id FROM role_taxonomy WHERE canonical_name = ?",
                    ("React Developer",),
                ).fetchone()["id"]
            )
            for skill, weight in (
                ("React", 1.0),
                ("CSS", 0.7),
                ("JavaScript", 0.8),
                ("Git", 0.2),
            ):
                conn.execute(
                    "INSERT INTO role_skill_weight (role_id, skill_id, weight) VALUES (?, ?, ?)",
                    (react_role, ids[skill], weight),
                )
            ensure_trend_tables(conn)
            conn.execute(
                """
                INSERT INTO skill_pair_daily (
                    day, base_skill_id, pair_skill_id, category, co_ad_count
                ) VALUES (?, ?, ?, '', ?)
                """,
                ("2026-10-05", ids["CI/CD"], ids["Docker"], 20),
            )
            conn.execute(
                """
                INSERT INTO skill_trend_daily (
                    day, skill_id, category, region, remote, relocation, ad_count
                ) VALUES (?, ?, 'Backend', '', 1, 0, ?)
                """,
                ("2026-10-05", ids["CI/CD"], 25),
            )
            conn.commit()
            self.ids = ids

    def test_categories_compatible(self):
        self.assertTrue(categories_compatible("devops", "backend"))
        self.assertTrue(categories_compatible("language", "backend"))
        self.assertFalse(categories_compatible("devops", "language"))
        self.assertFalse(categories_compatible("devops", "frontend"))
        self.assertFalse(categories_compatible("frontend", "devops"))

    def test_http_spring_family_and_exclude(self):
        res = self.client.get(
            "/api/v1/skills/related",
            params={"name": "Spring", "exclude": "Spring MVC", "limit": 8},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["name"], "Spring")
        self.assertEqual(data["skill_id"], self.ids["Spring"])
        names = [item["name"] for item in data["items"]]
        self.assertIn("Spring Security Framework", names)
        self.assertNotIn("Spring MVC", names)
        self.assertNotIn("Spring", names)
        self.assertTrue(all(item.get("source") for item in data["items"]))

    def test_http_spring_boot_synonym_resolves(self):
        res = self.client.get(
            "/api/v1/skills/related",
            params={"name": "spring boot", "limit": 5},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["name"], "Spring")
        names = [item["name"] for item in data["items"]]
        self.assertTrue(
            any(n.startswith("Spring ") for n in names),
            names,
        )

    def test_http_cicd_includes_docker(self):
        res = self.client.get(
            "/api/v1/skills/related",
            params={"name": "CI/CD", "limit": 8},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        names = [item["name"] for item in data["items"]]
        self.assertIn("Docker", names)
        docker = next(item for item in data["items"] if item["name"] == "Docker")
        self.assertIn(docker["source"], {"exploit", "adjacent", "serendipity", "pair"})

    def test_hub_git_does_not_pull_frontend(self):
        """Git is listed lightly on many roles — must not recommend React/CSS."""
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            payload = related_skills_for_conn(conn, name="Git", limit=12)
        names = [item["name"] for item in payload["items"]]
        self.assertNotIn("React", names)
        self.assertNotIn("CSS", names)
        self.assertNotIn("JavaScript", names)
        # Same-stack devops peers should still surface for density.
        self.assertTrue(
            {"Docker", "Kubernetes", "Terraform", "CI/CD"} & set(names),
            names,
        )

    def test_mixed_buckets_not_only_exploit(self):
        """Hybrid mix must leave room beyond same-category exploitation."""
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            payload = related_skills_for_conn(conn, name="Git", limit=12)
        sources = {item["source"] for item in payload["items"]}
        names = [item["name"] for item in payload["items"]]
        self.assertTrue(sources & {"exploit", "adjacent", "serendipity", "family"}, sources)
        self.assertTrue(
            any(not n.startswith("Git") for n in names),
            names,
        )

    def test_unknown_name_empty_items(self):
        res = self.client.get(
            "/api/v1/skills/related",
            params={"name": "DefinitelyNotASkillXYZ", "limit": 5},
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["skill_id"], None)
        self.assertEqual(data["items"], [])

    def test_conn_helper_spring_family_near_focus(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            payload = related_skills_for_conn(
                conn, name="Spring", exclude=["Java"], limit=4
            )
        names = [item["name"] for item in payload["items"]]
        self.assertTrue(names)
        self.assertTrue(
            any(n.startswith("Spring") for n in names),
            names,
        )
        self.assertNotIn("Java", names)


if __name__ == "__main__":
    unittest.main()
