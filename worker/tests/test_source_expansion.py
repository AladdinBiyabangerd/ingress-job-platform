"""Workable aggregator, niche RSS boards, Breezy/Pinpoint boards and the ATS sweep tool."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from worker.connectors.apis import WorkableAggregatorConnector
from worker.connectors.ats import BreezyConnector, PinpointConnector
from worker.connectors.nicheboards import (
    AiDevBoardConnector,
    CryptocurrencyJobsConnector,
    JsJobbsConnector,
    known_company_title,
)
from worker.parsing import norm_key

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sweep_ats_boards as sweep  # noqa: E402


def _store(conn=None):
    store = MagicMock()
    store.conn = conn
    store.has_source_url.return_value = False
    return store


def _rss(items: str) -> str:
    return f"<rss><channel>{items}</channel></rss>"


class WorkableAggregatorTest(unittest.TestCase):
    def _job(self, jid, title, company, country, workplace="remote", locations=("TELECOMMUTE",)):
        return {
            "id": jid, "title": title, "state": "published", "language": "en",
            "url": f"https://jobs.workable.com/view/{jid}", "description": "<p>Build things</p>",
            "requirementsSection": "<ul><li>Python</li></ul>", "workplace": workplace,
            "locations": list(locations), "location": {"city": "", "countryName": country},
            "company": {"title": company}, "created": "2026-10-10T10:00:00Z",
        }

    def test_merges_per_country_duplicates_and_shows_plain_remote(self):
        client = MagicMock()
        client.get_json.return_value = {"jobs": [
            self._job("a", "Software Engineer", "Acme Inc", "India"),
            self._job("b", "Software Engineer", "ACME Inc.", "Brazil"),
            self._job("c", "Data Engineer", "Acme Inc", "India"),
        ]}
        conn = WorkableAggregatorConnector(client, _store())
        conn.queries = (("software engineer", "&workplace=remote"), ("developer", "&workplace=remote"))
        items = conn.feed_items()
        self.assertEqual(sorted(i["title"] for i in items), ["Data Engineer", "Software Engineer"])
        self.assertTrue(all(i["city"] == "Remote" and i["remote"] for i in items))
        self.assertIn("Python", items[0]["text"])

    def test_follows_page_token_and_skips_unpublished(self):
        client = MagicMock()
        page1 = {"jobs": [self._job("a", "Developer", "X", "US")], "nextPageToken": "T1"}
        bad = self._job("z", "Developer II", "Y", "US")
        bad["state"] = "closed"
        page2 = {"jobs": [bad, self._job("b", "QA Engineer", "Z", "US", workplace="on_site", locations=["Berlin"])]}
        client.get_json.side_effect = [page1, page2]
        conn = WorkableAggregatorConnector(client, _store())
        conn.queries = (("developer", ""),)
        items = conn.feed_items()
        self.assertEqual([i["title"] for i in items], ["Developer", "QA Engineer"])
        self.assertIn("pageToken=T1", client.get_json.call_args_list[1].args[0])
        self.assertIsNone(items[1]["remote"])


class NicheBoardsTest(unittest.TestCase):
    def test_cryptocurrencyjobs_splits_on_last_at_and_unescapes(self):
        client = MagicMock()
        client.get_text.return_value = _rss(
            "<item><title>Tech Lead, dApp (TypeScript &amp;amp; Angular) at 1inch</title>"
            "<description>Full-time</description><link>https://cryptocurrencyjobs.co/engineering/x/</link>"
            "<pubDate>Tue, 06 Oct 2026 08:00:00 +0200</pubDate></item>")
        item, = CryptocurrencyJobsConnector(client, _store()).feed_items()
        self.assertEqual(item["title"], "Tech Lead, dApp (TypeScript & Angular)")
        self.assertEqual(item["company"], "1inch")

    def test_jsjobbs_remote_from_category(self):
        client = MagicMock()
        client.get_text.return_value = _rss(
            "<item><title><![CDATA[Staff Engineer]]></title><link>https://jsjobbs.com/javascript-jobs/jobabc-x</link>"
            "<guid>jobabc</guid><description><![CDATA[# Description\n\nBuild]]></description>"
            "<author>Acme</author><category>Germany and Remote</category></item>"
            "<item><title><![CDATA[Office Dev]]></title><link>https://jsjobbs.com/javascript-jobs/jobdef-y</link>"
            "<guid>jobdef</guid><description>x</description><author>Beta</author><category>Austin, TX</category></item>")
        a, b = JsJobbsConnector(client, _store()).feed_items()
        self.assertTrue(a["remote"])
        self.assertEqual(a["company"], "Acme")
        self.assertIsNone(b["remote"])

    def test_ai_dev_board_remote_only_salary_stripped_and_known_skipped(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE jobs (norm_key TEXT)")
        conn.execute("INSERT INTO jobs VALUES (?)", (norm_key("ML Engineer", "Known Co", "Remote"),))
        client = MagicMock()
        client.get_text.return_value = _rss(
            "<item><title>Sr Data Scientist at Dataiku ($210k-$220k)</title><link>https://aidevboard.com/job/a-1</link>"
            "<description>Sr Data Scientist — New York, NY · full-time · On-site · $210k</description></item>"
            "<item><title>ML Engineer at Known Co ($100k-$120k)</title><link>https://aidevboard.com/job/b-2</link>"
            "<description>ML Engineer — Worldwide · full-time · Remote · $100k</description></item>"
            "<item><title>AI Engineer at New Co ($100k-$120k)</title><link>https://aidevboard.com/job/c-3</link>"
            "<description>AI Engineer — Portugal · full-time · Remote · $100k</description>"
            "<category>llm, agents</category></item>")
        items = AiDevBoardConnector(client, _store(conn)).feed_items()
        self.assertEqual([i["title"] for i in items], ["AI Engineer"])
        self.assertEqual(items[0]["company"], "New Co")
        self.assertEqual(items[0]["city"], "Remote (Portugal)")
        self.assertEqual(items[0]["tags"], ["llm", "agents"])

    def test_known_company_title_handles_missing_store(self):
        self.assertFalse(known_company_title(_store(None), "A", "B"))
        self.assertFalse(known_company_title(_store(sqlite3.connect(":memory:")), "A", "B"))


class BreezyPinpointTest(unittest.TestCase):
    def test_breezy_maps_remote_flag_and_skips_non_tech(self):
        client = MagicMock()
        client.allowed.return_value = True
        client.get_json.return_value = [
            {"id": "1", "name": "Senior Backend Engineer", "url": "https://acme.breezy.hr/p/1-x",
             "department": "Engineering", "published_date": "2026-10-01",
             "location": {"is_remote": True, "name": "Remote", "country": {"name": "Polska", "id": "PL"}},
             "company": {"name": "Acme"}},
            {"id": "2", "name": "Receptionist", "url": "https://acme.breezy.hr/p/2-y",
             "location": {"is_remote": False, "name": "Austin, TX"}, "company": {"name": "Acme"}},
        ]
        conn = BreezyConnector(client, _store())
        rows = conn.board_items("acme")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["remote"])
        self.assertEqual(rows[0]["city"], "Remote (Poland)")  # English name from the ISO code
        self.assertEqual(rows[0]["external_id"], "breezy-acme-1")

    def test_pinpoint_builds_text_and_workplace(self):
        client = MagicMock()
        client.allowed.return_value = True
        client.get_json.return_value = {"data": [{
            "id": 7, "title": "Platform Engineer", "url": "https://acme.pinpointhq.com/en/postings/7",
            "description": "<p>We offer relocation support</p>", "key_responsibilities": "<ul><li>Ship</li></ul>",
            "workplace_type": "hybrid", "location": {"city": "Berlin", "province": "Berlin", "name": "HQ"},
            "job": {"department": {"name": "Engineering"}}}]}
        rows = PinpointConnector(client, _store()).board_items("acme")
        self.assertEqual(rows[0]["city"], "Berlin, Berlin")
        self.assertIsNone(rows[0]["remote"])
        self.assertIn("relocation support", rows[0]["text"])
        self.assertIn("Ship", rows[0]["text"])


class SweepToolTest(unittest.TestCase):
    def test_place_signal(self):
        for ok in ("Remote - Global Anywhere", "EMEA Remote", "Remote, Germany", "Berlin (relocation)", "Europe"):
            self.assertTrue(sweep.place_signal(ok), ok)
        for bad in ("", "Remote - US", "United States, Remote", "Remote (Canada)", "London"):
            self.assertFalse(sweep.place_signal(bad), bad)

    def test_load_slugs_formats_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "a.csv"
            csv_path.write_text("name,slug,url\nA,alpha,x\nB,Beta,y\nC,alpha,z\n")
            txt = Path(tmp) / "b.txt"
            txt.write_text("one\ntwo words\n\nthree\n")
            js = Path(tmp) / "c.json"
            js.write_text(json.dumps([{"slug": "x1"}, "x2", {"slug": "x1"}]))
            self.assertEqual(sweep.load_slugs(csv_path), ["alpha", "Beta"])
            self.assertEqual(sweep.load_slugs(txt), ["one", "three"])
            self.assertEqual(sweep.load_slugs(js), ["x1", "x2"])

    def test_sweep_one_requires_tech_title(self):
        client = MagicMock()
        client.get_json.return_value = {"jobs": [
            {"title": "Senior Software Engineer", "location": {"name": "Remote - EMEA"}},
            {"title": "Office Manager", "location": {"name": "Remote - EMEA"}},
            {"title": "Backend Engineer", "location": {"name": "Remote - US"}},
        ]}
        info = sweep.sweep_one(client, "greenhouse", "acme")
        self.assertEqual((info["total"], info["tech"], info["sig"]), (3, 2, 1))
        self.assertEqual(info["locs"], ["Remote - EMEA"])

    def test_sweep_resume_and_skip_existing(self):
        known = sweep.known_slugs("greenhouse")
        self.assertIn("monzo", known)
        self.assertNotIn("monzo", sweep.known_slugs("lever"))


if __name__ == "__main__":
    unittest.main()
