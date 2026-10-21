"""Engagement AI copy: flag off → template; invalid AI → soft-fail."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.ai_gateway import GatewayResult
from app.cabinet_store import _connect, ensure_schema
from app.engagement_copy import maybe_engagement_copy, template_copy


class EngagementCopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.env = patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-test",
                "AI_GATEWAY_ENABLED": "1",
                "ENGAGEMENT_AI_COPY_ENABLED": "1",
            },
            clear=False,
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def test_template_includes_score_and_skills(self):
        copy = template_copy(
            kind="match_near",
            locale="az",
            job_title="Data Engineer",
            score=0.58,
            missing=["Kubernetes", "Spark"],
        )
        self.assertIn("58%", copy["title"])
        self.assertIn("Data Engineer", copy["title"])
        self.assertIn("Kubernetes", copy["body"])
        self.assertLessEqual(len(copy["title"]), 60)
        self.assertLessEqual(len(copy["body"]), 160)

    def test_flag_off_uses_template(self):
        conn = _connect()
        try:
            with patch.dict("os.environ", {"ENGAGEMENT_AI_COPY_ENABLED": "0"}, clear=False):
                copy, status = maybe_engagement_copy(
                    conn,
                    kind="match_new",
                    locale="en",
                    job_id=1,
                    job_title="Backend",
                    score=0.82,
                    have=["Python"],
                    missing=[],
                )
            self.assertTrue(status.startswith("template"))
            self.assertIn("Backend", copy["title"])
            self.assertIn("82%", copy["title"])
        finally:
            conn.close()

    def test_defaults_on_with_api_key_when_env_unset(self):
        from app.ai_flags import feature_on, invalidate_flag_cache
        from app.engagement_copy import copy_enabled

        conn = _connect()
        try:
            env = {k: v for k, v in os.environ.items() if k != "ENGAGEMENT_AI_COPY_ENABLED"}
            env["OPENAI_API_KEY"] = "sk-test"
            with patch.dict("os.environ", env, clear=True):
                invalidate_flag_cache()
                self.assertTrue(feature_on("engagement_copy", conn))
                self.assertTrue(copy_enabled(conn))
        finally:
            invalidate_flag_cache()
            conn.close()

    def test_ai_applied(self):
        fake = GatewayResult(
            ok=True,
            data={
                "title": "New match: Backend · 82%",
                "body": "Python and Docker line up. Open and apply.",
                "tone": "encouraging",
            },
            prompt_version="engagement-copy-v1",
            model="test",
        )
        conn = _connect()
        try:
            with patch("app.engagement_copy.complete_json", return_value=fake) as ai_mock:
                copy, status = maybe_engagement_copy(
                    conn,
                    kind="match_new",
                    locale="en",
                    job_id=10,
                    job_title="Backend",
                    score=0.82,
                    have=["Python", "Docker"],
                    missing=[],
                    when=datetime(2026, 10, 8, tzinfo=timezone.utc),
                )
            self.assertEqual(status, "applied")
            self.assertEqual(copy["title"], "New match: Backend · 82%")
            self.assertIn("Python", copy["body"])
            ai_mock.assert_called_once()
            kwargs = ai_mock.call_args.kwargs
            self.assertEqual(kwargs["purpose"], "engagement_copy")
            self.assertEqual(kwargs["prompt_version"], "engagement-copy-v1")
            self.assertIn("day: 2026-10-08", kwargs["user"])
        finally:
            conn.close()

    def test_invalid_ai_soft_fails(self):
        fake = GatewayResult(
            ok=True,
            data={"title": "x", "body": "y"},
            prompt_version="engagement-copy-v1",
            model="test",
        )
        conn = _connect()
        try:
            with patch("app.engagement_copy.complete_json", return_value=fake):
                copy, status = maybe_engagement_copy(
                    conn,
                    kind="match_near",
                    locale="az",
                    job_id=11,
                    job_title="Data Engineer",
                    score=0.55,
                    have=["Python"],
                    missing=["Kubernetes"],
                )
            self.assertEqual(status, "template:empty_copy")
            self.assertIn("Data Engineer", copy["title"])
            self.assertIn("Kubernetes", copy["body"])
        finally:
            conn.close()

    def test_near_miss_must_mention_missing_skill(self):
        fake = GatewayResult(
            ok=True,
            data={
                "title": "Almost there: Data Engineer · 55%",
                "body": "You are close — keep learning and apply soon.",
                "tone": "encouraging",
            },
            prompt_version="engagement-copy-v1",
            model="test",
        )
        conn = _connect()
        try:
            with patch("app.engagement_copy.complete_json", return_value=fake):
                copy, status = maybe_engagement_copy(
                    conn,
                    kind="match_near",
                    locale="en",
                    job_id=12,
                    job_title="Data Engineer",
                    score=0.55,
                    have=["Python"],
                    missing=["Kubernetes"],
                )
            self.assertEqual(status, "template:missing_skill")
            self.assertIn("Kubernetes", copy["body"])
        finally:
            conn.close()

    def test_provider_error_soft_fails(self):
        fake = GatewayResult(
            ok=False,
            error="ai_budget_exceeded",
            prompt_version="engagement-copy-v1",
            model="test",
        )
        conn = _connect()
        try:
            with patch("app.engagement_copy.complete_json", return_value=fake):
                copy, status = maybe_engagement_copy(
                    conn,
                    kind="match_new",
                    locale="ru",
                    job_title="Backend",
                    score=0.9,
                    have=["Go"],
                )
            self.assertEqual(status, "template:ai_budget_exceeded")
            self.assertIn("Backend", copy["title"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
