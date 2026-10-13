"""Runner: per-page skip on flaky pages, time budgets, rules still apply."""
import unittest
from unittest import mock

from worker import runner
from worker.ats_boards import ATS_MAX_BOARDS
from worker.connectors import ats
from worker.http import SourceFailed


class FakeStore:
    conn = None

    def __init__(self):
        self.runs = []

    def start_run(self, source_id):
        return 1

    def finish_run(self, run_id, **kw):
        self.runs.append(kw)


class Conn:
    name = "Fake source"
    store = None
    require_remote_or_relocation = False

    def __init__(self, urls, fail=(), skip=True, item=None):
        self.urls, self.fail, self.skip_failed_pages = urls, set(fail), skip
        self.item = item
        self.upserted = []

    def discover(self):
        return list(self.urls)

    def fetch(self, url):
        if url in self.fail:
            raise SourceFailed("request failed: RemoteProtocolError")
        return url

    def normalize(self, raw, url):
        return dict(self.item or {}, source_url=url)

    def upsert(self, item):
        self.upserted.append(item["source_url"])
        return "created"


def run(conn, clock=None):
    store = FakeStore()
    kw = {"clock": clock} if clock else {}
    with mock.patch.object(runner, "is_rejected", return_value=False), \
         mock.patch.object(runner, "finish_item", side_effect=lambda c, i: i if i.get("ok") else None):
        runner._run_source(store, None, conn, 1, **kw)
    return store.runs[0]


class RunnerBudgetTests(unittest.TestCase):
    def test_failing_page_skipped_run_ok(self):
        c = Conn(["a", "b", "c"], fail={"b"}, item={"ok": 1})
        r = run(c)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(c.upserted, ["a", "c"])

    def test_skip_is_default_for_every_connector(self):
        class Plain(Conn):
            pass
        c = Plain(["a", "b", "c"], fail={"a"}, item={"ok": 1})
        del c.skip_failed_pages
        r = run(c)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(c.upserted, ["b", "c"])
        self.assertIn("skipped 1", r["error"])

    def test_without_opt_in_page_failure_errors(self):
        c = Conn(["a", "b"], fail={"a"}, skip=False, item={"ok": 1})
        self.assertEqual(run(c)["status"], "error")

    def test_many_consecutive_failures_stop_gracefully(self):
        urls = [str(i) for i in range(40)]
        c = Conn(urls, fail=set(urls), item={"ok": 1})
        r = run(c)
        self.assertEqual(r["status"], "ok")
        self.assertIn("in a row", r["error"])

    def test_time_budget_stops_and_keeps_progress(self):
        t = iter([0, 0, 10_000, 10_000, 10_000])
        c = Conn(["a", "b", "c"], item={"ok": 1})
        r = run(c, clock=lambda: next(t))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(c.upserted, ["a"])
        self.assertIn("time budget", r["error"])

    def test_budget_lookup(self):
        c = Conn([])
        for name, secs in (("Teamtailor boards (Nordics)", 300), ("Lever boards (X)", 300),
                           ("Greenhouse boards (DACH)", 300), ("JobTech Platsbanken (Sweden)", 300),
                           ("Crypto Jobs List", 300), ("Other", runner.DEFAULT_BUDGET)):
            c.name = name
            self.assertEqual(runner.source_budget(c), secs)

    def test_rules_still_reject_through_real_finish_item(self):
        # Non-IT and US-only remote ads are rejected by the real acceptance path.
        for item in ({"title": "Senior Account Executive", "city": "Remote", "remote": True,
                      "company": "X", "text": "Sell our SaaS."},
                     {"title": "Backend Engineer", "city": "Remote (US only)", "remote": True,
                      "company": "X", "text": "Remote, must reside in the United States. Python."}):
            c = Conn(["u1"], item=item)
            store = FakeStore()
            with mock.patch.object(runner, "is_rejected", return_value=False), \
                 mock.patch("worker.acceptance.is_rejected", return_value=False), \
                 mock.patch("worker.acceptance.mark_rejected", create=True):
                runner._run_source(store, None, c, 1)
            self.assertEqual(c.upserted, [], item["title"])


class AtsCapTests(unittest.TestCase):
    def test_caps(self):
        self.assertEqual(ats.PER_BOARD, 25)
        self.assertEqual(ats.AtsConnector.candidates, 80)
        self.assertEqual(ATS_MAX_BOARDS, 20)

    def test_ats_feed_stops_reading_boards_after_deadline(self):
        class G(ats.AtsConnector):
            name = "Greenhouse test"
            boards = ("a", "b", "c")
            read = []

            def board_items(self, slug):
                self.read.append(slug)
                return [{"title": "Backend Engineer", "source_url": f"https://x/{slug}"}]

        g = G.__new__(G)
        t = iter([0, 100, 100, 100])
        g.deadline, g.clock = 50, lambda: next(t)
        g.feed_items()
        self.assertEqual(G.read, ["a"])


if __name__ == "__main__":
    unittest.main()
