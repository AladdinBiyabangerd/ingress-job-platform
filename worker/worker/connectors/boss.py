"""Boss.az vacancy pages from the public sitemap."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from worker.connectors.sitemap import SitemapConnector, path_is
from worker.parsing import clean, meta_content, styled_text


class BossConnector(SitemapConnector):
    name = "Boss.az"
    entry_url = "https://boss.az/sitemap.xml"

    def accept_sitemap(self, url: str) -> bool:
        return False

    def accept_page(self, url: str) -> bool:
        return path_is(url, r"/vacancies/\d+")

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        title = clean(heading.get_text(" ", strip=True) if heading else "")
        company = ""
        city = ""
        og = meta_content(soup, "property", "og:title")
        match = re.search(
            r"^(.*?)\s+şirkətində\s+(.*?)\s+vakansiyası\s*,\s*([^|]+?)\s*\|",
            og,
        )
        if match:
            company = clean(match.group(1))
            if not title:
                title = clean(match.group(2))
            city = clean(match.group(3))
        text = styled_text(html, soup, "Content-styles__TextContent")
        if not text:
            text = meta_content(soup, "name", "description")
        found = re.search(r"/vacancies/(\d+)", url)
        if not title:
            return None
        return {
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": found.group(1) if found else "",
        }
