"""Staff moderation: approve, reject, close, and edit without leaking source URLs."""

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import (
    SWEEP_AI_HIDDEN_STEP,
    ensure_schema,
    sweep_published_ai_hidden_to_rejected,
)
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
            self.assertEqual(items[0].get("source_url") or "", "")
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
            listed_items = {item["id"]: item for item in listed.json()["items"]}
            self.assertEqual(listed_items[ids[0]].get("source_name"), "busy.az")
            self.assertEqual(listed_items[ids[0]].get("source_url"), "https://secret.example/a")
            self.assertEqual(listed_items[ids[0]].get("text") or "", "")
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

            # Collected "Gizlət" rejects → Rejected tab (leaves Collected).
            rejected = self.client.post(
                f"/api/v1/admin/crawled/{ids[0]}/hide",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(rejected.json()["status"], "rejected")
            self.assertFalse(rejected.json()["hidden"])
            after_hide = self.client.get(
                "/api/v1/admin/crawled",
                headers={"Authorization": "Bearer test"},
            )
            self.assertNotIn(ids[0], {item["id"] for item in after_hide.json()["items"]})
            moderation = self.client.get(
                "/api/v1/admin/jobs",
                headers={"Authorization": "Bearer test"},
            )
            rejected_items = {
                item["id"]: item
                for item in moderation.json()["items"]
                if item.get("status") == "rejected"
            }
            self.assertIn(ids[0], rejected_items)
            self.assertIn("gizlətdi", (rejected_items[ids[0]].get("reject_reason") or "").lower())

        public = self.client.get("/api/v1/jobs")
        public_ids = {item["id"] for item in public.json()["items"]}
        self.assertNotIn(ids[0], public_ids)
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
        status_hidden = conn.execute(
            "SELECT status, COALESCE(hidden, 0), reject_reason FROM jobs WHERE id = ?",
            (ids[0],),
        ).fetchone()
        conn.close()
        self.assertEqual(tuple(remembered), (ids[0], ids[1]))
        self.assertEqual(locked, 1)
        self.assertEqual(status_hidden[0], "rejected")
        self.assertEqual(status_hidden[1], 0)
        self.assertIn("gizlətdi", (status_hidden[2] or "").lower())

    def test_crawled_list_only_published_scraped(self):
        """Collected tab is published scraped only — pending stays on the queue."""
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject
            ) VALUES ('Pending scrape', 'Co', 'Baki', 'Body', 'pending', ?, ?, '')
            """,
            ("2026-10-16T12:00:00+04:00", "crawled-pending-only"),
        )
        pending_id = int(cur.lastrowid)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject
            ) VALUES ('Live scrape', 'Co', 'Baki', 'Body', 'published', ?, ?, '')
            """,
            ("2026-10-16T12:00:00+04:00", "crawled-published-only"),
        )
        published_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

        with self._auth("job:staff", "admin-staff"):
            headers = {"Authorization": "Bearer test"}
            crawled = self.client.get("/api/v1/admin/crawled", headers=headers)
            self.assertEqual(crawled.status_code, 200, crawled.text)
            ids = {item["id"] for item in crawled.json()["items"]}
            self.assertIn(published_id, ids)
            self.assertNotIn(pending_id, ids)
            queue = self.client.get("/api/v1/admin/jobs", headers=headers)
            self.assertEqual(queue.status_code, 200, queue.text)
            queue_ids = {item["id"] for item in queue.json()["items"]}
            self.assertIn(pending_id, queue_ids)

    def test_scraped_pending_appears_in_queue_and_bulk_approve_publishes(self):
        conn = sqlite3.connect(self.db)
        ids = []
        for index in (1, 2):
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject
                ) VALUES (?, 'Crawl Co', 'Baki', 'Scraped body', 'pending', ?, ?, '')
                """,
                (f"Scraped {index}", "2026-10-13T12:00:00+04:00", f"scraped-pending-{index}"),
            )
            job_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                VALUES (?, 'busy.az', ?, '', '2026-10-13T12:00:00+04:00')
                """,
                (job_id, f"https://secret.example/scraped-{index}"),
            )
            ids.append(job_id)
        live = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject
            ) VALUES ('Already live', 'Crawl Co', 'Baki', 'Live body', 'published', ?, ?, '')
            """,
            ("2026-10-13T12:00:00+04:00", "scraped-live"),
        )
        live_id = int(live.lastrowid)
        conn.commit()
        conn.close()

        before = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertEqual(before, {live_id})

        with self._auth("job:staff", "admin-staff"):
            queue = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(queue.status_code, 200, queue.text)
            pending_ids = [item["id"] for item in queue.json()["items"] if item["status"] == "pending"]
            self.assertEqual(set(pending_ids), set(ids))
            self.assertNotIn(live_id, pending_ids)
            for item in queue.json()["items"]:
                if item["id"] in ids:
                    self.assertEqual(item.get("owner_subject") or "", "")
                    self.assertEqual(item.get("source_name"), "busy.az")
                    self.assertTrue(str(item.get("source_url") or "").startswith("https://secret.example/scraped-"))
                    self.assertEqual(item.get("text") or "", "")
                    self.assertEqual(item.get("created_at"), "2026-10-13T12:00:00+04:00")

            rejected = self.client.post(
                f"/api/v1/admin/jobs/{ids[0]}/reject",
                headers={"Authorization": "Bearer test"},
                json={"reason": "Duplicate scrape"},
            )
            self.assertEqual(rejected.status_code, 200, rejected.text)
            self.assertEqual(rejected.json()["status"], "rejected")
            after_reject = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(after_reject.status_code, 200, after_reject.text)
            rejected_row = next(item for item in after_reject.json()["items"] if item["id"] == ids[0])
            self.assertEqual(rejected_row["status"], "rejected")
            self.assertEqual(rejected_row.get("reject_reason"), "Duplicate scrape")
            self.assertEqual(rejected_row.get("owner_subject") or "", "")
            detail = self.client.get(
                f"/api/v1/admin/jobs/{ids[0]}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json()["status"], "rejected")

            # Rejected ads stay off the public list until staff explicitly approve them.
            mid_ids = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
            self.assertEqual(mid_ids, {live_id})

            # Since 86ee2cd (business-rules: "Approve always means published (pending or
            # rejected → published)"), bulk approve publishes pending AND rejected ads;
            # already-published and unknown ids are skipped without failing.
            bulk = self.client.post(
                "/api/v1/admin/jobs/approve-bulk",
                headers={"Authorization": "Bearer test"},
                json={"ids": [ids[1], ids[0], live_id, 999999]},
            )
            self.assertEqual(bulk.status_code, 200, bulk.text)
            self.assertEqual(bulk.json()["approved"], 2)
            self.assertEqual([item["id"] for item in bulk.json()["items"]], [ids[1], ids[0]])
            self.assertTrue(all(item["status"] == "published" for item in bulk.json()["items"]))

        public_ids = {item["id"] for item in self.client.get("/api/v1/jobs").json()["items"]}
        self.assertEqual(public_ids, {ids[0], ids[1], live_id})

    def test_backfill_confidence_fills_rule_then_ai(self):
        conn = sqlite3.connect(self.db)
        clear_id = int(
            conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    remote, relocation
                ) VALUES (
                    'Remote Engineer', 'Co', 'Worldwide', 'Fully remote role, open to candidates worldwide.',
                    'pending', '2026-10-14T12:00:00+04:00', 'bf-clear', '', 1, 0
                )
                """
            ).lastrowid
        )
        unclear_id = int(
            conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    remote, relocation
                ) VALUES (
                    'Office Engineer', 'Co', '', 'Build products with our team.',
                    'pending', '2026-10-14T12:00:00+04:00', 'bf-unclear', '', 0, 0
                )
                """
            ).lastrowid
        )
        conn.commit()
        conn.close()

        verdict = {
            "suitable": True,
            "remote": False,
            "relocation": True,
            "visa_support": True,
            "reason": "visa ok",
            "confidence": 81,
        }
        with self._auth("job:staff", "admin-staff"):
            with patch("worker.market_fit.clarify_market_fit", return_value=verdict):
                res = self.client.post(
                    "/api/v1/admin/jobs/backfill-confidence",
                    headers={"Authorization": "Bearer test"},
                    json={"ai_limit": 40},
                )
            self.assertEqual(res.status_code, 200, res.text)
            body = res.json()
            self.assertGreaterEqual(body["rule_filled"], 1)
            self.assertEqual(body["ai_checked"], 1)
            self.assertEqual(body["ai_rejected"], 0)

        conn = sqlite3.connect(self.db)
        rule, ai_clear = conn.execute(
            "SELECT rule_confidence, ai_confidence FROM jobs WHERE id = ?",
            (clear_id,),
        ).fetchone()
        rule2, ai_unclear = conn.execute(
            "SELECT rule_confidence, ai_confidence FROM jobs WHERE id = ?",
            (unclear_id,),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(rule)
        self.assertGreaterEqual(int(rule), 70)
        self.assertLessEqual(int(rule), 80)  # rules alone never reach the 85 band
        self.assertIsNone(ai_clear)
        self.assertIsNone(rule2)
        # AI said 81 but nothing in the ad confirms working from AZ: eligibility cap 40.
        self.assertEqual(ai_unclear, 40)

    def test_threshold_approve_and_recheck_market_fit(self):
        conn = sqlite3.connect(self.db)
        rows = [
            ("High AI", 90, None),
            ("Low AI", 40, None),
            ("Rule clear", None, 100),
            ("No score", None, None),
        ]
        ids = {}
        for title, ai, rule in rows:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    ai_confidence, rule_confidence, market_fit_reason
                ) VALUES (?, 'Co', 'Baki', 'Body for market fit recheck.', 'pending', ?, ?, '', ?, ?, ?)
                """,
                (
                    title,
                    "2026-10-14T12:00:00+04:00",
                    f"thresh-{title}",
                    ai,
                    rule,
                    "seed",
                ),
            )
            ids[title] = int(cur.lastrowid)
        conn.commit()
        conn.close()

        with self._auth("job:staff", "admin-staff"):
            queue = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(queue.status_code, 200, queue.text)
            by_id = {item["id"]: item for item in queue.json()["items"]}
            self.assertEqual(by_id[ids["High AI"]]["ai_confidence"], 90)
            self.assertEqual(by_id[ids["Rule clear"]]["rule_confidence"], 100)
            self.assertIsNone(by_id[ids["No score"]]["ai_confidence"])

            published = self.client.post(
                "/api/v1/admin/jobs/approve-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "gte", "threshold": 80},
            )
            self.assertEqual(published.status_code, 200, published.text)
            self.assertEqual(published.json()["approved"], 1)
            self.assertEqual(published.json()["items"][0]["id"], ids["High AI"])

            low = self.client.post(
                "/api/v1/admin/jobs/approve-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "lte", "threshold": 50},
            )
            self.assertEqual(low.status_code, 200, low.text)
            self.assertEqual(low.json()["approved"], 1)
            self.assertEqual(low.json()["items"][0]["id"], ids["Low AI"])

            rule_pub = self.client.post(
                "/api/v1/admin/jobs/approve-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "rule", "op": "gte", "threshold": 90},
            )
            self.assertEqual(rule_pub.status_code, 200, rule_pub.text)
            self.assertEqual(rule_pub.json()["approved"], 1)
            self.assertEqual(rule_pub.json()["items"][0]["id"], ids["Rule clear"])

            verdict = {
                "suitable": False,
                "remote": False,
                "relocation": False,
                "visa_support": False,
                "reason": "not az market",
                "confidence": 22,
            }
            conn = sqlite3.connect(self.db)
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    rule_confidence, ai_confidence, market_fit_reason
                ) VALUES (
                    'Recheck me', 'Co', '', 'Backend role.', 'pending', ?, ?, '',
                    100, 55, ''
                )
                """,
                ("2026-10-14T13:00:00+04:00", "thresh-recheck"),
            )
            recheck_id = int(cur.lastrowid)
            conn.commit()
            conn.close()
            with patch("worker.market_fit.clarify_market_fit", return_value=verdict):
                again = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": [recheck_id]},
                )
                self.assertEqual(again.status_code, 200, again.text)
                job_key = again.json()["job_id"]
                self.assertTrue(job_key)
                status_body = None
                for _ in range(40):
                    polled = self.client.get(
                        f"/api/v1/admin/jobs/recheck-market-fit/{job_key}",
                        headers={"Authorization": "Bearer test"},
                    )
                    self.assertEqual(polled.status_code, 200, polled.text)
                    status_body = polled.json()
                    if status_body.get("status") in ("done", "failed"):
                        break
                    import time

                    time.sleep(0.05)
            self.assertIsNotNone(status_body)
            self.assertEqual(status_body["status"], "done")
            self.assertEqual(status_body["checked"], 1)
            self.assertEqual(status_body["rejected"], 1)
            self.assertEqual(status_body["failed"], 0)
            conn = sqlite3.connect(self.db)
            status, reason, conf, rule_val = conn.execute(
                """
                SELECT status, reject_reason, ai_confidence, rule_confidence
                FROM jobs WHERE id = ?
                """,
                (recheck_id,),
            ).fetchone()
            conn.close()
            self.assertEqual(status, "rejected")
            self.assertTrue(reason.startswith("not az market"), reason)
            self.assertEqual(conf, 22)
            self.assertIsNone(rule_val)

    def test_recheck_rejects_foreign_onsite_without_ai(self):
        """Eligibility gate: on-site Tokyo ad with no relocation is rejected before any AI call."""
        from app.cabinet_store import recheck_market_fit

        conn = sqlite3.connect(self.db)
        job_id = int(
            conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    rule_confidence, ai_confidence, market_fit_reason
                ) VALUES (
                    'Office Engineer', 'Co', 'Tokyo', 'Build products in our Tokyo office.',
                    'pending', '2026-10-14T13:00:00+04:00', 'elig-tokyo', '', 95, NULL, ''
                )
                """
            ).lastrowid
        )
        conn.commit()
        conn.close()
        with patch("worker.market_fit.clarify_market_fit") as ai:
            result = recheck_market_fit([job_id], scope="queue")
        ai.assert_not_called()
        self.assertEqual(result["rejected"], 1)
        conn = sqlite3.connect(self.db)
        status, conf, reason = conn.execute(
            "SELECT status, ai_confidence, market_fit_reason FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        conn.close()
        self.assertEqual(status, "rejected")
        self.assertLessEqual(conf, 10)
        self.assertTrue(reason.startswith("Qayda: "))

    def test_recheck_market_fit_cancel_keeps_done_stops_rest(self):
        """Stop cancels remaining ads only; already-checked results stay written."""
        import threading
        import time

        ids = []
        conn = sqlite3.connect(self.db)
        for i in range(5):
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key, owner_subject,
                    rule_confidence, ai_confidence, market_fit_reason
                ) VALUES (?, 'Co', 'Baki', 'Role text.', 'pending', ?, ?, '', 80, NULL, '')
                """,
                (f"Cancel me {i}", "2026-10-14T16:00:00+04:00", f"cancel-recheck-{i}"),
            )
            ids.append(int(cur.lastrowid))
        conn.commit()
        conn.close()

        started = threading.Event()
        calls = {"n": 0}

        def slow_recheck(ad_id, scope="queue"):
            calls["n"] += 1
            if calls["n"] == 1:
                started.set()
            time.sleep(0.15)
            return "checked"

        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=slow_recheck):
                started_res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": ids},
                )
                self.assertEqual(started_res.status_code, 200, started_res.text)
                job_key = started_res.json()["job_id"]
                self.assertTrue(started.wait(timeout=2))
                cancelled = self.client.post(
                    f"/api/v1/admin/jobs/recheck-market-fit/{job_key}/cancel",
                    headers={"Authorization": "Bearer test"},
                )
                self.assertEqual(cancelled.status_code, 200, cancelled.text)
                self.assertIn(
                    cancelled.json().get("status"),
                    ("cancelling", "cancelled", "running", "queued"),
                )

                status_body = None
                for _ in range(80):
                    polled = self.client.get(
                        f"/api/v1/admin/jobs/recheck-market-fit/{job_key}",
                        headers={"Authorization": "Bearer test"},
                    )
                    self.assertEqual(polled.status_code, 200, polled.text)
                    status_body = polled.json()
                    if status_body.get("status") == "cancelled":
                        break
                    time.sleep(0.05)

        self.assertIsNotNone(status_body)
        self.assertEqual(status_body["status"], "cancelled")
        self.assertLess(calls["n"], 5)
        self.assertGreaterEqual(calls["n"], 1)
        self.assertGreaterEqual(int(status_body.get("done") or 0), 1)
        self.assertGreater(int(status_body.get("remaining") or 0), 0)

    def test_recheck_market_fit_stale_cancelling_finalizes(self):
        """GET poll closes orphaned cancelling jobs so UI cannot stick on stop."""
        from datetime import datetime, timedelta, timezone

        from app import market_fit_recheck_jobs as jobs
        from app.cabinet_store import _LOCK, _connect

        stale_at = (datetime.now(timezone.utc) - timedelta(seconds=120)).astimezone().isoformat(
            timespec="seconds"
        )
        with _LOCK:
            conn = _connect()
            try:
                jobs._ensure(conn)
                conn.execute(
                    """
                    INSERT INTO market_fit_recheck_jobs (
                        id, scope, status, total, done, checked, rejected, hidden,
                        failed, skipped, error, job_ids, created_by, created_at, updated_at
                    ) VALUES (?, 'crawled', 'cancelling', 18, 6, 6, 0, 0, 0, 0, '', '[]', '', ?, ?)
                    """,
                    ("stale-cancel-job", stale_at, stale_at),
                )
                conn.commit()
            finally:
                conn.close()

        with self._auth("job:staff", "admin-staff"):
            with patch.object(jobs, "_STALE_SECONDS", 90):
                polled = self.client.get(
                    "/api/v1/admin/jobs/recheck-market-fit/stale-cancel-job",
                    headers={"Authorization": "Bearer test"},
                )
        self.assertEqual(polled.status_code, 200, polled.text)
        body = polled.json()
        self.assertEqual(body["status"], "cancelled")
        self.assertEqual(int(body["done"]), 6)
        self.assertEqual(int(body["remaining"]), 12)

    # --- Fresh «AI ilə yenidən yoxla» (selected ids / filter + limit / cap) ---

    def _seed_pending(self, title, *, ai=None, rule=None, source=None, key=None):
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                rule_confidence, ai_confidence, market_fit_reason
            ) VALUES (?, 'Co', '', 'Backend role.', 'pending', '2026-10-22T12:00:00+04:00', ?, '', ?, ?, 'seed')
            """,
            (title, key or f"fresh-{title}", rule, ai),
        )
        job_id = int(cur.lastrowid)
        if source:
            conn.execute(
                """
                INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                VALUES (?, ?, ?, '', '2026-10-22T12:00:00+04:00')
                """,
                (job_id, source, f"https://{source.lower()}.example/job/{job_id}"),
            )
        conn.commit()
        conn.close()
        return job_id

    def _poll_recheck(self, job_key):
        import time

        body = None
        for _ in range(80):
            polled = self.client.get(
                f"/api/v1/admin/jobs/recheck-market-fit/{job_key}",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(polled.status_code, 200, polled.text)
            body = polled.json()
            if body.get("status") in ("done", "failed", "cancelled"):
                break
            time.sleep(0.05)
        return body

    def test_fresh_recheck_selected_ids_rescored_even_with_existing_ai_score(self):
        scored = self._seed_pending("Already scored", ai=90)
        untouched = self._seed_pending("Not selected", ai=90)
        verdict = {
            "suitable": True,
            "unclear": False,
            "remote": True,
            "relocation": False,
            "reason": "fresh AI answer",
            "confidence": 70,
        }
        with self._auth("job:staff", "admin-staff"):
            with patch("worker.market_fit.clarify_market_fit", return_value=verdict) as ai:
                res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": [scored], "scope": "queue", "fresh": True},
                )
                self.assertEqual(res.status_code, 200, res.text)
                started = res.json()
                self.assertTrue(started["fresh"])
                self.assertEqual(started["total"], 1)
                self.assertEqual(started["requested"], 1)
                self.assertFalse(started["capped"])
                body = self._poll_recheck(started["job_id"])
        self.assertEqual(body["status"], "done")
        self.assertEqual(body["checked"], 1)
        ai.assert_called_once()
        # The AI cache must be bypassed for a staff re-check.
        self.assertTrue(ai.call_args.kwargs.get("fresh"))
        conn = sqlite3.connect(self.db)
        rows = dict(
            conn.execute(
                "SELECT id, ai_confidence FROM jobs WHERE id IN (?, ?)", (scored, untouched)
            ).fetchall()
        )
        conn.close()
        # Fresh AI 70 capped by eligibility (no AZ evidence in "Backend role.") → 40;
        # the old 90 is replaced, the unselected row keeps its score.
        self.assertEqual(rows[scored], 40)
        self.assertEqual(rows[untouched], 90)

    def test_fresh_recheck_without_selection_uses_list_filter_and_limit(self):
        a1 = self._seed_pending("Alpha old", ai=30, source="Alpha")
        a2 = self._seed_pending("Alpha mid", ai=10, source="Alpha")
        a3 = self._seed_pending("Alpha new", ai=40, source="Alpha")
        self._seed_pending("Alpha high", ai=95, source="Alpha")
        self._seed_pending("Beta", ai=10, source="Beta")
        self._seed_pending("Alpha unscored", ai=None, source="Alpha")
        calls = []

        def record(ad_id, scope="queue", fresh=False):
            calls.append((ad_id, scope, fresh))
            return "checked"

        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=record):
                res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={
                        "ids": [],
                        "scope": "queue",
                        "fresh": True,
                        "filter": {"ai_op": "lte", "ai_value": 50, "source": "alpha"},
                        "limit": 2,
                    },
                )
                self.assertEqual(res.status_code, 200, res.text)
                started = res.json()
                body = self._poll_recheck(started["job_id"])
        self.assertEqual(started["requested"], 3)
        self.assertEqual(started["total"], 2)
        self.assertTrue(started["capped"])
        self.assertEqual(body["status"], "done")
        # Table order (newest first), AI ≤ 50, source contains "alpha", limit 2.
        self.assertEqual([c[0] for c in calls], [a3, a2])
        self.assertTrue(all(c[2] is True for c in calls))
        self.assertNotIn(a1, [c[0] for c in calls])

        with self._auth("job:staff", "admin-staff"):
            none = self.client.post(
                "/api/v1/admin/jobs/recheck-market-fit",
                headers={"Authorization": "Bearer test"},
                json={"fresh": True, "filter": {"source": "nope-source"}, "limit": 5},
            )
        self.assertEqual(none.status_code, 422, none.text)

    def test_fresh_recheck_caps_batch_and_limit_bounds(self):
        from app import market_fit_recheck_jobs as jobs

        ids = list(range(100000, 100000 + jobs.FRESH_MAX_IDS + 5))
        seen = []

        def record(ad_id, scope="queue", fresh=False):
            seen.append(ad_id)
            return "skipped"

        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=record):
                res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": ids, "fresh": True},
                )
                self.assertEqual(res.status_code, 200, res.text)
                started = res.json()
                body = self._poll_recheck(started["job_id"])
            too_big = self.client.post(
                "/api/v1/admin/jobs/recheck-market-fit",
                headers={"Authorization": "Bearer test"},
                json={"ids": ids[:3], "fresh": True, "limit": jobs.FRESH_MAX_IDS + 1},
            )
        self.assertEqual(started["total"], jobs.FRESH_MAX_IDS)
        self.assertEqual(started["requested"], jobs.FRESH_MAX_IDS + 5)
        self.assertTrue(started["capped"])
        self.assertEqual(body["status"], "done")
        self.assertEqual(len(seen), jobs.FRESH_MAX_IDS)
        self.assertEqual(seen, ids[: jobs.FRESH_MAX_IDS])
        self.assertEqual(too_big.status_code, 422, too_big.text)

    def test_fresh_recheck_refuses_second_concurrent_run(self):
        import threading

        gate = threading.Event()
        entered = threading.Event()

        def slow(ad_id, scope="queue", fresh=False):
            entered.set()
            gate.wait(timeout=3)
            return "checked"

        job_id = self._seed_pending("Concurrent", ai=50)
        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=slow):
                first = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": [job_id], "fresh": True},
                )
                self.assertEqual(first.status_code, 200, first.text)
                self.assertTrue(entered.wait(timeout=2))
                second = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"ids": [job_id], "fresh": True},
                )
                gate.set()
                body = self._poll_recheck(first.json()["job_id"])
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(body["status"], "done")

    def test_crawled_recheck_rejects_published_unsuitable(self):
        """Published scraped ads AI marks unfit become rejected (Rejected tab), not only hidden."""
        from app.cabinet_store import recheck_market_fit

        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                hidden, ai_confidence, market_fit_reason
            ) VALUES (
                'Live unfit', 'Co', '', 'Backend role.', 'published', ?, ?, '',
                0, NULL, ''
            )
            """,
            ("2026-10-14T15:00:00+04:00", "crawled-pub-unfit"),
        )
        job_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

        verdict = {
            "suitable": False,
            "remote": False,
            "relocation": False,
            "visa_support": False,
            "reason": "foreign office",
            "confidence": 12,
        }
        with patch("worker.market_fit.clarify_market_fit", return_value=verdict):
            result = recheck_market_fit([job_id], scope="crawled")
        self.assertEqual(result["rejected"], 1)
        self.assertEqual(result["hidden"], 0)
        self.assertEqual(result["failed"], 0)

        conn = sqlite3.connect(self.db)
        status, reason, hidden, conf = conn.execute(
            """
            SELECT status, reject_reason, COALESCE(hidden, 0), ai_confidence
            FROM jobs WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(status, "rejected")
        self.assertTrue(reason.startswith("foreign office"), reason)
        self.assertEqual(hidden, 0)
        self.assertEqual(conf, 12)

        with self._auth("job:staff", "admin-staff"):
            headers = {"Authorization": "Bearer test"}
            queue = self.client.get("/api/v1/admin/jobs", headers=headers)
            self.assertEqual(queue.status_code, 200, queue.text)
            row = next(item for item in queue.json()["items"] if item["id"] == job_id)
            self.assertEqual(row["status"], "rejected")
            crawled = self.client.get("/api/v1/admin/crawled", headers=headers)
            self.assertEqual(crawled.status_code, 200, crawled.text)
            self.assertNotIn(job_id, {item["id"] for item in crawled.json()["items"]})

    def test_sweep_published_ai_hidden_to_rejected(self):
        """Legacy published+hidden AI unfit rows move to rejected once."""
        conn = sqlite3.connect(self.db)
        # Schema setup already marked the step done on the empty DB.
        conn.execute("DELETE FROM maintenance_steps WHERE name = ?", (SWEEP_AI_HIDDEN_STEP,))
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                hidden, ai_confidence, reject_reason, market_fit_reason
            ) VALUES (
                'Old AI hide', 'Co', 'Tokyo', 'Office Japan.', 'published', ?, ?, '',
                1, 18, 'foreign office', 'foreign office'
            )
            """,
            ("2026-10-14T12:00:00+04:00", "sweep-ai-hidden"),
        )
        target = int(cur.lastrowid)
        # Staff hide only (no AI fingerprint) — leave alone.
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                hidden, ai_confidence, reject_reason, market_fit_reason
            ) VALUES (
                'Staff hide', 'Co', 'Baki', 'Remote worldwide.', 'published', ?, ?, '',
                1, NULL, '', ''
            )
            """,
            ("2026-10-14T12:00:00+04:00", "sweep-staff-hide"),
        )
        staff_hide = int(cur.lastrowid)
        # Title-rule hide (has scores but system reason) — leave alone.
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                hidden, ai_confidence, reject_reason, market_fit_reason
            ) VALUES (
                'Title rule', 'Co', 'Baki', 'Remote worldwide.', 'published', ?, ?, '',
                1, 40, 'title_rule_2026_10_13', 'title rule pass'
            )
            """,
            ("2026-10-14T12:00:00+04:00", "sweep-title-rule"),
        )
        title_hide = int(cur.lastrowid)
        conn.commit()
        n = sweep_published_ai_hidden_to_rejected(conn)
        conn.commit()
        self.assertEqual(n, 1)
        self.assertEqual(sweep_published_ai_hidden_to_rejected(conn), 0)

        rows = {
            int(r[0]): (r[1], int(r[2] or 0), r[3])
            for r in conn.execute(
                "SELECT id, status, COALESCE(hidden, 0), reject_reason FROM jobs WHERE id IN (?, ?, ?)",
                (target, staff_hide, title_hide),
            )
        }
        conn.close()
        self.assertEqual(rows[target], ("rejected", 0, "foreign office"))
        self.assertEqual(rows[staff_hide], ("published", 1, ""))
        self.assertEqual(rows[title_hide], ("published", 1, "title_rule_2026_10_13"))

        with self._auth("job:staff", "admin-staff"):
            queue = self.client.get("/api/v1/admin/jobs", headers={"Authorization": "Bearer test"})
            self.assertEqual(queue.status_code, 200, queue.text)
            row = next(item for item in queue.json()["items"] if item["id"] == target)
            self.assertEqual(row["status"], "rejected")

    def test_threshold_approve_rejected_status(self):
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                ai_confidence, rule_confidence, reject_reason, market_fit_reason
            ) VALUES (
                'Rejected high', 'Co', 'Baki', 'Remote worldwide.', 'rejected', ?, ?, '',
                88, NULL, 'old reject', 'seed'
            )
            """,
            ("2026-10-14T14:00:00+04:00", "thresh-rej-high"),
        )
        high_id = int(cur.lastrowid)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                ai_confidence, rule_confidence, reject_reason, market_fit_reason
            ) VALUES (
                'Rejected low', 'Co', 'Baki', 'Office only.', 'rejected', ?, ?, '',
                30, NULL, 'unsuitable', 'seed'
            )
            """,
            ("2026-10-14T14:01:00+04:00", "thresh-rej-low"),
        )
        low_id = int(cur.lastrowid)
        conn.commit()
        conn.close()

        with self._auth("job:staff", "admin-staff"):
            pending_only = self.client.post(
                "/api/v1/admin/jobs/approve-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "gte", "threshold": 80},
            )
            self.assertEqual(pending_only.status_code, 200, pending_only.text)
            self.assertEqual(pending_only.json()["approved"], 0)

            published = self.client.post(
                "/api/v1/admin/jobs/approve-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "gte", "threshold": 80, "status": "rejected"},
            )
            self.assertEqual(published.status_code, 200, published.text)
            self.assertEqual(published.json()["approved"], 1)
            self.assertEqual(published.json()["items"][0]["id"], high_id)

        conn = sqlite3.connect(self.db)
        high_status, high_reason = conn.execute(
            "SELECT status, reject_reason FROM jobs WHERE id = ?",
            (high_id,),
        ).fetchone()
        low_status = conn.execute(
            "SELECT status FROM jobs WHERE id = ?",
            (low_id,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(high_status, "published")
        self.assertEqual(high_reason, "")
        self.assertEqual(low_status, "rejected")

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

    def test_crawl_rejects_list_publish_threshold_and_clear(self):
        conn = sqlite3.connect(self.db)
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS crawl_rejects (
                source_url TEXT PRIMARY KEY,
                reason TEXT NOT NULL DEFAULT '',
                decided_at TEXT NOT NULL DEFAULT '',
                via_ai INTEGER NOT NULL DEFAULT 0
            );
            """
        )
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                owner_subject, hidden, ai_confidence, market_fit_reason
            ) VALUES (
                'Remote World', 'Co', '', 'Worldwide remote role.', 'published',
                '2026-10-14T12:00:00+04:00', 'cr-linked', '', 1, 88, 'ok'
            )
            """
        )
        job_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO job_sources (job_id, source_name, source_url, last_seen)
            VALUES (?, 'Example', 'https://example.com/jobs/1', '2026-10-14T12:00:00+04:00')
            """,
            (job_id,),
        )
        conn.execute(
            """
            INSERT INTO crawl_rejects (source_url, reason, decided_at, via_ai)
            VALUES
              ('https://example.com/jobs/1', 'foreign_locked_remote', '2026-10-14T13:00:00+00:00', 0),
              ('https://example.com/jobs/orphan', 'thin_description', '2026-10-14T14:00:00+00:00', 1)
            """
        )
        conn.commit()
        conn.close()

        with self._auth("job:staff", "admin-staff"):
            headers = {"Authorization": "Bearer test"}
            listed = self.client.get("/api/v1/admin/crawl-rejects", headers=headers)
            self.assertEqual(listed.status_code, 200, listed.text)
            items = listed.json()["items"]
            self.assertEqual(len(items), 2)
            by_url = {item["source_url"]: item for item in items}
            self.assertEqual(by_url["https://example.com/jobs/1"]["job_id"], job_id)
            self.assertEqual(by_url["https://example.com/jobs/1"]["ai_confidence"], 88)
            self.assertEqual(by_url["https://example.com/jobs/1"]["source_name"], "Example")
            self.assertIsNone(by_url["https://example.com/jobs/orphan"]["job_id"])
            self.assertEqual(by_url["https://example.com/jobs/orphan"]["source_name"], "example.com")

            published = self.client.post(
                "/api/v1/admin/crawl-rejects/publish-threshold",
                headers=headers,
                json={"score": "ai", "op": "gte", "threshold": 80},
            )
            self.assertEqual(published.status_code, 200, published.text)
            self.assertEqual(published.json()["published"], 1)

            cleared = self.client.post(
                "/api/v1/admin/crawl-rejects/clear",
                headers=headers,
                json={"urls": ["https://example.com/jobs/orphan"]},
            )
            self.assertEqual(cleared.status_code, 200, cleared.text)
            self.assertEqual(cleared.json()["cleared"], 1)

            again = self.client.get("/api/v1/admin/crawl-rejects", headers=headers)
            self.assertEqual(again.json()["items"], [])

        conn = sqlite3.connect(self.db)
        status, hidden = conn.execute(
            "SELECT status, hidden FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        left = conn.execute("SELECT COUNT(*) FROM crawl_rejects").fetchone()[0]
        conn.close()
        self.assertEqual(status, "published")
        self.assertEqual(hidden, 0)
        self.assertEqual(left, 0)


    # --- queue threshold panel: «Faizə uyğun rədd et» + unlimited «AI ilə yenidən yoxla» ---

    def _statuses(self, *ids):
        conn = sqlite3.connect(self.db)
        marks = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT id, status, reject_reason FROM jobs WHERE id IN ({marks})", ids
        ).fetchall()
        conn.close()
        return {row[0]: (row[1], row[2]) for row in rows}

    def test_reject_threshold_requires_staff(self):
        body = {"score": "ai", "op": "lte", "threshold": 40}
        guest = self.client.post("/api/v1/admin/jobs/reject-threshold", json=body)
        self.assertEqual(guest.status_code, 401)
        with self._auth("job:employer", "admin-employer"):
            denied = self.client.post(
                "/api/v1/admin/jobs/reject-threshold",
                headers={"Authorization": "Bearer test"},
                json=body,
            )
        self.assertEqual(denied.status_code, 403)

    def test_reject_threshold_validates_body(self):
        headers = {"Authorization": "Bearer test"}
        with self._auth("job:staff", "admin-staff"):
            for bad in (
                {"score": "x", "op": "lte", "threshold": 40},
                {"score": "ai", "op": "lt", "threshold": 40},
                {"score": "ai", "op": "lte", "threshold": 101},
                {"score": "ai", "op": "lte", "threshold": -1},
                {"score": "ai", "op": "lte", "threshold": 40, "status": "rejected"},
            ):
                res = self.client.post("/api/v1/admin/jobs/reject-threshold", headers=headers, json=bad)
                self.assertEqual(res.status_code, 422, (bad, res.text))

    def test_reject_threshold_ai_lte_rejects_only_matching_pending(self):
        low = self._seed_pending("Low AI", ai=20, rule=95)
        edge = self._seed_pending("Edge AI", ai=40, rule=95)
        high = self._seed_pending("High AI", ai=80, rule=10)
        unscored = self._seed_pending("No AI", ai=None, rule=10)
        conn = sqlite3.connect(self.db)
        cur = conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                ai_confidence, market_fit_reason
            ) VALUES ('Live low', 'Co', '', 'x', 'published', '2026-10-22T12:00:00+04:00',
                      'live-low', '', 5, 'seed')
            """
        )
        live = int(cur.lastrowid)
        conn.commit()
        conn.close()

        with self._auth("job:staff", "admin-staff"):
            res = self.client.post(
                "/api/v1/admin/jobs/reject-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "lte", "threshold": 40},
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["rejected"], 2)
        self.assertEqual(sorted(res.json()["ids"]), sorted([low, edge]))
        rows = self._statuses(low, edge, high, unscored, live)
        self.assertEqual(rows[low][0], "rejected")
        self.assertEqual(rows[edge][0], "rejected")
        self.assertIn("AI ≤ 40", rows[low][1])
        self.assertEqual(rows[high][0], "pending")
        self.assertEqual(rows[unscored][0], "pending")
        self.assertEqual(rows[live][0], "published")

    def test_reject_threshold_rule_gte_uses_rule_score_and_custom_reason(self):
        a = self._seed_pending("Rule high", ai=10, rule=90)
        b = self._seed_pending("Rule low", ai=95, rule=30)
        with self._auth("job:staff", "admin-staff"):
            res = self.client.post(
                "/api/v1/admin/jobs/reject-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "rule", "op": "gte", "threshold": 90, "reason": "  Staff   cut  "},
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["rejected"], 1)
        rows = self._statuses(a, b)
        self.assertEqual(rows[a], ("rejected", "Staff cut"))
        self.assertEqual(rows[b][0], "pending")

    def test_reject_threshold_no_match_returns_zero(self):
        keep = self._seed_pending("Keep", ai=70)
        with self._auth("job:staff", "admin-staff"):
            res = self.client.post(
                "/api/v1/admin/jobs/reject-threshold",
                headers={"Authorization": "Bearer test"},
                json={"score": "ai", "op": "gte", "threshold": 99},
            )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json(), {"rejected": 0, "ids": []})
        self.assertEqual(self._statuses(keep)[keep][0], "pending")

    def test_reject_threshold_notifies_owner(self):
        ad = self._pending()
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE jobs SET ai_confidence = 10 WHERE id = ?", (ad["id"],))
        conn.commit()
        conn.close()
        with self._auth("job:staff", "admin-staff"):
            with patch("app.notifications.deliver_email") as mail:
                res = self.client.post(
                    "/api/v1/admin/jobs/reject-threshold",
                    headers={"Authorization": "Bearer test"},
                    json={"score": "ai", "op": "lte", "threshold": 20},
                )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["rejected"], 1)
        conn = sqlite3.connect(self.db)
        kinds = [
            row[0]
            for row in conn.execute(
                "SELECT kind FROM notifications WHERE job_id = ?", (ad["id"],)
            ).fetchall()
        ]
        conn.close()
        self.assertIn("ad_rejected", kinds)
        self.assertEqual(mail.call_count, 1)

    def test_fresh_recheck_by_threshold_takes_all_matches_without_cap(self):
        from app import market_fit_recheck_jobs as jobs

        conn = sqlite3.connect(self.db)
        conn.executemany(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, owner_subject,
                ai_confidence, rule_confidence, market_fit_reason
            ) VALUES (?, 'Co', '', 'x', 'pending', '2026-10-22T12:00:00+04:00', ?, '', ?, 50, 'seed')
            """,
            [
                (f"Bulk {i}", f"bulk-thr-{i}", 30 if i % 2 == 0 else 90)
                for i in range(2 * jobs.FRESH_MAX_IDS + 10)
            ],
        )
        conn.commit()
        want = [
            row[0]
            for row in conn.execute(
                "SELECT id FROM jobs WHERE status = 'pending' AND ai_confidence <= 30 ORDER BY id DESC"
            ).fetchall()
        ]
        conn.close()
        self.assertGreater(len(want), jobs.FRESH_MAX_IDS)
        seen = []

        def record(ad_id, scope="queue", fresh=False):
            seen.append((ad_id, fresh))
            return "checked"

        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=record):
                res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={
                        "scope": "queue",
                        "fresh": True,
                        "threshold": {"score": "ai", "op": "lte", "threshold": 30},
                    },
                )
                self.assertEqual(res.status_code, 200, res.text)
                started = res.json()
                body = self._poll_recheck(started["job_id"])
        self.assertEqual(started["total"], len(want))
        self.assertEqual(started["requested"], len(want))
        self.assertFalse(started["capped"])
        self.assertEqual(body["status"], "done")
        self.assertEqual(body["checked"], len(want))
        self.assertEqual([s[0] for s in seen], want)
        self.assertTrue(all(s[1] for s in seen))

    def test_fresh_recheck_by_threshold_rule_gte_and_no_match(self):
        hit = self._seed_pending("Rule hit", ai=10, rule=85)
        self._seed_pending("Rule miss", ai=99, rule=20)
        seen = []

        def record(ad_id, scope="queue", fresh=False):
            seen.append(ad_id)
            return "checked"

        with self._auth("job:staff", "admin-staff"):
            with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=record):
                res = self.client.post(
                    "/api/v1/admin/jobs/recheck-market-fit",
                    headers={"Authorization": "Bearer test"},
                    json={"fresh": True, "threshold": {"score": "rule", "op": "gte", "threshold": 80}},
                )
                self.assertEqual(res.status_code, 200, res.text)
                self._poll_recheck(res.json()["job_id"])
            none = self.client.post(
                "/api/v1/admin/jobs/recheck-market-fit",
                headers={"Authorization": "Bearer test"},
                json={"fresh": True, "threshold": {"score": "rule", "op": "gte", "threshold": 100}},
            )
            wrong_scope = self.client.post(
                "/api/v1/admin/jobs/recheck-market-fit",
                headers={"Authorization": "Bearer test"},
                json={
                    "scope": "crawled",
                    "fresh": True,
                    "threshold": {"score": "rule", "op": "gte", "threshold": 10},
                },
            )
        self.assertEqual(seen, [hit])
        self.assertEqual(none.status_code, 422, none.text)
        self.assertEqual(wrong_scope.status_code, 422, wrong_scope.text)

    def test_fresh_recheck_stops_early_when_ai_budget_is_spent(self):
        import worker.market_fit as mf

        ids = [self._seed_pending(f"Budget {i}", ai=20) for i in range(5)]
        calls = []

        def broke(ad_id, scope="queue", fresh=False):
            calls.append(ad_id)
            mf.last_miss_error = "ai_budget_exceeded"
            return "failed"

        with self._auth("job:staff", "admin-staff"):
            try:
                with patch("app.market_fit_recheck_jobs.recheck_one", side_effect=broke):
                    res = self.client.post(
                        "/api/v1/admin/jobs/recheck-market-fit",
                        headers={"Authorization": "Bearer test"},
                        json={"fresh": True, "threshold": {"score": "ai", "op": "lte", "threshold": 20}},
                    )
                    self.assertEqual(res.status_code, 200, res.text)
                    body = None
                    import time

                    for _ in range(80):
                        body = self.client.get(
                            f"/api/v1/admin/jobs/recheck-market-fit/{res.json()['job_id']}",
                            headers={"Authorization": "Bearer test"},
                        ).json()
                        if body["status"] not in ("queued", "running", "cancelling"):
                            break
                        time.sleep(0.05)
            finally:
                mf.last_miss_error = ""
        self.assertEqual(body["status"], "budget_stopped")
        self.assertEqual(body["error"], "ai_budget_exceeded")
        self.assertEqual(len(calls), 1)
        self.assertEqual(body["total"], len(ids))
        self.assertEqual(body["remaining"], len(ids) - 1)


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
                self.assertIn("llm_rerank", body["flags"])
                self.assertIn("role_coach", body["flags"])
                self.assertIn("engagement_copy", body["flags"])
                self.assertIn("market_fit", body["flags"])
                self.assertTrue(body["flags"]["llm_rerank"])
                self.assertTrue(body["flags"]["role_coach"])
                self.assertTrue(body["flags"]["engagement_copy"])
                self.assertTrue(body["flags"]["market_fit"])

                saved = self.client.put(
                    "/api/v1/admin/ai-flags",
                    headers=headers,
                    json={
                        "flags": {
                            "rerank": False,
                            "digest_intro": False,
                            "llm_rerank": False,
                            "role_coach": False,
                            "engagement_copy": False,
                        }
                    },
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertFalse(saved.json()["flags"]["rerank"])
                self.assertFalse(saved.json()["flags"]["digest_intro"])
                self.assertFalse(saved.json()["flags"]["llm_rerank"])
                self.assertFalse(saved.json()["flags"]["role_coach"])
                self.assertFalse(saved.json()["flags"]["engagement_copy"])
                self.assertTrue(saved.json()["flags"]["gateway"])

                again = self.client.get("/api/v1/admin/ai-flags", headers=headers)
                self.assertFalse(again.json()["flags"]["rerank"])
                self.assertFalse(again.json()["flags"]["llm_rerank"])
                self.assertFalse(again.json()["flags"]["role_coach"])

                bad = self.client.put(
                    "/api/v1/admin/ai-flags",
                    headers=headers,
                    json={"flags": {"nope": True}},
                )
                self.assertEqual(bad.status_code, 422)


if __name__ == "__main__":
    unittest.main()
