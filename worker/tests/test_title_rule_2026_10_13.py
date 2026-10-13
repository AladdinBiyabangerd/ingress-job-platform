"""2026-10-13 title rules: no leaks from domains, marketer/strategist,
product/motion designer; sysadmin/tester kept."""

import tempfile
import unittest
from pathlib import Path

from worker.db import TITLE_RULE_REASON, Store
from worker.techstack import is_tech_job

NON_IT = [
    "Growth Marketer- Reception.ai", "Growth Marketer", "Performance Marketer - Foo.io",
    "AI Strategist", "Data Strategist", "Head of AI Expansion", "Head of Market Expansion",
    "Delivery Manager", "Senior Delivery Manager", "Delivery Manager - Logistics",
    "Product Designer", "Senior Product Designer, Design Systems",
    "Sr Product Designer", "Motion Designer", "Motion Designer\\Tech Artist",
    "Sales Manager", "Account Executive - AI", "Recruiter (Tech)", "Mechanical Engineer",
]
IT = [
    "Backend Engineer", "ML Engineer at Foo.ai", "Developer Advocate - Supabase.io",
    "Senior .NET Developer", "ASP.NET Developer", "Node.js Developer",
    "Technical Project Manager", "IT Project Manager", "Software Project Manager",
    "Program Manager, Cloud Infrastructure", "Marketing Engineer",
    "Product Manager", "Senior Product Manager - Realtime", "Technical Product Manager",
    "UX/UI Designer", "UI Designer", "Scrum Master", "Project Manager",
    "Software Delivery Manager", "Technical Delivery Manager", "IT Delivery Manager",
    "Linux Administrator L2", "System Administrator", "Тестувальник", "Тестировщик",
    "Системний адміністратор", "Системный администратор",
]


class TitleRuleTest(unittest.TestCase):
    def test_non_it_titles_rejected(self):
        for title in NON_IT:
            with self.subTest(title=title):
                self.assertFalse(is_tech_job(title))

    def test_source_category_cannot_rescue(self):
        for title, cat in [("Product Designer", "Design"), ("Growth Marketer - x.ai", "AI/ML"),
("Motion Designer", "Software Development")]:
            with self.subTest(title=title):
                self.assertFalse(is_tech_job(title, cat, [cat]))

    def test_it_titles_kept(self):
        for title in IT:
            with self.subTest(title=title):
                self.assertTrue(is_tech_job(title))


class RecheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.conn.close()
        self.tmp.cleanup()

    def _add(self, title, status="published", owner="", locked=0):
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject, content_locked) "
                "VALUES (?, 'Acme', '', 't', ?, '2026-10-10T10:00:00+04:00', ?, ?, ?)",
                (title, status, title.lower() + "|acme|", owner, locked),
            )
        return int(cur.lastrowid)

    def _row(self, job_id):
        return self.store.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    def test_hides_only_new_rule_hits(self):
        designer = self._add("Product Designer")
        marketer = self._add("Growth Marketer- Reception.ai")
        backend = self._add("Backend Engineer")
        pm = self._add("Product Manager")
        owned = self._add("Motion Designer", owner="u1")
        locked = self._add("Product Designer II", locked=1)
        pending = self._add("AI Strategist", status="pending")
        delivery = self._add("Delivery Manager")
        project = self._add("Project Manager")
        hit = {job_id for job_id, _ in self.store.recheck_title_rule()}
        self.assertEqual(hit, {designer, marketer, delivery})
        self.assertEqual(self._row(project)["hidden"], 0)
        self.assertEqual(self._row(designer)["hidden"], 1)
        self.assertEqual(self._row(designer)["reject_reason"], TITLE_RULE_REASON)
        self.assertEqual(self._row(designer)["status"], "published")
        for job_id in (backend, pm, owned, locked, pending):
            self.assertEqual(self._row(job_id)["hidden"], 0)
        self.assertEqual(self.store.recheck_title_rule(), [])  # one-time


if __name__ == "__main__":
    unittest.main()
