"""Per-source new-ad caps, the pass time budget, host interleaving, reject skip, extra boards."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from worker import limits, runner
from worker.ats_boards import GROUPS
from worker.ats_boards_extra import MORE_GROUPS, all_groups
from worker.catalog import MAX_NEW_OVERRIDES, SOURCES
from worker.connectors.ats import ATS_GROUP_CONNECTORS
from worker.connectors.feed import FeedConnector
from worker.db import Store
from worker.market_fit import mark_rejected


def named(name, **attrs):
    return type("C", (), {"name": name, **attrs})()


class MaxNewTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in limits.TIER_ENV.values():
            os.environ.pop(key, None)

    def test_tier_defaults(self):
        self.assertEqual(limits.max_new(named("Greenhouse boards (DACH)")), 150)   # ATS group: api
        self.assertEqual(limits.max_new(named("The Muse")), 150)                   # official API
        self.assertEqual(limits.max_new(named("Python.org Jobs")), 100)            # RSS feed
        self.assertEqual(limits.max_new(named("Wellfound")), 50)                   # HTML pages
        self.assertEqual(limits.max_new(named("Not in catalog")), limits.LEGACY_CAP)

    def test_budgeted_sources_keep_30(self):
        self.assertEqual(MAX_NEW_OVERRIDES["Reed.co.uk"], 30)
        self.assertEqual(MAX_NEW_OVERRIDES["Jooble"], 30)
        self.assertEqual(limits.max_new(named("Reed.co.uk", create_cap=500)), 30)
        self.assertEqual(limits.max_new(named("Jooble")), 30)

    def test_connector_create_cap_beats_tier(self):
        self.assertEqual(limits.max_new(named("Djinni", create_cap=300)), 300)
        self.assertEqual(limits.max_new(named("Himalayas", create_cap=150)), 150)

    def test_env_overrides_tier_and_is_clamped(self):
        os.environ["MAX_NEW_PER_SOURCE"] = "220"
        os.environ["MAX_NEW_PER_SOURCE_FEED"] = "70"
        os.environ["MAX_NEW_PER_SOURCE_HTML"] = "oops"
        self.assertEqual(limits.max_new(named("Lever boards (Europe)")), 220)
        self.assertEqual(limits.max_new(named("Python.org Jobs")), 70)
        self.assertEqual(limits.max_new(named("Wellfound")), 50)
        os.environ["MAX_NEW_PER_SOURCE"] = "999999"
        self.assertEqual(limits.max_new(named("Lever boards (Europe)")), limits.MAX_CAP)
        os.environ["MAX_NEW_PER_SOURCE"] = "0"
        self.assertEqual(limits.max_new(named("Lever boards (Europe)")), 1)

    def test_pass_budget(self):
        os.environ.pop(limits.PASS_BUDGET_ENV, None)
        self.assertEqual(limits.pass_budget(), 3000)
        self.assertLess(limits.pass_budget(), runner.INTERVAL_SECONDS)
        os.environ[limits.PASS_BUDGET_ENV] = "10"
        self.assertEqual(limits.pass_budget(), limits.PASS_BUDGET_MIN)
        os.environ[limits.PASS_BUDGET_ENV] = "2400"
        self.assertEqual(limits.pass_budget(), 2400)


class FakeStore:
    conn = None

    def __init__(self):
        self.runs = []

    def start_run(self, source_id):
        return 1

    def finish_run(self, run_id, **kw):
        self.runs.append(kw)


class Conn:
    store = None
    require_remote_or_relocation = False

    def __init__(self, name, n):
        self.name = name
        self.urls = [f"u{i}" for i in range(n)]
        self.upserted = []

    def discover(self):
        return list(self.urls)

    def fetch(self, url):
        return url

    def normalize(self, raw, url):
        return {"source_url": url, "ok": 1}

    def upsert(self, item):
        self.upserted.append(item["source_url"])
        return "created"


def run_source(conn, **kw):
    store = FakeStore()
    with mock.patch.object(runner, "is_rejected", return_value=False), \
         mock.patch.object(runner, "finish_item", side_effect=lambda c, i: i):
        runner._run_source(store, None, conn, 1, **kw)
    return store.runs[0]


class RunnerCapTest(unittest.TestCase):
    def test_ats_group_saves_up_to_150(self):
        os.environ.pop("MAX_NEW_PER_SOURCE", None)
        conn = Conn("Greenhouse boards (DACH)", 400)
        run = run_source(conn)
        self.assertEqual(run["created"], 150)
        self.assertEqual(len(conn.upserted), 150)

    def test_reed_still_30(self):
        conn = Conn("Reed.co.uk", 100)
        self.assertEqual(run_source(conn)["created"], 30)

    def test_pass_deadline_stops_source_early(self):
        conn = Conn("Lever boards (Europe)", 50)
        clock = iter(range(0, 10_000, 10)).__next__
        run = run_source(conn, clock=clock, pass_deadline=35)
        self.assertLess(run["created"], 50)
        self.assertIn("time budget", run["error"])

    def test_source_not_started_after_pass_deadline(self):
        built = []
        with runner._RUNNING_LOCK:
            runner._RUNNING.add("Late source")
        runner._source_job(FakeStore(), None, "Late source", lambda c, s: built.append(1), 1,
                           deadline=time.monotonic() - 1)
        self.assertEqual(built, [])
        self.assertNotIn("Late source", runner._RUNNING)


class InterleaveTest(unittest.TestCase):
    def test_same_host_sources_are_spread(self):
        gh = [(f"Greenhouse {i}", type("G", (), {"entry_url": "https://boards-api.greenhouse.io/v1/boards"}), i)
              for i in range(4)]
        other = [(f"Feed {i}", type("F", (), {"entry_url": f"https://feed{i}.example/rss"}), 10 + i)
                 for i in range(2)]
        order = [name for name, _b, _i in runner.interleave_by_host(gh + other)]
        self.assertEqual(sorted(order), sorted(n for n, _b, _i in gh + other))
        self.assertEqual(order[:3], ["Greenhouse 0", "Feed 0", "Feed 1"])
        # No two Greenhouse groups back to back while other hosts are waiting.
        self.assertNotEqual(order[0][:5], order[1][:5])


class RejectSkipTest(unittest.TestCase):
    def test_discover_skips_rejected_urls(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = Store(Path(tmp.name) / "t.sqlite", sqlite_only=True)
        self.addCleanup(store.close)
        with store.conn:
            mark_rejected(store.conn, "https://ex.test/2", "foreign_office")

        class Feed(FeedConnector):
            name = "Feed"
            entry_url = "https://ex.test/feed"
            candidates = 2

            def feed_items(self):
                return [{"title": "Backend Engineer", "source_url": f"https://ex.test/{i}"} for i in (1, 2, 3)]

        client = mock.MagicMock()
        client.allowed.return_value = True
        urls = Feed(client, store).discover()
        # The rejected ad does not use one of the two candidate slots.
        self.assertEqual(urls, ["https://ex.test/1", "https://ex.test/3"])


class AshbyPayTest(unittest.TestCase):
    def test_pay_text_kept_as_published(self):
        from worker.connectors.ats import _ashby_pay

        self.assertEqual(_ashby_pay({"compensationTierSummary": "€70K – €90K • Offers Equity"}),
                         "€70K – €90K • Offers Equity")
        self.assertEqual(_ashby_pay({"compensationTierSummary": None,
                                     "scrapeableCompensationSalarySummary": "$150K - $180K"}),
                         "$150K - $180K")
        self.assertEqual(_ashby_pay({"compensationTierSummary": None}), "")


class ExtraBoardsTest(unittest.TestCase):
    def test_all_groups_have_rows_builders_and_unique_slugs(self):
        groups = all_groups()
        self.assertEqual(len(groups), len(GROUPS) + len(MORE_GROUPS))
        names = [g[0] for g in groups]
        self.assertEqual(len(names), len(set(names)))
        rows = {row["name"]: row for row in SOURCES}
        for name, ats, region, boards in MORE_GROUPS:
            self.assertIn(name, rows)
            self.assertTrue(rows[name]["enabled"])
            self.assertIn(name, ATS_GROUP_CONNECTORS)
            self.assertIn(name, runner.BUILDERS)
            self.assertTrue(region)
            self.assertGreaterEqual(len(boards), 3, name)
        seen = set()
        for _n, ats, _r, boards in groups:
            for slug in boards:
                key = (ats, slug.lower())
                self.assertNotIn(key, seen, key)
                seen.add(key)


if __name__ == "__main__":
    unittest.main()
