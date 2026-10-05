"""Reed.co.uk connector with a mocked API: robots refusal, parsing, details
for new ads only, salary in GBP, request budget, key never in URLs/errors."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from worker.connectors.reed import ReedConnector, month_period, salary_text
from worker.db import Store
from worker.http import SourceBlocked, SourceFailed
from worker.runner import finish_item

KEY = "reed-test-key-456"

SEARCH = {
    "results": [
        {
            "jobId": 101, "employerId": 9, "employerName": "Acme Ltd",
            "jobTitle": "Senior Python Developer", "locationName": "Remote",
            "minimumSalary": 60000.0, "maximumSalary": 75000.0, "currency": "GBP",
            "date": "04/10/2026", "jobDescription": "Python and AWS... ",
            "applications": 12, "jobUrl": "https://www.reed.co.uk/jobs/senior-python-developer/101",
        },
        {
            "jobId": 102, "employerName": "Shop", "jobTitle": "Store Manager",
            "locationName": "Leeds", "jobUrl": "https://www.reed.co.uk/jobs/store-manager/102",
        },
        {
            "jobId": 103, "employerName": "Ops Co", "jobTitle": "DevOps Engineer",
            "locationName": "Manchester", "jobDescription": "Kubernetes",
            "jobUrl": "https://www.reed.co.uk/jobs/devops-engineer/103",
        },
    ],
    "totalResults": 3,
}

DETAIL = {
    101: {
        "jobId": 101, "employerName": "Acme Ltd", "jobTitle": "Senior Python Developer",
        "locationName": "Remote", "minimumSalary": 60000.0, "maximumSalary": 75000.0,
        "yearlyMinimumSalary": 60000.0, "yearlyMaximumSalary": 75000.0, "currency": "GBP",
        "salaryType": "per annum", "contractType": "Permanent", "jobType": "Full Time",
        "jobDescription": "<p>Build APIs with <b>Python</b>, Django and PostgreSQL on AWS. "
                          "Fully remote within the UK.</p>" * 3,
        "externalUrl": "https://acme.example/jobs/1",
        "jobUrl": "https://www.reed.co.uk/jobs/senior-python-developer/101",
        "applicationCount": 12,
    },
    103: {"jobId": 103, "jobDescription": "<p>Terraform, Kubernetes, AWS.</p>", "salaryType": "per day",
          "minimumSalary": 500.0, "maximumSalary": 550.0, "currency": "GBP"},
}


class FakeClient:
    def __init__(self, robots_ok=True):
        self.robots_ok = robots_ok
        self.calls: list[tuple[str, tuple, str]] = []

    def allowed(self, url):
        return self.robots_ok

    def get_json(self, url, *, auth=None, shown=None):
        self.calls.append((url, auth, shown))
        if "/search?" in url:
            return SEARCH
        job_id = int(url.rsplit("/", 1)[1])
        return DETAIL.get(job_id, {})


class ReedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        self.env = mock.patch.dict(os.environ, {"REED_API_KEY": KEY}, clear=False)
        self.env.start()
        for name in ("REED_MONTHLY_BUDGET", "REED_MAX_QUERIES"):
            os.environ.pop(name, None)

    def tearDown(self):
        self.env.stop()
        self.store.close()
        self.tmp.cleanup()

    def test_robots_refusal_sends_nothing(self):
        client = FakeClient(robots_ok=False)
        with self.assertRaises(SourceBlocked):
            ReedConnector(client, self.store).discover()
        self.assertEqual(client.calls, [])
        self.assertEqual(self.store.api_requests_used("Reed.co.uk", month_period()), 0)

    def test_search_details_and_store(self):
        client = FakeClient()
        conn = ReedConnector(client, self.store)
        urls = conn.discover()
        searches = [c for c in client.calls if "/search?" in c[0]]
        self.assertEqual(len(searches), 5)
        self.assertTrue(all("resultsToTake=50" in c[0] for c in searches))
        self.assertTrue(all(c[1] == (KEY, "") for c in client.calls))   # Basic auth, empty password
        self.assertTrue(all(KEY not in c[0] and KEY not in c[2] for c in client.calls))
        # Tech only, de-duplicated across searches, remote first.
        self.assertEqual(urls, [
            "https://www.reed.co.uk/jobs/senior-python-developer/101",
            "https://www.reed.co.uk/jobs/devops-engineer/103",
        ])

        item = finish_item(conn, conn.normalize(conn.fetch(urls[0]), urls[0]))
        self.assertEqual(len(client.calls), 6)  # one details call for this new ad
        self.assertEqual(item["company"], "Acme Ltd")
        self.assertEqual(item["salary"], "60,000–75,000 GBP per annum")
        self.assertTrue(item["remote"])
        self.assertIn("Python", item["tech_stack"])
        self.assertIn("Permanent", item["text"])
        self.assertNotIn("applications", item)
        self.assertEqual(self.store.upsert(item), "created")
        row = self.store.conn.execute(
            "SELECT j.salary, s.source_url FROM jobs j JOIN job_sources s ON s.job_id = j.id"
        ).fetchone()
        self.assertEqual(row["salary"], "60,000–75,000 GBP per annum")
        self.assertEqual(row["source_url"], urls[0])
        self.assertEqual(self.store.api_requests_used("Reed.co.uk", month_period()), 6)

        # Next pass: the stored ad gets no details call.
        client2 = FakeClient()
        urls2 = ReedConnector(client2, self.store).discover()
        self.assertEqual(urls2, ["https://www.reed.co.uk/jobs/devops-engineer/103"])

    def test_budget_caps_searches_and_details(self):
        os.environ["REED_MONTHLY_BUDGET"] = "6"
        self.store.add_api_requests("Reed.co.uk", month_period(), 4)
        client = FakeClient()
        urls = ReedConnector(client, self.store).discover()
        self.assertEqual(len(client.calls), 2)  # two searches, then the cap
        self.assertEqual(urls, [])               # nothing left for details
        client2 = FakeClient()
        ReedConnector(client2, self.store).discover()
        self.assertEqual(client2.calls, [])

    def test_missing_key(self):
        os.environ.pop("REED_API_KEY")
        client = FakeClient()
        with self.assertRaises(SourceFailed) as ctx:
            ReedConnector(client, self.store).discover()
        self.assertEqual(client.calls, [])
        self.assertIn("REED_API_KEY", str(ctx.exception))

    def test_salary_text(self):
        self.assertEqual(salary_text(45000, 55000), "45,000–55,000 GBP")
        self.assertEqual(salary_text(500, 500, "GBP", "per day"), "500 GBP per day")
        self.assertEqual(salary_text(None, None), "")


if __name__ == "__main__":
    unittest.main()
