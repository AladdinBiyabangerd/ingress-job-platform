"""HelloJob vacancy pages from the public sitemap."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from worker.connectors.sitemap import SitemapConnector, vacancy_sitemap
from worker.parsing import clean, html_to_text, meta_content


class HelloJobConnector(SitemapConnector):
    name = "HelloJob"
    entry_url = "https://www.hellojob.az/sitemap.xml"

    def accept_sitemap(self, url: str) -> bool:
        return vacancy_sitemap(url)

    def accept_page(self, url: str) -> bool:
        from urllib.parse import urlparse
        path = urlparse(url).path
        return path.startswith("/vakansiya/") and path.count("/") == 2

    def parse_page(self, html: str, url: str) -> dict | None:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.select_one("h1.section-title") or soup.select_one("h2.vacancies__subTitle")
        title = clean(heading.get_text(" ", strip=True) if heading else "")
        company_el = soup.select_one("a.vacancies__category")
        company = clean(company_el.get_text(" ", strip=True) if company_el else "")
        city = ""
        for item in soup.select("ul.company__item__details li"):
            label_el = item.find("span")
            label = clean(label_el.get_text(" ", strip=True) if label_el else "").casefold()
            if label in {"şəhər", "seher", "city"}:
                value = item.find("p")
                city = clean(value.get_text(" ", strip=True) if value else "")
                break
        body = soup.select_one(".company__text") or soup.select_one(".vacancies__desc")
        text = html_to_text(str(body)) if body else ""
        if not text:
            text = meta_content(soup, "name", "description")
        row = soup.select_one(".company__row")
        external_id = clean(row.get("data-id")) if row is not None else ""
        if not external_id:
            match = re.search(r"(\d+)$", url.rstrip("/").rsplit("/", 1)[-1])
            external_id = match.group(1) if match else ""
        if not title:
            return None
        return {
            "title": title,
            "company": company,
            "city": city,
            "text": text,
            "external_id": external_id,
        }
