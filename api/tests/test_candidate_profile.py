"""Applicant profile stays on the job site and prefills nothing by itself."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.main import app
from app.profiles import take_transaction


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


class CandidateProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "accounts.sqlite"
        self.path_patch = patch("app.profiles.DATA_PATH", self.db)
        self.path_patch.start()
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def test_candidate_profile_is_stored_on_the_job_site_not_academy(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("academy")):
            with self._auth("job:candidate", "person-1"):
                missing = self.client.get("/api/v1/me", headers=self.headers)
                self.assertEqual(missing.status_code, 200, missing.text)
                self.assertEqual(
                    missing.json()["candidate_profile"],
                    {"display_name": "", "phone": "", "email": ""},
                )

                saved = self.client.post(
                    "/api/v1/candidate-profile",
                    headers=self.headers,
                    json={
                        "display_name": "  Aysel Məmmədli  ",
                        "phone": "+994 50 123 45 67",
                        "email": "Aysel@Example.com",
                    },
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                body = saved.json()
                self.assertEqual(body["candidate_profile"]["display_name"], "Aysel Məmmədli")
                self.assertEqual(body["candidate_profile"]["phone"], "+994 50 123 45 67")
                self.assertEqual(body["candidate_profile"]["email"], "aysel@example.com")
                self.assertNotIn("http", saved.text.lower())
                self.assertTrue(self.db.exists())

                again = self.client.get("/api/v1/me", headers=self.headers)
                self.assertEqual(again.json()["candidate_profile"]["email"], "aysel@example.com")

                cleared = self.client.post(
                    "/api/v1/candidate-profile",
                    headers=self.headers,
                    json={"display_name": "Aysel", "phone": "", "email": "aysel@example.com"},
                )
                self.assertEqual(cleared.status_code, 200, cleared.text)
                self.assertEqual(cleared.json()["candidate_profile"]["phone"], "")
                self.assertEqual(cleared.json()["candidate_profile"]["display_name"], "Aysel")

    def test_employer_cannot_write_an_applicant_profile(self):
        with self._auth("job:employer", "employer-9"):
            denied = self.client.post(
                "/api/v1/candidate-profile",
                headers=self.headers,
                json={"display_name": "Firma", "phone": "+994501112233", "email": "hr@example.com"},
            )
            self.assertEqual(denied.status_code, 403)
            me = self.client.get("/api/v1/me", headers=self.headers)
            self.assertEqual(me.json()["candidate_profile"]["display_name"], "")
            company = self.client.post(
                "/api/v1/company-profile",
                headers=self.headers,
                json={"company_name": "Ingress MMC", "city": "Baki", "about": "Qisa tesvir."},
            )
            self.assertEqual(company.status_code, 200, company.text)
            self.assertEqual(company.json()["company_profile"]["company_name"], "Ingress MMC")
            self.assertFalse(company.json()["needs_company_profile"])

    def test_staff_can_save_the_applicant_profile(self):
        with self._auth("job:staff", "staff-9"):
            saved = self.client.post(
                "/api/v1/candidate-profile",
                headers=self.headers,
                json={"display_name": "Moder", "phone": "", "email": ""},
            )
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()["candidate_profile"]["display_name"], "Moder")
            self.assertTrue(saved.json()["staff"])

    def test_blank_name_and_bad_contact_are_rejected(self):
        with self._auth("job:candidate", "person-2"):
            blank = self.client.post(
                "/api/v1/candidate-profile",
                headers=self.headers,
                json={"display_name": "   ", "phone": "", "email": ""},
            )
            self.assertEqual(blank.status_code, 422)
            phone = self.client.post(
                "/api/v1/candidate-profile",
                headers=self.headers,
                json={"display_name": "Aysel", "phone": "12", "email": ""},
            )
            self.assertEqual(phone.status_code, 422)
            email = self.client.post(
                "/api/v1/candidate-profile",
                headers=self.headers,
                json={"display_name": "Aysel", "phone": "", "email": "not-an-email"},
            )
            self.assertEqual(email.status_code, 422)
            self.assertEqual(self.client.get("/api/v1/me", headers=self.headers).json()["candidate_profile"]["display_name"], "")

    def test_guest_cannot_save_a_profile(self):
        response = self.client.post(
            "/api/v1/candidate-profile",
            json={"display_name": "Aysel", "phone": "", "email": ""},
        )
        self.assertEqual(response.status_code, 401)

    def test_profile_pages_are_safe_return_paths(self):
        for index, path in enumerate(("/profile", "/en/profile", "/ru/profile")):
            state = f"{'p' * 20}{index:02d}"
            response = self.client.post(
                "/api/v1/auth/transactions",
                json={
                    "state": state,
                    "verifier": "b" * 43,
                    "nonce": "c" * 43,
                    "return_to": path,
                    "intent": "job_candidate",
                    "redirect_uri": "http://localhost:3010/api/auth/callback",
                },
            )
            self.assertEqual(response.status_code, 204, path)
            row = take_transaction(state)
            self.assertIsNotNone(row)
            self.assertEqual(row["return_to"], path)


if __name__ == "__main__":
    unittest.main()
