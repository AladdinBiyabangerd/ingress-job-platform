"""Worker listing_language detect + Store language persist/backfill."""

import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.listing_language import listing_language


class ListingLanguageStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "jobs.sqlite"
        self.store = Store(self.db, sqlite_only=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_upsert_sets_german_language(self):
        body = (
            "Die Naturida GmbH ist ein wachsendes Unternehmen. "
            "Wir suchen eine erfahrene Product Managerin für unsere Beauty-Marke. "
            "Die Roadmap verantworten und mit Laboren steuern."
        )
        kind = self.store.upsert(
            {
                "title": "Freelance Product Manager (m/w/d)",
                "company": "Naturida",
                "city": "Berlin",
                "text": body,
                "source_name": "Arbeitnow",
                "source_url": "https://example.com/jobs/de-1",
            }
        )
        self.assertEqual(kind, "created")
        row = self.store.conn.execute(
            "SELECT language, status FROM jobs WHERE title LIKE 'Freelance%'"
        ).fetchone()
        self.assertEqual(row["language"], "de")
        self.assertEqual(row["status"], "pending")

    def test_backfill_language_rewrites_wrong_en(self):
        body = (
            "Die Naturida GmbH ist ein wachsendes Unternehmen. "
            "Wir suchen eine erfahrene Product Managerin für unsere Beauty-Marke. "
            "Fließende Deutschkenntnisse und Erfahrung mit Launch."
        )
        self.store.conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key, language
            )
            VALUES (?, 'Naturida', 'Berlin', ?, 'published', ?, ?, 'en')
            """,
            (
                "Freelance Product Manager (m/w/d)",
                body,
                "2026-10-11T09:00:00+00:00",
                "backfill-de-en",
            ),
        )
        self.store.conn.commit()
        self.assertEqual(listing_language("Freelance Product Manager (m/w/d)", body), "de")
        updated = self.store.backfill_language(limit=100)
        self.assertGreaterEqual(updated, 1)
        row = self.store.conn.execute(
            "SELECT language FROM jobs WHERE norm_key = ?",
            ("backfill-de-en",),
        ).fetchone()
        self.assertEqual(row["language"], "de")

    def test_backfill_skips_cabinet_az(self):
        self.store.conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                language, owner_subject
            )
            VALUES (?, 'Acme', 'Baku', ?, 'published', ?, ?, 'az', 'owner@example.com')
            """,
            (
                "Engineer",
                "We need Python experience for this English body.",
                "2026-10-11T09:00:00+00:00",
                "cabinet-az",
            ),
        )
        self.store.conn.commit()
        updated = self.store.backfill_language(limit=100)
        self.assertEqual(updated, 0)
        row = self.store.conn.execute(
            "SELECT language FROM jobs WHERE norm_key = ?",
            ("cabinet-az",),
        ).fetchone()
        self.assertEqual(row["language"], "az")


if __name__ == "__main__":
    unittest.main()
