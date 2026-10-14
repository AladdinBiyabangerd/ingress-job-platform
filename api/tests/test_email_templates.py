"""HTML marketing email templates."""

import os
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from app.email_templates import (
    render_coach_weekly_html,
    render_digest_html,
    render_match_job_html,
    render_profile_nudge_html,
)
from app.digests import send_marketing_email


class EmailTemplatesTests(unittest.TestCase):
    def test_match_near_html_includes_job_and_skills(self):
        html = render_match_job_html(
            kind="match_near",
            lang="az",
            match={
                "title": "Software Engineer (All Levels)",
                "company": "Cadence Solutions",
                "score": 0.56,
                "have": ["AWS", "GCP", "MySQL", "PostgreSQL"],
                "missing": ["Kubernetes"],
                "remote": True,
                "city": "",
                "explanation": "AWS və PostgreSQL uyğundur.",
            },
            job_url="https://example.com/jobs/1",
            unsubscribe_url="https://example.com/unsub",
            tip="AWS və PostgreSQL uyğundur.",
        )
        self.assertIn("Yaxın elan", html)
        self.assertIn("Cadence Solutions", html)
        self.assertIn("56%", html)
        self.assertIn("AWS", html)
        self.assertIn("4/5 bacarıq uyğundur", html)
        self.assertIn("https://example.com/jobs/1", html)
        self.assertIn("https://example.com/unsub", html)
        self.assertIn("Uzaqdan", html)

    def test_match_html_escapes_user_content(self):
        html = render_match_job_html(
            kind="high_match",
            lang="en",
            match={
                "title": '<script>alert(1)</script>',
                "company": "Acme & Co",
                "score": 0.9,
                "have": ["C++"],
                "missing": [],
                "remote": False,
                "city": "Baku",
            },
            job_url="https://example.com/j",
            unsubscribe_url="https://example.com/u",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Acme &amp; Co", html)
        self.assertIn("Strong match", html)

    def test_digest_and_nudge_and_coach(self):
        digest = render_digest_html(
            lang="az",
            matches=[
                {
                    "job_id": 7,
                    "title": "Backend",
                    "company": "X",
                    "score": 0.8,
                    "remote": True,
                }
            ],
            job_urls={7: "https://example.com/7"},
            trends=["Python · 12%"],
            gap="Docker öyrən",
            unsubscribe_url="https://example.com/u",
            intro="Salam",
        )
        self.assertIn("Backend", digest)
        self.assertIn("Python · 12%", digest)
        self.assertIn("Docker öyrən", digest)

        nudge = render_profile_nudge_html(
            lang="en",
            reason="Missing CV",
            profile_url="https://example.com/profile",
            unsubscribe_url="https://example.com/u",
        )
        self.assertIn("Complete your profile", nudge)
        self.assertIn("Missing CV", nudge)

        coach = render_coach_weekly_html(
            lang="ru",
            role="Backend",
            must_learn=["Kubernetes"],
            already_strong=["Python"],
            tip="Курс → https://academy",
            insights_url="https://example.com/insights",
            unsubscribe_url="https://example.com/u",
        )
        self.assertIn("План на неделю", coach)
        self.assertIn("Kubernetes", coach)
        self.assertIn("Python", coach)

    def test_send_marketing_email_attaches_html(self):
        captured: list[EmailMessage] = []

        class FakeSMTP:
            def __init__(self, *a, **k):
                pass

            def starttls(self):
                return None

            def login(self, *a):
                return None

            def send_message(self, message):
                captured.append(message)

            def quit(self):
                return None

        with (
            patch.dict(
                "os.environ",
                {
                    "EMAIL_HOST": "smtp.example.com",
                    "EMAIL_PORT": "587",
                    "EMAIL_HOST_USER": "jobs@example.com",
                    "EMAIL_HOST_PASSWORD": "p",
                    "DEFAULT_FROM_EMAIL": "jobs@example.com",
                },
                clear=False,
            ),
            patch("smtplib.SMTP", FakeSMTP),
        ):
            send_marketing_email(
                to="a@example.com",
                subject="Hi",
                body="plain",
                html_body="<html><body>hi</body></html>",
                unsubscribe_link="https://example.com/u",
            )
        self.assertEqual(len(captured), 1)
        msg = captured[0]
        self.assertEqual(msg.get_content_type(), "multipart/alternative")
        parts = list(msg.iter_parts())
        types = {p.get_content_type() for p in parts}
        self.assertIn("text/plain", types)
        self.assertIn("text/html", types)

    def test_app_base_url_prefers_web_public_not_localhost_in_prod(self):
        from app.email_prefs import app_base_url

        with patch.dict(
            "os.environ",
            {
                "DEBUG": "False",
                "APP_URL": "",
                "NEXT_PUBLIC_APP_URL": "",
                "PUBLIC_WEB_URL": "",
                "WEB_PUBLIC_DOMAIN": "jobs.example.com",
                "RAILWAY_ENVIRONMENT": "production",
            },
            clear=False,
        ):
            # Clear empty-string keys that patch.dict may leave; force unset.
            for key in ("APP_URL", "NEXT_PUBLIC_APP_URL", "PUBLIC_WEB_URL"):
                os.environ.pop(key, None)
            os.environ["DEBUG"] = "False"
            os.environ["WEB_PUBLIC_DOMAIN"] = "jobs.example.com"
            self.assertEqual(app_base_url(), "https://jobs.example.com")

        with patch.dict(
            "os.environ",
            {"DEBUG": "False", "WEB_PUBLIC_DOMAIN": "${{web.RAILWAY_PUBLIC_DOMAIN}}"},
            clear=False,
        ):
            for key in ("APP_URL", "NEXT_PUBLIC_APP_URL", "PUBLIC_WEB_URL", "WEB_PUBLIC_DOMAIN"):
                os.environ.pop(key, None)
            os.environ["DEBUG"] = "False"
            self.assertEqual(app_base_url(), "")


if __name__ == "__main__":
    unittest.main()
