"""Glorri public vacancy pages. Next.js assets are not fetched."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import clean, html_to_text, meta_content

_COUNTRY = {"azerbaijan", "azərbaycan", "aze"}
_SECTIONS = {"təsvir", "tələblər", "iş barədə məlumat", "iş şəraiti"}


class GlorriConnector(OpenListConnector):
    name = "Glorri"
    entry_url = "https://jobs.glorri.az/"

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if path_is(url, r"/vacancies/[^/]+/[^/]+"):
                urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        title = clean(heading.get_text(" ", strip=True) if heading else "")
        company = ""
        for company_el in soup.select('a[href^="/companies/"]'):
            company = clean(company_el.get_text(" ", strip=True))
            if company:
                break
        city = _city(heading)
        text = _sections(soup)
        if not text:
            text = meta_content(soup, "name", "description")
        found = re.search(r"-(\d+)$", url.rstrip("/").rsplit("/", 1)[-1])
        if not title:
            return None
        return {
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": found.group(1) if found else "",
        }


def _city(heading) -> str:
    if heading is None:
        return ""
    box = heading.find_next("ul")
    if box is None:
        return ""
    for item in box.find_all("li"):
        if item.find("a"):
            continue
        raw = clean(item.get_text(" ", strip=True))
        if "," not in raw:
            continue
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        if not parts:
            continue
        if parts[-1].casefold() in _COUNTRY and len(parts) >= 2:
            return parts[-2]
        return parts[-1]
    return ""


def _sections(soup: BeautifulSoup) -> str:
    chunks: list[str] = []
    for heading in soup.find_all("h3"):
        classes = " ".join(heading.get("class") or [])
        if "text-2xl" not in classes:
            continue
        label = clean(heading.get_text(" ", strip=True))
        if label.casefold() not in _SECTIONS:
            continue
        body = heading.find_next_sibling()
        if body is None:
            continue
        text = html_to_text(str(body))
        if text:
            chunks.append(f"{label}\n{text}")
    return "\n\n".join(chunks)[:20000]
