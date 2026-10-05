"""Jooble connector with a mocked API: parsing, tech filter, request budget,
and the key never showing up in errors. No network."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from worker.connectors.jooble import SHOWN, JoobleConnector, month_period
from worker.db import Store
from worker.http import SourceFailed
from worker.runner import finish_item

KEY = "test-key-123"

ANSWER = {
    "totalCount": 3,
    "jobs": [
        {
            "title": "Senior Python Developer (Remote)",
            "location": "Remote",
            "snippet": "&nbsp;...Build APIs with <b>Python</b>, Django and PostgreSQL on AWS. Visa sponsorship...",
            "salary": "$120k",
            "source": "example.com",
            "type": "Full-time",
            "link": "https://jooble.org/jdp/111",
            "company": "Acme",
            "updated": "2026-10-04T10:00:00.0000000",
            "id": 111,
        },
        {
            "title": "Sales Manager",
            "location": "Berlin",
            "snippet": "Sell things.",
            "link": "https://jooble.org/jdp/222",
            "company": "Shop",
            "id": 222,
        },
        {
            "title": "DevOps Engineer",
            "location": "Amsterdam",
            "snippet": "Kubernetes, Terraform.",
            "link": "https://jooble.org/jdp/333",
            "company": "Ops BV",
            "id": 333,
        },
    ],
}


class FakeClient:
    def __init__(self, answer=None, error=None):
        self.calls: list[tuple[str, dict, str]] = []
        self.answer = answer if answer is not None else ANSWER
        self.error = error

    def post_json(self, url, payload, *, shown=None):
        self.calls.append((url, payload, shown))
        if self.error:
            raise self.error
        return self.answer


class JoobleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        env = {"JOOBLE_API_KEY": KEY}
        self.env = mock.patch.dict(os.environ, env, clear=False)
        self.env.start()
        for name in ("JOOBLE_MONTHLY_BUDGET", "JOOBLE_MAX_QUERIES"):
            os.environ.pop(name, None)

    def tearDown(self):
        self.env.stop()
        self.store.close()
        self.tmp.cleanup()

    def test_parses_tech_only_and_counts_requests(self):
        client = FakeClient()
        conn = JoobleConnector(client, self.store)
        urls = conn.discover()
        self.assertEqual(len(client.calls), 3)  # three queries, page 1 only
        self.assertTrue(all(c[1]["page"] == "1" for c in client.calls))
        self.assertTrue(all(c[0].endswith(KEY) and c[2] == SHOWN for c in client.calls))
        self.assertEqual(urls, ["https://jooble.org/jdp/111", "https://jooble.org/jdp/333"])
        self.assertEqual(self.store.api_requests_used("Jooble", month_period()), 3)

        item = finish_item(conn, conn.normalize(conn.fetch(urls[0]), urls[0]))
        self.assertEqual(item["title"], "Senior Python Developer (Remote)")
        self.assertEqual(item["company"], "Acme")
        self.assertEqual(item["source_url"], "https://jooble.org/jdp/111")
        self.assertEqual(item["external_id"], "jooble-111")
        self.assertTrue(item["remote"])
        self.assertIn("Python", item["tech_stack"])
        self.assertEqual(item["job_category"], "Backend")
        self.assertIn("Jooble", item["credit_note"])

    def test_budget_stops_requests(self):
        self.store.add_api_requests("Jooble", month_period(), 449)
        client = FakeClient()
        JoobleConnector(client, self.store).discover()
        self.assertEqual(len(client.calls), 1)  # one left before 450
        self.assertEqual(self.store.api_requests_used("Jooble", month_period()), 450)
        client2 = FakeClient()
        self.assertEqual(JoobleConnector(client2, self.store).discover(), [])
        self.assertEqual(client2.calls, [])

    def test_budget_and_query_overrides(self):
        os.environ["JOOBLE_MAX_QUERIES"] = "1"
        os.environ["JOOBLE_MONTHLY_BUDGET"] = "9999"  # capped at the key's 500
        conn = JoobleConnector(FakeClient(), self.store)
        self.assertEqual(conn.budget, 500)
        conn.discover()
        self.assertEqual(len(conn.client.calls), 1)

    def test_missing_key_sends_nothing(self):
        os.environ.pop("JOOBLE_API_KEY")
        client = FakeClient()
        with self.assertRaises(SourceFailed):
            JoobleConnector(client, self.store).discover()
        self.assertEqual(client.calls, [])

    def test_key_not_in_errors(self):
        client = FakeClient(answer={"unexpected": True})
        with self.assertRaises(SourceFailed) as ctx:
            JoobleConnector(client, self.store).discover()
        self.assertNotIn(KEY, str(ctx.exception))
        stored = json.dumps([dict(r) for r in self.store.conn.execute("SELECT * FROM api_usage")])
        self.assertNotIn(KEY, stored)


if __name__ == "__main__":
    unittest.main()
