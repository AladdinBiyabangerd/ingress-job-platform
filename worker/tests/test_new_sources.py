"""Jobgether + RemoteYeah connectors and ATS slug expansion invariants."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from worker.ats_boards import GROUPS
from worker.connectors.apis import JobgetherConnector
from worker.connectors.ats import RecruiteeConnector, WorkableConnector
from worker.connectors.rssboards import RemoteYeahConnector
from worker.techstack import az_market_relevant, is_tech_job


class JobgetherConnectorTest(unittest.TestCase):
    def test_maps_remote_it_and_skips_empty(self):
        client = MagicMock()
        client.get_json.side_effect = [
            {
                "jobs": [
                    {
                        "id": "1",
                        "title": "C# Developer",
                        "company": "Acme",
                        "url": "https://jobgether.com/offer/1-csharp-developer",
                        "location": "EMEA",
                        "remote": "Full Remote",
                        "jobFunctions": ["C# Developer"],
                        "postedAt": "2026-10-10T00:00:00Z",
                    },
                    {
                        "id": "2",
                        "title": "Content Writer",
                        "company": "UpGuard",
                        "url": "https://jobgether.com/offer/2-content-writer",
                        "location": "Africa, South Africa",
                        "remote": "Full Remote",
                        "jobFunctions": ["Content Writer"],
                    },
                ],
                "pagination": {"page": 1, "hasMore": False},
            }
        ]
        conn = JobgetherConnector(client, MagicMock())
        items = conn.feed_items()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "C# Developer")
        self.assertEqual(items[0]["city"], "Remote (EMEA)")
        self.assertTrue(items[0]["remote"])
        self.assertTrue(is_tech_job(items[0]["title"], items[0]["category"], items[0]["tags"]))
        self.assertFalse(is_tech_job(items[1]["title"], items[1]["category"], items[1]["tags"]))

    def test_stops_when_no_more_pages(self):
        client = MagicMock()
        client.get_json.return_value = {"jobs": [], "pagination": {"hasMore": False}}
        conn = JobgetherConnector(client, MagicMock())
        self.assertEqual(conn.feed_items(), [])
        client.get_json.assert_called_once()


class RemoteYeahConnectorTest(unittest.TestCase):
    def test_parses_title_company_and_location(self):
        rss = """<?xml version="1.0"?>
        <rss><channel>
        <item>
          <title> Remote Backend Engineer at Acme Corp </title>
          <company> Acme Corp </company>
          <link>https://remoteyeah.com/jobs/backend-acme</link>
          <description><![CDATA[
            <ul><li>Locations: United States (Remote)</li></ul>
            <h2>Description:</h2><p>Build APIs with Python.</p>
          ]]></description>
        </item>
        </channel></rss>"""
        client = MagicMock()
        client.get_text.return_value = rss
        conn = RemoteYeahConnector(client, MagicMock())
        items = conn.feed_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Remote Backend Engineer")
        self.assertEqual(items[0]["company"], "Acme Corp")
        self.assertEqual(items[0]["city"], "United States (Remote)")
        self.assertTrue(items[0]["remote"])
        self.assertTrue(is_tech_job(items[0]["title"]))


class RemoteYeahTitleSplitTest(unittest.TestCase):
    def _items(self, title, company=None):
        co = f"<company>{company}</company>" if company else ""
        rss = f"""<?xml version="1.0"?><rss><channel><item><title>{title}</title>{co}
        <link>https://remoteyeah.com/jobs/x</link><description>Locations: Remote</description>
        </item></channel></rss>"""
        client = MagicMock()
        client.get_text.return_value = rss
        return RemoteYeahConnector(client, MagicMock()).feed_items()

    def test_multiple_at_with_company_field(self):
        it = self._items("Engineer at Scale at Acme", "Acme")[0]
        self.assertEqual((it["title"], it["company"]), ("Engineer at Scale", "Acme"))

    def test_multiple_at_without_company_field_splits_on_last(self):
        it = self._items("Engineer at Scale at Acme")[0]
        self.assertEqual((it["title"], it["company"]), ("Engineer at Scale", "Acme"))

    def test_company_suffix_must_follow_at(self):
        it = self._items("Engineer at Acme", "me")[0]
        self.assertEqual(it["company"], "me")
        self.assertEqual(it["title"], "Engineer")

    def test_no_at_keeps_title(self):
        it = self._items("Backend Engineer", "Acme")[0]
        self.assertEqual((it["title"], it["company"]), ("Backend Engineer", "Acme"))


class JobgetherDetailCapTest(unittest.TestCase):
    def test_candidates_capped_and_remote_first(self):
        self.assertLessEqual(JobgetherConnector.candidates, 30)
        jobs = [
            {"id": str(i), "title": "Backend Developer", "company": "C",
             "url": f"https://jobgether.com/offer/{i}", "location": "US",
             "remote": "Full Remote" if i % 2 else "On-site", "jobFunctions": ["Developer"]}
            for i in range(1, 101)
        ]
        client = MagicMock()
        client.get_json.return_value = {"jobs": jobs, "pagination": {"hasMore": False}}
        client.allowed.return_value = True
        store = MagicMock()
        store.has_source_url.return_value = False
        conn = JobgetherConnector(client, store)
        urls = conn.discover()
        self.assertEqual(len(urls), JobgetherConnector.candidates)
        self.assertTrue(all(conn._items[u]["remote"] is True for u in urls))

    def test_detail_pages_only_for_discovered(self):
        client = MagicMock()
        client.get_json.return_value = {"jobs": [
            {"id": "1", "title": "Backend Developer", "company": "C", "url": "https://jobgether.com/offer/1",
             "location": "US", "remote": "Full Remote", "jobFunctions": ["Developer"]}
            for _ in range(1)] + [
            {"id": "2", "title": "Content Writer", "company": "C", "url": "https://jobgether.com/offer/2",
             "location": "US", "remote": "Full Remote", "jobFunctions": ["Writer"]}],
            "pagination": {"hasMore": False}}
        client.allowed.return_value = True
        client.get_text.return_value = "<html></html>"
        store = MagicMock()
        store.has_source_url.return_value = False
        conn = JobgetherConnector(client, store)
        for u in conn.discover():
            conn.fetch(u)
        self.assertEqual(client.get_text.call_count, 1)


class AtsExpansionTest(unittest.TestCase):
    def test_new_greenhouse_slugs_present(self):
        by_name = {name: boards for name, _ats, _region, boards in GROUPS}
        self.assertIn("traderepublicbank", by_name["Greenhouse boards (DACH)"])
        self.assertIn("transfergo", by_name["Greenhouse boards (Southern & Eastern Europe)"])
        self.assertIn("robinhood", by_name["Greenhouse boards (US West)"])
        self.assertIn("jetbrains", by_name["Greenhouse boards (Southern & Eastern Europe)"])
        self.assertIn("lucidsoftware", by_name["Greenhouse boards (Canada)"])
        # 2026-10-10 second expansion (robots-clean probe)
        self.assertIn("form3", by_name["Greenhouse boards (UK & Ireland)"])
        self.assertIn("nix", by_name["Greenhouse boards (Southern & Eastern Europe)"])
        self.assertIn("bloomreach", by_name["Greenhouse boards (Southern & Eastern Europe)"])
        self.assertIn("togetherai", by_name["Greenhouse boards (US West)"])
        self.assertIn("braze", by_name["Greenhouse boards (US East)"])
        self.assertIn("leagueinc", by_name["Greenhouse boards (Canada)"])
        self.assertIn("cred", by_name["Lever boards (India)"])
        self.assertIn("bambuser", by_name["Teamtailor boards (Nordics)"])

    def test_workable_and_recruitee_boards_expanded(self):
        self.assertIn("mercari", WorkableConnector.boards)
        self.assertIn("huggingface", WorkableConnector.boards)
        self.assertIn("1password", WorkableConnector.boards)
        self.assertIn("peoplecert", WorkableConnector.boards)
        self.assertIn("orfium", WorkableConnector.boards)
        self.assertIn("effectory", RecruiteeConnector.boards)
        self.assertIn("mailerlite", RecruiteeConnector.boards)
        self.assertIn("adjust", RecruiteeConnector.boards)


class RuleGapSamplesTest(unittest.TestCase):
    def test_worldwide_remote_kept(self):
        self.assertTrue(
            az_market_relevant(
                "Software Engineer",
                "Worldwide",
                "Fully remote worldwide. Stack: Python.",
                remote=True,
                relocation=False,
            )
        )

    def test_jobgether_africa_south_africa_remote_rejected(self):
        self.assertFalse(
            az_market_relevant(
                "C# Developer",
                "Africa, Sub-Saharan Africa, EMEA, South Africa",
                "Full remote for candidates in South Africa.",
                remote=True,
                relocation=False,
            )
        )

    def test_remoteyeah_us_only_remote_rejected(self):
        self.assertFalse(
            az_market_relevant(
                "Remote Backend Engineer",
                "United States (Remote)",
                "Must be located in the United States.",
                remote=True,
                relocation=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
