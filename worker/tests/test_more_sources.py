"""DevITjobs UK, The Muse and Remote First Jobs RSS connectors."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from worker.connectors.apis import DevITjobsUkConnector, TheMuseConnector
from worker.connectors.rssboards import RemoteFirstJobsRssConnector
from worker.techstack import is_tech_job


def _store(known: set[str] | None = None):
    store = MagicMock()
    store.conn = None
    store.has_source_url.side_effect = lambda u: u in (known or set())
    return store


class DevITjobsTest(unittest.TestCase):
    JOBS = [
        {"_id": "1", "jobUrl": "Acme-Remote-Python-Dev", "name": "Python Developer", "company": "Acme",
         "workplace": "remote", "hasVisaSponsorship": "No", "actualCity": "leeds",
         "technologies": ["Python"], "techCategory": "Backend", "activeFrom": "2026-10-09"},
        {"_id": "2", "jobUrl": "Beta-Visa-Role", "name": "Senior Full Stack Engineer", "company": "Beta",
         "workplace": "hybrid", "hasVisaSponsorship": "Yes", "actualCity": "london",
         "technologies": ["React"], "techCategory": "Fullstack", "activeFrom": "2026-10-10"},
        {"_id": "3", "jobUrl": "Gamma-Office", "name": "Java Developer", "company": "Gamma",
         "workplace": "office", "hasVisaSponsorship": "No", "actualCity": "london"},
        {"_id": "4", "jobUrl": "Delta-Paused", "name": "Go Developer", "company": "Delta",
         "workplace": "remote", "isPaused": True},
    ]

    def test_keeps_only_remote_or_visa_and_maps_visa_to_relocation(self):
        client = MagicMock()
        client.get_json.return_value = self.JOBS
        client.get_text.return_value = (
            "<rss><channel><item><link>https://devitjobs.uk/jobs/Acme-Remote-Python-Dev?utm_source=x</link>"
            "<description><![CDATA[<p>Build Python APIs for our platform.</p>]]></description></item></channel></rss>"
        )
        items = DevITjobsUkConnector(client, _store()).feed_items()
        self.assertEqual([i["source_url"] for i in items],
                         ["https://devitjobs.uk/jobs/Beta-Visa-Role", "https://devitjobs.uk/jobs/Acme-Remote-Python-Dev"])
        visa, remote = items
        self.assertTrue(visa["relocation"])
        self.assertIsNone(visa["remote"])
        self.assertEqual(visa["city"], "London")
        self.assertTrue(remote["remote"])
        self.assertIsNone(remote["relocation"])
        self.assertEqual(remote["city"], "Remote (Leeds, UK)")
        self.assertIn("Build Python APIs", remote["text"])
        self.assertIn("Technologies", visa["text"])  # not in the RSS: built-in fallback text

    def test_rss_is_not_read_when_nothing_is_new(self):
        client = MagicMock()
        client.get_json.return_value = self.JOBS
        known = {"https://devitjobs.uk/jobs/Acme-Remote-Python-Dev", "https://devitjobs.uk/jobs/Beta-Visa-Role"}
        DevITjobsUkConnector(client, _store(known)).feed_items()
        client.get_text.assert_not_called()

    def test_rss_is_not_read_when_only_rejected_rows_remain(self):
        import sqlite3

        from worker.market_fit import mark_rejected

        conn = sqlite3.connect(":memory:")
        for slug in ("Acme-Remote-Python-Dev", "Beta-Visa-Role"):
            mark_rejected(conn, "https://devitjobs.uk/jobs/" + slug, "foreign_locked_remote")
        store = _store()
        store.conn = conn
        client = MagicMock()
        client.get_json.return_value = self.JOBS
        DevITjobsUkConnector(client, store).feed_items()
        client.get_text.assert_not_called()

    def test_visa_flag_is_stated_in_text(self):
        client = MagicMock()
        client.get_json.return_value = self.JOBS
        client.get_text.return_value = "<rss/>"
        items = DevITjobsUkConnector(client, _store()).feed_items()
        self.assertIn("Visa sponsorship: yes", items[0]["text"])
        self.assertNotIn("Visa sponsorship", items[1]["text"])

    def test_rss_failure_falls_back_to_summary_text(self):
        from worker.http import SourceFailed

        client = MagicMock()
        client.get_json.return_value = self.JOBS
        client.get_text.side_effect = SourceFailed("boom")
        items = DevITjobsUkConnector(client, _store()).feed_items()
        self.assertEqual(len(items), 2)


class TheMuseTest(unittest.TestCase):
    def _page(self, results, count=1):
        return {"page_count": count, "results": results}

    def test_remote_only_and_title_decides_tech(self):
        job = lambda name, locs, jid: {  # noqa: E731
            "id": jid, "name": name, "contents": "<p>Build things.</p>",
            "locations": [{"name": n} for n in locs],
            "categories": [{"name": "Software Engineering"}],
            "company": {"name": "Acme"},
            "refs": {"landing_page": f"https://www.themuse.com/jobs/acme/{jid}"},
            "publication_date": "2026-10-10T00:00:00Z",
        }
        client = MagicMock()
        client.get_json.return_value = self._page([
            job("Backend Engineer", ["Flexible / Remote", "Berlin, Germany"], 1),
            job("Litigation Counsel", ["Flexible / Remote", "London, United Kingdom"], 2),
            job("Office Engineer", ["Seattle, WA"], 3),
        ])
        conn = TheMuseConnector(client, _store())
        conn.categories = ("Software Engineering",)
        items = conn.feed_items()
        self.assertEqual([i["external_id"] for i in items], ["1", "2"])
        self.assertEqual(items[0]["city"], "Remote (Berlin, Germany)")
        self.assertTrue(is_tech_job(items[0]["title"], items[0]["category"], items[0]["tags"]))
        self.assertFalse(is_tech_job(items[1]["title"], items[1]["category"], items[1]["tags"]))

    def test_us_only_guard(self):
        guard = TheMuseConnector.not_us_only
        # bare "Flexible / Remote" with US pay signals: dropped
        self.assertFalse(guard([], "Pay range $120,000 - $150,000. 401(k) match."))
        # bare remote, no signals at all: dropped too (cannot tell where it is open)
        self.assertFalse(guard([], "Build backend services."))
        # explicit open text keeps it even with a USD range
        self.assertTrue(guard([], "Work from anywhere. Range $120,000 - $150,000"))
        # only US cities: dropped; a non-US place keeps it
        self.assertFalse(guard(["Seattle, WA"], "Build backend services."))
        self.assertTrue(guard(["Berlin, Germany"], "Build backend services."))

    def test_stops_at_last_page(self):
        client = MagicMock()
        client.get_json.return_value = self._page([], count=1)
        conn = TheMuseConnector(client, _store())
        conn.categories = ("Software Engineering",)
        conn.feed_items()
        client.get_json.assert_called_once()


class RemoteFirstJobsRssTest(unittest.TestCase):
    RSS = """<rss><channel><item>
      <title>Senior Backend Engineer at Scale at Acme</title>
      <link>https://remotefirstjobs.com/companies/acme/jobs/senior-backend-engineer-123</link>
      <description>&lt;p&gt;Build APIs.&lt;/p&gt;</description></item></channel></rss>"""

    def test_splits_title_on_last_at_and_marks_remote(self):
        client = MagicMock()
        client.get_text.return_value = self.RSS
        items = RemoteFirstJobsRssConnector(client, _store()).feed_items()
        self.assertEqual(items[0]["title"], "Senior Backend Engineer at Scale")
        self.assertEqual(items[0]["company"], "Acme")
        self.assertEqual(items[0]["external_id"], "123")
        self.assertTrue(items[0]["remote"])

    def test_fetch_reads_country_restriction_once(self):
        page = (
            '<script type="application/ld+json">{"@type":"JobPosting","title":"x","description":"d",'
            '"applicantLocationRequirements":[{"@type":"Country","name":"United States"}],'
            '"jobLocationType":"TELECOMMUTE"}</script>'
        )
        client = MagicMock()
        client.get_text.side_effect = [self.RSS, page]
        client.allowed.return_value = True
        conn = RemoteFirstJobsRssConnector(client, _store())
        url = conn.discover()[0]
        raw = conn.fetch(url)
        self.assertIn("Remote (United States)", raw)
        conn.fetch(url)
        self.assertEqual(client.get_text.call_count, 2)


if __name__ == "__main__":
    unittest.main()
