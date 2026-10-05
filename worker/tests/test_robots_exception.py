"""The robots.txt exception covers only Reed's official keyed API path."""

from __future__ import annotations

import unittest

import httpx

from worker.http import ROBOTS_EXCEPTIONS, PoliteClient, robots_exception

REED_ROBOTS = "User-agent: *\nDisallow: /api/\nDisallow: /courses/api/\n"


class RobotsExceptionTest(unittest.TestCase):
    def test_only_reed_api_1_0(self):
        self.assertEqual(ROBOTS_EXCEPTIONS, (("https", "www.reed.co.uk", "/api/1.0/"),))
        yes = [
            "https://www.reed.co.uk/api/1.0/search?keywords=python",
            "https://www.reed.co.uk/api/1.0/jobs/123",
            "https://WWW.REED.CO.UK/api/1.0/search",
        ]
        no = [
            "http://www.reed.co.uk/api/1.0/search",          # not https
            "https://reed.co.uk/api/1.0/search",              # other host
            "https://api.reed.co.uk/api/1.0/search",
            "https://www.reed.co.uk.evil.test/api/1.0/search",
            "https://www.reed.co.uk:8443/api/1.0/search",     # explicit port
            "https://user@www.reed.co.uk/api/1.0/search",
            "https://www.reed.co.uk/api/2.0/search",          # other API version
            "https://www.reed.co.uk/api/",
            "https://www.reed.co.uk/api/1.0",                 # no trailing slash path
            "https://www.reed.co.uk/courses/api/x",
            "https://www.reed.co.uk/jobs/python-developer/1",
            "https://www.reed.co.uk/api/1.0/../handlers/x",
            "https://www.reed.co.uk/api/1.0/%2e%2e/handlers/x",
            "https://www.jooble.org/api/1.0/x",
        ]
        for url in yes:
            self.assertTrue(robots_exception(url), url)
        for url in no:
            self.assertFalse(robots_exception(url), url)

    def test_client_still_applies_reed_robots_elsewhere(self):
        def handler(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=REED_ROBOTS)
            return httpx.Response(200, json={})

        client = PoliteClient()
        client._http = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            self.assertTrue(client.allowed("https://www.reed.co.uk/api/1.0/search?keywords=x"))
            self.assertFalse(client.allowed("https://www.reed.co.uk/api/2.0/search"))
            self.assertFalse(client.allowed("https://www.reed.co.uk/courses/api/x"))
            self.assertTrue(client.allowed("https://www.reed.co.uk/jobs/python-developer/1"))
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
