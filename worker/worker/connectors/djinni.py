"""Djinni public RSS of open jobs. Closed ads, /jobs2 and /q are not collected.

One RSS feed returns only the newest 100 ads and has no pagination, so we
read one feed per IT ``primary_keyword`` (the same list Djinni publishes as
/jobs/keyword-* in its sitemap) and, when a feed is full, its
``employment=remote`` slice too. Non-IT keywords (sales, HR, marketing,
design, finance, C-level business roles ...) are never requested."""

from __future__ import annotations

import re
import time
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from worker.db import Store
from worker.http import PoliteClient, SourceBlocked, SourceFailed
from worker.market_fit import is_rejected, mark_rejected
from worker.parsing import clean, html_to_text, job_postings, meta_content
from worker.techstack import is_tech_job

_JOB = re.compile(r"/jobs/(\d+)-[^/]+/?$")
FEED = "https://djinni.co/jobs/rss/"
FEED_SIZE = 100  # Djinni caps every RSS feed at 100 items.

# IT primary keywords from https://djinni.co/sitemap.xml (/jobs/keyword-*).
IT_KEYWORDS: tuple[str, ...] = (
    "python", "java", "javascript", "node_js", "react", "angular", "vue",
    "fullstack", "markup", "php", "laravel", "symfony", "magento", "drupal",
    "wordpress", "ruby", "golang", "rust", "scala", "elixir", "kotlin",
    "c", "cpp", "cplusplus", "dotnet", "dotnet_web", "dotnet_cloud",
    "dotnet_desktop", "asp_net", "wpf", "winforms", "ios", "android",
    "flutter", "react_native", "embedded", "gamedev", "game_developer",
    "unity", "unreal", "qa_automation", "qa_manual", "dev_ops", "sysadmin",
    "sql_dba", "data_engineer", "data_science", "data_analyst", "ml_ai",
    "architect", "security", "information_security", "security_analyst",
    "penetration_tester", "salesforce", "sap", "odoo", "ms_dynamics",
    "erp_systems", "technical_writing", "support", "engineering_manager",
    "lead", "cto", "business_analyst", "product_manager", "project_manager",
    "delivery_manager", "scrum_master", "product_owner", "ui_ux",
    "product_design", "ux_research", "finops", "no_code", "web_analyst",
)
# Detail pages fetched per run. Measured ~1.15 s/page with politeness, so a
# full first pass is ~38 min; later hourly runs only open new links.
# The RSS carries no location/remote field (only title, link, description,
# category) and Djinni's employment=office slice overlaps remote ads, so no
# location prefilter is safe; remote-slice links are just opened first.
MAX_CANDIDATES = 2000
RETRIES = 3
BACKOFF = (2.0, 6.0)


class DjinniConnector:
    name = "Djinni"
    entry_url = FEED
    # Djinni-specific limits (runner default is 30 new rows per source run).
    create_cap = 300
    max_candidates = MAX_CANDIDATES
    # A detail page that still fails after retries is skipped (runner).
    skip_failed_pages = True

    def __init__(self, client: PoliteClient, store: Store, keywords=None) -> None:
        self.client = client
        self.store = store
        self.keywords = tuple(keywords) if keywords is not None else IT_KEYWORDS
        self.stats: dict[str, int] = {}

    def _retry(self, fn, *args, **kw):
        """Transient request/robots failures are retried with backoff."""
        last: Exception | None = None
        for attempt in range(RETRIES):
            try:
                return fn(*args, **kw)
            except SourceFailed as exc:
                last = exc
                if attempt < RETRIES - 1:
                    time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
        assert last is not None
        raise last

    def feed_urls(self) -> list[str]:
        return [f"{FEED}?primary_keyword={k}" for k in self.keywords]

    def _read_feed(self, url: str) -> list[ET.Element]:
        text = self._retry(
            self.client.get_text,
            url,
            accept="application/rss+xml,application/xml,text/xml,*/*",
        )
        try:
            root = ET.fromstring(text.lstrip("\ufeff").encode("utf-8"))
        except ET.ParseError as exc:
            raise SourceFailed(f"rss unreadable: {exc.__class__.__name__}") from exc
        return list(root.iter("item"))

    def discover(self) -> list[str]:
        if not self._retry(self.client.allowed, self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        conn = getattr(self.store, "conn", None)
        urls: list[str] = []
        seen: set[str] = set()
        st = {"feeds": 0, "feed_errors": 0, "items": 0, "known": 0, "non_it": 0}
        self.rss_meta: dict[str, dict] = {}
        self._remote_links: set[str] = set()
        queue = self.feed_urls()
        i = 0
        while i < len(queue):
            feed = queue[i]
            i += 1
            try:
                items = self._read_feed(feed)
            except SourceBlocked:
                raise
            except SourceFailed:
                st["feed_errors"] += 1
                continue
            st["feeds"] += 1
            if len(items) >= FEED_SIZE and "employment=" not in feed:
                queue.append(feed + "&employment=remote")
            for item in items:
                link = _link(item)
                if link and "employment=remote" in feed:
                    self._remote_links.add(link)
                if not link or not _JOB.search(link) or link in seen:
                    continue
                seen.add(link)
                st["items"] += 1
                if self.store.has_source_url(link) or is_rejected(conn, link):
                    st["known"] += 1
                    continue
                title = clean(_text(item, "title"))
                category = next(
                    (clean(c.text or "") for c in item.findall("category") if (c.text or "").strip()),
                    "",
                )
                # Same first gate finish_item applies, without opening the page.
                if title and not is_tech_job(title, category, [category] if category else []):
                    mark_rejected(conn, link, "non_it", via_ai=False)
                    st["non_it"] += 1
                    continue
                if not self.client.allowed(link):
                    continue
                self.rss_meta[link] = {"category": category}
                urls.append(link)
        if st["feeds"] == 0:
            raise SourceFailed("all Djinni feeds failed")
        if conn is not None:
            conn.commit()
        st["candidates"] = len(urls)
        # Order only (never accept/reject): links seen in remote slices first.
        remote_first = [u for u in urls if u in self._remote_links]
        urls = remote_first + [u for u in urls if u not in self._remote_links]
        urls = urls[: self.max_candidates]
        self.stats = st
        return urls

    def fetch(self, url: str) -> str:
        return self._retry(self.client.get_text, url)

    def normalize(self, raw: str, url: str) -> dict | None:
        try:
            return self.parse_page(raw, url)
        except Exception:
            return None

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        for alert in soup.select(".alert"):
            if "no longer active" in alert.get_text(" ", strip=True).lower():
                return None
        og = meta_content(soup, "property", "og:title")
        if " at " in og:
            title, company = og.rsplit(" at ", 1)
            title, company = clean(title), clean(company)
        else:
            heading = soup.find("h1")
            title = clean(heading.get_text(" ", strip=True) if heading else og)
            company = ""
        place = soup.select_one(".location-text")
        city = clean(place.get_text(" ", strip=True) if place else "")
        body = soup.select_one(".job-post__description")
        text = html_to_text(str(body)) if body else ""
        if not text:
            text = meta_content(soup, "name", "description")
        found = _JOB.search(url)
        if not title:
            return None
        postings = job_postings(html)
        posting = postings[0] if postings else {}
        category = clean(posting.get("category")) if posting else ""
        if not category:
            category = (getattr(self, "rss_meta", {}).get(url) or {}).get("category", "")
        remote, relocation = _work_mode(soup, posting)
        countries = _applicant_countries(posting)
        if countries and not city:
            city = ", ".join(countries)
        item = {
            # Djinni's own category, e.g. "Python", "QA Manual" or "Sales".
            "category": category,
            "tags": [category] if category else [],
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": found.group(1) if found else "",
            "posted_at": (posting.get("datePosted") if posting else "") or "",
            "source_url": url,
            "source_name": self.name,
        }
        # Only positive structured signals are passed; rules decide the rest.
        if remote:
            item["remote"] = True
        if relocation:
            item["relocation"] = True
        return item

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)


def _link(item: ET.Element) -> str:
    el = item.find("link")
    raw = (el.text or "").strip() if el is not None else ""
    if not raw:
        return ""
    from worker.connectors.openlist import absolute_url
    return absolute_url(raw, raw)


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None else ""


_REMOTE_BADGE = re.compile(r"^(full(y)?\s+remote|remote(\s+work)?|віддалено|удаленно)$", re.I)
_RELOC_BADGE = re.compile(r"relocat|релокац", re.I)


def _work_mode(soup: BeautifulSoup, posting: dict) -> tuple[bool, bool]:
    """Djinni marks remote ads with JSON-LD jobLocationType=TELECOMMUTE and a
    'Full Remote' badge; relocation help is a badge in the same info list."""
    remote = str(posting.get("jobLocationType") or "").upper() == "TELECOMMUTE"
    relocation = False
    for badge in soup.select("strong.font-weight-600, .job-additional-info--item-text"):
        label = clean(badge.get_text(" ", strip=True))
        if not label or len(label) > 60:
            continue
        if _REMOTE_BADGE.match(label):
            remote = True
        if _RELOC_BADGE.search(label):
            relocation = True
    return remote, relocation


def _applicant_countries(posting: dict) -> list[str]:
    req = posting.get("applicantLocationRequirements") if posting else None
    reqs = req if isinstance(req, list) else [req] if req else []
    out: list[str] = []
    for r in reqs:
        if not isinstance(r, dict):
            continue
        addr = r.get("address") if isinstance(r.get("address"), dict) else {}
        name = clean(str(r.get("name") or addr.get("addressCountry") or ""))
        if name and name not in out:
            out.append(name)
    return out
