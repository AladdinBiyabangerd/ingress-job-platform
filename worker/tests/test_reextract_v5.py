import sqlite3
import tempfile
import unittest
from pathlib import Path

from worker.db import REEXTRACT_STACK_STEP, Store


class ReextractStackOnlyTest(unittest.TestCase):
    def test_rewrites_stack_only_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "j.sqlite"
            store = Store(path, sqlite_only=True)
            store.conn.execute(
                "INSERT INTO jobs (title, company, text, status, created_at, updated_at, norm_key, tech_stack) "
                "VALUES ('Backend Engineer', 'Acme', 'We use spring boot, Resilience4j and Kafka.', "
                "'published', '2026-10-01', '2026-10-01T00:00:00Z', 'k1', '[]')"
            )
            store.conn.commit()
            self.assertEqual(store.reextract_tech_stack(force=True), 1)
            self.assertEqual(store.reextract_tech_stack(force=True), 0)
            self.assertEqual(store.reextract_tech_stack(), 0)
            row = store.conn.execute("SELECT status, updated_at, tech_stack FROM jobs").fetchone()
            self.assertEqual(row["status"], "published")
            self.assertEqual(row["updated_at"], "2026-10-01T00:00:00Z")
            for name in ("Spring", "Resilience4j", "Kafka"):
                self.assertIn(name, row["tech_stack"])
            self.assertTrue(store.conn.execute(
                "SELECT 1 FROM maintenance_steps WHERE name = ?", (REEXTRACT_STACK_STEP,)).fetchone())


if __name__ == "__main__":
    unittest.main()
