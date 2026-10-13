"""robots.txt: retry with backoff, reuse last good copy, never-read host is not crawled."""
import time
import unittest
from unittest import mock

import httpx

from worker import http
from worker.http import PoliteClient, SourceFailed


class Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


ROBOTS = "User-agent: *\nDisallow: /private/\n"


class RobotsCacheTests(unittest.TestCase):
    def setUp(self):
        http._ROBOTS_GOOD.clear()
        self.sleep = mock.patch.object(http.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)
        self.addCleanup(http._ROBOTS_GOOD.clear)

    def client(self, answers):
        c = PoliteClient()
        self.addCleanup(c.close)
        seq = iter(answers)

        def get(url, **kw):
            a = next(seq)
            if isinstance(a, Exception):
                raise a
            return a

        c._http = mock.Mock(get=mock.Mock(side_effect=get))
        return c

    def test_timeout_then_success_retries(self):
        c = self.client([httpx.ReadTimeout("t"), Resp(200, ROBOTS)])
        self.assertTrue(c.allowed("https://ex.com/jobs/1"))
        self.assertFalse(c.allowed("https://ex.com/private/x"))
        self.assertEqual(c._http.get.call_count, 2)

    def test_never_read_host_fails(self):
        c = self.client([httpx.ReadTimeout("t")] * 3)
        with self.assertRaises(SourceFailed):
            c.allowed("https://ex.com/jobs/1")

    def test_last_good_copy_reused_and_rules_kept(self):
        first = self.client([Resp(200, ROBOTS)])
        self.assertTrue(first.allowed("https://ex.com/jobs/1"))
        second = self.client([httpx.ConnectError("x")] * 3)
        self.assertTrue(second.allowed("https://ex.com/jobs/1"))
        # Cached disallow rules still apply.
        self.assertFalse(second.allowed("https://ex.com/private/x"))

    def test_stale_copy_refreshed_after_ttl(self):
        c = self.client([Resp(200, ROBOTS), Resp(200, "User-agent: *\nDisallow: /\n")])
        self.assertTrue(c.allowed("https://ex.com/jobs/1"))
        c._loaded["ex.com"] = time.time() - http.ROBOTS_TTL - 1
        self.assertFalse(c.allowed("https://ex.com/jobs/1"))


if __name__ == "__main__":
    unittest.main()
