"""Staff moderation: approve, reject, close, and edit without leaking source URLs."""

import os
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


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("admin-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")

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
            "salary": "2000 AZN",
            "job_type": "hibrid",
        }
        body.update(extra)
        return body

    def _pending(self):
        with self._auth("job:employer", "admin-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(),
            )
            self.assertEqual(created.status_code, 201, created.text)
            return created.json()

    def test_staff_approves_edits_and_keeps_rejected_off_public_list(self):
        ad = self._pending()
        ad_id = ad["id"]

        with self._auth("job:employer", "admin-employer"):
            denied = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(denied.status_code, 403)

        guest = self.client.get("/api/v1/admin/jobs")
        self.assertEqual(guest.status_code, 401)

        with self._auth("job:staff", "admin-staff"):
            queue = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(queue.status_code, 200, queue.text)
            items = queue.json()["items"]
            self.assertEqual(items[0]["id"], ad_id)
            self.assertEqual(items[0]["status"], "pending")
            self.assertNotIn("source_url", queue.text)
            detail = self.client.get(
                f"/api/v1/admin/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json()["id"], ad_id)
            self.assertIn("form", detail.json())

            edited = self.client.patch(
                f"/api/v1/admin/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Backend mid", company="Ingress MMC", text="Yenilenmis metn"),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["title"], "Backend mid")
            self.assertEqual(edited.json()["status"], "pending")
            self.assertNotIn("source_url", edited.text)

            approved = self.client.post(
                f"/api/v1/admin/jobs/{ad_id}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
            self.assertEqual(approved.json()["status"], "published")

            after = self.client.patch(
                f"/api/v1/admin/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Backend mid+", company="Ingress MMC", text="Dercden sonra"),
            )
            self.assertEqual(after.status_code, 200, after.text)
            self.assertEqual(after.json()["status"], "published")
            self.assertEqual(after.json()["title"], "Backend mid+")

        public = self.client.get("/api/v1/jobs")
        self.assertEqual(public.status_code, 200)
        self.assertEqual(len(public.json()["items"]), 1)
        self.assertEqual(public.json()["items"][0]["title"], "Backend mid+")
        self.assertNotIn("secret.example", public.text)
        self.assertNotIn("source_url", public.text)

        other = self._pending()
        with self._auth("job:staff", "admin-staff"):
            rejected = self.client.post(
                f"/api/v1/admin/jobs/{other['id']}/reject",
                headers={"Authorization": "Bearer test"},
                json={"reason": "Metn natamamdir"},
            )
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(rejected.json()["status"], "rejected")
            self.assertEqual(rejected.json()["reject_reason"], "Metn natamamdir")
            self.assertNotIn("source_url", rejected.text)

        self.assertEqual(self.client.get(f"/api/v1/jobs/{other['id']}").status_code, 404)
        public_ids = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertNotIn(other["id"], public_ids)

        with self._auth("job:employer", "admin-employer"):
            mine = self.client.get("/api/v1/cabinet/jobs", headers={"Authorization": "Bearer test"})
            statuses = {item["id"]: item["status"] for item in mine.json()["items"]}
            reasons = {item["id"]: item["reject_reason"] for item in mine.json()["items"]}
            self.assertEqual(statuses[other["id"]], "rejected")
            self.assertEqual(reasons[other["id"]], "Metn natamamdir")
            self.assertEqual(statuses[ad_id], "published")

        with self._auth("job:staff", "admin-staff"):
            closed = self.client.post(
                f"/api/v1/admin/jobs/{ad_id}/close",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(closed.status_code, 200, closed.text)
            self.assertEqual(closed.json()["status"], "closed")
            queue = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            order = [item["status"] for item in queue.json()["items"]]
            self.assertEqual(order, ["closed", "rejected"])

        self.assertEqual(self.client.get("/api/v1/jobs").json()["items"], [])
        conn = sqlite3.connect(self.db)
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.close()
        self.assertEqual(count, 2)

    def test_approve_and_reject_only_pending(self):
        ad = self._pending()
        with self._auth("job:staff", "admin-staff"):
            self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/approve",
                headers={"Authorization": "Bearer test"},
            )
            again = self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(again.status_code, 409)
            reject = self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/reject",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(reject.status_code, 409)

    def test_reject_needs_a_reason_and_resubmit_returns_to_pending(self):
        ad = self._pending()
        with self._auth("job:staff", "admin-staff"):
            missing = self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/reject",
                headers={"Authorization": "Bearer test"},
                json={"reason": "  "},
            )
            self.assertEqual(missing.status_code, 422)
            rejected = self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/reject",
                headers={"Authorization": "Bearer test"},
                json={"reason": "Sirket adi yanlisdir"},
            )
            self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(self.client.get("/api/v1/jobs").json()["items"], [])
        with self._auth("job:employer", "admin-employer"):
            edited = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad['id']}",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Duzeldilmis rol", text="Yeni metn"),
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["status"], "pending")
            self.assertEqual(edited.json()["reject_reason"], "")
        self.assertEqual(self.client.get(f"/api/v1/jobs/{ad['id']}").status_code, 404)

    def test_crawled_ads_can_be_edited_hidden_and_merged_without_urls(self):
        conn = sqlite3.connect(self.db)
        ids = []
        for index, url in enumerate(("https://secret.example/a", "https://secret.example/b"), start=1):
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject
                ) VALUES (?, 'Busy', 'Baki', 'Toplanmis metn', 'published', ?, ?, '')
                """,
                (f"Toplanan {index}", "2026-10-04T12:00:00+04:00", f"crawl-{index}"),
            )
            job_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                VALUES (?, 'busy.az', ?, '', '2026-10-04T12:00:00+04:00')
                """,
                (job_id, url),
            )
            ids.append(job_id)
        conn.commit()
        conn.close()

        self.assertEqual(self.client.get("/api/v1/admin/crawled").status_code, 401)
        with self._auth("job:employer", "admin-employer"):
            denied = self.client.get("/api/v1/admin/crawled", headers={"Authorization": "Bearer test"})
            self.assertEqual(denied.status_code, 403)

        with self._auth("job:staff", "admin-staff"):
            listed = self.client.get("/api/v1/admin/crawled", headers={"Authorization": "Bearer test"})
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual([item["id"] for item in listed.json()["items"]], [ids[1], ids[0]])
            self.assertNotIn("source_url", listed.text)
            self.assertNotIn("secret.example", listed.text)
            one = self.client.get(
                f"/api/v1/admin/crawled/{ids[0]}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(one.status_code, 200, one.text)
            self.assertEqual(one.json()["id"], ids[0])
            self.assertEqual(one.json()["text"], "Toplanmis metn")
            self.assertNotIn("source_url", one.text)
            edited = self.client.patch(
                f"/api/v1/admin/crawled/{ids[0]}",
                headers={"Authorization": "Bearer test"},
                json={
                    "title": "Toplanan duzelis",
                    "company": "Busy",
                    "city": "Baki",
                    "remote": False,
                    "text": "Redakte metn",
                    "language": "az",
                    "salary": "",
                    "job_type": "",
                },
            )
            self.assertEqual(edited.status_code, 200, edited.text)
            self.assertEqual(edited.json()["title"], "Toplanan duzelis")
            self.assertNotIn("source_url", edited.text)
            hidden = self.client.post(
                f"/api/v1/admin/crawled/{ids[0]}/hide",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(hidden.status_code, 200, hidden.text)
            self.assertTrue(hidden.json()["hidden"])
            merged = self.client.post(
                "/api/v1/admin/crawled/merge",
                headers={"Authorization": "Bearer test"},
                json={"keep_id": ids[0], "hide_id": ids[1]},
            )
            self.assertEqual(merged.status_code, 409)
            shown = self.client.post(
                f"/api/v1/admin/crawled/{ids[0]}/show",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(shown.status_code, 200, shown.text)
            merged = self.client.post(
                "/api/v1/admin/crawled/merge",
                headers={"Authorization": "Bearer test"},
                json={"keep_id": ids[0], "hide_id": ids[1]},
            )
            self.assertEqual(merged.status_code, 200, merged.text)
            self.assertFalse(merged.json()["kept"]["hidden"])
            self.assertTrue(merged.json()["hidden"]["hidden"])
            self.assertEqual(merged.json()["hidden"]["merged_into"], ids[0])
            self.assertNotIn("secret.example", merged.text)

        public = self.client.get("/api/v1/jobs")
        public_ids = {item["id"] for item in public.json()["items"]}
        self.assertIn(ids[0], public_ids)
        self.assertNotIn(ids[1], public_ids)
        self.assertNotIn("secret.example", public.text)
        self.assertEqual(self.client.get(f"/api/v1/jobs/{ids[1]}").status_code, 404)
        conn = sqlite3.connect(self.db)
        remembered = conn.execute(
            "SELECT kept_id, hidden_id FROM job_merges"
        ).fetchone()
        locked = conn.execute(
            "SELECT content_locked FROM jobs WHERE id = ?",
            (ids[0],),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(tuple(remembered), (ids[0], ids[1]))
        self.assertEqual(locked, 1)

    def test_manual_source_publishes_without_showing_the_url(self):
        body = self._ad(company="Manual MMC", text="LinkedIn-de gorulen rol")
        body["source_url"] = "https://www.linkedin.com/jobs/view/manual-1"
        self.assertEqual(
            self.client.post("/api/v1/admin/jobs", json=body).status_code,
            401,
        )
        with self._auth("job:employer", "admin-employer"):
            denied = self.client.post(
                "/api/v1/admin/jobs",
                headers={"Authorization": "Bearer test"},
                json=body,
            )
            self.assertEqual(denied.status_code, 403)
        with self._auth("job:staff", "admin-staff"):
            bad = self.client.post(
                "/api/v1/admin/jobs",
                headers={"Authorization": "Bearer test"},
                json={**body, "source_url": "javascript:alert(1)"},
            )
            self.assertEqual(bad.status_code, 422)
            created = self.client.post(
                "/api/v1/admin/jobs",
                headers={"Authorization": "Bearer test"},
                json=body,
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad = created.json()
            self.assertEqual(ad["status"], "published")
            self.assertNotIn("source_url", ad)
            self.assertNotIn("linkedin.com", created.text)
        public = self.client.get("/api/v1/jobs")
        self.assertEqual(public.json()["items"][0]["id"], ad["id"])
        self.assertTrue(public.json()["items"][0]["onsite"])
        self.assertTrue(public.json()["items"][0]["has_original"])
        self.assertNotIn("linkedin.com", public.text)
        self.assertNotIn("source_url", public.text)
        guest = self.client.get(f"/api/v1/jobs/{ad['id']}/original")
        self.assertEqual(guest.status_code, 401)
        self.assertNotIn("linkedin.com", guest.text)
        with self._auth("job:candidate", "manual-candidate"):
            original = self.client.get(
                f"/api/v1/jobs/{ad['id']}/original",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(original.status_code, 200)
            self.assertEqual(original.json()["url"], body["source_url"])


class AdminAiFlagTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def test_employer_forbidden_and_staff_put(self):
        with self._auth("job:employer", "ai-employer"):
            denied = self.client.get(
                "/api/v1/admin/ai-flags",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(denied.status_code, 403)

        env = {"OPENAI_API_KEY": "sk-test", "AI_GATEWAY_ENABLED": "1"}
        with patch.dict(os.environ, env, clear=False):
            with self._auth("job:staff", "ai-staff"):
                headers = {"Authorization": "Bearer test"}
                got = self.client.get("/api/v1/admin/ai-flags", headers=headers)
                self.assertEqual(got.status_code, 200, got.text)
                body = got.json()
                self.assertTrue(body["key_configured"])
                self.assertTrue(body["flags"]["gateway"])
                self.assertTrue(body["flags"]["rerank"])

                saved = self.client.put(
                    "/api/v1/admin/ai-flags",
                    headers=headers,
                    json={"flags": {"rerank": False, "digest_intro": False}},
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertFalse(saved.json()["flags"]["rerank"])
                self.assertFalse(saved.json()["flags"]["digest_intro"])
                self.assertTrue(saved.json()["flags"]["gateway"])

                again = self.client.get("/api/v1/admin/ai-flags", headers=headers)
                self.assertFalse(again.json()["flags"]["rerank"])

                bad = self.client.put(
                    "/api/v1/admin/ai-flags",
                    headers=headers,
                    json={"flags": {"nope": True}},
                )
                self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
