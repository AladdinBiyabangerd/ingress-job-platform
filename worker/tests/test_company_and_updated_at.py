"""Listings without a company never pass acceptance; jobs.updated_at is a real timestamp."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from worker.acceptance import finish_item
from worker.db import Store


def _item(**kw):
    base = {
        "title": "Senior Backend Engineer",
        "company": "Acme",
        "city": "Remote",
        "text": "Fully remote, work from anywhere in the world. Python, Django. " * 5,
        "source_url": "https://example.com/jobs/1",
        "source_name": "test",
        "remote": True,
    }
    base.update(kw)
    return base


class CompanyGuardTest(unittest.TestCase):
    def test_missing_company_rejected(self):
        conn = SimpleNamespace(name="test", store=None)
        for company in ["", "   ", None]:
            self.assertIsNone(finish_item(conn, _item(company=company)), repr(company))

    def test_guard_only_rejects(self):
        conn = SimpleNamespace(name="test", store=None)
        # Non-IT title with a company is still rejected by the existing rules.
        self.assertIsNone(finish_item(conn, _item(title="Legal Ops Manager")))


class UpdatedAtTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.tmp.cleanup()

    def _row(self):
        return self.store.conn.execute("SELECT created_at, updated_at FROM jobs").fetchone()

    def test_insert_sets_updated_at(self):
        self.store.upsert(_item())
        row = self._row()
        self.assertTrue(row["updated_at"])
        self.assertEqual(row["updated_at"], row["created_at"])

    def test_unchanged_recrawl_keeps_stamp_changed_text_bumps(self):
        self.store.upsert(_item())
        self.store.conn.execute("UPDATE jobs SET updated_at = '2000-01-01T00:00:00+00:00'")
        self.store.upsert(_item())
        self.assertEqual(self._row()["updated_at"], "2000-01-01T00:00:00+00:00")
        self.store.upsert(_item(text="Changed body, remote anywhere."))
        self.assertNotEqual(self._row()["updated_at"], "2000-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
