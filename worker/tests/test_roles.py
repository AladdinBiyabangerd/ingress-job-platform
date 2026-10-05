"""role_taxonomy seed + signature skill weights (Phase 0.3)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.roles import load_seed, seed_path, seed_role_taxonomy
from worker.techstack import CATEGORIES


class RolesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_seed_loads_packaged_taxonomy(self):
        path = seed_path()
        self.assertTrue(path.is_file(), path)
        roles = load_seed(path)
        self.assertGreaterEqual(len(roles), 30)
        self.assertLessEqual(len(roles), 45)

        count = self.store.conn.execute("SELECT COUNT(*) FROM role_taxonomy").fetchone()[0]
        self.assertEqual(int(count), len(roles))

        row = self.store.conn.execute(
            """
            SELECT category, synonyms FROM role_taxonomy
            WHERE canonical_name = ?
            """,
            ("Java Developer",),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["category"], "Backend")
        self.assertIn("Java Engineer", json.loads(row["synonyms"]))

    def test_categories_are_known(self):
        known = set(CATEGORIES)
        for role in load_seed():
            self.assertIn(role["category"], known, role["canonical_name"])

    def test_signature_skills_link_dictionary(self):
        conn = self.store.conn
        java = conn.execute(
            """
            SELECT s.canonical_name, w.weight
            FROM role_skill_weight w
            JOIN role_taxonomy r ON r.id = w.role_id
            JOIN skill_dictionary s ON s.id = w.skill_id
            WHERE r.canonical_name = ?
            ORDER BY w.weight DESC, s.canonical_name
            """,
            ("Java Developer",),
        ).fetchall()
        names = [row["canonical_name"] for row in java]
        self.assertIn("Java", names)
        self.assertIn("Spring", names)
        top = java[0]
        self.assertEqual(top["canonical_name"], "Java")
        self.assertAlmostEqual(float(top["weight"]), 1.0)

        # Every linked skill must exist; orphan weights are a seed bug.
        orphans = conn.execute(
            """
            SELECT COUNT(*) FROM role_skill_weight w
            LEFT JOIN skill_dictionary s ON s.id = w.skill_id
            WHERE s.id IS NULL
            """
        ).fetchone()[0]
        self.assertEqual(int(orphans), 0)

    def test_seed_is_idempotent(self):
        first_roles, first_weights = seed_role_taxonomy(self.store.conn)
        second_roles, second_weights = seed_role_taxonomy(self.store.conn)
        self.assertEqual(first_roles, second_roles)
        self.assertEqual(first_weights, second_weights)
        count = self.store.conn.execute("SELECT COUNT(*) FROM role_taxonomy").fetchone()[0]
        self.assertEqual(int(count), first_roles)


if __name__ == "__main__":
    unittest.main()
