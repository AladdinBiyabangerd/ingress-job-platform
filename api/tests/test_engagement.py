"""Engagement schema (phase 1) + match engine (phase 2) + AI copy (phase 3) + nudge/coach (phase 4)."""

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
from app.engagement import (
    already_logged,
    build_coach_weekly_context,
    build_growth_cta,
    ensure_engagement_tables,
    fanout_coach_weekly,
    fanout_match_event,
    fanout_profile_nudge,
    inapp_count_today,
    insights_payload,
    job_ever_logged,
    log_engagement,
    needs_profile_nudge,
    process_user_engagement,
    profile_nudge_reasons,
    resolve_match_candidate,
    run_engagement_jobs,
    select_match_near,
    select_match_new,
    week_period_key,
)
from app.main import app
from app.notifications import insert_notification


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
        {"name": "SQL", "years": 3, "level": "intermediate", "source": "cv"},
    ],
    "languages": [{"code": "en", "name": "English"}],
    "education": [],
    "desired_roles": [],
    "preferences": {"remote": True, "relocation": False, "relocation_countries": [], "needs_visa_sponsorship": None},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class EngagementPhase1Tests(unittest.TestCase):
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

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def test_engagement_log_dedup(self):
        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            ok = log_engagement(
                conn,
                user_id="u1",
                kind="match_near",
                period_key="2026-10-08:42",
                job_id=42,
                channels=["in_app"],
            )
            self.assertTrue(ok)
            self.assertTrue(
                already_logged(
                    conn,
                    user_id="u1",
                    kind="match_near",
                    period_key="2026-10-08:42",
                    job_id=42,
                )
            )
            again = log_engagement(
                conn,
                user_id="u1",
                kind="match_near",
                period_key="2026-10-08:42",
                job_id=42,
                channels=["in_app", "email"],
            )
            self.assertFalse(again)
            self.assertEqual(
                inapp_count_today(conn, user_id="u1", when=datetime.now(timezone.utc)),
                1,
            )
            conn.commit()
        finally:
            conn.close()

    def test_insert_notification_payload_and_list(self):
        conn = _connect()
        try:
            note = insert_notification(
                conn,
                recipient="cand-1",
                kind="match_near",
                job_id=7,
                job_title="Data Engineer",
                application_id=None,
                status="",
                reason="",
                language="az",
                payload={
                    "score": 0.58,
                    "missing": [{"name": "Kubernetes"}],
                    "ai_body": "Kubernetes öyrən — bu elana yaxınsan.",
                    "cta_href": "/jobs/7",
                },
            )
            conn.commit()
        finally:
            conn.close()
        self.assertIsNotNone(note)
        self.assertEqual(note["kind"], "match_near")
        self.assertEqual(note["payload"]["score"], 0.58)

        with self._auth("job:candidate", "cand-1"):
            res = self.client.get("/api/v1/notifications", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["unread"], 1)
        item = body["items"][0]
        self.assertEqual(item["kind"], "match_near")
        self.assertEqual(item["payload"]["ai_body"], "Kubernetes öyrən — bu elana yaxınsan.")
        self.assertEqual(item["payload"]["cta_href"], "/jobs/7")

    def test_email_prefs_engagement_flags(self):
        subject = "eng-prefs-1"
        with self._auth("job:candidate", subject):
            self.client.put(
                "/api/v1/consents",
                headers=self.headers,
                json={"emails": True, "matching": True},
            )
            got = self.client.get("/api/v1/email-prefs", headers=self.headers)
        self.assertEqual(got.status_code, 200, got.text)
        prefs = got.json()
        self.assertTrue(prefs["match_near"])
        self.assertTrue(prefs["coach_weekly"])
        self.assertTrue(prefs["profile_nudge"])
        self.assertTrue(prefs["push_enabled"])

        with self._auth("job:candidate", subject):
            saved = self.client.put(
                "/api/v1/email-prefs",
                headers=self.headers,
                json={
                    "frequency": "weekly",
                    "match_near": False,
                    "coach_weekly": True,
                    "profile_nudge": False,
                    "push_enabled": False,
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        body = saved.json()
        self.assertFalse(body["match_near"])
        self.assertTrue(body["coach_weekly"])
        self.assertFalse(body["profile_nudge"])
        self.assertFalse(body["push_enabled"])


class EngagementPhase2Tests(unittest.TestCase):
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
        self._seed_skills()

    def tearDown(self):
        self.env.stop()
        self.accounts_patch.stop()
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_skills(self):
        with sqlite3.connect(self.db) as conn:
            for name, courses in (
                ("Python", "[]"),
                ("Docker", "[]"),
                ("Kubernetes", '["k8s-fundamentals"]'),
                ("Spark", "[]"),
                ("SQL", "[]"),
            ):
                conn.execute(
                    """
                    INSERT INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, '[]', '', ?, '2026-10-08T12:00:00+00:00')
                    """,
                    (name, courses),
                )
            conn.commit()

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
                    "cvs/aysel.pdf",
                    json.dumps(SAMPLE_PROFILE, ensure_ascii=False),
                    SAMPLE_PROFILE["headline"],
                    SAMPLE_PROFILE["seniority"],
                    SAMPLE_PROFILE["total_years"],
                    status,
                    "rules",
                    0.8,
                    "2026-10-08T12:00:00+00:00",
                ),
            )
            conn.commit()

    def _grant(self, subject: str, *, emails: bool = True, matching: bool = True):
        body = {}
        if emails:
            body["emails"] = True
        if matching:
            body["matching"] = True
        with self._auth("job:candidate", subject):
            res = self.client.put("/api/v1/consents", headers=self.headers, json=body)
        self.assertEqual(res.status_code, 200, res.text)

    def test_select_bands_and_mutual_exclusion(self):
        matches = [
            {
                "job_id": 1,
                "title": "Strong",
                "company": "A",
                "score": 0.82,
                "have": ["Python"],
                "missing": ["Kubernetes"],
                "explanation": "ok",
            },
            {
                "job_id": 2,
                "title": "Near",
                "company": "B",
                "score": 0.58,
                "have": ["Python"],
                "missing": ["Kubernetes", "Spark"],
                "explanation": "close",
            },
            {
                "job_id": 3,
                "title": "Too many missing",
                "company": "C",
                "score": 0.55,
                "have": ["Python"],
                "missing": ["a", "b", "c", "d"],
                "explanation": "nope",
            },
            {
                "job_id": 4,
                "title": "Too low",
                "company": "D",
                "score": 0.40,
                "have": ["Python"],
                "missing": ["Kubernetes"],
                "explanation": "low",
            },
        ]
        strong = select_match_new(matches)
        near = select_match_near(matches)
        self.assertIsNotNone(strong)
        self.assertEqual(strong["job_id"], 1)
        self.assertIsNotNone(near)
        self.assertEqual(near["job_id"], 2)
        # Same job cannot land in both bands by score.
        self.assertNotEqual(strong["job_id"], near["job_id"])
        self.assertIsNone(select_match_near([matches[0]]))  # ≥0.75 excluded from near
        self.assertIsNone(select_match_new([matches[1]]))  # <0.75 excluded from new

    def test_build_growth_cta_academy_vs_roadmap(self):
        subject = "cta-user"
        self._seed_profile(subject)
        self._grant(subject, emails=False, matching=True)
        conn = _connect()
        try:
            with patch("app.learning_roadmap.complete_json") as ai:
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(ok=False, error="disabled")
                academy = build_growth_cta(
                    conn,
                    user_id=subject,
                    missing_skills=["Kubernetes", "Spark"],
                    lang="en",
                    allow_ai_provider=False,
                )
            self.assertTrue(academy["academy_courses"])
            self.assertEqual(academy["academy_courses"][0]["slug"], "k8s-fundamentals")
            self.assertIn("utm_medium=notification", academy["academy_courses"][0]["url"])
            # Course + AI/template fill for uncovered Spark → hybrid rich shape.
            rich = academy.get("learning_roadmap") or {}
            self.assertTrue(rich)
            self.assertIn(rich.get("source"), {"academy", "hybrid", "ai"})
            self.assertTrue(rich.get("milestones"))
            # Legacy list still covers unmapped Spark.
            spark_rows = [r for r in (academy.get("roadmap") or []) if r.get("skill") == "Spark"]
            self.assertTrue(spark_rows)

            with patch("app.learning_roadmap.complete_json") as ai:
                from app.ai_gateway import GatewayResult

                ai.return_value = GatewayResult(ok=False, error="disabled")
                roadmap = build_growth_cta(
                    conn,
                    user_id=subject,
                    missing_skills=["Spark"],
                    lang="en",
                    allow_ai_provider=False,
                )
            # Spark has no course; career path may also be empty without taxonomy → roadmap.
            if not roadmap.get("academy_courses") and not roadmap.get("career_path"):
                self.assertTrue(roadmap["roadmap"])
                self.assertTrue(roadmap["roadmap"][0]["coming_soon"])
                self.assertEqual(roadmap["roadmap"][0]["skill"], "Spark")
                self.assertEqual((roadmap.get("learning_roadmap") or {}).get("source"), "ai")
        finally:
            conn.close()

    def test_fanout_dedup_and_inapp(self):
        subject = "fanout-1"
        self._seed_profile(subject)
        self._grant(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "fanout@example.com")
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        match = {
            "job_id": 99,
            "title": "Near Engineer",
            "company": "Acme",
            "score": 0.58,
            "have": ["Python"],
            "missing": ["Kubernetes"],
            "explanation": "close",
        }
        conn = _connect()
        try:
            from app.email_prefs import ensure_email_tables, get_prefs

            ensure_email_tables(conn)
            prefs = get_prefs(conn, subject)
            with patch("app.digests.send_marketing_email"):
                first = fanout_match_event(
                    conn,
                    user_id=subject,
                    kind="match_near",
                    match=match,
                    prefs=prefs,
                    when=when,
                )
                conn.commit()
                self.assertEqual(first["status"], "sent", first)
                self.assertIn("in_app", first["channels"])
                second = fanout_match_event(
                    conn,
                    user_id=subject,
                    kind="match_near",
                    match=match,
                    prefs=prefs,
                    when=when,
                )
                self.assertEqual(second.get("reason"), "already_logged")
            rows = conn.execute(
                "SELECT kind, payload FROM notifications WHERE recipient_subject = ?",
                (subject,),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            payload = json.loads(rows[0][1] or "{}")
            self.assertEqual(payload.get("cta_href"), "/jobs/99")
            self.assertTrue(payload.get("academy_courses") or payload.get("roadmap") is not None)
            self.assertTrue(payload.get("ai_title"))
            self.assertTrue(payload.get("ai_body"))
            self.assertIn("Near Engineer", payload["ai_title"])
            self.assertFalse(first.get("ai_applied"))
            self.assertTrue(str(first.get("ai_status") or "").startswith("template"))
        finally:
            conn.close()

    def test_fanout_ai_copy_applied(self):
        subject = "fanout-ai-1"
        self._seed_profile(subject)
        self._grant(subject)
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        match = {
            "job_id": 77,
            "title": "Backend",
            "company": "Acme",
            "score": 0.88,
            "have": ["Python"],
            "missing": [],
            "explanation": "strong",
        }
        from app.ai_gateway import GatewayResult
        from app.email_prefs import ensure_email_tables, get_prefs

        fake = GatewayResult(
            ok=True,
            data={
                "title": "Sənə uyğun: Backend · 88%",
                "body": "Python üst-üstə düşür. Bax və müraciət et.",
                "tone": "encouraging",
            },
            prompt_version="engagement-copy-v1",
            model="test",
        )
        conn = _connect()
        try:
            ensure_email_tables(conn)
            prefs = get_prefs(conn, subject)
            with (
                patch.dict(
                    "os.environ",
                    {
                        "OPENAI_API_KEY": "sk-test",
                        "AI_GATEWAY_ENABLED": "1",
                        "ENGAGEMENT_AI_COPY_ENABLED": "1",
                    },
                    clear=False,
                ),
                patch("app.engagement_copy.complete_json", return_value=fake),
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
            self.assertTrue(result.get("ai_applied"))
            self.assertEqual(result.get("ai_status"), "applied")
            row = conn.execute(
                "SELECT payload FROM notifications WHERE recipient_subject = ?",
                (subject,),
            ).fetchone()
            payload = json.loads(row[0] or "{}")
            self.assertEqual(payload.get("ai_title"), "Sənə uyğun: Backend · 88%")
            self.assertIn("Python", payload.get("ai_body") or "")
        finally:
            conn.close()

    def test_process_user_sends_match_new_and_near(self):
        subject = "eng-run-1"
        self._seed_profile(subject)
        self._grant(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "eng@example.com")
        when = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        fake = [
            {
                "job_id": 10,
                "title": "Senior Backend",
                "company": "Acme",
                "score": 0.88,
                "have": ["Python", "Docker"],
                "missing": [],
                "explanation": "strong",
                "created_at": "2026-10-08T10:00:00+00:00",
            },
            {
                "job_id": 11,
                "title": "Data Engineer",
                "company": "Beta",
                "score": 0.55,
                "have": ["Python"],
                "missing": ["Kubernetes", "Spark"],
                "explanation": "near",
                "created_at": "2026-10-08T11:00:00+00:00",
            },
        ]
        conn = _connect()
        try:
            with (
                patch("app.digests._top_matches", return_value=fake),
                patch("app.digests.send_marketing_email") as send_mock,
            ):
                result = process_user_engagement(conn, user_id=subject, when=when)
                conn.commit()
            self.assertEqual(result["match_new"], "sent", result)
            self.assertEqual(result["match_near"], "sent", result)
            # Daily marketing cap: first email (match_new/high_match) may block near email;
            # in-app still sent for both.
            kinds = {
                row[0]
                for row in conn.execute(
                    "SELECT kind FROM notifications WHERE recipient_subject = ?",
                    (subject,),
                ).fetchall()
            }
            self.assertEqual(kinds, {"match_new", "match_near"})
            self.assertGreaterEqual(send_mock.call_count, 1)
            # Dedup on second run.
            with (
                patch("app.digests._top_matches", return_value=fake),
                patch("app.digests.send_marketing_email") as send_mock2,
            ):
                again = process_user_engagement(conn, user_id=subject, when=when)
            self.assertIn(again["reasons"].get("match_new"), {"daily_kind_limit", "already_logged", "none"})
            self.assertEqual(again["match_new"], "skipped")
            self.assertEqual(again["match_near"], "skipped")
            send_mock2.assert_not_called()
        finally:
            conn.close()

    def test_process_user_catalog_fallback_no_email(self):
        """Stale catalog matches still fan out in-app; email stays fresh-only."""
        subject = "eng-catalog-1"
        self._seed_profile(subject)
        self._grant(subject)
        from app.profiles import remember_contact_email

        remember_contact_email(subject, "catalog@example.com")
        when = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        stale = [
            {
                "job_id": 40,
                "title": "Senior Backend",
                "company": "Acme",
                "score": 0.9,
                "have": ["Python", "Docker"],
                "missing": [],
                "explanation": "strong",
                "created_at": "2026-09-01T10:00:00+00:00",
            },
            {
                "job_id": 41,
                "title": "Data Engineer",
                "company": "Beta",
                "score": 0.55,
                "have": ["Python"],
                "missing": ["Kubernetes"],
                "explanation": "near",
                "created_at": "2026-09-02T11:00:00+00:00",
            },
        ]
        conn = _connect()
        try:
            with (
                patch("app.digests._top_matches", return_value=stale),
                patch("app.digests.send_marketing_email") as send_mock,
            ):
                result = process_user_engagement(conn, user_id=subject, when=when)
                conn.commit()
            self.assertEqual(result["match_new"], "sent", result)
            self.assertEqual(result["match_near"], "sent", result)
            self.assertEqual(result["reasons"].get("match_new"), "catalog")
            self.assertEqual(result["reasons"].get("match_near"), "catalog")
            send_mock.assert_not_called()
            self.assertTrue(
                job_ever_logged(conn, user_id=subject, kind="match_new", job_id=40)
            )
            # Same stale jobs must not re-notify.
            with (
                patch("app.digests._top_matches", return_value=stale),
                patch("app.digests.send_marketing_email") as send_mock2,
            ):
                again = process_user_engagement(conn, user_id=subject, when=when)
            self.assertEqual(again["match_new"], "skipped")
            self.assertIn(again["reasons"].get("match_new"), {"none", "daily_kind_limit"})
            send_mock2.assert_not_called()
        finally:
            conn.close()

    def test_resolve_match_candidate_prefers_fresh(self):
        fresh = [
            {
                "job_id": 1,
                "title": "A",
                "score": 0.9,
                "have": ["Python"],
                "missing": [],
                "created_at": "2026-10-08",
            }
        ]
        catalog = fresh + [
            {
                "job_id": 2,
                "title": "B",
                "score": 0.95,
                "have": ["Python"],
                "missing": [],
                "created_at": "2026-01-01",
            }
        ]
        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            match, source = resolve_match_candidate(
                conn,
                user_id="u-res",
                kind="match_new",
                fresh=fresh,
                catalog=catalog,
            )
            self.assertIsNotNone(match)
            self.assertEqual(match["job_id"], 1)
            self.assertEqual(source, "fresh")
        finally:
            conn.close()

    def test_internal_engagement_jobs_requires_token(self):
        denied = self.client.post("/api/v1/internal/engagement-jobs")
        self.assertEqual(denied.status_code, 401)
        with patch("app.engagement.list_engagement_user_ids", return_value=[]):
            ok = self.client.post(
                "/api/v1/internal/engagement-jobs?dry_run=true",
                headers={"X-Internal-Token": "test-internal-token"},
            )
        self.assertEqual(ok.status_code, 200, ok.text)
        body = ok.json()
        self.assertTrue(body["dry_run"])
        self.assertIn("match_new", body)
        self.assertIn("match_near", body)
        self.assertIn("users", body)

    def test_run_engagement_jobs_dry_run(self):
        with patch("app.engagement.list_engagement_user_ids", return_value=[]):
            stats = run_engagement_jobs(dry_run=True)
        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["users"], 0)


class EngagementPhase4Tests(unittest.TestCase):
    """profile_nudge + coach_weekly + /me/insights (reuses phase 2 fixtures)."""

    setUp = EngagementPhase2Tests.setUp
    tearDown = EngagementPhase2Tests.tearDown
    _auth = EngagementPhase2Tests._auth
    _seed_skills = EngagementPhase2Tests._seed_skills
    _seed_profile = EngagementPhase2Tests._seed_profile
    _grant = EngagementPhase2Tests._grant

    def test_week_period_key(self):
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(week_period_key(when=when), "2026-W41")

    def test_profile_nudge_reasons_draft_and_few_skills(self):
        when = datetime(2026, 10, 8, tzinfo=timezone.utc)
        draft = {
            "exists": True,
            "status": "draft",
            "updated_at": "2026-10-01T00:00:00+00:00",
            "profile": {"skills": [{"name": "Python"}]},
        }
        reasons = profile_nudge_reasons(draft, when=when)
        self.assertIn("draft", reasons)
        self.assertIn("few_skills", reasons)
        self.assertTrue(needs_profile_nudge(draft, when=when))

        fresh = {
            "exists": True,
            "status": "confirmed",
            "updated_at": "2026-10-07T00:00:00+00:00",
            "profile": {
                "skills": [
                    {"name": "Python"},
                    {"name": "Docker"},
                    {"name": "SQL"},
                ]
            },
        }
        self.assertEqual(profile_nudge_reasons(fresh, when=when), [])

        stale = {
            "exists": True,
            "status": "confirmed",
            "updated_at": (when - timedelta(days=20)).isoformat(),
            "profile": {
                "skills": [
                    {"name": "Python"},
                    {"name": "Docker"},
                    {"name": "SQL"},
                ]
            },
        }
        self.assertIn("stale", profile_nudge_reasons(stale, when=when))

    def test_fanout_profile_nudge_weekly_dedup(self):
        subject = "nudge-1"
        self._seed_profile(subject, status="draft")
        self._grant(subject)
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        from app.email_prefs import ensure_email_tables, get_prefs

        conn = _connect()
        try:
            ensure_email_tables(conn)
            prefs = get_prefs(conn, subject)
            with patch("app.digests.send_marketing_email"):
                first = fanout_profile_nudge(
                    conn,
                    user_id=subject,
                    prefs=prefs,
                    when=when,
                    reasons=["draft", "few_skills"],
                )
                conn.commit()
                self.assertEqual(first["status"], "sent", first)
                self.assertIn("in_app", first["channels"])
                second = fanout_profile_nudge(
                    conn,
                    user_id=subject,
                    prefs=prefs,
                    when=when,
                    reasons=["draft"],
                )
            self.assertEqual(second.get("reason"), "already_logged")
            row = conn.execute(
                "SELECT kind, payload FROM notifications WHERE recipient_subject = ?",
                (subject,),
            ).fetchone()
            self.assertEqual(row[0], "profile_nudge")
            payload = json.loads(row[1] or "{}")
            self.assertEqual(payload.get("cta_href"), "/profile/review")
            self.assertTrue(payload.get("ai_title"))
        finally:
            conn.close()

    def test_coach_context_uses_default_top_for_lang_or_group(self):
        """Backend Engineer + Java must still surface complementary gaps (not empty → Academy-only)."""
        subject = "coach-java-backend"
        with sqlite3.connect(self.db) as conn:
            for name in (
                "Java",
                "Python",
                "Go",
                "Node.js",
                ".NET",
                "SQL",
                "Docker",
                "Kafka",
                "Redis",
            ):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO skill_dictionary (
                        canonical_name, synonyms, category_hint, academy_course_ids, updated_at
                    ) VALUES (?, '[]', '', '[]', '2026-10-08T12:00:00+00:00')
                    """,
                    (name,),
                )
            ids = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT canonical_name, id FROM skill_dictionary"
                )
            }
            conn.execute(
                """
                INSERT INTO role_taxonomy (
                    canonical_name, category, synonyms, academy_career_path_id, updated_at
                ) VALUES (?, 'Backend', ?, ?, '2026-10-08T12:00:00+00:00')
                """,
                (
                    "Backend Engineer",
                    json.dumps(["Backend Developer"]),
                    "backend-developer",
                ),
            )
            role_id = conn.execute(
                "SELECT id FROM role_taxonomy WHERE canonical_name = 'Backend Engineer'"
            ).fetchone()[0]
            for skill, weight, group in (
                ("Java", 0.7, "lang"),
                ("Python", 0.7, "lang"),
                ("Go", 0.65, "lang"),
                ("Node.js", 0.65, "lang"),
                (".NET", 0.6, "lang"),
                ("SQL", 0.55, ""),
                ("Docker", 0.4, ""),
                ("Kafka", 0.35, ""),
                ("Redis", 0.35, ""),
            ):
                conn.execute(
                    """
                    INSERT INTO role_skill_weight (role_id, skill_id, weight, group_key)
                    VALUES (?, ?, ?, ?)
                    """,
                    (role_id, ids[skill], weight, group),
                )
            ensure_cv_queue_tables(conn)
            profile = {
                "headline": "Backend Engineer",
                "skills": [{"name": "Java", "years": 3}],
                "seniority": "middle",
                "total_years": 3,
            }
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, '', ?, 'Backend Engineer', 'middle', 3, 'confirmed', 'rules', 0.8, 'anonymous', ?)
                """,
                (subject, json.dumps(profile), "2026-10-08T12:00:00+00:00"),
            )
            conn.commit()
        self._grant(subject)
        conn = _connect()
        try:
            ctx = build_coach_weekly_context(
                conn,
                user_id=subject,
                lang="en",
                allow_ai_provider=False,
            )
            self.assertIsNotNone(ctx)
            self.assertEqual(ctx.get("role"), "Backend Engineer")
            must = set(ctx.get("must_learn") or [])
            self.assertTrue(
                must & {"SQL", "Docker", "Kafka", "Redis"},
                f"expected complementary gaps, got {must}",
            )
            self.assertNotIn("Python", must)
            self.assertNotIn("Go", must)
            lr = (ctx.get("growth") or {}).get("learning_roadmap") or {}
            hero_missing = set((lr.get("hero") or {}).get("missing") or [])
            self.assertTrue(hero_missing & must)
            week_texts = " ".join(
                str(i.get("text") or "")
                for i in ((lr.get("this_week") or {}).get("items") or [])
            )
            self.assertTrue(
                any(name in week_texts for name in must),
                f"this_week should name a missing skill, got {week_texts!r}",
            )
        finally:
            conn.close()

    def test_fanout_coach_weekly(self):
        subject = "coach-1"
        self._seed_profile(subject)
        self._grant(subject)
        when = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        from app.email_prefs import ensure_email_tables, get_prefs

        ctx = {
            "role": "Backend Developer",
            "must_learn": ["Kubernetes"],
            "already_strong": ["Python", "Docker"],
            "growth": {
                "academy_courses": [
                    {"slug": "k8s-fundamentals", "url": "https://ingress.academy/trainings/k8s-fundamentals/", "skill": "Kubernetes"}
                ],
                "career_path": None,
                "roadmap": [],
                "cta_secondary_href": "https://ingress.academy/trainings/k8s-fundamentals/",
                "missing_names": ["Kubernetes"],
            },
            "coach": None,
            "gap": {},
            "academy_career_path": "",
        }
        conn = _connect()
        try:
            ensure_email_tables(conn)
            prefs = get_prefs(conn, subject)
            with patch("app.digests.send_marketing_email"):
                result = fanout_coach_weekly(
                    conn,
                    user_id=subject,
                    prefs=prefs,
                    when=when,
                    ctx=ctx,
                )
                conn.commit()
            self.assertEqual(result["status"], "sent", result)
            row = conn.execute(
                "SELECT kind, job_title, payload FROM notifications WHERE recipient_subject = ?",
                (subject,),
            ).fetchone()
            self.assertEqual(row[0], "coach_weekly")
            self.assertEqual(row[1], "Backend Developer")
            payload = json.loads(row[2] or "{}")
            self.assertEqual(payload.get("cta_href"), "/me/insights/roadmap")
            self.assertEqual(payload.get("role"), "Backend Developer")
            self.assertIn("Kubernetes", payload.get("must_learn") or [])
        finally:
            conn.close()

    def test_process_user_sends_nudge_for_draft(self):
        subject = "nudge-run-1"
        self._seed_profile(subject, status="draft")
        self._grant(subject)
        when = datetime(2026, 10, 8, 15, 0, tzinfo=timezone.utc)
        conn = _connect()
        try:
            with (
                patch("app.digests._top_matches", return_value=[]),
                patch("app.digests.send_marketing_email"),
            ):
                result = process_user_engagement(conn, user_id=subject, when=when)
                conn.commit()
            self.assertEqual(result["reasons"].get("eligible"), "profile_not_confirmed")
            self.assertEqual(result["profile_nudge"], "sent", result)
            kinds = {
                row[0]
                for row in conn.execute(
                    "SELECT kind FROM notifications WHERE recipient_subject = ?",
                    (subject,),
                ).fetchall()
            }
            self.assertEqual(kinds, {"profile_nudge"})
        finally:
            conn.close()

    def test_insights_endpoint(self):
        subject = "insights-1"
        self._seed_profile(subject)
        self._grant(subject)
        conn = _connect()
        try:
            ensure_engagement_tables(conn)
            insert_notification(
                conn,
                recipient=subject,
                kind="coach_weekly",
                job_id=None,
                job_title="Backend Developer",
                application_id=None,
                status="",
                reason="",
                language="az",
                payload={
                    "role": "Backend Developer",
                    "must_learn": ["Kubernetes"],
                    "already_strong": ["Python"],
                    "cta_href": "/me/insights/roadmap",
                    "ai_title": "Bu həftənin planı: Backend Developer",
                    "ai_body": "Kubernetes öyrən.",
                },
            )
            insert_notification(
                conn,
                recipient=subject,
                kind="match_near",
                job_id=55,
                job_title="Near Role",
                application_id=None,
                status="",
                reason="",
                language="az",
                payload={
                    "score": 0.55,
                    "job_id": 55,
                    "job_title": "Near Role",
                    "have": ["Python"],
                    "missing": [{"name": "Kubernetes"}],
                    "cta_href": "/jobs/55",
                },
            )
            conn.commit()
            payload = insights_payload(conn, user_id=subject, lang="az")
            self.assertTrue(payload["matching_consent"])
            self.assertEqual(payload["coach"]["role"], "Backend Developer")
            self.assertEqual(payload["coach"]["source"], "notification")
            self.assertEqual(len(payload["near_misses"]), 1)
            self.assertEqual(payload["near_misses"][0]["job_id"], 55)
        finally:
            conn.close()

        with self._auth("job:candidate", subject):
            res = self.client.get("/api/v1/me/insights?lang=az", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["coach"]["role"], "Backend Developer")
        self.assertEqual(body["near_misses"][0]["job_title"], "Near Role")


if __name__ == "__main__":
    unittest.main()
