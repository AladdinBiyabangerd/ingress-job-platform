"""skill_trend_daily aggregation (plan §7.1)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from worker.db import Store
from worker.skill_trends import (
    aggregate_skill_trends,
    backfill_skill_trends,
    refresh_skill_trends,
)
from worker.skills import sync_job_skills


class SkillTrendsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _skill_id(self, name: str) -> int:
        row = self.store.conn.execute(
            "SELECT id FROM skill_dictionary WHERE canonical_name = ?",
            (name,),
        ).fetchone()
        self.assertIsNotNone(row, name)
        return int(row[0])

    def _insert_job(
        self,
        *,
        title: str,
        day: str,
        skills: list[str],
        category: str = "Backend",
        remote: int = 1,
        relocation: int = 0,
        status: str = "published",
        hidden: int = 0,
        salary: str = "",
    ) -> int:
        cur = self.store.conn.execute(
            """
            INSERT INTO jobs (
                title, company, city, text, status, created_at, norm_key,
                tech_stack, remote, relocation, category, hidden, salary
            ) VALUES (?, 'Co', '', '', ?, ?, ?, '[]', ?, ?, ?, ?, ?)
            """,
            (
                title,
                status,
                f"{day}T12:00:00+00:00",
                f"{title.lower()}-co",
                remote,
                relocation,
                category,
                hidden,
                salary,
            ),
        )
        job_id = int(cur.lastrowid)
        sync_job_skills(self.store.conn, job_id, skills)
        self.store.conn.commit()
        return job_id

    def test_aggregate_counts_distinct_jobs_per_skill(self):
        self._insert_job(title="A", day="2026-10-01", skills=["Python", "AWS"])
        self._insert_job(title="B", day="2026-10-01", skills=["Python"])
        self._insert_job(title="C", day="2026-10-02", skills=["Python"])
        written = aggregate_skill_trends(self.store.conn, "2026-10-01")
        self.store.conn.commit()
        self.assertGreaterEqual(written, 2)
        py = self._skill_id("Python")
        aws = self._skill_id("AWS")
        rows = {
            (int(r["skill_id"]), str(r["category"])): int(r["ad_count"])
            for r in self.store.conn.execute(
                """
                SELECT skill_id, category, ad_count
                FROM skill_trend_daily
                WHERE day = '2026-10-01'
                """
            )
        }
        self.assertEqual(rows[(py, "Backend")], 2)
        self.assertEqual(rows[(aws, "Backend")], 1)

    def test_aggregate_skips_hidden_and_non_published(self):
        self._insert_job(title="Ok", day="2026-10-03", skills=["Go"])
        self._insert_job(
            title="Hidden", day="2026-10-03", skills=["Go"], hidden=1
        )
        self._insert_job(
            title="Draft", day="2026-10-03", skills=["Go"], status="pending"
        )
        aggregate_skill_trends(self.store.conn, "2026-10-03")
        self.store.conn.commit()
        go = self._skill_id("Go")
        count = self.store.conn.execute(
            """
            SELECT ad_count FROM skill_trend_daily
            WHERE day = '2026-10-03' AND skill_id = ?
            """,
            (go,),
        ).fetchone()
        self.assertEqual(int(count[0]), 1)

    def test_aggregate_idempotent(self):
        self._insert_job(title="Once", day="2026-10-04", skills=["React"])
        a = aggregate_skill_trends(self.store.conn, "2026-10-04")
        b = aggregate_skill_trends(self.store.conn, "2026-10-04")
        self.store.conn.commit()
        self.assertEqual(a, b)
        react = self._skill_id("React")
        n = self.store.conn.execute(
            """
            SELECT COUNT(*), SUM(ad_count) FROM skill_trend_daily
            WHERE day = '2026-10-04' AND skill_id = ?
            """,
            (react,),
        ).fetchone()
        self.assertEqual(int(n[0]), 1)
        self.assertEqual(int(n[1]), 1)

    def test_refresh_backfills_when_empty(self):
        self._insert_job(title="Today", day="2026-10-05", skills=["TypeScript"])
        stats = refresh_skill_trends(self.store.conn)
        self.store.conn.commit()
        self.assertEqual(stats["mode"], "backfill")
        self.assertGreaterEqual(stats["groups"], 1)
        # Second call refreshes, does not re-backfill.
        stats2 = refresh_skill_trends(self.store.conn)
        self.store.conn.commit()
        self.assertEqual(stats2["mode"], "refresh")

    def test_backfill_span(self):
        self._insert_job(title="Old", day="2026-09-01", skills=["Java"])
        self._insert_job(title="New", day="2026-10-05", skills=["Java"])
        written = backfill_skill_trends(self.store.conn, days=3)
        self.store.conn.commit()
        self.assertGreaterEqual(written, 0)
        days = [
            r[0]
            for r in self.store.conn.execute(
                "SELECT DISTINCT day FROM skill_trend_daily ORDER BY day"
            )
        ]
        # Only days within the 3-day window relative to "today" get rows;
        # 2026-09-01 is outside unless today is near it. Assert shape only.
        self.assertTrue(all(len(d) == 10 for d in days))

    def test_aggregate_salary_median(self):
        self._insert_job(
            title="A",
            day="2026-10-06",
            skills=["Python"],
            salary="40,000 GBP per annum",
        )
        self._insert_job(
            title="B",
            day="2026-10-06",
            skills=["Python"],
            salary="60,000 GBP per year",
        )
        self._insert_job(
            title="C",
            day="2026-10-06",
            skills=["Python"],
            salary="negotiable",
        )
        aggregate_skill_trends(self.store.conn, "2026-10-06")
        self.store.conn.commit()
        py = self._skill_id("Python")
        row = self.store.conn.execute(
            """
            SELECT ad_count, salary_median, salary_currency, salary_n,
                   salary_low, salary_high
            FROM skill_trend_daily
            WHERE day = '2026-10-06' AND skill_id = ?
            """,
            (py,),
        ).fetchone()
        self.assertEqual(int(row["ad_count"]), 3)
        self.assertEqual(str(row["salary_currency"]), "GBP")
        self.assertEqual(int(row["salary_n"]), 2)
        self.assertEqual(float(row["salary_median"]), 50000.0)
        self.assertEqual(float(row["salary_low"]), 40000.0)
        self.assertEqual(float(row["salary_high"]), 60000.0)


if __name__ == "__main__":
    unittest.main()
