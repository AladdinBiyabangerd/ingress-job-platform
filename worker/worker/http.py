"""Polite HTTP. robots.txt is checked before a fetch. No browser bypass.

Two robots readers must both allow a URL: the stdlib parser (first match) and a
Google-style reader that understands ``*`` and ``$`` with longest-match wins.
The stdlib parser treats ``Disallow: /*?`` literally, so without the second
reader a wildcard rule would silently be ignored.
"""

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


ROBOT_TOKEN = "ingress-job-bot"


class WildcardRobots:
    """Google-style robots rules for one host: groups, ``*``, ``$``, longest match."""

    def __init__(self, lines: list[str]) -> None:
        groups: list[tuple[list[str], list[tuple[bool, str]]]] = []
        agents: list[str] = []
        rules: list[tuple[bool, str]] = []
        last_was_agent = False
        for raw in lines:
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if key == "user-agent":
                if not last_was_agent and (agents or rules):
                    groups.append((agents, rules))
                    agents, rules = [], []
                agents.append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key in {"allow", "disallow"}:
                rules.append((key == "allow", value))
        if agents or rules:
            groups.append((agents, rules))
        mine = [r for a, r in groups if ROBOT_TOKEN in a]
        star = [r for a, r in groups if "*" in a]
        chosen = mine or star
        self.rules: list[tuple[bool, str]] = [rule for group in chosen for rule in group]

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        best_len = -1
        best_allow = True
        for allow, pattern in self.rules:
            if not pattern:
                continue
            if not _robots_match(pattern, target):
                continue
            size = len(pattern)
            if size > best_len or (size == best_len and allow):
                best_len = size
                best_allow = allow
        return best_allow


def _robots_match(pattern: str, target: str) -> bool:
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    regex = "^" + regex + ("$" if anchored else "")
    return re.match(regex, target) is not None


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


# Exact (scheme, host, path prefix) entries where robots.txt is not applied.
# Keep this list tiny; every entry needs the owner's written approval.
#
# Reed.co.uk: www.reed.co.uk/robots.txt says "Disallow: /api/" for every user
# agent, but /api/1.0/ is Reed's official, keyed Jobseeker API
# (https://www.reed.co.uk/developers/jobseeker): Reed issues a developer key
# for exactly these calls and every request carries it (HTTP Basic). The
# project owner (Aladdin) approved this exception on 2026-10-05. It covers
# only https://www.reed.co.uk/api/1.0/...; the rest of reed.co.uk (and any
# other /api/ path) still follows robots.txt.
ROBOTS_EXCEPTIONS: tuple[tuple[str, str, str], ...] = (
    ("https", "www.reed.co.uk", "/api/1.0/"),
)


def robots_exception(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.port is not None or parsed.username or parsed.password:
        return False
    path = parsed.path or "/"
    if "/../" in path or path.endswith("/..") or "%2e" in path.lower():
        return False
    return any(
        parsed.scheme == scheme and host == want_host and path.startswith(prefix)
        for scheme, want_host, prefix in ROBOTS_EXCEPTIONS
    )


class PoliteClient:
    def __init__(self) -> None:
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(25.0),
            follow_redirects=True,
        )
        self._robots: dict[str, RobotFileParser] = {}
        self._wild: dict[str, WildcardRobots] = {}
        self._delay: dict[str, float] = {}
        self._last: dict[str, float] = {}

    def close(self) -> None:
        self._http.close()

    def allowed(self, url: str) -> bool:
        self._check_url(url)
        if robots_exception(url):
            return True
        self._ensure_robots(url)
        host = _host(url)
        return self._robots[host].can_fetch(USER_AGENT, url) and self._wild[host].allowed(url)

    def get_text(self, url: str, accept: str | None = None) -> str:
        return self.get(url, accept=accept).text

    def get_json(self, url: str, *, auth: tuple[str, str] | None = None, shown: str | None = None):
        response = self.get(url, accept="application/json", auth=auth, shown=shown)
        try:
            return response.json()
        except ValueError:
            raise SourceFailed(f"non-JSON answer from {shown or url}") from None

    def get(
        self,
        url: str,
        accept: str | None = None,
        *,
        auth: tuple[str, str] | None = None,
        shown: str | None = None,
    ) -> httpx.Response:
        """robots.txt is checked for the exact URL first. ``auth`` is HTTP Basic
        for keyed official APIs; ``shown`` replaces the URL in error messages."""
        label = shown or url
        self._check_url(url)
        if not self.allowed(url):
            raise Disallowed(label)
        self._pause(_host(url))
        headers = {"Accept": accept} if accept else None
        try:
            if auth is not None:
                response = self._http.get(url, headers=headers, auth=auth)
            else:
                response = self._http.get(url, headers=headers)
        except httpx.TimeoutException as exc:
            raise SourceFailed(f"timeout for {label}") from (None if auth else exc)
        except httpx.HTTPError as exc:
            raise SourceFailed(
                f"request failed for {label}: {exc.__class__.__name__}"
            ) from (None if auth else exc)
        final = str(response.url)
        self._check_url(final)
        if _host(final) != _host(url):
            if auth is not None:
                raise SourceFailed(f"unexpected redirect for {label}")
            self._ensure_robots(final)
        if not self.allowed(final):
            raise Disallowed(shown or final)
        if response.status_code in BLOCK_STATUSES:
            raise SourceBlocked(f"HTTP {response.status_code} for {label}")
        if response.status_code == 404:
            raise NotFound(label)
        if response.status_code >= 400:
            raise SourceFailed(f"HTTP {response.status_code} for {label}")
        self._reject_challenge(response.text[:2000], label)
        return response

    def post_json(self, url: str, payload: dict, *, shown: str | None = None):
        """POST a JSON body to an official API and return the decoded JSON.

        ``shown`` replaces the URL in every error message, for APIs that put
        the key in the path (the key must never reach logs or crawl_runs).
        """
        label = shown or url
        self._check_url(url)
        if not self.allowed(url):
            raise Disallowed(label)
        self._pause(_host(url))
        try:
            response = self._http.post(url, json=payload, headers={"Accept": "application/json"})
        except httpx.TimeoutException:
            raise SourceFailed(f"timeout for {label}") from None
        except httpx.HTTPError as exc:
            raise SourceFailed(f"request failed for {label}: {exc.__class__.__name__}") from None
        if _host(str(response.url)) != _host(url):
            raise SourceFailed(f"unexpected redirect for {label}")
        if response.status_code in BLOCK_STATUSES:
            raise SourceBlocked(f"HTTP {response.status_code} for {label}")
        if response.status_code == 404:
            raise NotFound(label)
        if response.status_code >= 400:
            raise SourceFailed(f"HTTP {response.status_code} for {label}")
        try:
            return response.json()
        except ValueError:
            raise SourceFailed(f"non-JSON answer from {label}") from None

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
        wild = WildcardRobots([])
        if response.status_code == 404:
            parser.parse([])
            delay = MIN_DELAY
        elif response.status_code >= 400:
            raise SourceFailed(f"robots.txt HTTP {response.status_code} for {host}")
        else:
            parser.parse(response.text.splitlines())
            wild = WildcardRobots(response.text.splitlines())
            raw_delay = parser.crawl_delay(USER_AGENT)
            if raw_delay is None:
                raw_delay = parser.crawl_delay("*")
            delay = max(MIN_DELAY, float(raw_delay or MIN_DELAY))
        # parse() does not mark the file as read. can_fetch() then refuses every URL.
        parser.last_checked = time.time()
        self._robots[host] = parser
        self._wild[host] = wild
        self._delay[host] = delay

    def _pause(self, host: str) -> None:
        delay = max(MIN_DELAY, self._delay.get(host, MIN_DELAY))
        last = self._last.get(host)
        if last is not None:
            remain = delay - (time.monotonic() - last)
            if remain > 0:
                time.sleep(remain)
        self._last[host] = time.monotonic()
