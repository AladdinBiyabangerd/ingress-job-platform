"""Employer cabinet ads stay off the public list until published."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import save_profile


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class CabinetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("cabinet-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _ad(self, **extra):
        body = {
            "title": "Backend muhendisi",
            "company": "Basqa MMC",
            "city": "Baki",
            "remote": False,
            "text": "Komanda ucun aciq rol. https://secret.example/apply",
            "language": "az",
            "salary": "2000-2500 AZN",
            "job_type": "hibrid",
        }
        body.update(extra)
        return body

    def test_employer_ad_is_pending_and_hidden_until_closed_row_remains(self):
        with self._auth("job:employer", "cabinet-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad = created.json()
            self.assertEqual(ad["status"], "pending")
            self.assertEqual(ad["company"], "Ingress MMC")
            self.assertNotIn("source_url", ad)
            self.assertNotIn("source_url", created.text)

            listed = self.client.get("/api/v1/cabinet/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(listed.status_code, 200)
            self.assertEqual([item["id"] for item in listed.json()["items"]], [ad["id"]])

            edited = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad['id']}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Backend muhendisi (mid)"),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["title"], "Backend muhendisi (mid)")
            self.assertEqual(edited.json()["status"], "pending")
            self.assertEqual(edited.json()["company"], "Ingress MMC")

        public = self.client.get("/api/v1/jobs")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(public.json()["items"], [])
        self.assertEqual(self.client.get(f"/api/v1/jobs/{ad['id']}").status_code, 404)

        conn = sqlite3.connect(self.db)
        conn.execute(
            """
            INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
            VALUES (?, 'secret', 'https://secret.example/job', '', '2026-10-04T12:00:00+04:00')
            """,
            (ad["id"],),
        )
        conn.commit()
        conn.close()

        leaked = self.client.get("/api/v1/jobs")
        self.assertNotIn("secret.example", leaked.text)
        self.assertNotIn("source_url", leaked.text)

        with self._auth("job:employer", "cabinet-employer"):
            closed = self.client.post(
                f"/api/v1/cabinet/jobs/{ad['id']}/close",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(closed.status_code, 200, closed.text)
            self.assertEqual(closed.json()["status"], "closed")
            mine = self.client.get("/api/v1/cabinet/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(mine.json()["items"][0]["status"], "closed")
            blocked = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad['id']}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(blocked.status_code, 409)

        self.assertEqual(self.client.get("/api/v1/jobs").json()["items"], [])
        conn = sqlite3.connect(self.db)
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        status = conn.execute("SELECT status FROM jobs WHERE id = ?", (ad["id"],)).fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)
        self.assertEqual(status, "closed")

    def test_staff_ad_publishes_immediately_without_a_source_url(self):
        with self._auth("job:staff", "cabinet-staff"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(company="Staff MMC", remote=True, city="", job_type="uzaqdan", salary=""),
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad = created.json()
            self.assertEqual(ad["status"], "published")
            self.assertEqual(ad["company"], "Staff MMC")
            self.assertTrue(ad["remote"])
            self.assertEqual(ad["city"], "")
            self.assertNotIn("source_url", ad)

            edited = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad['id']}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Staff rolu", company="Staff MMC", remote=True, city=""),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["title"], "Staff rolu")
            self.assertEqual(edited.json()["status"], "published")

        public = self.client.get("/api/v1/jobs")
        self.assertEqual(public.status_code, 200)
        items = public.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Staff rolu")
        self.assertEqual(items[0]["language"], "az")
        self.assertTrue(items[0]["remote"])
        self.assertNotIn("source_url", items[0])
        self.assertNotIn("http", public.text.lower())
        self.assertNotIn("secret.example", public.text)

        with self._auth("job:employer", "cabinet-employer"):
            hidden = self.client.get("/api/v1/cabinet/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(hidden.json()["items"], [])
            denied = self.client.post(
                f"/api/v1/cabinet/jobs/{ad['id']}/close",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(denied.status_code, 404)

    def test_significant_edit_returns_to_review_salary_and_type_do_not(self):
        with self._auth("job:employer", "cabinet-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(text="Metn"),
            )
            ad_id = created.json()["id"]
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE jobs SET status = 'published' WHERE id = ?", (ad_id,))
        conn.commit()
        conn.close()
        with self._auth("job:employer", "cabinet-employer"):
            salary = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(text="Metn", salary="3000 AZN", job_type="ofis"),
            )
            self.assertEqual(salary.status_code, 200, salary.text)
            self.assertEqual(salary.json()["status"], "published")
            self.assertEqual(salary.json()["salary"], "3000 AZN")
            self.assertEqual(salary.json()["job_type"], "ofis")
        self.assertEqual(len(self.client.get("/api/v1/jobs").json()["items"]), 1)
        with self._auth("job:employer", "cabinet-employer"):
            edited = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Deyisdi", text="Metn", salary="3000 AZN", job_type="ofis"),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["status"], "pending")
            self.assertEqual(edited.json()["title"], "Deyisdi")
        self.assertEqual(self.client.get("/api/v1/jobs").json()["items"], [])
        with self._auth("job:employer", "cabinet-employer"):
            closed = self.client.post(
                f"/api/v1/cabinet/jobs/{ad_id}/close",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(closed.status_code, 200)
            self.assertEqual(closed.json()["status"], "closed")
        self.assertEqual(self.client.get("/api/v1/jobs").json()["items"], [])

    def test_gates_and_required_fields(self):
        guest = self.client.get("/api/v1/cabinet/jobs")
        self.assertEqual(guest.status_code, 401)

        with self._auth("job:candidate", "cabinet-candidate"):
            denied = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(denied.status_code, 403)

        with self._auth("job:employer", "cabinet-empty"):
            gated = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(gated.status_code, 403)

        with self._auth("job:employer", "cabinet-employer"):
            missing = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(city="  ", remote=False, title="  "),
            )
            self.assertEqual(missing.status_code, 422)
            bad_type = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(job_type="freelance"),
            )
            self.assertEqual(bad_type.status_code, 422)
            remote = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(city="", remote=True, text="Uzaqdan is."),
            )
            self.assertEqual(remote.status_code, 201, remote.text)
            self.assertTrue(remote.json()["remote"])
            self.assertEqual(remote.json()["status"], "pending")

        with self._auth("job:staff", "cabinet-staff"):
            unnamed = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(company="  "),
            )
            self.assertEqual(unnamed.status_code, 422)


if __name__ == "__main__":
    unittest.main()
