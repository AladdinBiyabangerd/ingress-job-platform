"""Rules found by the pre-production DB review: category, non-IT titles, remote duplicates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.techstack import classify_category, is_tech_job


class CategoryRulesTest(unittest.TestCase):
    def test_qa_title_wins_over_source_board(self):
        for title, source in [
            ("QA Analyst", "DevOps"),
            ("Senior QA Automation Engineer (.NET/C#)", "Cloud"),
            ("QA Engineer", "Security"),
            ("QA Automation Engineer (Azure)", "Cloud, DevOps"),
        ]:
            self.assertEqual(classify_category(source, title, []), "QA", title)

    def test_non_qa_unchanged(self):
        self.assertEqual(classify_category("", "Senior Backend Engineer", []), "Backend")
        self.assertEqual(classify_category("", "DevOps Engineer", []), "DevOps/Cloud")

    def test_non_it_titles_rejected(self):
        for title in [
            "Propellant Quality Control Engineer",
            "Future Projects Thermal Engineer",
            "Senior Composite Engineer",
            "Renewal Risk Engineer - Management Liability",
            "VP of Trust & Safety",
            "Mobile Growth & Operations Manager",
            "Production Engineer – UAV Platform",
        ]:
            self.assertFalse(is_tech_job(title), title)

    def test_it_titles_kept(self):
        for title in ["Senior Software Engineer, Quality", "QA Engineer", "Site Reliability Engineer, Vehicle SW"]:
            self.assertTrue(is_tech_job(title), title)


def _item(city: str) -> dict:
    return {
        "title": "Agentic Python Engineer", "company": "Evaboot", "city": city,
        "text": "x" * 50, "source_url": f"https://e.test/{city or 'blank'}",
        "source_name": "t", "remote": True,
    }


class RemoteDuplicateTest(unittest.TestCase):
    def test_legacy_remote_key_not_duplicated(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        # a row saved before places were normalised keeps the raw label in its key
        self.assertEqual(store.upsert(_item("")), "created")
        store.conn.execute("UPDATE jobs SET norm_key = 'agentic python engineer|evaboot|remote worldwide'")
        store.conn.commit()
        item = _item("")
        item["source_url"] = "https://e.test/second"
        self.assertEqual(store.upsert(item), "updated")
        n = store.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        self.assertEqual(n, 1)

    def test_other_city_still_separate(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        store.upsert(_item(""))
        item = _item("Berlin, Germany")
        self.assertEqual(store.upsert(item), "created")


if __name__ == "__main__":
    unittest.main()
