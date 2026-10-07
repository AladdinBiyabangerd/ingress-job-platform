"""GET/PUT /api/v1/profile — CV profile review (Phase 1)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth_oidc import VerifiedAccess
from app.cabinet_store import ensure_schema
from app.cv_queue import ensure_cv_queue_tables
from app.main import app


def user(scopes: str, subject: str) -> VerifiedAccess:
    return VerifiedAccess(subject=subject, scopes=frozenset(scopes.split()))


SAMPLE = {
    "contact": {
        "full_name": "Aysel",
        "email": "aysel@example.com",
        "phone": "",
        "city": "Baku",
        "country": "AZ",
    },
    "links": {"linkedin_url": "https://linkedin.com/in/aysel", "github": "", "portfolio": "", "other": []},
    "headline": "Backend Developer",
    "summary": "Backend engineer focused on APIs and data pipelines.",
    "seniority": "middle",
    "total_years": 5.5,
    "work_history": [
        {
            "title": "Backend Developer",
            "company": "Acme",
            "start": "2021-03",
            "end": None,
            "location": "Baku",
            "summary": "Built services",
            "skills": ["Java"],
        }
    ],
    "skills": [{"name": "Java", "years": 5, "level": "advanced", "source": "cv"}],
    "languages": [{"code": "en", "level": "B2"}],
    "education": [{"degree": "BSc", "field": "CS", "school": "ADA", "year": 2018}],
    "desired_roles": [],
    "preferences": {
        "remote": None,
        "relocation": None,
        "relocation_countries": [],
        "needs_visa_sponsorship": None,
    },
    "salary_expectation": {"min": None, "currency": None, "period": "year"},
    "parse_meta": {"method": "rules", "confidence": 0.82, "parser_version": "1.0", "source": "upload"},
}


class CvProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db = root / "jobs.sqlite"
        self.path_patch = patch("app.sqlite_jobs.DB_PATH", self.db)
        self.path_patch.start()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        ensure_schema(create=True)
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test"}

    def tearDown(self):
        self.path_patch.stop()
        from app import cabinet_store

        cabinet_store._ENSURED.clear()
        self.tmp.cleanup()

    def _auth(self, scopes: str, subject: str):
        return patch("app.account.verify_access_token", return_value=user(scopes, subject))

    def _seed_draft(self, subject: str, *, confidence: float = 0.82, status: str = "draft"):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            ensure_cv_queue_tables(conn)
            data = dict(SAMPLE)
            data["parse_meta"] = {**SAMPLE["parse_meta"], "confidence": confidence}
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
                    json.dumps(data, ensure_ascii=False),
                    data["headline"],
                    data["seniority"],
                    data["total_years"],
                    status,
                    "rules",
                    confidence,
                    "2026-10-05T12:00:00+00:00",
                ),
            )
            conn.commit()

    def test_empty_profile_for_candidate(self):
        with self._auth("job:candidate", "person-1"):
            res = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["status"], "empty")
        self.assertEqual(body["parse_status"], "none")
        self.assertTrue(body["low_confidence"])

    def test_get_returns_draft_and_low_confidence_fields(self):
        self._seed_draft("person-2", confidence=0.3)
        with self._auth("job:candidate", "person-2"):
            res = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["exists"])
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["headline"], "Backend Developer")
        self.assertEqual(body["profile"]["skills"][0]["name"], "Java")
        self.assertEqual(body["profile"]["summary"], SAMPLE["summary"])
        self.assertEqual(body["profile"]["contact"]["city"], "Baku")
        self.assertEqual(body["profile"]["education"][0]["school"], "ADA")
        self.assertTrue(body["low_confidence"])
        self.assertIn("headline", body["low_confidence_fields"])
        self.assertIn("skills", body["low_confidence_fields"])

    def test_put_saves_about_education_links(self):
        self._seed_draft("person-rich")
        with self._auth("job:candidate", "person-rich"):
            saved = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={
                    "profile": {
                        "summary": "Full-stack engineer who likes clean APIs.",
                        "contact": {
                            "full_name": "Aysel",
                            "email": "aysel@example.com",
                            "phone": "",
                            "city": "Ganja",
                            "country": "AZ",
                        },
                        "links": {
                            "linkedin_url": "https://linkedin.com/in/aysel",
                            "github": "https://github.com/aysel",
                            "portfolio": "https://aysel.dev",
                        },
                        "education": [
                            {"degree": "MSc", "field": "SE", "school": "ADA", "year": 2020},
                        ],
                        "languages": [
                            {"code": "az", "level": "native"},
                            {"code": "en", "level": "C1"},
                        ],
                        "work_history": [
                            {
                                "title": "Backend Developer",
                                "company": "Acme",
                                "start": "2021-03",
                                "end": None,
                                "location": "Remote",
                                "summary": "Owned payment APIs",
                                "skills": ["Java"],
                            }
                        ],
                    },
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        profile = saved.json()["profile"]
        self.assertEqual(profile["summary"], "Full-stack engineer who likes clean APIs.")
        self.assertEqual(profile["contact"]["city"], "Ganja")
        self.assertEqual(profile["links"]["github"], "https://github.com/aysel")
        self.assertEqual(profile["education"][0]["degree"], "MSc")
        self.assertEqual(profile["languages"][0]["code"], "az")
        self.assertEqual(profile["work_history"][0]["summary"], "Owned payment APIs")
        self.assertEqual(profile["work_history"][0]["location"], "Remote")

    def test_put_edits_skills_and_logs(self):
        self._seed_draft("person-3")
        with self._auth("job:candidate", "person-3"):
            saved = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={
                    "headline": "Senior Backend Developer",
                    "seniority": "senior",
                    "total_years": 6,
                    "profile": {
                        "skills": [
                            {"name": "Java", "years": 6, "level": "advanced", "source": "user"},
                            {"name": "Kafka", "years": 3, "source": "user"},
                        ]
                    },
                },
            )
        self.assertEqual(saved.status_code, 200, saved.text)
        body = saved.json()
        self.assertEqual(body["headline"], "Senior Backend Developer")
        self.assertEqual(body["seniority"], "senior")
        self.assertEqual(body["total_years"], 6)
        self.assertEqual(body["status"], "draft")
        names = [item["name"] for item in body["profile"]["skills"]]
        self.assertEqual(names, ["Java", "Kafka"])

        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute(
                "SELECT action, before_status, after_status FROM profile_edit_log WHERE user_id = ?",
                ("person-3",),
            ).fetchone()
        self.assertIsNotNone(log)
        self.assertEqual(log["action"], "save")
        self.assertEqual(log["before_status"], "draft")
        self.assertEqual(log["after_status"], "draft")

    def test_confirm_sets_status(self):
        self._seed_draft("person-4")
        with self._auth("job:candidate", "person-4"):
            confirmed = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={"confirm": True, "headline": "Backend Developer"},
            )
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(confirmed.json()["status"], "confirmed")
        with self._auth("job:candidate", "person-4"):
            again = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(again.json()["status"], "confirmed")

        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute(
                "SELECT action, after_status FROM profile_edit_log WHERE user_id = ? ORDER BY id DESC",
                ("person-4",),
            ).fetchone()
        self.assertEqual(log["action"], "confirm")
        self.assertEqual(log["after_status"], "confirmed")

    def test_delete_clears_profile(self):
        self._seed_draft("person-clear")
        with self._auth("job:candidate", "person-clear"):
            cleared = self.client.delete("/api/v1/profile", headers=self.headers)
        self.assertEqual(cleared.status_code, 200, cleared.text)
        body = cleared.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["status"], "empty")
        with self._auth("job:candidate", "person-clear"):
            again = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertFalse(again.json()["exists"])
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            log = conn.execute(
                "SELECT action FROM profile_edit_log WHERE user_id = ? ORDER BY id DESC",
                ("person-clear",),
            ).fetchone()
        self.assertEqual(log["action"], "clear")

    def test_cancel_open_parse_keeps_profile(self):
        self._seed_draft("person-cancel")
        with sqlite3.connect(self.db) as conn:
            conn.execute(
                """
                INSERT INTO parse_cv_queue (
                    user_id, cv_file_key, cv_name, application_id, status,
                    attempts, error, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, NULL, 'pending', 0, '', ?, '', '')
                """,
                ("person-cancel", "cvs/x.pdf", "x.pdf", "2020-01-01T00:00:00+00:00"),
            )
            conn.commit()
        with self._auth("job:candidate", "person-cancel"):
            res = self.client.post("/api/v1/profile/cv/cancel", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body["exists"])
        self.assertEqual(body["parse_status"], "failed")
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT status, error FROM parse_cv_queue WHERE user_id = ? ORDER BY id DESC",
                ("person-cancel",),
            ).fetchone()
            profile = conn.execute(
                "SELECT id FROM candidate_profile WHERE user_id = ?",
                ("person-cancel",),
            ).fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertIn("cancelled", row["error"])
        self.assertIsNotNone(profile)

    def test_cancel_processing_parse(self):
        with sqlite3.connect(self.db) as conn:
            from app.cv_queue import ensure_cv_queue_tables

            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO parse_cv_queue (
                    user_id, cv_file_key, cv_name, application_id, status,
                    attempts, error, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, NULL, 'processing', 1, '', ?, ?, '')
                """,
                (
                    "person-cancel-proc",
                    "cvs/y.pdf",
                    "y.pdf",
                    "2020-01-01T00:00:00+00:00",
                    "2020-01-01T00:01:00+00:00",
                ),
            )
            conn.commit()
        with self._auth("job:candidate", "person-cancel-proc"):
            res = self.client.post("/api/v1/profile/cv/cancel", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertFalse(body["exists"])
        self.assertEqual(body["parse_status"], "failed")

    def test_employer_forbidden_and_guest_unauthorized(self):
        with self._auth("job:employer", "hr-1"):
            denied = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/profile").status_code, 401)

    def test_invalid_seniority_rejected(self):
        self._seed_draft("person-5")
        with self._auth("job:candidate", "person-5"):
            bad = self.client.put(
                "/api/v1/profile",
                headers=self.headers,
                json={"seniority": "god"},
            )
        self.assertEqual(bad.status_code, 422)

    def test_upload_cv_enqueues_parse(self):
        cvs = Path(self.tmp.name) / "cvs"
        cvs.mkdir()
        with (
            self._auth("job:candidate", "person-6"),
            patch("app.applications.CV_ROOT", cvs),
            patch("app.cv_parse_jobs.schedule_parse_cv_drain") as kick,
        ):
            res = self.client.post(
                "/api/v1/profile/cv",
                headers=self.headers,
                files={"cv": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")},
            )
        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertTrue(body.get("queued"))
        self.assertEqual(body["parse_status"], "pending")
        self.assertEqual(body["cv_name"], "resume.pdf")
        kick.assert_called_once()
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT user_id, cv_name, status, application_id FROM parse_cv_queue WHERE user_id = ?",
                ("person-6",),
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["cv_name"], "resume.pdf")
        self.assertEqual(row["status"], "pending")
        self.assertIsNone(row["application_id"])

    def test_get_pending_parse_kicks_drain(self):
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO parse_cv_queue (
                    user_id, cv_file_key, cv_name, application_id, status,
                    attempts, error, created_at, started_at, finished_at
                ) VALUES (?, ?, ?, NULL, 'pending', 0, '', ?, '', '')
                """,
                ("person-kick", "cvs/z.pdf", "z.pdf", "2020-01-01T00:00:00+00:00"),
            )
            conn.commit()
        with (
            self._auth("job:candidate", "person-kick"),
            patch("app.cv_parse_jobs.schedule_parse_cv_drain") as kick,
        ):
            res = self.client.get("/api/v1/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["parse_status"], "pending")
        kick.assert_called_once()

    def test_drain_parse_cv_queue_now_writes_profile(self):
        cvs = Path(self.tmp.name) / "cvs"
        cvs.mkdir()
        stored = "a" * 32 + ".pdf"
        (cvs / stored).write_bytes(b"%PDF-1.4 fake")
        with sqlite3.connect(self.db) as conn:
            ensure_cv_queue_tables(conn)
            conn.execute(
                """
                INSERT INTO parse_cv_queue (
                    user_id, cv_file_key, cv_name, application_id, status, attempts,
                    error, created_at, started_at, finished_at
                ) VALUES (?, ?, 'resume.pdf', NULL, 'pending', 0, '', 't', '', '')
                """,
                ("person-7", stored),
            )
            conn.commit()

        def fake_drain(conn, *, limit=20, cv_root=None):
            now = "2026-01-01T00:00:00+00:00"
            conn.execute(
                """
                UPDATE parse_cv_queue
                SET status = 'done', finished_at = ?, attempts = attempts + 1
                WHERE user_id = ? AND status = 'pending'
                """,
                (now, "person-7"),
            )
            conn.execute(
                """
                INSERT INTO candidate_profile (
                    user_id, cv_file_key, data, headline, seniority, total_years,
                    status, parse_method, confidence, visibility, updated_at
                ) VALUES (?, ?, ?, 'Backend Developer', 'middle', 5.5,
                          'draft', 'rules', 0.9, 'hidden', ?)
                """,
                ("person-7", stored, json.dumps(SAMPLE), now),
            )
            return {"claimed": 1, "done": 1, "failed": 0}

        with (
            patch("app.applications.CV_ROOT", cvs),
            patch("app.cv_parse_jobs._drain_fn", return_value=fake_drain),
        ):
            from app.cv_parse_jobs import drain_parse_cv_queue_now

            stats = drain_parse_cv_queue_now()
        self.assertEqual(stats.get("claimed"), 1)
        self.assertEqual(stats.get("done"), 1)
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            queue = conn.execute(
                "SELECT status FROM parse_cv_queue WHERE user_id = ?",
                ("person-7",),
            ).fetchone()
            profile = conn.execute(
                "SELECT headline, status FROM candidate_profile WHERE user_id = ?",
                ("person-7",),
            ).fetchone()
        self.assertEqual(queue["status"], "done")
        self.assertEqual(profile["headline"], "Backend Developer")
        self.assertEqual(profile["status"], "draft")


if __name__ == "__main__":
    unittest.main()
