import sqlite3
import unittest

from worker.connectors import djinni as dj
from worker.connectors.djinni import DjinniConnector
from worker.http import SourceFailed
from worker.market_fit import is_rejected, mark_rejected


def rss(items):
    body = "".join(
        f"<item><title>{t}</title><link>https://djinni.co/jobs/{i}-x/</link>"
        f"<category>{c}</category><category></category></item>"
        for i, t, c in items
    )
    return f"<?xml version='1.0'?><rss><channel>{body}</channel></rss>"


class FakeStore:
    def __init__(self, known=()):
        self.conn = sqlite3.connect(":memory:")
        self.known = set(known)

    def has_source_url(self, url):
        return url in self.known


class FakeClient:
    def __init__(self, feeds, fail_first=0):
        self.feeds = feeds
        self.calls = []
        self.fail_first = fail_first

    def allowed(self, url):
        return True

    def get_text(self, url, accept=None):
        self.calls.append(url)
        if self.fail_first:
            self.fail_first -= 1
            raise SourceFailed("timeout")
        return self.feeds.get(url, rss([]))


class DjinniTests(unittest.TestCase):
    def setUp(self):
        dj.BACKOFF = (0.0, 0.0)

    def test_keywords_are_it_only(self):
        for bad in ("sales", "hr", "recruiter", "marketing", "seo", "cfo", "graphic_design"):
            self.assertNotIn(bad, dj.IT_KEYWORDS)
        self.assertGreater(len(dj.IT_KEYWORDS), 60)

    def test_merge_dedupe_skip_known_and_prefilter(self):
        feeds = {
            f"{dj.FEED}?primary_keyword=python": rss([(1, "Python Dev", "Python"), (2, "Data Eng", "Python"), (3, "Old", "Python")]),
            f"{dj.FEED}?primary_keyword=java": rss([(1, "Python Dev", "Python"), (4, "Sales Manager", "Sales"), (5, "Rej", "Java")]),
        }
        store = FakeStore(known={"https://djinni.co/jobs/3-x"})
        mark_rejected(store.conn, "https://djinni.co/jobs/5-x", "foreign_office")
        c = DjinniConnector(FakeClient(feeds), store, keywords=["python", "java"])
        urls = c.discover()
        self.assertEqual(urls, ["https://djinni.co/jobs/1-x", "https://djinni.co/jobs/2-x"])
        self.assertTrue(is_rejected(store.conn, "https://djinni.co/jobs/4-x"))
        self.assertEqual(c.stats["known"], 2)
        self.assertEqual(c.stats["non_it"], 1)

    def test_full_feed_adds_remote_slice(self):
        full = rss([(i, f"Python Dev {i}", "Python") for i in range(100, 200)])
        client = FakeClient({f"{dj.FEED}?primary_keyword=python": full})
        DjinniConnector(client, FakeStore(), keywords=["python"]).discover()
        self.assertIn(f"{dj.FEED}?primary_keyword=python&employment=remote", client.calls)

    def test_retry_on_request_failure(self):
        feeds = {f"{dj.FEED}?primary_keyword=python": rss([(1, "Python Dev", "Python")])}
        c = DjinniConnector(FakeClient(feeds, fail_first=2), FakeStore(), keywords=["python"])
        self.assertEqual(len(c.discover()), 1)

    def test_all_feeds_failing_is_error(self):
        c = DjinniConnector(FakeClient({}, fail_first=99), FakeStore(), keywords=["python"])
        with self.assertRaises(SourceFailed):
            c.discover()

    def test_remote_and_relocation_signals(self):
        html = """<html><head><meta property="og:title" content="Go Dev at Acme">
        <script type="application/ld+json">{"@type":"JobPosting","title":"Go Dev","category":"Golang",
        "jobLocationType":"TELECOMMUTE","applicantLocationRequirements":{"@type":"Country","name":"Poland"}}</script>
        </head><body><ul><li><strong class="d-block font-weight-600">Full Remote</strong></li>
        <li><strong class="d-block font-weight-600">Relocation help</strong></li></ul>
        <div class="job-post__description">Go services</div></body></html>"""
        c = DjinniConnector(FakeClient({}), FakeStore())
        item = c.parse_page(html, "https://djinni.co/jobs/9-go/")
        self.assertTrue(item["remote"])
        self.assertTrue(item["relocation"])
        self.assertEqual(item["city"], "Poland")
        self.assertEqual(item["category"], "Golang")

    def test_office_ad_has_no_forced_flags(self):
        html = """<html><head><meta property="og:title" content="Go Dev at Acme"></head><body>
        <span class="location-text">Kyiv</span><div class="job-post__description">Office</div></body></html>"""
        item = DjinniConnector(FakeClient({}), FakeStore()).parse_page(html, "https://djinni.co/jobs/9-go/")
        self.assertNotIn("remote", item)
        self.assertNotIn("relocation", item)


if __name__ == "__main__":
    unittest.main()
