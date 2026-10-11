"""Parked recommendations / roadmap / employer-posting product gates."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.main import app
from app.profiles import save_profile


class ProductFeaturesTests(unittest.TestCase):
    def test_default_off(self):
        with patch.dict(os.environ, {}, clear=True):
            # Re-import helpers under emptied env (module functions read env live).
            from app.product_features import (
                employer_posting_enabled,
                recommendations_enabled,
                roadmap_enabled,
            )

            self.assertFalse(recommendations_enabled())
            self.assertFalse(roadmap_enabled())
            self.assertFalse(employer_posting_enabled())

    def test_env_on(self):
        with patch.dict(
            os.environ,
            {
                "PRODUCT_RECOMMENDATIONS_ENABLED": "1",
                "PRODUCT_ROADMAP_ENABLED": "true",
                "PRODUCT_EMPLOYER_POSTING_ENABLED": "on",
            },
            clear=False,
        ):
            from app.product_features import (
                employer_posting_enabled,
                recommendations_enabled,
                roadmap_enabled,
            )

            self.assertTrue(recommendations_enabled())
            self.assertTrue(roadmap_enabled())
            self.assertTrue(employer_posting_enabled())

    def test_env_hard_off(self):
        with patch.dict(
            os.environ,
            {
                "PRODUCT_RECOMMENDATIONS_ENABLED": "0",
                "PRODUCT_ROADMAP_ENABLED": "off",
                "PRODUCT_EMPLOYER_POSTING_ENABLED": "false",
            },
            clear=False,
        ):
            from app.product_features import (
                employer_posting_enabled,
                recommendations_enabled,
                roadmap_enabled,
            )

            self.assertFalse(recommendations_enabled())
            self.assertFalse(roadmap_enabled())
            self.assertFalse(employer_posting_enabled())


class EmployerPostingParkedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", Path(self.tmp.name) / "jobs.sqlite")
        self.path_patch.start()
        ensure_schema(create=True)
        self.client = TestClient(app)
        save_profile("park-employer", "Ingress MMC", "Baki", "Aciq vakansiyalar.")
        self.headers = {"Authorization": "Bearer test"}
        self.user = VerifiedAccess(
            subject="park-employer",
            scopes=frozenset({"job:employer"}),
        )

    def tearDown(self):
        self.path_patch.stop()
        self.tmp.cleanup()

    def test_cabinet_talent_company_profile_404_when_parked(self):
        with (
            patch.dict(os.environ, {"PRODUCT_EMPLOYER_POSTING_ENABLED": "0"}, clear=False),
            patch("app.account.verify_access_token", return_value=self.user),
        ):
            cabinet = self.client.get("/api/v1/cabinet/jobs", headers=self.headers)
            talent = self.client.get("/api/v1/talent", headers=self.headers)
            company = self.client.post(
                "/api/v1/company-profile",
                headers=self.headers,
                json={
                    "company_name": "Ingress MMC",
                    "city": "Baki",
                    "about": "Aciq vakansiyalar.",
                },
            )
            self.assertEqual(cabinet.status_code, 404, cabinet.text)
            self.assertEqual(talent.status_code, 404, talent.text)
            self.assertEqual(company.status_code, 404, company.text)
            self.assertEqual(cabinet.json().get("detail"), "Tapılmadı")
