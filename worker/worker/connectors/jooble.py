"""Jooble REST API (https://jooble.org/api/about) with a metered key.

The key allows 500 requests in total, so this source is deliberately small:
- read at most every 6 hours (min_interval_hours),
- a few IT keyword queries per pass, page 1 only (3 requests per pass,
  JOOBLE_MAX_QUERIES can lower it),
- every request is counted in the api_usage table before it is sent, and the
  connector sends nothing once JOOBLE_MONTHLY_BUDGET (default 450) requests
  were used in the current calendar month (UTC).

The key sits in the URL path, so it is never written to logs or run errors:
every error message shows "jooble.org/api/<key>" instead.

Jooble's links point to jooble.org redirect pages. We store and show that link
as Jooble asks API partners to; the worker never fetches it (robots.txt keeps
crawlers off /desc/ and /away/, and nothing here crawls them).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from worker.connectors.feed import FeedConnector, text_from_html
from worker.http import SourceFailed
from worker.parsing import clean
from worker.techstack import is_tech_job

KEY_ENV = "JOOBLE_API_KEY"
DEFAULT_BUDGET = 450
SHOWN = "jooble.org/api/<key>"


def _int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        value = default
    return max(low, min(high, value))


def month_period(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


class JoobleConnector(FeedConnector):
    name = "Jooble"
    entry_url = "https://jooble.org/api/"
    min_interval_hours = 6
    credit_note = "Jobs from the Jooble API (jooble.org). The link opens the offer through Jooble."
    queries = (
        "remote software developer",
        "relocation software engineer",
        "remote devops engineer",
    )

    def __init__(self, client, store) -> None:
        super().__init__(client, store)
        self.key = os.environ.get(KEY_ENV, "").strip()
        self.budget = _int_env("JOOBLE_MONTHLY_BUDGET", DEFAULT_BUDGET, 0, 500)
        self.max_queries = _int_env("JOOBLE_MAX_QUERIES", len(self.queries), 0, len(self.queries))

    def requests_left(self) -> int:
        return max(0, self.budget - self.store.api_requests_used(self.name, month_period()))

    def feed_items(self) -> list[dict]:
        if not self.key:
            raise SourceFailed(f"{KEY_ENV} is not set")
        out: list[dict] = []
        url = self.entry_url + self.key
        for keywords in self.queries[: self.max_queries]:
            if self.requests_left() <= 0:
                print(f"{self.name}: monthly request budget ({self.budget}) used up, no request sent", flush=True)
                break
            self.store.add_api_requests(self.name, month_period())
            payload = self.client.post_json(url, {"keywords": keywords, "page": "1"}, shown=SHOWN)
            jobs = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(jobs, list):
                raise SourceFailed(f"{SHOWN} answer had no jobs list")
            for job in jobs:
                if not isinstance(job, dict):
                    continue
                title = clean(job.get("title"))
                if not title or not is_tech_job(title):
                    continue
                kind = clean(job.get("type"))
                salary = clean(job.get("salary"))
                text = text_from_html(job.get("snippet"))
                extra = " | ".join(x for x in (kind, salary) if x)
                out.append({
                    "title": title,
                    "company": clean(job.get("company")),
                    "city": clean(job.get("location")),
                    "text": f"{text}\n\n{extra}".strip() if extra else text,
                    "source_url": str(job.get("link") or "").strip(),
                    "external_id": f"jooble-{job.get('id')}" if job.get("id") else "",
                    "tags": [kind] if kind else [],
                })
        return out

    def discover(self) -> list[str]:
        # Not FeedConnector.discover: that checks robots.txt for every item
        # link before a fetch. Jooble's links are never fetched (see the
        # module note); only the API endpoint itself is requested, and
        # post_json checks robots.txt for it.
        items = self.feed_items()
        urls: list[str] = []
        for item in items:
            url = item.get("source_url") or ""
            if not url.startswith(("https://", "http://")) or url in self._items:
                continue
            if self.store.has_source_url(url):
                continue
            self._items[url] = item
            urls.append(url)
            if len(urls) >= self.candidates:
                break
        return urls

    def fetch(self, url: str) -> str:
        item = self._items.get(url)
        if item is None:
            raise SourceFailed("jooble item missing")
        return json.dumps(item, ensure_ascii=False)
