"""In-site notifications stay even when mail settings are missing."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import remember_contact_email, save_profile


MAIL_KEYS = (
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "EMAIL_USE_TLS",
    "EMAIL_USE_SSL",
    "EMAIL_TIMEOUT",
    "DEFAULT_FROM_EMAIL",
)


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class RecordingSMTP:
    sent = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.messages = []
        RecordingSMTP.sent.append(self)

    def starttls(self):
        return None

    def login(self, username, password):
        self.username = username
        return None

    def send_message(self, message):
        self.messages.append(message)

    def quit(self):
        return None


class NotificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.accounts = root / "accounts.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.account_patch = patch("app.profiles.DATA_PATH", self.accounts)
        self.path_patch.start()
        self.account_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("note-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")
        self._saved_mail = {key: os.environ.get(key) for key in MAIL_KEYS}
        for key in MAIL_KEYS:
            os.environ.pop(key, None)
        RecordingSMTP.sent = []

    def tearDown(self):
        for key, value in self._saved_mail.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.account_patch.stop()
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _ad(self, **extra):
        body = {
            "title": "Backend muhendisi",
            "company": "Ingress MMC",
            "city": "Baki",
            "remote": False,
            "text": "Komanda ucun aciq rol.",
            "language": "az",
            "salary": "",
            "job_type": "ofis",
        }
        body.update(extra)
        return body

    def _publish(self, **extra):
        with self._auth("job:employer", "note-employer"):
            created = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(**extra),
            )
            self.assertEqual(created.status_code, 201, created.text)
            ad = created.json()
        with self._auth("job:staff", "note-staff"):
            approved = self.client.post(
                f"/api/v1/admin/jobs/{ad['id']}/approve",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(approved.status_code, 200, approved.text)
        return ad["id"], approved.json()

    def _items(self, subject: str, scopes: str):
        with self._auth(scopes, subject):
            response = self.client.get(
                "/api/v1/notifications",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_guest_has_no_notification_list(self):
        guest = self.client.get("/api/v1/notifications")
        self.assertEqual(guest.status_code, 401)

    def test_events_are_saved_when_mail_is_not_configured(self):
        with patch("smtplib.SMTP", side_effect=AssertionError("smtp should not start")):
            ad_id, published = self._publish()
            owner = self._items("note-employer", "job:employer")
            self.assertEqual(owner["unread"], 1)
            self.assertEqual(owner["items"][0]["kind"], "ad_approved")
            self.assertNotIn("reason", owner["items"][0])
            self.assertEqual(self._items("note-candidate", "job:candidate")["items"], [])

            with self._auth("job:candidate", "note-candidate"):
                created = self.client.post(
                    f"/api/v1/jobs/{ad_id}/apply",
                    headers={"Authorization": "Bearer test"},
                    json={"message": "Bu rol mene uygundur."},
                )
                self.assertEqual(created.status_code, 200, created.text)
            owner = self._items("note-employer", "job:employer")
            self.assertEqual([item["kind"] for item in owner["items"]], ["application_new", "ad_approved"])
            self.assertEqual(self._items("note-candidate", "job:candidate")["items"], [])

            with self._auth("job:employer", "note-employer"):
                seen = self.client.patch(
                    f"/api/v1/cabinet/applications/{created.json()['id']}",
                    headers={"Authorization": "Bearer test"},
                    json={"status": "seen", "reason": "gizli qalmalidir"},
                )
                self.assertEqual(seen.status_code, 200, seen.text)
                again = self.client.patch(
                    f"/api/v1/cabinet/applications/{created.json()['id']}",
                    headers={"Authorization": "Bearer test"},
                    json={"status": "seen", "reason": ""},
                )
                self.assertEqual(again.status_code, 200, again.text)
            candidate = self._items("note-candidate", "job:candidate")
            self.assertEqual([item["kind"] for item in candidate["items"]], ["application_seen"])
            self.assertNotIn("reason", candidate["items"][0])

            with self._auth("job:employer", "note-employer"):
                rejected = self.client.patch(
                    f"/api/v1/cabinet/applications/{created.json()['id']}",
                    headers={"Authorization": "Bearer test"},
                    json={"status": "rejected", "reason": "Tecrube catismir"},
                )
                self.assertEqual(rejected.status_code, 200, rejected.text)
            candidate = self._items("note-candidate", "job:candidate")
            self.assertEqual(candidate["items"][0]["kind"], "application_rejected")
            self.assertEqual(candidate["items"][0]["reason"], "Tecrube catismir")

        with self._auth("job:employer", "note-employer"):
            pending = self.client.post(
                "/api/v1/cabinet/jobs",
                headers={"Authorization": "Bearer test"},
                json=self._ad(title="Gozleyen rol"),
            )
            self.assertEqual(pending.status_code, 201, pending.text)
            pending_id = pending.json()["id"]
        with self._auth("job:staff", "note-staff"):
            denied = self.client.post(
                f"/api/v1/admin/jobs/{pending_id}/reject",
                headers={"Authorization": "Bearer test"},
                json={"reason": "Metn catismir"},
            )
            self.assertEqual(denied.status_code, 200, denied.text)
        rejected_note = self._items("note-employer", "job:employer")["items"][0]
        self.assertEqual(rejected_note["kind"], "ad_rejected")
        self.assertEqual(rejected_note["reason"], "Metn catismir")

        edited = dict(published)
        edited["title"] = "Backend muhendisi"
        edited["salary"] = "2500 AZN"
        with self._auth("job:employer", "note-employer"):
            salary = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._body(edited),
            )
            self.assertEqual(salary.status_code, 200, salary.text)
            self.assertEqual(salary.json()["status"], "published")
        kinds = [item["kind"] for item in self._items("note-employer", "job:employer")["items"]]
        self.assertNotIn("ad_review", kinds)

        edited["title"] = "Bas muhendis"
        with self._auth("job:employer", "note-employer"):
            review = self.client.patch(
                f"/api/v1/cabinet/jobs/{ad_id}",
                headers={"Authorization": "Bearer test"},
                json=self._body(edited),
            )
            self.assertEqual(review.status_code, 200, review.text)
            self.assertEqual(review.json()["status"], "pending")
        self.assertEqual(self._items("note-employer", "job:employer")["items"][0]["kind"], "ad_review")
        self.assertNotIn("reason", self._items("note-employer", "job:employer")["items"][0])

        with self._auth("job:staff", "note-staff"):
            staff_edit = self.client.patch(
                f"/api/v1/admin/jobs/{pending_id}",
                headers={"Authorization": "Bearer test"},
                json=self._body(pending.json() | {"title": "Staff basligi"}),
            )
            self.assertEqual(staff_edit.status_code, 200, staff_edit.text)
        self.assertNotIn(
            "ad_review",
            [item["kind"] for item in self._items("note-employer", "job:employer")["items"] if item["job_id"] == pending_id],
        )

        resubmit = self._body(denied.json() | {"title": "Duzeldilmis rol"})
        with self._auth("job:employer", "note-employer"):
            again = self.client.patch(
                f"/api/v1/cabinet/jobs/{pending_id}",
                headers={"Authorization": "Bearer test"},
                json=resubmit,
            )
            self.assertEqual(again.status_code, 200, again.text)
            self.assertEqual(again.json()["status"], "pending")
        pending_kinds = [
            item["kind"]
            for item in self._items("note-employer", "job:employer")["items"]
            if item["job_id"] == pending_id
        ]
        self.assertEqual(pending_kinds, ["ad_rejected"])

        owner = self._items("note-employer", "job:employer")
        note_id = owner["items"][0]["id"]
        with self._auth("job:candidate", "note-candidate"):
            hidden = self.client.post(
                f"/api/v1/notifications/{note_id}/read",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(hidden.status_code, 404)
        with self._auth("job:employer", "note-employer"):
            marked = self.client.post(
                f"/api/v1/notifications/{note_id}/read",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(marked.status_code, 200, marked.text)
            self.assertTrue(marked.json()["read"])
            cleared = self.client.post(
                "/api/v1/notifications/read",
                headers={"Authorization": "Bearer test"},
            )
            self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertEqual(self._items("note-employer", "job:employer")["unread"], 0)

    def test_email_is_a_separate_job_message_and_smtp_failure_does_not_crash(self):
        os.environ["EMAIL_HOST"] = "smtp.example.test"
        os.environ["EMAIL_PORT"] = "587"
        os.environ["EMAIL_HOST_USER"] = "jobs@example.test"
        os.environ["EMAIL_HOST_PASSWORD"] = "x"
        os.environ["EMAIL_USE_TLS"] = "true"
        os.environ["EMAIL_USE_SSL"] = "false"
        os.environ["DEFAULT_FROM_EMAIL"] = "Name <jobs@example.test>"
        remember_contact_email("note-employer", "owner@example.test")

        with patch("smtplib.SMTP", RecordingSMTP):
            ad_id, _published = self._publish(
                language="en",
                title="Backend engineer",
                form={
                    "message": {"enabled": True, "required": True},
                    "cv": {"enabled": False, "required": False},
                    "phone": {"enabled": False, "required": False},
                    "email": {"enabled": True, "required": True},
                    "questions": [],
                },
            )
        approved = RecordingSMTP.sent[-1].messages[-1]
        self.assertEqual(approved["From"], "Ingress Job <jobs@example.test>")
        self.assertEqual(approved["To"], "owner@example.test")
        self.assertEqual(approved["Subject"], "Your ad was approved: Backend engineer")
        self.assertIn("ingress-job", approved.get_content())
        self.assertNotIn("Reason:", approved.get_content())

        with patch("smtplib.SMTP", RecordingSMTP):
            with self._auth("job:candidate", "note-candidate"):
                created = self.client.post(
                    f"/api/v1/jobs/{ad_id}/apply",
                    headers={"Authorization": "Bearer test"},
                    json={"message": "I can start soon.", "email": "person@example.test"},
                )
                self.assertEqual(created.status_code, 200, created.text)
            with self._auth("job:employer", "note-employer"):
                empty = self.client.patch(
                    f"/api/v1/cabinet/applications/{created.json()['id']}",
                    headers={"Authorization": "Bearer test"},
                    json={"status": "rejected", "reason": "   "},
                )
                self.assertEqual(empty.status_code, 200, empty.text)
        rejected = RecordingSMTP.sent[-1].messages[-1]
        self.assertEqual(rejected["To"], "person@example.test")
        self.assertNotIn("Reason:", rejected.get_content())
        self.assertNotIn("Səbəb:", rejected.get_content())

        with patch("smtplib.SMTP", side_effect=OSError("down")):
            with self._auth("job:employer", "note-employer"):
                changed = self.client.patch(
                    f"/api/v1/cabinet/jobs/{ad_id}",
                    headers={"Authorization": "Bearer test"},
                    json=self._ad(language="en", title="Lead engineer", text="A longer description."),
                )
                self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(self._items("note-employer", "job:employer")["items"][0]["kind"], "ad_review")

        with self._auth("job:staff", "note-staff"):
            with patch("smtplib.SMTP", RecordingSMTP):
                denied = self.client.post(
                    f"/api/v1/admin/jobs/{ad_id}/reject",
                    headers={"Authorization": "Bearer test"},
                    json={"reason": "Needs a clearer title"},
                )
                self.assertEqual(denied.status_code, 200, denied.text)
        mail = RecordingSMTP.sent[-1].messages[-1]
        self.assertEqual(mail["Subject"], "Your ad was rejected: Lead engineer")
        self.assertIn("Reason: Needs a clearer title", mail.get_content())

    def _body(self, ad: dict) -> dict:
        return {
            "title": ad["title"],
            "company": ad.get("company") or "Ingress MMC",
            "city": ad.get("city") or "",
            "remote": bool(ad.get("remote")),
            "text": ad["text"],
            "language": ad["language"],
            "salary": ad.get("salary") or "",
            "job_type": ad.get("job_type") or "",
        }
