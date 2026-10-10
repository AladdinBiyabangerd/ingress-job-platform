"""Rules found by the pre-production DB review: category, non-IT titles, remote duplicates."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.place import normalize_city
from worker.techstack import classify_category, enrich, is_tech_job, relocation_flag


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
            "Head of Crypto",
            "Crypto Business Development Manager",
            "Director of Crypto Partnerships",
        ]:
            self.assertFalse(is_tech_job(title), title)

    def test_pm_game_and_crypto_engineer_titles_kept(self):
        for title in [
            "Game Designer / Project Manager",
            "Senior Game Designer",
            "Technical Project Manager",
            "Program Manager, Platform",
            "Delivery Manager",
            "Crypto Engineer",
            "Blockchain Developer",
        ]:
            self.assertTrue(is_tech_job(title), title)

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


class SecondAuditRulesTest(unittest.TestCase):
    def test_security_and_mobile_titles(self):
        self.assertEqual(classify_category("", "Head of Infrastructure and Cloud Security", []), "Security")
        self.assertEqual(classify_category("", "Especialista Senior en Seguridad de Infraestructura", []), "Security")
        self.assertNotEqual(classify_category("", "Senior Mobile Traffic Infrastructure Engineer (Keitaro)", []), "Mobile")
        self.assertEqual(classify_category("", "Front-end Android Sr", []), "Mobile")

    def test_spanish_security_title_is_tech(self):
        self.assertTrue(is_tech_job("Especialista Senior en Seguridad de Infraestructura"))
        self.assertTrue(is_tech_job("Desarrollador/a Full-Stack (Node.js/angular)"))

    def test_html_negated_visa_is_not_relocation(self):
        text = "<p>Cast AI <u><em>does not</em></u><em> provide any form of visa sponsorship/work permit.</em></p>"
        self.assertFalse(relocation_flag("Senior ML Engineer", "", text))
        self.assertTrue(relocation_flag("Developer", "", "<p>Visa sponsorship + relocation support</p>"))

    def test_remote_default_relocation_dropped_without_text(self):
        item = {"title": "Applied AI Engineer", "city": "", "text": "Build agents. Fully remote role.",
                "remote": True}
        self.assertFalse(enrich(item, relocation_default=True)["relocation"])
        item = {"title": "Dev", "city": "", "text": "Fully remote role. Relocation support offered.", "remote": True}
        self.assertTrue(enrich(item, relocation_default=True)["relocation"])

    def test_work_mode_is_not_a_city(self):
        self.assertEqual(normalize_city("Hybrid"), "")
        self.assertEqual(normalize_city("Cambridge / Hybrid"), "Cambridge")
        self.assertEqual(normalize_city("NE61SF"), "")
        self.assertEqual(normalize_city("Berlin, Germany"), "Berlin, Germany")

    def test_spaced_company_is_same_remote_ad(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        first = _item("")
        first["company"] = "DuckDuckGo"
        self.assertEqual(store.upsert(first), "created")
        second = _item("")
        second["company"] = "Duck Duck Go"
        second["source_url"] = "https://e.test/ddg2"
        self.assertEqual(store.upsert(second), "updated")
        self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
