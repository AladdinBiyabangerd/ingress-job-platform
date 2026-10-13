import sqlite3
import unittest

from worker import categories as cat
from worker.techstack import classify_category


class JobCategoriesTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        cat.ensure_categories(self.conn)
        cat.reload_rules(self.conn)

    def tearDown(self):
        cat.set_rules(None)

    def test_seed_and_idempotent(self):
        self.assertEqual(cat.ensure_categories(self.conn), 0)
        slugs = [i["slug"] for i in cat.read_categories(self.conn)]
        self.assertIn("Backend", slugs)
        self.assertEqual(slugs[-1], cat.OTHER)

    def test_table_drives_rules(self):
        self.assertEqual(classify_category("", "Senior Python Developer", []), "Backend")
        self.conn.execute("UPDATE job_categories SET active = 0 WHERE slug = 'Backend'")
        cat.reload_rules(self.conn)
        self.assertEqual(classify_category("", "Senior Python Developer", []), cat.OTHER)
        self.conn.execute(
            "UPDATE job_categories SET title_pattern = 'python' WHERE slug = 'Data/ML'"
        )
        cat.reload_rules(self.conn)
        self.assertEqual(classify_category("", "Senior Python Developer", []), "Data/ML")

    def test_alias_and_empty_fallback(self):
        self.conn.execute("UPDATE job_categories SET aliases = '[\"plumbing\"]' WHERE slug = 'Backend'")
        cat.reload_rules(self.conn)
        self.assertEqual(classify_category("Plumbing", "Engineer", []), "Backend")
        cat.set_rules([])
        self.assertEqual(classify_category("", "Frontend Engineer", []), "Frontend")

    def test_bad_regex_rejected(self):
        self.assertTrue(cat.validate_pattern("("))
        self.assertEqual(cat.validate_pattern("a|b"), "")


if __name__ == "__main__":
    unittest.main()
