"""Wellfound public job list. /search is not collected."""

from __future__ import annotations

import re

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import posting_item


class WellfoundConnector(OpenListConnector):
    name = "Wellfound"
    entry_url = "https://wellfound.com/jobs"

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if "/search" in urlparse_path(url):
                continue
            if path_is(url, r"/jobs/\d+-[^/]+"):
                urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        if not item["external_id"]:
            found = re.search(r"/jobs/(\d+)", url)
            item["external_id"] = found.group(1) if found else ""
        return item


def urlparse_path(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).path
