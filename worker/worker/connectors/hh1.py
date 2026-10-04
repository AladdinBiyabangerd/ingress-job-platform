"""hh1.az public vacancy pages. Not the hh.ru API. No query string, RSS, or resumes."""

from __future__ import annotations

import re

from worker.connectors.openlist import OpenListConnector, absolute_url
from worker.connectors.sitemap import path_is
from worker.parsing import posting_item

_HREF = re.compile(r"""href=["']([^"'#]+)["']""", re.IGNORECASE)


class Hh1Connector(OpenListConnector):
    name = "hh1.az"
    entry_url = "https://hh1.az/vacancies"

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()
        for href in _HREF.findall(html or ""):
            url = absolute_url(page_url, href)
            if not url or url in seen:
                continue
            if not path_is(url, r"/vacancy/\d+"):
                continue
            seen.add(url)
            urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        if not item["external_id"]:
            found = re.search(r"/vacancy/(\d+)", url)
            item["external_id"] = found.group(1) if found else ""
        return item
