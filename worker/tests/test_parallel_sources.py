"""Sources run side by side; one slow source does not block the rest, and a
source still running is never started a second time."""
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

from worker import runner


class Store:
    def __init__(self):
        self.closed = 0

    def thread_store(self):
        return self

    def close(self):
        self.closed += 1


class RunnerParallelTests(unittest.TestCase):
    def setUp(self):
        runner._RUNNING.clear()
        self.ex = ThreadPoolExecutor(4)
        self.addCleanup(self.ex.shutdown, True)
        self.addCleanup(runner._RUNNING.clear)
        self.done = []
        self.slow_gate = threading.Event()

        def fake_run(store, client, connector, source_id, **kw):
            if connector.name == "Slow":
                self.slow_gate.wait(5)
            self.done.append(connector.name)

        mock.patch.object(runner, "_run_source", side_effect=fake_run).start()
        mock.patch.object(runner, "_too_soon", return_value=False).start()
        self.addCleanup(mock.patch.stopall)

    def builder(self, name):
        def build(client, store):
            return type("C", (), {"name": name})()
        return build

    def picked(self, *names):
        return [(n, self.builder(n), i) for i, n in enumerate(names)]

    def test_slow_source_does_not_block_others(self):
        runner._run_sources_parallel(Store(), self.picked("Slow", "A", "B"),
                                     wait_seconds=1, executor=self.ex, client=object())
        self.assertEqual(sorted(self.done), ["A", "B"])
        self.assertIn("Slow", runner._RUNNING)
        self.slow_gate.set()

    def test_running_source_not_started_again(self):
        runner._run_sources_parallel(Store(), self.picked("Slow"), wait_seconds=0.2,
                                     executor=self.ex, client=object())
        futures = runner._run_sources_parallel(Store(), self.picked("Slow", "A"),
                                               wait_seconds=1, executor=self.ex, client=object())
        self.assertEqual(len(futures), 1)  # only A was submitted
        self.slow_gate.set()
        deadline = time.time() + 5
        while "Slow" in runner._RUNNING and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.done.count("Slow"), 1)
        self.assertNotIn("Slow", runner._RUNNING)

    def test_one_shot_waits_for_all(self):
        self.slow_gate.set()
        runner._run_sources_parallel(Store(), self.picked("Slow", "A"),
                                     wait_seconds=None, executor=self.ex, client=object())
        self.assertEqual(sorted(self.done), ["A", "Slow"])


class SqliteThreadsTests(unittest.TestCase):
    def test_thread_stores_write_concurrently(self):
        import os
        import tempfile
        from pathlib import Path
        from worker.db import Store as RealStore

        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"DATABASE_URL": ""}):
            base = RealStore(Path(d) / "j.sqlite", sqlite_only=True)
            mode = base.conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertEqual(mode.lower(), "wal")
            sid = int(base.conn.execute("SELECT id FROM crawl_sources LIMIT 1").fetchone()[0])
            errors = []

            def work():
                s = base.thread_store()
                try:
                    for _ in range(20):
                        rid = s.start_run(sid)
                        s.finish_run(rid, status="ok", found=0, created=0, updated=0, error=None)
                except Exception as exc:  # pragma: no cover
                    errors.append(exc)
                finally:
                    s.close()

            ts = [threading.Thread(target=work) for _ in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
            n = base.conn.execute("SELECT COUNT(*) FROM crawl_runs").fetchone()[0]
            base.close()
        self.assertEqual(errors, [])
        self.assertEqual(n, 120)


class HostLockTests(unittest.TestCase):
    def test_same_host_never_concurrent(self):
        from worker.http import PoliteClient

        c = PoliteClient()
        self.addCleanup(c.close)
        c._robots["ex.com"] = mock.Mock(can_fetch=lambda *a: True)
        c._wild["ex.com"] = mock.Mock(allowed=lambda u: True)
        c._loaded["ex.com"] = time.time()
        c._delay["ex.com"] = 0.0
        active, peak, lock = [0], [0], threading.Lock()

        def get(url, **kw):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.02)
            with lock:
                active[0] -= 1
            r = mock.Mock(status_code=200, text="ok", url=url)
            return r

        c._http = mock.Mock(get=get)
        with mock.patch("worker.http.MIN_DELAY", 0.0):
            ts = [threading.Thread(target=c.get, args=(f"https://ex.com/{i}",)) for i in range(6)]
            [t.start() for t in ts]
            [t.join() for t in ts]
        self.assertEqual(peak[0], 1)


if __name__ == "__main__":
    unittest.main()
