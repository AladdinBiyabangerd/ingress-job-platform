"""JobSearch.az public vacancy list. The page body is read, not a private API."""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import clean, html_to_text, meta_content

_TEXT = re.compile(r'text:"((?:\\.|[^"\\])*)"')


class JobSearchConnector(OpenListConnector):
    name = "JobSearch.az"
    entry_url = "https://jobsearch.az/vacancies"

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if path_is(url, r"/vacancies/.+-\d+"):
                urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        og = meta_content(soup, "property", "og:title")
        match = re.match(r"^(.*?)\s+-\s+(.*?)\s+\|\s+JobSearch\.az$", og)
        if match:
            title = clean(match.group(1))
            company = clean(match.group(2))
        else:
            title = clean(re.sub(r"\s*\|\s*JobSearch\.az\s*$", "", og))
            company = ""
        text = _embedded_text(html)
        if not text:
            text = meta_content(soup, "name", "description")
        found = re.search(r"-(\d+)$", url.rstrip("/").rsplit("/", 1)[-1])
        if not title:
            return None
        return {
            "title": title,
            "company": company,
            "city": "",
            "text": text,
            "external_id": found.group(1) if found else "",
        }


def _embedded_text(html: str) -> str:
    chosen = ""
    for raw in _TEXT.findall(html or ""):
        if "\\u003C" not in raw and "<" not in raw:
            continue
        if len(raw) > len(chosen):
            chosen = raw
    if not chosen:
        return ""
    try:
        decoded = json.loads('"' + chosen + '"')
    except json.JSONDecodeError:
        return ""
    return html_to_text(str(decoded))
