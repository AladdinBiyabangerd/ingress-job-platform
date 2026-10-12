"""Pagination / multi-feed for high-yield sources, and proof that every item
they return still goes through the full acceptance pipeline (finish_item)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from worker.acceptance import finish_item
from worker.connectors import weworkremotely as wwr_mod
from worker.connectors.apis import ArbeitnowConnector, HimalayasConnector
from worker.connectors.regional import GetOnBoardConnector
from worker.connectors.rssboards import RealWorkFromAnywhereConnector
from worker.connectors.weworkremotely import WeWorkRemotelyConnector
from worker.db import Store

JD = ("Fully remote, work from anywhere. We build a payments platform. You will design Python and Go services on AWS, "
      "write tests, run Kubernetes and PostgreSQL in production. ") * 6


class FakeClient:
    def __init__(self, json_pages=None, texts=None):
        self.json_pages = json_pages or {}
        self.texts = texts or {}
        self.calls = []

    def allowed(self, url):
        return True

    def get_json(self, url, **kw):
        self.calls.append(url)
        for key, val in self.json_pages.items():
            if key(url):
                return val(url)
        return {"data": [], "jobs": []}

    def get_text(self, url, accept=None):
        self.calls.append(url)
        return self.texts.get(url, "<rss><channel></channel></rss>")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.sqlite", sqlite_only=True)
        # AI clarification never accepts in these tests.
        self.ai = patch("worker.acceptance.clarify_market_fit", return_value=None)
        self.ai.start()

    def tearDown(self):
        self.ai.stop()
        self.store.close()
        self.tmp.cleanup()

    def run_pipeline(self, conn):
        out = {}
        for url in conn.discover():
            out[url] = finish_item(conn, conn.normalize(conn.fetch(url), url))
        return out


def arbeitnow_job(i, title, remote, location="Berlin", tags=("Python",), desc=None):
    return {"title": title, "company_name": "Acme", "location": location, "description": f"<p>{JD} We offer visa sponsorship and relocation support to Germany.</p>",
            "url": f"https://www.arbeitnow.com/jobs/{i}", "slug": f"s{i}", "tags": list(tags), "remote": remote,
            **({"description": desc} if desc else {})}


class ArbeitnowTests(Base):
    def test_pages_until_next_empty_and_rules_apply(self):
        def page(url):
            n = int(url.split("page=")[1]) if "page=" in url else 1
            visa = "visa_sponsorship" in url
            jobs = [arbeitnow_job(n * 10 + (0 if visa else 5), "Backend Python Engineer", remote=not visa)]
            if n == 2 and not visa:
                jobs.append(arbeitnow_job(99, "Warehouse Forklift Driver", remote=True, tags=("Logistics",),
                                          desc="Drive forklifts in our Berlin warehouse. Fully remote."))
            return {"data": jobs, "links": {"next": "x" if n < 3 else None}}
        client = FakeClient({(lambda u: "arbeitnow" in u): page})
        conn = ArbeitnowConnector(client, self.store)
        res = self.run_pipeline(conn)
        self.assertEqual(sum(1 for u in client.calls if "arbeitnow" in u), 6)
        self.assertIsNone(res.get("https://www.arbeitnow.com/jobs/99"))  # non-IT rejected
        self.assertIsNotNone(res["https://www.arbeitnow.com/jobs/10"])
        self.assertEqual(conn.create_cap, 100)


class HimalayasTests(Base):
    def test_pages_and_region_lock_still_rejects(self):
        def page(url):
            n = int(url.split("page=")[1]) if "page=" in url else 1
            if n > 2:
                return {"jobs": []}
            q = url.split("q=")[1].split("&")[0]
            return {"jobs": [
                {"title": "Senior Backend Engineer", "companyName": "Acme", "description": JD + " US only. Must reside in the United States.",
                 "applicationLink": f"https://himalayas.app/j/us-{q}-{n}", "guid": f"us-{q}-{n}",
                 "locationRestrictions": ["United States"], "categories": ["Backend"]},
            ]}
        client = FakeClient({(lambda u: "himalayas" in u): page})
        conn = HimalayasConnector(client, self.store)
        conn.queries = ("software",)
        res = self.run_pipeline(conn)
        self.assertEqual(len([u for u in client.calls if "himalayas" in u]), 3)
        self.assertEqual(len(res), 2)
        for item in res.values():
            self.assertIsNone(item)  # US-only remote stays locked out
        self.assertEqual(conn.min_interval_hours, 24)


class GetOnBoardTests(Base):
    def test_paginates_by_total_pages(self):
        def page(url):
            n = int(url.split("page=")[1].split("&")[0])
            return {"meta": {"total_pages": 2}, "data": [{"id": f"{url[-60:]}-{n}", "attributes": {
                "title": "Office Receptionist", "countries": ["Chile"], "remote": False,
                "published_at": n, "category_name": "Other"}, "links": {"public_url": f"https://www.getonbrd.com/jobs/{abs(hash(url))}"}}]}
        client = FakeClient({(lambda u: "getonbrd" in u): page})
        conn = GetOnBoardConnector(client, self.store)
        conn.categories = ("programming", "data-science-analytics")
        res = self.run_pipeline(conn)
        self.assertEqual(len(client.calls), 4)
        self.assertTrue(all("per_page=100" in u for u in client.calls))
        self.assertEqual(res, {})  # non-IT office ads never become candidates


def wwr_rss(items):
    body = "".join(
        f"<item><title>Acme: {t}</title><link>https://weworkremotely.com/remote-jobs/{i}</link>"
        f"<region>{r}</region><description>{JD}</description><category>Programming</category></item>"
        for i, t, r in items)
    return f"<rss><channel>{body}</channel></rss>"


class WWRTests(Base):
    def test_category_feeds_deduped_and_rules_apply(self):
        texts = {WeWorkRemotelyConnector.entry_url: wwr_rss([(1, "Backend Engineer", "Anywhere in the World")])}
        texts[wwr_mod.CATEGORY_FEEDS[0]] = wwr_rss([(1, "Backend Engineer", "Anywhere in the World"),
                                                     (2, "Frontend Engineer", "USA Only")])
        conn = WeWorkRemotelyConnector(FakeClient(texts=texts), self.store)
        res = self.run_pipeline(conn)
        self.assertEqual(sorted(res), ["https://weworkremotely.com/remote-jobs/1", "https://weworkremotely.com/remote-jobs/2"])
        self.assertIsNotNone(res["https://weworkremotely.com/remote-jobs/1"])
        self.assertIsNone(res["https://weworkremotely.com/remote-jobs/2"])  # USA-only stays rejected


class CapsTests(unittest.TestCase):
    def test_caps_raised(self):
        self.assertGreaterEqual(RealWorkFromAnywhereConnector.create_cap, 100)
        self.assertGreaterEqual(WeWorkRemotelyConnector.create_cap, 100)
        self.assertEqual(GetOnBoardConnector.per_page, 100)


if __name__ == "__main__":
    unittest.main()
