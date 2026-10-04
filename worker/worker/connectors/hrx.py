"""HRX public vacancy list. /api/ is not called. The blocked sitemap is not used."""

from __future__ import annotations

import re

from worker.connectors.openlist import OpenListConnector, page_links
from worker.connectors.sitemap import path_is
from worker.parsing import posting_item

_JOB = r"/is-elanlari/[^/]+/[^/]+/.+-[0-9a-fA-F]{6}"


class HrxConnector(OpenListConnector):
    name = "HRX"
    entry_url = "https://hrx.az/is-elanlari"

    def list_pages(self) -> list[str]:
        return [
            self.entry_url,
            "https://hrx.az/is-elanlari/sehife/2",
            "https://hrx.az/is-elanlari/sehife/3",
        ]

    def links(self, html: str, page_url: str) -> list[str]:
        urls: list[str] = []
        for url, _text in page_links(html, page_url):
            if "/api/" in urlparse_path(url):
                continue
            if path_is(url, _JOB):
                urls.append(url)
        return urls

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        if not item["external_id"]:
            found = re.search(r"-([0-9a-fA-F]{6})$", url.rstrip("/"))
            item["external_id"] = found.group(1) if found else ""
        return item


def urlparse_path(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).path
