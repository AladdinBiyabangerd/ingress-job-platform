"""Sitemap discovery shared by the Azerbaijan job boards."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from worker.db import Store
from worker.http import Disallowed, PoliteClient, SourceBlocked, SourceFailed
from worker.parsing import last_number, parse_sitemap

CANDIDATES = 80


class SitemapConnector:
    name = ""
    entry_url = ""

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store

    def accept_sitemap(self, url: str) -> bool:
        return False

    def accept_page(self, url: str) -> bool:
        return False

    def parse_page(self, html: str, url: str) -> dict | None:
        raise NotImplementedError

    def discover(self) -> list[str]:
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        pages = self._collect(self.entry_url, depth=0)
        fresh = [url for url in pages if not self.store.has_source_url(url)]
        fresh.sort(key=last_number, reverse=True)
        return fresh[:CANDIDATES]

    def fetch(self, url: str) -> str:
        return self.client.get_text(url)

    def normalize(self, raw: str, url: str) -> dict | None:
        try:
            item = self.parse_page(raw, url)
        except Exception:
            return None
        if not item or not str(item.get("title") or "").strip():
            return None
        item["source_url"] = url
        item["source_name"] = self.name
        return item

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)

    def _collect(self, url: str, depth: int) -> list[str]:
        if depth > 4:
            return []
        if not self.client.allowed(url):
            if depth == 0:
                raise SourceBlocked(f"robots.txt disallows {url}")
            return []
        try:
            text = self.client.get_text(url, accept="application/xml,text/xml,*/*")
            is_index, locs = parse_sitemap(text)
        except (Disallowed, SourceBlocked, SourceFailed) as exc:
            if depth == 0 and isinstance(exc, Disallowed):
                raise SourceBlocked(f"robots.txt disallows {url}") from exc
            raise
        except Exception as exc:
            if depth == 0:
                raise SourceFailed(f"sitemap unreadable: {exc.__class__.__name__}") from exc
            return []
        if not is_index:
            return [item for item in locs if self._page_ok(item)]
        children = [item for item in locs if self.accept_sitemap(item) and self._same_site(item)]
        if len(children) > 1:
            children = [children[-1]]
        found: list[str] = []
        for child in children:
            found.extend(self._collect(child, depth + 1))
        return found

    def _page_ok(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.query:
            return False
        if not self._same_site(url):
            return False
        if not self.accept_page(url):
            return False
        return self.client.allowed(url)

    def _same_site(self, url: str) -> bool:
        return urlparse(url).netloc.lower().removeprefix("www.") == urlparse(self.entry_url).netloc.lower().removeprefix("www.")


def vacancy_sitemap(url: str) -> bool:
    path = urlparse(url).path.lower()
    if any(bad in path for bad in ("expired", "compan", "blog", "categor", "position", "jobseeker", "profession", "cities", "pages", "resume")):
        return False
    return "vacanc" in path


def path_is(url: str, pattern: str) -> bool:
    return re.fullmatch(pattern, urlparse(url).path) is not None
