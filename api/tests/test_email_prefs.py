"""Email prefs, unsubscribe, and digest idempotency (plan §8)."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class EmailPrefsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.accounts = root / "accounts.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        self.accounts_patch = patch("app.profiles.DATA_PATH", self.accounts)
        self.accounts_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}
        self.token_env = patch.dict(
            "os.environ",
            {
                "INTERNAL_JOB_TOKEN": "test-internal-token",
                "EMAIL_UNSUBSCRIBE_SECRET": "test-unsub-secret",
                "APP_URL": "http://localhost:3010",
            },
            clear=False,
        )
        self.token_env.start()

    def tearDown(self):
        self.token_env.stop()
        self.accounts_patch.stop()
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _grant_emails(self, subject: str):
        with self._auth("job:candidate", subject):
            res = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"emails": True, "matching": True},
            )
        self.assertEqual(res.status_code, 200, res.text)

    def test_default_prefs_and_put(self):
        subject = "mail-user-1"
        self._grant_emails(subject)
        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/email-prefs", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["emails_consent"])
        self.assertEqual(body["frequency"], "weekly")
        self.assertTrue(body["unsubscribe_url"])

        with self._auth("job:candidate", subject):
            saved = self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={
                    "frequency": "weekly",
                    "digest": True,
                    "high_match": True,
                    "language": "en",
                    "send_weekday": 1,
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        prefs = saved.json()
        self.assertEqual(prefs["frequency"], "weekly")
        self.assertEqual(prefs["language"], "en")
        self.assertEqual(prefs["send_weekday"], 1)
        self.assertEqual(prefs["unsubscribed_at"], "")

    def test_unsubscribe_token_flow(self):
        subject = "mail-user-2"
        self._grant_emails(subject)
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "language": "az"},
            )
            prefs = self.client.get("/api/v1/email-prefs", headers=self.headers).json()
        from app.email_prefs import unsubscribe_token

        token = unsubscribe_token(subject)
        status = self.client.get(f"/api/v1/unsubscribe/{token}")
        self.assertEqual(status.status_code, 200, status.text)
        self.assertTrue(status.json()["valid"])
        self.assertFalse(status.json()["unsubscribed"])

        applied = self.client.post(f"/api/v1/unsubscribe/{token}")
        self.assertEqual(applied.status_code, 200, applied.text)
        self.assertTrue(applied.json()["unsubscribed"])

        with self._auth("job:candidate", subject):
            again = self.client.get("/api/v1/email-prefs", headers=self.headers).json()
        self.assertEqual(again["frequency"], "none")
        self.assertFalse(again["emails_consent"])

        bad = self.client.get("/api/v1/unsubscribe/not-a-token")
        self.assertEqual(bad.status_code, 404)

    def test_digest_idempotent_and_empty_skip(self):
        subject = "mail-user-3"
        self._grant_emails(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "cand@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        # Monday 2026-10-05
        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with patch("app.digests.send_marketing_email") as send_mock:
            conn = _connect()
            try:
                first = send_digest_for_user(conn, user_id=subject, when=monday)
                self.assertEqual(first.get("reason"), "empty")
                self.assertEqual(first.get("status"), "skipped")
                send_mock.assert_not_called()
            finally:
                conn.close()

    def test_internal_email_jobs_requires_token(self):
        denied = self.client.post("/api/v1/internal/email-jobs")
        self.assertEqual(denied.status_code, 401)
        ok = self.client.post(
            "/api/v1/internal/email-jobs?dry_run=true",
            headers={"X-Internal-Token": "test-internal-token"},
        )
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertTrue(body["dry_run"])
        self.assertIn("users", body)

    def test_digest_sends_once_per_period(self):
        subject = "mail-user-4"
        self._grant_emails(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "cand4@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        fake_matches = [
            {
                "job_id": 42,
                "title": "Python Dev",
                "company": "Acme",
                "score": 0.82,
                "explanation": "2/3 skills",
                "created_at": "2026-10-04T12:00:00+00:00",
            }
        ]

        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with (
            patch("app.digests.send_marketing_email") as send_mock,
            patch("app.digests._matches_since", return_value=fake_matches),
            patch("app.digests._trend_lines", return_value=["Python · 20%"]),
            patch("app.digests._gap_tip", return_value="Docker"),
        ):
            conn = _connect()
            try:
                first = send_digest_for_user(conn, user_id=subject, when=monday)
                conn.commit()
                self.assertEqual(first.get("status"), "sent", first)
                self.assertEqual(send_mock.call_count, 1)
                second = send_digest_for_user(conn, user_id=subject, when=monday)
                self.assertEqual(second.get("reason"), "already_sent")
                self.assertEqual(send_mock.call_count, 1)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
