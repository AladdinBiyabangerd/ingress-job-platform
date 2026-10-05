"""Company directory, company page and on-site application counts."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.cabinet_store import ensure_schema
from app.companies import company_key, company_slug, slug_for
from app.jobs_db import adapt_sql
from app.main import app


class CompanyKeyTests(unittest.TestCase):
    def test_legal_forms_case_and_quotes_merge(self):
        self.assertEqual(company_key("Acme, Inc."), "acme")
        self.assertEqual(company_key("ACME   LLC"), "acme")
        self.assertEqual(company_key("acme l.l.c."), "acme")
        self.assertEqual(company_key("“Kontakt Home” MMC"), "kontakt home")
        self.assertEqual(company_key("ООО «Ромашка»"), "ромашка")
        self.assertEqual(company_key("Bosch GmbH"), "bosch")
        self.assertEqual(company_key("PASHA Bank ASC"), "pasha bank")

    def test_legal_word_alone_is_kept_or_dropped_safely(self):
        # Only a legal form left: not a company.
        self.assertEqual(company_key("LLC"), "")
        # The last real word is never stripped.
        self.assertEqual(company_key("Company"), "")
        self.assertEqual(company_key("Limited Edition Games Ltd"), "limited edition games")

    def test_junk_names_are_skipped(self):
        for name in ("", "  ", "Confidential", "Company not listed", "Şirkət göstərilməyib", "N/A", "—", "12345"):
            self.assertEqual(company_key(name), "", name)

    def test_slugs_are_ascii_and_stable(self):
        self.assertEqual(company_slug("Azərbaycan Şəkər İstehsalat"), "azerbaycan-seker-istehsalat")
        self.assertEqual(company_slug("ООО «Ромашка»"), "romashka")
        self.assertEqual(company_slug("Acme, Inc."), company_slug("ACME LLC"))
        self.assertTrue(slug_for("株式会社").startswith("c-"))
        self.assertEqual(slug_for("株式会社"), slug_for("株式会社"))

    def test_grouped_count_sql_is_postgres_compatible(self):
        sql = adapt_sql(
            "SELECT a.job_id AS job_id, COUNT(*) AS total FROM applications a "
            "WHERE LOWER(COALESCE(a.status, '')) NOT IN ('withdrawn', 'deleted') AND a.job_id = ? GROUP BY a.job_id"
        )
        self.assertIn("a.job_id = %s", sql)
        self.assertIn("GROUP BY a.job_id", sql)


class CompanyApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.n = 0

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _job(self, company, *, owner="", city="Bakı", remote=0, relocation=0, category="Backend",
             tech='["Python"]', created="2026-10-01T10:00:00+04:00", hidden=0, status="published"):
        self.n += 1
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject,
                              remote, relocation, tech_stack, category, hidden)
            VALUES (?, ?, ?, 'Body text', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"Job {self.n}", company, city, status, created, f"k-{self.n}", owner, remote, relocation, tech, category, hidden),
        )
        conn.commit()
        conn.close()
        return int(cur.lastrowid)

    def _apply(self, job_id, count, status="submitted"):
        conn = sqlite3.connect(self.db)
        for index in range(count):
            conn.execute(
                """
                INSERT INTO applications (job_id, candidate_subject, message, created_at, status)
                VALUES (?, ?, 'hi', '2026-10-02T10:00:00+04:00', ?)
                """,
                (job_id, f"cand-{job_id}-{status}-{index}", status),
            )
        conn.commit()
        conn.close()

    def _seed(self):
        a1 = self._job("Acme, Inc.", owner="emp-1", tech='["Python", "AWS"]', created="2026-10-03T10:00:00+04:00")
        a2 = self._job("ACME LLC", owner="emp-1", remote=1, city="", category="DevOps/Cloud", tech='["AWS"]')
        a3 = self._job("Acme Inc", relocation=1, created="2026-09-20T10:00:00+04:00")
        b1 = self._job("Beta Soft", owner="emp-2", category="QA", tech='["Selenium"]', created="2026-10-04T10:00:00+04:00")
        self._job("Confidential")
        self._job("")
        self._job("Hidden Co", hidden=1)
        self._job("Closed Co", status="closed")
        self._apply(a1, 3)
        self._apply(a2, 1)
        self._apply(b1, 4)
        self._apply(b1, 2, status="withdrawn")
        return a1, a2, a3, b1

    def test_directory_merges_names_and_counts(self):
        self._seed()
        data = self.client.get("/api/v1/companies").json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["total_applications"], 8)
        acme, beta = data["items"]
        self.assertEqual(acme["slug"], "acme")
        self.assertEqual(acme["open_jobs"], 3)
        self.assertEqual(acme["onsite_jobs"], 2)
        self.assertEqual(acme["remote_jobs"], 1)
        self.assertEqual(acme["relocation_jobs"], 1)
        self.assertEqual(acme["remote_share"], 33)
        self.assertEqual(acme["applications"], 4)
        self.assertEqual(acme["applications_per_job"], 2.0)
        self.assertEqual(acme["application_share"], 50.0)
        self.assertEqual(acme["top_categories"][0], {"name": "Backend", "count": 2})
        self.assertEqual(acme["top_tech"][0], {"name": "AWS", "count": 2})
        self.assertEqual(acme["locations"], ["Bakı"])
        self.assertEqual(acme["latest_posted"], "2026-10-03T10:00:00+04:00")
        self.assertEqual(beta["applications"], 4)
        self.assertNotIn("candidate_subject", str(data))

    def test_sort_search_and_pagination(self):
        self._seed()
        names = lambda params: [item["slug"] for item in self.client.get("/api/v1/companies", params=params).json()["items"]]
        self.assertEqual(names({"sort": "jobs"}), ["acme", "beta-soft"])
        self.assertEqual(names({"sort": "newest"}), ["beta-soft", "acme"])
        self.assertEqual(names({"sort": "name"}), ["acme", "beta-soft"])
        self.assertEqual(names({"sort": "applications", "q": "beta"}), ["beta-soft"])
        self.assertEqual(names({"q": "ACME llc"}), ["acme"])
        self.assertEqual(names({"sort": "bogus"}), ["acme", "beta-soft"])
        page = self.client.get("/api/v1/companies", params={"per_page": 1, "page": 2}).json()
        self.assertEqual((page["page"], page["pages"], page["total"]), (2, 2, 2))
        self.assertEqual(page["items"][0]["slug"], "beta-soft")
        self.assertEqual(self.client.get("/api/v1/companies", params={"per_page": 0}).status_code, 422)

    def test_company_page_lists_its_jobs(self):
        a1, a2, a3, _ = self._seed()
        data = self.client.get("/api/v1/companies/acme", params={"per_page": 2}).json()
        self.assertEqual(data["company"]["name"], "Acme, Inc.")
        self.assertEqual(data["jobs"]["total"], 3)
        self.assertEqual([job["id"] for job in data["jobs"]["items"]], [a1, a2])
        self.assertEqual(data["jobs"]["items"][0]["company_slug"], "acme")
        more = self.client.get("/api/v1/companies/acme", params={"per_page": 2, "page": 2}).json()
        self.assertEqual([job["id"] for job in more["jobs"]["items"]], [a3])
        self.assertEqual(self.client.get("/api/v1/companies/nope").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/companies/hidden-co").status_code, 404)

    def test_job_payloads_carry_slug_and_onsite_counts(self):
        a1, _, a3, b1 = self._seed()
        detail = self.client.get(f"/api/v1/jobs/{a1}").json()
        self.assertEqual(detail["company_slug"], "acme")
        self.assertEqual(detail["applications"], 3)
        self.assertEqual(self.client.get(f"/api/v1/jobs/{b1}").json()["applications"], 4)
        # Collected ads are applied to on the source site: no count.
        self.assertIsNone(self.client.get(f"/api/v1/jobs/{a3}").json()["applications"])
        items = {item["id"]: item for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertEqual(items[a1]["applications"], 3)
        self.assertIsNone(items[a3]["applications"])


if __name__ == "__main__":
    unittest.main()
