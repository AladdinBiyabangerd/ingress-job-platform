"""Landing.jobs / NoDesk / Ashby connectors: parsing, and acceptance still rejects."""
import json
import os
import unittest

os.environ.setdefault("AI_GATEWAY_ENABLED", "0")
os.environ.setdefault("AI_MARKET_FIT_ENABLED", "0")

from worker.acceptance import finish_item
from worker.connectors.ats import AshbyConnector
from worker.connectors.rssboards import LandingJobsConnector, NoDeskConnector

LJ = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>https://landing.jobs/at/acme/backend-engineer</id><title>Backend Engineer</title>
<content type="html"><![CDATA[<div class="offer-info">At Acme (Permanent), in Lisbon, Portugal<br />Remote policy: Full remote</div><p>Python, Django, AWS. Remote from anywhere in the world.</p>]]></content>
<x:foo>unbound prefix</x:foo></entry>
<entry><id>https://landing.jobs/at/acme/recruiter</id><title>Senior Recruiter</title>
<content type="html"><![CDATA[<div class="offer-info">At Acme (Permanent), in Lisbon, Portugal<br />Remote policy: Full remote</div><p>Hire people.</p>]]></content></entry>
<entry><id>https://landing.jobs/at/acme/java-dev</id><title>Java Developer</title>
<content type="html"><![CDATA[<div class="offer-info">At Acme (Permanent), in Porto, Portugal<br />Remote policy: Partial remote</div><p>Java, Spring. Hybrid, 3 days in the Porto office.</p>]]></content></entry>
</feed>"""

ND = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Senior Infrastructure Engineer at Buffer</title><description>Kubernetes, AWS, Terraform. Work from anywhere.</description><guid>https://nodesk.co/remote-jobs/buffer-sie/</guid></item>
<item><title>Staff GTM Analyst (USA Only, 100% Remote) at Close</title><description>Go-to-market.</description><guid>https://nodesk.co/remote-jobs/close-gtm/</guid></item>
<item><title>Senior Backend Engineer (USA Only, 100% Remote) at Close</title><description>Python. Must reside in the United States.</description><guid>https://nodesk.co/remote-jobs/close-be/</guid></item>
</channel></rss>"""


def ashby_page(data):
    return "<html><script>window.__appData = " + json.dumps(data) + ";</script></html>"


BOARD = {"organization": {"name": "Acme"}, "jobBoard": {"teams": [{"id": "t", "name": "Engineering"}], "jobPostings": [
    {"id": "1", "title": "Senior Backend Engineer", "teamId": "t", "locationName": "Remote", "workplaceType": "Remote"},
    {"id": "2", "title": "Account Executive", "teamId": "t", "locationName": "Remote", "workplaceType": "Remote"},
    {"id": "3", "title": "Platform Engineer", "teamId": "t", "locationName": "Remote (US)", "workplaceType": "Remote",
     "secondaryLocations": [{"locationName": "Remote (Canada)"}]},
]}}
POSTS = {
    "1": {"descriptionHtml": "<p>Python, Go, Kubernetes. Fully remote, work from anywhere.</p>", "locationName": "Remote",
          "workplaceType": "Remote"},
    "3": {"descriptionHtml": "<p>Go, AWS. Remote, must be based in the United States.</p>", "locationName": "Remote (US)",
          "secondaryLocationNames": ["Remote (Canada)"], "workplaceType": "Remote"},
}


class FakeClient:
    def __init__(self, pages):
        self.pages = pages

    def allowed(self, url):
        return True

    def get_text(self, url, accept=None):
        return self.pages[url]


class FakeStore:
    conn = None

    def has_source_url(self, url):
        return False


def accepted(conn):
    out = []
    for url in conn.discover():
        item = finish_item(conn, conn.normalize(conn.fetch(url), url))
        if item:
            out.append(item["title"])
    return out


class ConnectorTests(unittest.TestCase):
    def test_landing_parses_loose_atom_and_rules_reject(self):
        c = LandingJobsConnector(FakeClient({LandingJobsConnector.entry_url: LJ}), FakeStore())
        items = c.feed_items()
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["company"], "Acme")
        self.assertEqual(items[0]["city"], "Lisbon, Portugal")
        self.assertTrue(items[0]["remote"])
        self.assertIsNone(items[2]["remote"])  # partial remote = hybrid
        got = accepted(LandingJobsConnector(FakeClient({LandingJobsConnector.entry_url: LJ}), FakeStore()))
        self.assertNotIn("Senior Recruiter", got)   # non-IT
        self.assertNotIn("Java Developer", got)     # hybrid office in Portugal

    def test_nodesk_splits_company_and_rules_reject(self):
        c = NoDeskConnector(FakeClient({NoDeskConnector.entry_url: ND}), FakeStore())
        c.detail = False
        items = c.feed_items()
        self.assertEqual(items[0]["title"], "Senior Infrastructure Engineer")
        self.assertEqual(items[0]["company"], "Buffer")
        got = accepted(c)
        self.assertIn("Senior Infrastructure Engineer", got)
        self.assertNotIn("Staff GTM Analyst (USA Only, 100% Remote)", got)
        self.assertNotIn("Senior Backend Engineer (USA Only, 100% Remote)", got)

    def test_ashby_board_and_rules_reject(self):
        pages = {"https://jobs.ashbyhq.com/acme": ashby_page(BOARD)}
        for jid, post in POSTS.items():
            pages[f"https://jobs.ashbyhq.com/acme/{jid}"] = ashby_page({"posting": post})
        cls = type("A", (AshbyConnector,), {"name": "Ashby test", "boards": ("acme",)})
        c = cls(FakeClient(pages), FakeStore())
        rows = c.board_items("acme")
        self.assertEqual([r["title"] for r in rows], ["Senior Backend Engineer", "Platform Engineer"])
        got = accepted(cls(FakeClient(pages), FakeStore()))
        self.assertEqual(got, ["Senior Backend Engineer"])  # US/Canada-only remote rejected


if __name__ == "__main__":
    unittest.main()
