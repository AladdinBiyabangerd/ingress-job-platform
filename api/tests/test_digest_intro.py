"""AI #4 digest intro: soft-fail to static copy when AI unavailable."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.ai_gateway import GatewayResult
from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.main import app


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


SAMPLE_PROFILE = {
    "contact": {"full_name": "Aysel", "email": "aysel@example.com", "phone": "", "city": "", "country": ""},
    "headline": "Backend Developer",
    "seniority": "middle",
    "total_years": 5.0,
    "work_history": [],
    "skills": [
        {"name": "Python", "years": 4, "level": "advanced", "source": "cv"},
        {"name": "Docker", "years": 2, "level": "", "source": "cv"},
    ],
    "languages": [{"code": "en", "name": "English"}],
    "education": [],
    "desired_roles": [],
    "preferences": {"remote": True, "relocation": False, "relocation_countries": [], "needs_visa_sponsorship": None},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class DigestIntroTests(unittest.TestCase):
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
        self.env = patch.dict(
            "os.environ",
            {
                "INTERNAL_JOB_TOKEN": "test-internal-token",
                "EMAIL_UNSUBSCRIBE_SECRET": "test-unsub-secret",
                "APP_URL": "http://localhost:3010",
                "DIGEST_AI_INTRO_ENABLED": "1",
                "OPENAI_API_KEY": "sk-test",
                "AI_GATEWAY_ENABLED": "1",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
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

    def _seed_profile(self, subject: str):
        import sqlite3

        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'confirmed', 'rules', 0.8, 'anonymous', ?)
                """,
                (
                    subject,
                    "cvs/intro.pdf",
                    json.dumps(SAMPLE_PROFILE, ensure_ascii=False),
                    SAMPLE_PROFILE["headline"],
                    SAMPLE_PROFILE["seniority"],
                    SAMPLE_PROFILE["total_years"],
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.commit()

    def test_ai_intro_applied_in_body(self):
        subject = "intro-user-1"
        self._grant_emails(subject)
        self._seed_profile(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "intro1@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        fake_matches = [
            {
                "job_id": 7,
                "title": "Python Engineer",
                "company": "Acme",
                "score": 0.88,
                "explanation": "2/2 skills",
                "created_at": "2026-10-04T12:00:00+00:00",
            }
        ]
        ai_text = (
            "This week we found roles that lean on your Python and Docker background. "
            "Python Engineer at Acme looks especially close to your middle-level path."
        )
        fake_result = GatewayResult(ok=True, data={"intro": ai_text})

        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with (
            patch("app.digests.send_marketing_email") as send_mock,
            patch("app.digests._matches_since", return_value=fake_matches),
            patch("app.digests._trend_lines", return_value=["Python · 22%"]),
            patch("app.digests._gap_tip", return_value="Kubernetes"),
            patch("app.digest_intro.complete_json", return_value=fake_result) as ai_mock,
        ):
            conn = _connect()
            try:
                result = send_digest_for_user(conn, user_id=subject, when=monday)
                conn.commit()
            finally:
                conn.close()

        self.assertEqual(result.get("status"), "sent", result)
        self.assertEqual(result.get("ai_intro"), "applied")
        ai_mock.assert_called_once()
        send_mock.assert_called_once()
        body = send_mock.call_args.kwargs["body"]
        self.assertIn(ai_text, body)
        self.assertIn("Python Engineer", body)
        self.assertNotIn("New jobs that fit your profile:", body)

        # email_log meta
        from app.cabinet_store import _connect

        conn = _connect()
        try:
            row = conn.execute(
                "SELECT meta FROM email_log WHERE user_id = ? AND kind = 'digest'",
                (subject,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        meta = json.loads(row[0] if not hasattr(row, "keys") else row["meta"])
        self.assertEqual(meta.get("ai_intro"), "applied")

    def test_disabled_keeps_static_intro(self):
        subject = "intro-user-2"
        self._grant_emails(subject)
        self._seed_profile(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "intro2@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        fake_matches = [
            {
                "job_id": 8,
                "title": "Backend Dev",
                "company": "Beta",
                "score": 0.7,
                "explanation": "skills",
                "created_at": "2026-10-04T12:00:00+00:00",
            }
        ]

        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with (
            patch.dict(os.environ, {"DIGEST_AI_INTRO_ENABLED": "0"}, clear=False),
            patch("app.digests.send_marketing_email") as send_mock,
            patch("app.digests._matches_since", return_value=fake_matches),
            patch("app.digests._trend_lines", return_value=[]),
            patch("app.digests._gap_tip", return_value=""),
            patch("app.digest_intro.complete_json") as ai_mock,
        ):
            conn = _connect()
            try:
                result = send_digest_for_user(conn, user_id=subject, when=monday)
                conn.commit()
            finally:
                conn.close()

        self.assertEqual(result.get("status"), "sent", result)
        self.assertEqual(result.get("ai_intro"), "skipped:disabled")
        ai_mock.assert_not_called()
        body = send_mock.call_args.kwargs["body"]
        self.assertIn("New jobs that fit your profile:", body)

    def test_budget_exceeded_keeps_static_intro(self):
        subject = "intro-user-3"
        self._grant_emails(subject)
        self._seed_profile(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "intro3@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        fake_matches = [
            {
                "job_id": 9,
                "title": "Platform Eng",
                "company": "Gamma",
                "score": 0.75,
                "explanation": "ok",
                "created_at": "2026-10-04T12:00:00+00:00",
            }
        ]
        fake_result = GatewayResult(ok=False, error="ai_budget_exceeded")

        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with (
            patch("app.digests.send_marketing_email") as send_mock,
            patch("app.digests._matches_since", return_value=fake_matches),
            patch("app.digests._trend_lines", return_value=[]),
            patch("app.digests._gap_tip", return_value=""),
            patch("app.digest_intro.complete_json", return_value=fake_result),
        ):
            conn = _connect()
            try:
                result = send_digest_for_user(conn, user_id=subject, when=monday)
                conn.commit()
            finally:
                conn.close()

        self.assertEqual(result.get("status"), "sent", result)
        self.assertEqual(result.get("ai_intro"), "skipped:ai_budget_exceeded")
        body = send_mock.call_args.kwargs["body"]
        self.assertIn("New jobs that fit your profile:", body)

    def test_empty_digest_still_skips_without_ai(self):
        subject = "intro-user-4"
        self._grant_emails(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "intro4@example.com")
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={"frequency": "weekly", "digest": True, "send_weekday": 0, "language": "en"},
            )

        monday = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
        from app.cabinet_store import _connect
        from app.digests import send_digest_for_user

        with (
            patch("app.digests.send_marketing_email") as send_mock,
            patch("app.digest_intro.complete_json") as ai_mock,
        ):
            conn = _connect()
            try:
                result = send_digest_for_user(conn, user_id=subject, when=monday)
            finally:
                conn.close()

        self.assertEqual(result.get("reason"), "empty")
        send_mock.assert_not_called()
        ai_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
