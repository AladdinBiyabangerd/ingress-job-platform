"""skill_dictionary seed + job_skill backfill from tech_stack (Phase 0.2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from worker.db import REEXTRACT_STACK_STEP, Store
from worker.skills import (
    BACKFILL_STEP,
    backfill_job_skills,
    seed_path,
    seed_skill_dictionary,
    sync_job_skills,
)


class SkillsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_seed_loads_packaged_dictionary(self):
        path = seed_path()
        self.assertTrue(path.is_file(), path)
        count = self.store.conn.execute("SELECT COUNT(*) FROM skill_dictionary").fetchone()[0]
        self.assertGreaterEqual(int(count), 180)
        row = self.store.conn.execute(
            "SELECT synonyms, category_hint FROM skill_dictionary WHERE canonical_name = ?",
            ("Python",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["category_hint"], "language")
        self.assertIn("py", json.loads(row["synonyms"]))

    def test_backfill_links_known_tech_stack_values(self):
        conn = self.store.conn
        # Store.__init__ already ran the one-time backfill on an empty jobs table.
        conn.execute("DELETE FROM maintenance_steps WHERE name = ?", (BACKFILL_STEP,))
        conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, tech_stack
            ) VALUES (
                'Backend', 'Acme', '', 'Python AWS', 'published',
                '2026-10-05T12:00:00+04:00', 'backend-acme', ?
            )
            """,
            (json.dumps(["Python", "AWS", "NotARealSkill"], ensure_ascii=False),),
        )
        conn.commit()
        processed = backfill_job_skills(conn)
        conn.commit()
        self.assertEqual(processed, 1)
        names = [
            row[0]
            for row in conn.execute(
                """
                SELECT s.canonical_name
                FROM job_skill js
                JOIN skill_dictionary s ON s.id = js.skill_id
                ORDER BY s.canonical_name
                """
            )
        ]
        self.assertEqual(names, ["AWS", "Python"])
        # Second run is a no-op unless forced.
        self.assertEqual(backfill_job_skills(conn), 0)

    def test_upsert_syncs_job_skill(self):
        kind = self.store.upsert(
            {
                "title": "Go Engineer",
                "company": "Ship",
                "city": "Remote",
                "text": "Go and Kubernetes",
                "source_name": "Test",
                "source_url": "https://example.test/go-1",
                "tech_stack": ["Go", "Kubernetes"],
                "remote": True,
                "job_category": "Backend",
            }
        )
        self.assertEqual(kind, "created")
        names = [
            row[0]
            for row in self.store.conn.execute(
                """
                SELECT s.canonical_name
                FROM job_skill js
                JOIN skill_dictionary s ON s.id = js.skill_id
                JOIN jobs j ON j.id = js.job_id
                WHERE j.title = 'Go Engineer'
                ORDER BY s.canonical_name
                """
            )
        ]
        self.assertEqual(names, ["Go", "Kubernetes"])

    def test_sync_replaces_previous_links(self):
        conn = self.store.conn
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, tech_stack
            ) VALUES (
                'FE', 'Co', '', 'React', 'published',
                '2026-10-05T12:00:00+04:00', 'fe-co', '["React"]'
            )
            """
        )
        job_id = int(cur.lastrowid)
        sync_job_skills(conn, job_id, ["React"])
        sync_job_skills(conn, job_id, ["Vue.js", "TypeScript"])
        conn.commit()
        names = [
            row[0]
            for row in conn.execute(
                """
                SELECT s.canonical_name FROM job_skill js
                JOIN skill_dictionary s ON s.id = js.skill_id
                WHERE js.job_id = ?
                ORDER BY s.canonical_name
                """,
                (job_id,),
            )
        ]
        self.assertEqual(names, ["TypeScript", "Vue.js"])

    def test_reextract_adds_new_dictionary_skills_from_text(self):
        conn = self.store.conn
        conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, tech_stack
            ) VALUES (
                'Backend', 'Acme', '',
                'Python Fastify Terraform Prisma',
                'published', '2026-10-05T12:00:00+04:00', 'backend-acme-re',
                ?
            )
            """,
            (json.dumps(["Python"], ensure_ascii=False),),
        )
        job_id = int(conn.execute("SELECT id FROM jobs WHERE norm_key = 'backend-acme-re'").fetchone()[0])
        sync_job_skills(conn, job_id, ["Python"])
        conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                tech_stack, owner_subject
            ) VALUES (
                'Company post', 'Co', '', 'Prisma Fastify',
                'published', '2026-10-05T12:00:00+04:00', 'company-post-re',
                ?, 'company:1'
            )
            """,
            (json.dumps(["Python"], ensure_ascii=False),),
        )
        conn.commit()
        changed = self.store.reextract_tech_stack()
        self.assertEqual(changed, 1)
        stack = json.loads(
            conn.execute(
                "SELECT tech_stack FROM jobs WHERE norm_key = 'backend-acme-re'"
            ).fetchone()[0]
        )
        self.assertIn("Python", stack)
        self.assertIn("Fastify", stack)
        self.assertIn("Terraform", stack)
        self.assertIn("Prisma", stack)
        names = {
            row[0]
            for row in conn.execute(
                """
                SELECT s.canonical_name
                FROM job_skill js
                JOIN skill_dictionary s ON s.id = js.skill_id
                WHERE js.job_id = ?
                """,
                (job_id,),
            )
        }
        self.assertGreaterEqual(names, {"Python", "Fastify", "Terraform", "Prisma"})
        company_stack = json.loads(
            conn.execute(
                "SELECT tech_stack FROM jobs WHERE norm_key = 'company-post-re'"
            ).fetchone()[0]
        )
        self.assertEqual(company_stack, ["Python"])
        self.assertEqual(self.store.reextract_tech_stack(), 0)

    def test_reextract_force_rewrites_after_marker(self):
        conn = self.store.conn
        conn.execute(
            "INSERT INTO maintenance_steps (name, done_at) VALUES (?, 'already')",
            (REEXTRACT_STACK_STEP,),
        )
        conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, tech_stack
            ) VALUES (
                'DevOps', 'Acme', '', 'Ansible Helm',
                'published', '2026-10-05T12:00:00+04:00', 'devops-re',
                '["Linux"]'
            )
            """
        )
        conn.commit()
        self.assertEqual(self.store.reextract_tech_stack(), 0)
        changed = self.store.reextract_tech_stack(force=True)
        self.assertEqual(changed, 1)
        stack = json.loads(
            conn.execute("SELECT tech_stack FROM jobs WHERE norm_key = 'devops-re'").fetchone()[0]
        )
        self.assertIn("Ansible", stack)
        self.assertIn("Helm", stack)

    def test_seed_is_idempotent(self):
        first = seed_skill_dictionary(self.store.conn)
        second = seed_skill_dictionary(self.store.conn)
        self.assertEqual(first, second)
        count = self.store.conn.execute("SELECT COUNT(*) FROM skill_dictionary").fetchone()[0]
        self.assertEqual(int(count), first)


if __name__ == "__main__":
    unittest.main()
