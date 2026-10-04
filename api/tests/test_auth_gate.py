"""Guest browse stays open. Employer profile gate and candidate links are closed."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.main import app
from app.sqlite_jobs import list_jobs


def user(scopes: str, subject: str = "42") -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class AuthGateTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_guest_can_browse_without_source_url(self):
        response = self.client.get("/api/v1/jobs")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(items)
        self.assertNotIn("source_url", items[0])
        self.assertNotIn("url", items[0])
        text = response.text.lower()
        self.assertNotIn("http://", text)
        self.assertNotIn("https://", text)

    def test_guest_apply_and_original_hide_the_address(self):
        job_id = list_jobs()[0]["id"]
        for path in (f"/api/v1/jobs/{job_id}/apply", f"/api/v1/jobs/{job_id}/original"):
            response = self.client.post(path) if path.endswith("apply") else self.client.get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertNotIn("http", response.text.lower())

    def test_employer_without_profile_is_gated_until_name_city_about(self):
        import sqlite3

        from app.profiles import DATA_PATH

        conn = sqlite3.connect(DATA_PATH)
        conn.execute("DELETE FROM company_profiles WHERE subject = ?", ("employer-1",))
        conn.commit()
        conn.close()
        employer = user("job:employer profile:read", subject="employer-1")
        with patch("app.account.verify_access_token", return_value=employer):
            me = self.client.get("/api/v1/me", headers={"Authorization": "Bearer test"})
            self.assertEqual(me.status_code, 200)
            body = me.json()
            self.assertTrue(body["employer"])
            self.assertFalse(body["candidate"])
            self.assertFalse(body["staff"])
            self.assertTrue(body["needs_company_profile"])
            self.assertFalse(body["company_profile"]["complete"])

            rejected = self.client.post(
                "/api/v1/company-profile",
                headers={"Authorization": "Bearer test"},
                json={"company_name": "  ", "city": "Baki", "about": "Qisa"},
            )
            self.assertEqual(rejected.status_code, 422)

            saved = self.client.post(
                "/api/v1/company-profile",
                headers={"Authorization": "Bearer test"},
                json={
                    "company_name": "Ingress MMC",
                    "city": "Baki",
                    "about": "Komanda ucun aciq vakansiyalar.",
                },
            )
            self.assertEqual(saved.status_code, 200)
            done = saved.json()
            self.assertFalse(done["needs_company_profile"])
            self.assertTrue(done["company_profile"]["complete"])
            self.assertEqual(done["company_profile"]["company_name"], "Ingress MMC")

    def test_staff_skips_the_company_gate(self):
        staff = user("job:employer job:staff", subject="staff-1")
        with patch("app.account.verify_access_token", return_value=staff):
            me = self.client.get("/api/v1/me", headers={"Authorization": "Bearer test"})
        self.assertEqual(me.status_code, 200)
        self.assertTrue(me.json()["staff"])
        self.assertFalse(me.json()["needs_company_profile"])

    def test_candidate_receives_original_employer_does_not(self):
        job_id = list_jobs()[0]["id"]
        candidate = user("job:candidate", subject="candidate-1")
        employer = user("job:employer", subject="employer-2")
        with patch("app.account.verify_access_token", return_value=employer):
            denied = self.client.get(
                f"/api/v1/jobs/{job_id}/original",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn("http", denied.text.lower())

        with patch("app.account.verify_access_token", return_value=candidate):
            allowed = self.client.get(
                f"/api/v1/jobs/{job_id}/original",
                headers={"Authorization": "Bearer test"},
            )
            applied = self.client.post(
                f"/api/v1/jobs/{job_id}/apply",
                headers={"Authorization": "Bearer test"},
            )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()["url"].startswith("http"))
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(applied.json()["url"], allowed.json()["url"])

    def test_transaction_rejects_a_foreign_return_path(self):
        response = self.client.post(
            "/api/v1/auth/transactions",
            json={
                "state": "a" * 22,
                "verifier": "b" * 43,
                "nonce": "c" * 43,
                "return_to": "https://evil.example/phish",
                "intent": "job_candidate",
                "redirect_uri": "http://localhost:3010/api/auth/callback",
            },
        )
        self.assertEqual(response.status_code, 204)
        from app.profiles import take_transaction

        row = take_transaction("a" * 22)
        self.assertIsNotNone(row)
        self.assertEqual(row["return_to"], "/")
        self.assertEqual(row["intent"], "job_candidate")


if __name__ == "__main__":
    unittest.main()
