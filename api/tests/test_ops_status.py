"""Ops status: AI health + crawl funnel for staff / internal callers."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class OpsStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.env = patch.dict(
            os.environ,
            {
                "INTERNAL_JOB_TOKEN": "test-internal-token",
                "GEMINI_API_KEY": "gemini-test",
                "AI_GATEWAY_ENABLED": "1",
                "AI_CHAT_PROVIDERS": "gemini,openai",
                "AI_EMBED_PROVIDERS": "openai",
                "OPENAI_API_KEY": "",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_crawl(self):
        from app.cabinet_store import _LOCK, _connect
        from app.ops_status import _CRAWL_RUNS_DDL

        with _LOCK:
            conn = _connect()
            try:
                conn.executescript(_CRAWL_RUNS_DDL)
                conn.execute(
                    """
                    INSERT INTO crawl_sources
                    (id, name, homepage, connector, entry_url, enabled, go_decision, api_key_env)
                    VALUES (1, 'Remote OK', 'https://remoteok.com', 'remoteok', 'https://remoteok.com', 1, 'go', '')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO crawl_runs
                    (source_id, started_at, finished_at, status, found_count, created_count, updated_count, error)
                    VALUES (1, '2099-01-01T00:00:00+00:00', '2099-01-01T01:00:00+00:00', 'ok', 10, 3, 2, '')
                    """
                )
                conn.execute(
                    """
                    INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject, hidden)
                    VALUES ('Dev', 'Co', '', 'text', 'published', '2099-01-01T00:00:00+00:00', 'k1', '', 0)
                    """
                )
                job_id = conn.execute("SELECT id FROM jobs WHERE norm_key = 'k1'").fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO job_sources (job_id, source_name, source_url, last_seen)
                    VALUES (?, 'Remote OK', 'https://remoteok.com/1', '2099-01-01T00:00:00+00:00')
                    """,
                    (job_id,),
                )
                conn.commit()
            finally:
                conn.close()

    def test_staff_ops_status_derives_providers_and_funnel(self):
        self._seed_crawl()
        with self._auth("job:staff", "ops-staff"):
            res = self.client.get(
                "/api/v1/admin/ops-status?days=7",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertIn("ai", body)
        self.assertIn("crawl", body)

        chat = {p["id"]: p for p in body["ai"]["chat_providers"]}
        self.assertEqual(chat["gemini"]["status"], "running")
        self.assertEqual(chat["openai"]["status"], "stopped")
        self.assertIn("açar", chat["openai"]["reason"].lower())

        features = {f["id"]: f for f in body["ai"]["features"]}
        self.assertEqual(features["gateway"]["status"], "running")
        self.assertTrue(features["gateway"]["label"])

        sources = {s["name"]: s for s in body["crawl"]["sources"]}
        self.assertIn("Remote OK", sources)
        self.assertEqual(sources["Remote OK"]["fetched"], 10)
        self.assertEqual(sources["Remote OK"]["selected"], 5)
        self.assertEqual(sources["Remote OK"]["published_live"], 1)
        # KPI matches public board total (unique open ads), not sum of sources.
        self.assertEqual(body["crawl"]["totals"]["published_live"], 1)

    def test_published_live_total_matches_board_not_source_sum(self):
        """Board COUNT(*) rules; multi-source + employer ads must not skew the KPI."""
        from app.cabinet_store import _LOCK, _connect
        from app.ops_status import _CRAWL_RUNS_DDL

        with _LOCK:
            conn = _connect()
            try:
                conn.executescript(_CRAWL_RUNS_DDL)
                conn.execute(
                    """
                    INSERT INTO crawl_sources
                    (id, name, homepage, connector, entry_url, enabled, go_decision, api_key_env)
                    VALUES
                      (1, 'Remote OK', 'https://remoteok.com', 'remoteok', 'https://remoteok.com', 1, 'go', ''),
                      (2, 'Other', 'https://other.example', 'other', 'https://other.example', 1, 'go', '')
                    """
                )
                # Scraped job linked to two sources → would double-count if totals summed rows.
                conn.execute(
                    """
                    INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject, hidden)
                    VALUES ('Dev', 'Co', '', 'text', 'published', '2099-01-01T00:00:00+00:00', 'k-multi', '', 0)
                    """
                )
                job_id = conn.execute("SELECT id FROM jobs WHERE norm_key = 'k-multi'").fetchone()[0]
                conn.execute(
                    """
                    INSERT INTO job_sources (job_id, source_name, source_url, last_seen)
                    VALUES
                      (?, 'Remote OK', 'https://remoteok.com/1', '2099-01-01T00:00:00+00:00'),
                      (?, 'Other', 'https://other.example/1', '2099-01-01T00:00:00+00:00')
                    """,
                    (job_id, job_id),
                )
                # Employer-posted ad (no crawl source) — public board includes it.
                conn.execute(
                    """
                    INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject, hidden)
                    VALUES ('Hire', 'Acme', 'Baku', 'text', 'published', '2099-01-01T00:00:00+00:00', 'k-owner', 'employer-1', 0)
                    """
                )
                conn.commit()
            finally:
                conn.close()

        with self._auth("job:staff", "ops-staff"):
            res = self.client.get(
                "/api/v1/admin/ops-status?days=7",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        sources = {s["name"]: s for s in body["crawl"]["sources"]}
        self.assertEqual(sources["Remote OK"]["published_live"], 1)
        self.assertEqual(sources["Other"]["published_live"], 1)
        # 1 multi-source scraped + 1 employer = 2 unique open ads (not 1+1 scraped only).
        self.assertEqual(body["crawl"]["totals"]["published_live"], 2)

    def test_linkedin_extension_stats_are_separate(self):
        from app.cabinet_store import _LOCK, _connect
        from app.ops_status import _CRAWL_RUNS_DDL

        with _LOCK:
            conn = _connect()
            try:
                conn.executescript(_CRAWL_RUNS_DDL)
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS crawl_rejects (
                        source_url TEXT PRIMARY KEY,
                        reason TEXT NOT NULL DEFAULT '',
                        decided_at TEXT NOT NULL,
                        via_ai INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO jobs (title, company, city, text, status, created_at, norm_key, owner_subject, hidden)
                    VALUES
                      ('LI Dev', 'Co', '', 'text', 'published', '2099-01-02T00:00:00+00:00', 'k-li', '', 0),
                      ('Old LI', 'Co', '', 'text', 'published', '2000-01-01T00:00:00+00:00', 'k-li-old', '', 0)
                    """
                )
                ids = {
                    r[0]: r[1]
                    for r in conn.execute("SELECT norm_key, id FROM jobs WHERE norm_key LIKE 'k-li%'").fetchall()
                }
                conn.execute(
                    """
                    INSERT INTO job_sources (job_id, source_name, source_url, external_id, last_seen)
                    VALUES
                      (?, 'linkedin-extension', 'https://www.linkedin.com/jobs/view/1/', '1', '2099-01-02T00:00:00+00:00'),
                      (?, 'linkedin-extension', 'https://www.linkedin.com/jobs/view/2/', '2', '2000-01-01T00:00:00+00:00')
                    """,
                    (ids["k-li"], ids["k-li-old"]),
                )
                conn.execute(
                    """
                    INSERT INTO crawl_rejects (source_url, reason, decided_at, via_ai)
                    VALUES
                      ('https://www.linkedin.com/jobs/view/9/', 'rules', '2099-01-02T00:00:00+00:00', 0),
                      ('https://remoteok.com/x', 'rules', '2099-01-02T00:00:00+00:00', 0)
                    """
                )
                conn.commit()
            finally:
                conn.close()

        with self._auth("job:staff", "ops-staff"):
            res = self.client.get(
                "/api/v1/admin/ops-status?days=7",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(res.status_code, 200, res.text)
        li = res.json()["crawl"]["linkedin_extension"]
        self.assertEqual(li["source_name"], "linkedin-extension")
        self.assertEqual(li["created"], 1)  # only the recent one in the rolling window
        self.assertEqual(li["published_live"], 2)
        self.assertEqual(li["rejected"], 1)
        source_names = {s["name"] for s in res.json()["crawl"]["sources"]}
        self.assertNotIn("linkedin-extension", source_names)

    def test_internal_ops_status_requires_token(self):
        denied = self.client.get("/api/v1/internal/ops-status")
        self.assertEqual(denied.status_code, 401)

        ok = self.client.get(
            "/api/v1/internal/ops-status?days=7",
            headers={"X-Internal-Token": "test-internal-token"},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertIn("ai", ok.json())

    def test_gateway_off_stops_features(self):
        with patch.dict(os.environ, {"AI_GATEWAY_ENABLED": "0"}, clear=False):
            with self._auth("job:staff", "ops-staff"):
                res = self.client.get(
                    "/api/v1/admin/ops-status",
                    headers={"Authorization": "Bearer test"},
                )
        self.assertEqual(res.status_code, 200, res.text)
        features = {f["id"]: f for f in res.json()["ai"]["features"]}
        self.assertEqual(features["gateway"]["status"], "stopped")
        self.assertIn("söndür", features["gateway"]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
