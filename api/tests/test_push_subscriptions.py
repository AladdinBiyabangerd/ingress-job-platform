"""Web Push subscribe API + 410 cleanup (engagement Phase 5)."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import _connect, ensure_schema
from app.engagement import ensure_engagement_tables, fanout_match_event
from app.main import app
from app.push import delete_endpoint, list_subscriptions, send_web_push, upsert_subscription


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class PushSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.accounts = root / "accounts.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.accounts_patch = patch("app.profiles.DATA_PATH", self.accounts)
        self.path_patch.start()
        self.accounts_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}
        self.env = patch.dict(
            "os.environ",
            {
                "VAPID_PUBLIC_KEY": "BPublicTestKeyForUnitTestsOnlyXXXXXXXXXXXX",
                "VAPID_PRIVATE_KEY": "PrivateTestKeyForUnitTestsOnly",
                "VAPID_SUBJECT": "mailto:ops@example.com",
            },
            clear=False,
        )
        self.env.start()
        self.auth = patch(
            "app.account.verify_access_token",
            return_value=user("openid job:candidate", "push-user-1"),
        )
        self.auth.start()

    def tearDown(self):
        self.auth.stop()
        self.env.stop()
        self.accounts_patch.stop()
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def test_vapid_key_endpoint(self):
        res = self.client.get("/api/v1/me/push-vapid-key", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("publicKey", res.json())
        self.assertTrue(res.json()["publicKey"])

    def test_vapid_key_reports_missing_env(self):
        with patch.dict(
            "os.environ",
            {"VAPID_PUBLIC_KEY": "", "VAPID_PRIVATE_KEY": "", "VAPID_SUBJECT": ""},
            clear=False,
        ):
            res = self.client.get("/api/v1/me/push-vapid-key", headers=self.headers)
        self.assertEqual(res.status_code, 503, res.text)
        detail = res.json().get("detail") or {}
        self.assertEqual(detail.get("error"), "web_push_not_configured")
        self.assertIn("VAPID_PUBLIC_KEY", detail.get("missing") or [])

    def test_subscribe_and_delete(self):
        body = {
            "endpoint": "https://push.example/endpoint/abc",
            "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
        }
        res = self.client.post(
            "/api/v1/me/push-subscription",
            headers=self.headers,
            json=body,
        )
        self.assertEqual(res.status_code, 201, res.text)
        self.assertEqual(res.json()["endpoint"], body["endpoint"])

        conn = _connect()
        try:
            rows = list_subscriptions(conn, user_id="push-user-1")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["p256dh"], "p256dh-key")
        finally:
            conn.close()

        res = self.client.request(
            "DELETE",
            "/api/v1/me/push-subscription",
            headers=self.headers,
            json={"endpoint": body["endpoint"]},
        )
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["deleted"])

        conn = _connect()
        try:
            self.assertEqual(list_subscriptions(conn, user_id="push-user-1"), [])
        finally:
            conn.close()

    def test_subscribe_rejects_missing_keys(self):
        res = self.client.post(
            "/api/v1/me/push-subscription",
            headers=self.headers,
            json={"endpoint": "https://push.example/x", "keys": {}},
        )
        self.assertEqual(res.status_code, 400)

    def test_410_cleanup(self):
        from pywebpush import WebPushException

        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            upsert_subscription(
                conn,
                user_id="push-user-1",
                endpoint="https://push.example/gone2",
                p256dh="k",
                auth="a",
            )
            conn.commit()

            exc = WebPushException("gone", response=MagicMock(status_code=410))

            with patch("pywebpush.webpush", side_effect=exc):
                result = send_web_push(
                    conn,
                    user_id="push-user-1",
                    title="Hi",
                    body="Body",
                )
                conn.commit()

            self.assertEqual(result["cleaned"], 1)
            self.assertEqual(result["sent"], 0)
            self.assertEqual(list_subscriptions(conn, user_id="push-user-1"), [])
        finally:
            conn.close()

    def test_fanout_includes_push_channel(self):
        from app.email_prefs import ensure_email_tables, get_prefs, save_prefs

        subject = "push-user-1"
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        match = {
            "job_id": 42,
            "title": "Backend",
            "company": "Acme",
            "score": 0.9,
            "have": ["Python"],
            "missing": [],
            "explanation": "strong",
        }
        conn = _connect()
        try:
            ensure_email_tables(conn)
            ensure_engagement_tables(conn)
            save_prefs(conn, subject, push_enabled=True)
            upsert_subscription(
                conn,
                user_id=subject,
                endpoint="https://push.example/fanout",
                p256dh="k",
                auth="a",
            )
            prefs = get_prefs(conn, subject)
            self.assertTrue(prefs["push_enabled"])

            with (
                patch(
                    "app.push.send_web_push",
                    return_value={"sent": 1, "failed": 0, "cleaned": 0},
                ),
                patch("app.digests.send_marketing_email"),
            ):
                result = fanout_match_event(
                    conn,
                    user_id=subject,
                    kind="match_new",
                    match=match,
                    prefs=prefs,
                    when=when,
                    allow_email=False,
                )
                conn.commit()

            self.assertEqual(result["status"], "sent", result)
            self.assertIn("push", result["channels"])
            self.assertIn("in_app", result["channels"])
        finally:
            conn.close()

    def test_delete_endpoint_helper(self):
        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            upsert_subscription(
                conn,
                user_id="push-user-1",
                endpoint="https://push.example/x",
                p256dh="k",
                auth="a",
            )
            delete_endpoint(conn, endpoint="https://push.example/x")
            conn.commit()
            self.assertEqual(list_subscriptions(conn, user_id="push-user-1"), [])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
