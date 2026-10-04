"""eJob.az vacancy sitemap only. Resume sitemaps are not read."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from worker.connectors.sitemap import SitemapConnector, path_is
from worker.parsing import html_to_text, posting_item


class EjobConnector(SitemapConnector):
    name = "eJob.az"
    entry_url = "https://ejob.az/sitemap/sitemap.xml"

    def accept_sitemap(self, url: str) -> bool:
        return urlparse(url).path.lower().endswith("/sitemap_vc.xml")

    def accept_page(self, url: str) -> bool:
        return path_is(url, r"/is-elani/\d+-[^/]+/?")

    def parse_page(self, html: str, url: str) -> dict | None:
        item = posting_item(html)
        if not item:
            return None
        soup = BeautifulSoup(html, "html.parser")
        table = soup.select_one("table.description")
        if table is not None:
            text = html_to_text(str(table))
            if len(text) > len(item["text"]):
                item["text"] = text
        if not item["external_id"]:
            found = re.search(r"/is-elani/(\d+)", url)
            item["external_id"] = found.group(1) if found else ""
        return item
