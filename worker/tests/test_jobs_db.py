"""SQL translation for the worker Postgres jobs database. No database is contacted."""

import unittest

from worker.jobs_db import _wants_returning


class WantsReturningTest(unittest.TestCase):
    def test_crawl_rejects_skips_returning_id(self):
        self.assertFalse(
            _wants_returning(
                "INSERT INTO crawl_rejects (source_url, reason, decided_at, via_ai) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(source_url) DO UPDATE SET "
                "reason = excluded.reason"
            )
        )
        self.assertTrue(_wants_returning("INSERT INTO jobs (title) VALUES (?)"))


if __name__ == "__main__":
    unittest.main()
