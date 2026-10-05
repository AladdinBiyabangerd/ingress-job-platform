"""Djinni public RSS of open jobs. Closed ads, /jobs2 and /q are not collected."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from worker.connectors.sitemap import CANDIDATES
from worker.db import Store
from worker.http import PoliteClient, SourceBlocked, SourceFailed
from worker.parsing import clean, html_to_text, job_postings, meta_content

_JOB = re.compile(r"/jobs/(\d+)-[^/]+/?$")


class DjinniConnector:
    name = "Djinni"
    entry_url = "https://djinni.co/jobs/rss/"

    def __init__(self, client: PoliteClient, store: Store) -> None:
        self.client = client
        self.store = store

    def discover(self) -> list[str]:
        if not self.client.allowed(self.entry_url):
            raise SourceBlocked(f"robots.txt disallows {self.entry_url}")
        try:
            text = self.client.get_text(
                self.entry_url,
                accept="application/rss+xml,application/xml,text/xml,*/*",
            )
            root = ET.fromstring(text.lstrip("\ufeff").encode("utf-8"))
        except (SourceBlocked,):
            raise
        except Exception as exc:
            raise SourceFailed(f"rss unreadable: {exc.__class__.__name__}") from exc
        urls: list[str] = []
        seen: set[str] = set()
        for item in root.iter("item"):
            link = _link(item)
            if not link or not _JOB.search(link):
                continue
            if link in seen or self.store.has_source_url(link):
                continue
            if not self.client.allowed(link):
                continue
            seen.add(link)
            urls.append(link)
            if len(urls) >= CANDIDATES:
                break
        return urls

    def fetch(self, url: str) -> str:
        return self.client.get_text(url)

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
        category = clean(postings[0].get("category")) if postings else ""
        return {
            # Djinni's own category, e.g. "Python", "QA Manual" or "Sales".
            "category": category,
            "tags": [category] if category else [],
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": found.group(1) if found else "",
            "source_url": url,
            "source_name": self.name,
        }

    def upsert(self, item: dict) -> str:
        return self.store.upsert(item)


def _link(item: ET.Element) -> str:
    el = item.find("link")
    raw = (el.text or "").strip() if el is not None else ""
    if not raw:
        return ""
    from worker.connectors.openlist import absolute_url
    return absolute_url(raw, raw)
