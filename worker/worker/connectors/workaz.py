"""Work.az public vacancy list. Login and cabinet paths are not fetched."""

from __future__ import annotations

import re

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import posting_item


class WorkAzConnector(OpenListConnector):
    name = "Work.az"
    entry_url = "https://www.work.az/vakansiyalar"

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if path_is(url, r"/vakansiyalar/[^/]+"):
                urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        if not item["external_id"]:
            found = re.search(r"/vakansiyalar/([^/]+)$", url)
            item["external_id"] = found.group(1) if found else ""
        return item
