"""Reed.co.uk Jobseeker API (https://www.reed.co.uk/developers/jobseeker).

Keyed official API: HTTP Basic with REED_API_KEY as the user name and an empty
password. The key is never put in a URL, a log line or a run error.

Kept small and polite:
- read at most every 6 hours (min_interval_hours), 1 request per second
  (PoliteClient's per-host delay),
- a few IT keyword searches per pass, first page only (resultsToTake=50),
- the details call (/jobs/{id}, full description) only for new tech ads,
  at most `candidates` per pass,
- every request is counted in api_usage before it is sent; nothing is sent
  once REED_MONTHLY_BUDGET (default 3000, a soft cap: Reed publishes none)
  requests were used in the current calendar month (UTC).

robots.txt still applies: PoliteClient checks the exact API URL first, and
www.reed.co.uk/robots.txt currently has "Disallow: /api/" for every user
agent. While that stays, the connector refuses before any API request and
before any budget is spent (see catalog note).

Reed's own "applications" count is not stored: it is not our on-site
applications and there is no column for it.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from worker.connectors.feed import FeedConnector, text_from_html
from worker.http import SourceBlocked, SourceFailed
from worker.parsing import clean
from worker.techstack import is_tech_job

KEY_ENV = "REED_API_KEY"
DEFAULT_BUDGET = 3000
API = "https://www.reed.co.uk/api/1.0"


def _int_env(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        value = default
    return max(low, min(high, value))


def month_period(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m")


def _money(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return ""
    if number <= 0:
        return ""
    return f"{number:,.2f}".rstrip("0").rstrip(".") if number < 1000 else f"{number:,.0f}"


def salary_text(low: object, high: object, currency: object = "GBP", period: object = "") -> str:
    """'45,000–55,000 GBP per annum'; '' when Reed hides the salary."""
    lo, hi = _money(low), _money(high)
    if not lo and not hi:
        return ""
    amount = lo if (lo == hi or not hi) else (hi if not lo else f"{lo}–{hi}")
    unit = clean(currency).upper() or "GBP"
    tail = clean(period).lower()
    return " ".join(x for x in (amount, unit, tail) if x)


class ReedConnector(FeedConnector):
    name = "Reed.co.uk"
    entry_url = f"{API}/search"
    min_interval_hours = 6
    candidates = 30
    credit_note = "Jobs from the Reed.co.uk Jobseeker API. The link opens the original ad on reed.co.uk."
    # Remote first, then UK tech roles.
    queries = (
        "remote software developer",
        "software engineer",
        "devops engineer",
        "data engineer",
        "frontend developer",
    )
    take = 50

    def __init__(self, client, store) -> None:
        super().__init__(client, store)
        self.key = os.environ.get(KEY_ENV, "").strip()
        self.budget = _int_env("REED_MONTHLY_BUDGET", DEFAULT_BUDGET, 0, 100000)
        self.max_queries = _int_env("REED_MAX_QUERIES", len(self.queries), 0, len(self.queries))

    # ---- budget

    def requests_left(self) -> int:
        return max(0, self.budget - self.store.api_requests_used(self.name, month_period()))

    def _call(self, url: str, shown: str):
        if self.requests_left() <= 0:
            return None
        self.store.add_api_requests(self.name, month_period())
        return self.client.get_json(url, auth=(self.key, ""), shown=shown)

    # ---- search

    def feed_items(self) -> list[dict]:
        if not self.key:
            raise SourceFailed(f"{KEY_ENV} is not set")
        probe_url = f"{self.entry_url}?keywords=software"
        if not self.client.allowed(probe_url):
            # Checked before any request or budget is spent.
            raise SourceBlocked("robots.txt disallows www.reed.co.uk/api/ (Disallow: /api/)")
        out: list[dict] = []
        for keywords in self.queries[: self.max_queries]:
            query = urlencode({"keywords": keywords, "resultsToTake": self.take, "resultsToSkip": 0})
            payload = self._call(f"{self.entry_url}?{query}", shown=f"reed.co.uk/api/1.0/search ({keywords})")
            if payload is None:
                print(f"{self.name}: monthly request budget ({self.budget}) used up, no request sent", flush=True)
                break
            rows = payload.get("results") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise SourceFailed("reed search answer had no results list")
            for job in rows:
                if not isinstance(job, dict) or not job.get("jobId"):
                    continue
                title = clean(job.get("jobTitle"))
                if not title or not is_tech_job(title):
                    continue
                place = clean(job.get("locationName"))
                low_place = place.lower()
                remote = True if ("remote" in low_place or "work from home" in low_place) else None
                out.append({
                    "title": title,
                    "company": clean(job.get("employerName")),
                    "city": place,
                    "text": text_from_html(job.get("jobDescription")),
                    "source_url": str(job.get("jobUrl") or f"https://www.reed.co.uk/jobs/{job['jobId']}").strip(),
                    "external_id": f"reed-{job['jobId']}",
                    "salary": salary_text(job.get("minimumSalary"), job.get("maximumSalary"),
                                          job.get("currency") or "GBP"),
                    "remote": remote,
                    "_job_id": int(job["jobId"]),
                })
        # The same ad can come back from several searches; remote ones first.
        seen: set[int] = set()
        unique = []
        for item in out:
            if item["_job_id"] in seen:
                continue
            seen.add(item["_job_id"])
            unique.append(item)
        unique.sort(key=lambda r: 0 if r.get("remote") else 1)
        return unique

    def discover(self) -> list[str]:
        urls = super().discover()
        # Never queue more detail calls than the month has left.
        return urls[: max(0, min(len(urls), self.requests_left()))]

    # ---- details (new ads only: discover already skipped stored URLs)

    def fetch(self, url: str) -> str:
        item = self._items.get(url)
        if item is not None and item.get("_job_id"):
            job_id = item.pop("_job_id")
            detail = self._call(f"{API}/jobs/{job_id}", shown=f"reed.co.uk/api/1.0/jobs/{job_id}")
            if isinstance(detail, dict) and detail:
                text = text_from_html(detail.get("jobDescription"))
                if len(text) > len(item.get("text") or ""):
                    item["text"] = text
                pay = salary_text(
                    detail.get("yearlyMinimumSalary") or detail.get("minimumSalary"),
                    detail.get("yearlyMaximumSalary") or detail.get("maximumSalary"),
                    detail.get("currency") or "GBP",
                    "per annum" if detail.get("yearlyMinimumSalary") or detail.get("yearlyMaximumSalary")
                    else detail.get("salaryType"),
                )
                if pay:
                    item["salary"] = pay
                kinds = [clean(detail.get(k)) for k in ("contractType", "jobType") if clean(detail.get(k))]
                if kinds:
                    item["tags"] = kinds
                    item["text"] = f"{item['text']}\n\n{' | '.join(kinds)}".strip()
                for key, field in (("company", "employerName"), ("city", "locationName")):
                    if not item.get(key) and clean(detail.get(field)):
                        item[key] = clean(detail.get(field))
        return super().fetch(url)
