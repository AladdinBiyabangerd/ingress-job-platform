"""parse_cv_queue drain + candidate_profile stub (Phase 1.2)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.cv_queue import (
    ENQUEUE_EXISTING_STEP,
    drain_parse_cv_queue,
    enqueue_existing_application_cvs,
    enqueue_parse,
    ensure_cv_queue_tables,
)
from worker.db import Store

FIXTURES = Path(__file__).parent / "fixtures" / "cv"


class CvQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cvs = self.root / "cvs"
        self.cvs.mkdir()
        self.store = Store(self.root / "t.sqlite", sqlite_only=True)
        ensure_cv_queue_tables(self.store.conn)
        self.store.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                id INTEGER PRIMARY KEY,
                job_id INTEGER NOT NULL,
                candidate_subject TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                cv_name TEXT NOT NULL DEFAULT '',
                cv_stored TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'submitted',
                decision_reason TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                answers TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        self.store.conn.commit()

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _write_sample_cv(self) -> str:
        from docx import Document

        stored = "b" * 32 + ".docx"
        doc = Document()
        for line in (FIXTURES / "sample_backend.txt").read_text(encoding="utf-8").splitlines():
            doc.add_paragraph(line)
        doc.save(self.cvs / stored)
        return stored

    def test_drain_writes_candidate_profile(self):
        stored = self._write_sample_cv()
        queue_id = enqueue_parse(
            self.store.conn,
            user_id="cand-1",
            cv_file_key=stored,
            cv_name="cv.docx",
            application_id=7,
        )
        self.store.conn.commit()
        self.assertIsNotNone(queue_id)

        stats = drain_parse_cv_queue(self.store.conn, cv_root=self.cvs)
        self.store.conn.commit()
        self.assertEqual(stats["claimed"], 1)
        self.assertEqual(stats["done"], 1)

        row = self.store.conn.execute(
            "SELECT status, error FROM parse_cv_queue WHERE id = ?",
            (queue_id,),
        ).fetchone()
        self.assertEqual(row["status"], "done")

        profile = self.store.conn.execute(
            """
            SELECT user_id, cv_file_key, headline, seniority, total_years,
                   status, parse_method, confidence, visibility, data
            FROM candidate_profile WHERE user_id = ?
            """,
            ("cand-1",),
        ).fetchone()
        self.assertIsNotNone(profile)
        self.assertEqual(profile["cv_file_key"], stored)
        self.assertEqual(profile["status"], "draft")
        self.assertEqual(profile["visibility"], "hidden")
        self.assertEqual(profile["parse_method"], "rules")
        self.assertGreaterEqual(float(profile["confidence"] or 0), 0.6)
        self.assertGreaterEqual(float(profile["total_years"] or 0), 5.0)
        data = json.loads(profile["data"])
        names = {item["name"] for item in data["skills"]}
        self.assertIn("Java", names)
        self.assertEqual(data["contact"]["email"], "aysel.mammadli@example.com")

    def test_enqueue_skips_duplicate_open_job(self):
        stored = "c" * 32 + ".pdf"
        first = enqueue_parse(
            self.store.conn, user_id="cand-2", cv_file_key=stored, cv_name="a.pdf"
        )
        second = enqueue_parse(
            self.store.conn, user_id="cand-2", cv_file_key=stored, cv_name="a.pdf"
        )
        self.assertEqual(first, second)
        count = self.store.conn.execute(
            "SELECT COUNT(*) FROM parse_cv_queue WHERE user_id = ?",
            ("cand-2",),
        ).fetchone()[0]
        self.assertEqual(int(count), 1)

    def test_enqueue_existing_application_cvs_once(self):
        stored = "d" * 32 + ".pdf"
        self.store.conn.execute(
            """
            INSERT INTO applications (
                job_id, candidate_subject, message, cv_name, cv_stored, created_at
            ) VALUES (1, 'cand-3', '', 'old.pdf', ?, '2026-10-05T12:00:00+04:00')
            """,
            (stored,),
        )
        self.store.conn.commit()
        # Clear any maintenance mark from Store init (no applications then).
        self.store.conn.execute(
            "DELETE FROM maintenance_steps WHERE name = ?",
            (ENQUEUE_EXISTING_STEP,),
        )
        self.store.conn.commit()

        queued = enqueue_existing_application_cvs(self.store.conn)
        self.store.conn.commit()
        self.assertEqual(queued, 1)
        again = enqueue_existing_application_cvs(self.store.conn)
        self.assertEqual(again, 0)
        row = self.store.conn.execute(
            """
            SELECT user_id, cv_file_key, status, application_id
            FROM parse_cv_queue WHERE user_id = ?
            """,
            ("cand-3",),
        ).fetchone()
        self.assertEqual(row["cv_file_key"], stored)
        self.assertEqual(row["status"], "pending")
        self.assertEqual(int(row["application_id"]), 1)

    def test_missing_cv_marks_failed(self):
        stored = "e" * 32 + ".pdf"
        queue_id = enqueue_parse(
            self.store.conn, user_id="cand-4", cv_file_key=stored, cv_name="missing.pdf"
        )
        self.store.conn.commit()
        stats = drain_parse_cv_queue(self.store.conn, cv_root=self.cvs)
        self.store.conn.commit()
        self.assertEqual(stats["failed"], 1)
        row = self.store.conn.execute(
            "SELECT status, error FROM parse_cv_queue WHERE id = ?",
            (queue_id,),
        ).fetchone()
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error"], "cv_missing")

    def test_confirmed_profile_not_overwritten(self):
        stored = self._write_sample_cv()
        self.store.conn.execute(
            """
            INSERT INTO candidate_profile (
                user_id, cv_file_key, data, headline, seniority, total_years,
                status, parse_method, confidence, visibility, updated_at
            ) VALUES (
                'cand-5', 'old.pdf', '{}', 'Keep Me', 'senior', 10,
                'confirmed', 'rules', 0.9, 'anonymous', '2026-10-05T12:00:00+04:00'
            )
            """
        )
        enqueue_parse(
            self.store.conn, user_id="cand-5", cv_file_key=stored, cv_name="cv.docx"
        )
        self.store.conn.commit()
        drain_parse_cv_queue(self.store.conn, cv_root=self.cvs)
        self.store.conn.commit()
        row = self.store.conn.execute(
            "SELECT headline, status, cv_file_key FROM candidate_profile WHERE user_id = ?",
            ("cand-5",),
        ).fetchone()
        self.assertEqual(row["headline"], "Keep Me")
        self.assertEqual(row["status"], "confirmed")
        self.assertEqual(row["cv_file_key"], "old.pdf")

    def test_slow_ai_does_not_block_queue_done(self):
        """Rules finish the job even when AI enhancement hangs / fails."""
        stored = self._write_sample_cv()
        queue_id = enqueue_parse(
            self.store.conn,
            user_id="cand-ai-slow",
            cv_file_key=stored,
            cv_name="cv.docx",
        )
        self.store.conn.commit()

        def hang(*_a, **_k):
            raise TimeoutError("provider_stuck")

        with patch("worker.cv_parse.ai_fallback.maybe_ai_fallback", side_effect=hang):
            stats = drain_parse_cv_queue(self.store.conn, cv_root=self.cvs)
        self.store.conn.commit()
        self.assertEqual(stats["done"], 1)
        row = self.store.conn.execute(
            "SELECT status FROM parse_cv_queue WHERE id = ?",
            (queue_id,),
        ).fetchone()
        self.assertEqual(row["status"], "done")
        profile = self.store.conn.execute(
            "SELECT status, parse_method, headline FROM candidate_profile WHERE user_id = ?",
            ("cand-ai-slow",),
        ).fetchone()
        self.assertEqual(profile["status"], "draft")
        self.assertEqual(profile["parse_method"], "rules")
        self.assertTrue(profile["headline"])

    def test_stale_processing_is_reclaimed_and_done(self):
        stored = self._write_sample_cv()
        self.store.conn.execute(
            """
            INSERT INTO parse_cv_queue (
                user_id, cv_file_key, cv_name, application_id, status, attempts,
                error, created_at, started_at, finished_at
            ) VALUES (
                'cand-stale', ?, 'cv.docx', NULL, 'processing', 1,
                '', '2020-01-01T00:00:00+00:00', '2020-01-01T00:00:00+00:00', ''
            )
            """,
            (stored,),
        )
        self.store.conn.commit()
        stats = drain_parse_cv_queue(self.store.conn, cv_root=self.cvs)
        self.store.conn.commit()
        self.assertEqual(stats["done"], 1)
        row = self.store.conn.execute(
            "SELECT status FROM parse_cv_queue WHERE user_id = 'cand-stale'"
        ).fetchone()
        self.assertEqual(row["status"], "done")
        profile = self.store.conn.execute(
            "SELECT headline FROM candidate_profile WHERE user_id = 'cand-stale'"
        ).fetchone()
        self.assertTrue(profile["headline"])


class RowcountHelperTests(unittest.TestCase):
    def test_missing_rowcount_counts_as_affected(self):
        from worker.cv_queue import _rowcount

        class Bare:
            pass

        self.assertEqual(_rowcount(Bare()), 1)
        self.assertEqual(_rowcount(type("C", (), {"rowcount": 0})()), 0)
        self.assertEqual(_rowcount(type("C", (), {"rowcount": 1})()), 1)


if __name__ == "__main__":
    unittest.main()
