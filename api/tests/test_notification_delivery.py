"""Notification delivery fixes: send result, retries, catch-up, weekly email
retry, fresh-ad detection, per-ad dedupe, skip log and the staff log view."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import _connect, ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.main import app

from tests.test_engagement import SAMPLE_PROFILE


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


def ok_send(**_kwargs):
    from app.digests import SendResult

    return SendResult(True)


def fail_send(**_kwargs):
    from app.digests import SendResult

    return SendResult(False, "smtp_error:SMTPServerDisconnected")


MON = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)  # ISO week 41, Monday


class NotificationDeliveryTests(unittest.TestCase):
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
                "INTERNAL_JOB_TOKEN": "test-internal-token",
                "EMAIL_UNSUBSCRIBE_SECRET": "test-unsub-secret",
                "APP_URL": "http://localhost:3010",
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

    # -- helpers ---------------------------------------------------------
    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _grant(self, subject: str, *, email: str | None = None):
        with self._auth("job:candidate", subject):
            res = self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"emails": True, "matching": True},
            )
        self.assertEqual(res.status_code, 200, res.text)
        if email:
            from app.profiles import remember_contact_email

            remember_contact_email(subject, email)

    def _seed_profile(self, subject: str, *, status: str = "confirmed"):
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'anonymous', ?)
                """,
                (
                    subject,
                    "cvs/x.pdf",
                    json.dumps(SAMPLE_PROFILE, ensure_ascii=False),
                    "Backend Developer",
                    "middle",
                    5.0,
                    status,
                    "rules",
                    0.8,
                    "2026-10-08T12:00:00+00:00",
                ),
            )

    def _email_rows(self, conn, subject: str, kind: str):
        return conn.execute(
            "SELECT period_key, status, attempts, reason FROM email_log "
            "WHERE user_id = ? AND kind = ? ORDER BY id",
            (subject, kind),
        ).fetchall()

    def _digest_patches(self, send):
        fake = [
            {
                "job_id": 42,
                "title": "Python Dev",
                "company": "Acme",
                "score": 0.82,
                "explanation": "2/3 skills",
                "created_at": "2026-10-04T12:00:00+00:00",
            }
        ]
        return (
            patch("app.digests.send_marketing_email", side_effect=send),
            patch("app.digests._matches_since", return_value=fake),
            patch("app.digests._trend_lines", return_value=[]),
            patch("app.digests._gap_tip", return_value=""),
        )

    # -- fix 1: send result / failed rows / retry ------------------------
    def test_send_marketing_email_without_host_is_a_failure(self):
        from app.digests import send_marketing_email

        with patch.dict("os.environ", {"EMAIL_HOST": ""}, clear=False):
            with self.assertLogs("ingress-job.digests", level="ERROR"):
                import app.digests as digests

                digests._UNCONFIGURED_LOGGED_AT = 0.0
                result = send_marketing_email(
                    to="a@example.com", subject="s", body="b", unsubscribe_link=""
                )
        self.assertFalse(result)
        self.assertEqual(result.reason, "smtp_unconfigured")

    def test_failed_digest_is_logged_failed_and_retried_next_run(self):
        subject = "deliv-1"
        self._grant(subject, email="d1@example.com")
        from app.digests import send_digest_for_user

        conn = _connect()
        try:
            p1, p2, p3, p4 = self._digest_patches(fail_send)
            with p1 as send_mock, p2, p3, p4:
                first = send_digest_for_user(conn, user_id=subject, when=MON)
            self.assertEqual(first["status"], "skipped")
            self.assertTrue(first["reason"].startswith("send_failed"), first)
            self.assertEqual(send_mock.call_count, 1)
            rows = self._email_rows(conn, subject, "digest")
            self.assertEqual([(r[1], r[2]) for r in rows], [("failed", 1)])
            self.assertIn("SMTPServerDisconnected", rows[0][3])

            p1, p2, p3, p4 = self._digest_patches(ok_send)
            with p1 as send_mock, p2, p3, p4:
                second = send_digest_for_user(conn, user_id=subject, when=MON + timedelta(hours=1))
                third = send_digest_for_user(conn, user_id=subject, when=MON + timedelta(hours=2))
            self.assertEqual(second["status"], "sent", second)
            self.assertEqual(third["reason"], "already_sent")
            self.assertEqual(send_mock.call_count, 1)
            rows = self._email_rows(conn, subject, "digest")
            self.assertEqual([(r[1], r[2]) for r in rows], [("sent", 2)])
        finally:
            conn.close()

    def test_failed_send_stops_after_max_attempts(self):
        subject = "deliv-2"
        self._grant(subject, email="d2@example.com")
        from app.digests import send_digest_for_user
        from app.email_prefs import EMAIL_SEND_MAX_ATTEMPTS

        conn = _connect()
        try:
            p1, p2, p3, p4 = self._digest_patches(fail_send)
            with p1 as send_mock, p2, p3, p4:
                for i in range(EMAIL_SEND_MAX_ATTEMPTS + 2):
                    send_digest_for_user(conn, user_id=subject, when=MON + timedelta(hours=i))
            self.assertEqual(send_mock.call_count, EMAIL_SEND_MAX_ATTEMPTS)
            rows = self._email_rows(conn, subject, "digest")
            self.assertEqual(rows[0][1], "failed")
            self.assertEqual(rows[0][2], EMAIL_SEND_MAX_ATTEMPTS)
        finally:
            conn.close()

    def test_run_email_jobs_records_skip_reasons(self):
        subject = "deliv-skip"
        self._grant(subject)  # consent but no contact email -> no_email
        from app.digests import run_email_jobs

        run_email_jobs()
        run_email_jobs()
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT kind, reason, hits FROM notification_skip_log WHERE user_id = ?",
                (subject,),
            ).fetchall()
        finally:
            conn.close()
        self.assertEqual([(r[0], r[1], r[2]) for r in rows], [("digest", "no_email", 2)])

    # -- fix 3: digest catch-up ------------------------------------------
    def test_digest_due_catch_up_within_period(self):
        from app.digests import _due_for_digest

        base = {"digest": True, "emails_consent": True, "unsubscribed_at": ""}
        weekly_mon = {**base, "frequency": "weekly", "send_weekday": 0}
        weekly_thu = {**base, "frequency": "weekly", "send_weekday": 3}
        wed = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
        sun = datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc)
        self.assertTrue(_due_for_digest(weekly_mon, when=MON))
        self.assertTrue(_due_for_digest(weekly_mon, when=wed))
        self.assertTrue(_due_for_digest(weekly_mon, when=sun))
        self.assertFalse(_due_for_digest(weekly_thu, when=wed))
        self.assertTrue(_due_for_digest(weekly_thu, when=sun))
        # Biweekly: week 41 is the first of the pair (41-42).
        bi_wed = {**base, "frequency": "biweekly", "send_weekday": 2}
        self.assertFalse(_due_for_digest(bi_wed, when=MON))
        self.assertTrue(_due_for_digest(bi_wed, when=wed))
        self.assertTrue(_due_for_digest(bi_wed, when=MON + timedelta(days=7)))  # week 42
        self.assertFalse(_due_for_digest(bi_wed, when=MON + timedelta(days=14)))  # week 43 Mon
        self.assertTrue(_due_for_digest({**base, "frequency": "daily", "send_weekday": 6}, when=MON))

    def test_missed_monday_digest_goes_out_later_that_week_once(self):
        subject = "deliv-catchup"
        self._grant(subject, email="c@example.com")
        from app.digests import send_digest_for_user

        wed = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
        conn = _connect()
        try:
            p1, p2, p3, p4 = self._digest_patches(ok_send)
            with p1 as send_mock, p2, p3, p4:
                first = send_digest_for_user(conn, user_id=subject, when=wed)
                again = send_digest_for_user(conn, user_id=subject, when=wed + timedelta(days=1))
                next_week = send_digest_for_user(conn, user_id=subject, when=MON + timedelta(days=7))
            self.assertEqual(first["status"], "sent", first)
            self.assertEqual(again["reason"], "already_sent")
            self.assertEqual(next_week["status"], "sent")
            self.assertEqual(send_mock.call_count, 2)
            periods = [r[0] for r in self._email_rows(conn, subject, "digest")]
            self.assertEqual(periods, ["2026-W41", "2026-W42"])
        finally:
            conn.close()

    # -- fix 2: weekly reminder email retried after the digest day -------
    def test_weekly_nudge_email_retried_when_digest_used_the_slot(self):
        subject = "deliv-nudge"
        self._seed_profile(subject, status="draft")
        self._grant(subject, email="n@example.com")
        from app.engagement import logged_channels, process_user_engagement

        tue = MON + timedelta(days=1)
        conn = _connect()
        try:
            with (
                patch("app.email_prefs.marketing_sent_today", return_value=True),
                patch("app.digests._top_matches", return_value=[]),
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                mon = process_user_engagement(conn, user_id=subject, when=MON)
            self.assertEqual(mon["profile_nudge"], "sent", mon)
            send_mock.assert_not_called()
            self.assertEqual(
                logged_channels(conn, user_id=subject, kind="profile_nudge", period_key="2026-W41"),
                ["in_app"],
            )
            with (
                patch("app.email_prefs.marketing_sent_today", return_value=False),
                patch("app.digests._top_matches", return_value=[]),
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                retry = process_user_engagement(conn, user_id=subject, when=tue)
                done = process_user_engagement(conn, user_id=subject, when=tue + timedelta(hours=1))
            self.assertEqual(retry["profile_nudge"], "sent", retry)
            self.assertEqual(retry["reasons"]["profile_nudge"], "email_retry")
            self.assertEqual(done["reasons"]["profile_nudge"], "already_logged")
            self.assertEqual(send_mock.call_count, 1)
            self.assertEqual(
                logged_channels(conn, user_id=subject, kind="profile_nudge", period_key="2026-W41"),
                ["in_app", "email"],
            )
            notes = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE recipient_subject = ? AND kind = 'profile_nudge'",
                (subject,),
            ).fetchone()[0]
            self.assertEqual(notes, 1)
            skip = conn.execute(
                "SELECT reason FROM notification_skip_log WHERE user_id = ? AND kind = 'profile_nudge_email'",
                (subject,),
            ).fetchone()
            self.assertEqual(skip[0], "daily_limit")
        finally:
            conn.close()

    # -- fix 4: fresh ads beyond the top 20 ------------------------------
    def test_fresh_ad_ranked_below_top_20_triggers_alert(self):
        subject = "deliv-fresh"
        self._seed_profile(subject)
        self._grant(subject, email="f@example.com")
        when = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        stale = [
            {
                "job_id": 100 + i,
                "title": f"Old {i}",
                "company": "Old",
                "score": 0.9 - i * 0.001,
                "have": ["Python"],
                "missing": [],
                "created_at": "2026-08-01T10:00:00+00:00",
            }
            for i in range(20)
        ]
        fresh = {
            "job_id": 999,
            "title": "New Backend",
            "company": "Fresh",
            "score": 0.78,
            "have": ["Python"],
            "missing": [],
            "explanation": "new",
            "created_at": "2026-10-08T09:00:00+00:00",
        }
        payload = {"matching_consent": True, "matches": stale, "fresh_matches": [fresh]}
        from app.digests import _top_matches
        from app.engagement import process_user_engagement

        conn = _connect()
        try:
            with patch("app.matching.matches_payload", return_value=payload) as mp:
                items = _top_matches(
                    conn, user_id=subject, limit=20, lang="az", fresh_since=when - timedelta(hours=72)
                )
                self.assertEqual(mp.call_args.kwargs.get("fresh_since"), "2026-10-05")
            self.assertEqual(len(items), 21)
            self.assertEqual(items[-1]["job_id"], 999)
            with (
                patch("app.matching.matches_payload", return_value=payload),
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                result = process_user_engagement(conn, user_id=subject, when=when)
            self.assertEqual(result["match_new"], "sent", result)
            self.assertEqual(result["reasons"]["match_new"], "fresh")
            self.assertEqual(send_mock.call_count, 1)
            self.assertIn("New Backend", send_mock.call_args.kwargs["subject"])
        finally:
            conn.close()

    def test_matches_payload_fresh_since_scans_whole_gated_list(self):
        from app import matching

        self.assertIn("fresh_since", matching.matches_payload.__code__.co_varnames)
        self.assertGreaterEqual(matching.FRESH_MATCHES_CAP, 100)

    # -- fix 5: per-user per-ad dedupe ------------------------------------
    def _one_fresh(self):
        return [
            {
                "job_id": 10,
                "title": "Senior Backend",
                "company": "Acme",
                "score": 0.88,
                "have": ["Python", "Docker"],
                "missing": [],
                "explanation": "strong",
                "created_at": "2026-10-08T10:00:00+00:00",
            }
        ]

    def test_same_fresh_ad_is_not_emailed_on_later_days(self):
        subject = "deliv-dedupe"
        self._seed_profile(subject)
        self._grant(subject, email="dd@example.com")
        from app.engagement import process_user_engagement

        day1 = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        conn = _connect()
        try:
            with (
                patch("app.digests._top_matches", return_value=self._one_fresh()),
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                first = process_user_engagement(conn, user_id=subject, when=day1)
                second = process_user_engagement(conn, user_id=subject, when=day1 + timedelta(days=1))
                third = process_user_engagement(conn, user_id=subject, when=day1 + timedelta(days=2))
            self.assertEqual(first["match_new"], "sent")
            self.assertEqual(second["match_new"], "skipped")
            self.assertEqual(third["match_new"], "skipped")
            self.assertEqual(send_mock.call_count, 1)
            notes = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE recipient_subject = ? AND kind = 'match_new'",
                (subject,),
            ).fetchone()[0]
            self.assertEqual(notes, 1)
        finally:
            conn.close()

    def test_ad_shown_in_app_while_capped_gets_only_its_email_next_day(self):
        subject = "deliv-owed"
        self._seed_profile(subject)
        self._grant(subject, email="ow@example.com")
        from app.engagement import process_user_engagement

        day1 = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        conn = _connect()
        try:
            with (
                patch("app.email_prefs.marketing_sent_today", return_value=True),
                patch("app.digests._top_matches", return_value=self._one_fresh()),
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                first = process_user_engagement(conn, user_id=subject, when=day1)
            self.assertEqual(first["match_new"], "sent")
            send_mock.assert_not_called()
            with (
                patch("app.email_prefs.marketing_sent_today", return_value=False),
                patch("app.digests._top_matches", return_value=self._one_fresh()),
                patch("app.engagement_copy.maybe_engagement_copy") as copy_mock,
                patch("app.digests.send_marketing_email", side_effect=ok_send) as send_mock,
            ):
                second = process_user_engagement(conn, user_id=subject, when=day1 + timedelta(days=1))
            self.assertEqual(second["match_new"], "sent", second)
            self.assertEqual(second["reasons"]["match_new"], "fresh_email")
            self.assertEqual(send_mock.call_count, 1)
            copy_mock.assert_not_called()
            notes = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE recipient_subject = ? AND kind = 'match_new'",
                (subject,),
            ).fetchone()[0]
            self.assertEqual(notes, 1)
        finally:
            conn.close()

    # -- fix 6: staff notification log -----------------------------------
    def test_admin_notification_log_is_staff_only_and_masks_email(self):
        subject = "deliv-admin"
        self._grant(subject, email="person@example.com")
        from app.email_prefs import claim_email, finish_email, record_skip

        conn = _connect()
        try:
            claim_email(conn, user_id=subject, kind="digest", period_key="2026-W41", to_email="person@example.com")
            finish_email(conn, user_id=subject, kind="digest", period_key="2026-W41", ok=True)
            claim_email(conn, user_id=subject, kind="digest", period_key="2026-W42", to_email="person@example.com")
            finish_email(conn, user_id=subject, kind="digest", period_key="2026-W42", ok=False, reason="smtp_error:X")
            record_skip(conn, user_id=subject, kind="high_match_email", reason="daily_limit")
            conn.commit()
        finally:
            conn.close()

        with self._auth("job:candidate", subject):
            denied = self.client.get("/api/v1/admin/notification-log", headers=self.headers)
        self.assertEqual(denied.status_code, 403)

        with self._auth("job:staff", "staff-1"):
            res = self.client.get(
                "/api/v1/admin/notification-log?user=person@example.com&days=30",
                headers=self.headers,
            )
            missing = self.client.get(
                "/api/v1/admin/notification-log?user=nobody@example.com",
                headers=self.headers,
            )
            overall = self.client.get("/api/v1/admin/notification-log", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["user"]["user_id"], subject)
        self.assertEqual(body["user"]["email"], "p***@example.com")
        self.assertEqual(body["user"]["prefs"]["frequency"], "weekly")
        self.assertEqual(body["totals"]["sent"], 1)
        self.assertEqual(body["totals"]["failed"], 1)
        self.assertNotIn("person@example.com", res.text)
        failed = [row for row in body["emails"] if row["status"] == "failed"]
        self.assertEqual(failed[0]["reason"], "smtp_error:X")
        self.assertEqual(body["skips"][0]["reason"], "daily_limit")
        self.assertTrue(missing.json().get("not_found"))
        self.assertEqual(overall.status_code, 200)
        self.assertIsNone(overall.json()["user"])
        self.assertEqual(len(overall.json()["emails"]), 2)

    def test_postgres_adapter_knows_skip_log_has_no_id(self):
        from app.jobs_db import _wants_returning

        self.assertFalse(
            _wants_returning("INSERT INTO notification_skip_log (user_id) VALUES (?)")
        )
        self.assertTrue(_wants_returning("INSERT INTO email_log (user_id) VALUES (?)"))

    def test_old_email_log_table_gets_new_columns(self):
        with sqlite3.connect(self.db) as raw:
            raw.execute("DROP TABLE IF EXISTS email_log")
            raw.execute(
                """
                CREATE TABLE email_log (
                    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
                    period_key TEXT NOT NULL, to_email TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'sent', meta TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL, UNIQUE (user_id, kind, period_key)
                )
                """
            )
            raw.execute(
                "INSERT INTO email_log (user_id, kind, period_key, created_at) "
                "VALUES ('legacy', 'digest', '2026-W40', '2026-09-28T00:00:00+00:00')"
            )
        from app.email_prefs import already_logged, ensure_email_tables

        conn = _connect()
        try:
            ensure_email_tables(conn)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(email_log)")}
            self.assertTrue({"attempts", "reason"} <= cols)
            self.assertTrue(
                already_logged(conn, user_id="legacy", kind="digest", period_key="2026-W40")
            )
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
