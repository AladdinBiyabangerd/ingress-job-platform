"""Open HTML listings. One public page, then each job URL. No query strings."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from worker.connectors.sitemap import CANDIDATES
from worker.db import Store
from worker.http import NotFound, PoliteClient, SourceBlocked
from worker.parsing import clean


class OpenListConnector:
    name = ""
    entry_url = ""

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store

    def list_pages(self) -> list[str]:
        return [self.entry_url]

    def links(self, html: str, page_url: str) -> list[str]:
        raise NotImplementedError

    def parse_page(self, html: str, url: str) -> dict | None:
        raise NotImplementedError

    def discover(self) -> list[str]:
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        found: list[str] = []
        seen: set[str] = set()
        for page in self.list_pages():
            if len(found) >= CANDIDATES:
                break
            if not self.client.allowed(page):
                continue
            try:
                html = self.client.get_text(page)
            except NotFound:
                if page == self.entry_url:
                    raise
                continue
            for url in self.links(html, page):
                if url in seen or self.store.has_source_url(url):
                    continue
                if not self._ok(url):
                    continue
                seen.add(url)
                found.append(url)
                if len(found) >= CANDIDATES:
                    break
        return found

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

    def _ok(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.query or not parsed.netloc:
            return False
        if not self._same_site(url):
            return False
        return self.client.allowed(url)

    def _same_site(self, url: str) -> bool:
        return urlparse(url).netloc.lower().removeprefix("www.") == urlparse(
            self.entry_url
        ).netloc.lower().removeprefix("www.")


def page_links(html: str, page_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        url = absolute_url(page_url, str(anchor.get("href") or ""))
        if not url or url in seen:
            continue
        seen.add(url)
        found.append((url, clean(anchor.get_text(" ", strip=True))))
    return found


def absolute_url(base: str, href: str) -> str:
    joined = urljoin(base, (href or "").strip())
    parsed = urlparse(joined)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
