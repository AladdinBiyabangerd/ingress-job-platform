"""Polite HTTP. robots.txt is checked before a fetch. No browser bypass."""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "ingress-job-bot/0.1 (+https://ingress.academy)"
MIN_DELAY = 1.0
BLOCK_STATUSES = {401, 403, 407, 429, 451, 503}

# These hosts are not connectors.
REFUSED_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "indeed.com",
    "www.indeed.com",
    "az.indeed.com",
    "tap.az",
    "www.tap.az",
    "gloria.az",
    "www.gloria.az",
    "job.az",
    "www.job.az",
}


class Disallowed(Exception):
    """robots.txt does not allow this path."""


class NotFound(Exception):
    """The item URL returned 404. Skip it."""


class SourceBlocked(Exception):
    """The source refused the client. Stop that source."""


class SourceFailed(Exception):
    """The source could not be read. Stop that source."""


def _host(url: str) -> str:
    return urlparse(url).netloc.lower()


class PoliteClient:
    def __init__(self) -> None:
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(25.0),
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._delay: dict[str, float] = {}
        self._last: dict[str, float] = {}

    def close(self) -> None:
        self._http.close()

    def allowed(self, url: str) -> bool:
        self._check_url(url)
        self._ensure_robots(url)
        return self._robots[_host(url)].can_fetch(USER_AGENT, url)

    def get_text(self, url: str, accept: str | None = None) -> str:
        return self.get(url, accept=accept).text

    def get_json(self, url: str):
        return self.get(url, accept="application/json").json()

    def get(self, url: str, accept: str | None = None) -> httpx.Response:
        self._check_url(url)
        if not self.allowed(url):
            raise Disallowed(url)
        self._pause(_host(url))
        headers = {"Accept": accept} if accept else None
        try:
            response = self._http.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise SourceFailed(f"timeout for {url}") from exc
        except httpx.HTTPError as exc:
            raise SourceFailed(f"request failed for {url}: {exc.__class__.__name__}") from exc
        final = str(response.url)
        self._check_url(final)
        if _host(final) != _host(url):
            self._ensure_robots(final)
        if not self._robots[_host(final)].can_fetch(USER_AGENT, final):
            raise Disallowed(final)
        if response.status_code in BLOCK_STATUSES:
            raise SourceBlocked(f"HTTP {response.status_code} for {url}")
        if response.status_code == 404:
            raise NotFound(url)
        if response.status_code >= 400:
            raise SourceFailed(f"HTTP {response.status_code} for {url}")
        self._reject_challenge(response.text[:2000], url)
        return response

    def _check_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SourceFailed(f"unsupported url {url}")
        host = parsed.netloc.lower()
        if host in REFUSED_HOSTS:
            raise SourceBlocked(f"refused host {host}")
        if "action=get_jobs" in parsed.query.lower():
            raise SourceBlocked("refused ?action=get_jobs")

    def _reject_challenge(self, head: str, url: str) -> None:
        match = re.search(r"<title>(.*?)</title>", head, flags=re.IGNORECASE | re.DOTALL)
        title = (match.group(1) if match else "").lower()
        markers = ("just a moment", "attention required", "access denied", "robot check", "captcha")
        if any(marker in title for marker in markers):
            raise SourceBlocked(f"bot check at {url}")

    def _ensure_robots(self, url: str) -> None:
        host = _host(url)
        if host in self._robots:
            return
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        self._pause(host)
        try:
            response = self._http.get(robots_url)
        except httpx.TimeoutException as exc:
            raise SourceFailed(f"robots.txt timeout for {host}") from exc
        except httpx.HTTPError as exc:
            raise SourceFailed(f"robots.txt failed for {host}: {exc.__class__.__name__}") from exc
        if response.status_code in BLOCK_STATUSES:
            raise SourceBlocked(f"robots.txt HTTP {response.status_code} for {host}")
        parser = RobotFileParser()
        if response.status_code == 404:
            parser.parse([])
            delay = MIN_DELAY
        elif response.status_code >= 400:
            raise SourceFailed(f"robots.txt HTTP {response.status_code} for {host}")
        else:
            parser.parse(response.text.splitlines())
            raw_delay = parser.crawl_delay(USER_AGENT)
            if raw_delay is None:
                raw_delay = parser.crawl_delay("*")
            delay = max(MIN_DELAY, float(raw_delay or MIN_DELAY))
        # parse() does not mark the file as read. can_fetch() then refuses every URL.
        parser.last_checked = time.time()
        self._robots[host] = parser
        self._delay[host] = delay

    def _pause(self, host: str) -> None:
        delay = max(MIN_DELAY, self._delay.get(host, MIN_DELAY))
        last = self._last.get(host)
        if last is not None:
            remain = delay - (time.monotonic() - last)
            if remain > 0:
                time.sleep(remain)
        self._last[host] = time.monotonic()
