"""GET /api/v1/me/export + DELETE /api/v1/me (Phase 1 privacy rights)."""

import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.main import app
from app.me_data import audit_pseudonym


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


SAMPLE = {
    "contact": {"full_name": "Aysel", "email": "aysel@example.com", "phone": "", "city": "", "country": ""},
    "headline": "Backend Developer",
    "seniority": "middle",
    "total_years": 5.0,
    "work_history": [],
    "skills": [{"name": "Java", "years": 5, "level": "advanced", "source": "cv"}],
    "languages": [],
    "education": [],
    "desired_roles": [],
    "preferences": {},
    "salary_expectation": {},
    "parse_meta": {"method": "rules", "confidence": 0.8, "parser_version": "1.0"},
}


class MeDataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.accounts = root / "accounts.sqlite"
        self.cvs = root / "cvs"
        self.cvs.mkdir()
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.accounts_patch = patch("app.profiles.DATA_PATH", self.accounts)
        self.cv_patch = patch("app.applications.CV_ROOT", self.cvs)
        self.path_patch.start()
        self.accounts_patch.start()
        self.cv_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}
        self.subject = "cand-export-1"

    def tearDown(self):
        self.path_patch.stop()
        self.accounts_patch.stop()
        self.cv_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str = "job:candidate", subject: str | None = None):
        return patch(
            "app.account.verify_access_token",
            return_value=user(scopes, subject or self.subject),
        )

    def _seed(self):
        stored = "a" * 32 + ".pdf"
        (self.cvs / stored).write_bytes(b"%PDF-1.4 export-cv")
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            ensure_cv_queue_tables(conn)
            from app.consents import ensure_consent_tables
            from app.cv_profile import ensure_profile_tables

            ensure_consent_tables(conn)
            ensure_profile_tables(conn)
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, 'Backend Developer', 'middle', 5.0,
                          'confirmed', 'rules', 0.8, 'anonymous', ?)
                """,
                (
                    self.subject,
                    stored,
                    json.dumps(SAMPLE, ensure_ascii=False),
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.execute(
                """
                INSERT INTO consent (user_id, kind, granted, version, ts, ip, ua)
                VALUES (?, 'emails', 1, 'v1', ?, '127.0.0.1', 'test')
                """,
                (self.subject, "2026-10-05T12:00:00+00:00"),
            )
            conn.execute(
                """
                INSERT INTO profile_edit_log (
                    user_id, profile_id, action, before_data, after_data,
                    before_status, after_status, ts
                ) VALUES (?, 1, 'confirm', '{}', '{}', 'draft', 'confirmed', ?)
                """,
                (self.subject, "2026-10-05T12:00:00+00:00"),
            )
            conn.execute(
                """
                INSERT INTO jobs (
                    title, company, city, text, status, created_at, norm_key,
                    owner_subject, language, updated_at
                ) VALUES (
                    'Dev', 'Acme', 'Baku', 'desc', 'published', ?, 'norm-export-1',
                    'employer-1', 'az', ?
                )
                """,
                ("2026-10-05T12:00:00+00:00", "2026-10-05T12:00:00+00:00"),
            )
            job_id = conn.execute("SELECT id FROM jobs LIMIT 1").fetchone()[0]
            conn.execute(
                """
                INSERT INTO applications (
                    job_id, candidate_subject, message, cv_name, cv_stored, created_at,
                    status, decision_reason, phone, email, answers
                ) VALUES (?, ?, 'hello', 'cv.pdf', ?, ?, 'submitted', '',
                          '+994501112233', 'aysel@example.com', '[]')
                """,
                (job_id, self.subject, stored, "2026-10-05T12:00:00+00:00"),
            )
            conn.commit()
        from app.profiles import save_candidate_profile

        save_candidate_profile(self.subject, "Aysel", "+994 50 111 22 33", "aysel@example.com")

    def test_export_zip_contains_json_and_cv(self):
        self._seed()
        with self._auth():
            res = self.client.get("/api/v1/me/export", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/zip")
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = set(zf.namelist())
            self.assertIn("export.json", names)
            stored = "a" * 32 + ".pdf"
            self.assertIn(f"cvs/{stored}", names)
            payload = json.loads(zf.read("export.json"))
            self.assertEqual(payload["user_id"], self.subject)
            self.assertEqual(payload["contact_profile"]["display_name"], "Aysel")
            self.assertTrue(payload["cv_profile"]["exists"])
            self.assertEqual(zf.read(f"cvs/{stored}"), b"%PDF-1.4 export-cv")

    def test_delete_removes_profile_cv_prefs_keeps_audit_pseudonym(self):
        self._seed()
        stored = "a" * 32 + ".pdf"
        self.assertTrue((self.cvs / stored).is_file())
        with self._auth():
            res = self.client.delete("/api/v1/me", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["deleted"])
        pseudo = audit_pseudonym(self.subject)
        self.assertEqual(body["pseudonym"], pseudo)

        with sqlite3.connect(self.db) as conn:
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM candidate_profile WHERE user_id = ?",
                    (self.subject,),
                ).fetchone()
            )
            self.assertIsNone(
                conn.execute(
                    "SELECT 1 FROM consent WHERE user_id = ?",
                    (self.subject,),
                ).fetchone()
            )
            logs = conn.execute(
                "SELECT user_id, action FROM profile_edit_log ORDER BY id"
            ).fetchall()
            self.assertTrue(logs)
            self.assertTrue(all(row[0] == pseudo for row in logs))
            self.assertIn("delete_account_data", {row[1] for row in logs})
            app = conn.execute(
                """
                SELECT candidate_subject, phone, email, cv_stored, message
                FROM applications LIMIT 1
                """
            ).fetchone()
            self.assertEqual(app[0], pseudo)
            self.assertEqual(app[1], "")
            self.assertEqual(app[2], "")
            self.assertEqual(app[3], "")
            self.assertEqual(app[4], "")

        self.assertFalse((self.cvs / stored).exists())
        from app.profiles import candidate_profile_for, contact_email_for

        self.assertEqual(candidate_profile_for(self.subject)["display_name"], "")
        self.assertEqual(contact_email_for(self.subject), "")

    def test_export_requires_candidate(self):
        with self._auth(scopes="job:employer"):
            res = self.client.get("/api/v1/me/export", headers=self.headers)
        self.assertEqual(res.status_code, 403)

    def test_account_me_still_json(self):
        with self._auth():
            res = self.client.get("/api/v1/me", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["authenticated"])


if __name__ == "__main__":
    unittest.main()
